import os
import time
from itertools import product
from multiprocessing import Process, Queue
from typing import Optional, Tuple

import numpy as np
from numpy.random import choice

from fast_damage_calculator import calculate_damage
from vgc2.agent import BattlePolicy
from vgc2.agent.battle import RandomBattlePolicy, deduce_state
from vgc2.battle_engine import (
    BattleCommand,
    BattleEngine,
    BattleRuleParam,
    State,
)
from vgc2.battle_engine.team import BattlingTeam
from vgc2.battle_engine.view import TeamView
from vgc2.util.forward import copy_state


def greedy_single_battle_decision(
        params: BattleRuleParam, state: State
) -> list[BattleCommand]:
    """
    Greedy decision for single battles.
    """
    attacker, defender = state.sides[0].team.active[0], state.sides[1].team.active[0]
    outcomes = [
        calculate_damage(params, 0, move.constants, state, attacker, defender)
        if move.pp > 0 and not move.disabled
        else 0
        for move in attacker.battling_moves
    ]
    return [(int(np.argmax(outcomes)), 0) if outcomes else (0, 0)]


def greedy_double_battle_decision(
        params: BattleRuleParam, state: State
) -> list[BattleCommand]:
    """
    Greedy decision for double battles.
    """
    attackers, defenders = state.sides[0].team.active, state.sides[1].team.active
    strategies = []
    for sources, targets in product(
            product(
                list(range(len(attackers[0].battling_moves))),
                list(range(len(attackers[1].battling_moves))) if len(attackers) > 1 else [],
            ),
            product(list(range(len(defenders))), list(range(len(defenders)))),
    ):
        damage, ko, hp = 0, 0, [d.hp for d in defenders]
        for i, (source, target) in enumerate(zip(sources, targets)):
            attacker, defender, move = (
                attackers[i],
                defenders[target],
                attackers[i].battling_moves[source],
            )
            if move.pp == 0 or move.disabled:
                continue
            new_hp = max(
                0,
                hp[target]
                - calculate_damage(
                    params, 0, move.constants, state, attacker, defender
                ),
            )
            damage += hp[target] - new_hp
            ko += int(new_hp == 0)
            hp[target] = new_hp
        strategies += [(ko, damage, sources, targets)]
    if len(strategies) == 0:
        return [
            (choice(len(a.battling_moves)), choice(len(defenders))) for a in attackers
        ]
    best = max(strategies, key=lambda x: 1000 * x[0] + x[1])
    return list(zip(best[2], best[3]))


class GreedyBattlePolicy(BattlePolicy):
    """
    Greedy strategy that prioritizes KOs and damage output with only one turn lookahead. Performs no switches.
    """

    def __init__(self, params: BattleRuleParam = BattleRuleParam()):
        self.params = params

    def decision(
            self, state: State, opp_view: Optional[TeamView] = None
    ) -> list[BattleCommand]:
        n_active_0, n_active_1 = (
            len(state.sides[0].team.active),
            len(state.sides[1].team.active),
        )
        match max(n_active_0, n_active_1):
            case 1:
                return greedy_single_battle_decision(self.params, state)
            case 2:
                return greedy_double_battle_decision(self.params, state)


def get_actions(team: tuple[BattlingTeam, BattlingTeam]) -> list[list[BattleCommand]]:
    attackers = team[0].active
    move_targets = [i for i in range(len(team[1].active))]
    switch_targets = [i for i, p in enumerate(team[0].reserve) if p.hp > 0]
    commands = []
    for attacker in attackers:
        moves = [
            i
            for i, m in enumerate(attacker.battling_moves)
            if m.pp > 0 and not m.disabled
        ]
        commands += [
            list(product(moves, move_targets)) + list(product([-1], switch_targets))
        ]
    return list(product(*commands))


def rollout(
        predict_winner,
        params: BattleRuleParam,
        d_state: State,
        first_our_action: list[BattleCommand],
        rollout_turns_greedy: int,
        rollout_turns_random: int,
) -> tuple[float, int]:
    """
    rolloutを行う。
    最初のターンの自分の行動は、 first_our_action で指定する。
    self.rollout_turns_greedy ターンの間、Greedyで行動を選択する。
    その後、 self.rollout_turns_random ターンの間、Randomで行動を選択する。
    それが完了した時点で、静的評価により勝敗を決定する。
    戻り値: 報酬と進めたターン数。自分が勝つと+1、負けると-1、引き分けは0、静的評価により、+1～-1の範囲の実数値となる。
    """
    engine = BattleEngine(d_state, params)
    greedy_policy = GreedyBattlePolicy(params)
    random_policy = RandomBattlePolicy()

    reward = 0.0

    turn = -1
    for turn in range(rollout_turns_greedy + rollout_turns_random):
        if turn == 0:
            command = (
                first_our_action,
                greedy_policy.decision(
                    State((d_state.sides[1], d_state.sides[0])), None
                ),
            )
        elif turn < rollout_turns_greedy:
            command = (
                greedy_policy.decision(d_state),
                greedy_policy.decision(
                    State((d_state.sides[1], d_state.sides[0])), None
                ),
            )
        else:
            command = (
                random_policy.decision(d_state),
                random_policy.decision(
                    State((d_state.sides[1], d_state.sides[0])), None
                ),
            )
        engine.run_turn(command)
        d_state = engine.state

        if engine.finished():
            match engine.winning_side:
                case 0:
                    reward = 1.0
                    break
                case 1:
                    reward = -1.0
                    break
                case _:
                    reward = 0.0
                    break
    else:
        # ゲームが終了していない場合、評価関数を使用
        predicted_winner, confidence = predict_winner(d_state)
        # プレイヤー0の勝率を報酬に変換
        if predicted_winner == 0:
            reward = 2.0 * confidence - 1.0  # [0.5, 1.0] -> [0.0, 1.0]
        else:
            reward = 2.0 * (1.0 - confidence) - 1.0  # [0.5, 1.0] -> [0.0, -1.0]

    return reward, turn + 1


def rollout_worker_process(
        job_queue: Queue,
        result_queue: Queue,
        model_path: str,
        params: BattleRuleParam,
        rollout_turns_greedy: int,
        rollout_turns_random: int,
):
    # NumPy-only version for inference
    from numpy_inference import (
        load_model_numpy_only,
        predict_winner_numpy,
    )

    model, normalization_params, metrics = load_model_numpy_only(model_path)

    def predict_winner(state: State) -> Tuple[int, float]:
        return predict_winner_numpy(model, normalization_params, state)

    while True:
        item = job_queue.get()
        if item is None:
            break
        key, d_state, first_our_action = item
        try:
            reward, rollout_turns = rollout(
                predict_winner,
                params,
                d_state,
                first_our_action,
                rollout_turns_greedy,
                rollout_turns_random,
            )
        except Exception as e:
            print(f"Error in rollout_worker_process: {e}")
            reward = 0.0
        result_queue.put((key, reward))


class MonteCarloMultiProcessBattlePolicy(BattlePolicy):
    """
    Monte Carlo battle strategy.
    各合法手に対してロールアウトを行い、最善の手を選択する。
    """

    def __init__(
            self,
            max_moves: int = 4,
            params: BattleRuleParam = BattleRuleParam(),
            decision_time: float = 1.0,
            rollout_turns_greedy: int = 4,
            rollout_turns_random: int = 2,
            c_puct: float = 1.0,
            model_path: str = "submission/evaluation_model.pkl",
            rollout_processes: Optional[int] = None,
    ):
        """
        Args:
            max_moves: 最大移動数
            params: バトルルールパラメータ
            decision_time: 持ち時間
            virtual_time: 検証用に仮想持ち時間を使用する
            virtual_time_per_greedy_turn: Greedyでrolloutした場合の1ターン当たり仮想時間の加算
            virtual_time_per_random_turn: Randomでrolloutした場合の1ターン当たり仮想時間の加算
            rollout_turns_greedy: Greedyでrolloutするターン数
            rollout_turns_random: Randomでrolloutするターン数(Greedy終了後)
            c_puct: UCB1の計算のハイパラ
            model_path: 評価モデルのパス
        """
        self.max_moves = max_moves
        self.params = params
        self.decision_time = decision_time
        self.rollout_turns_greedy = rollout_turns_greedy
        self.rollout_turns_random = rollout_turns_random
        self.c_puct = c_puct
        self.model_path = model_path

        # 現在思考中の局面に対するdeteminizationの結果
        self._determinization_cache = {}

        self.job_queue = Queue()
        self.result_queue = Queue()
        self.processes = [
            Process(
                target=rollout_worker_process,
                args=(
                    self.job_queue,
                    self.result_queue,
                    model_path,
                    params,
                    rollout_turns_greedy,
                    rollout_turns_random,
                ),
            )
            for _ in range(rollout_processes or os.cpu_count())
        ]
        for p in self.processes:
            p.start()

    def __del__(self):
        for _ in self.processes:
            self.job_queue.put(None)

    def _determinization(
            self, play_count: int, state: State, opp_view: Optional[TeamView]
    ) -> State:
        if play_count in self._determinization_cache:
            return copy_state(self._determinization_cache[play_count])
        _state = deduce_state(state, opp_view, self.max_moves)
        self._determinization_cache[play_count] = _state
        return copy_state(_state)

    def _is_within_time(self):
        if self.time_start + self.decision_time > time.time():
            return True
        else:
            return False

    def decision(
            self, state: State, opp_view: Optional[TeamView] = None
    ) -> list[BattleCommand]:
        # 有効なBattleCommandを列挙
        # 相手の控えポケモン等は不明であるが、それは合法手の列挙には影響しないはず
        available_actions = get_actions((state.sides[0].team, state.sides[1].team))
        if len(available_actions) == 0:
            return []

        try:
            self.time_start = time.time()
            self._determinization_cache.clear()
            visit_count = np.zeros(len(available_actions), dtype=np.int32)
            sum_reward = np.zeros(len(available_actions), dtype=np.float32)

            pending = 0
            # 初回は全actionを評価
            for initial_step in range(2):
                d_state = self._determinization(initial_step, state, opp_view)
                for action_idx in range(len(available_actions)):
                    action = available_actions[action_idx]
                    self.job_queue.put((action_idx, d_state, action))
                    pending += 1
            while pending > 0:
                action_idx, reward = self.result_queue.get()
                pending -= 1
                visit_count[action_idx] += 1
                sum_reward[action_idx] += reward

            while self._is_within_time():
                while pending < len(self.processes) * 2:
                    # UCB1
                    ucb_values = sum_reward / visit_count + self.c_puct * np.sqrt(
                        np.log(np.sum(visit_count)) / visit_count
                    )
                    action_idx = np.argmax(ucb_values)

                    action = available_actions[action_idx]
                    d_state = self._determinization(
                        visit_count[action_idx], state, opp_view
                    )
                    self.job_queue.put((action_idx, d_state, action))
                    pending += 1
                    visit_count[action_idx] += 1
                    sum_reward[action_idx] += -1.0  # virtual loss

                action_idx, reward = self.result_queue.get()
                pending -= 1
                sum_reward[action_idx] += reward + 1.0  # virtual lossを回復

            while pending > 0:
                action_idx, reward = self.result_queue.get()
                pending -= 1
                sum_reward[action_idx] += reward + 1.0  # virtual lossを回復

            best_action_idx = np.argmax(visit_count)
            # time_end = time.time()
            # print("time", time_end - self.time_start, "visits", np.sum(visit_count))
            # print(sum_reward[best_action_idx] / visit_count[best_action_idx])
            # print(visit_count)
        except Exception as e:
            print(f"Error in decision: {e}")
            # 即負けを回避するため、一応ランダムに行動
            best_action_idx = np.random.choice(len(available_actions))

        return list(available_actions[best_action_idx])
