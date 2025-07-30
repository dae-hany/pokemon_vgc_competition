from typing import Any, Dict, List

import numpy as np

from vgc2.battle_engine import State
from vgc2.battle_engine.modifiers import Stat


def extract_features_from_state(state: State) -> np.ndarray:
    """
    Stateから特徴量ベクトルを抽出する

    特徴量:
    - 各ポケモンのHP率 (アクティブ + リザーブ)
    - 各ポケモンのステータス異常
    - 各ポケモンの能力値変化
    - 天候・フィールド効果
    - サイドコンディション
    """
    features = []

    # 各サイドについて特徴量を抽出
    for side_idx in range(2):
        side = state.sides[side_idx]
        team = side.team

        # アクティブポケモンの特徴量（固定で2匹分）
        for i in range(2):
            if i < len(team.active):
                pokemon = team.active[i]
                # HP率
                hp_ratio = (
                    pokemon.hp / pokemon.constants.stats[Stat.MAX_HP]
                    if pokemon.constants.stats[Stat.MAX_HP] > 0
                    else 0.0
                )
                features.append(hp_ratio)

                # ステータス異常 (one-hot)
                status_features = [
                                      0.0
                                  ] * 7  # NONE, BURN, FREEZE, PARALYSIS, POISON, BADLY_POISON, SLEEP
                if pokemon.status.value < len(status_features):
                    status_features[pokemon.status.value] = 1.0
                features.extend(status_features)

                # 能力値変化 (7つのステータス: attack, defense, sp_attack, sp_defense, speed, accuracy, evasion)
                features.extend(pokemon.boosts[1:])  # index 0は未使用

                # プロテクト状態
                features.append(1.0 if pokemon.protect else 0.0)

                # 気絶状態
                features.append(1.0 if pokemon.fainted() else 0.0)
            else:
                # ポケモンが存在しない場合はゼロで埋める
                features.extend(
                    [0.0] * 17
                )  # HP + status7 + boosts7 + protect + fainted

        # リザーブポケモンの特徴量（最大4匹分で固定）
        for i in range(4):
            if i < len(team.reserve):
                pokemon = team.reserve[i]
                # HP率
                hp_ratio = (
                    pokemon.hp / pokemon.constants.stats[Stat.MAX_HP]
                    if pokemon.constants.stats[Stat.MAX_HP] > 0
                    else 0.0
                )
                features.append(hp_ratio)

                # ステータス異常 (one-hot)
                status_features = [
                                      0.0
                                  ] * 7  # NONE, BURN, FREEZE, PARALYSIS, POISON, BADLY_POISON, SLEEP
                if pokemon.status.value < len(status_features):
                    status_features[pokemon.status.value] = 1.0
                features.extend(status_features)

                # 気絶状態
                features.append(1.0 if pokemon.fainted() else 0.0)
            else:
                # ポケモンが存在しない場合はゼロで埋める
                features.extend([0.0] * 9)  # HP + status7 + fainted

        # サイドコンディション
        conditions = side.conditions
        features.append(1.0 if conditions.reflect else 0.0)
        features.append(1.0 if conditions.lightscreen else 0.0)
        features.append(1.0 if conditions.tailwind else 0.0)
        features.append(1.0 if conditions.stealth_rock else 0.0)
        features.append(1.0 if conditions.poison_spikes else 0.0)

    # グローバル効果
    # 天候 (one-hot)
    weather_features = [
                           0.0
                       ] * 8  # CLEAR, SUN, RAIN, SANDSTORM, HAIL, HARSH_SUN, HEAVY_RAIN, STRONG_WINDS
    if state.weather.value < len(weather_features):
        weather_features[state.weather.value] = 1.0
    features.extend(weather_features)

    # フィールド効果 (one-hot)
    terrain_features = [0.0] * 5  # NONE, ELECTRIC, GRASSY, MISTY, PSYCHIC
    if state.field.value < len(terrain_features):
        terrain_features[state.field.value] = 1.0
    features.extend(terrain_features)

    # トリックルーム
    features.append(1.0 if state.trickroom else 0.0)

    return np.array(features, dtype=np.float32)


def get_feature_dimension() -> int:
    """特徴量ベクトルの次元数を返す"""
    # 各サイド:
    # - アクティブ2匹 * (HP + status_onehot7 + boosts7 + protect + fainted) = 2 * 17 = 34
    # - リザーブ4匹 * (HP + status_onehot7 + fainted) = 4 * 9 = 36
    # - サイドコンディション5 = 5
    # サイド合計: 34 + 36 + 5 = 75
    # 両サイド: 75 * 2 = 150
    # グローバル: weather_onehot8 + terrain_onehot5 + trickroom = 8 + 5 + 1 = 14
    # 合計: 150 + 14 = 164
    return 164


def extract_features_batch(data: List[Dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    """
    バッチデータから特徴量とラベルを抽出

    Returns:
        X: 特徴量行列 (n_samples, n_features)
        y: ラベルベクトル (n_samples,) - 勝者を表す (0 or 1)
    """
    X = []
    y = []

    for i, sample in enumerate(data):
        try:
            state = sample["state"]
            winner = sample["winner"]

            features = extract_features_from_state(state)

            # 次元数チェック
            if len(features) != get_feature_dimension():
                print(
                    f"Warning: Sample {i} has {len(features)} dimensions, expected {get_feature_dimension()}"
                )
                # 不足している場合はゼロパディング
                if len(features) < get_feature_dimension():
                    padding = [0.0] * (get_feature_dimension() - len(features))
                    features = np.concatenate([features, padding])
                # 多すぎる場合は切り捨て
                elif len(features) > get_feature_dimension():
                    features = features[: get_feature_dimension()]

            X.append(features)
            y.append(winner)
        except Exception as e:
            print(f"Error processing sample {i}: {e}")
            continue

    return np.array(X), np.array(y)


def normalize_features(X: np.ndarray) -> tuple[np.ndarray, Dict[str, np.ndarray]]:
    """
    特徴量を正規化する

    Returns:
        X_normalized: 正規化された特徴量
        normalization_params: 正規化パラメータ (mean, std)
    """
    mean = np.mean(X, axis=0)
    std = np.std(X, axis=0)

    # 標準偏差が0の特徴量を処理
    std = np.where(std == 0, 1, std)

    X_normalized = (X - mean) / std

    normalization_params = {"mean": mean, "std": std}

    return X_normalized, normalization_params


def apply_normalization(
        X: np.ndarray, normalization_params: Dict[str, np.ndarray]
) -> np.ndarray:
    """
    保存された正規化パラメータを適用する
    """
    mean = normalization_params["mean"]
    std = normalization_params["std"]
    return (X - mean) / std
