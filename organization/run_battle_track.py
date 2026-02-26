import argparse
from multiprocessing.connection import Client

from vgc2.battle_engine import BattleRuleParam
from vgc2.competition import CompetitorManager
from vgc2.competition.tournament import TreeTournament
from vgc2.net.client import ProxyCompetitor
from vgc2.net.server import BASE_PORT
from vgc2.net.stream import CLIENT_MAP
from vgc2.util.generator import gen_team, gen_rule_set


def main(_args):
    conns = []
    params = gen_rule_set(_args.n_attr_changes, _args.n_type_changes) if _args.random_rules else BattleRuleParam()
    params.print_delta()
    tournament = TreeTournament(gen_team, _args.max_team_size, _args.max_pkm_moves, args.n_active, args.n_battles,
                                params, CLIENT_MAP[_args.stream]())
    for i in range(_args.n_agents):
        address = ('localhost', _args.base_port + i)
        conn = Client(address, authkey=f'Competitor {i}'.encode('utf-8'))
        conns.append(conn)
        tournament.register(CompetitorManager(ProxyCompetitor(conn)))
    tournament.build_tree()
    winner = tournament.run()
    print(winner.competitor.name + " wins the tournament!")
    for conn in conns:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--n_agents', type=int, default=2)
    parser.add_argument('--max_team_size', type=int, default=4)
    parser.add_argument('--n_active', type=int, default=2)
    parser.add_argument('--max_pkm_moves', type=int, default=4)
    parser.add_argument('--n_battles', type=int, default=10)
    parser.add_argument('--random_rules', action="store_true")
    parser.add_argument('--base_port', type=int, default=BASE_PORT)
    parser.add_argument('--n_attr_changes', type=int, default=3)
    parser.add_argument('--n_type_changes', type=int, default=5)
    parser.add_argument("--stream", choices=CLIENT_MAP.keys(), default="file")
    args = parser.parse_args()
    main(args)
