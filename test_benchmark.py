import sys
sys.path.insert(0, 'my_submission')

from vgc2.agent.battle import GreedyBattlePolicy
from vgc2.agent.selection import RandomSelectionPolicy
from selection_policy import CoverageSelectionPolicy
from benchmark import benchmark

w, l, e = benchmark("Greedy", GreedyBattlePolicy(), RandomSelectionPolicy(), n_matches=50)
total = w + l
print(f"vs Greedy (using EnhancedBattlePolicy): {w}/{total} ({(w/total)*100:.1f}%)")

class MockComp:
    name = "Greedy_with_Coverage"
    battlepolicy = GreedyBattlePolicy()
    selectionpolicy = CoverageSelectionPolicy()

w, l, e = benchmark("Greedy", GreedyBattlePolicy(), RandomSelectionPolicy(), my_comp=MockComp(), n_matches=50)
total = w + l
print(f"vs Greedy (using GreedyBattlePolicy + CoverageSelectionPolicy): {w}/{total} ({(w/total)*100:.1f}%)")
try:
    import os
    jir_dir = os.path.join('edition', 'vgc2025', 'submissions', 'jirachi - DONGMIN KIM')
    sys.path.insert(0, jir_dir)
    from jirachi_core_policies import AlwaysSmartBeamSearchPolicy
    
    class GreedyComp:
        name = "Greedy_Coverage"
        battlepolicy = GreedyBattlePolicy()
        selectionpolicy = CoverageSelectionPolicy()

    # vs JJJ
    try:
        jjj_dir = os.path.join('edition', 'vgc2025', 'submissions', 'JJJ - JunSung - wfd gfd')
        sys.path.insert(0, jjj_dir)
        from JJJ import JJJ_BattlePolicy, JJJ_selectionPolicy
        benchmark("JJJ", JJJ_BattlePolicy(), JJJ_selectionPolicy(), my_comp=GreedyComp(), n_matches=50)
    except Exception as e: print(e)

    # vs Yamabuki
    try:
        ice_dir = os.path.join('edition', 'vgc2025', 'submissions', 'iceMonteSubmission')
        sys.path.insert(0, ice_dir)
        from iceMonteBattlePolicy import IceMonteBattlePolicy
        from iceMonteSelectionPolicy import IceMonteSelectionPolicy
        benchmark("Yamabuki", IceMonteBattlePolicy(), IceMonteSelectionPolicy(), my_comp=GreedyComp(), n_matches=50)
    except Exception as e: print(e)
    
    # vs Jirachi
    try:
        benchmark("Jirachi", AlwaysSmartBeamSearchPolicy(time_limit_ms=90), CoverageSelectionPolicy(), my_comp=GreedyComp(), n_matches=50)
    except Exception as e: print(e)

except Exception as e:
    print(f"Failed: {e}")
