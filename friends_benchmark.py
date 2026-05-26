"""
friends_benchmark.py — DaehoV2 vs 친구들 battle + championship track 승률 측정.

friends/ 폴더의 하위 디렉터리를 자동 스캔한다.
각 친구 폴더 안에 *Competitor.py 파일이 있어야 한다.

Battle track       : 랜덤 팀으로 selection + battle 성능 측정
Championship track : roster 기반 team build → selection → battle 전체 측정
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
from itertools import cycle

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

logging.disable(logging.INFO)

repo_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(repo_root, 'my_submission_battleV2'))

from vgc2.agent.battle import GreedyBattlePolicy
from vgc2.agent.selection import RandomSelectionPolicy
from vgc2.balance.meta import BasicMeta
from vgc2.battle_engine import BattleEngine, State, BattleRuleParam
from vgc2.battle_engine.game_state import get_battle_teams
from vgc2.battle_engine.view import TeamView, StateView
from vgc2.battle_engine.security import sanitized_selection_decision, sanitized_team_build_decision
from vgc2.competition.ecosystem import label_roster, build_team
from vgc2.competition.match import label_teams, run_battle, subteam
from vgc2.util.generator import gen_team, gen_move_set, gen_pkm_roster
from competitor import DaehoV2Competitor

# ──────────────────────────────────────────────
#  Config
# ──────────────────────────────────────────────
N_BATTLE_MATCHES = 200
N_CHAMP_MATCHES  = 200
BUILD_SIZE       = 6      # 팀빌딩: 50마리 중 6마리 선택
SELECT_SIZE      = 4      # 선발: 6마리 중 4마리 출전 (championship)
N_MOVES          = 100
ROSTER_SIZE      = 50
MAX_PKM_MOVES    = 4
N_ACTIVE         = 2
N_ROSTER_POOL    = 20     # 미리 생성해두는 로스터 풀 크기


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


class QuietTeamBuildPolicy:
    def __init__(self, inner):
        self._inner = inner
    def __getattr__(self, name): return getattr(self._inner, name)
    def decision(self, roster, meta, max_team_size, max_pkm_moves, n_active):
        try:
            with _quiet_output():
                return self._inner.decision(roster, meta, max_team_size, max_pkm_moves, n_active)
        except Exception:
            return []


# ──────────────────────────────────────────────
#  Auto-discovery & loading
# ──────────────────────────────────────────────

def _find_competitor_class(mod):
    from vgc2.competition import Competitor
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if issubclass(obj, Competitor) and obj is not Competitor:
            return obj
    return None


def load_friend(folder_path, friend_folder_name):
    """
    friends/{name}/ 폴더에서 *Competitor.py를 찾아 로드.
    Returns: (display_name, bp, sp, tbp)  — tbp는 없으면 None.
    """
    comp_files = [
        f for f in os.listdir(folder_path)
        if f.endswith('Competitor.py') and not f.startswith('__')
    ]
    if not comp_files:
        raise FileNotFoundError(f"*Competitor.py not found in {folder_path}")

    module_key = f"friend_{friend_folder_name.lower()}"
    old_cwd = os.getcwd()
    if folder_path not in sys.path:
        sys.path.insert(0, folder_path)
    os.chdir(folder_path)
    try:
        spec = importlib.util.spec_from_file_location(
            module_key, os.path.join(folder_path, comp_files[0])
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_key] = mod
        spec.loader.exec_module(mod)

        cls = _find_competitor_class(mod)
        if cls is None:
            raise ImportError(f"Competitor subclass not found in {comp_files[0]}")

        comp = cls()
        bp  = SafeBattlePolicy(comp.battlepolicy) if comp.battlepolicy else GreedyBattlePolicy()
        sp  = SafeSelectionPolicy(comp.selectionpolicy) if getattr(comp, 'selectionpolicy', None) else RandomSelectionPolicy()
        tbp_raw = getattr(comp, 'teambuildpolicy', None)
        tbp = QuietTeamBuildPolicy(tbp_raw) if tbp_raw else None
        return comp.name, bp, sp, tbp
    finally:
        os.chdir(old_cwd)
        if folder_path in sys.path:
            sys.path.remove(folder_path)


def discover_friends(friends_root):
    if not os.path.isdir(friends_root):
        return []
    return [
        (name, os.path.join(friends_root, name))
        for name in sorted(os.listdir(friends_root))
        if os.path.isdir(os.path.join(friends_root, name)) and not name.startswith('_')
    ]


# ──────────────────────────────────────────────
#  Core game runner
# ──────────────────────────────────────────────

def _run_game(team0, team1, bp0, sp0, bp1, sp1, params, select_size):
    """선발 + 배틀 1회 실행. side 0 승리 → 0, side 1 승리 → 1."""
    base_view = (TeamView(team0), TeamView(team1))
    idx0 = sanitized_selection_decision(sp0, (team0, base_view[1]), select_size)
    idx1 = sanitized_selection_decision(sp1, (team1, base_view[0]), select_size)
    sub0 = subteam(team0, base_view[0], idx0)
    sub1 = subteam(team1, base_view[1], idx1)
    team  = (sub0[0], sub1[0])
    view  = (sub0[1], sub1[1])
    state = State(get_battle_teams(team, N_ACTIVE))
    state_view = (StateView(state, 0, view), StateView(state, 1, view))
    engine = BattleEngine(state, params)
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        return run_battle(engine, (bp0, bp1), base_view, state_view)
    finally:
        sys.stdout = old_stdout


def _set_params_safe(bp, params):
    """SafeBattlePolicy / 일반 BattlePolicy 모두 set_params 호출."""
    try:
        bp.set_params(params)
    except Exception:
        pass


# ──────────────────────────────────────────────
#  Battle track
# ──────────────────────────────────────────────

def benchmark_battle(display_name, friend_bp, friend_sp, my_bp, my_sp, n_matches):
    """랜덤 팀 기반 battle track. 양방향 symmetric."""
    params = BattleRuleParam()
    _set_params_safe(my_bp, params)
    _set_params_safe(friend_bp, params)

    wins = losses = errors = 0
    n_pairs = n_matches // 2
    log_every = max(2, n_matches // 4)
    print(f"\n  [Battle]        DaehoV2 vs {display_name}  ({n_matches} games)")

    for i in range(n_pairs):
        team0 = gen_team(6, 4)
        team1 = gen_team(6, 4)
        label_teams((team0, team1))

        # Direction 1: DaehoV2 = side 0
        try:
            result = _run_game(team0, team1, my_bp, my_sp, friend_bp, friend_sp, params, 6)
            if result == 0: wins += 1
            else:           losses += 1
        except Exception:
            errors += 1

        # Direction 2: DaehoV2 = side 1
        try:
            result = _run_game(team1, team0, friend_bp, friend_sp, my_bp, my_sp, params, 6)
            if result == 1: wins += 1
            else:           losses += 1
        except Exception:
            errors += 1

        done = (i + 1) * 2
        if done % log_every == 0:
            total = wins + losses
            wr = wins / total * 100 if total > 0 else 0
            print(f"    [{done:>4}/{n_matches}] WR: {wr:5.1f}%  Err: {errors}")

    return wins, losses, errors


# ──────────────────────────────────────────────
#  Championship track
# ──────────────────────────────────────────────

def gen_roster_pool(n):
    """n개의 (roster, meta) 쌍을 미리 생성. championship 매치에서 순환 사용."""
    print(f"  Generating {n} rosters for championship...", end='', flush=True)
    pool = []
    for _ in range(n):
        move_set = gen_move_set(N_MOVES)
        roster   = gen_pkm_roster(ROSTER_SIZE, move_set)
        label_roster(move_set, roster)
        pool.append((roster, BasicMeta(move_set, roster)))
    print(" done.")
    return pool


def benchmark_championship(display_name, friend_bp, friend_sp, friend_tbp,
                            my_bp, my_sp, my_tbp, roster_pool, n_matches):
    """
    roster pool 기반 championship track.
    roster_pool을 순환 사용하므로 다양한 roster 환경에서 팀빌딩 성능 측정.
    """
    params = BattleRuleParam()
    _set_params_safe(my_bp, params)
    _set_params_safe(friend_bp, params)

    wins = losses = errors = 0
    n_pairs = n_matches // 2
    log_every = max(2, n_matches // 4)
    roster_cycle = cycle(roster_pool)
    print(f"\n  [Championship]  DaehoV2 vs {display_name}  ({n_matches} games, build-{BUILD_SIZE}/select-{SELECT_SIZE})")

    for i in range(n_pairs):
        roster, meta = next(roster_cycle)

        # 팀빌딩 (양측 동일 roster에서)
        try:
            cmd0  = sanitized_team_build_decision(my_tbp,     roster, meta, BUILD_SIZE, MAX_PKM_MOVES, N_ACTIVE)
            cmd1  = sanitized_team_build_decision(friend_tbp, roster, meta, BUILD_SIZE, MAX_PKM_MOVES, N_ACTIVE)
            team0 = build_team(cmd0, roster)
            team1 = build_team(cmd1, roster)
            if not team0.members or not team1.members:
                errors += 2
                continue
        except Exception:
            errors += 2
            continue

        # Direction 1: DaehoV2 = side 0
        try:
            result = _run_game(team0, team1, my_bp, my_sp, friend_bp, friend_sp, params, SELECT_SIZE)
            if result == 0: wins += 1
            else:           losses += 1
        except Exception:
            errors += 1

        # Direction 2: DaehoV2 = side 1
        try:
            result = _run_game(team1, team0, friend_bp, friend_sp, my_bp, my_sp, params, SELECT_SIZE)
            if result == 1: wins += 1
            else:           losses += 1
        except Exception:
            errors += 1

        done = (i + 1) * 2
        if done % log_every == 0:
            total = wins + losses
            wr = wins / total * 100 if total > 0 else 0
            print(f"    [{done:>4}/{n_matches}] WR: {wr:5.1f}%  Err: {errors}")

    return wins, losses, errors


# ──────────────────────────────────────────────
#  CSV 저장
# ──────────────────────────────────────────────

def save_results(rows):
    filename = "friends_benchmark_results.csv"
    file_exists = os.path.isfile(filename)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Friend", "Track", "Wins", "Losses", "Errors", "WinRate"])
            for name, track, w, l, e in rows:
                total = w + l
                wr = f"{w / total * 100:.1f}%" if total > 0 else "N/A"
                writer.writerow([timestamp, name, track, w, l, e, wr])
        print(f"[INFO] Appended to friends_benchmark_results.csv")
    except Exception as ex:
        print(f"[ERROR] Could not save: {ex}")


# ──────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='DaehoV2 vs 친구들 battle + championship track benchmark'
    )
    parser.add_argument('--n',  type=int, default=None,
                        help='battle/championship 공통 대전 수')
    parser.add_argument('--nb', type=int, default=N_BATTLE_MATCHES,
                        help=f'battle track 대전 수 (default: {N_BATTLE_MATCHES})')
    parser.add_argument('--nc', type=int, default=N_CHAMP_MATCHES,
                        help=f'championship track 대전 수 (default: {N_CHAMP_MATCHES})')
    parser.add_argument('--friend', type=str, default=None,
                        help='특정 친구 폴더 이름만 테스트 (예: wonyoung)')
    parser.add_argument('--mode', choices=['battle', 'championship', 'both'], default='both',
                        help='테스트 트랙 선택 (default: both)')
    args = parser.parse_args()

    nb = args.n if args.n is not None else args.nb
    nc = args.n if args.n is not None else args.nc
    nb = nb if nb % 2 == 0 else nb + 1
    nc = nc if nc % 2 == 0 else nc + 1

    do_battle = args.mode in ('battle', 'both')
    do_champ  = args.mode in ('championship', 'both')

    friends_root = os.path.join(repo_root, 'friends')
    discovered   = discover_friends(friends_root)

    if args.friend:
        discovered = [(n, p) for n, p in discovered if n == args.friend]
        if not discovered:
            print(f"[ERROR] '{args.friend}' not found in friends/")
            sys.exit(1)

    print("=" * 65)
    print("  DaehoV2 — Friends Benchmark")
    print(f"  Battle track      : {'ON  (' + str(nb) + ' games)' if do_battle else 'OFF'}")
    champ_label = f"ON  ({nc} games, build-{BUILD_SIZE}/select-{SELECT_SIZE})" if do_champ else "OFF"
    print(f"  Championship track: {champ_label}")
    print(f"  Friends folder    : {friends_root}")
    print("=" * 65)

    print("\nDiscovered friends:")
    for name, _ in discovered:
        print(f"  • {name}")
    if not discovered:
        print("  (없음 — friends/ 폴더에 하위 디렉터리를 추가하세요)")
        sys.exit(0)

    my_comp = DaehoV2Competitor("DaehoV2")
    my_bp   = my_comp.battlepolicy
    my_sp   = my_comp.selectionpolicy
    my_tbp  = my_comp.teambuildpolicy

    # Championship 로스터 풀 미리 생성
    roster_pool = None
    if do_champ:
        print()
        roster_pool = gen_roster_pool(N_ROSTER_POOL)

    all_results = []
    start_time  = time.time()

    for friend_folder, folder_path in discovered:
        print(f"\n{'─'*65}")
        print(f"  Loading {friend_folder}...")
        try:
            display_name, friend_bp, friend_sp, friend_tbp = load_friend(folder_path, friend_folder)
            tbp_info = "있음" if friend_tbp else "없음 (championship 스킵)"
            print(f"  Name: {display_name}  |  teambuildpolicy: {tbp_info}")
        except Exception as ex:
            print(f"  [WARN] Failed to load {friend_folder}: {ex}")
            continue

        friend_rows = []

        if do_battle:
            w, l, e = benchmark_battle(display_name, friend_bp, friend_sp, my_bp, my_sp, nb)
            friend_rows.append((display_name, 'battle', w, l, e))

        if do_champ:
            if friend_tbp is None:
                print(f"\n  [Championship] {display_name} — teambuildpolicy 없음, 스킵")
            else:
                w, l, e = benchmark_championship(
                    display_name, friend_bp, friend_sp, friend_tbp,
                    my_bp, my_sp, my_tbp, roster_pool, nc,
                )
                friend_rows.append((display_name, 'championship', w, l, e))

        all_results.extend(friend_rows)
        save_results(friend_rows)

    elapsed = time.time() - start_time

    print(f"\n\n{'='*65}")
    print(f"  FINAL RESULTS  (elapsed: {elapsed/60:.1f} min)")
    print(f"{'='*65}")
    print(f"  {'Friend':<22} {'Track':<16} {'WinRate':>8}  {'W/Total':>12}  Err")
    print(f"  {'─'*58}")
    for name, track, w, l, e in all_results:
        total = w + l
        wr    = f"{w / total * 100:.1f}%" if total > 0 else "N/A"
        print(f"  {name:<22} {track:<16} {wr:>8}  {f'{w}/{total}':>12}  {e}")
    print(f"{'='*65}\n")
