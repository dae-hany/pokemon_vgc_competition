"""
Benchmark: Daeho_AI vs Greedy/Random - 100 match (1:1) 승률 측정.
각 match는 독립적인 랜덤 팀으로 진행 (Battle Track 방식).
"""
import sys
import time

sys.path.insert(0, 'my_submission')

from vgc2.agent.battle import RandomBattlePolicy, GreedyBattlePolicy
from vgc2.agent.selection import RandomSelectionPolicy
from vgc2.battle_engine import BattleEngine, State, BattleRuleParam
from vgc2.battle_engine.game_state import get_battle_teams
from vgc2.battle_engine.security import sanitized_selection_decision
from vgc2.battle_engine.view import TeamView, StateView
from vgc2.competition.match import label_teams, run_battle
from vgc2.util.generator import gen_team

from competitor import DaehoCompetitor


N_MATCHES = 100
N_ACTIVE = 2
MAX_TEAM_SIZE = 4
MAX_PKM_MOVES = 4


def run_single_match(my_competitor, opp_battle_policy, opp_selection_policy, params):
    """Run a single match with random teams. Returns 0 if my_competitor wins, 1 otherwise."""
    # Generate random teams
    team = (gen_team(MAX_TEAM_SIZE, MAX_PKM_MOVES), gen_team(MAX_TEAM_SIZE, MAX_PKM_MOVES))
    label_teams(team)
    team_view = (TeamView(team[0]), TeamView(team[1]))

    # Selection phase
    my_sel = my_competitor.selectionpolicy
    my_idx = sanitized_selection_decision(my_sel, (team[0], team_view[1]), MAX_TEAM_SIZE)
    opp_idx = sanitized_selection_decision(opp_selection_policy, (team[1], team_view[0]), MAX_TEAM_SIZE)

    # Build sub-teams
    from vgc2.competition.match import subteam
    my_sub_team, my_sub_view = subteam(team[0], team_view[0], my_idx)
    opp_sub_team, opp_sub_view = subteam(team[1], team_view[1], opp_idx)

    # Battle setup
    state = State(get_battle_teams((my_sub_team, opp_sub_team), N_ACTIVE))
    state_view = (StateView(state, 0, (my_sub_view, opp_sub_view)),
                  StateView(state, 1, (my_sub_view, opp_sub_view)))
    engine = BattleEngine(state, params)

    # Battle
    my_bp = my_competitor.battlepolicy
    winner = run_battle(engine, (my_bp, opp_battle_policy), (team_view[0], team_view[1]), state_view)
    return winner


def benchmark(opponent_name, opp_battle_policy, opp_selection_policy):
    """Run N_MATCHES and report win rate."""
    params = BattleRuleParam()

    # Set params for policies
    my_comp = DaehoCompetitor("Daeho_AI")
    my_comp.battlepolicy.set_params(params)
    opp_battle_policy.set_params(params)

    wins = 0
    losses = 0
    errors = 0

    print(f"\n{'='*60}")
    print(f"  Daeho_AI vs {opponent_name} - {N_MATCHES} matches")
    print(f"{'='*60}")

    start = time.time()
    for i in range(N_MATCHES):
        try:
            result = run_single_match(my_comp, opp_battle_policy, opp_selection_policy, params)
            if result == 0:
                wins += 1
            else:
                losses += 1
        except Exception as e:
            errors += 1
            print(f"  Match {i+1}: ERROR - {e}")

        # Progress every 10 matches
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start
            rate = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
            print(f"  [{i+1:3d}/{N_MATCHES}] W:{wins} L:{losses} E:{errors} | WinRate: {rate:.1f}% | {elapsed:.1f}s")

    elapsed = time.time() - start
    total_valid = wins + losses
    win_rate = wins / total_valid * 100 if total_valid > 0 else 0

    print(f"\n{'='*60}")
    print(f"  FINAL RESULT: Daeho_AI vs {opponent_name}")
    print(f"  Wins: {wins} | Losses: {losses} | Errors: {errors}")
    print(f"  Win Rate: {win_rate:.1f}% ({wins}/{total_valid})")
    print(f"  Total Time: {elapsed:.1f}s ({elapsed/N_MATCHES:.2f}s per match)")
    print(f"{'='*60}")

    return wins, losses, errors


if __name__ == '__main__':
    # 1) vs Greedy
    greedy_wins, greedy_losses, greedy_errors = benchmark(
        "Greedy", GreedyBattlePolicy(), RandomSelectionPolicy()
    )

    # 2) vs Random
    random_wins, random_losses, random_errors = benchmark(
        "Random", RandomBattlePolicy(), RandomSelectionPolicy()
    )

    # Summary
    print(f"\n{'='*60}")
    print(f"  BENCHMARK SUMMARY")
    print(f"{'='*60}")
    g_total = greedy_wins + greedy_losses
    r_total = random_wins + random_losses
    print(f"  vs Greedy:  {greedy_wins}/{g_total} ({greedy_wins/g_total*100:.1f}%)" if g_total else "  vs Greedy: N/A")
    print(f"  vs Random:  {random_wins}/{r_total} ({random_wins/r_total*100:.1f}%)" if r_total else "  vs Random: N/A")
    print(f"{'='*60}")
