import os
import sys

# my_submission 모듈을 찾을 수 있도록 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vgc2.competition import Competitor
from ppo_submission.battle_policy import PPOBattlePolicy
from my_submission.selection_policy import CoverageSelectionPolicy
from my_submission.team_build_policy import SmartTeamBuildPolicy

class PPOCompetitor(Competitor):
    """
    PPO 기반 Battle Policy와 기존 Coverage 기반 Selection/TeamBuild Policy를
    결합한 최종 하이브리드 에이전트 클래스입니다.
    """
    def __init__(self, name: str = "PPO_League_Agent"):
        self._name = name
        
        # Battle Phase: PPO (RL)
        self._battle_policy = PPOBattlePolicy()
        
        # Selection Phase: Coverage (Rule-based, 4v4 선출)
        self._selection_policy = CoverageSelectionPolicy()
        
        # Team Building Phase: Smart Builder
        self._team_build_policy = SmartTeamBuildPolicy()

    @property
    def battlepolicy(self) -> PPOBattlePolicy:
        return self._battle_policy

    @property
    def selectionpolicy(self) -> CoverageSelectionPolicy:
        return self._selection_policy

    @property
    def teambuildpolicy(self) -> SmartTeamBuildPolicy:
        return self._team_build_policy

    @property
    def name(self) -> str:
        return self._name
