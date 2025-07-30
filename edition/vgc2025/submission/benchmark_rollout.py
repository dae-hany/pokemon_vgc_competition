"""
rolloutの速度計測
GreedyとRandomの配分を決めるために使用
"""

import time

from monte_carlo_battle_policy import MonteCarloBattlePolicy
from vgc2.battle_engine import State, TeamView
from vgc2.battle_engine.game_state import get_battle_teams
from vgc2.competition.match import label_teams
from vgc2.util.generator import gen_team


def rollout_in_one_team(
        policy: MonteCarloBattlePolicy,
        n_rollouts=100,
        team_size: int = 4,
        n_active: int = 2,
        n_moves: int = 4,
):
    # Generate teams
    team = gen_team(team_size, n_moves), gen_team(team_size, n_moves)
    label_teams(team)

    # Create team views
    team_view = TeamView(team[0]), TeamView(team[1])

    # Create battle state
    state = State(get_battle_teams(team, n_active))
    total_turns = policy._benchmark_rollout(n_rollouts, state, team_view[1])

    return total_turns


def rollout_multiple_team(policy: MonteCarloBattlePolicy, n_trial=100, n_rollouts=100):
    time_start = time.time()
    total_turns = 0
    for _ in range(n_trial):
        total_turns += rollout_in_one_team(policy, n_rollouts)
    time_end = time.time()
    time_per_turn = (time_end - time_start) / total_turns
    print(
        f"total_rollouts: {n_trial * n_rollouts}, total_turns: {total_turns}, time_per_turn: {time_per_turn}"
    )


def main():
    print("Random rollout")
    # 評価関数は使わず対戦終了までrolloutする想定
    rollout_multiple_team(
        policy=MonteCarloBattlePolicy(rollout_turns_greedy=0, rollout_turns_random=100)
    )
    print("Greedy rollout")
    rollout_multiple_team(
        policy=MonteCarloBattlePolicy(rollout_turns_greedy=100, rollout_turns_random=0)
    )


if __name__ == "__main__":
    main()
