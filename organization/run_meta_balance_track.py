import argparse
from multiprocessing.connection import Client

from vgc2.agent import BattlePolicy, SelectionPolicy, TeamBuildPolicy
from vgc2.agent.battle import GreedyBattlePolicy
from vgc2.agent.selection import RandomSelectionPolicy
from vgc2.agent.teambuild import RandomTeamBuildPolicy
from vgc2.balance.meta import MetaConstraints
from vgc2.competition import CompetitorManager, DesignCompetitorManager, Competitor
from vgc2.competition.ecosystem import Championship, Strategy, MetaDesign, label_roster
from vgc2.balance.meta import BasicMeta

from vgc2.net.client import ProxyDesignCompetitor
from vgc2.net.server import BASE_PORT
from vgc2.util.generator import gen_move_set, gen_pkm_roster


class CPUCompetitor(Competitor):

    def __init__(self, name: str = "Example"):
        self.__name = name
        self.__battle_policy = GreedyBattlePolicy()
        self.__selection_policy = RandomSelectionPolicy()
        self.__team_build_policy = RandomTeamBuildPolicy()

    @property
    def battlepolicy(self) -> BattlePolicy | None:
        return self.__battle_policy

    @property
    def selectionpolicy(self) -> SelectionPolicy | None:
        return self.__selection_policy

    @property
    def teambuildpolicy(self) -> TeamBuildPolicy | None:
        return self.__team_build_policy

    @property
    def name(self) -> str:
        return self.__name


def main(_args):
    move_set = gen_move_set(_args.n_moves)
    roster = gen_pkm_roster(_args.roster_size, move_set)
    label_roster(move_set, roster)
    meta = BasicMeta(move_set, roster)
    constraints = MetaConstraints()
    championship = Championship(roster, meta, _args.epochs, _args.n_active, _args.n_battles, _args.max_team_size,
                                _args.max_pkm_moves, Strategy.ELO_PAIRING)
    balance_design = MetaDesign(move_set, roster, constraints, championship, _args.d_epochs)
    for _ in range(_args.n_agents):
        championship.register(CompetitorManager(CPUCompetitor()))
    conn = Client(('localhost', _args.base_port), authkey='Competitor 0'.encode('utf-8'))
    dcm = DesignCompetitorManager(ProxyDesignCompetitor(conn))
    balance_design.register(dcm)
    balance_design.run()
    print(dcm.competitor.name + " got " + dcm.score + " score!")
    conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--d_epochs', type=int, default=100)
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--n_moves', type=int, default=100)
    parser.add_argument('--roster_size', type=int, default=50)
    parser.add_argument('--n_agents', type=int, default=8)
    parser.add_argument('--max_team_size', type=int, default=4)
    parser.add_argument('--n_active', type=int, default=2)
    parser.add_argument('--max_pkm_moves', type=int, default=4)
    parser.add_argument('--n_battles', type=int, default=10)
    parser.add_argument('--base_port', type=int, default=BASE_PORT)
    args = parser.parse_args()
    main(args)
