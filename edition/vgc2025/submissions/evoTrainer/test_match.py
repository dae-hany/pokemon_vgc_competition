import os
import sys

current_file_path = os.path.abspath(os.path.dirname(__file__))
repo_path = os.path.abspath(os.path.join(current_file_path, ".."))
framework_path = os.path.join(repo_path, "framework")

sys.path.insert(0, repo_path)
sys.path.insert(0, framework_path)

from EvoCompetitor import EvoCompetitor
from vgc2.competition import CompetitorManager
from vgc2.competition.match import Match
from vgc2.util.generator import gen_team

evo_competitor = EvoCompetitor(f"EvoTrainer 1")
player1 = CompetitorManager(evo_competitor)
player2 = CompetitorManager(EvoCompetitor(f"EvoTrainer 2"))

match = Match((player1, player2), team_gen=gen_team)
match.run()
if match.wins[0] > match.wins[1]:
    print("Match won by EvoTrainer 1")
else:
    print("Match won by EvoTrainer 2")
