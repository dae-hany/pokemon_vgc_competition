"""
1-Turn Minimax Battle Policy for General AI (VGC 2026).

Uses a fast heuristic simulation to evaluate all combinations of our moves 
against all combinations of the opponent's moves, selecting the action 
that maximizes our minimum guaranteed outcome (Minimax).
Handles Speed, Protect, and Status intrinsically.
"""
from typing import Optional
import numpy as np

from vgc2.agent import BattlePolicy
from vgc2.battle_engine import State, BattleCommand, BattleRuleParam, TeamView
from vgc2.battle_engine.modifiers import Stat, Category

# Standard type effectiveness chart
TYPE_CHART = np.array([
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, .5, 0, 1, 1, .5, 1, 1],
    [1, .5, .5, 1, 2, 2, 1, 1, 1, 1, 1, 2, .5, 1, .5, 1, 2, 1, 1],
    [1, 2, .5, 1, .5, 1, 1, 1, 2, 1, 1, 1, 2, 1, .5, 1, 1, 1, 1],
    [1, 1, 2, .5, .5, 1, 1, 1, 0, 2, 1, 1, 1, 1, .5, 1, 1, 1, 1],
    [1, .5, 2, 1, .5, 1, 1, .5, 2, .5, 1, .5, 2, 1, .5, 1, .5, 1, 1],
    [1, .5, .5, 1, 2, .5, 1, 1, 2, 2, 1, 1, 1, 1, 2, 1, .5, 1, 1],
    [2, 1, 1, 1, 1, 2, 1, .5, 1, .5, .5, .5, 2, 0, 1, 2, 2, .5, 1],
    [1, 1, 1, 1, 2, 1, 1, .5, .5, 1, 1, 1, .5, .5, 1, 1, 0, 2, 1],
    [1, 2, 1, 2, .5, 1, 1, 2, 1, 0, 1, .5, 2, 1, 1, 1, 2, 1, 1],
    [1, 1, 1, .5, 2, 1, 2, 1, 1, 1, 1, 2, .5, 1, 1, 1, .5, 1, 1],
    [1, 1, 1, 1, 1, 1, 2, 2, 1, 1, .5, 1, 1, 1, 1, 0, .5, 1, 1],
    [1, .5, 1, 1, 2, 1, .5, .5, 1, .5, 2, 1, 1, .5, 1, 2, .5, .5, 1],
    [1, 2, 1, 1, 1, 2, .5, 1, .5, 2, 1, 2, 1, 1, 1, 1, .5, 1, 1],
    [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 2, 1, .5, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, .5, 0, 1],
    [1, 1, 1, 1, 1, 1, .5, 1, 1, 1, 2, 1, 1, 2, 1, .5, 1, .5, 1],
    [1, .5, .5, .5, 1, 2, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, .5, 2, 1],
    [1, .5, 1, 1, 1, 1, 2, .5, 1, 1, 1, 1, 1, 1, 2, 2, .5, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
], dtype=float)

def _estimate_damage(attacker, defender, move) -> float:
    if move.category not in (Category.PHYSICAL, Category.SPECIAL):
        return 0.0
    
    atk_stat = attacker.constants.stats[Stat.ATTACK] if move.category == Category.PHYSICAL else attacker.constants.stats[Stat.SPECIAL_ATTACK]
    def_stat = defender.constants.stats[Stat.DEFENSE] if move.category == Category.PHYSICAL else defender.constants.stats[Stat.SPECIAL_DEFENSE]
    
    stab = 1.5 if move.pkm_type in attacker.constants.species.types else 1.0
    eff = 1.0
    for dt in defender.constants.species.types:
        eff *= TYPE_CHART[move.pkm_type, dt]
        
    dmg = int((2 * 50 / 5) + 2)
    dmg = int(dmg * move.base_power)
    dmg = int(dmg * atk_stat / def_stat)
    dmg = int(dmg / 50) + 2
    final = dmg * stab * eff
    return final

class EnhancedBattlePolicy(BattlePolicy):
    def __init__(self, time_limit_ms: int = 90):
        self.time_limit_ms = time_limit_ms
        self.params = BattleRuleParam()

    def set_params(self, params: BattleRuleParam):
        super().set_params(params)
        self.params = params

    def get_possible_actions(self, active_team, opp_team_size):
        if not active_team:
            return [[(0, 0)]]
            
        actions1 = []
        for i, move in enumerate(active_team[0].battling_moves):
            if move.pp <= 0 or move.disabled: continue
            for j in range(opp_team_size):
                actions1.append((i, j))
        if not actions1: actions1 = [(0, 0)]
        
        if len(active_team) == 1:
            return [[a1] for a1 in actions1]
            
        actions2 = []
        for i, move in enumerate(active_team[1].battling_moves):
            if move.pp <= 0 or move.disabled: continue
            for j in range(opp_team_size):
                actions2.append((i, j))
        if not actions2: actions2 = [(0, 0)]
        
        return [[a1, a2] for a1 in actions1 for a2 in actions2]

    def _fast_simulate(self, my_active, opp_active, my_action, opp_action):
        """
        Fast heuristic evaluation of a single turn without engine overhead.
        Returns a score from our perspective (+ is good, - is bad).
        """
        score = 0.0
        
        my_hp = [p.hp for p in my_active]
        opp_hp = [p.hp for p in opp_active]
        
        my_protect = [False] * len(my_active)
        opp_protect = [False] * len(opp_active)
        
        # 1. Parse Protect
        for idx, (move_idx, target_idx) in enumerate(my_action):
            move = my_active[idx].battling_moves[move_idx].constants
            if move.protect:
                my_protect[idx] = True
                score -= 10.0 # Minor penalty to prevent protect spam if unnecessary
                
        for idx, (move_idx, target_idx) in enumerate(opp_action):
            move = opp_active[idx].battling_moves[move_idx].constants
            if move.protect:
                opp_protect[idx] = True
                
        # 2. Build execution order based on Speed and Priority
        events = []
        for idx, (move_idx, target_idx) in enumerate(my_action):
            move = my_active[idx].battling_moves[move_idx].constants
            priority = move.priority
            if move.protect: priority += 4
            speed = my_active[idx].constants.stats[Stat.SPEED]
            events.append(('my', idx, target_idx, move, priority, speed))
            
        for idx, (move_idx, target_idx) in enumerate(opp_action):
            move = opp_active[idx].battling_moves[move_idx].constants
            priority = move.priority
            if move.protect: priority += 4
            speed = opp_active[idx].constants.stats[Stat.SPEED]
            events.append(('opp', idx, target_idx, move, priority, speed))
            
        events.sort(key=lambda x: (x[4], x[5]), reverse=True)
        
        # 3. Execute attacks
        for team, idx, target_idx, move, priority, speed in events:
            if team == 'my':
                if my_hp[idx] <= 0: continue
                if move.category in (Category.PHYSICAL, Category.SPECIAL):
                    if target_idx < len(opp_active) and opp_hp[target_idx] > 0:
                        if opp_protect[target_idx]:
                            score -= 20.0 # Wasted attack
                        else:
                            dmg = _estimate_damage(my_active[idx], opp_active[target_idx], move)
                            actual_dmg = min(opp_hp[target_idx], dmg)
                            opp_hp[target_idx] -= actual_dmg
                            score += actual_dmg * 2.0
                            if opp_hp[target_idx] <= 0:
                                score += 800.0 # KO bonus
                elif move.toggle_tailwind:
                    score += 150.0 # Setup bonus
            else:
                if opp_hp[idx] <= 0: continue
                if move.category in (Category.PHYSICAL, Category.SPECIAL):
                    if target_idx < len(my_active) and my_hp[target_idx] > 0:
                        if my_protect[target_idx]:
                            score += 50.0 # Successfully protected against an attack!
                        else:
                            dmg = _estimate_damage(opp_active[idx], my_active[target_idx], move)
                            actual_dmg = min(my_hp[target_idx], dmg)
                            my_hp[target_idx] -= actual_dmg
                            score -= actual_dmg * 2.0
                            if my_hp[target_idx] <= 0:
                                score -= 1000.0 # KO penalty
                                
        return score

    def decision(self, state: State, opp_view: Optional[TeamView] = None) -> list[BattleCommand]:
        my_active = [p for p in state.sides[0].team.active if p is not None]
        opp_active = [p for p in state.sides[1].team.active if p is not None]
        
        if not my_active:
            return []
            
        my_actions = self.get_possible_actions(my_active, len(opp_active))
        opp_actions = self.get_possible_actions(opp_active, len(my_active))
        
        best_action = my_actions[0]
        best_minimax_score = -float('inf')
        
        for my_act in my_actions:
            min_score_for_this_act = float('inf')
            
            for opp_act in opp_actions:
                score = self._fast_simulate(my_active, opp_active, my_act, opp_act)
                if score < min_score_for_this_act:
                    min_score_for_this_act = score
                    
            if min_score_for_this_act > best_minimax_score:
                best_minimax_score = min_score_for_this_act
                best_action = my_act
                
        return best_action
