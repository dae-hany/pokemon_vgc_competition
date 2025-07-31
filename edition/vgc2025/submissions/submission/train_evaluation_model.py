import pickle
from typing import Any, Dict, List

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import cross_val_score, train_test_split

from data_collection import load_data
from feature_extraction import (
    extract_features_batch,
    get_feature_dimension,
    normalize_features,
)


def train_evaluation_model(
        data: List[Dict[str, Any]], test_size: float = 0.2, random_state: int = 42
):
    """
    評価モデルを学習する

    Args:
        data: 収集したバトルデータ
        test_size: テストデータの割合
        random_state: 乱数シード

    Returns:
        model: 学習済みモデル
        normalization_params: 正規化パラメータ
        metrics: 評価メトリクス
    """
    print("Extracting features from data...")
    X, y = extract_features_batch(data)

    print(f"Feature dimension: {X.shape[1]}")
    print(f"Number of samples: {X.shape[0]}")
    print(f"Class distribution: {np.bincount(y)}")

    # 特徴量正規化
    print("Normalizing features...")
    X_normalized, normalization_params = normalize_features(X)

    # 訓練・テスト分割
    X_train, X_test, y_train, y_test = train_test_split(
        X_normalized, y, test_size=test_size, random_state=random_state, stratify=y
    )

    print(f"Training samples: {X_train.shape[0]}")
    print(f"Test samples: {X_test.shape[0]}")

    # ロジスティック回帰モデルの学習
    print("Training logistic regression model...")
    model = LogisticRegression(
        random_state=random_state,
        max_iter=1000,
        solver="liblinear",  # 小さなデータセットに適している
    )

    model.fit(X_train, y_train)

    # 予測と評価
    y_train_pred = model.predict(X_train)
    y_test_pred = model.predict(X_test)

    train_accuracy = accuracy_score(y_train, y_train_pred)
    test_accuracy = accuracy_score(y_test, y_test_pred)

    print(f"Training accuracy: {train_accuracy:.4f}")
    print(f"Test accuracy: {test_accuracy:.4f}")

    # クロスバリデーション
    print("Performing cross-validation...")
    cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring="accuracy")
    print(
        f"Cross-validation accuracy: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})"
    )

    # 詳細な評価
    print("\nTest set evaluation:")
    print(classification_report(y_test, y_test_pred))
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, y_test_pred))

    # 特徴量の重要度 (係数の絶対値)
    feature_importance = np.abs(model.coef_[0])
    top_features_idx = np.argsort(feature_importance)[-10:]  # トップ10の特徴量
    print("\nTop 10 most important features (by coefficient magnitude):")
    for i, idx in enumerate(reversed(top_features_idx)):
        print(f"{i + 1}. Feature {idx}: {feature_importance[idx]:.4f}")

    metrics = {
        "train_accuracy": train_accuracy,
        "test_accuracy": test_accuracy,
        "cv_scores": cv_scores,
        "cv_mean": cv_scores.mean(),
        "cv_std": cv_scores.std(),
        "feature_importance": feature_importance,
    }

    return model, normalization_params, metrics


def save_model(
        model,
        normalization_params: Dict[str, np.ndarray],
        metrics: Dict[str, Any],
        filename: str = "evaluation_model.pkl",
):
    """
    学習済みモデルと関連データを保存
    """
    model_data = {
        "model": model,
        "normalization_params": normalization_params,
        "metrics": metrics,
        "feature_dimension": get_feature_dimension(),
    }

    with open(filename, "wb") as f:
        pickle.dump(model_data, f)

    print(f"Model saved to {filename}")


def load_model(filename: str = "evaluation_model.pkl"):
    """
    学習済みモデルと関連データを読み込み
    """
    with open(filename, "rb") as f:
        model_data = pickle.load(f)

    # print(f"Model loaded from {filename}")
    return (
        model_data["model"],
        model_data["normalization_params"],
        model_data["metrics"],
    )


def predict_winner(
        model, normalization_params: Dict[str, np.ndarray], state
) -> tuple[int, float]:
    """
    現在のStateから勝者を予測

    Returns:
        predicted_winner: 予測された勝者 (0 or 1)
        confidence: 予測の確信度 (0.5-1.0)
    """
    from feature_extraction import apply_normalization, extract_features_from_state

    # 特徴量抽出
    features = extract_features_from_state(state).reshape(1, -1)

    # 正規化
    features_normalized = apply_normalization(features, normalization_params)

    # 予測
    prediction = model.predict(features_normalized)[0]
    probabilities = model.predict_proba(features_normalized)[0]
    confidence = max(probabilities)

    return int(prediction), float(confidence)


if __name__ == "__main__":
    # データの読み込み
    print("Loading battle data...")
    data = load_data("submission/battle_data.pkl")

    # モデルの学習
    model, normalization_params, metrics = train_evaluation_model(data)

    # モデルの保存
    save_model(model, normalization_params, metrics, "submission/evaluation_model.pkl")

    print("\nTraining completed successfully!")
