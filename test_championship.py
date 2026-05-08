"""
Championship Track local test (no network).
Tests DaehoCompetitor vs Greedy/2025 winners in Championship format.
"""
import sys
import os
import io
import argparse

# Fix Unicode output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

parser = argparse.ArgumentParser()
parser.add_argument('--ppo', action='store_true', help='Use PPOCompetitor')
args, _ = parser.parse_known_args()

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

if args.ppo:
    from ppo_submission.competitor import PPOCompetitor as DaehoCompetitor
else:
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
    comp_name = "PPO_AI" if args.ppo else "Daeho_AI"
    my_comp = DaehoCompetitor(comp_name)

    final_summary = []

    # Test 1: vs Greedy only
    print(f"\n--- Test 1: {comp_name} vs Greedy ---")
    greedy = make_greedy_competitor()
    try:
        ranking = run_championship([my_comp, greedy], n_epochs=10)
        final_summary.append(("Greedy", ranking))
    except Exception as e:
        print(f"  Test 1 failed: {e}")

    # Test 2: vs 2025 Winners (with error handling)
    print(f"\n--- Test 2: {comp_name} vs 2025 Winners ---")
    print("Loading 2025 winners...")
    winners = load_2025_competitors()
    if winners:
        # Test each winner individually to isolate failures
        for winner in winners:
            try:
                print(f"\n  --- {comp_name} vs {winner.name} ---")
                all_comp = [DaehoCompetitor(comp_name), winner]
                ranking = run_championship(all_comp, n_epochs=10, n_battles=3)
                final_summary.append((winner.name, ranking))
            except Exception as e:
                print(f"  Championship vs {winner.name} failed: {e}")
    else:
        print("No 2025 winners loaded, skipping.")

    # ---------------------------------------------------------
    # Print Final Summary Table
    # ---------------------------------------------------------
    print("\n\n" + "="*75)
    print(f" 🏆 FINAL CHAMPIONSHIP SUMMARY : {comp_name} 🏆 ")
    print("="*75)
    print(f" {'Opponent':<15} | {'Winner':<15} | {'My ELO':<10} | {'Opp ELO':<10} | {'Diff':<10}")
    print("-" * 75)
    for opp_name, ranking in final_summary:
        my_elo = 0
        opp_elo = 0
        winner_name = ranking[0].competitor.name
        for cm in ranking:
            if cm.competitor.name == comp_name:
                my_elo = cm.elo
            else:
                opp_elo = cm.elo
        
        diff = my_elo - opp_elo
        diff_str = f"+{diff:.0f}" if diff > 0 else f"{diff:.0f}"
        
        if my_elo > opp_elo:
            winner_disp = f"✅ {winner_name}"
            diff_disp = f"{diff_str} 🔼"
        elif my_elo < opp_elo:
            winner_disp = f"❌ {winner_name}"
            diff_disp = f"{diff_str} 🔽"
        else:
            winner_disp = f"➖ Draw"
            diff_disp = f"{diff_str} ➖"
            
        print(f" {opp_name:<15} | {winner_disp:<15} | {my_elo:<10.0f} | {opp_elo:<10.0f} | {diff_disp:<10}")
    print("="*75 + "\n")

