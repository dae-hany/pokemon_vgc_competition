"""
Debug test: Run a single battle to check MCTS behavior.
"""
import sys
import traceback

sys.path.insert(0, 'my_submission')

from vgc2.agent.battle import GreedyBattlePolicy
from vgc2.battle_engine import BattleEngine, State, BattleRuleParam
from vgc2.battle_engine.game_state import get_battle_teams
from vgc2.battle_engine.view import TeamView, StateView
from vgc2.competition.match import label_teams
from vgc2.util.generator import gen_team

from my_submission.battle_policy import MCTSBattlePolicy


def run_single_battle():
    params = BattleRuleParam()
    n_active = 2
    max_team_size = 4
    max_pkm_moves = 4

    team = (gen_team(max_team_size, max_pkm_moves), gen_team(max_team_size, max_pkm_moves))
    label_teams(team)
    team_view = (TeamView(team[0]), TeamView(team[1]))

    b_teams = get_battle_teams(team, n_active)
    state = State(b_teams)
    engine = BattleEngine(state, params)
    state_view = (StateView(state, 0, team_view), StateView(state, 1, team_view))

    my_policy = MCTSBattlePolicy(time_limit_ms=85.0)
    my_policy.set_params(params)
    opp_policy = GreedyBattlePolicy()
    opp_policy.set_params(params)

    turn = 0
    while not engine.state.terminal() and turn < 100:
        turn += 1
        try:
            my_cmds = my_policy.decision(state_view[0], opp_view=team_view[1])
            opp_cmds = opp_policy.decision(state_view[1])
            engine.run_turn((my_cmds, opp_cmds))
            print(f"Turn {turn}: my_cmds={my_cmds}, opp_cmds={opp_cmds}")
        except Exception as e:
            print(f"ERROR on turn {turn}: {e}")
            traceback.print_exc()
            break

    print(f"\nBattle ended after {turn} turns. Winner: side {engine.winning_side}")


if __name__ == '__main__':
    run_single_battle()
