"""
Advanced MCTS Battle Policy for VGC AI Competition 2026.

CHAMPIONSHIP-ONLY PATCH:
- Adds a thin weather-controller wrapper that actually uses weather-setting moves
  (Move.weather_start) when it is strongly beneficial for our current 4.

Engine facts (vgc2):
- state.weather exists and starts as Weather.CLEAR
- a move sets weather if move.constants.weather_start != Weather.CLEAR
- offensive weather modifiers only affect FIRE/WATER moves in SUN/RAIN
"""
import random
import time
import math
from typing import Optional

from vgc2.agent import BattlePolicy
from vgc2.agent.battle import GreedyBattlePolicy
from vgc2.battle_engine import (
    State,
    BattleCommand,
    BattleRuleParam,
    TeamView,
    BattlingPokemon,
    BattlingMove,
    calculate_damage,
)
from vgc2.battle_engine.modifiers import Status, Stat, Type, Weather, Category
from vgc2.util.forward import copy_state, forward


class EnhancedBattlePolicy(BattlePolicy):
    def __init__(self, time_limit_ms: int = 90):
        self.time_limit_ms = time_limit_ms
        self.params = BattleRuleParam()
        self.opp_policy = GreedyBattlePolicy()
        self.action_policy = GreedyBattlePolicy()
        self.rollout_depth = 4
        self.C = 1.4
        self.expand_explore_prob = 0.01

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
                pokemon.battling_moves += [
                    BattlingMove(m)
                    for m in random.sample(moves, min(len(moves), max_moves - n_moves))
                ]

    def _should_switch(self, pkm: BattlingPokemon, state: State, side: int) -> bool:
        opp_side = 1 - side
        hp_max = pkm.constants.stats[Stat.MAX_HP]

        # 1. OHKO Threat
        for opp_pkm in state.sides[opp_side].team.active:
            if opp_pkm.hp <= 0:
                continue
            for move in opp_pkm.battling_moves:
                if move.pp <= 0:
                    continue
                dmg = calculate_damage(self.params, opp_side, move.constants, state, opp_pkm, pkm)
                if dmg >= pkm.hp:
                    return True

        # 2. Bad Matchup
        max_dmg_to_opp = 0
        for opp_pkm in state.sides[opp_side].team.active:
            if opp_pkm.hp <= 0:
                continue
            for move in pkm.battling_moves:
                if move.pp <= 0 or move.disabled:
                    continue
                dmg = calculate_damage(self.params, side, move.constants, state, pkm, opp_pkm)
                max_dmg_to_opp = max(max_dmg_to_opp, dmg)

        max_dmg_from_opp = 0
        for opp_pkm in state.sides[opp_side].team.active:
            if opp_pkm.hp <= 0:
                continue
            for move in opp_pkm.battling_moves:
                if move.pp <= 0:
                    continue
                dmg = calculate_damage(self.params, opp_side, move.constants, state, opp_pkm, pkm)
                max_dmg_from_opp = max(max_dmg_from_opp, dmg)

        if max_dmg_to_opp < hp_max * 0.15 and max_dmg_from_opp > hp_max * 0.35:
            return True

        # 3. Status Risks
        if pkm.status == Status.BURN and pkm.constants.stats[Stat.ATTACK] > pkm.constants.stats[Stat.SPECIAL_ATTACK]:
            return True

        return False

    def get_possible_actions(self, pokemon, state):
        actions = []
        n_targets = len(state.sides[1].team.active)
        for move_idx in range(len(pokemon.battling_moves)):
            move = pokemon.battling_moves[move_idx]
            if move.pp <= 0 or move.disabled:
                continue
            for enemy_idx in range(n_targets):
                actions.append((move_idx, enemy_idx))

        if self._should_switch(pokemon, state, 0):
            switch_targets = [i for i, reserve in enumerate(state.sides[0].team.reserve) if reserve.hp > 0]
            actions += [(-1, idx) for idx in switch_targets]

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

        for pkm in own_team:
            if pkm.status != Status.NONE:
                enemy_score += 1000
            own_score += pkm.constants.stats[Stat.SPEED]
            own_score += 20 * sum(pkm.boosts)

        for pkm in enemy_team:
            if pkm.status != Status.NONE:
                own_score += 1000
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
        best_ucb = float("-inf")
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
            return self.select_best_child(node) if node.children else node

        if random.random() < self.expand_explore_prob:
            actions_to_take = random.sample(list(untried), 1)[0]
        else:
            best_action = self.action_policy.decision(node.state)
            best_action = tuple(best_action)
            if best_action in untried:
                actions_to_take = best_action
            else:
                existing_child = next((child for child in node.children if child.actions == best_action), None)
                if existing_child is not None:
                    return existing_child
                actions_to_take = random.sample(list(untried), 1)[0]

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
                action = random.choice(own_actions) if random.random() < 0.6 else self.action_policy.decision(current_state)
            else:
                action = random.choice(own_actions) if random.random() < 0.2 else self.action_policy.decision(current_state)

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

            curr = node
            while curr is not None:
                curr.visit_count += 1
                curr.total_reward += reward
                curr = curr.parent

        if not root_node.children:
            return None

        best_child = max(
            root_node.children,
            key=lambda child: (child.visit_count, child.total_reward / max(1, child.visit_count)),
        )
        return list(best_child.actions)

    def decision(self, state: State, opp_view: Optional[TeamView] = None) -> list[BattleCommand]:
        actions = self.MCTS(state, self.time_limit_ms)
        if actions is None:
            actions = self.action_policy.decision(state)
        return actions


# ---------------- Championship weather wrapper ----------------
class ChampionshipWeatherBattlePolicy(BattlePolicy):
    """
    Championship-only wrapper:
    - If we can set a beneficial weather (RAIN/SUN) with our current active mons, do it.
    - Else delegate to EnhancedBattlePolicy (MCTS).
    """

    def __init__(self, inner: Optional[BattlePolicy] = None, time_limit_ms: int = 90):
        self.params = BattleRuleParam()
        self.inner = inner if inner is not None else EnhancedBattlePolicy(time_limit_ms=time_limit_ms)

        # tuneables
        self.force_threshold = 85.0   # lower -> set weather more aggressively
        self.cooldown_turns = 2       # avoid repeated weather spamming
        self._last_forced_turn = -999
        self._turn = 0

    def set_params(self, params: BattleRuleParam):
        super().set_params(params)
        self.params = params
        try:
            self.inner.set_params(params)
        except Exception:
            pass

    def _benefit_score_for_weather(self, pkm: BattlingPokemon, weather: Weather) -> float:
        """
        Score how much this pokemon benefits from given weather (no-knowledge heuristic).
        Only uses FIRE/WATER attacking moves because engine weather boost affects only those.
        """
        target_type = Type.WATER if weather == Weather.RAIN else Type.FIRE
        best = 0.0
        for bm in getattr(pkm, "battling_moves", []) or []:
            mv = getattr(bm, "constants", bm)
            if getattr(mv, "category", Category.OTHER) not in (Category.PHYSICAL, Category.SPECIAL):
                continue
            if getattr(mv, "pkm_type", Type.TYPELESS) != target_type:
                continue
            bp = float(getattr(mv, "base_power", 0))
            acc = float(getattr(mv, "accuracy", 1.0))
            pr = float(getattr(mv, "priority", 0))
            bp = bp + max(0.0, pr) * 10.0
            if bp <= 0:
                continue
            stab = 1.0 + (0.5 if target_type in getattr(pkm, "types", []) else 0.0)
            best = max(best, bp * acc * stab)
        return best

    def _team_weather_advantage(self, state: State, weather: Weather) -> float:
        """(Our benefit - Opp benefit) under this weather."""
        my_team = state.sides[0].team.active + state.sides[0].team.reserve
        opp_team = state.sides[1].team.active + state.sides[1].team.reserve
        my_b = sum(self._benefit_score_for_weather(p, weather) for p in my_team if p is not None)
        opp_b = sum(self._benefit_score_for_weather(p, weather) for p in opp_team if p is not None)

        # If opponent seems to benefit from current weather more than us, incentive to overwrite.
        cur = getattr(state, "weather", Weather.CLEAR)
        override_bonus = 0.0
        if cur in (Weather.RAIN, Weather.SUN) and cur != weather:
            opp_cur = sum(self._benefit_score_for_weather(p, cur) for p in opp_team if p is not None)
            my_cur = sum(self._benefit_score_for_weather(p, cur) for p in my_team if p is not None)
            override_bonus = max(0.0, (opp_cur - my_cur) * 0.12)

        return (my_b - opp_b) + override_bonus

    def _find_weather_move_index(self, pkm: BattlingPokemon, weather: Weather) -> Optional[int]:
        for i, bm in enumerate(getattr(pkm, "battling_moves", []) or []):
            mv = getattr(bm, "constants", bm)
            if getattr(mv, "weather_start", Weather.CLEAR) == weather:
                if getattr(bm, "pp", 0) > 0 and not getattr(bm, "disabled", False):
                    return i
        return None
        
    def _maybe_force_weather(self, state: State) -> Optional[tuple[int, list[BattleCommand]]]:
        """
        v2:
        - Decide best weather (RAIN/SUN) if advantage is high enough.
        - Force weather only on slots that have a setter move available.
        - Return (best_weather, partial_cmds) where partial_cmds contains
          forced commands for some slots and None for others.

        Return None if we should not force weather this turn.
        """
        cur = getattr(state, "weather", Weather.CLEAR)

        # cooldown
        if self._turn - self._last_forced_turn <= self.cooldown_turns:
            return None

        # choose best weather among (RAIN, SUN)
        best_w = None
        best_adv = -1e18
        for w in (Weather.RAIN, Weather.SUN):
            if w == cur:
                continue
            adv = self._team_weather_advantage(state, w)
            if adv > best_adv:
                best_adv = adv
                best_w = w

        if best_w is None or best_adv < self.force_threshold:
            return None

        my_active = state.sides[0].team.active
        if not my_active:
            return None

        partial: list[Optional[BattleCommand]] = []
        forced_any = False

        for p in my_active:
            if p is None or p.hp <= 0:
                partial.append((-1, 0))
                continue

            mi = self._find_weather_move_index(p, best_w)
            if mi is None:
                partial.append(None)  # not forced on this slot
            else:
                partial.append((int(mi), 0))
                forced_any = True

        if not forced_any:
            return None

        self._last_forced_turn = self._turn
        
        # return best weather and partial forced actions
        return (int(best_w), [c for c in partial])  # keep structure simple

    def decision(self, state: State, opp_view: Optional[TeamView] = None) -> list[BattleCommand]:
        self._turn += 1

        # keep inner synced
        try:
            self.inner.set_params(self.params)
        except Exception:
            pass

        # First, get inner (MCTS) decision as baseline
        try:
            base_cmds = self.inner.decision(state, opp_view)
        except Exception:
            gp = GreedyBattlePolicy()
            gp.set_params(self.params)
            base_cmds = gp.decision(TeamView(state, 0))

        # Ensure base_cmds length matches number of active slots
        my_active = state.sides[0].team.active
        n_slots = len(my_active) if my_active is not None else len(base_cmds)
        if n_slots <= 0:
            return base_cmds

        if not isinstance(base_cmds, list):
            base_cmds = list(base_cmds)

        # pad if needed
        while len(base_cmds) < n_slots:
            base_cmds.append((0, 0))

        # Try forcing weather partially (v2)
        try:
            forced = self._maybe_force_weather(state)
        except Exception:
            forced = None

        if forced is None:
            return base_cmds

        _best_w_int, partial_forced = forced

        # Overlay forced commands onto base commands
        out: list[BattleCommand] = []
        for i in range(n_slots):
            fc = partial_forced[i] if i < len(partial_forced) else None
            if fc is None:
                out.append(base_cmds[i])
            else:
                out.append(fc)

        return out


# This is the class you should import in competitor.py for CHAMPIONSHIP submission.
class ChampionshipBattlePolicy(ChampionshipWeatherBattlePolicy):
    def __init__(self, time_limit_ms: int = 90):
        super().__init__(inner=EnhancedBattlePolicy(time_limit_ms=time_limit_ms), time_limit_ms=time_limit_ms)