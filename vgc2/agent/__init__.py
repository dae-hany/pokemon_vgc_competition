from abc import abstractmethod, ABC

from vgc2.balance.meta import Meta, Roster, MoveSet
from vgc2.balance.meta.constraints import MetaConstraints
from vgc2.balance.rules.constraints import RuleConstraints
from vgc2.battle_engine import BattleCommand, BattleRuleParam
from vgc2.battle_engine.game_state import State
from vgc2.battle_engine.modifiers import Stats, Nature, Type
from vgc2.battle_engine.move import Move
from vgc2.battle_engine.team import Team
from vgc2.battle_engine.view import TeamView

SelectionCommand = list[int]  # indexes on team
TeamBuildCommand = list[tuple[int, Stats, Stats, Nature, list[int]]]  # id, evs, ivs, nature, moves
MoveSetBalanceCommand = list[tuple[int, Move]]
RosterBalanceCommand = list[tuple[int, list[Type], Stats, list[int]]]  # id, types, stats, moves


class GameplayPolicy(ABC):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        original_init = cls.__init__

        def new_init(self, *args, **kw):
            if not hasattr(self, "params") or self.params is None:
                self.params = BattleRuleParam()
            original_init(self, *args, **kw)

        cls.__init__ = new_init

    def set_params(self, params: BattleRuleParam):
        self.params = params


class BattlePolicy(GameplayPolicy, ABC):

    @abstractmethod
    def decision(self,
                 state: State,
                 opp_view: TeamView | None = None) -> list[BattleCommand]:
        pass

    def set_meta(self, meta: Meta):
        pass

    def on_new_battle(self):
        pass


class SelectionPolicy(GameplayPolicy, ABC):

    @abstractmethod
    def decision(self,
                 teams: tuple[Team, Team],
                 max_size: int) -> SelectionCommand:
        pass

    def set_meta(self, meta: Meta):
        pass


class TeamBuildPolicy(GameplayPolicy, ABC):

    @abstractmethod
    def decision(self,
                 roster: Roster,
                 meta: Meta | None,
                 max_team_size: int,
                 max_pkm_moves: int,
                 n_active: int) -> TeamBuildCommand:
        pass


class MetaBalancePolicy(ABC):

    @abstractmethod
    def decision(self,
                 move_set: MoveSet,
                 roster: Roster,
                 constraints: MetaConstraints) -> tuple[MoveSetBalanceCommand, RosterBalanceCommand]:
        pass


class RuleBalancePolicy(ABC):

    @abstractmethod
    def decision(self,
                 team_pairs: list[tuple[Team, Team]],
                 constraints: RuleConstraints) -> BattleRuleParam:
        pass
