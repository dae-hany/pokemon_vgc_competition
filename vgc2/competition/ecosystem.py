import time
from enum import IntEnum
from random import shuffle

from vgc2.agent import TeamBuildCommand, RosterBalanceCommand, MoveSetBalanceCommand
from vgc2.balance.meta import Roster, Meta, MoveSet
from vgc2.balance.meta.constraints import MetaConstraints
from vgc2.balance.meta.evaluator import MetaEvaluator
from vgc2.balance.rules.constraints import RuleConstraints
from vgc2.balance.rules.evaluator import RuleEvaluator
from vgc2.battle_engine import Team
from vgc2.battle_engine.pokemon import Pokemon
from vgc2.battle_engine.security import sanitized_team_build_decision
from vgc2.competition import CompetitorManager, DesignCompetitorManager
from vgc2.competition.elo import elo_rating
from vgc2.competition.fixed_matches import FixedMatches
from vgc2.competition.match import Match
from vgc2.competition.score import time_score
from vgc2.net.stream import StreamClient


class Strategy(IntEnum):
    FIXED = 0
    RANDOM_PAIRING = 1
    ELO_PAIRING = 2


STRATEGY_MAP = {
    "fixed": Strategy.FIXED,
    "random": Strategy.RANDOM_PAIRING,
    "elo": Strategy.ELO_PAIRING
}


def build_team(cmd: TeamBuildCommand,
               roster: Roster) -> Team:
    return Team([Pokemon(roster[params[0]], params[4], 100, params[1], params[2], params[3]) for params in cmd])


def label_roster(move_set: MoveSet,
                 roster: Roster):
    for i, m in enumerate(move_set):
        m.id = i
    for i, p in enumerate(roster):
        p.id = i


class Championship:
    __slots__ = ('cm', 'roster', 'meta', 'epochs', 'n_active', 'n_battles', 'max_team_size', 'max_pkm_moves',
                 'strategy', 'client')

    def __init__(self,
                 roster: Roster,
                 meta: Meta,
                 epochs: int = 100,
                 n_active: int = 2,
                 n_battles: int = 3,
                 max_team_size: int = 4,
                 max_pkm_moves: int = 4,
                 strategy: Strategy = Strategy.RANDOM_PAIRING,
                 client: StreamClient | None = None):
        self.cm: list[CompetitorManager] = []
        self.roster = roster
        self.meta = meta
        self.epochs = epochs
        self.n_active = n_active
        self.n_battles = n_battles
        self.max_team_size = max_team_size
        self.max_pkm_moves = max_pkm_moves
        self.strategy = strategy
        self.client = client

    def register(self,
                 cm: CompetitorManager):
        self.cm += [cm]

    def run(self):
        e = 0
        shuffle(self.cm)
        while e < self.epochs:
            self._build_teams()
            self._pairings()
            self._matches()
            e += 1
            print(f"\nWave {e} ELO ratings:")
            for cm in self.cm:
                print(cm.competitor.name + " ELO " + str(cm.elo))
            print()

    def _build_teams(self):
        for cm in self.cm:
            cm.team = build_team(sanitized_team_build_decision(cm.competitor.teambuildpolicy, self.roster,
                                                               self.meta, self.max_team_size, self.max_pkm_moves,
                                                               self.n_active), self.roster)

    def _pairings(self):
        match self.strategy:
            case Strategy.RANDOM_PAIRING:
                shuffle(self.cm)
            case Strategy.ELO_PAIRING:
                self.cm = sorted(self.cm, key=lambda x: -x.elo)

    def _matches(self):
        n_matches = len(self.cm) // 2
        m = 0
        while m < n_matches:
            cm = self.cm[2 * m], self.cm[2 * m + 1]
            match = Match(cm, self.n_active, self.n_battles, self.max_team_size, self.max_pkm_moves, meta=self.meta,
                          client=self.client)
            match.run()
            winner = 1 if match.wins[1] > match.wins[0] else 0
            cm[0].elo, cm[1].elo = elo_rating(cm[0].elo, cm[1].elo, winner)
            self.meta.add_match((cm[0].team, cm[1].team), winner, (cm[0].elo, cm[1].elo))
            m += 1

    def ranking(self) -> list[CompetitorManager]:
        return sorted(self.cm, key=lambda cm: -cm.elo)


def build_move_set(cmd: MoveSetBalanceCommand,
                   move_set: MoveSet):
    for c in cmd:
        c[1].id = c[0]  # assure labeling
        move_set[c[0]] = c[1]


def build_roster(cmd: RosterBalanceCommand,
                 roster: Roster,
                 move_set: MoveSet):
    for c in cmd:
        roster[c[0]].edit(c[2], c[1], [move_set[i] for i in c[3]])


class MetaDesign:

    def __init__(self,
                 move_set: MoveSet,
                 roster: Roster,
                 constraints: MetaConstraints,
                 championship: Championship,
                 balance_evaluators: list[MetaEvaluator],
                 metric_weight: float = 0.7,
                 time_weight: float = 0.3):
        self.move_set = move_set
        self.roster = roster
        self.constraints = constraints
        self.championship = championship
        self.balance_evaluators = balance_evaluators
        self.metric_weight = metric_weight
        self.time_weight = time_weight
        self.dcm: DesignCompetitorManager

    def register(self, dcm: DesignCompetitorManager):
        self.dcm = dcm

    def run(self):
        for balance_evaluator in self.balance_evaluators:
            start = time.perf_counter()
            move_set_cmd, roster_cmd = self.dcm.competitor.metabalancepolicy.decision(self.move_set, self.roster,
                                                                                      self.constraints)
            end = time.perf_counter()
            delta = end - start
            build_move_set(move_set_cmd, self.move_set)
            build_roster(roster_cmd, self.roster, self.move_set)
            self.championship.run()
            self.dcm.score += (self.metric_weight * balance_evaluator(self.championship.meta) + self.time_weight *
                               time_score(delta))


class RuleDesign:

    def __init__(self,
                 fixed_matches: FixedMatches,
                 constraints: RuleConstraints,
                 balance_evaluators: list[RuleEvaluator],
                 metric_weight: float = 0.7,
                 time_weight: float = 0.3):
        self.constraints = constraints
        self.fixed_matches = fixed_matches
        self.balance_evaluators = balance_evaluators
        self.metric_weight = metric_weight
        self.time_weight = time_weight
        self.dcm: DesignCompetitorManager

    def register(self, dcm: DesignCompetitorManager):
        self.dcm = dcm

    def run(self):
        for balance_evaluator in self.balance_evaluators:
            start = time.perf_counter()
            params = self.dcm.competitor.rulebalancepolicy.decision(self.fixed_matches.team_pairs, self.constraints)
            end = time.perf_counter()
            delta = end - start
            self.fixed_matches.set_params(params)
            self.fixed_matches.run()
            self.dcm.score += (self.metric_weight * balance_evaluator(self.fixed_matches.rollouts,
                                                                      self.fixed_matches.results) + self.time_weight *
                               time_score(delta))
