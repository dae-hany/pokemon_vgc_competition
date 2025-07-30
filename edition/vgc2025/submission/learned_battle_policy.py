import os
from typing import Optional, List

from train_evaluation_model import load_model, predict_winner
from vgc2.agent import BattlePolicy
from vgc2.battle_engine import BattleCommand, BattleRuleParam, TeamView
from vgc2.battle_engine.game_state import State
from vgc2.util.forward import copy_state, forward


class LearnedBattlePolicy(BattlePolicy):
    """
    学習した評価関数を使用してバトル決定を行うポリシー
    各可能なアクションを試して、最も勝率の高いアクションを選択する
    """

    def __init__(self,
                 model_path: str = 'submission/evaluation_model.pkl',
                 params: BattleRuleParam = BattleRuleParam(),
                 fallback_to_greedy: bool = True):
        """
        Args:
            model_path: 学習済みモデルのパス
            params: バトルルールパラメータ
            fallback_to_greedy: モデル読み込みに失敗した場合にGreedyに切り替えるか
        """
        self.params = params
        self.fallback_to_greedy = fallback_to_greedy

        # モデルの読み込み
        try:
            if os.path.exists(model_path):
                self.model, self.normalization_params, self.metrics = load_model(model_path)
                self.model_loaded = True
                print(f"Loaded evaluation model from {model_path}")
                print(f"Model test accuracy: {self.metrics.get('test_accuracy', 'N/A'):.4f}")
            else:
                print(f"Model file not found: {model_path}")
                self.model_loaded = False
        except Exception as e:
            print(f"Failed to load model: {e}")
            self.model_loaded = False

        # フォールバック用のGreedyポリシー
        if self.fallback_to_greedy:
            from vgc2.agent.battle import GreedyBattlePolicy
            self.greedy_policy = GreedyBattlePolicy(params)
            if not self.model_loaded:
                print("Using GreedyBattlePolicy as fallback")

    def decision(self,
                 state: State,
                 opp_view: Optional[TeamView] = None) -> List[BattleCommand]:
        """
        現在の状態から最適なアクションを決定する
        """
        # モデルが読み込まれていない場合はフォールバック
        if not self.model_loaded:
            if self.fallback_to_greedy:
                return self.greedy_policy.decision(state, opp_view)
            else:
                raise RuntimeError("Evaluation model not loaded and fallback disabled")

        # 可能なアクションを生成
        possible_actions = self._get_possible_actions(state)

        if not possible_actions:
            # アクションが無い場合は何もしない（通常は起こらない）
            return [(0, 0) for _ in state.sides[0].team.active]

        best_actions = None
        best_win_prob = -1.0

        # 各アクションを評価
        for actions in possible_actions:
            try:
                # アクションを実行したらどうなるかシミュレート
                future_state = self._simulate_action(state, actions)

                if future_state is None:
                    continue

                # 学習した評価関数で勝率を予測
                predicted_winner, confidence = predict_winner(
                    self.model, self.normalization_params, future_state
                )

                # プレイヤー0の勝率を計算（predicted_winner=0なら高い確信度、=1なら低い確信度）
                win_prob = confidence if predicted_winner == 0 else (1.0 - confidence)

                if win_prob > best_win_prob:
                    best_win_prob = win_prob
                    best_actions = actions

            except Exception as e:
                # エラーが起きた場合はそのアクションをスキップ
                continue

        # 最良のアクションを返す
        if best_actions is not None:
            return best_actions
        else:
            # 全てのアクションでエラーが起きた場合はフォールバック
            if self.fallback_to_greedy:
                return self.greedy_policy.decision(state, opp_view)
            else:
                # デフォルトアクション（最初の技を使用）
                return [(0, 0) for _ in state.sides[0].team.active]

    def _get_possible_actions(self, state: State) -> List[List[BattleCommand]]:
        """
        現在の状態で可能なアクションの組み合わせを生成
        """
        my_team = state.sides[0].team
        opp_team = state.sides[1].team

        actions_per_pokemon = []

        for pokemon in my_team.active:
            if pokemon.fainted():
                # 気絶している場合は交代のみ
                switch_actions = []
                for i, reserve_pokemon in enumerate(my_team.reserve):
                    if not reserve_pokemon.fainted():
                        switch_actions.append((-1, i))
                actions_per_pokemon.append(switch_actions if switch_actions else [(0, 0)])
            else:
                # 技使用のアクション
                move_actions = []
                for i, move in enumerate(pokemon.battling_moves):
                    if move.pp > 0 and not move.disabled:
                        # 各相手ポケモンをターゲット
                        for j, target in enumerate(opp_team.active):
                            if not target.fainted():
                                move_actions.append((i, j))

                # 交代のアクション（HPが低い場合のみ考慮）
                switch_actions = []
                hp_ratio = pokemon.hp / pokemon.constants.stats[0] if pokemon.constants.stats[0] > 0 else 0
                if hp_ratio < 0.3:  # HP30%以下の場合のみ交代を考慮
                    for i, reserve_pokemon in enumerate(my_team.reserve):
                        if not reserve_pokemon.fainted():
                            switch_actions.append((-1, i))

                all_actions = move_actions + switch_actions
                actions_per_pokemon.append(all_actions if all_actions else [(0, 0)])

        # 全ての組み合わせを生成（計算量を制限）
        from itertools import product
        combinations = list(product(*actions_per_pokemon))

        # 組み合わせが多すぎる場合は制限（最大100組み合わせまで）
        if len(combinations) > 100:
            import random
            combinations = random.sample(combinations, 100)

        return combinations

    def _simulate_action(self, state: State, actions: List[BattleCommand]) -> Optional[State]:
        """
        アクションを実行した後の状態をシミュレート
        """
        try:
            # 状態をコピー
            future_state = copy_state(state)

            # ランダムな相手のアクション（簡単のため）
            opp_actions = self._get_simple_opponent_actions(future_state)

            # アクションを実行
            combined_actions = [actions, opp_actions]
            future_state = forward(future_state, combined_actions, self.params)

            return future_state

        except Exception as e:
            # シミュレーション失敗
            return None

    def _get_simple_opponent_actions(self, state: State) -> List[BattleCommand]:
        """
        相手の簡単なアクション（ランダムな技使用）を生成
        """
        opp_team = state.sides[1].team
        actions = []

        for pokemon in opp_team.active:
            if pokemon.fainted():
                # 気絶している場合は交代
                for i, reserve_pokemon in enumerate(opp_team.reserve):
                    if not reserve_pokemon.fainted():
                        actions.append((-1, i))
                        break
                else:
                    actions.append((0, 0))  # デフォルト
            else:
                # 使用可能な技からランダム選択
                available_moves = []
                for i, move in enumerate(pokemon.battling_moves):
                    if move.pp > 0 and not move.disabled:
                        available_moves.append(i)

                if available_moves:
                    import random
                    move_idx = random.choice(available_moves)
                    target_idx = 0  # 簡単のため最初のターゲット
                    actions.append((move_idx, target_idx))
                else:
                    actions.append((0, 0))  # デフォルト

        return actions
