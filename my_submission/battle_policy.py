"""
Advanced MCTS Battle Policy for VGC AI Competition 2026.

Uses Monte Carlo Tree Search (MCTS) inspired by the 2025 Battle Track Winner (Yamabuki).
Simulates outcomes using a Greedy rollout policy.
Overcomes DUMMY_MOVE by generating a Mock State.
Respects 100ms time limit constraint.
"""
import random
import time
import math
from typing import Optional

from vgc2.agent import BattlePolicy
from vgc2.agent.battle import GreedyBattlePolicy
from vgc2.battle_engine import State, BattleCommand, BattleRuleParam, TeamView, BattlingPokemon, BattlingMove
from vgc2.battle_engine.modifiers import Status, Stat
from vgc2.util.forward import copy_state, forward


class EnhancedBattlePolicy(BattlePolicy):
    def __init__(self, time_limit_ms: int = 90):
        self.time_limit_ms = time_limit_ms
        self.params = BattleRuleParam()
        self.opp_policy = GreedyBattlePolicy()
        self.action_policy = GreedyBattlePolicy()
        self.rollout_depth = 4
        self.C = 1.4

    def set_params(self, params: BattleRuleParam):
        super().set_params(params)
        self.params = params
        self.opp_policy.set_params(params)
        self.action_policy.set_params(params)

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

    def _deduce_moves(self, pokemon: BattlingPokemon, max_moves: int):
        n_moves = len(pokemon.battling_moves)
        if n_moves < max_moves:
            ids = [m.constants.id for m in pokemon.battling_moves]
            moves = [m for m in pokemon.constants.species.moves if m.id not in ids]
            if moves:
                pokemon.battling_moves += [BattlingMove(m) for m in random.sample(moves, min(len(moves), max_moves - n_moves))]

    def get_possible_actions(self, pokemon, state):
        actions = []
        for move_idx in range(len(pokemon.battling_moves)):
            move = pokemon.battling_moves[move_idx]
            if move.pp <= 0 or move.disabled:
                continue
            for enemy_idx in range(len(state.sides[1].team.active)):
                actions.append((move_idx, enemy_idx))
        if not actions:
            actions.append((0, 0))
        return actions

    def get_all_possible_actions(self, state):
        team = state.sides[0].team.active
        if not team:
            return [[(0, 0)]]
            
        actions1 = self.get_possible_actions(team[0], state)
        if len(team) > 1:
            actions2 = self.get_possible_actions(team[1], state)
            actions = []
            for a1 in actions1:
                for a2 in actions2:
                    actions.append([a1, a2])
            return actions
        else:
            return [[a] for a in actions1]

    def evaluate_state(self, state):
        own_team = [x for x in state.sides[0].team.active if x.hp > 0]
        own_reserve = [x for x in state.sides[0].team.reserve if x.hp > 0]
        enemy_team = [x for x in state.sides[1].team.active if x.hp > 0]
        enemy_reserve = [x for x in state.sides[1].team.reserve if x.hp > 0]
        
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

        # Status and speed evaluation
        for pkm in own_team:
            if pkm.status != Status.NONE: enemy_score += 1000
            own_score += pkm.constants.stats[Stat.SPEED]
            own_score += 20 * sum(pkm.boosts)

        for pkm in enemy_team:
            if pkm.status != Status.NONE: own_score += 1000
            enemy_score += pkm.constants.stats[Stat.SPEED]
            enemy_score += 20 * sum(pkm.boosts)

        if own_count + enemy_count <= 2:
            own_score *= 0.8
            enemy_score *= 0.8

        return own_score - enemy_score

    def select_best_child(self, node: MCTNode):
        for child in node.children:
            if child.visit_count == 0:
                return child

        best_child = node
        best_ucb = float('-inf')
        for child in node.children:
            Q = child.total_reward / child.visit_count
            N = child.visit_count
            N_parent = max(1, node.visit_count)
            UCB1 = Q + self.C * math.sqrt(math.log(N_parent) / N)
            if UCB1 > best_ucb:
                best_ucb = UCB1
                best_child = child

        return best_child

    def expand_one_child(self, node: MCTNode):
        actions = self.get_all_possible_actions(node.state)
        actions = [tuple(action) for action in actions]
        untried = set(actions) - node.used_actions
        
        if not untried:
            return node
            
        if random.random() < 0.2:
            actions_to_take = random.sample(list(untried), 1)[0]
        else:
            best_action = self.action_policy.decision(node.state)
            actions_to_take = tuple(best_action)
            
        # Deduce missing moves for opponent
        for enemy in node.state.sides[1].team.active:
            self._deduce_moves(enemy, 4)

        opp_action = self.opp_policy.decision(State((node.state.sides[1], node.state.sides[0])))
        
        new_state = copy_state(node.state)
        forward(new_state, (list(actions_to_take), opp_action), self.params)
        
        child_node = self.MCTNode(new_state, parent=node, actions=actions_to_take, depth=node.depth + 1)
        node.children.append(child_node)
        node.used_actions.add(actions_to_take)
        return child_node

    def rollout(self, state, rollout_depth):
        current_state = copy_state(state)
        
        for _ in range(rollout_depth):
            if current_state.terminal():
                break

            own_actions = self.get_all_possible_actions(current_state)
            if not own_actions:
                break
                
            if self.evaluate_state(current_state) < 0:
                if random.random() < 0.6:
                    action = random.choice(own_actions)
                else:
                    action = self.action_policy.decision(current_state)
            else:
                if random.random() < 0.2:
                    action = random.choice(own_actions)
                else:
                    action = self.action_policy.decision(current_state)
                    
            for enemy in current_state.sides[1].team.active:
                self._deduce_moves(enemy, 4)
                
            enemy_action = self.opp_policy.decision(State((current_state.sides[1], current_state.sides[0])))
            forward(current_state, (action, enemy_action), self.params)

        return self.evaluate_state(current_state)

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

    def MCTS(self, root_state, time_limit_ms):
        root_node = self.MCTNode(root_state)
        start_time = time.perf_counter()
        
        while (time.perf_counter() - start_time) * 1000 < time_limit_ms * 0.9:
            node = self.tree_policy(root_node)
            reward = self.rollout(node.state, self.rollout_depth)
            
            if reward < -600:
                self.C = 10.0
                self.rollout_depth *= 2
            else:
                self.C = 1.41
                self.rollout_depth = 4
                
            # Backpropagate
            curr = node
            while curr is not None:
                curr.visit_count += 1
                curr.total_reward += reward
                curr = curr.parent

        if not root_node.children:
            return None
            
        best_child = self.select_best_child(root_node)
        return list(best_child.actions)

    def decision(self, state: State, opp_view: Optional[TeamView] = None) -> list[BattleCommand]:
        actions = self.MCTS(state, self.time_limit_ms)
        if actions is None:
            actions = self.action_policy.decision(state)
        return actions
