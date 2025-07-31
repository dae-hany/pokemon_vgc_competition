#!/usr/bin/env python3
"""
Battle Evaluator Tool

This tool evaluates BattlePolicy implementations by running multiple battles
and calculating win rates. It uses the same default parameters as
organization/run_battle_track.py and supports both single-process and
multiprocess execution for improved performance.
"""

import argparse
from multiprocessing import Pool, cpu_count
from typing import Tuple

from vgc2.agent import BattlePolicy
from vgc2.battle_engine import BattleEngine, State, StateView, TeamView
from vgc2.battle_engine.game_state import get_battle_teams
from vgc2.competition.match import label_teams, run_battle
from vgc2.util.generator import gen_team


# Import our custom battle policy


def get_battle_policy(policy_name: str) -> BattlePolicy:
    """
    Get a BattlePolicy instance by name.

    Args:
        policy_name: Name of the policy class

    Returns:
        BattlePolicy instance

    Raises:
        ValueError: If policy name is not recognized
    """

    # MonteCarloBattlePolicy のほかに
    # MonteCarloBattlePolicy(rollout_turns_greedy=2)
    # のような指定を雑に可能にした
    if not policy_name.endswith(")"):
        policy_name = policy_name + "()"
    return eval(policy_name)


def run_single_battle(
        policy1: BattlePolicy,
        policy2: BattlePolicy,
        team_size: int = 4,
        n_active: int = 2,
        n_moves: int = 4,
) -> int:
    """
    Run a single battle between two policies.

    Args:
        policy1: First battle policy
        policy2: Second battle policy
        team_size: Maximum team size
        n_active: Number of active Pokemon
        n_moves: Maximum moves per Pokemon

    Returns:
        Winner side (0 or 1)
    """
    # Generate teams
    team = gen_team(team_size, n_moves), gen_team(team_size, n_moves)
    label_teams(team)

    # Create team views
    team_view = TeamView(team[0]), TeamView(team[1])

    # Create battle state
    state = State(get_battle_teams(team, n_active))
    state_view = StateView(state, 0, team_view), StateView(state, 1, team_view)

    # Create battle engine
    engine = BattleEngine(state)

    # Run battle
    agents = (policy1, policy2)
    winner = run_battle(engine, agents, team_view, state_view)

    return winner


def run_battle_worker(args: Tuple[str, str, int, int, int]) -> int:
    """
    Worker function for multiprocessing battle execution.

    Args:
        args: Tuple of (policy1_name, policy2_name, team_size, n_active, n_moves)

    Returns:
        Winner side (0 or 1)
    """
    policy1_name, policy2_name, team_size, n_active, n_moves = args

    # Create policy instances
    policy1 = get_battle_policy(policy1_name)
    policy2 = get_battle_policy(policy2_name)

    # Run single battle
    return run_single_battle(policy1, policy2, team_size, n_active, n_moves)


def evaluate_policies(
        policy1_name: str,
        policy2_name: str,
        n_battles: int = 100,
        team_size: int = 4,
        n_active: int = 2,
        n_moves: int = 4,
        verbose: bool = False,
        n_processes: int = 1,
) -> Tuple[int, int, float]:
    """
    Evaluate two policies by running multiple battles.

    Args:
        policy1_name: Name of first policy
        policy2_name: Name of second policy
        n_battles: Number of battles to run
        team_size: Maximum team size
        n_active: Number of active Pokemon
        n_moves: Maximum moves per Pokemon
        verbose: Whether to print progress
        n_processes: Number of processes to use (1 for single-process)

    Returns:
        Tuple of (policy1_wins, policy2_wins, policy1_win_rate)
    """
    wins = [0, 0]

    if n_processes == 1:
        # Single-process execution
        policy1 = get_battle_policy(policy1_name)
        policy2 = get_battle_policy(policy2_name)

        for i in range(n_battles):
            if verbose and (i + 1) % 10 == 0:
                print(f"Battle {i + 1}/{n_battles}")

            winner = run_single_battle(policy1, policy2, team_size, n_active, n_moves)
            wins[winner] += 1
    else:
        # Multi-process execution
        if verbose:
            print(f"Running {n_battles} battles using {n_processes} processes...")

        # Prepare arguments for worker processes
        battle_args = [
            (policy1_name, policy2_name, team_size, n_active, n_moves)
            for _ in range(n_battles)
        ]

        # Run battles in parallel
        with Pool(processes=n_processes) as pool:
            results = pool.map(run_battle_worker, battle_args)

        # Count wins
        for winner in results:
            wins[winner] += 1

    win_rate = wins[0] / n_battles
    return wins[0], wins[1], win_rate


def main():
    """Main function to run the battle evaluator."""
    parser = argparse.ArgumentParser(
        description="Evaluate BattlePolicy implementations"
    )
    parser.add_argument("policy1", type=str, help="First policy name")
    parser.add_argument("policy2", type=str, help="Second policy name")
    parser.add_argument(
        "--n_battles",
        type=int,
        default=100,
        help="Number of battles to run (default: 100)",
    )
    parser.add_argument(
        "--max_team_size", type=int, default=4, help="Maximum team size (default: 4)"
    )
    parser.add_argument(
        "--n_active", type=int, default=2, help="Number of active Pokemon (default: 2)"
    )
    parser.add_argument(
        "--max_pkm_moves",
        type=int,
        default=4,
        help="Maximum moves per Pokemon (default: 4)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print progress during evaluation"
    )
    parser.add_argument(
        "--n_processes",
        type=int,
        default=1,
        help="Number of processes for parallel execution (default: 1)",
    )
    parser.add_argument(
        "--auto_processes",
        action="store_true",
        help="Automatically use all available CPU cores",
    )

    args = parser.parse_args()

    # Handle automatic process count
    if args.auto_processes:
        args.n_processes = cpu_count()

    try:
        print(f"Evaluating {args.policy1} vs {args.policy2}")
        print(
            f"Parameters: team_size={args.max_team_size}, n_active={args.n_active}, "
            f"max_moves={args.max_pkm_moves}, n_battles={args.n_battles}"
        )
        print(f"Processes: {args.n_processes}")
        print("-" * 60)

        wins1, wins2, win_rate = evaluate_policies(
            args.policy1,
            args.policy2,
            args.n_battles,
            args.max_team_size,
            args.n_active,
            args.max_pkm_moves,
            args.verbose,
            args.n_processes,
        )

        print("\nResults:")
        print(f"{args.policy1}: {wins1} wins ({win_rate:.2%})")
        print(f"{args.policy2}: {wins2} wins ({(1 - win_rate):.2%})")
        print(f"Total battles: {args.n_battles}")

    except ValueError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    # Required for multiprocessing on Windows and some Unix systems
    exit(main())
