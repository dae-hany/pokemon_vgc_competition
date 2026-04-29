"""
Quick local test: Daeho_AI vs Random/Greedy agent.
Runs a simple battle without network communication.
"""
import sys
import time

sys.path.insert(0, 'my_submission')

from vgc2.agent.battle import RandomBattlePolicy, GreedyBattlePolicy
from vgc2.agent.selection import RandomSelectionPolicy
from vgc2.agent.teambuild import RandomTeamBuildPolicy
from vgc2.competition import CompetitorManager, Competitor
from vgc2.competition.tournament import TreeTournament
from vgc2.util.generator import gen_team

from competitor import DaehoCompetitor


class RandomCompetitor(Competitor):
    def __init__(self, name="Random"):
        self._name = name
        self._bp = RandomBattlePolicy()
        self._sp = RandomSelectionPolicy()
        self._tbp = RandomTeamBuildPolicy()

    @property
    def battlepolicy(self):
        return self._bp

    @property
    def selectionpolicy(self):
        return self._sp

    @property
    def teambuildpolicy(self):
        return self._tbp

    @property
    def name(self):
        return self._name


class GreedyCompetitor(Competitor):
    def __init__(self, name="Greedy"):
        self._name = name
        self._bp = GreedyBattlePolicy()
        self._sp = RandomSelectionPolicy()
        self._tbp = RandomTeamBuildPolicy()

    @property
    def battlepolicy(self):
        return self._bp

    @property
    def selectionpolicy(self):
        return self._sp

    @property
    def teambuildpolicy(self):
        return self._tbp

    @property
    def name(self):
        return self._name


def run_tournament(competitor_classes, n_battles=10):
    """Run a battle track tournament."""
    tournament = TreeTournament(gen_team, max_team_size=4, max_pkm_moves=4, n_active=2, n_battles=n_battles)
    for cls in competitor_classes:
        tournament.register(CompetitorManager(cls))
    tournament.build_tree()
    winner = tournament.run()
    return winner


if __name__ == '__main__':
    print("=" * 60)
    print("  VGC AI Local Test: Daeho_AI vs Random vs Greedy")
    print("=" * 60)

    competitors = [
        DaehoCompetitor("Daeho_AI"),
        RandomCompetitor("Random"),
        GreedyCompetitor("Greedy"),
    ]

    n_battles = 10
    print(f"\nRunning Battle Track Tournament ({n_battles} battles per match)...")
    start = time.time()

    winner = run_tournament(competitors, n_battles)

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"  Winner: {winner.competitor.name}")
    print(f"  Time: {elapsed:.1f}s")
    print(f"{'=' * 60}")
