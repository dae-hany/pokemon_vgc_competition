import sys
import os
import io
import time
import csv
import importlib.util
from datetime import datetime
from typing import Optional

# Fix Unicode output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, 'my_submission')

from vgc2.agent.battle import RandomBattlePolicy, GreedyBattlePolicy
from vgc2.agent.selection import RandomSelectionPolicy
from vgc2.battle_engine import BattleEngine, State, BattleRuleParam
from vgc2.battle_engine.game_state import get_battle_teams
from vgc2.battle_engine.view import TeamView, StateView
from vgc2.competition.match import label_teams, run_battle
from vgc2.util.generator import gen_team
from competitor import DaehoCompetitor

# --- 1. Utility Loader ---

class SimpleCompetitor:
    def __init__(self, name, battle_policy):
        self._name, self._bp = name, battle_policy
    @property
    def name(self): return self._name
    @property
    def battlepolicy(self): return self._bp
    @property
    def selectionpolicy(self): return RandomSelectionPolicy()

def load_competitor_policy(name, folder, comp_file, comp_cls, custom_policies=None):
    base_path = os.path.join('edition', 'vgc2025', 'submissions')
    path = os.path.abspath(os.path.join(base_path, folder))
    if not os.path.exists(path): return None
    
    # Unique module key to prevent collision
    module_key = f"battle_comp_{name.replace(' ', '_').lower()}"
    
    try:
        if path not in sys.path: sys.path.insert(0, path)
        
        if custom_policies:
            old_cwd = os.getcwd()
            os.chdir(path)
            try:
                b_mod = importlib.import_module(custom_policies['b_mod'])
                bp = getattr(b_mod, custom_policies['b_cls'])()
                return SimpleCompetitor(name, bp)
            finally: 
                os.chdir(old_cwd)
                if path in sys.path: sys.path.remove(path)

        file_path = os.path.join(path, comp_file + '.py')
        spec = importlib.util.spec_from_file_location(module_key, file_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_key] = mod
        
        old_cwd = os.getcwd()
        os.chdir(path)
        try:
            spec.loader.exec_module(mod)
            comp = getattr(mod, comp_cls)()
            return comp
        finally: 
            os.chdir(old_cwd)
            if path in sys.path: sys.path.remove(path)
    except Exception as e:
        print(f"  [WARN] Failed to load {name}: {e}")
        if path in sys.path: sys.path.remove(path)
        return None

def save_battle_results_to_csv(results):
    filename = "battle_results.csv"
    file_exists = os.path.isfile(filename)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Opponent", "Wins", "Losses", "Errors", "WinRate"])
            for name, w, l, e in results:
                total = w + l
                rate = (w / total) * 100 if total > 0 else 0
                writer.writerow([timestamp, name, w, l, e, f"{rate:.1f}%"])
        print(f"\n[INFO] Results saved to {filename}")
    except Exception as e:
        print(f"\n[ERROR] Could not save results to CSV: {e}")

# --- 2. Benchmark Engine ---

def run_single_match(my_battle, opp_battle, params):
    team = (gen_team(4, 4), gen_team(4, 4))
    label_teams(team)
    team_view = (TeamView(team[0]), TeamView(team[1]))
    state = State(get_battle_teams(team, 2))
    state_view = (StateView(state, 0, team_view), StateView(state, 1, team_view))
    engine = BattleEngine(state, params)
    
    # Suppress internal engine logs
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        result = run_battle(engine, (my_battle, opp_battle), team_view, state_view)
    finally:
        sys.stdout = old_stdout
    return result

def benchmark_battle(opponent_name, opp_policy, my_policy, n_matches=100):
    params = BattleRuleParam()
    my_policy.set_params(params)
    opp_policy.set_params(params)
    
    wins, losses, errors = 0, 0, 0
    print(f"\n>>> Battle Track Match: Daeho_AI vs {opponent_name} ({n_matches} matches)")
    
    for i in range(n_matches):
        try:
            result = run_single_match(my_policy, opp_policy, params)
            if result == 0: wins += 1
            else: losses += 1
        except Exception as e:
            errors += 1
            # print(f"  [ERR] Match {i+1}: {e}") # Optional: suppress error noise
        
        # Dynamic progress logging (every 5 matches)
        if (i + 1) % 5 == 0:
            total = wins + losses
            rate = (wins / total) * 100 if total > 0 else 0
            print(f"  Progress: {i+1:>3}/{n_matches} | Wins: {wins:>3} | WR: {rate:>5.1f}% | Errors: {errors}")
            
    return wins, losses, errors

if __name__ == '__main__':
    my_comp = DaehoCompetitor("Daeho_AI")
    my_battle = my_comp.battlepolicy
    
    targets = [
        ("Random", None, None, None, "RANDOM"),
        ("Greedy", None, None, None, "GREEDY"),
        ("JJJ", "JJJ - JunSung - wfd gfd", None, None, {'b_mod': 'JJJ', 'b_cls': 'JJJ_BattlePolicy'}),
        ("Yamabuki", "iceMonteSubmission", None, None, {'b_mod': 'iceMonteBattlePolicy', 'b_cls': 'IceMonteBattlePolicy'}),
        ("Jirachi", "jirachi - DONGMIN KIM", None, None, {'b_mod': 'jirachi_core_policies', 'b_cls': 'AlwaysSmartBeamSearchPolicy'}),
        ('Botzilla', 'BotzillaSubmission', 'botzillaCompetitor', 'BotzillaCompetitor', None),
        ('Laze', 'LazeComp', 'LazeCompetitor', 'LazeCompetitor', None),
        ('Peach', 'PeachSubmission', 'PeachCompetitor', 'PeachCompetitor', None),
        ('StocKarpador', 'StocKarpadorSubmission', 'StocKarpadorCompetitor', 'StocKarpadorCompetitor', None),
        ('EvoTrainer', 'evoTrainer', 'EvoCompetitor', 'EvoCompetitor', None),
        ('Minimon', 'minimon_02 - Leon Brunke', 'minimon', 'minimon', None),
        ('Caaaden', 'caaaden_competitor', 'caaaden_competitor', 'CaaadenCompetitor', None),
    ]

    print("Loading Battle Policies...")
    competitors = []
    for name, folder, c_file, c_cls, extra in targets:
        if name == "Random": competitors.append(SimpleCompetitor("Random", RandomBattlePolicy()))
        elif name == "Greedy": competitors.append(SimpleCompetitor("Greedy", GreedyBattlePolicy()))
        else:
            c = load_competitor_policy(name, folder, c_file, c_cls, extra if isinstance(extra, dict) else None)
            if c: competitors.append(c)

    results = {}
    start_time = time.time()
    for other in competitors:
        w, l, e = benchmark_battle(other.name, other.battlepolicy, my_battle, n_matches=100)
        results[other.name] = (w, l, e)
        # Partial save
        save_battle_results_to_csv([(other.name, w, l, e)])

    total_time = time.time() - start_time
    print("\n\n" + "="*75)
    print(f" 🏆 2026 VGC AI BATTLE TRACK BENCHMARK SUMMARY : Daeho_AI 🏆 ")
    print(f" Time Elapsed: {total_time/60:.1f} minutes")
    print("="*75)
    print(f" {'Opponent':<18} | {'Win Rate':<12} | {'Wins/Total':<15} | {'Errors':<8}")
    print("-" * 75)
    for name, (w, l, e) in results.items():
        total = w + l
        rate = (w / total) * 100 if total > 0 else 0
        print(f" {name:<18} | {rate:>10.1f}% | {w:>6}/{total:<7} | {e:<8}")
    print("="*75 + "\n")
    print(f"Full results appended to battle_results.csv")
