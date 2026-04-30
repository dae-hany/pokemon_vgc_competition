"""
Enhanced Battle Policy for VGC AI Competition 2026.

Strategy: Framework's GreedyBattlePolicy (proven strong) + Enhanced Switching.

Key insight from benchmarking:
- Framework Greedy's double battle logic exhaustively enumerates ALL (move, target)
  combinations and picks the one maximizing 1000*KO + damage. This is already optimal
  for pure-attack decisions.
- Where we CAN improve: SWITCHING. Greedy NEVER switches.
  Smart switching adds value when:
  1. Current pokemon is about to be KO'd (defensive switch)
  2. A reserve pokemon has much better matchup (offensive switch)
  3. Current pokemon has no effective moves vs opponents (type disadvantage switch)
"""
from typing import Optional

from vgc2.agent import BattlePolicy
from vgc2.agent.battle import GreedyBattlePolicy
from vgc2.battle_engine import (
    State, BattleCommand, BattleRuleParam, TeamView,
    BattlingPokemon, calculate_damage
)
from vgc2.battle_engine.modifiers import Status, Stat, Category


class EnhancedBattlePolicy(BattlePolicy):
    """
    Framework Greedy + Enhanced Switching.
    Greedy handles move selection (proven optimal for 1-turn lookahead).
    We add switching logic that Greedy completely lacks.
    """

    def __init__(self):
        self.greedy = GreedyBattlePolicy()

    def decision(self,
                 state: State,
                 opp_view: Optional[TeamView] = None) -> list[BattleCommand]:
        try:
            # Get greedy baseline (optimal move selection)
            greedy_cmds = self.greedy.decision(state, opp_view)

            my_team = state.sides[0].team
            opp_team = state.sides[1].team
            result = list(greedy_cmds)

            # Evaluate switching for each active pokemon
            for idx, pkm in enumerate(my_team.active):
                if idx >= len(result):
                    break
                if pkm.fainted():
                    continue
                # Don't override if greedy already chose a move with high value
                # Check if switching would be better
                switch_decision = self._evaluate_switch(
                    pkm, idx, my_team, opp_team, state, result[idx]
                )
                if switch_decision is not None:
                    result[idx] = switch_decision

            return result

        except Exception:
            return self.greedy.decision(state, opp_view)

    def _evaluate_switch(self, pkm, idx, my_team, opp_team, state, current_cmd):
        """
        Evaluate if switching is better than the greedy-chosen move.
        Returns (-1, reserve_idx) if switching is recommended, None otherwise.
        """
        reserve = my_team.reserve
        if not reserve or all(r.fainted() for r in reserve):
            return None

        hp_ratio = pkm.hp / pkm.constants.stats[Stat.MAX_HP]

        # Calculate threat level: max damage any opponent can deal to us
        max_incoming = 0
        for opp in opp_team.active:
            if opp.fainted():
                continue
            for move in opp.battling_moves:
                if move.pp <= 0 or move.disabled:
                    continue
                if move.constants.category not in (Category.PHYSICAL, Category.SPECIAL):
                    continue
                try:
                    dmg = calculate_damage(self.params, 1, move.constants, state, opp, pkm)
                    max_incoming = max(max_incoming, dmg)
                except Exception:
                    continue

        # Calculate our best offensive output
        my_best_dmg = 0
        for move in pkm.battling_moves:
            if move.pp <= 0 or move.disabled:
                continue
            for opp in opp_team.active:
                if opp.fainted():
                    continue
                try:
                    dmg = calculate_damage(self.params, 0, move.constants, state, pkm, opp)
                    my_best_dmg = max(my_best_dmg, dmg)
                except Exception:
                    continue

        # --- Switching Conditions ---

        # Condition 1: SURVIVAL SWITCH
        # About to be KO'd AND has low HP AND not dealing great damage
        will_be_ko = max_incoming >= pkm.hp
        low_hp = hp_ratio < 0.3
        not_threatening = my_best_dmg < 50  # not dealing much damage

        if will_be_ko and low_hp and not_threatening:
            best = self._find_best_reserve(pkm, reserve, opp_team, state)
            if best is not None:
                return (-1, best)

        # Condition 2: TYPE DISADVANTAGE SWITCH
        # Our pokemon has no effective attacks AND a reserve has much better matchup
        if my_best_dmg < 30 and hp_ratio > 0.5:
            best = self._find_offensive_reserve(reserve, opp_team, state, threshold=80)
            if best is not None:
                return (-1, best)

        # Condition 3: STATUS + LOW HP SWITCH
        # Badly statused (burn/toxic/freeze) and low HP
        bad_status = pkm.status in (Status.BURN, Status.TOXIC, Status.FROZEN, Status.SLEEP)
        if bad_status and hp_ratio < 0.4:
            best = self._find_best_reserve(pkm, reserve, opp_team, state)
            if best is not None:
                return (-1, best)

        return None

    def _find_best_reserve(self, current_pkm, reserve, opp_team, state):
        """Find the best reserve pokemon to switch to."""
        best_idx = None
        best_score = -1

        current_hp_ratio = current_pkm.hp / current_pkm.constants.stats[Stat.MAX_HP]

        for i, r_pkm in enumerate(reserve):
            if r_pkm.fainted():
                continue

            r_hp_ratio = r_pkm.hp / r_pkm.constants.stats[Stat.MAX_HP]

            # Must have decent HP
            if r_hp_ratio < 0.3:
                continue

            score = r_hp_ratio * 100

            # Bonus for offensive potential
            for opp in opp_team.active:
                if opp.fainted():
                    continue
                for move in r_pkm.battling_moves:
                    if move.pp <= 0 or move.disabled:
                        continue
                    try:
                        dmg = calculate_damage(self.params, 0, move.constants, state, r_pkm, opp)
                        score += dmg * 0.3
                    except Exception:
                        continue

            # Speed bonus
            score += r_pkm.constants.stats[Stat.SPEED] * 0.05

            if score > best_score:
                best_score = score
                best_idx = i

        # Only switch if reserve is meaningfully better
        if best_idx is not None and best_score > current_hp_ratio * 100 + 30:
            return best_idx

        return None

    def _find_offensive_reserve(self, reserve, opp_team, state, threshold=80):
        """Find a reserve pokemon with much better offensive matchup."""
        best_idx = None
        best_dmg = threshold  # minimum damage threshold

        for i, r_pkm in enumerate(reserve):
            if r_pkm.fainted():
                continue
            r_hp = r_pkm.hp / r_pkm.constants.stats[Stat.MAX_HP]
            if r_hp < 0.4:
                continue

            for opp in opp_team.active:
                if opp.fainted():
                    continue
                for move in r_pkm.battling_moves:
                    if move.pp <= 0 or move.disabled:
                        continue
                    try:
                        dmg = calculate_damage(self.params, 0, move.constants, state, r_pkm, opp)
                        if dmg > best_dmg:
                            best_dmg = dmg
                            best_idx = i
                    except Exception:
                        continue

        return best_idx

    def set_params(self, params: BattleRuleParam):
        super().set_params(params)
        self.greedy.set_params(params)
