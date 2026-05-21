"""
Advanced MCTS Battle Policy for VGC AI Competition 2026.

Improved version (design-driven):
- Top-K action candidates per active Pokémon (reduces doubles combinatorics)
- State-local damage cache (reduces calculate_damage volume)
- Root-level determinization cache for opponent hidden moves (reduces variance + overhead)
- Keeps ~100ms constraint by internal soft budget
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
    MCTS policy tuned for 100ms-ish budget:
    - limits branching factor (Top-K)
    - caches damage for current state snapshot
    - caches opponent move determinization for this decision call
    """

    # ----------------------------
    # Tunables (you can tweak)
    # ----------------------------
    TOPK_PER_ACTIVE = 5            # set to 4 if time is tight
    SWITCH_TOPK_WHEN_BAD = 2       # max switch candidates if "should switch" is True
    SWITCH_TOPK_WHEN_OK = 0        # 0 or 1; keep 0 initially to avoid explosion
    DETERMINIZATION_SCENARIOS = 3  # set to 2 if time is tight
    SOFT_TIME_FRACTION = 0.88      # use ~88% of budget inside MCTS loop

    def __init__(self, time_limit_ms: int = 90):
        self.time_limit_ms = time_limit_ms
        self.params = BattleRuleParam()
        self.opp_policy = GreedyBattlePolicy()
        self.action_policy = GreedyBattlePolicy()

        # MCTS params
        self.rollout_depth = 4
        self.C = 1.4

        # root-level caches (per decision)
        self._root_det_scenarios = None  # type: Optional[List[dict]]
        self._root_det_index = 0

    def set_params(self, params: BattleRuleParam):
        super().set_params(params)
        self.params = params
        self.opp_policy.set_params(params)
        self.action_policy.set_params(params)

    class MCTNode:
        def __init__(self, state: State, actions=None, parent=None, depth=0):
            self.state = state
            self.parent = parent
            self.actions = actions  # tuple of commands for our side (per active slot)
            self.children = []
            self.visit_count = 0
            self.total_reward = 0.0
            self.depth = depth

            # cached action list for this node (list of tuple-of-commands)
            self.all_actions = None  # type: Optional[List[tuple]]
            self.used_actions = set()

            # local caches (valid only for this exact state snapshot)
            self.damage_cache = {}  # type: Dict[Tuple[int,int,int,int], int]

    # ----------------------------
    # Determinization for opponent hidden moves
    # ----------------------------
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
        """
        Build a small set of opponent hidden-move fillings for this decision call.
        Each scenario stores, per enemy active slot, a list of BattlingMove objects to append.
        We do NOT mutate root state here; we store what to apply later.
        """
        scenarios = []
        # We must be careful: state may already have some battling_moves; we only fill up to 4.
        enemy_actives = [p for p in state.sides[1].team.active]

        for s in range(self.DETERMINIZATION_SCENARIOS):
            rng = random.Random(1337 + s)  # stable per scenario to reduce variance
            scenario = {"append": []}      # append[slot] = list[MoveConstants] to append (we'll store BattlingMove-ready)
            for enemy in enemy_actives:
                # build a sampled list of move constants to append (do not mutate enemy here)
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
        """
        Mutate given state in-place: append sampled hidden moves to enemy actives.
        """
        enemy_actives = state.sides[1].team.active
        app = scenario.get("append", [])
        for i, enemy in enumerate(enemy_actives):
            if i >= len(app):
                break
            sampled_constants = app[i]
            if not sampled_constants:
                continue
            # append up to 4 moves total
            n_moves = len(enemy.battling_moves)
            room = 4 - n_moves
            if room <= 0:
                continue
            enemy.battling_moves += [BattlingMove(m) for m in sampled_constants[:room]]

    # ----------------------------
    # Damage cache helpers (state-local)
    # ----------------------------
    def _dmg(self, node: "EnhancedBattlePolicy.MCTNode", atk_side: int, atk_slot: int, def_slot: int, move_idx: int) -> int:
        """
        Cached calculate_damage for the node.state snapshot, using active slot indices.
        Key assumes node.state is fixed; if state changes, node changes, cache is safe.
        """
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

    # ----------------------------
    # Switching heuristic (cheaper than before using cached dmg)
    # ----------------------------
    def _should_switch(self, node: "EnhancedBattlePolicy.MCTNode", own_slot: int) -> bool:
        """
        Heuristic: consider switching if
        - enemy can KO us this turn, OR
        - our best damage is very low while enemy best damage is high, OR
        - burn on physical attacker
        """
        st = node.state
        pkm = st.sides[0].team.active[own_slot]
        if pkm.hp <= 0:
            return False

        hp_max = pkm.constants.stats[Stat.MAX_HP]

        # 1) OHKO threat: check enemy max damage against this pkm (approx by scanning their available moves)
        # We keep it simple: scan all enemy actives and their moves.
        for e_slot, opp in enumerate(st.sides[1].team.active):
            if opp.hp <= 0:
                continue
            for m_idx, move in enumerate(opp.battling_moves):
                if move.pp <= 0:
                    continue
                # no cache here because caching enemy->own also helps; reuse node cache by mapping side/slot indices
                # Enemy is side=1, attacker slot=e_slot, defender slot=own_slot, move_idx=m_idx
                dmg = self._dmg(node, 1, e_slot, own_slot, m_idx)
                if dmg >= pkm.hp:
                    return True

        # 2) Bad matchup check (very rough)
        # our max damage to any enemy
        max_dmg_to_enemy = 0
        for move_idx, move in enumerate(pkm.battling_moves):
            if move.pp <= 0 or move.disabled:
                continue
            for e_slot, opp in enumerate(st.sides[1].team.active):
                if opp.hp <= 0:
                    continue
                dmg = self._dmg(node, 0, own_slot, e_slot, move_idx)
                if dmg > max_dmg_to_enemy:
                    max_dmg_to_enemy = dmg

        # enemy max damage to us (approx)
        max_dmg_from_enemy = 0
        for e_slot, opp in enumerate(st.sides[1].team.active):
            if opp.hp <= 0:
                continue
            for m_idx, move in enumerate(opp.battling_moves):
                if move.pp <= 0:
                    continue
                dmg = self._dmg(node, 1, e_slot, own_slot, m_idx)
                if dmg > max_dmg_from_enemy:
                    max_dmg_from_enemy = dmg

        if max_dmg_to_enemy < hp_max * 0.15 and max_dmg_from_enemy > hp_max * 0.35:
            return True

        # 3) Status risk: burn on physical attacker
        if pkm.status == Status.BURN and pkm.constants.stats[Stat.ATTACK] > pkm.constants.stats[Stat.SPECIAL_ATTACK]:
            return True

        return False

    # ----------------------------
    # Top-K candidate generation
    # ----------------------------
    def _topk_commands_for_active(self, node: "EnhancedBattlePolicy.MCTNode", own_slot: int) -> List[BattleCommand]:
        """
        Return up to TOPK_PER_ACTIVE commands for given own active slot.
        Commands are BattleCommand tuples: (move_idx, enemy_idx) or (-1, reserve_idx)
        """
        st = node.state
        pkm = st.sides[0].team.active[own_slot]
        if pkm.hp <= 0:
            return [(0, 0)]

        n_targets = len(st.sides[1].team.active)
        candidates = []  # type: List[Tuple[float, BattleCommand]]

        # 1) Always include Greedy's chosen command for this slot (if possible).
        greedy_cmds = self.action_policy.decision(st)
        if greedy_cmds and own_slot < len(greedy_cmds):
            gc = greedy_cmds[own_slot]
            # push with high score to preserve
            candidates.append((1e18, gc))

        # 2) Per-target best-damage move (top1 per enemy slot)
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

        # 3) Any KO candidate: include one best KO (highest dmg among KO moves)
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
            candidates.append((best_ko_dmg + 1e9, best_ko))  # boost KO slightly

        # 4) Switch candidates (limited)
        bad = self._should_switch(node, own_slot)
        if bad:
            max_sw = self.SWITCH_TOPK_WHEN_BAD
        else:
            max_sw = self.SWITCH_TOPK_WHEN_OK

        if max_sw > 0:
            reserves = [(i, r) for i, r in enumerate(st.sides[0].team.reserve) if r.hp > 0]
            if reserves:
                # choose switch candidates by simple survivability: minimize max enemy damage into that reserve
                scored = []
                for r_idx, rpkm in reserves:
                    # approximate: enemy best damage to this reserve (loop enemy actives & their moves)
                    worst = 0
                    for e_slot, opp in enumerate(st.sides[1].team.active):
                        if opp.hp <= 0:
                            continue
                        for m_idx, mv in enumerate(opp.battling_moves):
                            if mv.pp <= 0:
                                continue
                            dmg = calculate_damage(self.params, 1, mv.constants, st, opp, rpkm)
                            if dmg > worst:
                                worst = dmg
                    scored.append((worst, r_idx))
                scored.sort(key=lambda x: x[0])  # lower worst damage is better
                for _, r_idx in scored[:max_sw]:
                    candidates.append((5e8, (-1, r_idx)))  # mid-high priority if switching is allowed

        # Deduplicate by command
        best_score_by_cmd = {}
        for sc, cmd in candidates:
            if cmd not in best_score_by_cmd or sc > best_score_by_cmd[cmd]:
                best_score_by_cmd[cmd] = sc

        # take topK by score
        cmds = sorted(best_score_by_cmd.items(), key=lambda kv: kv[1], reverse=True)
        result = [cmd for cmd, _ in cmds[: self.TOPK_PER_ACTIVE]]

        if not result:
            result = [(0, 0)]
        return result

    def _node_all_actions(self, node: "EnhancedBattlePolicy.MCTNode") -> List[tuple]:
        """
        Build and cache all candidate joint-actions for our side at this node, using Top-K per active.
        Returns list of tuple(action_for_slot0, action_for_slot1?) where each element is a BattleCommand.
        """
        if node.all_actions is not None:
            return node.all_actions

        st = node.state
        team = st.sides[0].team.active
        if not team:
            node.all_actions = [((0, 0),)]
            return node.all_actions

        cmds0 = self._topk_commands_for_active(node, 0)

        if len(team) > 1:
            cmds1 = self._topk_commands_for_active(node, 1)
            joint = []
            for c0 in cmds0:
                for c1 in cmds1:
                    # simple prune: avoid both switching to same reserve index
                    if c0[0] < 0 and c1[0] < 0 and c0[1] == c1[1]:
                        continue
                    joint.append((c0, c1))
            node.all_actions = joint if joint else [(cmds0[0], cmds1[0])]
        else:
            node.all_actions = [(c,) for c in cmds0]

        return node.all_actions

    # ----------------------------
    # MCTS mechanics
    # ----------------------------
    def evaluate_state(self, state: State) -> float:
        """
        Keep your original eval mostly, but minor cleanup: avoid huge swings from status.
        You can tune later; kept conservative to avoid regressions.
        """
        own_team = [x for x in state.sides[0].team.active if x.hp > 0]
        own_reserve = [x for x in state.sides[0].team.reserve if x.hp > 0]
        enemy_team = [x for x in state.sides[1].team.active if x.hp > 0]
        enemy_reserve = [x for x in state.sides[1].team.reserve if x.hp > 0]

        enemy_count = len(enemy_team) + len(enemy_reserve)
        own_count = len(own_team) + len(own_reserve)

        own_hps = [x.hp / x.constants.stats[Stat.MAX_HP] for x in own_team] if own_team else []
        enemy_hps = [x.hp / x.constants.stats[Stat.MAX_HP] for x in enemy_team] if enemy_team else []

        own_score = 0.0
        enemy_score = 0.0

        own_score += 50.0 * sum(own_hps)
        enemy_score += 50.0 * sum(enemy_hps)

        own_score += 400.0 * (4 - enemy_count)
        enemy_score += 400.0 * (4 - own_count)

        own_score += 300.0 * len(own_team) + 100.0 * len(own_reserve)
        enemy_score += 300.0 * len(enemy_team) + 100.0 * len(enemy_reserve)

        # Status and speed evaluation (reduced weight for status to avoid overfitting)
        for pkm in own_team:
            if pkm.status != Status.NONE:
                enemy_score += 300.0
            own_score += pkm.constants.stats[Stat.SPEED]
            own_score += 20.0 * sum(pkm.boosts)

        for pkm in enemy_team:
            if pkm.status != Status.NONE:
                own_score += 300.0
            enemy_score += pkm.constants.stats[Stat.SPEED]
            enemy_score += 20.0 * sum(pkm.boosts)

        # Trick room context (simple): invert speed contribution when trickroom is active
        if getattr(state, "trickroom", False):
            # remove original speed and add inverted (bounded) effect
            # (cheap heuristic; you can tune)
            own_score *= 0.98
            enemy_score *= 0.98

        if own_count + enemy_count <= 2:
            own_score *= 0.8
            enemy_score *= 0.8

        return own_score - enemy_score

    def select_best_child(self, node: "EnhancedBattlePolicy.MCTNode") -> "EnhancedBattlePolicy.MCTNode":
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

    def expand_one_child(self, node: "EnhancedBattlePolicy.MCTNode") -> "EnhancedBattlePolicy.MCTNode":
        actions = self._node_all_actions(node)
        untried = [a for a in actions if a not in node.used_actions]
        if not untried:
            return self.select_best_child(node) if node.children else node

        # choose one untried: bias toward Greedy-at-this-node joint action if present, else random
        greedy_joint = tuple(self.action_policy.decision(node.state))
        if greedy_joint in untried:
            actions_to_take = greedy_joint
        else:
            actions_to_take = random.choice(untried)

        # determinization: apply one fixed scenario for this iteration
        new_state = copy_state(node.state)
        if self._root_det_scenarios:
            scenario = self._root_det_scenarios[self._root_det_index % len(self._root_det_scenarios)]
            self._apply_determinization_to_state_inplace(new_state, scenario)

        # opponent action (greedy, from opponent perspective)
        opp_action = self.opp_policy.decision(State((new_state.sides[1], new_state.sides[0])))

        # forward one turn
        forward(new_state, (list(actions_to_take), opp_action), self.params)

        child_node = self.MCTNode(new_state, parent=node, actions=actions_to_take, depth=node.depth + 1)
        node.children.append(child_node)
        node.used_actions.add(actions_to_take)
        return child_node

    def tree_policy(self, node: "EnhancedBattlePolicy.MCTNode") -> "EnhancedBattlePolicy.MCTNode":
        while not node.state.terminal():
            actions = self._node_all_actions(node)
            if any(a not in node.used_actions for a in actions):
                return self.expand_one_child(node)
            node = self.select_best_child(node)
        return node

    def rollout(self, state: State, rollout_depth: int) -> float:
        current_state = copy_state(state)

        # apply determinization consistently within rollout too
        if self._root_det_scenarios:
            scenario = self._root_det_scenarios[self._root_det_index % len(self._root_det_scenarios)]
            self._apply_determinization_to_state_inplace(current_state, scenario)

        for _ in range(rollout_depth):
            if current_state.terminal():
                break

            # cheap Top-K actions for rollout as well (avoid full cartesian)
            tmp_node = self.MCTNode(current_state)
            joint_actions = self._node_all_actions(tmp_node)
            if not joint_actions:
                break

            # slightly stochastic, but not too random
            if random.random() < 0.25:
                action = random.choice(joint_actions)
            else:
                action = tuple(self.action_policy.decision(current_state))

            enemy_action = self.opp_policy.decision(State((current_state.sides[1], current_state.sides[0])))
            forward(current_state, (list(action), enemy_action), self.params)

        return self.evaluate_state(current_state)

    def MCTS(self, root_state: State, time_limit_ms: int):
        root_node = self.MCTNode(root_state)

        # build determinization scenarios once per decision call
        self._root_det_scenarios = self._build_root_determinization_scenarios(root_state)
        self._root_det_index = 0

        start_time = time.perf_counter()
        soft_budget = time_limit_ms * self.SOFT_TIME_FRACTION

        while (time.perf_counter() - start_time) * 1000.0 < soft_budget:
            # cycle determinization scenario index per iteration
            self._root_det_index += 1

            node = self.tree_policy(root_node)
            reward = self.rollout(node.state, self.rollout_depth)

            # simple adaptive exploration (keep stable)
            if reward < -600:
                self.C = 3.0
                self.rollout_depth = 5
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