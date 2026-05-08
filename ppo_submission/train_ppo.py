import os
import random
import numpy as np
from typing import List, Callable

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv

# VGC Engine Imports
from vgc2.util.generator import gen_move_set, gen_pkm_roster
from vgc2.competition.ecosystem import label_roster
from vgc2.agent import BattlePolicy
from vgc2.agent.battle import GreedyBattlePolicy, RandomBattlePolicy
# my_submission 의 Policy 임포트
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from my_submission.battle_policy import EnhancedBattlePolicy
from vgc2.battle_engine import BattleRuleParam

# 방금 작성한 환경
from ppo_submission.vgc_env import VgcEnv

class CurriculumManager:
    """
    학습 진척도에 따라 PPO 에이전트의 상대방(Opponent) 풀을 관리하고 점진적으로 난이도를 올립니다.
    """
    def __init__(self):
        self.phase = 1
        # 다양한 난이도의 봇 인스턴스 생성
        self.bots = {
            "random": RandomBattlePolicy(),
            "greedy": GreedyBattlePolicy(),
            "my_enhanced": EnhancedBattlePolicy(),
            # "yamabuki": Yamabuki(), # TODO: 필요시 과거 수상작 임포트
        }
        
    def sample_opponent(self, current_timestep: int, max_timesteps: int) -> BattlePolicy:
        """
        현재 타임스텝에 비례하여 상대방을 확률적으로 샘플링합니다.
        초기엔 Random/Greedy, 후반엔 my_enhanced 비중이 늘어납니다.
        """
        progress = current_timestep / max_timesteps
        
        if progress < 0.2:
            self.phase = 1
            # Phase 1: 50% Random, 50% Greedy
            choices = ["random", "greedy"]
            probs = [0.5, 0.5]
        elif progress < 0.6:
            self.phase = 2
            # Phase 2: 20% Random, 50% Greedy, 30% Enhanced
            choices = ["random", "greedy", "my_enhanced"]
            probs = [0.2, 0.5, 0.3]
        else:
            self.phase = 3
            # Phase 3 (League): 10% Greedy, 90% Enhanced 
            # (차후 Self-Play 모델 추가 위치)
            choices = ["greedy", "my_enhanced"]
            probs = [0.1, 0.9]
            
        chosen = np.random.choice(choices, p=probs)
        return self.bots[chosen]

class OpponentUpdateCallback(BaseCallback):
    """
    일정 스텝마다 환경(Env) 내부의 상대방 Policy를 CurriculumManager를 통해 업데이트하는 콜백입니다.
    """
    def __init__(self, envs, manager: CurriculumManager, total_timesteps: int, verbose=0):
        super().__init__(verbose)
        self.envs = envs
        self.manager = manager
        self.total_timesteps = total_timesteps

    def _on_step(self) -> bool:
        # 매 10,000 스텝마다 혹은 에피소드 종료 시 상대를 바꿀 수 있지만, 
        # Vectorized Env 환경에서는 강제로 일괄 변경하는 방식을 사용.
        if self.num_timesteps % 10000 == 0:
            new_policy = self.manager.sample_opponent(self.num_timesteps, self.total_timesteps)
            # 모든 병렬 환경의 opponent를 업데이트
            for i in range(self.envs.num_envs):
                self.envs.env_method('set_opponent', new_policy, indices=[i])
            
            if self.verbose > 0:
                print(f"[Curriculum] Step {self.num_timesteps}: Switched opponents to {type(new_policy).__name__} (Phase {self.manager.phase})")
        return True

def make_env(manager: CurriculumManager, total_timesteps: int, roster: list):
    """DummyVecEnv를 위한 환경 팩토리 함수"""
    def _init():
        initial_opp = manager.sample_opponent(0, total_timesteps)
        env = VgcEnv(opponent_policy=initial_opp, params=BattleRuleParam())
        env.roster = roster # 로스터 주입
        return env
    return _init

def train():
    TOTAL_TIMESTEPS = 1_000_000
    
    # 훈련용 로스터 생성 (100가지 Moveset, 50마리 포켓몬 조합)
    print("Generating Training Roster...")
    move_set = gen_move_set(100)
    roster = gen_pkm_roster(50, move_set)
    label_roster(move_set, roster)
    
    manager = CurriculumManager()
    
    # Windows 환경의 Multiprocessing(Pickling) 에러를 원천 차단하기 위해 
    # SubprocVecEnv 대신 단일 프로세스 병렬 래퍼인 DummyVecEnv를 사용합니다.
    vec_env = DummyVecEnv([make_env(manager, TOTAL_TIMESTEPS, roster) for _ in range(4)])
    
    callback = OpponentUpdateCallback(vec_env, manager, TOTAL_TIMESTEPS, verbose=1)
    
    print("Initializing PPO Model...")
    # NOTE: 원래 Action Masking을 위해서는 sb3_contrib.MaskablePPO 가 필요합니다.
    # 현재 환경은 일반 PPO를 사용하며, Invalid Action이 선택되면 무시하고 Fallback 액션(Struggle 등)을
    # 환경 내부에서 처리하는 방식으로 우회 구현할 수 있습니다. 완벽함을 위해선 MaskablePPO 권장.
    model = PPO(
        "MlpPolicy",
        vec_env,
        verbose=1,
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=256,
        n_epochs=10,
        gamma=0.99,            # PBRS와 시너지를 위한 Discount Factor
        ent_coef=0.01,         # 탐색(Exploration) 장려
        tensorboard_log="./ppo_tensorboard/"
    )
    
    print(f"Starting Training for {TOTAL_TIMESTEPS} timesteps...")
    try:
        model.learn(total_timesteps=TOTAL_TIMESTEPS, callback=callback)
        model.save("ppo_submission/vgc_ppo_model")
        print("Model saved successfully.")
    except KeyboardInterrupt:
        print("Training interrupted manually. Saving current model...")
        model.save("ppo_submission/vgc_ppo_model_interrupted")
    finally:
        vec_env.close()

if __name__ == "__main__":
    train()
