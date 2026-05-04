"""
Grid Search for Selection Policy weight tuning.
Tests different weight combinations and reports win rates vs Greedy.
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
MAX_TEAM_SIZE = 4
MAX_PKM_MOVES = 4


def run_match(my_battle, my_sel, opp_battle, opp_sel, params):
    team = (gen_team(MAX_TEAM_SIZE, MAX_PKM_MOVES), gen_team(MAX_TEAM_SIZE, MAX_PKM_MOVES))
    label_teams(team)
    tv = (TeamView(team[0]), TeamView(team[1]))
    mi = sanitized_selection_decision(my_sel, (team[0], tv[1]), MAX_TEAM_SIZE)
    oi = sanitized_selection_decision(opp_sel, (team[1], tv[0]), MAX_TEAM_SIZE)
    ms, mv = subteam(team[0], tv[0], mi)
    os_, ov = subteam(team[1], tv[1], oi)
    state = State(get_battle_teams((ms, os_), N_ACTIVE))
    sv = (StateView(state, 0, (mv, ov)), StateView(state, 1, (mv, ov)))
    engine = BattleEngine(state, params)
    return run_battle(engine, (my_battle, opp_battle), (tv[0], tv[1]), sv)


def test_weights(weights, n=N_MATCHES):
    params = BattleRuleParam()
    sel = CoverageSelectionPolicy()
    sel.W_OFFENSE = weights[0]
    sel.W_DEFENSE = weights[1]
    sel.W_BALANCE = weights[2]
    sel.W_SPEED = weights[3]
    sel.W_UTIL = weights[4]
    sel.W_WEAKNESS = weights[5]
    bp = EnhancedBattlePolicy()
    bp.set_params(params)
    ob = GreedyBattlePolicy()
    ob.set_params(params)
    os_ = RandomSelectionPolicy()
    wins = sum(1 for _ in range(n)
               if run_match(bp, sel, ob, os_, params) == 0)
    return wins / n * 100


def main():
    off_r = [0.8, 1.07, 1.3]
    def_r = [0.2, 0.42, 0.6]
    bal_r = [0.3, 0.5, 0.8, 1.25]
    spd_r = [0.1, 0.3, 0.5]
    utl_r = [0.0, 0.2, 0.4]
    wkn_r = [0.0, 0.15, 0.3]

    total = len(off_r)*len(def_r)*len(bal_r)*len(spd_r)*len(utl_r)*len(wkn_r)
    print(f"Total configs: {total}, {N_MATCHES} matches each")

    results = []
    n = 0
    for o in off_r:
        for d in def_r:
            for b in bal_r:
                for s in spd_r:
                    for u in utl_r:
                        for w in wkn_r:
                            n += 1
                            t = time.time()
                            wr = test_weights((o, d, b, s, u, w))
                            dt = time.time() - t
                            results.append((wr, o, d, b, s, u, w))
                            print(f"[{n:3d}/{total}] "
                                  f"O={o:.2f} D={d:.2f} B={b:.2f} "
                                  f"S={s:.2f} U={u:.2f} W={w:.2f} "
                                  f"-> {wr:.0f}% ({dt:.1f}s)")

    results.sort(reverse=True)
    print(f"\n{'='*70}")
    print("  TOP 10 CONFIGS")
    print(f"{'='*70}")
    for i, (wr, o, d, b, s, u, w) in enumerate(results[:10]):
        print(f"  #{i+1}: {wr:.0f}% | O={o} D={d} B={b} S={s} U={u} W={w}")

    best = results[0]
    print(f"\nBEST: W_OFFENSE={best[1]}, W_DEFENSE={best[2]}, "
          f"W_BALANCE={best[3]}, W_SPEED={best[4]}, "
          f"W_UTIL={best[5]}, W_WEAKNESS={best[6]} -> {best[0]:.0f}%")


if __name__ == '__main__':
    main()
