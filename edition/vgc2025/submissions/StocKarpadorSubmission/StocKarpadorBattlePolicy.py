import concurrent.futures
import logging
import time
from itertools import product
from statistics import mean
from typing import Tuple, Any

from vgc2.agent import BattlePolicy
from vgc2.agent.battle import GreedyBattlePolicy, _deduce_moves
from vgc2.battle_engine import TeamView, BattleRuleParam, State, BattleCommand, Status, BattlingTeam
from vgc2.battle_engine.modifiers import Hazard, Weather, Terrain
from vgc2.util.forward import copy_state, forward
from vgc2.util.rng import ZERO_RNG

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


def eval_state_with_context(state: State) -> float:
    my_team = state.sides[0].team
    opp_team = state.sides[1].team

    # Normalized HP
    my_hp = sum(p.hp / p.constants.stats[0] for p in my_team.active + my_team.reserve)
    opp_hp = sum(p.hp / p.constants.stats[0] for p in opp_team.active + opp_team.reserve)

    # Alive Pokémon
    my_alive = sum(1 for p in my_team.active + my_team.reserve if p.hp > 0)
    opp_alive = sum(1 for p in opp_team.active + opp_team.reserve if p.hp > 0)

    return (
            3 * my_hp
            - 5 * opp_hp
            + 2 * my_alive
            - 2.5 * opp_alive
    )


def deduce_state_safe(state: State,
                      opp_team_view: TeamView,
                      max_moves: int) -> State:
    _state = copy_state(state)
    opp_team = _state.sides[1].team

    current_pokemon = len(opp_team.active + opp_team.reserve)
    total_pokemon = len(opp_team_view.members)

    if current_pokemon < total_pokemon:
        ids = [p.constants.species.id for p in opp_team.active + opp_team.reserve]
        pokemon = [p for p in opp_team_view.members if p.species.id not in ids]
        required = total_pokemon - current_pokemon

        if len(pokemon) < required:
            required = len(pokemon)

    for p in opp_team.active + opp_team.reserve:
        _deduce_moves(p, max_moves)

    return _state


def is_attacking_move(pokemon, attack_index):
    atk = pokemon.battling_moves[attack_index]
    atkc = atk.constants
    return atkc.base_power > 0 and (not atkc.force_switch) and (not atkc.self_switch) and (
        not atkc.ignore_evasion) and (not atkc.protect) and atkc.boosts == (0,) * 8 and (
                atkc.heal == 0.) and atkc.weather_start == Weather.CLEAR and atkc.field_start == Terrain.NONE and (
        not atkc.toggle_trickroom) and (not atkc.change_type) and (not atkc.toggle_reflect) and (
        not atkc.toggle_lightscreen) and (
        not atkc.toggle_tailwind) and atkc.hazard == Hazard.NONE and atkc.status == Status.NONE and (not atkc.disable)


def get_actions_test(team: Tuple[BattlingTeam, BattlingTeam]) -> list[Any] | list[tuple[Any, ...]]:
    attackers = team[0].active
    move_targets = list(range(len(team[1].active)))
    switch_targets = [i for i, p in enumerate(team[0].reserve) if p.hp > 0]

    commands = []

    for idx, attacker in enumerate(attackers):
        moves = [i for i, m in enumerate(attacker.battling_moves) if
                 m.pp > 0 and (not m.disabled) and (not is_attacking_move(attacker, i))]

        action_list = []

        if moves:
            move_actions = list(product(moves, move_targets))
            action_list += move_actions
            logger.info(f"[get_actions] Attacker {idx}: legal move actions -> {move_actions}")

        if switch_targets:
            switch_actions = list(product([-1], switch_targets))
            action_list += switch_actions
            logger.info(f"[get_actions] Attacker {idx}: legal switch actions -> {switch_actions}")

        commands.append(action_list)

    if not commands:
        return []

    action_combinations = list(product(*commands))
    return action_combinations


def evaluate_single_action(args: tuple):
    action, state, depth, opp_action, num_simulations, simulate_func, copy_state_func = args

    scores = [simulate_func(copy_state_func(state), list(action), depth, opp_action)
              for _ in range(num_simulations)]

    avg_score = mean(scores) if scores else float('-inf')
    return (avg_score, action)


class MonteCarloBattlePolicy(BattlePolicy):
    """
    Monte Carlo strategy: samples random actions, simulates future turns, and picks the action with best average outcome.
    """

    def __init__(self,
                 max_moves: int = 4,
                 num_simulations: int = 1,
                 max_depth: int = 1,
                 params: BattleRuleParam = BattleRuleParam()):
        self.opp_team = None
        self.max_moves = max_moves
        self.num_simulations = num_simulations
        self.max_depth = max_depth
        self.params = params
        self.opp_policy = GreedyBattlePolicy()

    def simulate(self, state: State, action: list[BattleCommand], depth: int, opp_action) -> float:
        """Simulates one rollout starting from given state and action."""
        _state = copy_state(state)
        forward(_state, (action, opp_action), self.params,
                acc_rng=tuple([tuple([ZERO_RNG, ZERO_RNG]), tuple([ZERO_RNG, ZERO_RNG])]))

        for d in range(depth):
            if _state.terminal():
                return 100.000
            my_action = self.opp_policy.decision(State((_state.sides[0], _state.sides[1])), self.opp_team)

            opp_action = self.opp_policy.decision(State((_state.sides[1], _state.sides[0])), self.opp_team)

            forward(_state, (my_action, opp_action), self.params,
                    acc_rng=tuple([tuple([ZERO_RNG, ZERO_RNG]), tuple([ZERO_RNG, ZERO_RNG])]))

        score = eval_state_with_context(_state, )
        return score

    def decision(self, state: State, opp_team: TeamView) -> list[BattleCommand]:
        start_time = time.time()
        self.opp_team = opp_team

        _state = deduce_state_safe(state, self.opp_team, self.max_moves)
        actions = get_actions_test((_state.sides[0].team, _state.sides[1].team))

        action_scores = []
        depth = 1

        opp_action = self.opp_policy.decision(State((_state.sides[1], _state.sides[0])), self.opp_team)
        greedy_action = self.opp_policy.decision(State((_state.sides[0], _state.sides[1])))
        greedy_score = self.simulate(copy_state(_state), greedy_action, depth, opp_action)
        action_scores.append((greedy_score, greedy_action))

        if actions:
            tasks = [
                (action, _state, depth, opp_action, self.num_simulations, self.simulate, copy_state)
                for action in actions
            ]

            with concurrent.futures.ThreadPoolExecutor() as executor:
                results = executor.map(evaluate_single_action, tasks)
                action_scores.extend(results)

        if not action_scores:
            # Fallback if there are no actions and no greedy result
            return greedy_action

        best_action = max(action_scores, key=lambda x: x[0])[1]

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"[new TIMING] Decision took {elapsed_ms:.2f} ms for {len(actions)} actions.")
        return list(best_action)
