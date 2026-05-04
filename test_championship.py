"""
Championship Track local test (no network).
Tests DaehoCompetitor vs Greedy/2025 winners in Championship format.
"""
import sys
import os
import io

# Fix Unicode output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, 'my_submission')

from vgc2.agent.battle import GreedyBattlePolicy, RandomBattlePolicy
from vgc2.agent.selection import RandomSelectionPolicy
from vgc2.agent.teambuild import RandomTeamBuildPolicy
from vgc2.balance.meta import BasicMeta
from vgc2.battle_engine import BattleRuleParam
from vgc2.battle_engine.pokemon import Pokemon
from vgc2.battle_engine.team import Team
from vgc2.battle_engine.security import sanitized_team_build_decision
from vgc2.competition import CompetitorManager
from vgc2.competition.ecosystem import Championship, label_roster, build_team
from vgc2.util.generator import gen_move_set, gen_pkm_roster

from competitor import DaehoCompetitor


class SafeSelectionPolicy:
    """Wraps a selection policy with error handling fallback to first N."""
    def __init__(self, inner_policy):
        self._inner = inner_policy

    def __getattr__(self, name):
        """Proxy all other attributes to inner policy (e.g. set_meta)."""
        return getattr(self._inner, name)

    def decision(self, teams, max_size):
        try:
            result = self._inner.decision(teams, max_size)
            n_members = len(teams[0].members)
            valid = [i for i in result if 0 <= i < n_members]
            if len(valid) >= min(max_size, n_members):
                return valid[:max_size]
        except Exception:
            pass
        return list(range(min(max_size, len(teams[0].members))))


class SimpleCompetitor:
    """Minimal competitor wrapper for testing."""
    def __init__(self, name, battle_policy, selection_policy, teambuild_policy):
        self._name = name
        self._bp = battle_policy
        self._sp = selection_policy
        self._tp = teambuild_policy

    @property
    def name(self):
        return self._name

    @property
    def battlepolicy(self):
        return self._bp

    @property
    def selectionpolicy(self):
        return self._sp

    @property
    def teambuildpolicy(self):
        return self._tp


def make_greedy_competitor():
    return SimpleCompetitor(
        "Greedy",
        GreedyBattlePolicy(),
        RandomSelectionPolicy(),
        RandomTeamBuildPolicy()
    )


def load_2025_competitors():
    """Load 2025 winner competitors for championship testing."""
    competitors = []

    # JJJ
    try:
        jjj_dir = os.path.join('edition', 'vgc2025', 'submissions',
                               'JJJ - JunSung - wfd gfd')
        sys.path.insert(0, jjj_dir)
        from JJJ import JJJ_BattlePolicy, JJJ_selectionPolicy
        from JJJTeamPolicy import JJJ_TeamBuildPolicy
        competitors.append(SimpleCompetitor(
            "JJJ", JJJ_BattlePolicy(), JJJ_selectionPolicy(),
            JJJ_TeamBuildPolicy()
        ))
        print("  [OK] JJJ loaded")
        sys.path.remove(jjj_dir)
    except Exception as e:
        print(f"  [FAIL] JJJ: {e}")
        # Fallback: use JJJ battle+selection with random teambuild
        try:
            competitors.append(SimpleCompetitor(
                "JJJ", JJJ_BattlePolicy(), JJJ_selectionPolicy(),
                RandomTeamBuildPolicy()
            ))
            print("  [OK] JJJ loaded (random teambuild fallback)")
        except Exception:
            pass

    # Yamabuki/IceMonte
    try:
        ice_dir = os.path.join('edition', 'vgc2025', 'submissions',
                               'iceMonteSubmission')
        sys.path.insert(0, ice_dir)
        from iceMonteBattlePolicy import IceMonteBattlePolicy
        from iceMonteSelectionPolicy import IceMonteSelectionPolicy
        competitors.append(SimpleCompetitor(
            "Yamabuki", IceMonteBattlePolicy(),
            SafeSelectionPolicy(IceMonteSelectionPolicy()),
            RandomTeamBuildPolicy()
        ))
        print("  [OK] Yamabuki loaded")
        sys.path.remove(ice_dir)
    except Exception as e:
        print(f"  [FAIL] Yamabuki: {e}")

    # Jirachi
    try:
        jir_dir = os.path.join('edition', 'vgc2025', 'submissions',
                               'jirachi - DONGMIN KIM')
        sys.path.insert(0, jir_dir)
        from jirachi_core_policies import (AlwaysSmartBeamSearchPolicy,
                                           MaxFirepowerSelectionPolicy)
        competitors.append(SimpleCompetitor(
            "Jirachi",
            AlwaysSmartBeamSearchPolicy(time_limit_ms=90),
            SafeSelectionPolicy(MaxFirepowerSelectionPolicy()),
            RandomTeamBuildPolicy()
        ))
        print("  [OK] Jirachi loaded")
        sys.path.remove(jir_dir)
    except Exception as e:
        print(f"  [FAIL] Jirachi: {e}")

    return competitors


def run_championship(competitors, n_epochs=10, n_battles=3,
                     roster_size=50, n_moves=100):
    """Run a local championship and report ELO ratings."""
    move_set = gen_move_set(n_moves)
    roster = gen_pkm_roster(roster_size, move_set)
    label_roster(move_set, roster)
    meta = BasicMeta(move_set, roster)

    championship = Championship(
        roster, meta, n_epochs,
        n_active=2, n_battles=n_battles,
        max_team_size=4, max_pkm_moves=4
    )

    for comp in competitors:
        cm = CompetitorManager(comp)
        championship.register(cm)

    print(f"\nRunning Championship: {n_epochs} epochs, "
          f"{n_battles} battles/match, {roster_size} roster")
    print(f"Competitors: {[c.name for c in competitors]}")
    print()

    championship.run()

    ranking = championship.ranking()
    print(f"\n{'='*50}")
    print(f"  CHAMPIONSHIP RESULTS")
    print(f"{'='*50}")
    for i, cm in enumerate(ranking):
        print(f"  #{i+1}: {cm.competitor.name:15s} ELO: {cm.elo:.0f}")
    print(f"{'='*50}")

    return ranking


if __name__ == '__main__':
    print("Loading competitors...")
    my_comp = DaehoCompetitor("Daeho_AI")

    # Test 1: vs Greedy only
    print("\n--- Test 1: Daeho_AI vs Greedy ---")
    greedy = make_greedy_competitor()
    try:
        run_championship([my_comp, greedy], n_epochs=10)
    except Exception as e:
        print(f"  Test 1 failed: {e}")

    # Test 2: vs 2025 Winners (with error handling)
    print("\n--- Test 2: Daeho_AI vs 2025 Winners ---")
    print("Loading 2025 winners...")
    winners = load_2025_competitors()
    if winners:
        # Test each winner individually to isolate failures
        for winner in winners:
            try:
                print(f"\n  --- Daeho_AI vs {winner.name} ---")
                all_comp = [DaehoCompetitor("Daeho_AI"), winner]
                run_championship(all_comp, n_epochs=10, n_battles=3)
            except Exception as e:
                print(f"  Championship vs {winner.name} failed: {e}")
    else:
        print("No 2025 winners loaded, skipping.")

