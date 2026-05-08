import sys
sys.path.insert(0, 'my_submission')
from vgc2.battle_engine import State, BattleRuleParam, BattlingMove, Move, Type, Category
from vgc2.battle_engine.view import StateView, TeamView
from vgc2.util.generator import gen_team
from vgc2.battle_engine.game_state import get_battle_teams
from vgc2.competition.match import label_teams, subteam
from vgc2.util.forward import copy_state, forward

team = (gen_team(4, 4), gen_team(4, 4))
label_teams(team)
team_view = (TeamView(team[0]), TeamView(team[1]))
state = State(get_battle_teams((team[0], team[1]), 2))
state_view = StateView(state, 0, team_view)

copied_state = copy_state(state_view)
forward(copied_state, ([(0, 0), (0, 0)], [(0, 0), (0, 0)]))
print("Forward success!")
