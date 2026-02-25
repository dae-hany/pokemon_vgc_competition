import copy
from random import shuffle
from typing import Callable

from vgc2.battle_engine import BattleRuleParam
from vgc2.battle_engine.security import sanitized_team_build_decision
from vgc2.competition import CompetitorManager
from vgc2.competition.match import Match
from vgc2.balance import Roster
from vgc2.net.stream import StreamClient
from vgc2.util.generator import TeamGenerator, gen_team


class MatchHandler:
    __slots__ = ('max_team_size', 'max_pkm_moves', 'n_active', 'n_battles', 'random_teams', 'gen', 'prev', 'cm',
                 'winner', 'params', 'client')

    def __init__(self,
                 max_team_size: int = 4,
                 max_pkm_moves: int = 4,
                 n_active: int = 2,
                 n_battles: int = 10,
                 gen: TeamGenerator | None = gen_team,
                 params: BattleRuleParam = BattleRuleParam(),
                 client: StreamClient | None = None):
        self.max_team_size = max_team_size
        self.max_pkm_moves = max_pkm_moves
        self.n_active = n_active
        self.n_battles = n_battles
        self.random_teams = bool(gen)
        self.gen = gen
        self.prev: tuple | None = None
        self.cm: tuple[CompetitorManager, CompetitorManager] | None = None
        self.winner: CompetitorManager | None = None
        self.params = params
        self.client = client

    def setup(self, cms):
        if len(cms) == 1:
            self.winner = cms[0]
        elif len(cms) == 2:
            self.cm = cms[0], cms[1]
        else:
            self.prev = (MatchHandler(self.max_team_size, self.max_pkm_moves, self.n_active, self.n_battles, self.gen,
                                      self.params, self.client),
                         MatchHandler(self.max_team_size, self.max_pkm_moves, self.n_active, self.n_battles, self.gen,
                                      self.params, self.client))
            self.prev[0].setup(cms[:len(cms) // 2])
            self.prev[1].setup(cms[len(cms) // 2:])

    def run(self):
        if self.winner is not None:
            return
        if self.prev:
            for mh in self.prev:
                mh.run()
                if not self.cm:
                    self.cm = (mh.winner,)
                else:
                    self.cm += (mh.winner,)
        match = Match(self.cm, self.n_active, self.n_battles, self.max_team_size, self.max_pkm_moves, self.gen,
                      self.params, client=self.client)
        match.run()
        self.winner = self.cm[match.wins[1] > match.wins[0]]


class TreeTournament:
    __slots__ = ('cms', 'roster_gen', 'max_team_size', 'max_pkm_moves', 'n_active', 'params', 'mh')

    def __init__(self,
                 roster_gen: Roster | TeamGenerator,
                 max_team_size: int = 4,
                 max_pkm_moves: int = 4,
                 n_active: int = 2,
                 n_battles: int = 10,
                 params: BattleRuleParam = BattleRuleParam(),
                 client: StreamClient | None = None):
        self.cms: list[CompetitorManager] = []
        self.roster_gen = roster_gen
        self.max_team_size = max_team_size
        self.max_pkm_moves = max_pkm_moves
        self.n_active = n_active
        self.params = params
        self.mh = MatchHandler(max_team_size, max_pkm_moves, n_active, n_battles,
                               roster_gen if isinstance(roster_gen, Callable) else None, params, client)

    def register(self,
                 cm: CompetitorManager):
        self.cms += [cm]

    def _set_rules(self):
        for cm in self.cms:
            cm.competitor.set_params(copy.deepcopy(self.params))

    def _set_teams(self):
        if isinstance(self.roster_gen, Roster):
            for cm in self.cms:
                cm.team = sanitized_team_build_decision(cm.competitor.teambuildpolicy, self.roster_gen, None,
                                                        self.max_team_size, self.max_pkm_moves, self.n_active)

    def build_tree(self):
        shuffle(self.cms)
        self.mh.setup(self.cms)

    def run(self) -> CompetitorManager:
        if isinstance(self.roster_gen, list):
            self._set_rules()
            self._set_teams()
        self.mh.run()
        return self.mh.winner
