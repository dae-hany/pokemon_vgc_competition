from abc import ABC

from vgc2.agent import BattlePolicy, SelectionPolicy, TeamBuildPolicy, MetaBalancePolicy, RuleBalancePolicy
from vgc2.battle_engine import Team, BattleRuleParam


class Competitor(ABC):

    @property
    def battlepolicy(self) -> BattlePolicy | None:
        return None

    @property
    def selectionpolicy(self) -> SelectionPolicy | None:
        return None

    @property
    def teambuildpolicy(self) -> TeamBuildPolicy | None:
        return None

    @property
    def name(self) -> str:
        return ""

    def set_params(self, params: BattleRuleParam):
        if self.battlepolicy:
            self.battlepolicy.set_params(params)
        if self.selectionpolicy:
            self.selectionpolicy.set_params(params)
        if self.teambuildpolicy:
            self.teambuildpolicy.set_params(params)


class CompetitorManager:
    __slots__ = ('competitor', 'team', 'elo')

    def __init__(self,
                 c: Competitor):
        self.competitor: Competitor = c
        self.team: Team | None = None
        self.elo = 1200

    def __str__(self):
        return self.competitor.name + " ELO " + str(self.elo) + (" Team " + str(self.team) if self.team else "")


class DesignCompetitor(ABC):

    @property
    def metabalancepolicy(self) -> MetaBalancePolicy | None:
        return None

    @property
    def rulebalancepolicy(self) -> RuleBalancePolicy | None:
        return None

    @property
    def name(self) -> str:
        return ""


class DesignCompetitorManager:
    __slots__ = ('competitor', 'score')

    def __init__(self,
                 c: DesignCompetitor):
        self.competitor: DesignCompetitor = c
        self.score = 0
