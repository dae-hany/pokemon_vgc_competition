#!/usr/bin/env python3
"""
評価関数の学習と評価を実行するメインスクリプト

使用方法:
1. データ収集: python run_evaluation_learning.py --collect-data --n-samples 10000
2. モデル学習: python run_evaluation_learning.py --train-model
3. モデルテスト: python run_evaluation_learning.py --test-policy
4. 全て実行: python run_evaluation_learning.py --all
"""

import argparse
import os
import sys


def collect_data(n_samples: int = 10000):
    """データ収集を実行"""
    print(f"Starting data collection with {n_samples} samples...")

    from data_collection import collect_battle_data, save_data

    data = collect_battle_data(n_samples)
    save_data(data, "submission/battle_data.pkl")

    print(f"Data collection completed. Collected {len(data)} samples.")


def train_model():
    """モデル学習を実行"""
    print("Starting model training...")

    from data_collection import load_data
    from train_evaluation_model import save_model, train_evaluation_model

    # データの読み込み
    data = load_data("submission/battle_data.pkl")
    print(f"Loaded {len(data)} samples for training")

    # モデル学習
    model, normalization_params, metrics = train_evaluation_model(data)

    # モデル保存
    save_model(model, normalization_params, metrics, "submission/evaluation_model.pkl")

    print("Model training completed!")


def test_policy():
    """学習したポリシーをテスト"""
    print("Testing learned battle policy...")

    from learned_battle_policy import LearnedBattlePolicy

    from vgc2.agent.battle import GreedyBattlePolicy
    from vgc2.battle_engine import BattleEngine, State, StateView, TeamView
    from vgc2.battle_engine.game_state import get_battle_teams
    from vgc2.competition.match import label_teams, run_battle
    from vgc2.util.generator import gen_team

    # テストバトルの設定
    n_active = 2
    team_size = 4
    n_moves = 4
    n_test_battles = 100

    learned_policy = LearnedBattlePolicy()
    greedy_policy = GreedyBattlePolicy()

    learned_wins = 0

    print(f"Running {n_test_battles} test battles...")

    for i in range(n_test_battles):
        # ランダムチーム生成
        team = gen_team(team_size, n_moves), gen_team(team_size, n_moves)
        label_teams(team)
        team_view = TeamView(team[0]), TeamView(team[1])
        state = State(get_battle_teams(team, n_active))
        state_view = StateView(state, 0, team_view), StateView(state, 1, team_view)
        engine = BattleEngine(state)

        # LearnedPolicy vs GreedyPolicy
        agents = (learned_policy, greedy_policy)

        try:
            winner = run_battle(engine, agents, team_view, state_view)
            if winner == 0:  # LearnedPolicyが勝利
                learned_wins += 1
            print(f"Battle {i + 1}: {'Learned' if winner == 0 else 'Greedy'} wins")
        except Exception as e:
            print(f"Battle {i + 1} failed: {e}")

    win_rate = learned_wins / n_test_battles
    print("\nTest Results:")
    print(f"Learned Policy wins: {learned_wins}/{n_test_battles}")
    print(f"Win rate: {win_rate:.2%}")

    if win_rate > 0.5:
        print("✅ Learned policy performs better than greedy!")
    else:
        print("❌ Learned policy needs improvement.")


def main():
    parser = argparse.ArgumentParser(description="Evaluation function learning system")
    parser.add_argument(
        "--collect-data", action="store_true", help="Collect battle data"
    )
    parser.add_argument(
        "--n-samples", type=int, default=10000, help="Number of samples to collect"
    )
    parser.add_argument(
        "--train-model", action="store_true", help="Train evaluation model"
    )
    parser.add_argument(
        "--test-policy", action="store_true", help="Test learned policy"
    )
    parser.add_argument("--all", action="store_true", help="Run all steps")

    args = parser.parse_args()

    if not any([args.collect_data, args.train_model, args.test_policy, args.all]):
        parser.print_help()
        return

    # submissionディレクトリを作成
    os.makedirs("submission", exist_ok=True)

    try:
        if args.all or args.collect_data:
            collect_data(args.n_samples)

        if args.all or args.train_model:
            train_model()

        if args.all or args.test_policy:
            test_policy()

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    print("\nAll tasks completed successfully! 🎉")


if __name__ == "__main__":
    main()
