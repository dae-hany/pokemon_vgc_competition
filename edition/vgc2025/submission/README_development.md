# README for development

開発コマンドに関する説明

# 環境構築

Python 3.11を想定

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python setup.py develop
```

# tutorial動作確認

```bash
python tutorial/battle.py 
```

# コンペシステム動作確認

3つのターミナルでそれぞれ動作させる。localhostでTCP通信が行われる。

参加者0

```bash
python template/main.py --id 0
```

参加者1

```bash
python template/main.py --id 1
```

マッチシステム

```bash
python organization/run_battle_track.py
```

1分程度で勝者が決定して表示される。

```
Example 0 wins the tournament!
```

## 開発環境構築

最適化用のツールを追加する

```bash
pip install -r requirements.dev.txt
```

# 勝敗予測モデルの学習

```bash

# 1. データ収集（約10分-1時間、サンプル数による）
python submission/run_evaluation_learning.py --collect-data --n-samples 10000

# 2. モデル学習（約1-5分）
python submission/run_evaluation_learning.py --train-model

# 3. 学習済みポリシーのテスト（約1分）
python submission/run_evaluation_learning.py --test-policy
```

# Policyの評価

```bash
python submission/battle_evaluator.py GreedyBattlePolicy "MonteCarloBattlePolicy(use_evaluation_model=True)" --auto_processes
```

# Rolloutの速度評価

Rolloutの1ターン当たりの処理時間を測定する。ランダムは速いためたくさんrolloutできる、Greedyは少し遅いためrollout回数が減るというトレードオフを調整するために使用する。

```bash
python submission/benchmark_rollout.py
```

Core i7-10700Fにて

```
Random rollout
total_rollouts: 10000, total_turns: 170144, time_per_turn: 0.00024090652231975495
Greedy rollout
total_rollouts: 10000, total_turns: 82316, time_per_turn: 0.0007589436393013744
```

# ハイパラ調整

```bash
python submission/optimize_monte_carlo_params.py
```

実験の結果、Best trialは以下のようになった。

```
Params = [rollout_turns_greedy: 2, rollout_turns_random: 1, c_puct: 0.5072020847679097]
```

動かし方は以下(マルチプロセスで探索しているため、並列評価は不可)

```bash
python submission/battle_evaluator.py GreedyBattlePolicy "MonteCarloMultiProcessBattlePolicy(decision_time=0.5,rollout_turns_greedy=2,rollout_turns_random=1,c_puct=0.5)"
```
