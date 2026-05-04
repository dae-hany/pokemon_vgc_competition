"""
Benchmark: Daeho_AI vs Greedy/Random/2025 Winners - 100 match 승률 측정.
각 match는 독립적인 랜덤 팀으로 진행 (Battle Track 방식).
"""
import sys
import time
import os

sys.path.insert(0, 'my_submission')

from vgc2.agent.battle import RandomBattlePolicy, GreedyBattlePolicy
from vgc2.agent.selection import RandomSelectionPolicy
from vgc2.battle_engine import BattleEngine, State, BattleRuleParam
from vgc2.battle_engine.game_state import get_battle_teams
from vgc2.battle_engine.security import sanitized_selection_decision
from vgc2.battle_engine.view import TeamView, StateView
from vgc2.competition.match import label_teams, run_battle, subteam
from vgc2.util.generator import gen_team

from competitor import DaehoCompetitor


N_MATCHES = 500
N_ACTIVE = 2
TEAM_GEN_SIZE = 6    # Generate 6 pokemon per team
MAX_TEAM_SIZE = 4    # Select 4 from 6 (selection policy matters!)
MAX_PKM_MOVES = 4


def run_single_match(my_battle, my_sel, opp_battle, opp_sel, params):
    """Run a single match. Returns 0 if side 0 wins, 1 otherwise."""
    team = (gen_team(TEAM_GEN_SIZE, MAX_PKM_MOVES), gen_team(TEAM_GEN_SIZE, MAX_PKM_MOVES))
    label_teams(team)
    team_view = (TeamView(team[0]), TeamView(team[1]))

    my_idx = sanitized_selection_decision(my_sel, (team[0], team_view[1]), TEAM_GEN_SIZE)[:MAX_TEAM_SIZE]
    opp_idx = sanitized_selection_decision(opp_sel, (team[1], team_view[0]), TEAM_GEN_SIZE)[:MAX_TEAM_SIZE]

    my_sub_team, my_sub_view = subteam(team[0], team_view[0], my_idx)
    opp_sub_team, opp_sub_view = subteam(team[1], team_view[1], opp_idx)

    state = State(get_battle_teams((my_sub_team, opp_sub_team), N_ACTIVE))
    state_view = (StateView(state, 0, (my_sub_view, opp_sub_view)),
                  StateView(state, 1, (my_sub_view, opp_sub_view)))
    engine = BattleEngine(state, params)

    winner = run_battle(engine, (my_battle, opp_battle), (team_view[0], team_view[1]), state_view)
    return winner


def benchmark(opponent_name, opp_battle_policy, opp_selection_policy, my_comp=None, n_matches=N_MATCHES):
    """Run N_MATCHES and report win rate."""
    params = BattleRuleParam()

    if my_comp is None:
        my_comp = DaehoCompetitor("Daeho_AI")
    my_comp.battlepolicy.set_params(params)
    opp_battle_policy.set_params(params)

    my_battle = my_comp.battlepolicy
    my_sel = my_comp.selectionpolicy

    wins = 0
    losses = 0
    errors = 0

    print(f"\n{'='*60}")
    print(f"  Daeho_AI vs {opponent_name} - {n_matches} matches")
    print(f"{'='*60}")

    start = time.time()
    for i in range(n_matches):
        try:
            result = run_single_match(my_battle, my_sel, opp_battle_policy, opp_selection_policy, params)
            if result == 0:
                wins += 1
            else:
                losses += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  Match {i+1}: ERROR - {e}")

        if (i + 1) % 10 == 0:
            elapsed = time.time() - start
            rate = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
            print(f"  [{i+1:3d}/{n_matches}] W:{wins} L:{losses} E:{errors} | WinRate: {rate:.1f}% | {elapsed:.1f}s")

    elapsed = time.time() - start
    total_valid = wins + losses
    win_rate = wins / total_valid * 100 if total_valid > 0 else 0

    print(f"\n{'='*60}")
    print(f"  FINAL RESULT: Daeho_AI vs {opponent_name}")
    print(f"  Wins: {wins} | Losses: {losses} | Errors: {errors}")
    print(f"  Win Rate: {win_rate:.1f}% ({wins}/{total_valid})")
    print(f"  Total Time: {elapsed:.1f}s ({elapsed/n_matches:.2f}s per match)")
    print(f"{'='*60}")

    return wins, losses, errors


def load_2025_winners():
    """Load 2025 winner battle/selection policies for benchmarking."""
    winners = {}

    # JJJ (Battle 2nd, Championship 1st)
    try:
        jjj_dir = os.path.join('edition', 'vgc2025', 'submissions', 'JJJ - JunSung - wfd gfd')
        sys.path.insert(0, jjj_dir)
        from JJJ import JJJ_BattlePolicy, JJJ_selectionPolicy
        winners['JJJ'] = (JJJ_BattlePolicy(), JJJ_selectionPolicy())
        print("  [OK] JJJ (Battle 2nd) loaded")
        sys.path.remove(jjj_dir)
    except Exception as e:
        print(f"  [FAIL] JJJ load failed: {e}")

    # IceMonte/Yamabuki (Battle 1st)
    try:
        ice_dir = os.path.join('edition', 'vgc2025', 'submissions', 'iceMonteSubmission')
        sys.path.insert(0, ice_dir)
        from iceMonteBattlePolicy import IceMonteBattlePolicy
        from iceMonteSelectionPolicy import IceMonteSelectionPolicy
        winners['Yamabuki'] = (IceMonteBattlePolicy(), IceMonteSelectionPolicy())
        print("  [OK] Yamabuki/IceMonte (Battle 1st) loaded")
        sys.path.remove(ice_dir)
    except Exception as e:
        print(f"  [FAIL] Yamabuki load failed: {e}")

    # Jirachi (Battle 3rd)
    try:
        jir_dir = os.path.join('edition', 'vgc2025', 'submissions', 'jirachi - DONGMIN KIM')
        sys.path.insert(0, jir_dir)
        from jirachi_core_policies import AlwaysSmartBeamSearchPolicy, MaxFirepowerSelectionPolicy
        winners['Jirachi'] = (AlwaysSmartBeamSearchPolicy(time_limit_ms=90), MaxFirepowerSelectionPolicy())
        print("  [OK] Jirachi (Battle 3rd) loaded")
        sys.path.remove(jir_dir)
    except Exception as e:
        print(f"  [FAIL] Jirachi load failed: {e}")

    return winners


if __name__ == '__main__':
    results = {}

    # 1) vs Greedy
    w, l, e = benchmark("Greedy", GreedyBattlePolicy(), RandomSelectionPolicy())
    results['Greedy'] = (w, l, e)

    # 2) vs Random
    w, l, e = benchmark("Random", RandomBattlePolicy(), RandomSelectionPolicy())
    results['Random'] = (w, l, e)

    # 3) vs 2025 Winners
    print(f"\n{'='*60}")
    print(f"  Loading 2025 Winners...")
    print(f"{'='*60}")
    winners = load_2025_winners()

    for name, (bp, sp) in winners.items():
        try:
            w, l, e = benchmark(name, bp, sp, n_matches=50)
            results[name] = (w, l, e)
        except Exception as ex:
            print(f"  Benchmark vs {name} failed: {ex}")
            results[name] = (0, 0, -1)

    # Summary
    print(f"\n{'='*60}")
    print(f"  BENCHMARK SUMMARY")
    print(f"{'='*60}")
    for name, (w, l, e) in results.items():
        total = w + l
        if total > 0:
            print(f"  vs {name:12s}: {w}/{total} ({w/total*100:.1f}%) | Errors: {e}")
        else:
            print(f"  vs {name:12s}: FAILED")
    print(f"{'='*60}")
