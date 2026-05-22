import sys
import os
import io
import time
import csv
import importlib.util
from datetime import datetime

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Parse --submission early so sys.path is set before module-level imports
import argparse as _argparse
_pre_parser = _argparse.ArgumentParser(add_help=False)
_pre_parser.add_argument('--submission', choices=['battle', 'battleV2'], default='battle')
_pre_args, _ = _pre_parser.parse_known_args()
_submission_folder = 'my_submission_' + _pre_args.submission

repo_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(repo_root, _submission_folder))

from vgc2.agent.battle import RandomBattlePolicy, GreedyBattlePolicy
from vgc2.agent.selection import RandomSelectionPolicy
from vgc2.battle_engine import BattleEngine, State, BattleRuleParam
from vgc2.battle_engine.game_state import get_battle_teams
from vgc2.battle_engine.view import TeamView, StateView
from vgc2.battle_engine.security import sanitized_selection_decision
from vgc2.competition.match import label_teams, run_battle, subteam
from vgc2.util.generator import gen_team
if _pre_args.submission == 'battleV2':
    from competitor import DaehoV2Competitor as DaehoCompetitor
else:
    from competitor import DaehoCompetitor


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
    if not os.path.exists(path):
        return None
    module_key = "battle_comp_" + name.replace(' ', '_').lower()
    try:
        if path not in sys.path:
            sys.path.insert(0, path)
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
        print("  [WARN] Failed to load " + name + ": " + str(e))
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
                writer.writerow([timestamp, name, w, l, e, str(round(rate, 1)) + "%"])
        print("\n[INFO] Results saved to " + filename)
    except Exception as e:
        print("\n[ERROR] Could not save results: " + str(e))


def run_match_once(side0_comp, side1_comp, base_team, params):
    """Match._run_once 완전 재현. Selection 단계를 거쳐 배틀 실행.
    Returns 0 if side 0 wins, 1 if side 1 wins."""
    base_view = (TeamView(base_team[0]), TeamView(base_team[1]))

    idx0 = sanitized_selection_decision(
        side0_comp.selectionpolicy, (base_team[0], base_view[1]), 6
    )
    idx1 = sanitized_selection_decision(
        side1_comp.selectionpolicy, (base_team[1], base_view[0]), 6
    )

    sub0 = subteam(base_team[0], base_view[0], idx0)
    sub1 = subteam(base_team[1], base_view[1], idx1)
    team = (sub0[0], sub1[0])
    view = (sub0[1], sub1[1])

    state = State(get_battle_teams(team, 2))
    state_view = (StateView(state, 0, view), StateView(state, 1, view))
    engine = BattleEngine(state, params)

    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        result = run_battle(
            engine,
            (side0_comp.battlepolicy, side1_comp.battlepolicy),
            base_view,
            state_view
        )
    finally:
        sys.stdout = old_stdout
    return result


def benchmark_battle(opponent_name, opp_comp, my_comp, n_matches=100):
    """n_matches 게임 실행 (n_matches//2 팀 쌍 x 2 방향).
    동일 팀으로 양측을 교환해 공정성 보장 (Match._run_random 방식)."""
    params = BattleRuleParam()
    my_comp.battlepolicy.set_params(params)
    opp_comp.battlepolicy.set_params(params)

    wins, losses, errors = 0, 0, 0
    n_pairs = n_matches // 2
    print("\n>>> Battle Track: Daeho_AI vs " + opponent_name +
          " (" + str(n_matches) + " games = " + str(n_pairs) + " pairs x 2 directions)")

    for i in range(n_pairs):
        base_team = (gen_team(6, 4), gen_team(6, 4))
        label_teams(base_team)

        # Direction 1: 내가 side 0
        try:
            result = run_match_once(my_comp, opp_comp, base_team, params)
            if result == 0:
                wins += 1
            else:
                losses += 1
        except Exception:
            errors += 1

        # Direction 2: 팀 스왑. 내가 side 1 (result==1 이면 내가 이김)
        try:
            swapped = (base_team[1], base_team[0])
            result = run_match_once(opp_comp, my_comp, swapped, params)
            if result == 1:
                wins += 1
            else:
                losses += 1
        except Exception:
            errors += 1

        if (i + 1) % 5 == 0:
            total = wins + losses
            rate = (wins / total) * 100 if total > 0 else 0
            print("  Progress: " + str((i+1)*2).rjust(3) + "/" + str(n_matches) +
                  " | Wins: " + str(wins).rjust(3) +
                  " | WR: " + str(round(rate, 1)).rjust(5) + "%" +
                  " | Errors: " + str(errors))

    return wins, losses, errors


FAST_TARGETS = {"Random", "Greedy", "JJJ", "Yamabuki"}

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--fast', action='store_true', help='Run only Random/Greedy/JJJ/Yamabuki')
    parser.add_argument('--submission', choices=['battle', 'battleV2'], default='battle',
                        help='Which submission folder to use (default: battle)')
    args = parser.parse_args()
    print(f"[INFO] Using submission: my_submission_{args.submission}")

    my_comp = DaehoCompetitor("Daeho_AI")

    targets = [
        ("Random",       None,                        None,                     None,                     "RANDOM"),
        ("Greedy",       None,                        None,                     None,                     "GREEDY"),
        ("JJJ",          "JJJ - JunSung - wfd gfd",  None,                     None,
            {'b_mod': 'JJJ', 'b_cls': 'JJJ_BattlePolicy'}),
        ("Yamabuki",     "iceMonteSubmission",        None,                     None,
            {'b_mod': 'iceMonteBattlePolicy', 'b_cls': 'IceMonteBattlePolicy'}),
        ("Jirachi",      "jirachi - DONGMIN KIM",    None,                     None,
            {'b_mod': 'jirachi_core_policies', 'b_cls': 'AlwaysSmartBeamSearchPolicy'}),
        ("Botzilla",     "BotzillaSubmission",       "botzillaCompetitor",     "BotzillaCompetitor",     None),
        ("Laze",         "LazeComp",                 "LazeCompetitor",         "LazeCompetitor",         None),
        ("Peach",        "PeachSubmission",          "PeachCompetitor",        "PeachCompetitor",        None),
        ("StocKarpador", "StocKarpadorSubmission",   "StocKarpadorCompetitor", "StocKarpadorCompetitor", None),
        ("EvoTrainer",   "evoTrainer",               "EvoCompetitor",          "EvoCompetitor",          None),
        ("Minimon",      "minimon_02 - Leon Brunke", "minimon",                "minimon",                None),
        ("Caaaden",      "caaaden_competitor",       "caaaden_competitor",     "CaaadenCompetitor",      None),
    ]

    if args.fast:
        targets = [t for t in targets if t[0] in FAST_TARGETS]

    print("Loading Battle Policies...")
    competitors = []
    for name, folder, c_file, c_cls, extra in targets:
        if name == "Random":
            competitors.append(SimpleCompetitor("Random", RandomBattlePolicy()))
        elif name == "Greedy":
            competitors.append(SimpleCompetitor("Greedy", GreedyBattlePolicy()))
        else:
            c = load_competitor_policy(
                name, folder, c_file, c_cls,
                extra if isinstance(extra, dict) else None
            )
            if c:
                competitors.append(c)

    results = {}
    start_time = time.time()
    for other in competitors:
        w, l, e = benchmark_battle(other.name, other, my_comp, n_matches=100)
        results[other.name] = (w, l, e)
        save_battle_results_to_csv([(other.name, w, l, e)])

    total_time = time.time() - start_time
    sep = "=" * 75
    print("\n\n" + sep)
    print(" 2026 VGC AI BATTLE TRACK BENCHMARK SUMMARY : Daeho_AI")
    print(" Time Elapsed: " + str(round(total_time / 60, 1)) + " minutes")
    print(sep)
    print(" " + "Opponent".ljust(18) + " | " + "Win Rate".ljust(12) +
          " | " + "Wins/Total".ljust(15) + " | Errors")
    print("-" * 75)
    for name, (w, l, e) in results.items():
        total = w + l
        rate = (w / total) * 100 if total > 0 else 0
        print(" " + name.ljust(18) + " | " + (str(round(rate, 1)) + "%").rjust(11) +
              " | " + (str(w) + "/" + str(total)).ljust(15) + " | " + str(e))
    print(sep + "\n")
    print("Full results appended to battle_results.csv")
