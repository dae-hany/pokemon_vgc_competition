"""
Matrix-based Selection Policy for General AI (VGC 2026).

Selects 4 out of 6 pokemon by mathematically optimizing offensive coverage 
and defensive bulk against the opponent's 6 pokemon roster.
"""
from typing import List
import numpy as np

from vgc2.agent import SelectionPolicy, SelectionCommand
from vgc2.battle_engine.modifiers import Stat, Category
from vgc2.battle_engine.pokemon import Pokemon
from vgc2.battle_engine.team import Team

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

def _estimate_damage_ratio(attacker: Pokemon, defender: Pokemon) -> float:
    best = 0.0
    for move in attacker.moves:
        if move.category not in (Category.PHYSICAL, Category.SPECIAL):
            continue
            
        base_power = move.base_power + max(0, move.priority) * 10
        if base_power <= 0:
            continue
            
        atk_stat = attacker.stats[Stat.ATTACK] if move.category == Category.PHYSICAL else attacker.stats[Stat.SPECIAL_ATTACK]
        def_stat = defender.stats[Stat.DEFENSE] if move.category == Category.PHYSICAL else defender.stats[Stat.SPECIAL_DEFENSE]
        
        stab = 1.5 if move.pkm_type in attacker.species.types else 1.0
        eff = 1.0
        for dt in defender.species.types:
            eff *= TYPE_CHART[move.pkm_type, dt]
            
        dmg = int((2 * 50 / 5) + 2)
        dmg = int(dmg * base_power)
        dmg = int(dmg * atk_stat / def_stat)
        dmg = int(dmg / 50) + 2
        final = int(dmg * stab * eff)
        
        ratio = final / max(defender.stats[Stat.MAX_HP], 1)
        best = max(best, ratio)
    return best

def _score_attacker(attacker: Pokemon, enemy_team: List[Pokemon]) -> float:
    total_damage = sum(_estimate_damage_ratio(attacker, e) for e in enemy_team)
    
    hp_ratio = attacker.stats[Stat.MAX_HP] / 402
    def_ratio = attacker.stats[Stat.DEFENSE] / 257
    spd_ratio = attacker.stats[Stat.SPECIAL_DEFENSE] / 257
    bulk = hp_ratio * def_ratio * spd_ratio * 0.42
    
    return 1.07 * total_damage + bulk

class CoverageSelectionPolicy(SelectionPolicy):
    def decision(self, teams: tuple[Team, Team], max_size: int) -> SelectionCommand:
        my_team = teams[0].members
        enemy_team = teams[1].members
        
        m = len(my_team)
        k = len(enemy_team)
        
        if max_size >= m:
            return list(range(m))
            
        damage_matrix = np.zeros((m, k), dtype=float)
        for i, atk in enumerate(my_team):
            for j, dfn in enumerate(enemy_team):
                damage_matrix[i, j] = _estimate_damage_ratio(atk, dfn)
                
        score_vec = np.array([_score_attacker(p, enemy_team) for p in my_team], dtype=float)
        
        selected = []
        first_idx = int(np.argmax(score_vec))
        selected.append(first_idx)
        coverage = damage_matrix[first_idx].copy()
        candidates = set(range(m)) - {first_idx}
        
        for _ in range(1, min(max_size, m)):
            old_range = coverage.max() - coverage.min()
            best_i, best_val = None, -np.inf
            
            for i in candidates:
                new_cov = coverage + damage_matrix[i]
                new_range = new_cov.max() - new_cov.min()
                delta_range = old_range - new_range
                
                # Balances damage spread + high overall score
                val = 1.25 * delta_range + 0.74 * score_vec[i]
                if val > best_val:
                    best_val, best_i = val, i
                    
            selected.append(best_i)
            coverage += damage_matrix[best_i]
            candidates.remove(best_i)
            
        return selected
