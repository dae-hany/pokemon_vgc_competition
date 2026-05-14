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

# Import benchmark utilities from battle_benchmark
# Since I can't easily import from a script not in path, I'll redefine the core logic
from vgc2.battle_engine import BattleEngine, State, BattleRuleParam
from vgc2.battle_engine.game_state import get_battle_teams
from vgc2.battle_engine.view import TeamView, StateView
from vgc2.competition.match import label_teams, run_battle
from vgc2.util.generator import gen_team

def run_single_match(my_battle, opp_battle, params):
    team = (gen_team(4, 4), gen_team(4, 4))
    label_teams(team)
    team_view = (TeamView(team[0]), TeamView(team[1]))
    state = State(get_battle_teams(team, 2))
    state_view = (StateView(state, 0, team_view), StateView(state, 1, team_view))
    engine = BattleEngine(state, params)
    
    # Suppress logs
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        result = run_battle(engine, (my_battle, opp_battle), team_view, state_view)
    finally:
        sys.stdout = old_stdout
    return result

def benchmark(my_comp, opp_comp, n=20):
    params = BattleRuleParam()
    my_comp.battlepolicy.set_params(params)
    opp_comp.battlepolicy.set_params(params)
    
    wins, losses, errors = 0, 0, 0
    print(f"Benchmarking Battle Track: {my_comp.name} vs {opp_comp.name} ({n} matches)")
    for i in range(n):
        try:
            res = run_single_match(my_comp.battlepolicy, opp_comp.battlepolicy, params)
            if res == 0: wins += 1
            else: losses += 1
        except Exception as e:
            errors += 1
        if (i+1) % 5 == 0:
            print(f"  {i+1}/{n} matches done...")
            
    print(f"Results: {wins} Wins, {losses} Losses, {errors} Errors")
    print(f"Win Rate: {(wins/(wins+losses))*100:.1f}%" if wins+losses > 0 else "N/A")

if __name__ == '__main__':
    daeho = DaehoCompetitor("DaehoAI")
    minseo = MyCompetitor("MinseoLee")
    benchmark(daeho, minseo, n=100)

