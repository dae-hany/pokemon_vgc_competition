"""
friends_benchmark.py — DaehoV2 + 친구들 전원 round-robin 승률 측정.

friends/ 폴더의 하위 디렉터리를 자동 스캔한다.
각 친구 폴더 안에 *Competitor.py 파일이 있어야 한다.

Battle track       : 랜덤 팀으로 selection + battle 성능 측정
Championship track : roster 기반 team build → selection → battle 전체 측정

모든 참가자 쌍이 서로 붙는 round-robin 방식.
결과는 Win Rate 행렬로 출력된다.
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
from collections import namedtuple
from datetime import datetime
from itertools import combinations, cycle

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
BUILD_SIZE       = 6      # 팀빌딩: 50마리 중 6마리
SELECT_SIZE      = 4      # 선발: 6마리 중 4마리 (championship)
N_MOVES          = 100
ROSTER_SIZE      = 50
MAX_PKM_MOVES    = 4
N_ACTIVE         = 2
N_ROSTER_POOL    = 20     # 미리 생성해두는 roster 풀 크기

Participant = namedtuple('Participant', ['name', 'bp', 'sp', 'tbp'])


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
#  Loading
# ──────────────────────────────────────────────

def _find_competitor_class(mod):
    from vgc2.competition import Competitor
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if issubclass(obj, Competitor) and obj is not Competitor:
            return obj
    return None


def load_friend(folder_path, friend_folder_name) -> Participant:
    """
    friends/{name}/ 폴더에서 *Competitor.py를 찾아 Participant로 반환.
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
        return Participant(comp.name, bp, sp, tbp)
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

def _run_game(team0, team1, bp0, sp0, bp1, sp1, params, select_size) -> int:
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
    try:
        bp.set_params(params)
    except Exception:
        pass


def _run_pair(p1: Participant, p2: Participant, team0, team1, params, select_size):
    """
    p1 vs p2 양방향 1쌍 실행.
    Returns (p1_wins, p2_wins, errors) — 각각 0 또는 1.
    """
    p1w = p2w = err = 0

    # Direction 1: p1 = side 0
    try:
        result = _run_game(team0, team1, p1.bp, p1.sp, p2.bp, p2.sp, params, select_size)
        if result == 0: p1w += 1
        else:           p2w += 1
    except Exception:
        err += 1

    # Direction 2: p1 = side 1
    try:
        result = _run_game(team1, team0, p2.bp, p2.sp, p1.bp, p1.sp, params, select_size)
        if result == 1: p1w += 1
        else:           p2w += 1
    except Exception:
        err += 1

    return p1w, p2w, err


# ──────────────────────────────────────────────
#  Battle track
# ──────────────────────────────────────────────

def benchmark_pair_battle(p1: Participant, p2: Participant, n_matches: int):
    """
    battle track: 랜덤 팀으로 n_matches 대전.
    Returns (p1_wins, p2_wins, errors).
    """
    params = BattleRuleParam()
    _set_params_safe(p1.bp, params)
    _set_params_safe(p2.bp, params)

    p1w = p2w = errors = 0
    n_pairs   = n_matches // 2
    log_every = max(2, n_matches // 4)

    for i in range(n_pairs):
        team0 = gen_team(6, 4)
        team1 = gen_team(6, 4)
        label_teams((team0, team1))
        w1, w2, e = _run_pair(p1, p2, team0, team1, params, 6)
        p1w += w1; p2w += w2; errors += e

        done = (i + 1) * 2
        if done % log_every == 0:
            total = p1w + p2w
            wr = p1w / total * 100 if total > 0 else 0
            print(f"    [{done:>4}/{n_matches}]  {p1.name}: {wr:5.1f}%  Err: {errors}")

    return p1w, p2w, errors


# ──────────────────────────────────────────────
#  Championship track
# ──────────────────────────────────────────────

def gen_roster_pool(n):
    print(f"  Generating {n} rosters for championship...", end='', flush=True)
    pool = []
    for _ in range(n):
        move_set = gen_move_set(N_MOVES)
        roster   = gen_pkm_roster(ROSTER_SIZE, move_set)
        label_roster(move_set, roster)
        pool.append((roster, BasicMeta(move_set, roster)))
    print(" done.")
    return pool


def benchmark_pair_championship(p1: Participant, p2: Participant,
                                 roster_pool: list, n_matches: int):
    """
    championship track: roster pool을 순환하며 n_matches 대전.
    두 참가자 모두 teambuildpolicy가 있어야 한다.
    Returns (p1_wins, p2_wins, errors).
    """
    params = BattleRuleParam()
    _set_params_safe(p1.bp, params)
    _set_params_safe(p2.bp, params)

    p1w = p2w = errors = 0
    n_pairs      = n_matches // 2
    log_every    = max(2, n_matches // 4)
    roster_cycle = cycle(roster_pool)

    for i in range(n_pairs):
        roster, meta = next(roster_cycle)
        try:
            cmd0  = sanitized_team_build_decision(p1.tbp, roster, meta, BUILD_SIZE, MAX_PKM_MOVES, N_ACTIVE)
            cmd1  = sanitized_team_build_decision(p2.tbp, roster, meta, BUILD_SIZE, MAX_PKM_MOVES, N_ACTIVE)
            team0 = build_team(cmd0, roster)
            team1 = build_team(cmd1, roster)
            if not team0.members or not team1.members:
                errors += 2
                continue
        except Exception:
            errors += 2
            continue

        w1, w2, e = _run_pair(p1, p2, team0, team1, params, SELECT_SIZE)
        p1w += w1; p2w += w2; errors += e

        done = (i + 1) * 2
        if done % log_every == 0:
            total = p1w + p2w
            wr = p1w / total * 100 if total > 0 else 0
            print(f"    [{done:>4}/{n_matches}]  {p1.name}: {wr:5.1f}%  Err: {errors}")

    return p1w, p2w, errors


# ──────────────────────────────────────────────
#  결과 출력 & 저장
# ──────────────────────────────────────────────

def print_matrix(participants: list[Participant], results: dict, track: str):
    """
    Win Rate 행렬 출력.
    results[(p1.name, p2.name)] = (p1_wins, p2_wins, errors)
    행(row): 내가 누구를 이겼는지 / 열(col): 상대
    """
    names = [p.name for p in participants]
    col_w = max(10, max(len(n) for n in names) + 2)
    row_label_w = col_w

    print(f"\n  Win Rate Matrix — {track.capitalize()} Track  (행 vs 열, 행의 승률)")
    print(f"  {'':>{row_label_w}}", end='')
    for n in names:
        print(f"  {n:>{col_w}}", end='')
    print()
    print(f"  {'─' * (row_label_w + (col_w + 2) * len(names))}")

    for p1 in participants:
        print(f"  {p1.name:>{row_label_w}}", end='')
        for p2 in participants:
            if p1.name == p2.name:
                print(f"  {'—':>{col_w}}", end='')
            elif (p1.name, p2.name) in results:
                w1, w2, _ = results[(p1.name, p2.name)]
                total = w1 + w2
                wr = f"{w1 / total * 100:.1f}%" if total > 0 else "N/A"
                print(f"  {wr:>{col_w}}", end='')
            elif (p2.name, p1.name) in results:
                w2_stored, w1_stored, _ = results[(p2.name, p1.name)]
                total = w1_stored + w2_stored
                wr = f"{w1_stored / total * 100:.1f}%" if total > 0 else "N/A"
                print(f"  {wr:>{col_w}}", end='')
            else:
                print(f"  {'skip':>{col_w}}", end='')
        print()


def save_results(rows: list, track: str):
    filename = "friends_benchmark_results.csv"
    file_exists = os.path.isfile(filename)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Track", "P1", "P2",
                                 "P1_Wins", "P2_Wins", "Errors", "P1_WinRate"])
            for p1_name, p2_name, w1, w2, e in rows:
                total = w1 + w2
                wr = f"{w1 / total * 100:.1f}%" if total > 0 else "N/A"
                writer.writerow([timestamp, track, p1_name, p2_name, w1, w2, e, wr])
        print(f"[INFO] Appended to friends_benchmark_results.csv")
    except Exception as ex:
        print(f"[ERROR] Could not save: {ex}")


# ──────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='DaehoV2 + 친구들 round-robin battle + championship benchmark'
    )
    parser.add_argument('--n',  type=int, default=None,
                        help='battle/championship 공통 대전 수')
    parser.add_argument('--nb', type=int, default=N_BATTLE_MATCHES,
                        help=f'battle track 쌍당 대전 수 (default: {N_BATTLE_MATCHES})')
    parser.add_argument('--nc', type=int, default=N_CHAMP_MATCHES,
                        help=f'championship track 쌍당 대전 수 (default: {N_CHAMP_MATCHES})')
    parser.add_argument('--friend', type=str, default=None,
                        help='특정 친구 폴더만 포함 (예: wonyoung). 미지정 시 전원 포함')
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

    # ── 참가자 로드 ──────────────────────────────
    print("=" * 65)
    print("  DaehoV2 + Friends — Round-Robin Benchmark")
    print(f"  Battle track      : {'ON  (' + str(nb) + ' games/pair)' if do_battle else 'OFF'}")
    champ_label = f"ON  ({nc} games/pair, build-{BUILD_SIZE}/select-{SELECT_SIZE})" if do_champ else "OFF"
    print(f"  Championship track: {champ_label}")
    print("=" * 65)

    my_raw = DaehoV2Competitor("DaehoV2")
    participants: list[Participant] = [
        Participant("DaehoV2", my_raw.battlepolicy, my_raw.selectionpolicy, my_raw.teambuildpolicy)
    ]

    print("\nLoading friends...")
    for folder_name, folder_path in discovered:
        try:
            p = load_friend(folder_path, folder_name)
            tbp_info = "teambuild O" if p.tbp else "teambuild X"
            print(f"  Loaded: {p.name} ({tbp_info})")
            participants.append(p)
        except Exception as ex:
            print(f"  [WARN] {folder_name}: {ex}")

    if len(participants) < 2:
        print("[ERROR] 참가자가 2명 미만입니다.")
        sys.exit(1)

    pairs = list(combinations(participants, 2))
    n_pairs_total = len(pairs)
    print(f"\nParticipants : {len(participants)}명  →  {n_pairs_total}쌍")
    for p in participants:
        print(f"  • {p.name}")

    # ── Championship roster pool 생성 ────────────
    roster_pool = None
    if do_champ:
        print()
        roster_pool = gen_roster_pool(N_ROSTER_POOL)

    # ── Round-robin 실행 ─────────────────────────
    battle_results: dict[tuple, tuple] = {}
    champ_results:  dict[tuple, tuple] = {}
    start_time = time.time()

    for pair_idx, (p1, p2) in enumerate(pairs, 1):
        print(f"\n{'─'*65}")
        print(f"  [{pair_idx}/{n_pairs_total}]  {p1.name}  vs  {p2.name}")

        if do_battle:
            print(f"  [Battle]")
            w1, w2, e = benchmark_pair_battle(p1, p2, nb)
            battle_results[(p1.name, p2.name)] = (w1, w2, e)
            total = w1 + w2
            wr1 = f"{w1/total*100:.1f}%" if total > 0 else "N/A"
            wr2 = f"{w2/total*100:.1f}%" if total > 0 else "N/A"
            print(f"    → {p1.name}: {wr1}  /  {p2.name}: {wr2}  (Err: {e})")

        if do_champ:
            if p1.tbp is None or p2.tbp is None:
                missing = [p.name for p in (p1, p2) if p.tbp is None]
                print(f"  [Championship] 스킵 — teambuildpolicy 없음: {', '.join(missing)}")
            else:
                print(f"  [Championship]")
                w1, w2, e = benchmark_pair_championship(p1, p2, roster_pool, nc)
                champ_results[(p1.name, p2.name)] = (w1, w2, e)
                total = w1 + w2
                wr1 = f"{w1/total*100:.1f}%" if total > 0 else "N/A"
                wr2 = f"{w2/total*100:.1f}%" if total > 0 else "N/A"
                print(f"    → {p1.name}: {wr1}  /  {p2.name}: {wr2}  (Err: {e})")

    elapsed = time.time() - start_time

    # ── 결과 출력 ────────────────────────────────
    print(f"\n\n{'='*65}")
    print(f"  FINAL RESULTS  (elapsed: {elapsed/60:.1f} min)")
    print(f"{'='*65}")

    if do_battle and battle_results:
        print_matrix(participants, battle_results, 'battle')

    if do_champ and champ_results:
        print_matrix(participants, champ_results, 'championship')

    print(f"\n{'='*65}\n")

    # ── CSV 저장 ─────────────────────────────────
    if do_battle and battle_results:
        rows = [(k[0], k[1], v[0], v[1], v[2]) for k, v in battle_results.items()]
        save_results(rows, 'battle')
    if do_champ and champ_results:
        rows = [(k[0], k[1], v[0], v[1], v[2]) for k, v in champ_results.items()]
        save_results(rows, 'championship')
