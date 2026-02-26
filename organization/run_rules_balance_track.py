import argparse
from multiprocessing.connection import Client

from vgc2.agent.battle import GreedyBattlePolicy
from vgc2.balance.rules.constraints import RuleConstraints
from vgc2.balance.rules.evaluator import evaluate_rules
from vgc2.competition import DesignCompetitorManager
from vgc2.competition.ecosystem import RuleDesign
from vgc2.competition.fixed_matches import FixedMatches
from vgc2.net.client import ProxyDesignCompetitor
from vgc2.net.server import BASE_PORT


def main(_args):
    constraints = RuleConstraints()
    agent_pair = GreedyBattlePolicy(), GreedyBattlePolicy()
    fixed_matches = FixedMatches(agent_pair, _args.n_team_pairs)
    balance_design = RuleDesign(fixed_matches, constraints, [evaluate_rules])
    conn = Client(('localhost', _args.base_port), authkey='Competitor 0'.encode('utf-8'))
    dcm = DesignCompetitorManager(ProxyDesignCompetitor(conn))
    balance_design.register(dcm)
    balance_design.run()
    print(dcm.competitor.name + " got " + dcm.score + " score!")
    conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--n_team_pairs', type=int, default=8)
    parser.add_argument('--max_team_size', type=int, default=4)
    parser.add_argument('--n_active', type=int, default=2)
    parser.add_argument('--max_pkm_moves', type=int, default=4)
    parser.add_argument('--n_battles', type=int, default=10)
    parser.add_argument('--base_port', type=int, default=BASE_PORT)
    args = parser.parse_args()
    main(args)
