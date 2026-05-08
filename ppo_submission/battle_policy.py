import os
from typing import Optional, List
import numpy as np

from stable_baselines3 import PPO

from vgc2.agent import BattlePolicy
from vgc2.battle_engine import State, BattleCommand, TeamView, BattleRuleParam
from ppo_submission.vgc_env import VgcEnv, OBS_DIM

class PPOBattlePolicy(BattlePolicy):
    """
    훈련된 PPO 모델을 불러와 실제 대회 환경(Engine)에서 Action을 추론(Inference)하는 Policy 클래스입니다.
    """
    def __init__(self, model_path: str = "vgc_ppo_model.zip"):
        super().__init__()
        # 현재 스크립트 위치 기준으로 모델 경로 절대화
        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_model_path = os.path.join(base_dir, model_path)
        
        try:
            self.model = PPO.load(full_model_path)
            self.model_loaded = True
        except Exception as e:
            print(f"Failed to load PPO model from {full_model_path}. Using fallback. Error: {e}")
            self.model = None
            self.model_loaded = False
            
        # Observation 및 Action Decoding 로직을 재사용하기 위해 
        # 상대방 없는 Dummy Env를 생성해 둡니다. (메모리상으로만 존재)
        self.dummy_env = VgcEnv(opponent_policy=None, params=BattleRuleParam())

    def set_params(self, params: BattleRuleParam):
        super().set_params(params)
        self.dummy_env.params = params

    def decision(self,
                 state: State,
                 opp_view: Optional[TeamView] = None) -> List[BattleCommand]:
        """
        엔진으로부터 현재 State를 받아 모델을 통과시킨 뒤, BattleCommand를 반환합니다.
        """
        # Fallback 1: 모델이 없거나 예기치 못한 에러
        if not self.model_loaded:
            return [(0, 0)] # 첫번째 포켓몬의 첫번째 기술 사용
            
        try:
            # 1. State를 Environment 내부 변수에 주입 (관측값 변환용)
            self.dummy_env.current_state = state
            
            # 2. VgcEnv에 구현된 완벽한 로직을 재사용하여 State -> Tensor 변환
            obs = self.dummy_env._get_obs(state)
            
            # 3. 선택 불가능한 Action Masking 처리
            # sb3-contrib MaskablePPO의 경우 action_masks 인자를 줄 수 있으나,
            # 일반 PPO인 경우 아래와 같이 휴리스틱하게 마스킹을 적용해 강제 보정 가능
            mask = self.dummy_env._get_action_mask()
            
            # 4. PPO 추론 (Inference) - 무작위성(Exploration) 제거를 위해 deterministic=True
            action, _states = self.model.predict(obs, deterministic=True)
            action = int(action)
            
            # 일반 PPO 보정: 모델이 고른 action이 불가능한 경우(mask == 0) 차선책 선택
            if mask[action] == 0.0:
                # 가능한 액션 중 임의 선택 (원래는 logits을 가져와 두번째로 높은 것을 골라야 완벽함)
                valid_actions = np.where(mask == 1.0)[0]
                if len(valid_actions) > 0:
                    action = valid_actions[0]
                else:
                    return [(0, 0)] # 마지막 Fallback
            
            # 5. 정수형 Action을 엔진이 이해하는 BattleCommand 리스트로 변환
            cmds = self.dummy_env._decode_action(action, state.sides[0])
            
            # 4v4 더블 배틀 등 다수 Action이 필요한 경우를 대비한 Padding
            # VGC 2026 Engine 구조상 Active가 여러 마리일 수 있으므로 (현재 VGC는 통상 Active 1~2)
            active_count = len(state.sides[0].team.active)
            while len(cmds) < active_count:
                cmds.append((0, 0))
                
            return cmds
            
        except Exception as e:
            # 실전 대회에서 에이전트가 크래시나는 것을 방지하기 위한 최후의 방어벽
            print(f"PPO Inference Error: {e}")
            return [(0, 0)]
