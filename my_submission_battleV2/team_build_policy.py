"""
Bulk-First Team Build Policy for VGC 2026 Championship Track.

Builds a team of 6 from a 50-pokemon roster by:
1. Building a 50x50 damage matrix
2. Scoring Pokemon by firepower + bulk (equal weight) + HP bonus — no speed
3. Greedy coverage selection (minimizes damage range across roster)
4. Local swap improvement: try single-member swaps to raise composite score
5. Applying EV/Nature/Move assignments per Pokemon
"""
import numpy as np

from vgc2.agent import TeamBuildPolicy, TeamBuildCommand
from vgc2.balance.meta import Meta, Roster
from vgc2.battle_engine.modifiers import Nature, Type, Category, Stat

TYPE_CHART = np.array([
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, .5, 0, 1, 1, .5, 1, 1],
    [1, .5, .5, 1, 2, 2, 1, 1, 1, 1, 1, 2, .5, 1, .5, 1, 2, 1, 1],
    [1, 2, .5, 1, .5, 1, 1, 1, 2, 1, 1, 1, 2, 1, .5, 1, 1, 1, 1],
    [1, 1, 2, .5, .5, 1, 1, 1, 0, 2, 1, 1, 1, 1, .5, 1, 1, 1, 1],
    [1, .5, 2, 1, .5, 1, 1, .5, 2, .5, 1, .5, 2, 1, .5, 1, .5, 1, 1],
    [1, .5, .5, 1, 2, .5, 1, 1, 2, 2, 1, 1, 1, 1, 2, 1, .5, 1, 1],
    [2, 1, 1, 1, 1, 2, 1, .5, 1, .5, .5, .5, 2, 0, 1, 2, 2, .5, 1],
    [1, 1, 1, 1, 2, 1, 1, .5, .5, 1, 1, 1, .5, .5, 1, 1, 0, 2, 1],
    [1, 2, 1, 2, .5, 1, 1, 2, 1, 0, 1, .5, 2, 1, 1, 1, 2, 1, 1],
    [1, 1, 1, .5, 2, 1, 2, 1, 1, 1, 1, 2, .5, 1, 1, 1, .5, 1, 1],
    [1, 1, 1, 1, 1, 1, 2, 2, 1, 1, .5, 1, 1, 1, 1, 0, .5, 1, 1],
    [1, .5, 1, 1, 2, 1, .5, .5, 1, .5, 2, 1, 1, .5, 1, 2, .5, .5, 1],
    [1, 2, 1, 1, 1, 2, .5, 1, .5, 2, 1, 2, 1, 1, 1, 1, .5, 1, 1],
    [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 2, 1, .5, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, .5, 0, 1],
    [1, 1, 1, 1, 1, 1, .5, 1, 1, 1, 2, 1, 1, 2, 1, .5, 1, .5, 1],
    [1, .5, .5, .5, 1, 2, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, .5, 2, 1],
    [1, .5, 1, 1, 1, 1, 2, .5, 1, 1, 1, 1, 1, 1, 2, 2, .5, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
], dtype=float)


def _get_best_damage_ratio(attacker, defender) -> float:
    best = 0.0
    for move in attacker.moves:
        if move.category not in (Category.PHYSICAL, Category.SPECIAL):
            continue
        base_power = move.base_power + max(0, move.priority) * 10
        if base_power <= 0:
            continue
        atk_stat = attacker.base_stats[Stat.ATTACK] if move.category == Category.PHYSICAL else attacker.base_stats[Stat.SPECIAL_ATTACK]
        def_stat = defender.base_stats[Stat.DEFENSE] if move.category == Category.PHYSICAL else defender.base_stats[Stat.SPECIAL_DEFENSE]
        def_stat = max(def_stat, 1)
        stab = 1.5 if move.pkm_type in attacker.types else 1.0
        eff = 1.0
        for dt in defender.types:
            eff *= TYPE_CHART[move.pkm_type, dt]
        dmg = int((2 * 50 / 5) + 2)
        dmg = int(dmg * base_power)
        dmg = int(dmg * atk_stat / def_stat)
        dmg = int(dmg / 50) + 2
        final = int(dmg * stab * eff)
        max_hp = max(defender.base_stats[Stat.MAX_HP], 1)
        best = max(best, final / max_hp)
    return best


def _score_bulk(species) -> float:
    hp_ratio = max(species.base_stats[Stat.MAX_HP], 1) / 150
    def_ratio = max(species.base_stats[Stat.DEFENSE], 1) / 150
    spd_ratio = max(species.base_stats[Stat.SPECIAL_DEFENSE], 1) / 150
    return hp_ratio * def_ratio * spd_ratio


def _determine_orientation(species):
    phy_total = sum(m.base_power * species.base_stats[Stat.ATTACK] for m in species.moves if m.category == Category.PHYSICAL)
    spc_total = sum(m.base_power * species.base_stats[Stat.SPECIAL_ATTACK] for m in species.moves if m.category == Category.SPECIAL)
    if phy_total > spc_total * 1.2:
        return 'physical'
    elif spc_total > phy_total * 1.2:
        return 'special'
    return 'mixed'


def _select_best_moves(species, max_moves: int) -> list[int]:
    scores = []
    for i, move in enumerate(species.moves):
        score = 0.0
        if move.category in (Category.PHYSICAL, Category.SPECIAL):
            stab = 1.5 if move.pkm_type in species.types else 1.0
            atk = species.base_stats[Stat.ATTACK] if move.category == Category.PHYSICAL else species.base_stats[Stat.SPECIAL_ATTACK]
            score = move.base_power * move.accuracy * stab * atk / 100.0
            if move.priority > 0:
                score *= 1.2
        else:
            score = 30.0
            if move.protect:
                score = 150.0
            if move.toggle_tailwind:
                score = 100.0
            if move.toggle_reflect or move.toggle_lightscreen:
                score = 80.0
            if any(b != 0 for b in move.boosts):
                score = 60.0
        scores.append((i, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    selected = []
    selected_types = set()
    for idx, sc in scores:
        move = species.moves[idx]
        if len(selected) < max_moves:
            if move.pkm_type not in selected_types or len(selected) >= max_moves - 1:
                selected.append(idx)
                if move.category in (Category.PHYSICAL, Category.SPECIAL):
                    selected_types.add(move.pkm_type)
    return selected[:max_moves]


def _greedy_fill(core_idxs: list[int], damage_matrix: np.ndarray,
                 base_scores: np.ndarray, max_team_size: int, n: int) -> list[int]:
    team = list(core_idxs)
    coverage = np.sum(damage_matrix[team], axis=0) if team else np.zeros(n)
    candidates = set(range(n)) - set(team)
    while len(team) < max_team_size and candidates:
        old_range = coverage.max() - coverage.min()
        best_i, best_val = None, -float('inf')
        for i in candidates:
            new_cov = coverage + damage_matrix[i]
            new_range = new_cov.max() - new_cov.min()
            delta = old_range - new_range
            val = 1.5 * delta + 1.0 * base_scores[i]
            if val > best_val:
                best_val, best_i = val, i
        team.append(best_i)
        coverage += damage_matrix[best_i]
        candidates.remove(best_i)
    return team


def _score_team(team_idxs: list[int], damage_matrix: np.ndarray) -> float:
    return float(np.mean(np.sum(damage_matrix[team_idxs], axis=0)))


class SmartTeamBuildPolicy(TeamBuildPolicy):
    def decision(self, roster: Roster, meta: Meta | None, max_team_size: int, max_pkm_moves: int, n_active: int) -> TeamBuildCommand:
        n = len(roster)
        if n == 0:
            return []

        # Build 50x50 damage matrix
        damage_matrix = np.zeros((n, n), dtype=float)
        for i in range(n):
            for j in range(n):
                damage_matrix[i, j] = _get_best_damage_ratio(roster[i], roster[j])

        # Bulk-first base scores: firepower and bulk equally weighted, HP bonus, speed removed.
        # HP is counted separately from _score_bulk (which is HP*DEF*SpD product) to give
        # raw survivability extra emphasis — mirrors JJJ's HP-120 filter in a continuous way.
        base_scores = np.zeros(n, dtype=float)
        for i in range(n):
            firepower = np.mean(damage_matrix[i])
            bulk = _score_bulk(roster[i])
            hp_score = roster[i].base_stats[Stat.MAX_HP] / 150.0
            base_scores[i] = 1.0 * firepower + 1.0 * bulk + 0.5 * hp_score

        # Greedy team selection from best base-score Pokemon
        first_idx = int(np.argmax(base_scores))
        selected_ids = _greedy_fill([first_idx], damage_matrix, base_scores, max_team_size, n)

        # Local swap improvement: single-member swap that raises composite score.
        # composite = coverage mean + 0.5 * team quality mean
        def composite(ids: list[int]) -> float:
            return _score_team(ids, damage_matrix) + 0.5 * float(np.mean(base_scores[ids]))

        best_score = composite(selected_ids)
        improved = True
        while improved:
            improved = False
            for i in range(len(selected_ids)):
                for j in range(n):
                    if j in selected_ids:
                        continue
                    candidate = selected_ids[:]
                    candidate[i] = j
                    s = composite(candidate)
                    if s > best_score + 1e-9:
                        selected_ids = candidate
                        best_score = s
                        improved = True
                        break
                if improved:
                    break

        # Assign EVs, IVs, Nature, Moves
        cmds: TeamBuildCommand = []
        for idx in selected_ids:
            species = roster[idx]
            orientation = _determine_orientation(species)
            if orientation == 'physical':
                evs, nature = (252, 252, 0, 0, 0, 4), Nature.ADAMANT
            elif orientation == 'special':
                evs, nature = (252, 0, 0, 252, 0, 4), Nature.MODEST
            else:
                evs, nature = (252, 126, 0, 126, 0, 4), Nature.HASTY
            ivs = (31,) * 6
            move_indices = _select_best_moves(species, max_pkm_moves)
            cmds.append((idx, evs, ivs, nature, move_indices))

        return cmds
