"""
friends_benchmark.py — DaehoV2 vs 친구들 battle track 1대1 승률 측정.

friends/ 폴더의 하위 디렉터리를 자동 스캔한다.
각 친구 폴더 안에 *Competitor.py 파일이 있어야 한다.
"""
import sys
import os
import io
import time
import csv
import logging
import contextlib
import importlib.util
import inspect
from datetime import datetime

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

logging.disable(logging.INFO)

repo_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(repo_root, 'my_submission_battleV2'))

from vgc2.agent.battle import GreedyBattlePolicy
from vgc2.agent.selection import RandomSelectionPolicy
from vgc2.battle_engine import BattleEngine, State, BattleRuleParam
from vgc2.battle_engine.game_state import get_battle_teams
from vgc2.battle_engine.view import TeamView, StateView
from vgc2.battle_engine.security import sanitized_selection_decision
from vgc2.competition.match import label_teams, run_battle, subteam
from vgc2.util.generator import gen_team
from competitor import DaehoV2Competitor

N_MATCHES = 200   # 친구당 대전 수 (짝수 권장 — 양방향 symmetric)


# ──────────────────────────────────────────────
#  Safety wrappers
# ──────────────────────────────────────────────

@contextlib.contextmanager
def _quiet_output():
    with open(os.devnull, 'w', encoding='utf-8') as devnull:
        with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
            yield


class SafeBattlePolicy:
    def __init__(self, inner):
        self._inner = inner
        self._fallback = GreedyBattlePolicy()
    def __getattr__(self, name): return getattr(self._inner, name)
    def decision(self, state, opp_view=None):
        try:
            with _quiet_output():
                return self._inner.decision(state, opp_view)
        except Exception:
            return self._fallback.decision(state, opp_view)


class SafeSelectionPolicy:
    def __init__(self, inner):
        self._inner = inner
    def __getattr__(self, name): return getattr(self._inner, name)
    def decision(self, teams, max_size):
        try:
            with _quiet_output():
                result = self._inner.decision(teams, max_size)
            n = len(teams[0].members)
            valid = [i for i in result if 0 <= i < n]
            if len(valid) >= min(max_size, n):
                return valid[:max_size]
        except Exception:
            pass
        return list(range(min(max_size, len(teams[0].members))))


# ──────────────────────────────────────────────
#  Auto-discovery
# ──────────────────────────────────────────────

def _find_competitor_class(mod):
    """모듈에서 Competitor를 상속하는 클래스를 찾아 반환."""
    from vgc2.competition import Competitor
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if issubclass(obj, Competitor) and obj is not Competitor:
            return obj
    return None


def load_friend(folder_path: str, friend_name: str):
    """
    friends/{friend_name}/ 폴더에서 *Competitor.py를 찾아 경쟁자를 로드.
    battlepolicy / selectionpolicy에 Safety wrapper를 씌워 반환.
    """
    competitor_files = [
        f for f in os.listdir(folder_path)
        if f.endswith('Competitor.py') and not f.startswith('__')
    ]
    if not competitor_files:
        raise FileNotFoundError(f"*Competitor.py not found in {folder_path}")

    comp_file = competitor_files[0]
    module_key = f"friend_{friend_name.lower()}"

    old_cwd = os.getcwd()
    if folder_path not in sys.path:
        sys.path.insert(0, folder_path)
    os.chdir(folder_path)
    try:
        spec = importlib.util.spec_from_file_location(
            module_key, os.path.join(folder_path, comp_file)
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_key] = mod
        spec.loader.exec_module(mod)

        cls = _find_competitor_class(mod)
        if cls is None:
            raise ImportError(f"Competitor subclass not found in {comp_file}")

        comp = cls()
        bp = SafeBattlePolicy(comp.battlepolicy) if comp.battlepolicy else GreedyBattlePolicy()
        sp_raw = getattr(comp, 'selectionpolicy', None)
        sp = SafeSelectionPolicy(sp_raw) if sp_raw else RandomSelectionPolicy()
        return comp.name, bp, sp
    finally:
        os.chdir(old_cwd)
        if folder_path in sys.path:
            sys.path.remove(folder_path)


def discover_friends(friends_root: str) -> list[tuple[str, str]]:
    """friends/ 하위 폴더를 스캔해 (friend_name, folder_path) 리스트를 반환."""
    if not os.path.isdir(friends_root):
        return []
    entries = []
    for name in sorted(os.listdir(friends_root)):
        path = os.path.join(friends_root, name)
        if os.path.isdir(path) and not name.startswith('_'):
            entries.append((name, path))
    return entries


# ──────────────────────────────────────────────
#  Battle runner
# ──────────────────────────────────────────────

def _run_match(side0_bp, side0_sp, side1_bp, side1_sp, params):
    """한 번의 매치 실행. side 0이 이기면 0, side 1이 이기면 1 반환."""
    base_team = (gen_team(6, 4), gen_team(6, 4))
    label_teams(base_team)
    base_view = (TeamView(base_team[0]), TeamView(base_team[1]))

    idx0 = sanitized_selection_decision(side0_sp, (base_team[0], base_view[1]), 6)
    idx1 = sanitized_selection_decision(side1_sp, (base_team[1], base_view[0]), 6)

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
        return run_battle(engine, (side0_bp, side1_bp), base_view, state_view)
    finally:
        sys.stdout = old_stdout


def benchmark_vs_friend(friend_name, friend_bp, friend_sp,
                         my_bp, my_sp, n_matches=N_MATCHES):
    """
    n_matches 게임 실행 (n_matches//2 쌍 × 양방향).
    동일한 팀 생성은 _run_match 내부에서 하므로 여기선 방향만 교환한다.
    """
    params = BattleRuleParam()
    my_bp.set_params(params)
    if hasattr(friend_bp, '_inner'):
        friend_bp._inner.set_params(params)
    elif hasattr(friend_bp, 'set_params'):
        friend_bp.set_params(params)

    wins = losses = errors = 0
    n_pairs = n_matches // 2

    print(f"\n>>> DaehoV2 vs {friend_name}  ({n_matches} games = {n_pairs} pairs × 2 dir)")

    for i in range(n_pairs):
        # Direction 1: DaehoV2 = side 0
        try:
            result = _run_match(my_bp, my_sp, friend_bp, friend_sp, params)
            if result == 0: wins += 1
            else:           losses += 1
        except Exception:
            errors += 1

        # Direction 2: DaehoV2 = side 1
        try:
            result = _run_match(friend_bp, friend_sp, my_bp, my_sp, params)
            if result == 1: wins += 1
            else:           losses += 1
        except Exception:
            errors += 1

        if (i + 1) % (max(1, n_pairs // 4)) == 0:
            done = (i + 1) * 2
            total = wins + losses
            wr = wins / total * 100 if total > 0 else 0
            print(f"  [{done:>4}/{n_matches}]  Win: {wins:>4}  WR: {wr:5.1f}%  Err: {errors}")

    return wins, losses, errors


# ──────────────────────────────────────────────
#  CSV 저장
# ──────────────────────────────────────────────

def save_results(results: list[tuple]):
    filename = "friends_benchmark_results.csv"
    file_exists = os.path.isfile(filename)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Friend", "Wins", "Losses", "Errors", "WinRate"])
            for name, w, l, e in results:
                total = w + l
                wr = f"{w / total * 100:.1f}%" if total > 0 else "N/A"
                writer.writerow([timestamp, name, w, l, e, wr])
        print(f"\n[INFO] Results saved to {filename}")
    except Exception as ex:
        print(f"\n[ERROR] Could not save results: {ex}")


# ──────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='DaehoV2 vs Friends — battle track benchmark')
    parser.add_argument('--n', type=int, default=N_MATCHES,
                        help=f'games per friend (default: {N_MATCHES}, must be even)')
    parser.add_argument('--friend', type=str, default=None,
                        help='specific friend folder name to test (default: all)')
    args = parser.parse_args()
    n_matches = args.n if args.n % 2 == 0 else args.n + 1

    friends_root = os.path.join(repo_root, 'friends')
    discovered = discover_friends(friends_root)

    if args.friend:
        discovered = [(n, p) for n, p in discovered if n == args.friend]
        if not discovered:
            print(f"[ERROR] '{args.friend}' not found in friends/")
            sys.exit(1)

    print("=" * 60)
    print("  DaehoV2 — Friends Battle Track Benchmark")
    print(f"  Games per friend : {n_matches}  (양방향 symmetric)")
    print(f"  Friends folder   : {friends_root}")
    print("=" * 60)

    print("\nDiscovered friends:")
    for name, _ in discovered:
        print(f"  • {name}")
    if not discovered:
        print("  (없음 — friends/ 폴더에 하위 디렉터리를 추가하세요)")
        sys.exit(0)

    my_comp = DaehoV2Competitor("DaehoV2")
    my_bp = my_comp.battlepolicy
    my_sp = my_comp.selectionpolicy

    results = []
    start_time = time.time()

    for friend_name, folder_path in discovered:
        print(f"\nLoading {friend_name}...")
        try:
            display_name, friend_bp, friend_sp = load_friend(folder_path, friend_name)
            print(f"  Loaded: {display_name}")
        except Exception as ex:
            print(f"  [WARN] Failed to load {friend_name}: {ex}")
            continue

        w, l, e = benchmark_vs_friend(
            display_name, friend_bp, friend_sp,
            my_bp, my_sp,
            n_matches=n_matches,
        )
        results.append((display_name, w, l, e))
        save_results([(display_name, w, l, e)])

    elapsed = time.time() - start_time

    print(f"\n\n{'='*60}")
    print(f"  FINAL RESULTS  (elapsed: {elapsed/60:.1f} min)")
    print(f"{'='*60}")
    print(f"  {'Friend':<20} {'WinRate':>8}  {'W/Total':>12}  Errors")
    print(f"  {'-'*50}")
    for name, w, l, e in results:
        total = w + l
        wr = f"{w / total * 100:.1f}%" if total > 0 else "N/A"
        print(f"  {name:<20} {wr:>8}  {f'{w}/{total}':>12}  {e}")
    print(f"{'='*60}\n")
