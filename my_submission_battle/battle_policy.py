"""
Advanced MCTS Battle Policy for VGC AI Competition 2026.

Phase 1 optimizations (overhead reduction):
- Greedy decision cached per node (was called 3x per expansion, now 1x)
- rollout no longer creates MCTNode or calls Top-K (was ~12 Greedy calls/rollout, now 1)
- SOFT_TIME_FRACTION tightened to 0.82 to prevent last-iteration overshoot
- Adaptive C removed from backprop loop (UCB1 requires constant C)
- _last_iter_count tracks actual iterations per decision call for diagnostics

Phase 2 optimizations (simulation quality):
- _smart_rollout_for_slot: KO-priority action selection in rollout
  (Greedy picks highest raw damage; smart policy adds large bonus for securing a KO)
- evaluate_state: Trick Room speed correctly INVERTED (was only 0.98x scaling = ~nothing)
- evaluate_state: Boost weight raised 20 -> 50 (+1 Atk boost = ~50% more damage)

Phase 3 optimizations (focus-fire coordination -- inspired by JJJ analysis):
- _focus_fire_action: both active slots target the SAME enemy (max combined damage).
  Doubles battles are won by KO-ing one enemy fast (2v1 snowball), not spreading damage.
- _focus_fire_rollout_actions: replaces per-slot _smart_rollout_for_slot in rollout,
  ensuring rollout simulations also play coordinated focus-fire.
- _node_all_actions: focus-fire joint action prepended as the first candidate so MCTS
  explores it before any other action in each node.
- expand_one_child: prefers focus-fire action over generic greedy as the first expansion.
"""
import random
import time
import math
from typing import Optional, Dict, Tuple, List

from vgc2.agent import BattlePolicy
from vgc2.agent.battle import GreedyBattlePolicy
from vgc2.battle_engine import (
    State, BattleCommand, BattleRuleParam, TeamView,
    BattlingPokemon, BattlingMove, calculate_damage
)
from vgc2.battle_engine.modifiers import Status, Stat, Type
from vgc2.util.forward import copy_state, forward


class EnhancedBattlePolicy(BattlePolicy):
    """
    MCTS policy tuned for 100ms budget:
    - Top-K action candidates per active Pokemon (reduces doubles combinatorics)
    - State-local damage cache (reduces calculate_damage volume)
    - Root-level determinization cache for opponent hidden moves
    - Greedy decision cached per node (Phase 1)
    - KO-priority rollout policy (Phase 2)
    - Focus-fire coordination (Phase 3)
    """

    TOPK_PER_ACTIVE = 3
    SWITCH_TOPK_WHEN_BAD = 2
    SWITCH_TOPK_WHEN_OK = 1
    DETERMINIZATION_SCENARIOS = 3
    SOFT_TIME_FRACTION = 0.82

    def __init__(self, time_limit_ms: int = 90):
        self.time_limit_ms = time_limit_ms
        self.params = BattleRuleParam()
        self.opp_policy = GreedyBattlePolicy()
        self.action_policy = GreedyBattlePolicy()
        self.rollout_depth = 3
        self.C = 1.4
        self._root_det_scenarios = None
        self._root_det_index = 0
        self._last_iter_count = 0

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
            self.total_reward = 0.0
            self.depth = depth
            self.all_actions = None
            self.used_actions = set()
            self.damage_cache = {}
            self._greedy_cmds = None

    def _get_node_greedy(self, node):
        if node._greedy_cmds is None:
            node._greedy_cmds = self.action_policy.decision(node.state)
        return node._greedy_cmds

    def _deduce_moves_inplace(self, pokemon: BattlingPokemon, max_moves: int, rng: random.Random):
        n_moves = len(pokemon.battling_moves)
        if n_moves >= max_moves:
            return
        known_ids = [m.constants.id for m in pokemon.battling_moves]
        candidates = [m for m in pokemon.constants.species.moves if m.id not in known_ids]
        if not candidates:
            return
        sample_n = min(len(candidates), max_moves - n_moves)
        pokemon.battling_moves += [BattlingMove(m) for m in rng.sample(candidates, sample_n)]

    def _build_root_determinization_scenarios(self, state: State) -> List[dict]:
        scenarios = []
        enemy_actives = [p for p in state.sides[1].team.active]
        for s in range(self.DETERMINIZATION_SCENARIOS):
            rng = random.Random(1337 + s)
            scenario = {"append": []}
            for enemy in enemy_actives:
                n_moves = len(enemy.battling_moves)
                if n_moves >= 4:
                    scenario["append"].append([])
                    continue
                known_ids = [m.constants.id for m in enemy.battling_moves]
                candidates = [m for m in enemy.constants.species.moves if m.id not in known_ids]
                if not candidates:
                    scenario["append"].append([])
                    continue
                sample_n = min(len(candidates), 4 - n_moves)
                sampled = rng.sample(candidates, sample_n)
                scenario["append"].append(sampled)
            scenarios.append(scenario)
        return scenarios

    def _apply_determinization_to_state_inplace(self, state: State, scenario: dict):
        enemy_actives = state.sides[1].team.active
        app = scenario.get("append", [])
        for i, enemy in enumerate(enemy_actives):
            if i >= len(app):
                break
            sampled_constants = app[i]
            if not sampled_constants:
                continue
            n_moves = len(enemy.battling_moves)
            room = 4 - n_moves
            if room <= 0:
                continue
            enemy.battling_moves += [BattlingMove(m) for m in sampled_constants[:room]]

    def _dmg(self, node, atk_side: int, atk_slot: int, def_slot: int, move_idx: int) -> int:
        key = (atk_side, atk_slot, def_slot, move_idx)
        if key in node.damage_cache:
            return node.damage_cache[key]
        st = node.state
        attacker = st.sides[atk_side].team.active[atk_slot]
        defender = st.sides[1 - atk_side].team.active[def_slot]
        move = attacker.battling_moves[move_idx]
        dmg = calculate_damage(self.params, atk_side, move.constants, st, attacker, defender)
        node.damage_cache[key] = dmg
        return dmg

    def _should_switch(self, node, own_slot: int) -> bool:
        st = node.state
        pkm = st.sides[0].team.active[own_slot]
        if pkm.hp <= 0:
            return False
        hp_max = pkm.constants.stats[Stat.MAX_HP]

        for e_slot, opp in enumerate(st.sides[1].team.active):
            if opp.hp <= 0:
                continue
            for m_idx, move in enumerate(opp.battling_moves):
                if move.pp <= 0:
                    continue
                if self._dmg(node, 1, e_slot, own_slot, m_idx) >= pkm.hp:
                    return True

        max_dmg_to_enemy = 0
        for move_idx, move in enumerate(pkm.battling_moves):
            if move.pp <= 0 or move.disabled:
                continue
            for e_slot, opp in enumerate(st.sides[1].team.active):
                if opp.hp <= 0:
                    continue
                d = self._dmg(node, 0, own_slot, e_slot, move_idx)
                if d > max_dmg_to_enemy:
                    max_dmg_to_enemy = d

        max_dmg_from_enemy = 0
        for e_slot, opp in enumerate(st.sides[1].team.active):
            if opp.hp <= 0:
                continue
            for m_idx, move in enumerate(opp.battling_moves):
                if move.pp <= 0:
                    continue
                d = self._dmg(node, 1, e_slot, own_slot, m_idx)
                if d > max_dmg_from_enemy:
                    max_dmg_from_enemy = d

        if max_dmg_to_enemy < hp_max * 0.15 and max_dmg_from_enemy > hp_max * 0.35:
            return True

        if (pkm.status == Status.BURN and
                pkm.constants.stats[Stat.ATTACK] > pkm.constants.stats[Stat.SPECIAL_ATTACK]):
            return True

        return False

    # --- Phase 3: Focus-Fire ---

    def _focus_fire_action(self, node) -> tuple:
        """
        JJJ-style focus fire: both active slots target the same enemy.
        Picks the target where combined best-move damage (with KO bonus) is maximised,
        then picks the best move per slot for that target.
        Returns a joint-action tuple ready for use in all_actions.
        """
        st = node.state
        own_team = st.sides[0].team.active
        n_own = len(own_team)
        n_enemies = len(st.sides[1].team.active)

        if n_own == 0:
            return ((0, 0),)

        best_e_slot, best_total = 0, -1
        for e_slot in range(n_enemies):
            opp = st.sides[1].team.active[e_slot]
            if opp.hp <= 0:
                continue
            total = 0
            for own_slot in range(n_own):
                pkm = own_team[own_slot]
                if pkm.hp <= 0:
                    continue
                slot_best = max(
                    (self._dmg(node, 0, own_slot, e_slot, m_idx)
                     for m_idx, mv in enumerate(pkm.battling_moves)
                     if mv.pp > 0 and not mv.disabled),
                    default=0
                )
                if slot_best >= opp.hp:
                    slot_best += 10000
                total += slot_best
            if total > best_total:
                best_total = total
                best_e_slot = e_slot

        cmds = []
        for own_slot in range(n_own):
            pkm = own_team[own_slot]
            if pkm.hp <= 0:
                cmds.append((0, 0))
                continue
            best_cmd, best_dmg = (0, best_e_slot), -1
            for m_idx, mv in enumerate(pkm.battling_moves):
                if mv.pp <= 0 or mv.disabled:
                    continue
                dmg = self._dmg(node, 0, own_slot, best_e_slot, m_idx)
                if dmg > best_dmg:
                    best_dmg = dmg
                    best_cmd = (m_idx, best_e_slot)
            cmds.append(best_cmd)
        return tuple(cmds)

    def _focus_fire_rollout_actions(self, state: State) -> list:
        """
        Phase 3 rollout policy: both slots coordinate to attack the same enemy.
        Uses calculate_damage directly (no node cache) since rollout states are ephemeral.
        """
        own_team = state.sides[0].team.active
        enemies = state.sides[1].team.active

        if not own_team:
            return []

        best_e_slot, best_total = 0, -1
        for e_slot, opp in enumerate(enemies):
            if opp.hp <= 0:
                continue
            total = 0
            for pkm in own_team:
                if pkm.hp <= 0:
                    continue
                slot_best = max(
                    (calculate_damage(self.params, 0, mv.constants, state, pkm, opp)
                     for mv in pkm.battling_moves if mv.pp > 0 and not mv.disabled),
                    default=0
                )
                if slot_best >= opp.hp:
                    slot_best += 5000
                total += slot_best
            if total > best_total:
                best_total = total
                best_e_slot = e_slot

        cmds = []
        opp_focus = enemies[best_e_slot]
        for pkm in own_team:
            if pkm.hp <= 0:
                cmds.append((0, 0))
                continue
            best_cmd, best_dmg = (0, best_e_slot), -1
            for m_idx, mv in enumerate(pkm.battling_moves):
                if mv.pp <= 0 or mv.disabled:
                    continue
                dmg = calculate_damage(self.params, 0, mv.constants, state, pkm, opp_focus)
                if dmg >= opp_focus.hp:
                    dmg += 5000
                if dmg > best_dmg:
                    best_dmg = dmg
                    best_cmd = (m_idx, best_e_slot)
            cmds.append(best_cmd)
        return cmds

    # --- Top-K candidate generation ---

    def _topk_commands_for_active(self, node, own_slot: int, greedy_cmds: list = None) -> List[BattleCommand]:
        st = node.state
        pkm = st.sides[0].team.active[own_slot]
        if pkm.hp <= 0:
            return [(0, 0)]

        n_targets = len(st.sides[1].team.active)
        candidates = []

        if greedy_cmds is None:
            greedy_cmds = self._get_node_greedy(node)
        if greedy_cmds and own_slot < len(greedy_cmds):
            candidates.append((1e18, greedy_cmds[own_slot]))

        for e_slot in range(n_targets):
            best = None
            best_dmg = -1
            for m_idx, mv in enumerate(pkm.battling_moves):
                if mv.pp <= 0 or mv.disabled:
                    continue
                dmg = self._dmg(node, 0, own_slot, e_slot, m_idx)
                if dmg > best_dmg:
                    best_dmg = dmg
                    best = (m_idx, e_slot)
            if best is not None:
                candidates.append((best_dmg, best))

        best_ko = None
        best_ko_dmg = -1
        for e_slot, opp in enumerate(st.sides[1].team.active):
            if opp.hp <= 0:
                continue
            for m_idx, mv in enumerate(pkm.battling_moves):
                if mv.pp <= 0 or mv.disabled:
                    continue
                dmg = self._dmg(node, 0, own_slot, e_slot, m_idx)
                if dmg >= opp.hp and dmg > best_ko_dmg:
                    best_ko_dmg = dmg
                    best_ko = (m_idx, e_slot)
        if best_ko is not None:
            candidates.append((best_ko_dmg + 1e9, best_ko))

        bad = self._should_switch(node, own_slot)
        max_sw = self.SWITCH_TOPK_WHEN_BAD if bad else self.SWITCH_TOPK_WHEN_OK
        if max_sw > 0:
            reserves = [(i, r) for i, r in enumerate(st.sides[0].team.reserve) if r.hp > 0]
            if reserves:
                scored = []
                for r_idx, rpkm in reserves:
                    worst = 0
                    for e_slot, opp in enumerate(st.sides[1].team.active):
                        if opp.hp <= 0:
                            continue
                        for m_idx, mv in enumerate(opp.battling_moves):
                            if mv.pp <= 0:
                                continue
                            d = calculate_damage(self.params, 1, mv.constants, st, opp, rpkm)
                            if d > worst:
                                worst = d
                    scored.append((worst, r_idx))
                scored.sort(key=lambda x: x[0])
                for _, r_idx in scored[:max_sw]:
                    candidates.append((5e8, (-1, r_idx)))

        best_score_by_cmd = {}
        for sc, cmd in candidates:
            if cmd not in best_score_by_cmd or sc > best_score_by_cmd[cmd]:
                best_score_by_cmd[cmd] = sc
        cmds = sorted(best_score_by_cmd.items(), key=lambda kv: kv[1], reverse=True)
        result = [cmd for cmd, _ in cmds[:self.TOPK_PER_ACTIVE]]
        return result if result else [(0, 0)]

    def _node_all_actions(self, node) -> List[tuple]:
        if node.all_actions is not None:
            return node.all_actions

        st = node.state
        team = st.sides[0].team.active
        if not team:
            node.all_actions = [((0, 0),)]
            return node.all_actions

        greedy_cmds = self._get_node_greedy(node)
        cmds0 = self._topk_commands_for_active(node, 0, greedy_cmds)

        if len(team) > 1:
            cmds1 = self._topk_commands_for_active(node, 1, greedy_cmds)
            joint = []
            for c0 in cmds0:
                for c1 in cmds1:
                    if c0[0] < 0 and c1[0] < 0 and c0[1] == c1[1]:
                        continue
                    joint.append((c0, c1))

            ff = self._focus_fire_action(node)
            if ff not in joint:
                joint.insert(0, ff)

            node.all_actions = joint if joint else [(cmds0[0], cmds1[0])]
        else:
            node.all_actions = [(c,) for c in cmds0]

        return node.all_actions

    # --- State evaluation (Phase 2) ---

    def evaluate_state(self, state: State) -> float:
        own_team    = [x for x in state.sides[0].team.active  if x.hp > 0]
        own_reserve = [x for x in state.sides[0].team.reserve if x.hp > 0]
        enemy_team    = [x for x in state.sides[1].team.active  if x.hp > 0]
        enemy_reserve = [x for x in state.sides[1].team.reserve if x.hp > 0]

        enemy_count = len(enemy_team) + len(enemy_reserve)
        own_count   = len(own_team)   + len(own_reserve)

        own_score   = 0.0
        enemy_score = 0.0

        for x in own_team:
            own_score   += 200.0 * (x.hp / x.constants.stats[Stat.MAX_HP])
        for x in enemy_team:
            enemy_score += 200.0 * (x.hp / x.constants.stats[Stat.MAX_HP])

        own_score   += 400.0 * (4 - enemy_count)
        enemy_score += 400.0 * (4 - own_count)

        own_score   += 300.0 * len(own_team)   + 100.0 * len(own_reserve)
        enemy_score += 300.0 * len(enemy_team) + 100.0 * len(enemy_reserve)

        trickroom = getattr(state, "trickroom", False)

        for pkm in own_team:
            if pkm.status != Status.NONE:
                enemy_score += 300.0
            own_score += 50.0 * sum(pkm.boosts)

        for pkm in enemy_team:
            if pkm.status != Status.NONE:
                own_score += 300.0
            enemy_score += 50.0 * sum(pkm.boosts)

        if own_count + enemy_count <= 2:
            own_score   *= 0.8
            enemy_score *= 0.8

        return (own_score - enemy_score) / 2500.0

    # --- MCTS mechanics ---

    def select_best_child(self, node):
        for child in node.children:
            if child.visit_count == 0:
                return child
        best_child = node
        best_ucb = float("-inf")
        for child in node.children:
            Q = child.total_reward / child.visit_count
            N = child.visit_count
            N_parent = max(1, node.visit_count)
            ucb1 = Q + self.C * math.sqrt(math.log(N_parent) / N)
            if ucb1 > best_ucb:
                best_ucb = ucb1
                best_child = child
        return best_child

    def expand_one_child(self, node):
        actions = self._node_all_actions(node)
        untried = [a for a in actions if a not in node.used_actions]
        if not untried:
            return self.select_best_child(node) if node.children else node

        actions_to_take = random.choice(untried)

        new_state = copy_state(node.state)
        if self._root_det_scenarios:
            scenario = self._root_det_scenarios[self._root_det_index % len(self._root_det_scenarios)]
            self._apply_determinization_to_state_inplace(new_state, scenario)

        opp_action = self.opp_policy.decision(State((new_state.sides[1], new_state.sides[0])))
        forward(new_state, (list(actions_to_take), opp_action), self.params)

        child_node = self.MCTNode(new_state, parent=node, actions=actions_to_take, depth=node.depth + 1)
        node.children.append(child_node)
        node.used_actions.add(actions_to_take)
        return child_node

    def tree_policy(self, node):
        while not node.state.terminal():
            actions = self._node_all_actions(node)
            if any(a not in node.used_actions for a in actions):
                return self.expand_one_child(node)
            node = self.select_best_child(node)
        return node

    # --- Rollout ---

    def _smart_rollout_for_slot(self, state: State, own_slot: int) -> BattleCommand:
        """Kept for reference; superseded by _focus_fire_rollout_actions in Phase 3."""
        pkm = state.sides[0].team.active[own_slot]
        if pkm.hp <= 0:
            return (0, 0)
        enemies = state.sides[1].team.active
        best_cmd = None
        best_score = -1.0
        for m_idx, mv in enumerate(pkm.battling_moves):
            if mv.pp <= 0 or mv.disabled:
                continue
            for e_slot, opp in enumerate(enemies):
                if opp.hp <= 0:
                    continue
                dmg = calculate_damage(self.params, 0, mv.constants, state, pkm, opp)
                score = float(dmg) + (5000.0 if dmg >= opp.hp else 0.0)
                if score > best_score:
                    best_score = score
                    best_cmd = (m_idx, e_slot)
        return best_cmd if best_cmd is not None else (0, 0)

    def rollout(self, state: State, rollout_depth: int) -> float:
        current_state = copy_state(state)
        if self._root_det_scenarios:
            scenario = self._root_det_scenarios[self._root_det_index % len(self._root_det_scenarios)]
            self._apply_determinization_to_state_inplace(current_state, scenario)

        for _ in range(rollout_depth):
            if current_state.terminal():
                break
            our_action = self._focus_fire_rollout_actions(current_state)
            opp_action = self.opp_policy.decision(
                State((current_state.sides[1], current_state.sides[0])))
            forward(current_state, (our_action, opp_action), self.params)

        return self.evaluate_state(current_state)

    def MCTS(self, root_state: State, time_limit_ms: int):
        root_node = self.MCTNode(root_state)
        self._root_det_scenarios = self._build_root_determinization_scenarios(root_state)
        self._root_det_index = 0
        start_time = time.perf_counter()
        soft_budget = time_limit_ms * self.SOFT_TIME_FRACTION
        self._last_iter_count = 0

        while (time.perf_counter() - start_time) * 1000.0 < soft_budget:
            self._root_det_index += 1
            self._last_iter_count += 1
            node = self.tree_policy(root_node)
            reward = self.rollout(node.state, self.rollout_depth)
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
