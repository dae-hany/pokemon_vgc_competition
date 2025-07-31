import pickle
import random
from copy import deepcopy
from typing import Any, Dict, List

from vgc2.agent.battle import GreedyBattlePolicy, RandomBattlePolicy
from vgc2.battle_engine import BattleEngine, State, StateView, TeamView
from vgc2.battle_engine.game_state import get_battle_teams
from vgc2.competition.match import label_teams
from vgc2.util.generator import gen_team


def collect_battle_data(n_samples: int = 10000) -> List[Dict[str, Any]]:
    """
    バトルデータを収集する

    Returns:
        各サンプルには以下が含まれる:
        - team0, team1: 対戦チーム
        - state: RandomBattlePolicyで進めた後のState
        - winner: GreedyBattlePolicyで続行した勝者 (0 or 1)
        - random_turns: ランダムに進めたターン数
        - total_turns: 全体のターン数
    """
    data = []

    for i in range(n_samples):
        if i % 1000 == 0:
            print(f"Progress: {i}/{n_samples}")

        # ランダムパーティ生成
        n_active = 2
        team_size = 4
        n_moves = 4
        team = gen_team(team_size, n_moves), gen_team(team_size, n_moves)
        label_teams(team)

        # バトル初期化
        team_view = TeamView(team[0]), TeamView(team[1])
        state = State(get_battle_teams(team, n_active))
        state_view = StateView(state, 0, team_view), StateView(state, 1, team_view)
        engine = BattleEngine(state)

        # ランダムターン数決定 (0-20)
        random_turns = random.randint(0, 20)

        # RandomBattlePolicyでランダムターン進める
        random_agent = RandomBattlePolicy(), RandomBattlePolicy()

        for turn in range(random_turns):
            if engine.finished():
                break

            # 各プレイヤーのアクションを取得
            actions = []
            for player_id in range(2):
                action = random_agent[player_id].decision(
                    state_view[player_id], team_view[1 - player_id]
                )
                actions.append(action)

            # ターンを進める
            engine.run_turn(actions)

        # この時点のStateを保存対象とする
        if engine.finished():
            # 既に終了している場合はスキップ
            continue

        mid_state = deepcopy(engine.state)

        # GreedyBattlePolicyで終了まで進める
        greedy_agent = GreedyBattlePolicy(), GreedyBattlePolicy()

        total_turns = random_turns
        while not engine.finished():
            actions = []
            for player_id in range(2):
                action = greedy_agent[player_id].decision(
                    state_view[player_id], team_view[1 - player_id]
                )
                actions.append(action)

            engine.run_turn(actions)
            total_turns += 1

        # 勝者を決定
        winner = engine.winning_side

        # データを保存
        sample = {
            "team0": team[0],
            "team1": team[1],
            "state": mid_state,
            "winner": winner,
            "random_turns": random_turns,
            "total_turns": total_turns,
        }
        data.append(sample)

    return data


def save_data(data: List[Dict[str, Any]], filename: str = "battle_data.pkl"):
    """データをファイルに保存"""
    with open(filename, "wb") as f:
        pickle.dump(data, f)
    print(f"Data saved to {filename}")


def load_data(filename: str = "battle_data.pkl") -> List[Dict[str, Any]]:
    """データをファイルから読み込み"""
    with open(filename, "rb") as f:
        data = pickle.load(f)
    print(f"Data loaded from {filename}")
    return data


if __name__ == "__main__":
    print("Starting data collection...")
    data = collect_battle_data(n_samples=10000)
    save_data(data, "submission/battle_data.pkl")
    print(f"Collected {len(data)} samples")
