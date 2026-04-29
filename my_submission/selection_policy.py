"""
Type-coverage-based Selection Policy for VGC AI Competition 2026.

Selects the best N pokemon from the team to counter the opponent's team
based on type effectiveness analysis and balanced coverage.

Reference: JJJ/Jun Sung (2025 Battle 2nd, Championship 1st)
"""
from vgc2.agent import SelectionPolicy, SelectionCommand
from vgc2.battle_engine import BattleCommand
from vgc2.battle_engine.constants import BattleRuleParam
from vgc2.battle_engine.modifiers import Stat, Category, Type
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


def _best_damage_vs(attacker: Pokemon, defender: Pokemon) -> float:
    """Estimate the best damage ratio the attacker can deal to the defender."""
    best = 0.0
    for move in attacker.moves:
        if move.category not in (Category.PHYSICAL, Category.SPECIAL):
            continue

        # Choose correct attack stat
        if move.category == Category.PHYSICAL:
            atk_stat = attacker.stats[Stat.ATTACK]
            def_stat = defender.stats[Stat.DEFENSE]
        else:
            atk_stat = attacker.stats[Stat.SPECIAL_ATTACK]
            def_stat = defender.stats[Stat.SPECIAL_DEFENSE]

        # STAB
        stab = 1.5 if move.pkm_type in attacker.species.types else 1.0

        # Type effectiveness
        type_eff = 1.0
        for dtype in defender.species.types:
            type_eff *= TYPE_CHART[move.pkm_type][dtype]

        # Simplified damage formula
        level = attacker.level
        dmg = int((2 * level / 5 + 2) * move.base_power * atk_stat / def_stat / 50) + 2
        dmg = int(dmg * stab * type_eff * move.accuracy)
        ratio = dmg / max(defender.stats[Stat.MAX_HP], 1)
        best = max(best, ratio)
    return best


def _defensive_score(pokemon: Pokemon) -> float:
    """Calculate a defensive bulk score."""
    hp = pokemon.stats[Stat.MAX_HP]
    defense = pokemon.stats[Stat.DEFENSE]
    sp_defense = pokemon.stats[Stat.SPECIAL_DEFENSE]
    return (hp / 400.0) * (defense / 250.0) * (sp_defense / 250.0)


class CoverageSelectionPolicy(SelectionPolicy):
    """
    Selects team members that maximize type coverage against the opponent.
    Uses a greedy iterative approach:
    1. Pick the pokemon with highest offensive score vs all opponents
    2. Then pick members that add the most marginal coverage
    Also factors in defensive bulk.
    """

    def decision(self,
                 teams: tuple[Team, Team],
                 max_size: int) -> SelectionCommand:
        my_team = teams[0].members
        opp_team = teams[1].members
        n = min(max_size, len(my_team))

        if n >= len(my_team):
            return list(range(len(my_team)))

        # Build damage matrix: my_pokemon x opponent_pokemon
        m = len(my_team)
        k = len(opp_team)
        damage_matrix = [[0.0] * k for _ in range(m)]
        for i, atk in enumerate(my_team):
            for j, dfn in enumerate(opp_team):
                damage_matrix[i][j] = _best_damage_vs(atk, dfn)

        # Overall offensive score per pokemon
        offensive_scores = [
            sum(damage_matrix[i]) + 0.3 * _defensive_score(my_team[i])
            for i in range(m)
        ]

        # Greedy iterative selection
        selected: list[int] = []

        # First pick: highest overall score
        first = max(range(m), key=lambda i: offensive_scores[i])
        selected.append(first)
        coverage = list(damage_matrix[first])

        # Subsequent picks: maximize marginal coverage + diversity
        for _ in range(1, n):
            best_idx = -1
            best_val = float('-inf')
            for i in range(m):
                if i in selected:
                    continue
                # Marginal coverage: how much new damage this pokemon adds
                new_coverage = [max(coverage[j], damage_matrix[i][j]) for j in range(k)]
                marginal = sum(new_coverage) - sum(coverage)
                # Range reduction: prefer balanced coverage
                old_range = max(coverage) - min(coverage) if coverage else 0
                new_range = max(new_coverage) - min(new_coverage)
                range_bonus = old_range - new_range
                val = marginal + 0.5 * range_bonus + 0.3 * offensive_scores[i]
                if val > best_val:
                    best_val = val
                    best_idx = i

            if best_idx >= 0:
                selected.append(best_idx)
                coverage = [max(coverage[j], damage_matrix[best_idx][j]) for j in range(k)]

        return selected
