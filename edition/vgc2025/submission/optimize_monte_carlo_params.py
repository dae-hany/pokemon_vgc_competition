"""
Optunaを用いて、モンテカルロのハイパラ調整をする
"""

import optuna

from battle_evaluator import evaluate_policies


def objective(trial: optuna.Trial):
    rollout_turns_greedy = trial.suggest_int("rollout_turns_greedy", 1, 5)
    rollout_turns_random = trial.suggest_int("rollout_turns_random", 0, 20)
    c_puct = trial.suggest_float("c_puct", 0.1, 10.0)
    policy1 = f"MonteCarloMultiProcessBattlePolicy(decision_time=0.5,rollout_turns_greedy={rollout_turns_greedy},rollout_turns_random={rollout_turns_random},c_puct={c_puct})"
    _, _, winrate = evaluate_policies(
        policy1, "GreedyBattlePolicy()", verbose=False, n_processes=1
    )
    print(policy1, winrate)
    return winrate


study = optuna.create_study(
    storage="sqlite:///submission/optuna.sqlite3",  # Specify the storage URL here.
    study_name="monte_carlo_multi_process_battle_policy",
    direction="maximize",
)
study.optimize(objective, n_trials=100)
print(f"Best value: {study.best_value} (params: {study.best_params})")
