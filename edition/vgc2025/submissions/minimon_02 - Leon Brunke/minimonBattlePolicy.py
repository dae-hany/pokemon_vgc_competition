from itertools import product
from typing import Optional

from numpy import argmax
from numpy.random import choice

from vgc2.agent import BattlePolicy
from vgc2.battle_engine import State, BattleCommand, calculate_damage, BattleRuleParam, TeamView
from vgc2.battle_engine.modifiers import Status


def expected_damage(move, attacker, defender, state, params):
    """
    Berechne erwarteten Schaden = Schaden * (Accuracy / 100) + Status-Bonus
    """
    if move.pp == 0 or move.disabled:
        return 0

    dmg = calculate_damage(params, 0, move.constants, state, attacker, defender)
    acc_factor = move.constants.accuracy / 100 if move.constants.accuracy is not None else 1.0
    acc_factor = 1

    status_bonus = 0
    # Prüfe, ob der Move einen Status verursacht und Gegner keinen Status hat
    if defender.status == Status.NONE:
        status = move.constants.status
        if status in {Status.BURN, Status.PARALYZED, Status.SLEEP, Status.POISON, Status.TOXIC, Status.FROZEN}:
            # Unterschiedliche Gewichtung je Status
            status_weights = {
                Status.BURN: 20,
                Status.PARALYZED: 20,
                Status.SLEEP: 20,
                Status.POISON: 18,
                Status.TOXIC: 18,
                Status.FROZEN: 20,
            }
            prob = move.constants.effect_prob  # Wahrscheinlichkeit, dass Status trifft
            status_bonus = prob * status_weights.get(status, 0)

    return dmg * acc_factor + status_bonus


def greedy_single_battle_decision(params: BattleRuleParam,
                                  state: State) -> list[BattleCommand]:
    attacker, defender = state.sides[0].team.active[0], state.sides[1].team.active[0]
    outcomes = [expected_damage(move, attacker, defender, state, params) for move in attacker.battling_moves]
    return [(int(argmax(outcomes)), 0) if outcomes else (0, 0)]


def greedy_double_battle_decision(params: BattleRuleParam,
                                  state: State) -> list[BattleCommand]:
    attackers, defenders = state.sides[0].team.active, state.sides[1].team.active
    strategies = []

    for sources in product(range(len(attackers[0].battling_moves)),
                           range(len(attackers[1].battling_moves)) if len(attackers) > 1 else []):
        for targets in product(range(len(defenders)), repeat=len(sources)):
            damage, ko, hp = 0, 0, [d.hp for d in defenders]
            for i, (source_idx, target_idx) in enumerate(zip(sources, targets)):
                attacker = attackers[i]
                defender = defenders[target_idx]
                move = attacker.battling_moves[source_idx]

                dmg = expected_damage(move, attacker, defender, state, params)
                new_hp = max(0, hp[target_idx] - dmg)
                damage += hp[target_idx] - new_hp

                ko += int(new_hp == 0)
                hp[target_idx] = new_hp
            strategies.append((ko, damage, sources, targets))

    if not strategies:
        # Fallback: zufällige Wahl
        return [(choice(len(a.battling_moves)), choice(len(defenders))) for a in attackers]

    # KO > Schaden > Zielvielfalt
    def strategy_score(ko, damage, sources, targets):
        diversity_bonus = len(set(targets)) * 2  # kleiner Bonus, gleichartige Ziele vermeiden
        return 1000 * ko + damage + diversity_bonus

    best = max(strategies, key=lambda x: strategy_score(*x))
    return list(zip(best[2], best[3]))


class GreedyBattlePolicy(BattlePolicy):
    """
    Greedy strategy mit Accuracy-Gewichtung und Statusbonus.
    """

    def __init__(self,
                 params: BattleRuleParam = BattleRuleParam()):
        self.params = params

    def decision(self,
                 state: State,
                 opp_view: Optional[TeamView] = None) -> list[BattleCommand]:
        n_active_0, n_active_1 = len(state.sides[0].team.active), len(state.sides[1].team.active)
        match max(n_active_0, n_active_1):
            case 1:
                return greedy_single_battle_decision(self.params, state)
            case 2:
                return greedy_double_battle_decision(self.params, state)
