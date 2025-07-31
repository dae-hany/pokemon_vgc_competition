import random
import time
from math import sqrt, log
from random import sample
from typing import Optional

from vgc2.agent import BattlePolicy
from vgc2.agent.battle import GreedyBattlePolicy
from vgc2.battle_engine import State, BattleCommand, BattleEngine, BattleRuleParam, BattlingPokemon, BattlingMove
from vgc2.battle_engine import TeamView
from vgc2.battle_engine.modifiers import Status, Stat
from vgc2.util.forward import copy_state, forward
from greedyBattlePolicy import GreedyIceBattlePolicy


class IceMonteBattlePolicy(BattlePolicy):
    BattleCommand = tuple[int, int]  # action, target
    FullCommand = tuple[list[BattleCommand], list[BattleCommand]]

    def __init__(self):
        super().__init__()
        self.params = BattleRuleParam()
        self.opp_policy = GreedyBattlePolicy(self.params)
        self.action_policy = GreedyIceBattlePolicy(self.params)
        self.rollout_depth = 4
        self.C = 1.4

    class Actions:
        def __init__(self, action_1, action_2, target_1=None, target_2=None):
            self.action_1 = action_1
            self.action_2 = action_2
            self.target_1 = target_1
            self.target_2 = target_2

    class MCTNode:
        def __init__(self, state: State, actions=None, parent=None, depth=0):
            self.state = state
            self.parent = parent
            self.actions = actions
            self.children = []
            self.visit_count = 0
            self.total_reward = 0
            self.depth = depth
            self.used_actions = set()

    def simulate_game(self, state, commands: FullCommand):
        forward(state, commands, self.params)
        return state

    def _deduce_moves(self, pokemon: BattlingPokemon,
                      max_moves: int):
        n_moves = len(pokemon.battling_moves)
        if n_moves < max_moves:
            ids = [m.constants.id for m in pokemon.battling_moves]
            moves = [m for m in pokemon.constants.species.moves if m.id not in ids]
            pokemon.battling_moves += [BattlingMove(m) for m in sample(moves, max_moves - n_moves)]  # ignoring meta

    def select_best_child(self, node: MCTNode):
        for child in node.children:
            if child.visit_count == 0:
                return child

        best_child = node
        best_ucb = float('-inf')
        for child in node.children:
            # Calculate UCB1 score for each child
            Q = child.total_reward / child.visit_count
            N = child.visit_count
            N_parent = node.visit_count
            if N_parent == 0:
                N_parent += 1
            UCB1 = Q + self.C * sqrt(log(N_parent) / N)
            if UCB1 > best_ucb:
                best_ucb = UCB1
                best_child = child

        return best_child

    def is_bad_move(self, move):
        if move.pp <= 0 or move.disabled:
            return True
        return False

    def is_bad_switch(self, pkm, switch_pkm):
        pkm_ratio = pkm.hp / pkm.constants.stats[Stat.MAX_HP]
        switch_ratio = switch_pkm.hp / switch_pkm.constants.stats[Stat.MAX_HP]

        if pkm_ratio >= switch_ratio:
            return True
        if pkm.hp / pkm.constants.stats[Stat.MAX_HP] <= 0.3 or pkm.status != Status.NONE:
            return False
        return True

    def get_possible_actions(self, pokemon, state):
        actions = []
        for move in range(len(pokemon.battling_moves)):
            possible_move = pokemon.battling_moves[move]
            if self.is_bad_move(possible_move):
                continue
            if not possible_move.disabled:
                for enemy in range(len(state.sides[1].team.active)):
                    command = (move, enemy)
                    actions.append(command)
        for reserve_pkm in range(len(state.sides[0].team.reserve)):
            # if not self.is_bad_switch(pokemon, state.sides[0].team.reserve[reserve_pkm]):
            command = (-1, reserve_pkm)
            actions.append(command)
        return actions

    def get_all_possible_actions(self, state):
        team = state.sides[0].team.active
        enemy_team = state.sides[1].team.active
        reserve = state.sides[0].team.reserve
        possible_moves = [-1, 0, 1, 2, 3]
        actions1 = self.get_possible_actions(team[0], state)
        actions = []
        if (len(team) > 1):
            actions2 = self.get_possible_actions(team[1], state)
            for action1 in actions1:
                for action2 in actions2:
                    joint = [action1, action2]
                    actions.append(joint)
            return actions
        else:
            actions = [[x] for x in actions1]
        return actions

    def status_score(self, pokemon):
        if pokemon.status == Status.BURN:
            return 10
        elif pokemon.status == Status.SLEEP:
            return 15
        elif pokemon.status == Status.PARALYZED:
            return 10
        elif pokemon.status == Status.POISON:
            return 5
        elif pokemon.status == Status.TOXIC:
            return 15
        elif pokemon.status == Status.FROZEN:
            return 20
        elif pokemon.status == Status.NONE:
            return 0
        else:
            return 3  # unknown fallback

    def evaluate_state2(self, state):
        own_team = [x for x in state.sides[0].team.active if not x.fainted()]
        own_reserve = [x for x in state.sides[0].team.reserve if not x.fainted()]
        enemy_team = [x for x in state.sides[1].team.active if not x.fainted()]
        enemy_reserve = [x for x in state.sides[1].team.reserve if not x.fainted()]
        enemy_count = len(enemy_team) + len(enemy_reserve)
        own_count = len(own_team) + len(own_reserve)
        own_hps = [x.hp / x.constants.stats[Stat.MAX_HP] for x in own_team]
        enemy_hps = [x.hp / x.constants.stats[Stat.MAX_HP] for x in enemy_team]
        own_score = 0
        enemy_score = 0

        own_score += 50 * sum(own_hps)
        enemy_score += 50 * sum(enemy_hps)

        own_score += 400 * (4 - enemy_count)
        enemy_score += 400 * (4 - own_count)

        own_score += 300 * len(own_team) + 100 * len(own_reserve)
        enemy_score += 300 * len(enemy_team) + 100 * len(enemy_reserve)

        enemy_status = 0
        for pkm in own_team:
            enemy_status += self.status_score(pkm)
            own_score += pkm.constants.stats[Stat.SPEED]
            own_score += 20 * sum(pkm.boosts)
        enemy_score += enemy_status * 100

        own_status = 0
        for pkm in enemy_team:
            own_status += self.status_score(pkm)
            enemy_score += pkm.constants.stats[Stat.SPEED]
            enemy_score += 20 * sum(pkm.boosts)
        own_score += own_status * 100

        if own_count + enemy_count <= 2:
            own_score *= 0.8
            enemy_score *= 0.8

        return own_score - enemy_score

    def backpropagate(self, node, reward):
        while node is not None:
            node.visit_count += 1
            node.total_reward += reward
            node = node.parent

    def expand_one_child(self, node: MCTNode):
        # action = pick one untried action from node
        ownTeam = node.state.sides[0].team.active
        start_time = time.time()
        enemyTeam = node.state.sides[1].team.active
        actions = self.get_all_possible_actions(node.state)
        actions = [tuple(action) for action in actions]
        untried = set(actions) - node.used_actions
        if not untried:
            return node
        if random.random() < 0.2:
            actions = random.sample(list(untried), 1)[0]
        else:
            actions = self.action_policy.decision(node.state)
        if (len(actions) == 2):
            actions = (actions[0], actions[1])
        else:
            actions = (actions[0],)
        for enemy in enemyTeam:
            if len(enemy.battling_moves) < 4:
                self._deduce_moves(enemy, 4)

        opp_action = self.opp_policy.decision(State((node.state.sides[1], node.state.sides[0])))
        commands = (actions, opp_action)
        new_state = self.simulate_game(copy_state(node.state), commands)
        child_node = self.MCTNode(new_state, parent=node, actions=actions, depth=node.depth + 1)
        node.children.append(child_node)
        node.used_actions.add(actions)
        return child_node

    def is_critical_state(self, state):
        own_team = [x for x in state.sides[0].team.active if not x.fainted()]
        own_reserve = [x for x in state.sides[0].team.reserve if not x.fainted()]
        enemy_team = [x for x in state.sides[1].team.active if not x.fainted()]
        enemy_reserve = [x for x in state.sides[1].team.reserve if not x.fainted()]
        enemy_count = len(enemy_team) + len(enemy_reserve)
        own_count = len(own_team) + len(own_reserve)
        own_hps = sum([x.hp / x.constants.stats[Stat.MAX_HP] for x in own_team])
        enemy_hps = sum([x.hp / x.constants.stats[Stat.MAX_HP] for x in enemy_team])
        own_res_hps = sum([x.hp / x.constants.stats[Stat.MAX_HP] for x in own_reserve])
        enemy_res_hps = sum([x.hp / x.constants.stats[Stat.MAX_HP] for x in enemy_reserve])

        own_hp = own_hps + 0.5 * own_res_hps
        enemy_hp = enemy_hps + 0.5 * enemy_res_hps
        own_statused = sum(1 for p in own_team if p.status != Status.NONE)
        enemy_statused = sum(1 for p in enemy_team if p.status != Status.NONE)

        hp_diff = own_hp - enemy_hp
        count_diff = own_count - enemy_count
        status_diff = enemy_statused - own_statused
        if count_diff >= 3 or count_diff <= -3:
            return True

        if hp_diff >= 2.0 or hp_diff <= -2.0:  # significant HP advantage/disadvantage
            return True

        if status_diff >= 2:
            return True
        return False

    def rollout(self, state, rollout_depth):

        current_state = copy_state(state)
        used_actions = []
        for _ in range(rollout_depth):
            if current_state.terminal():
                break

            # --- Own action selection (simple heuristic) ---

            own_actions = self.get_all_possible_actions(current_state)
            untried = [x for x in own_actions if not x in used_actions]
            if not own_actions:
                # No valid action? Forfeit turn.
                action = []
                break
            else:
                if self.evaluate_state2(current_state) < 0:
                    if random.random() < 0.6:
                        action = random.choice(untried or own_actions)
                    else:
                        action = self.action_policy.decision(current_state)
                else:
                    if random.random() < 0.2:
                        action = random.choice(untried or own_actions)
                    else:
                        action = self.action_policy.decision(current_state)
            for enemy in state.sides[1].team.active:
                self._deduce_moves(enemy, 4)
            enemy_action = self.opp_policy.decision(State((current_state.sides[1], current_state.sides[0])))

            commands = (action, enemy_action)
            # Apply one turn
            current_state = self.simulate_game(current_state, commands)

        reward = self.evaluate_state2(current_state)
        # print(reward)
        return reward

    def tree_policy(self, node):
        while not node.state.terminal():
            actions = self.get_all_possible_actions(node.state)
            actions = [tuple(action) for action in actions]
            untried = set(actions) - node.used_actions
            if untried:
                return self.expand_one_child(node)
            else:
                node = self.select_best_child(node)
        return node

    def MCTS2(self, root_state, time_limit=160, max_rollout=2):
        root_node = self.MCTNode(root_state)
        iterations = 0
        start_time = time.time()
        while (time.time() - start_time) * 1000 < time_limit:
            iterations += 1
            node = root_node

            # 1. Selection &  2. expansion
            node = self.tree_policy(node)
            # 3. Simulation
            reward = self.rollout(node.state, self.rollout_depth)
            if reward < -600:
                self.C = 10.0
                self.rollout_depth *= 2
            else:
                self.C = 1.41
                self.rollout_depth = 4
            # print((time.time() - start_time)* 1000)
            # 4. Backpropagate
            self.backpropagate(node, reward)
        # print("children at root: ", len(root_node.used_actions))
        # best_action = max(root_node.children, key=lambda child: child.total_reward/child.visit_count)
        best_action = self.select_best_child(root_node)
        return best_action.actions

    def decision(
            self, state: State, opp_view: Optional[TeamView] = None
    ) -> list[BattleCommand]:
        engine = BattleEngine(state)
        cmds: list[BattleCommand] = []
        start_time = time.time()

        actions = self.MCTS2(state, 95)
        if actions is None:
            actions = self.action_policy.decision(state)
        return actions
