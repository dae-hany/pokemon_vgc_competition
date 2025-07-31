import csv
from collections import defaultdict
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
from numpy.random import choice

from vgc2.agent import BattlePolicy
from vgc2.agent.battle import BattleCommand
from vgc2.agent.battle import GreedyBattlePolicy
from vgc2.battle_engine import State
from vgc2.battle_engine import TeamView, BattleRuleParam
from vgc2.util.encoding import encode_state, EncodeContext


class RandomBattlePolicy(BattlePolicy):
    """
    Policy that selects moves and switches randomly. Tailored for single and double battles.
    """

    def __init__(self,
                 switch_prob: float = .15):
        self.switch_prob = switch_prob

    def decision(self,
                 state: State,
                 opp_view: Optional[TeamView] = None) -> list[BattleCommand]:
        team = state.sides[0].team
        n_switches = len(team.reserve)
        n_targets = len(state.sides[1].team.active)
        cmds: list[BattleCommand] = []
        for pkm in team.active:
            n_moves = len(pkm.battling_moves)
            switch_prob = 0 if n_switches == 0 else self.switch_prob
            action = choice(n_moves + 1, p=[switch_prob] + [(1. - switch_prob) / n_moves] * n_moves) - 1
            if action >= 0:
                target = choice(n_targets, p=[1 / n_targets] * n_targets)
            else:
                target = choice(n_switches, p=[1 / n_switches] * n_switches)
            cmds += [(action, target)]
        return cmds


# ----------------------------------------------------------------------------------------#

class QTableBattlePolicy(BattlePolicy):
    def __init__(self,
                 q_table_path: str,
                 ctx: EncodeContext,
                 action_shape: list[int]):
        self.ctx = ctx
        self.action_shape = action_shape
        self.n_actions = int(np.prod(action_shape))
        self.q_table = self._load_q_table(q_table_path)

    def _load_q_table(self, path):
        Q = defaultdict(lambda: np.zeros(self.n_actions))
        with open(path, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                key = eval(row[0])
                Q[key] = np.array(row[1:], dtype=np.float64)
        return Q

    def decision(self,
                 state: State,
                 opp_view: Optional[TeamView] = None) -> list[BattleCommand]:
        return q_table_battle_decision(
            self.q_table, self.ctx, state, self.n_actions, self.action_shape
        )


def q_table_battle_decision(q_table,
                            ctx: EncodeContext,
                            state: State,
                            n_actions: int,
                            action_shape: list[int]) -> list[BattleCommand]:
    # encode state
    obs = np.zeros(5000)  # what encoder expects
    encode_state(obs, state, ctx)
    state_key = tuple(round(x, 1) for x in obs[:2179])
    debug_mode = True

    commands = []
    # choose best known action
    try:
        if not debug_mode and state_key in q_table:
            action_id = int(np.argmax(q_table[state_key]))
            action_tuple = np.unravel_index(action_id, action_shape)
            # decode action ids to BattleCommands
            for action_id in action_tuple:
                if action_id < 8:
                    move_idx = action_id // 2
                    target_idx = action_id % 2
                    commands.append((move_idx, target_idx))  # tuple format for moves
                else:
                    switch_idx = action_id - 8
                    commands.append((switch_idx,))  # tuple format for switch

    except Exception as e:
        print(f"[Fallback Warning] Using default strategy due to error: {e}")

    # else:
    # fallback for unknown state
    fallback_pol = GreedyBattlePolicy()
    commands = fallback_pol.decision(state)

    return commands


# ----------------------------------------------------------------------------------------#


class ModelBattlePolicy(BattlePolicy):
    def __init__(self, ctx, action_shape):
        self.ctx = ctx
        self.action_shape = action_shape
        self.n_actions = int(np.prod(action_shape))
        current_dir = Path(__file__).resolve().parent
        model_path = current_dir / 'trained_classifier.joblib'
        self.model = joblib.load(model_path)
        self.greedy = GreedyBattlePolicy(BattleRuleParam())

    def decision(self, state, opp_view=None):
        obs = np.zeros(2179)
        encode_state(obs, state, self.ctx)
        state_key = tuple(int(x / 0.2) for x in obs)  # match training precision
        action_id = self.model.predict([state_key])[0]
        action_tuple = np.unravel_index(action_id, self.action_shape)

        return [
            (a // 2, a % 2) if a < 8 else (a - 8,)
            for a in action_tuple
        ]
