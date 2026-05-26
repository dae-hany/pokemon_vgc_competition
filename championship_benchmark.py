import sys
import os
import io
import time
import csv
import importlib.util
from datetime import datetime
from random import shuffle

# Fix Unicode output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

repo_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(repo_root, 'my_submission_battleV2'))

from vgc2.agent.battle import GreedyBattlePolicy
from vgc2.agent.selection import RandomSelectionPolicy
from vgc2.agent.teambuild import RandomTeamBuildPolicy
from vgc2.balance.meta import BasicMeta
from vgc2.competition import CompetitorManager
from vgc2.competition.ecosystem import Championship, label_roster, Strategy
from vgc2.util.generator import gen_move_set, gen_pkm_roster
# pyrefly: ignore [missing-import]
from competitor import DaehoV2Competitor

# ──────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────
N_EPOCHS    = 30   # 에포크 수 (실제 대회는 100, 빠른 테스트는 10 권장)
N_MOVES     = 100  # 무브셋 크기
ROSTER_SIZE = 50   # 로스터 크기 (실제 대회와 동일)
N_ACTIVE    = 2    # 동시 출전 포켓몬 수
N_BATTLES   = 3    # 매치당 배틀 수
# ──────────────────────────────────────────────


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


def load_competitor(name, folder, comp_file, comp_cls, custom_policies=None):
    base_path = os.path.join('edition', 'vgc2025', 'submissions')
    path = os.path.abspath(os.path.join(base_path, folder))
    if not os.path.exists(path): return None

    module_key = f"competitor_{name.replace(' ', '_').lower()}"

    try:
        if path not in sys.path: sys.path.insert(0, path)
        if custom_policies:
            old_cwd = os.getcwd()
            os.chdir(path)
            try:
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


def save_results_to_csv(ranking, elapsed_s):
    filename = "championship_benchmark_results.csv"
    file_exists = os.path.isfile(filename)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Rank", "Name", "ELO", "ElapsedMin"])
            for rank, cm in enumerate(ranking, 1):
                writer.writerow([timestamp, rank, cm.competitor.name,
                                 f"{cm.elo:.1f}", f"{elapsed_s/60:.1f}"])
        print(f"\n[INFO] Results saved to {filename}")
    except Exception as e:
        print(f"\n[ERROR] Could not save results: {e}")


if __name__ == '__main__':
    # 1. 로스터 한 번 생성 (실제 대회와 동일)
    print("Generating fixed roster...")
    move_set = gen_move_set(N_MOVES)
    roster   = gen_pkm_roster(ROSTER_SIZE, move_set)
    label_roster(move_set, roster)
    meta = BasicMeta(move_set, roster)
    print(f"  Roster fixed: {ROSTER_SIZE} Pokemon, {N_MOVES} moves\n")

    # 2. 참가자 로드
    print("Initializing DaehoAI...")
    my_comp = DaehoV2Competitor("DaehoV2")

    targets = [
        ("Greedy",       "Greedy",                     None,                    None,                      "FIXED"),
        ("JJJ",          "JJJ - JunSung - wfd gfd",    None,                    None,                      {
            'b_mod': 'JJJ', 'b_cls': 'JJJ_BattlePolicy',
            's_mod': 'JJJ', 's_cls': 'JJJ_selectionPolicy',
            't_mod': 'JJJTeamPolicy', 't_cls': 'JJJ_TeamBuildPolicy'
        }),
        ("Yamabuki",     "iceMonteSubmission",          None,                    None,                      {
            'b_mod': 'iceMonteBattlePolicy', 'b_cls': 'IceMonteBattlePolicy',
            's_mod': 'iceMonteSelectionPolicy', 's_cls': 'IceMonteSelectionPolicy'
        }),
        ("Jirachi",      "jirachi - DONGMIN KIM",       None,                    None,                      {
            'b_mod': 'jirachi_core_policies', 'b_cls': 'AlwaysSmartBeamSearchPolicy',
            's_mod': 'jirachi_core_policies', 's_cls': 'MaxFirepowerSelectionPolicy'
        }),
        ('Botzilla',     'BotzillaSubmission',          'botzillaCompetitor',    'BotzillaCompetitor',      None),
        ('Laze',         'LazeComp',                    'LazeCompetitor',        'LazeCompetitor',          None),
        ('Peach',        'PeachSubmission',             'PeachCompetitor',       'PeachCompetitor',         None),
        ('StocKarpador', 'StocKarpadorSubmission',      'StocKarpadorCompetitor','StocKarpadorCompetitor',  None),
        ('EvoTrainer',   'evoTrainer',                  'EvoCompetitor',         'EvoCompetitor',           None),
        ('Minimon',      'minimon_02 - Leon Brunke',    'minimon',               'minimon',                 None),
        ('Caaaden',      'caaaden_competitor',          'caaaden_competitor',    'CaaadenCompetitor',       None),
    ]

    print("\nLoading Competitors...")
    all_comps = [my_comp]
    for name, folder, c_file, c_cls, extra in targets:
        if name == "Greedy":
            comp = SimpleCompetitor("Greedy", GreedyBattlePolicy(),
                                    RandomSelectionPolicy(), RandomTeamBuildPolicy())
        else:
            comp = load_competitor(name, folder, c_file, c_cls,
                                   extra if isinstance(extra, dict) else None)
        if comp:
            # teambuildpolicy가 None인 경쟁자는 RandomTeamBuildPolicy로 대체
            if getattr(comp, 'teambuildpolicy', None) is None:
                comp = SimpleCompetitor(
                    comp.name,
                    comp.battlepolicy,
                    comp.selectionpolicy or RandomSelectionPolicy(),
                    RandomTeamBuildPolicy(),
                )
            all_comps.append(comp)
            print(f"  Loaded: {comp.name}")
        else:
            print(f"  Skipped: {name} (not found)")

    n_participants = len(all_comps)
    print(f"\nTotal participants: {n_participants}")

    # 3. Championship 실행 (고정 로스터, 전원 참가)
    print(f"\n{'='*65}")
    print(f"  CHAMPIONSHIP BENCHMARK")
    print(f"  Roster : FIXED {ROSTER_SIZE} Pokemon")
    print(f"  Players: {n_participants}")
    print(f"  Epochs : {N_EPOCHS}  |  Battles/match: {N_BATTLES}")
    print(f"{'='*65}\n")

    championship = Championship(
        roster, meta,
        epochs=N_EPOCHS,
        n_active=N_ACTIVE,
        n_battles=N_BATTLES,
        max_team_size=6,          # 실제 대회 설정: 6마리 빌드, 4마리 선발
        strategy=Strategy.ELO_PAIRING,
    )
    for comp in all_comps:
        championship.register(CompetitorManager(comp))

    start_time = time.time()

    # 에포크 루프 (진행 상황 직접 출력)
    e = 0
    shuffle(championship.cm)
    while e < N_EPOCHS:
        championship._build_teams()
        championship._pairings()
        championship._matches()
        e += 1

        if e % 5 == 0 or e == 1:
            elapsed = time.time() - start_time
            ranking_now = championship.ranking()
            my_rank = next((i + 1 for i, cm in enumerate(ranking_now)
                            if cm.competitor.name == "Daeho_AI"), "?")
            my_elo  = next((f"{cm.elo:.0f}" for cm in ranking_now
                            if cm.competitor.name == "DaehoV2"), "?")
            print(f"  [Epoch {e:>3}/{N_EPOCHS}]  "
                  f"Elapsed: {elapsed/60:.1f}min  |  "
                  f"DaehoV2: #{my_rank} (ELO {my_elo})")

    elapsed_total = time.time() - start_time

    # 4. 최종 순위 출력
    ranking = championship.ranking()
    print(f"\n\n{'='*65}")
    print(f"  FINAL RANKING  (elapsed: {elapsed_total/60:.1f} min)")
    print(f"{'='*65}")
    print(f"  {'Rank':<6} {'Name':<22} {'ELO':>8}")
    print(f"  {'-'*40}")
    for rank, cm in enumerate(ranking, 1):
        marker = " ◀" if cm.competitor.name == "DaehoV2" else ""
        print(f"  {rank:<6} {cm.competitor.name:<22} {cm.elo:>8.1f}{marker}")
    print(f"{'='*65}\n")

    save_results_to_csv(ranking, elapsed_total)
