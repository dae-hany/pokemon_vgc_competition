"""
Battle Policy for VGC AI Competition 2026.

Uses framework's GreedyBattlePolicy as core (proven strong vs Random: 20-0),
with smart switching logic added on top.

GreedyBattlePolicy already handles:
- Damage calculation considering type effectiveness, STAB, weather, terrain
- KO prioritization (1000*ko + damage scoring)
- Both single and double battle formats
"""
from typing import Optional

from vgc2.agent import BattlePolicy
from vgc2.agent.battle import GreedyBattlePolicy
from vgc2.battle_engine import (
    State, BattleCommand, BattleRuleParam, calculate_damage,
    TeamView
)
from vgc2.battle_engine.modifiers import Stat, Status, Category


class EnhancedBattlePolicy(BattlePolicy):
    """
    Enhanced Greedy with smart switching.
    Framework's GreedyBattlePolicy as base + switch evaluation.
    """

    def __init__(self, max_depth: int = 1, max_moves: int = 4):
        self.greedy = GreedyBattlePolicy()

    def decision(self,
                 state: State,
                 opp_view: Optional[TeamView] = None) -> list[BattleCommand]:
        # Get greedy baseline commands
        greedy_cmds = self.greedy.decision(state, opp_view)

        # Evaluate if switching would be better for any active pokemon
        my_team = state.sides[0].team
        opp_team = state.sides[1].team
        result = list(greedy_cmds)

        for idx, pkm in enumerate(my_team.active):
            if pkm.fainted():
                continue

            # Check if current pokemon is in a bad situation
            should_switch, switch_target = self._should_switch(
                pkm, idx, my_team, opp_team, state
            )
            if should_switch and switch_target is not None:
                result[idx] = (-1, switch_target)

        return result

    def _should_switch(self, pkm, idx, my_team, opp_team, state):
        """Evaluate if switching is beneficial."""
        reserve = my_team.reserve

        # No reserve available
        if not reserve or all(r.fainted() for r in reserve):
            return False, None

        # Don't switch if HP is high and doing well
        hp_ratio = pkm.hp / pkm.constants.stats[Stat.MAX_HP]

        # Check if we're taking super-effective hits
        is_threatened = False
        for opp in opp_team.active:
            if opp.fainted():
                continue
            for move in opp.battling_moves:
                if move.pp <= 0 or move.disabled:
                    continue
                if move.constants.category not in (Category.PHYSICAL, Category.SPECIAL):
                    continue
                dmg = calculate_damage(self.params, 1, move.constants, state, opp, pkm)
                if dmg > pkm.hp * 0.6:
                    is_threatened = True
                    break

        # Only switch if threatened AND we have a better option
        if is_threatened and hp_ratio < 0.4:
            # Find best reserve pokemon
            best_idx = None
            best_score = -1
            for i, reserve_pkm in enumerate(reserve):
                if reserve_pkm.fainted():
                    continue
                r_hp_ratio = reserve_pkm.hp / reserve_pkm.constants.stats[Stat.MAX_HP]
                # Prefer higher HP ratio
                score = r_hp_ratio * 100
                # Bonus for speed advantage
                score += reserve_pkm.constants.stats[Stat.SPEED] * 0.1
                if score > best_score:
                    best_score = score
                    best_idx = i

            if best_idx is not None and best_score > hp_ratio * 100 + 20:
                return True, best_idx

        return False, None

    def set_params(self, params: BattleRuleParam):
        super().set_params(params)
        self.greedy.set_params(params)
