"""
Type-analysis-based Team Build Policy for VGC AI Competition 2026 (Championship Track).

Builds a team from the roster by:
1. Analyzing type coverage against all possible opponents
2. Selecting pokemon with highest offensive + defensive scores
3. Optimizing EVs and Nature based on physical/special orientation
4. Adapting to the meta over epochs

Reference: JJJ/Jun Sung (2025 Championship 1st)
"""
from typing import Optional

import numpy as np
from numpy.random import choice

from vgc2.agent import TeamBuildPolicy, TeamBuildCommand
from vgc2.balance.meta import Meta, Roster
from vgc2.battle_engine.modifiers import Nature, Type, Category, Stat

# Standard type effectiveness chart
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


def _max_expected_damage_vs_type(species, target_type: int) -> float:
    """Calculate the max expected damage a species can deal against a target type."""
    best = 0.0
    for move in species.moves:
        if move.category not in (Category.PHYSICAL, Category.SPECIAL):
            continue
        if move.category == Category.PHYSICAL:
            atk = species.base_stats[Stat.ATTACK]
        else:
            atk = species.base_stats[Stat.SPECIAL_ATTACK]

        stab = 1.5 if move.pkm_type in species.types else 1.0
        eff = TYPE_CHART[move.pkm_type, target_type]
        exp_dmg = move.accuracy * move.base_power * atk * stab * eff / 100.0
        best = max(best, exp_dmg)
    return best


def _score_species(species, roster) -> float:
    """Score a species based on offensive coverage against all roster types + defensive bulk."""
    offensive = 0.0
    for t in range(18):
        offensive += _max_expected_damage_vs_type(species, t)

    # Defensive bulk
    hp = species.base_stats[Stat.MAX_HP]
    defense = species.base_stats[Stat.DEFENSE]
    sp_def = species.base_stats[Stat.SPECIAL_DEFENSE]
    bulk = (hp * defense * sp_def) / (150.0 ** 3)

    # Speed bonus
    speed = species.base_stats[Stat.SPEED] / 200.0

    return offensive + 500.0 * bulk + 100.0 * speed


def _determine_orientation(species):
    """Determine if a species is physical, special, or mixed attacker."""
    phy_total = sum(
        m.base_power * species.base_stats[Stat.ATTACK]
        for m in species.moves if m.category == Category.PHYSICAL
    )
    spc_total = sum(
        m.base_power * species.base_stats[Stat.SPECIAL_ATTACK]
        for m in species.moves if m.category == Category.SPECIAL
    )
    if phy_total > spc_total * 1.2:
        return 'physical'
    elif spc_total > phy_total * 1.2:
        return 'special'
    return 'mixed'


def _select_best_moves(species, max_moves: int) -> list[int]:
    """Select the best moves for a species, prioritizing coverage and power."""
    move_scores = []
    for i, move in enumerate(species.moves):
        score = 0.0
        if move.category in (Category.PHYSICAL, Category.SPECIAL):
            stab = 1.5 if move.pkm_type in species.types else 1.0
            if move.category == Category.PHYSICAL:
                score = move.base_power * move.accuracy * stab * species.base_stats[Stat.ATTACK] / 100.0
            else:
                score = move.base_power * move.accuracy * stab * species.base_stats[Stat.SPECIAL_ATTACK] / 100.0
        else:
            # Utility moves get a base score
            score = 30.0
            if move.protect:
                score = 80.0
            if any(b != 0 for b in move.boosts):
                score = 60.0
        move_scores.append((i, score))

    # Sort by score descending and take top N
    move_scores.sort(key=lambda x: x[1], reverse=True)

    # Ensure type diversity in selected moves
    selected = []
    selected_types = set()
    for idx, sc in move_scores:
        move = species.moves[idx]
        if len(selected) < max_moves:
            if move.pkm_type not in selected_types or len(selected) >= max_moves - 1:
                selected.append(idx)
                if move.category in (Category.PHYSICAL, Category.SPECIAL):
                    selected_types.add(move.pkm_type)
    return selected[:max_moves]


class SmartTeamBuildPolicy(TeamBuildPolicy):
    """
    Builds a team optimized for type coverage, with EV/Nature optimization.
    """

    def decision(self,
                 roster: Roster,
                 meta: Meta | None,
                 max_team_size: int,
                 max_pkm_moves: int,
                 n_active: int) -> TeamBuildCommand:

        n_roster = len(roster)
        if n_roster == 0:
            return []

        # ── Score all species ──
        scores = [_score_species(s, roster) for s in roster]

        # ── Meta adaptation: boost counter-meta pokemon ──
        if meta is not None:
            for i, species in enumerate(roster):
                usage = meta.usage_rate_pokemon(species)
                if usage > 0.1:
                    # Slightly penalize overused pokemon (anti-meta)
                    scores[i] *= 0.9
                # Boost pokemon that counter popular types
                for t in range(18):
                    type_damage = _max_expected_damage_vs_type(species, t)
                    if type_damage > 0:
                        scores[i] += type_damage * 0.1

        # ── Greedy team selection with coverage diversity ──
        selected_ids: list[int] = []
        selected_types: set = set()

        for _ in range(min(max_team_size, n_roster)):
            best_idx = -1
            best_score = float('-inf')
            for i in range(n_roster):
                if i in selected_ids:
                    continue
                # Diversity bonus for new types
                type_bonus = sum(
                    50.0 for t in roster[i].types if t not in selected_types
                )
                total = scores[i] + type_bonus
                if total > best_score:
                    best_score = total
                    best_idx = i

            if best_idx >= 0:
                selected_ids.append(best_idx)
                for t in roster[best_idx].types:
                    selected_types.add(t)

        # ── Build command for each selected pokemon ──
        cmds: TeamBuildCommand = []
        for idx in selected_ids:
            species = roster[idx]
            orientation = _determine_orientation(species)

            # EV distribution based on role
            if orientation == 'physical':
                evs = (252, 172, 0, 0, 0, 86)   # HP, ATK, SPD
                nature = Nature.ADAMANT           # ATK↑ SPATK↓
            elif orientation == 'special':
                evs = (252, 0, 0, 172, 0, 86)   # HP, SPATK, SPD
                nature = Nature.MODEST            # SPATK↑ ATK↓
            else:
                evs = (252, 86, 0, 86, 0, 86)   # Balanced
                nature = Nature.HASTY             # SPD↑ DEF↓

            ivs = (31,) * 6

            # Select best moves
            move_indices = _select_best_moves(species, max_pkm_moves)

            cmds.append((idx, evs, ivs, nature, move_indices))

        return cmds
