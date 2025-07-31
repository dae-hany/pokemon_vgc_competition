# Submission files by Masatoshi Hidaka for VGC AI Competition 3rd Edition (2025)

AI name: "Yamabuki"

This code only supports Battle Track.

# How to run

```bash
python main.py --id 0
```

# Files

Files directly used for the battle are described. Other files are for development.

- `main.py`: entry point for server.
- `competitor.py`: instantiates policy classes.
- `monte_carlo_multi_process_battle_policy.py`: core battle policy using Monte Carlo based algorithm.
- `fast_damage_calculator.py`: slightly accelerated version of damage calculator.
- `numpy_inference.py`: winning rate predictor for battle state.
- `evaluation_model_numpy.pkl`: model file for winning rate predictor.

# Algorithm of Battle Policy

It employs a Monte Carlo based algorithm.
It is solved as a multi-armed bandit problem for a given phase.
In each trial, one of the legal moves is chosen, determinization is performed, and the opponent's move is assumed to be
Greedy, and one turn is proceeded.
Then, one more turn is carried out in Greedy move. Next, the game proceeds for two turns in Random move. The features (
HP, abnormalities, etc.) are extracted from the state of the game at that point, and the win rate is estimated.
The most effective move (the move with the largest number of visits) is selected after many trials within the time
limit.

Because Greedy is relatively computationally heavy, the damage calculation portion, which requires a large number of
calls, has been sped up slightly. However, it remains a bottleneck in the Pure Python implementation. Multi-processing
allows multiple moves to be evaluated in parallel.

This method achieves about 65% winning rate to the baseline Greedy Battle Policy.

Details of the methodology will be posted on the blog after the results are published. https://select766.hatenablog.com/

## Original Japanese text

モンテカルロ法ベースのアルゴリズムを採用しています。
与えられた局面に対する多腕バンディット問題として解いています。
各試行で合法手の1つを選び、決定化(determinization)を行い相手の行動はGreedyと仮定して1ターン進めます。
さらにGreedyで1ターン進めます。次にRandomで2ターン進めます。その時点の状態から特徴量(HP・状態異常等)を抽出し、勝率を推定します。
制限時間内で多数の試行を行い、最も有効な手（訪問回数最大の手）を選択します。

Greedyは計算が比較的重いため、呼び出し回数が多いダメージ計算部分を若干高速化しました。しかし、Pure
Pythonの範囲ではボトルネックとして残っています。マルチプロセスにより複数の手の評価を並列に行います。

この手法は、ベースラインのGreedy Battle Policyに対して約65%の勝率を達成しました。

手法の詳細は、結果発表後にブログに掲載予定です。 https://select766.hatenablog.com/
