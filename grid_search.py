"""
Grid Search for Selection Policy weight tuning (v3).
8 weights, reduced grid on less-important factors.
"""
import sys
import time

sys.path.insert(0, 'my_submission')

from vgc2.agent.battle import GreedyBattlePolicy
from vgc2.agent.selection import RandomSelectionPolicy
from vgc2.battle_engine import BattleEngine, State, BattleRuleParam
from vgc2.battle_engine.game_state import get_battle_teams
from vgc2.battle_engine.security import sanitized_selection_decision
from vgc2.battle_engine.view import TeamView, StateView
from vgc2.competition.match import label_teams, run_battle, subteam
from vgc2.util.generator import gen_team

from selection_policy import CoverageSelectionPolicy
from battle_policy import EnhancedBattlePolicy

N_MATCHES = 100
N_ACTIVE = 2
TEAM_GEN_SIZE = 6
MAX_TEAM_SIZE = 4
MAX_PKM_MOVES = 4


def run_match(my_battle, my_sel, opp_battle, opp_sel, params):
    team = (gen_team(TEAM_GEN_SIZE, MAX_PKM_MOVES),
            gen_team(TEAM_GEN_SIZE, MAX_PKM_MOVES))
    label_teams(team)
    tv = (TeamView(team[0]), TeamView(team[1]))
    mi = sanitized_selection_decision(my_sel, (team[0], tv[1]), TEAM_GEN_SIZE)[:MAX_TEAM_SIZE]
    oi = sanitized_selection_decision(opp_sel, (team[1], tv[0]), TEAM_GEN_SIZE)[:MAX_TEAM_SIZE]
    ms, mv = subteam(team[0], tv[0], mi)
    os_, ov = subteam(team[1], tv[1], oi)
    state = State(get_battle_teams((ms, os_), N_ACTIVE))
    sv = (StateView(state, 0, (mv, ov)),
          StateView(state, 1, (mv, ov)))
    engine = BattleEngine(state, params)
    return run_battle(engine, (my_battle, opp_battle),
                      (tv[0], tv[1]), sv)


def test_weights(w, n=N_MATCHES):
    params = BattleRuleParam()
    sel = CoverageSelectionPolicy()
    # w = (offense, firepower, defense, balance, speed, util, weakness, min_cov)
    sel.W_OFFENSE = w[0]
    sel.W_FIREPOWER = w[1]
    sel.W_DEFENSE = w[2]
    sel.W_BALANCE = w[3]
    sel.W_SPEED = w[4]
    sel.W_UTIL = w[5]
    sel.W_WEAKNESS = w[6]
    sel.W_MIN_COV = w[7]
    bp = EnhancedBattlePolicy()
    bp.set_params(params)
    ob = GreedyBattlePolicy()
    ob.set_params(params)
    os_ = RandomSelectionPolicy()
    wins = 0
    total = 0
    for _ in range(n):
        try:
            if run_match(bp, sel, ob, os_, params) == 0:
                wins += 1
            total += 1
        except Exception:
            pass
    return wins / total * 100 if total > 0 else 0.0


def main():
    # Key weights to search (most impactful)
    off_r = [0.8, 1.1, 1.5]      # offense (max-coverage)
    fp_r = [0.0, 0.3, 0.6]       # firepower (total sum)
    bal_r = [0.3, 0.6, 1.0]      # balance
    mcv_r = [0.4, 0.8, 1.2]      # min coverage

    # Fixed secondary weights (less impactful)
    dfn = 0.42
    spd = 0.30
    utl = 0.20
    wkn = 0.15

    configs = []
    for o in off_r:
        for f in fp_r:
            for b in bal_r:
                for m in mcv_r:
                    configs.append((o, f, dfn, b, spd, utl, wkn, m))

    total = len(configs)
    print(f"Total configs: {total}, {N_MATCHES} matches each")
    print(f"Fixed: DEF={dfn} SPD={spd} UTL={utl} WKN={wkn}")
    print()

    results = []
    for i, w in enumerate(configs):
        t = time.time()
        wr = test_weights(w)
        dt = time.time() - t
        results.append((wr, w))
        print(f"[{i+1:3d}/{total}] "
              f"OFF={w[0]:.1f} FP={w[1]:.1f} "
              f"BAL={w[3]:.1f} MCV={w[7]:.1f} "
              f"-> {wr:.0f}% ({dt:.1f}s)")

    results.sort(reverse=True)
    print(f"\n{'='*70}")
    print("  TOP 10 CONFIGS")
    print(f"{'='*70}")
    for i, (wr, w) in enumerate(results[:10]):
        print(f"  #{i+1}: {wr:.0f}% | "
              f"OFF={w[0]} FP={w[1]} DEF={w[2]} BAL={w[3]} "
              f"SPD={w[4]} UTL={w[5]} WKN={w[6]} MCV={w[7]}")

    best = results[0]
    print(f"\n{'='*70}")
    print(f"  BEST: {best[0]:.0f}%")
    print(f"  W_OFFENSE   = {best[1][0]}")
    print(f"  W_FIREPOWER = {best[1][1]}")
    print(f"  W_DEFENSE   = {best[1][2]}")
    print(f"  W_BALANCE   = {best[1][3]}")
    print(f"  W_SPEED     = {best[1][4]}")
    print(f"  W_UTIL      = {best[1][5]}")
    print(f"  W_WEAKNESS  = {best[1][6]}")
    print(f"  W_MIN_COV   = {best[1][7]}")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
