import sys
import os
import io

# Setup paths
sys.path.insert(0, os.path.abspath('my_submission'))
sys.path.insert(0, os.path.abspath('minseo_lee'))

# pyrefly: ignore [missing-import]
from competitor import DaehoCompetitor
# pyrefly: ignore [missing-import]
from luciner_competitor import MyCompetitor

from vgc2.competition.ecosystem import Championship, label_roster
from vgc2.util.generator import gen_move_set, gen_pkm_roster
from vgc2.balance.meta import BasicMeta
from vgc2.competition import CompetitorManager

def run_single_session(my_comp, other_comp):
    move_set = gen_move_set(100)
    roster = gen_pkm_roster(50, move_set)
    label_roster(move_set, roster)
    meta = BasicMeta(move_set, roster)
    
    # 1 epoch, 2 active competitors, 3 battles per pair
    championship = Championship(roster, meta, epochs=1, n_active=2, n_battles=3)
    championship.register(CompetitorManager(my_comp))
    championship.register(CompetitorManager(other_comp))
    
    # Suppress logs
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        championship.run()
    finally:
        sys.stdout = old_stdout
    
    ranking = championship.ranking()
    return 1 if ranking[0].competitor.name == my_comp.name else 0

def benchmark_champ(my_comp, opp_comp, n=20):
    print(f"Benchmarking Championship Track: {my_comp.name} vs {opp_comp.name} ({n} rosters)")
    wins = 0
    for i in range(n):
        try:
            res = run_single_session(my_comp, opp_comp)
            wins += res
        except Exception as e:
            print(f"  Error in trial {i+1}: {e}")
        if (i+1) % 5 == 0:
            print(f"  {i+1}/{n} rosters done...")
            
    print(f"Results: {wins} Wins, {n-wins} Losses")
    print(f"Win Rate: {(wins/n)*100:.1f}%")

if __name__ == '__main__':
    daeho = DaehoCompetitor("DaehoAI")
    minseo = MyCompetitor("MinseoLee")
    benchmark_champ(daeho, minseo, n=100)

