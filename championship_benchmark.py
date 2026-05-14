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

from vgc2.agent.battle import GreedyBattlePolicy, RandomBattlePolicy
from vgc2.agent.selection import RandomSelectionPolicy
from vgc2.agent.teambuild import RandomTeamBuildPolicy
from vgc2.balance.meta import BasicMeta
from vgc2.competition import CompetitorManager
from vgc2.competition.ecosystem import Championship, label_roster
from vgc2.util.generator import gen_move_set, gen_pkm_roster
# pyrefly: ignore [missing-import]
from competitor import DaehoCompetitor

# --- 1. Utility Classes ---

class SafeSelectionPolicy:
    def __init__(self, inner_policy):
        self._inner = inner_policy
    def __getattr__(self, name): return getattr(self._inner, name)
    def decision(self, teams, max_size):
        try:
            result = self._inner.decision(teams, max_size)
            n_members = len(teams[0].members)
            valid = [i for i in result if 0 <= i < n_members]
            if len(valid) >= min(max_size, n_members): return valid[:max_size]
        except Exception: pass
        return list(range(min(max_size, len(teams[0].members))))

class SimpleCompetitor:
    def __init__(self, name, battle_policy, selection_policy, teambuild_policy):
        self._name, self._bp, self._sp, self._tp = name, battle_policy, selection_policy, teambuild_policy
    @property
    def name(self): return self._name
    @property
    def battlepolicy(self): return self._bp
    @property
    def selectionpolicy(self): return self._sp
    @property
    def teambuildpolicy(self): return self._tp

# --- 2. Loader Logic ---

def load_competitor(name, folder, comp_file, comp_cls, custom_policies=None):
    base_path = os.path.join('edition', 'vgc2025', 'submissions')
    path = os.path.abspath(os.path.join(base_path, folder))
    if not os.path.exists(path): return None
    
    # Unique module key to prevent collision between submissions
    module_key = f"competitor_{name.replace(' ', '_').lower()}"
    
    try:
        if path not in sys.path: sys.path.insert(0, path)
        if custom_policies:
            old_cwd = os.getcwd()
            os.chdir(path)
            try:
                # Use unique names for internal modules if possible, but at least clear them
                b_mod = importlib.import_module(custom_policies['b_mod'])
                s_mod = importlib.import_module(custom_policies['s_mod'])
                t_mod_name = custom_policies.get('t_mod')
                t_mod = importlib.import_module(t_mod_name) if t_mod_name else None
                
                bp = getattr(b_mod, custom_policies['b_cls'])()
                sp = SafeSelectionPolicy(getattr(s_mod, custom_policies['s_cls'])())
                tp = getattr(t_mod, custom_policies['t_cls'])() if t_mod else RandomTeamBuildPolicy()
                
                return SimpleCompetitor(name, bp, sp, tp)
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
        finally: 
            os.chdir(old_cwd)
            if path in sys.path: sys.path.remove(path)
        return comp
    except Exception as e:
        print(f"  [WARN] Failed to load {name}: {e}")
        return None

def save_results_to_csv(results):
    filename = "championship_benchmark_results_weather_aware.csv"
    file_exists = os.path.isfile(filename)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Opponent", "Wins", "Total", "WinRate"])
            for name, w, total in results:
                rate = (w / total) * 100 if total > 0 else 0
                writer.writerow([timestamp, name, w, total, f"{rate:.1f}%"])
        print(f"\n[INFO] Results saved to {filename}")
    except Exception as e:
        print(f"\n[ERROR] Could not save results to CSV: {e}")

# --- 3. Benchmark Engine (Diversity Mode) ---

def run_single_session(my_comp, other_comp):
    """Runs a 1-epoch championship on a FRESH roster."""
    move_set = gen_move_set(100)
    roster = gen_pkm_roster(50, move_set)
    label_roster(move_set, roster)
    meta = BasicMeta(move_set, roster)
    
    # 1 epoch on 1 unique roster
    championship = Championship(roster, meta, epochs=1, n_active=2, n_battles=3)
    championship.register(CompetitorManager(my_comp))
    championship.register(CompetitorManager(other_comp))
    
    # Suppress internal engine logs
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        championship.run()
    finally:
        sys.stdout = old_stdout
    
    ranking = championship.ranking()
    return 1 if ranking[0].competitor.name == my_comp.name else 0

if __name__ == '__main__':
    print("Initializing DaehoAI...")
    my_comp = DaehoCompetitor("Daeho_AI")
    
    targets = [
        ("Greedy", "Greedy", None, None, "FIXED"), 
        ("JJJ", "JJJ - JunSung - wfd gfd", None, None, {
            'b_mod': 'JJJ', 'b_cls': 'JJJ_BattlePolicy',
            's_mod': 'JJJ', 's_cls': 'JJJ_selectionPolicy',
            't_mod': 'JJJTeamPolicy', 't_cls': 'JJJ_TeamBuildPolicy'
        }),
        ("Yamabuki", "iceMonteSubmission", None, None, {
            'b_mod': 'iceMonteBattlePolicy', 'b_cls': 'IceMonteBattlePolicy',
            's_mod': 'iceMonteSelectionPolicy', 's_cls': 'IceMonteSelectionPolicy'
        }),
        ("Jirachi", "jirachi - DONGMIN KIM", None, None, {
            'b_mod': 'jirachi_core_policies', 'b_cls': 'AlwaysSmartBeamSearchPolicy',
            's_mod': 'jirachi_core_policies', 's_cls': 'MaxFirepowerSelectionPolicy'
        }),
        ('Botzilla', 'BotzillaSubmission', 'botzillaCompetitor', 'BotzillaCompetitor', None),
        ('Laze', 'LazeComp', 'LazeCompetitor', 'LazeCompetitor', None),
        ('Peach', 'PeachSubmission', 'PeachCompetitor', 'PeachCompetitor', None),
        ('StocKarpador', 'StocKarpadorSubmission', 'StocKarpadorCompetitor', 'StocKarpadorCompetitor', None),
        ('EvoTrainer', 'evoTrainer', 'EvoCompetitor', 'EvoCompetitor', None),
        ('Minimon', 'minimon_02 - Leon Brunke', 'minimon', 'minimon', None),
        ('Caaaden', 'caaaden_competitor', 'caaaden_competitor', 'CaaadenCompetitor', None),
    ]
    
    print("\nLoading Competitors...")
    others = []
    for name, folder, c_file, c_cls, extra in targets:
        if name == "Greedy": others.append(SimpleCompetitor("Greedy", GreedyBattlePolicy(), RandomSelectionPolicy(), RandomTeamBuildPolicy()))
        else:
            c = load_competitor(name, folder, c_file, c_cls, extra if isinstance(extra, dict) else None)
            if c: others.append(c)

    n_trials = 100 # Number of independent rosters per opponent
    results = []
    print(f"\n{'='*75}\n  STARTING ROSTER-DIVERSITY BENCHMARK ({n_trials} rosters per opponent)\n{'='*75}")
    
    start_time = time.time()
    for other in others:
        print(f"\n>>> Opponent: {other.name}")
        wins = 0
        for i in range(n_trials):
            try:
                result = run_single_session(my_comp, other)
                wins += result
                
                # Dynamic progress logging
                if (i + 1) % 5 == 0:
                    current_rate = (wins / (i + 1)) * 100
                    print(f"  Progress: {i+1:>3}/{n_trials} | Wins: {wins:>3} | Current WR: {current_rate:>5.1f}%")
            except Exception as e:
                print(f"  [ERROR] Trial {i+1}: {e}")
        
        results.append((other.name, wins, n_trials))
        # Partial save after each opponent
        save_results_to_csv([(other.name, wins, n_trials)])

    total_time = time.time() - start_time
    print("\n\n" + "="*70)
    print(f" 🏆 2026 VGC AI ROSTER-DIVERSITY SUMMARY : Daeho_AI 🏆 ")
    print(f" Time Elapsed: {total_time/60:.1f} minutes")
    print("="*70)
    print(f" {'Opponent':<18} | {'Win Rate':<12} | {'Wins / Rosters'}")
    print("-" * 70)
    for name, w, total in results:
        rate = (w / total) * 100 if total > 0 else 0
        print(f" {name:<18} | {rate:>10.1f}% | {w:>3} / {total:<3}")
    print("="*70 + "\n")
    print(f"Full results appended to benchmark_results.csv")
