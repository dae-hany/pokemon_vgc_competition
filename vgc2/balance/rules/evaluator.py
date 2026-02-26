from typing import Callable

from vgc2.competition.fixed_matches import ActionRollout, SWITCH

RuleEvaluator = Callable[[list[ActionRollout], list[list[int]]], float]


def evaluate_rules(rollouts: list[ActionRollout],
                   results: list[list[int]]) -> float:
    counts = {"switch": 0, "damage": 0, "effect": 0}
    total_winner_actions = 0

    for i, rollout in enumerate(rollouts):
        # Determine who won this specific set of matches
        res = results[i]
        if res[0] == res[1]:
            continue  # Skip draws if they don't help define a 'winner'

        winner_idx = 0 if res[0] > res[1] else 1

        for turn in rollout:
            winner_move = turn[winner_idx]
            total_winner_actions += 1

            # Categorize the move
            if winner_move == SWITCH:
                counts["switch"] += 1
            elif winner_move.base_power > 0:
                counts["damage"] += 1
            else:
                counts["effect"] += 1

    if total_winner_actions == 0:
        return 0.

    # 1. Calculate actual frequencies
    freq_switch = counts["switch"] / total_winner_actions
    freq_damage = counts["damage"] / total_winner_actions
    freq_effect = counts["effect"] / total_winner_actions

    # 2. Calculate distance from targets: 20% Switch, 60% Damage, 20% Effect
    dist_switch = abs(0.20 - freq_switch)
    dist_damage = abs(0.60 - freq_damage)
    dist_effect = abs(0.20 - freq_effect)

    # Return total deviation (Lower is better)
    return dist_switch + dist_damage + dist_effect
