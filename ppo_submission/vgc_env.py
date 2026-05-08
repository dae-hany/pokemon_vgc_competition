import numpy as np
import gymnasium as gym
from gymnasium import spaces
from typing import Optional, List, Tuple
import traceback

from vgc2.battle_engine import (
    State, BattleCommand, BattleRuleParam,
    BattlingPokemon, calculate_damage
)
from vgc2.battle_engine.__init__ import BattleEngine
from vgc2.battle_engine.team import Team, BattlingTeam
from vgc2.agent.selection import RandomSelectionPolicy
from vgc2.util.generator import gen_team_from_roster
import random
import copy
from vgc2.battle_engine.modifiers import Status, Stat, Category

# 상수를 정의합니다.
MAX_HP = 1000.0  # 정규화를 위한 임의의 최대 HP (실제 엔진 상수 기반이 이상적)
NUM_STATS = 5    # ATK, DEF, SPA, SPD, SPE
NUM_STATUS = 7   # NONE, BURN, FREEZE, PARALYSIS, POISON, TOXIC, SLEEP

# 상태 차원 계산
# - Active PKM (나): HP(1) + Status(7) + Boosts(5) + Move PP(4) = 17
# - Bench PKM (나) x 3: HP(1) + Status(7) = 8 * 3 = 24
# - Active PKM (상대): HP(1) + Status(7) + Boosts(5) = 13
# - Bench PKM (상대) x 3: (알려진 정보라 가정) HP(1) + Status(7) = 8 * 3 = 24
# - Field: Weather(5) + Terrain(5) + Trickroom(1) = 11
# - Derived (나 Active): Speed Advantage(1) + Lethality(4) + Threat(1) = 6
# Total = 17 + 24 + 13 + 24 + 11 + 6 = 95
OBS_DIM = 95

class VgcEnv(gym.Env):
    """
    VGC 엔진을 Gymnasium 표준에 맞게 래핑한 환경입니다.
    """
    metadata = {"render_modes": ["human"]}

    def __init__(self, opponent_policy, params: BattleRuleParam):
        super().__init__()
        self.opponent_policy = opponent_policy
        self.params = params
        
        # Action: 4 기술 (0~3) + 3 벤치 교체 (4~6)
        self.action_space = spaces.Discrete(7)
        self.observation_space = spaces.Box(low=-1.0, high=2.0, shape=(OBS_DIM,), dtype=np.float32)
        
        self.battle = None
        self.current_state = None
        self.roster = None  # 훈련 스크립트에서 주입됨
        self.selection_policy = RandomSelectionPolicy()
        
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        
        # 1. 로스터(PokemonSpecies)에서 6마리를 무작위로 골라 실제 Pokemon 인스턴스로 구성 (Team 반환)
        if self.roster:
            my_team_obj = gen_team_from_roster(self.roster, n=6, n_moves=4)
            opp_team_obj = gen_team_from_roster(self.roster, n=6, n_moves=4)
            my_party = my_team_obj.members
            opp_party = opp_team_obj.members
        else:
            my_party = []
            opp_party = []
        
        # 2. 선출 (4마리)
        # 훈련 효율을 위해 RandomSelection 사용
        my_idx = self.selection_policy.decision([Team(my_party), Team(opp_party)], max_size=4)
        opp_idx = self.selection_policy.decision([Team(opp_party), Team(my_party)], max_size=4)
        
        # 3. 얕은 복사본(인스턴스 분리)으로 배틀용 몬스터 구성
        # Deepcopy를 안하면 로스터의 몬스터가 영구적으로 데미지를 입습니다.
        my_active = [copy.deepcopy(my_party[i]) for i in my_idx[:2]]
        my_bench = [copy.deepcopy(my_party[i]) for i in my_idx[2:]]
        opp_active = [copy.deepcopy(opp_party[i]) for i in opp_idx[:2]]
        opp_bench = [copy.deepcopy(opp_party[i]) for i in opp_idx[2:]]
        
        my_bteam = BattlingTeam(my_active, my_bench)
        opp_bteam = BattlingTeam(opp_active, opp_bench)
        
        # 4. State 및 BattleEngine 인스턴스화
        self.current_state = State((my_bteam, opp_bteam))
        self.battle = BattleEngine(self.current_state, self.params)
        
        obs = self._get_obs(self.current_state)
        info = {'action_mask': self._get_action_mask()}
        return obs, info

    def set_opponent(self, opponent_policy):
        """Curriculum Manager가 주기적으로 상대방 정책을 변경하기 위해 호출합니다."""
        self.opponent_policy = opponent_policy

    def step(self, action: int):
        # Action을 엔진 커맨드로 변환 (현재 싱글 배틀, 또는 첫 번째 Active 포켓몬 중심이라고 가정)
        my_cmds = self._decode_action(action, self.current_state.sides[0])
        
        # 상대(Curriculum) Action (FullCommand 구조: list[BattleCommand])
        try:
            opp_cmds = self.opponent_policy.decision(self.current_state, self.current_state.sides[1].team)
        except Exception:
            opp_cmds = [(0, 0)] # Fallback: 첫번째 기술 사용
            
        full_cmds = (my_cmds, opp_cmds)
        
        # 이전 잠재 가치 (Potential for Reward Shaping)
        phi_t = self._calculate_potential(self.current_state)
        
        # 한 턴 진행
        try:
            self.battle.run_turn(full_cmds)
        except Exception as e:
            traceback.print_exc()

        self.current_state = self.battle.state
        
        # 새로운 잠재 가치 및 Reward 계산
        phi_t_next = self._calculate_potential(self.current_state)
        reward = 0.99 * phi_t_next - phi_t  # PBRS
        
        # 종료 판별
        done = self.battle.finished()
        truncated = False
        
        # 최종 승패 보상 크게 부여
        if done:
            if self.battle.winning_side == 0:
                reward += 10.0
            elif self.battle.winning_side == 1:
                reward -= 10.0
                
        obs = self._get_obs(self.current_state)
        info = {'action_mask': self._get_action_mask()}
        
        return obs, reward, done, truncated, info
        
    def _decode_action(self, action: int, my_side) -> List[BattleCommand]:
        """Action int(0~6)을 BattleCommand [(action_id, target)] 로 변환"""
        # VGC 엔진은 BattleCommand = tuple[int, int] (action_id, target_id) 사용.
        # action_id: 0~3은 기술, -1은 교체를 뜻함. 
        # engine 내부 _set_action_queue 보면: a[0] >= 0 이면 기술, 아니면 교체 (a[1]이 벤치 인덱스)
        
        active_len = len(my_side.team.active)
        target = 0 # 싱글 타겟 가정
        
        if action < 4:
            # 기술 사용 (0~3)
            return [(action, target)]
        else:
            # 교체 사용 (4~6) -> 벤치 슬롯 0~2
            reserve_idx = action - 4
            # 엔진의 Switch queue는 (side, active_pos, reserve_pos) 이며 
            # action < 0 일때, a[1]이 reserve_pos로 들어감
            return [(-1, reserve_idx)]

    def _get_action_mask(self) -> np.ndarray:
        """선택 불가능한 Action을 걸러내는 Mask 배열 (1: 가능, 0: 불가능)"""
        mask = np.ones(7, dtype=np.float32)
        my_team = self.current_state.sides[0].team
        
        if len(my_team.active) == 0:
            return np.zeros(7, dtype=np.float32)
            
        pkm = my_team.active[0]
        
        # 1. 기술 제약 마스킹
        for i in range(4):
            if i >= len(pkm.battling_moves):
                mask[i] = 0.0
            else:
                move = pkm.battling_moves[i]
                if move.pp <= 0 or move.disabled:
                    mask[i] = 0.0
                    
        # 2. 교체 제약 마스킹
        for i in range(3):
            if i >= len(my_team.reserve):
                mask[i + 4] = 0.0
            elif my_team.reserve[i].fainted():
                mask[i + 4] = 0.0
                
        # 교체 봉인(그림자밟기 등) 체크가 필요하다면 여기에 추가
        return mask

    def _encode_status(self, status: Status) -> list[float]:
        v = [0.0] * 7
        idx_map = {Status.NONE:0, Status.BURN:1, Status.FROZEN:2, Status.PARALYZED:3, Status.POISON:4, Status.TOXIC:5, Status.SLEEP:6}
        if status in idx_map:
            v[idx_map[status]] = 1.0
        return v

    def _get_obs(self, state: State) -> np.ndarray:
        obs = []
        my_team = state.sides[0].team
        opp_team = state.sides[1].team
        
        # 1. My Active
        if len(my_team.active) > 0:
            pkm = my_team.active[0]
            obs.append(pkm.hp / pkm.constants.stats[Stat.MAX_HP])
            obs.extend(self._encode_status(pkm.status))
            obs.extend([b / 6.0 for b in pkm.boosts[1:6]]) # ATK, DEF, SPA, SPD, SPE
            # Moves PP
            for i in range(4):
                if i < len(pkm.battling_moves):
                    obs.append(pkm.battling_moves[i].pp / max(1, pkm.battling_moves[i].constants.max_pp))
                else:
                    obs.append(0.0)
        else:
            obs.extend([0.0] * 17)
            
        # 2. My Bench (3 slots)
        for i in range(3):
            if i < len(my_team.reserve):
                pkm = my_team.reserve[i]
                obs.append(pkm.hp / pkm.constants.stats[Stat.MAX_HP])
                obs.extend(self._encode_status(pkm.status))
            else:
                obs.extend([0.0] * 8)
                
        # 3. Opp Active
        if len(opp_team.active) > 0:
            pkm = opp_team.active[0]
            obs.append(pkm.hp / pkm.constants.stats[Stat.MAX_HP])
            obs.extend(self._encode_status(pkm.status))
            obs.extend([b / 6.0 for b in pkm.boosts[1:6]])
        else:
            obs.extend([0.0] * 13)
            
        # 4. Opp Bench (3 slots)
        for i in range(3):
            if i < len(opp_team.reserve):
                pkm = opp_team.reserve[i]
                obs.append(pkm.hp / pkm.constants.stats[Stat.MAX_HP])
                obs.extend(self._encode_status(pkm.status))
            else:
                obs.extend([0.0] * 8)
                
        # 5. Field (Weather 5, Terrain 5, Trickroom 1) -> Simply 11 dims
        w_vec = [0.0]*5; t_vec = [0.0]*5
        w_idx = min(state.weather.value, 4) if hasattr(state.weather, 'value') else 0
        t_idx = min(state.field.value, 4) if hasattr(state.field, 'value') else 0
        w_vec[w_idx] = 1.0
        t_vec[t_idx] = 1.0
        obs.extend(w_vec)
        obs.extend(t_vec)
        obs.append(1.0 if state.trickroom else 0.0)
        
        # 6. Derived Variables (Speed, Lethality, Threat)
        my_active = my_team.active[0] if len(my_team.active) > 0 else None
        opp_active = opp_team.active[0] if len(opp_team.active) > 0 else None
        
        if my_active and opp_active:
            # 스피드 (단순 값 비교, 실제 priority 로직은 생략/근사)
            my_spd = my_active.constants.stats[Stat.SPEED] * (1.5 if my_active.boosts[5] > 0 else 1.0)
            opp_spd = opp_active.constants.stats[Stat.SPEED] * (1.5 if opp_active.boosts[5] > 0 else 1.0)
            if state.trickroom:
                spd_adv = 1.0 if my_spd < opp_spd else (0.5 if my_spd == opp_spd else 0.0)
            else:
                spd_adv = 1.0 if my_spd > opp_spd else (0.5 if my_spd == opp_spd else 0.0)
            obs.append(spd_adv)
            
            # Lethality
            for i in range(4):
                if i < len(my_active.battling_moves) and my_active.battling_moves[i].pp > 0:
                    try:
                        dmg = calculate_damage(self.params, 0, my_active.battling_moves[i].constants, state, my_active, opp_active)
                        obs.append(min(2.0, dmg / max(1.0, opp_active.hp)))
                    except Exception:
                        obs.append(0.0)
                else:
                    obs.append(0.0)
                    
            # Threat (상대의 가장 아픈 공격)
            max_threat = 0.0
            for m in opp_active.battling_moves:
                if m.pp > 0:
                    try:
                        dmg = calculate_damage(self.params, 1, m.constants, state, opp_active, my_active)
                        max_threat = max(max_threat, dmg / max(1.0, my_active.hp))
                    except Exception:
                        pass
            obs.append(min(2.0, max_threat))
        else:
            obs.extend([0.0] * 6)
            
        assert len(obs) == OBS_DIM, f"Obs length {len(obs)} != {OBS_DIM}"
        return np.array(obs, dtype=np.float32)

    def _calculate_potential(self, state: State) -> float:
        """잠재 가치 함수 Phi(s). 아군 HP 비율 합 - 상대 HP 비율 합"""
        my_hp = sum([p.hp / p.constants.stats[Stat.MAX_HP] for p in state.sides[0].team.active + state.sides[0].team.reserve])
        opp_hp = sum([p.hp / p.constants.stats[Stat.MAX_HP] for p in state.sides[1].team.active + state.sides[1].team.reserve])
        return my_hp - opp_hp
