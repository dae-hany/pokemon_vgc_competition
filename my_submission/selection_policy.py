"""
Advanced Selection Policy for VGC AI Competition 2026.

Combines the best strategies from 2025 top submissions:
- JJJ (2nd/1st): damage ratio estimation, cumulative coverage, range balancing
- Yamabuki (1st): exhaustive search, speed advantage, utility move bonus
- New: defensive type synergy (shared weakness penalty)

Uses exhaustive search over C(6,4)=15 combinations with multi-factor evaluation.
"""
from itertools import combinations

from vgc2.agent import SelectionPolicy, SelectionCommand
from vgc2.battle_engine.modifiers import Stat, Category, Type, Status
from vgc2.battle_engine.move import Move
from vgc2.battle_engine.pokemon import Pokemon
from vgc2.battle_engine.team import Team

# Standard type effectiveness chart (19x19 including TYPELESS)
TYPE_CHART = [
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
]


def _best_damage_ratio(attacker: Pokemon, defender: Pokemon) -> float:
    """Estimate the best damage ratio (JJJ-style with priority bonus).

    Returns damage as a fraction of defender's max HP.
    """
    best = 0.0
    for move in attacker.moves:
        if move.category not in (Category.PHYSICAL, Category.SPECIAL):
            continue

        # Priority bonus (JJJ: base_power + 12 * priority - 6)
        base_power = move.base_power + 12 * move.priority - 6
        if base_power <= 0:
            continue

        # Choose correct attack/defense stat
        if move.category == Category.PHYSICAL:
            atk_stat = attacker.stats[Stat.ATTACK]
            def_stat = defender.stats[Stat.DEFENSE]
        else:
            atk_stat = attacker.stats[Stat.SPECIAL_ATTACK]
            def_stat = defender.stats[Stat.SPECIAL_DEFENSE]

        # STAB
        stab = 1.5 if move.pkm_type in attacker.species.types else 1.0

        # Type effectiveness (dual type)
        type_eff = 1.0
        for dtype in defender.species.types:
            type_eff *= TYPE_CHART[move.pkm_type][dtype]

        # Damage formula (simplified, level=100)
        level = 100
        dmg = int((2 * level / 5) + 2)
        dmg = int(dmg * base_power)
        dmg = int(dmg * atk_stat / def_stat)
        dmg = int(dmg / 50) + 2
        final = int(dmg * stab * type_eff)

        ratio = final / max(defender.stats[Stat.MAX_HP], 1)
        best = max(best, ratio)
    return best


def _defensive_multiplier(pokemon: Pokemon) -> float:
    """JJJ-style normalized defensive bulk score."""
    hp_ratio = pokemon.stats[Stat.MAX_HP] / 402
    def_ratio = pokemon.stats[Stat.DEFENSE] / 257
    spd_ratio = pokemon.stats[Stat.SPECIAL_DEFENSE] / 257
    return hp_ratio * def_ratio * spd_ratio


def _utility_score(pokemon: Pokemon) -> float:
    """Yamabuki-style utility move bonus."""
    score = 0.0
    for move in pokemon.moves:
        if move.protect:
            score += 1.0
        if move.toggle_tailwind:
            score += 1.0
        if move.toggle_reflect or move.toggle_lightscreen:
            score += 0.5
        if move.status != Status.NONE:
            score += 0.3
    return score


def _shared_weakness_penalty(members: list[Pokemon], opp_team: list[Pokemon]) -> float:
    """Penalize teams where 3+ members share the same type weakness.

    Extra penalty if opponents actually have attacking moves of that type.
    """
    penalty = 0.0

    for atk_type in range(18):
        # Count how many of our selected members are weak to this type
        weak_count = 0
        for member in members:
            eff = 1.0
            for def_type in member.species.types:
                eff *= TYPE_CHART[atk_type][def_type]
            if eff > 1.0:
                weak_count += 1

        if weak_count < 3:
            continue

        # Check if any opponent has attacking moves of this type
        opp_has_type = False
        for opp in opp_team:
            for m in opp.moves:
                if m.pkm_type == atk_type and m.category in (Category.PHYSICAL, Category.SPECIAL):
                    opp_has_type = True
                    break
            if opp_has_type:
                break

        if opp_has_type:
            penalty += weak_count * 1.0
        else:
            penalty += weak_count * 0.3

    return penalty


class CoverageSelectionPolicy(SelectionPolicy):
    """
    Advanced selection policy combining strategies from top 2025 submissions.

    Uses exhaustive search (C(6,4)=15 combos) with multi-factor scoring:
    - Offensive damage ratios (JJJ-style)
    - Defensive bulk (JJJ-style normalization)
    - Coverage balance (JJJ-style range minimization)
    - Speed advantage (Yamabuki-style)
    - Utility moves (Yamabuki-style)
    - Shared weakness penalty (new)
    """

    # Tunable weights (initial values based on JJJ ratios)
    W_OFFENSE = 1.07
    W_DEFENSE = 0.42
    W_BALANCE = 0.50
    W_SPEED = 0.30
    W_UTIL = 0.20
    W_WEAKNESS = 0.15

    def decision(self,
                 teams: tuple[Team, Team],
                 max_size: int) -> SelectionCommand:
        my_team = teams[0].members
        opp_team = teams[1].members
        n = min(max_size, len(my_team))

        if n >= len(my_team):
            return list(range(len(my_team)))

        # Precompute damage matrix: my_pokemon x opponent_pokemon
        m = len(my_team)
        k = len(opp_team)
        damage_matrix = [[0.0] * k for _ in range(m)]
        for i, atk in enumerate(my_team):
            for j, dfn in enumerate(opp_team):
                damage_matrix[i][j] = _best_damage_ratio(atk, dfn)

        # Precompute per-pokemon scores
        defense_scores = [_defensive_multiplier(p) for p in my_team]
        utility_scores = [_utility_score(p) for p in my_team]

        # Opponent max speed for speed comparison
        opp_max_speed = max(p.stats[Stat.SPEED] for p in opp_team) if opp_team else 0

        # Exhaustive search over all C(m, n) combinations
        best_score = float('-inf')
        best_combo = list(range(n))  # fallback

        for combo in combinations(range(m), n):
            score = self._evaluate_combo(
                combo, my_team, opp_team, damage_matrix,
                defense_scores, utility_scores, opp_max_speed, k
            )
            if score > best_score:
                best_score = score
                best_combo = list(combo)

        return best_combo

    def _evaluate_combo(self, combo, my_team, opp_team, damage_matrix,
                        defense_scores, utility_scores, opp_max_speed, k):
        """Multi-factor evaluation of a team combination."""
        members = [my_team[i] for i in combo]

        # 1. Offensive: total damage ratio across all matchups (JJJ-style sum)
        offense = sum(
            sum(damage_matrix[i][j] for j in range(k))
            for i in combo
        )

        # 2. Defensive bulk (JJJ-style)
        defense = sum(defense_scores[i] for i in combo)

        # 3. Coverage balance: minimize range of "best coverage per opponent"
        #    For each opponent, what's the best we can do?
        best_per_opp = [
            max(damage_matrix[i][j] for i in combo)
            for j in range(k)
        ]
        if best_per_opp:
            balance = -(max(best_per_opp) - min(best_per_opp))
        else:
            balance = 0.0

        # 4. Speed advantage (Yamabuki-style): count members faster than all opponents
        speed_bonus = sum(
            1 for p in members
            if p.stats[Stat.SPEED] > opp_max_speed
        )

        # 5. Utility moves (Yamabuki-style)
        util_bonus = sum(utility_scores[i] for i in combo)

        # 6. Shared weakness penalty (new)
        weakness_penalty = _shared_weakness_penalty(members, opp_team)

        return (self.W_OFFENSE * offense
                + self.W_DEFENSE * defense
                + self.W_BALANCE * balance
                + self.W_SPEED * speed_bonus
                + self.W_UTIL * util_bonus
                - self.W_WEAKNESS * weakness_penalty)
