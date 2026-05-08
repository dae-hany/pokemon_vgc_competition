"""
Enhanced Jirachi AI Core Policies - VGC2 호환성 완전 수정
VGC2 State 접근 안정화 + BattleCommand 타입 일관성 + 지형 누락 수정 완료
"""

import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# VGC2 imports with enhanced compatibility
try:
    from vgc2.agent import BattlePolicy, SelectionPolicy, BattleCommand, SelectionCommand
    from vgc2.battle_engine import State, TeamView, Team, BattlingPokemon, BattlingMove
    from vgc2.battle_engine.constants import BattleRuleParam
    from vgc2.battle_engine.damage_calculator import calculate_damage
    from vgc2.battle_engine.modifiers import Type, Status, Category, Weather, Terrain, Nature
    from vgc2.battle_engine.pokemon import Stat
    from vgc2.util.forward import copy_state, forward
except ImportError as e:
    print(f"VGC2 import error: {e}")
    print("Please ensure VGC2 is properly installed")
    sys.exit(1)


@dataclass
class SearchResult:
    """빔 서치 결과"""
    action: List[BattleCommand]
    confidence: float
    evaluation_score: float


class OpponentEvaluator:
    """상대방 전용 평가 시스템"""

    def __init__(self):
        self.weights = {
            'safe_kill': 1000,
            'hp_preservation': 800,
            'speed_control': 600,
            'damage_consistency': 400,
            'type_advantage': 300,
            'risk_mitigation': 500
        }

    def evaluate_state_for_opponent(self, state: State) -> float:
        """상대방 시점에서 상태 평가"""
        try:
            opp_team = state.sides[1].team
            my_team = state.sides[0].team

            score = 0.0

            # HP 보존 우선 평가
            opp_hp_ratio = self._calculate_team_hp_ratio(opp_team)
            my_hp_ratio = self._calculate_team_hp_ratio(my_team)

            hp_diff = opp_hp_ratio - my_hp_ratio
            if hp_diff > 0.3:
                score += self.weights['hp_preservation'] + hp_diff * 200
            elif hp_diff < -0.2:
                score -= 300 + abs(hp_diff) * 150
            else:
                score += hp_diff * 100

            # 안전한 킬 기회 평가
            safe_kills = self._count_safe_kill_opportunities(opp_team, my_team, state)
            score += safe_kills * self.weights['safe_kill']

            return score

        except Exception:
            return 0.0

    def predict_opponent_action(self, state: State) -> List[BattleCommand]:
        """상대방 행동 예측 (안전성 중심)"""
        opp_team = state.sides[1].team
        my_team = state.sides[0].team

        commands = []
        for attacker in opp_team.active:
            if attacker.hp <= 0:
                commands.append((0, 0))
                continue

            best_move = (0, 0)
            best_score = 0.0

            for move_idx, move in enumerate(attacker.battling_moves):
                if move.pp <= 0 or move.disabled:
                    continue

                for target_idx, target in enumerate(my_team.active):
                    if target is None or target.hp <= 0:
                        continue

                    damage = calculate_damage(BattleRuleParam(), 0, move.constants, state, attacker, target)
                    accuracy = getattr(move.constants, 'accuracy', 100) / 100.0

                    score = float(damage)
                    if damage >= target.hp and accuracy >= 0.9:
                        score *= 5.0  # 안전한 킬
                    elif damage >= target.hp * 0.7 and accuracy >= 0.85:
                        score *= 2.0  # 안정적 큰 데미지

                    if accuracy < 0.8:
                        score *= 0.5

                    if score > best_score:
                        best_score = score
                        best_move = (move_idx, target_idx)

            commands.append(best_move)

        return commands

    def _calculate_team_hp_ratio(self, team) -> float:
        """팀 HP 비율 계산"""
        try:
            total_hp = 0
            max_hp = 0

            all_pokemon = team.active + team.reserve
            for pokemon in all_pokemon:
                if hasattr(pokemon, 'hp') and hasattr(pokemon.constants, 'stats'):
                    total_hp += pokemon.hp
                    max_hp += pokemon.constants.stats[Stat.MAX_HP]

            return total_hp / max_hp if max_hp > 0 else 0.0

        except Exception:
            return 0.0

    def _count_safe_kill_opportunities(self, opp_team, my_team, state: State) -> int:
        """안전한 킬 기회 계산"""
        safe_kills = 0

        for attacker in opp_team.active:
            if attacker.hp <= 0:
                continue

            for target in my_team.active:
                if target is None or target.hp <= 0:
                    continue

                for move in attacker.battling_moves:
                    if move.pp <= 0 or move.disabled:
                        continue

                    damage = calculate_damage(BattleRuleParam(), 0, move.constants, state, attacker, target)
                    accuracy = getattr(move.constants, 'accuracy', 100) / 100.0

                    if damage >= target.hp and accuracy >= 0.9:
                        safe_kills += 1
                        break

        return safe_kills


class AlwaysSmartBeamSearchPolicy(BattlePolicy):
    """매번 스마트 빔 서치를 적용하는 정책 - VGC2 완전 호환"""

    def __init__(self, time_limit_ms: int = 90, is_championship: bool = False):
        self.params = BattleRuleParam()
        self.time_limit_ms = time_limit_ms
        self.is_championship = is_championship
        self.turn_count = 0
        self.damage_cache = {}

        # 🌦️ 날씨 우선순위 시스템 (VGC2 확인됨)
        self.weather_priority_map = {
            Weather.RAIN: [Type.WATER, Type.ELECTRIC],
            Weather.SUN: [Type.FIRE, Type.GRASS],
            Weather.SAND: [Type.ROCK, Type.GROUND, Type.STEEL],
            Weather.SNOW: [Type.ICE]
        }

        # 🌍 지형 우선순위 시스템 (누락 수정 완료)
        self.terrain_priority_map = {
            Terrain.ELECTRIC_TERRAIN: [Type.ELECTRIC],
            Terrain.GRASSY_TERRAIN: [Type.GRASS],
            Terrain.MISTY_TERRAIN: [Type.FAIRY],
            Terrain.PSYCHIC_TERRAIN: [Type.PSYCHIC]
        }

        # 상대방 평가자
        self.opponent_evaluator = OpponentEvaluator()

        print("Always Smart Beam Search Policy Initialized")
        print(f"Time Budget: {time_limit_ms}ms per decision")
        print(f"Championship Mode: {'ON' if is_championship else 'OFF'}")
        print("Weather Support: 4개 날씨 완전 지원")
        print("Terrain Support: 4개 지형 완전 지원 (누락 수정 완료)")

    def decision(self, state: State, opp_view: Optional[TeamView] = None) -> List[BattleCommand]:
        """매번 Always Smart Beam Search 적용 - VGC2 호환"""
        start_time = time.time()
        self.turn_count += 1

        try:
            my_team = state.sides[0].team

            # print(f"🌟 Turn {self.turn_count}: Always Smart Beam Search Starting")

            # 1단계: 빠른 Greedy (5ms) - 항상 안전한 기본 결과 확보
            current_best = self._greedy_analysis(state)
            # print(f"⚡ Greedy baseline secured: {current_best.confidence:.2f} confidence")

            # 2단계: 점진적 빔 서치 확장
            for beam_width in [2, 3, 4, 5]:
                for depth in [1, 2, 3]:
                    elapsed = (time.time() - start_time) * 1000
                    if elapsed > self.time_limit_ms * 0.9:
                        break

                    remaining_time = self.time_limit_ms - elapsed
                    if remaining_time < 10:
                        break

                    beam_result = self._beam_search(state, beam_width, depth, remaining_time)

                    if beam_result and beam_result.evaluation_score > current_best.evaluation_score:
                        # print(
                        #     f"🔥 Improved! Beam({beam_width},{depth}): {beam_result.evaluation_score:.0f} > {current_best.evaluation_score:.0f}")
                        current_best = beam_result

                elapsed = (time.time() - start_time) * 1000
                if elapsed > self.time_limit_ms * 0.9:
                    break

            total_time = (time.time() - start_time) * 1000
            # print(f"✅ Final Decision ({total_time:.1f}ms)")
            return current_best.action

        except Exception as e:
            print(f"❌ Always Smart Beam Search error: {e}")
            my_team = state.sides[0].team
            # VGC2 호환: BattleCommand = Tuple[int, int] 확인됨
            return [(0, 0)] * len(my_team.active)

    def _get_current_terrain(self, state: State) -> Terrain:
        """VGC2 State에서 안전한 terrain 접근"""
        try:
            return state.field  # VGC2에서 확인된 속성
        except AttributeError:
            return Terrain.NONE  # Fallback

    def _get_current_weather(self, state: State) -> Weather:
        """VGC2 State에서 안전한 weather 접근"""
        try:
            return state.weather  # VGC2에서 확인된 속성
        except AttributeError:
            return Weather.CLEAR  # Fallback

    def _greedy_analysis(self, state: State) -> SearchResult:
        """빠른 Greedy 분석"""
        my_team = state.sides[0].team
        opp_team = state.sides[1].team

        best_commands = []
        total_confidence = 0.0

        for attacker_idx, attacker in enumerate(my_team.active):
            if attacker.hp <= 0:
                best_commands.append((0, 0))
                continue

            if self.is_championship and self.turn_count == 1:
                pokemon_role = self._get_pokemon_role(attacker)

                if pokemon_role == "SETTER":
                    command, confidence = self._championship_setter_priority(attacker, state, my_team, opp_team)
                else:
                    command, confidence = self._championship_attacker_priority(attacker, state, opp_team)

                best_commands.append(command)
                total_confidence += confidence
                continue

            command, confidence = self._battle_track_priority(attacker, state, my_team, opp_team)
            best_commands.append(command)
            total_confidence += confidence

        if not my_team.active:
            return SearchResult(
                action=[(0, 0)],
                confidence=0.0,
                evaluation_score=0.0
            )

        avg_confidence = total_confidence / len(my_team.active)
        evaluation_score = self._evaluate_state_jirachi(state, state)

        return SearchResult(
            action=best_commands,
            confidence=avg_confidence,
            evaluation_score=evaluation_score
        )

    def _get_pokemon_role(self, pokemon: BattlingPokemon) -> str:
        """포켓몬 역할 추정"""
        try:
            moves = getattr(pokemon, 'battling_moves', [])
            if not moves:
                return "ATTACKER"

            for move in moves:
                if not hasattr(move, 'constants'):
                    continue

                weather_effect = getattr(move.constants, 'weather_start', Weather.CLEAR)
                field_effect = getattr(move.constants, 'field_start', Terrain.NONE)

                if weather_effect != Weather.CLEAR or field_effect != Terrain.NONE:
                    return "SETTER"

            return "ATTACKER"

        except Exception:
            return "ATTACKER"

    def _championship_setter_priority(self, attacker: BattlingPokemon, state: State, my_team, opp_team) -> Tuple[
        BattleCommand, float]:
        """Championship 설치자 우선순위"""
        # 1순위: 환경 설치
        if self._should_setup_weather(state, my_team, opp_team):
            setup_move, confidence = self._find_weather_setup(attacker, state)
            if setup_move != (0, 0):
                return setup_move, confidence

        if self._should_setup_terrain(state, my_team, opp_team):
            setup_move, confidence = self._find_terrain_setup(attacker, state)
            if setup_move != (0, 0):
                return setup_move, confidence

        # 2순위: 즉시 킬
        if self._has_immediate_kill_potential([attacker], opp_team.active, state):
            kill_move, confidence = self._find_obvious_kill(attacker, opp_team.active, state)
            if kill_move != (0, 0):
                return kill_move, confidence

        # 3순위: 일반 공격
        return self._find_best_greedy_move(attacker, opp_team.active, state)

    def _championship_attacker_priority(self, attacker: BattlingPokemon, state: State, opp_team) -> Tuple[
        BattleCommand, float]:
        """Championship 공격자 우선순위"""
        # 1순위: 즉시 킬
        if self._has_immediate_kill_potential([attacker], opp_team.active, state):
            kill_move, confidence = self._find_obvious_kill(attacker, opp_team.active, state)
            if kill_move != (0, 0):
                return kill_move, confidence

        # 2순위: 일반 공격
        return self._find_best_greedy_move(attacker, opp_team.active, state)

    def _battle_track_priority(self, attacker: BattlingPokemon, state: State, my_team, opp_team) -> Tuple[
        BattleCommand, float]:
        """Battle Track 우선순위"""
        # 1순위: 즉시 킬
        if self._has_immediate_kill_potential([attacker], opp_team.active, state):
            kill_move, confidence = self._find_obvious_kill(attacker, opp_team.active, state)
            if kill_move != (0, 0) and confidence >= 0.9:
                return kill_move, confidence

        # 2순위: 고가치 환경 설치
        if self._should_setup_weather(state, my_team, opp_team):
            setup_move, confidence = self._find_weather_setup(attacker, state)
            if setup_move != (0, 0):
                weather_value = self._calculate_weather_synergy_value_for_move(attacker, state, my_team, opp_team)
                if weather_value > 600:
                    return setup_move, confidence

        if self._should_setup_terrain(state, my_team, opp_team):
            setup_move, confidence = self._find_terrain_setup(attacker, state)
            if setup_move != (0, 0):
                terrain_value = self._calculate_terrain_synergy_value_for_move(attacker, state, my_team, opp_team)
                if terrain_value > 400:
                    return setup_move, confidence

        # 3순위: 일반 공격
        return self._find_best_greedy_move(attacker, opp_team.active, state)

    def _should_setup_weather(self, state: State, my_team, opp_team) -> bool:
        """날씨 설치 필요성 판단"""
        current_weather = self._get_current_weather(state)
        if current_weather != Weather.CLEAR:
            return False

        if not my_team or not hasattr(my_team, 'active') or not my_team.active:
            return False

        for pokemon in my_team.active:
            if pokemon.hp <= 0:
                continue

            moves = getattr(pokemon, 'battling_moves', [])
            if not moves:
                continue

            for move in moves:
                if move.pp <= 0 or move.disabled:
                    continue

                if not hasattr(move, 'constants'):
                    continue

                weather_effect = getattr(move.constants, 'weather_start', Weather.CLEAR)
                if weather_effect != Weather.CLEAR:
                    try:
                        synergy_value = self._calculate_weather_synergy_value(weather_effect, my_team, opp_team)
                        if synergy_value > 300:
                            return True
                    except Exception:
                        return True

        return False

    def _should_setup_terrain(self, state: State, my_team, opp_team) -> bool:
        """지형 설치 필요성 판단 (누락 수정)"""
        current_terrain = self._get_current_terrain(state)
        if current_terrain != Terrain.NONE:
            return False

        if not my_team or not hasattr(my_team, 'active') or not my_team.active:
            return False

        for pokemon in my_team.active:
            if pokemon.hp <= 0:
                continue

            moves = getattr(pokemon, 'battling_moves', [])
            if not moves:
                continue

            for move in moves:
                if move.pp <= 0 or move.disabled:
                    continue

                if not hasattr(move, 'constants'):
                    continue

                terrain_effect = getattr(move.constants, 'field_start', Terrain.NONE)
                if terrain_effect != Terrain.NONE:
                    try:
                        synergy_value = self._calculate_terrain_synergy_value(terrain_effect, my_team, opp_team)
                        if synergy_value > 200:
                            return True
                    except Exception:
                        return True

        return False

    def _calculate_weather_synergy_value(self, weather: Weather, my_team, opp_team) -> float:
        """날씨 시너지 가치 계산"""
        try:
            boosted_types = self.weather_priority_map.get(weather, [])
            if not boosted_types:
                return 0.0

            value = 0.0

            if not my_team or not hasattr(my_team, 'active'):
                return 0.0

            active_pokemon = getattr(my_team, 'active', [])
            for pokemon in active_pokemon:
                if not pokemon or pokemon.hp <= 0:
                    continue

                pokemon_types = set(getattr(pokemon.constants, 'types', []))
                moves = getattr(pokemon, 'battling_moves', [])

                for move in moves:
                    if not hasattr(move, 'constants'):
                        continue

                    move_type = getattr(move.constants, 'pkm_type', Type.NORMAL)
                    if move_type in boosted_types:
                        base_power = getattr(move.constants, 'base_power', 0)

                        multiplier = 1.5
                        if move_type in pokemon_types:
                            multiplier *= 1.5

                        value += base_power * multiplier

            reserve_pokemon = getattr(my_team, 'reserve', [])
            for pokemon in reserve_pokemon:
                if not pokemon or pokemon.hp <= 0:
                    continue

                pokemon_types = set(getattr(pokemon.constants, 'types', []))
                moves = getattr(pokemon, 'battling_moves', [])

                for move in moves:
                    if not hasattr(move, 'constants'):
                        continue

                    move_type = getattr(move.constants, 'pkm_type', Type.NORMAL)
                    if move_type in boosted_types:
                        base_power = getattr(move.constants, 'base_power', 0)

                        multiplier = 1.5
                        if move_type in pokemon_types:
                            multiplier *= 1.5

                        value += (base_power * multiplier) * 0.5

            return value

        except Exception:
            return 0.0

    def _calculate_terrain_synergy_value(self, terrain: Terrain, my_team, opp_team) -> float:
        """지형 시너지 가치 계산 (누락 수정)"""
        try:
            boosted_types = self.terrain_priority_map.get(terrain, [])
            if not boosted_types:
                return 0.0

            value = 0.0

            if not my_team or not hasattr(my_team, 'active'):
                return 0.0

            active_pokemon = getattr(my_team, 'active', [])
            for pokemon in active_pokemon:
                if not pokemon or pokemon.hp <= 0:
                    continue

                pokemon_types = set(getattr(pokemon.constants, 'types', []))
                moves = getattr(pokemon, 'battling_moves', [])

                for move in moves:
                    if not hasattr(move, 'constants'):
                        continue

                    move_type = getattr(move.constants, 'pkm_type', Type.NORMAL)
                    if move_type in boosted_types:
                        base_power = getattr(move.constants, 'base_power', 0)

                        multiplier = 1.3  # 지형 부스트
                        if move_type in pokemon_types:
                            multiplier *= 1.5  # STAB

                        value += base_power * multiplier

            reserve_pokemon = getattr(my_team, 'reserve', [])
            for pokemon in reserve_pokemon:
                if not pokemon or pokemon.hp <= 0:
                    continue

                pokemon_types = set(getattr(pokemon.constants, 'types', []))
                moves = getattr(pokemon, 'battling_moves', [])

                for move in moves:
                    if not hasattr(move, 'constants'):
                        continue

                    move_type = getattr(move.constants, 'pkm_type', Type.NORMAL)
                    if move_type in boosted_types:
                        base_power = getattr(move.constants, 'base_power', 0)

                        multiplier = 1.3
                        if move_type in pokemon_types:
                            multiplier *= 1.5

                        value += (base_power * multiplier) * 0.5

            return value

        except Exception:
            return 0.0

    def _calculate_weather_synergy_value_for_move(self, attacker: BattlingPokemon, state: State, my_team,
                                                  opp_team) -> float:
        """특정 포켓몬이 날씨 설치할 때의 시너지 값"""
        for move in attacker.battling_moves:
            weather_effect = getattr(move.constants, 'weather_start', Weather.CLEAR)
            if weather_effect != Weather.CLEAR:
                return self._calculate_weather_synergy_value(weather_effect, my_team, opp_team)
        return 0.0

    def _calculate_terrain_synergy_value_for_move(self, attacker: BattlingPokemon, state: State, my_team,
                                                  opp_team) -> float:
        """특정 포켓몬이 지형 설치할 때의 시너지 값 (누락 수정)"""
        for move in attacker.battling_moves:
            terrain_effect = getattr(move.constants, 'field_start', Terrain.NONE)
            if terrain_effect != Terrain.NONE:
                return self._calculate_terrain_synergy_value(terrain_effect, my_team, opp_team)
        return 0.0

    def _find_weather_setup(self, attacker: BattlingPokemon, state: State) -> Tuple[BattleCommand, float]:
        """날씨 설치 기술 찾기"""
        if not attacker or not hasattr(attacker, 'battling_moves'):
            return (0, 0), 0.0

        moves = getattr(attacker, 'battling_moves', [])
        if not moves:
            return (0, 0), 0.0

        for move_idx, move in enumerate(moves):
            if move.pp <= 0 or move.disabled:
                continue

            if not hasattr(move, 'constants'):
                continue

            weather_effect = getattr(move.constants, 'weather_start', Weather.CLEAR)
            if weather_effect != Weather.CLEAR:
                try:
                    value = self._calculate_weather_synergy_value(weather_effect,
                                                                  state.sides[0].team,
                                                                  state.sides[1].team)
                    confidence = min(0.8, value / 600)
                    return (move_idx, 0), confidence
                except Exception:
                    return (move_idx, 0), 0.5

        return (0, 0), 0.0

    def _find_terrain_setup(self, attacker: BattlingPokemon, state: State) -> Tuple[BattleCommand, float]:
        """지형 설치 기술 찾기 (누락 수정)"""
        if not attacker or not hasattr(attacker, 'battling_moves'):
            return (0, 0), 0.0

        moves = getattr(attacker, 'battling_moves', [])
        if not moves:
            return (0, 0), 0.0

        for move_idx, move in enumerate(moves):
            if move.pp <= 0 or move.disabled:
                continue

            if not hasattr(move, 'constants'):
                continue

            terrain_effect = getattr(move.constants, 'field_start', Terrain.NONE)
            if terrain_effect != Terrain.NONE:
                try:
                    value = self._calculate_terrain_synergy_value(terrain_effect,
                                                                  state.sides[0].team,
                                                                  state.sides[1].team)
                    confidence = min(0.75, value / 400)
                    return (move_idx, 0), confidence
                except Exception:
                    return (move_idx, 0), 0.4

        return (0, 0), 0.0

    def _has_immediate_kill_potential(self, attackers, targets, state: State) -> bool:
        """즉시 킬 가능성 체크"""
        for attacker in attackers:
            if attacker.hp <= 0:
                continue

            for target in targets:
                if target is None or target.hp <= 0:
                    continue

                for move in attacker.battling_moves:
                    if move.pp <= 0 or move.disabled:
                        continue

                    damage = self._calculate_enhanced_damage(attacker, target, move, state)
                    accuracy = getattr(move.constants, 'accuracy', 100) / 100.0

                    if damage * accuracy >= target.hp * 0.9:
                        return True

        return False

    def _find_obvious_kill(self, attacker: BattlingPokemon, targets, state: State) -> Tuple[BattleCommand, float]:
        """명확한 킬 찾기"""
        best_move = (0, 0)
        best_confidence = 0.0

        for move_idx, move in enumerate(attacker.battling_moves):
            if move.pp <= 0 or move.disabled:
                continue

            for target_idx, target in enumerate(targets):
                if target is None or target.hp <= 0:
                    continue

                damage = self._calculate_enhanced_damage(attacker, target, move, state)
                accuracy = getattr(move.constants, 'accuracy', 100) / 100.0
                expected_damage = damage * accuracy

                if expected_damage >= target.hp:
                    confidence = min(0.95, accuracy + 0.1)
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_move = (move_idx, target_idx)

        return best_move, best_confidence

    def _find_best_greedy_move(self, attacker: BattlingPokemon, targets, state: State) -> Tuple[BattleCommand, float]:
        """지라치 스타일 최선의 수 찾기"""
        best_move = (0, 0)
        best_score = 0.0
        max_possible_score = 1.0

        for move_idx, move in enumerate(attacker.battling_moves):
            if move.pp <= 0 or move.disabled:
                continue

            for target_idx, target in enumerate(targets):
                if target is None or target.hp <= 0:
                    continue

                damage = self._calculate_enhanced_damage(attacker, target, move, state)

                score = damage

                if damage >= target.hp:
                    score *= 10.0
                    max_possible_score = max(max_possible_score, score)

                priority = getattr(move.constants, 'priority', 0)
                if priority > 0:
                    score *= 3.0

                score *= self._get_environment_boost(move, state)

                if score > best_score:
                    best_score = score
                    best_move = (move_idx, target_idx)

        confidence = min(0.9, best_score / max_possible_score) if max_possible_score > 0 else 0.5
        return best_move, confidence

    def _get_environment_boost(self, move: BattlingMove, state: State) -> float:
        """환경 부스트 계산 (날씨 + 지형 완전 지원)"""
        boost = 1.0
        move_type = getattr(move.constants, 'pkm_type', Type.NORMAL)

        # 날씨 부스트
        current_weather = self._get_current_weather(state)
        if current_weather != Weather.CLEAR:
            boosted_types = self.weather_priority_map.get(current_weather, [])
            if move_type in boosted_types:
                boost *= 1.5

        # 지형 부스트 (누락 수정 완료)
        current_terrain = self._get_current_terrain(state)
        if current_terrain != Terrain.NONE:
            terrain_boosted_types = self.terrain_priority_map.get(current_terrain, [])
            if move_type in terrain_boosted_types:
                boost *= 1.3

        return boost

    def _beam_search(self, state: State, beam_width: int, max_depth: int, time_limit: float) -> Optional[SearchResult]:
        """Progressive Beam Search 구현"""
        start_time = time.time()

        try:
            beam = [(state, [], 0.0)]

            for depth in range(max_depth):
                elapsed = (time.time() - start_time) * 1000
                if elapsed > time_limit * 0.8:
                    break

                new_beam = []

                for current_state, command_history, current_score in beam:
                    possible_actions = self._generate_possible_actions(current_state)

                    for action in possible_actions[:beam_width * 2]:
                        try:
                            new_state = self._simulate_action(current_state, action)
                            new_score = self._evaluate_state_jirachi(new_state, current_state)

                            new_command_history = command_history + [action]
                            new_beam.append((new_state, new_command_history, new_score))

                        except Exception:
                            continue

                new_beam.sort(key=lambda x: x[2], reverse=True)
                beam = new_beam[:beam_width]

                if not beam:
                    break

            if beam and beam[0][1]:
                best_score = beam[0][2]
                best_action = beam[0][1][0]

                return SearchResult(
                    action=best_action,
                    confidence=0.8,
                    evaluation_score=best_score
                )

            return None

        except Exception as e:
            print(f"⚠️ Beam search error: {e}")
            return None

    def _generate_possible_actions(self, state: State) -> List[List[BattleCommand]]:
        """가능한 액션들 생성"""
        my_team = state.sides[0].team
        opp_team = state.sides[1].team

        if not my_team.active:
            return [[(0, 0)]]

        pokemon_actions = []

        for attacker in my_team.active:
            if attacker.hp <= 0:
                pokemon_actions.append([(0, 0)])
                continue

            actions = []

            for move_idx, move in enumerate(attacker.battling_moves):
                if move.pp <= 0 or move.disabled:
                    continue

                for target_idx, target in enumerate(opp_team.active):
                    if target is None or target.hp <= 0:
                        continue
                    actions.append((move_idx, target_idx))

            actions.sort(key=lambda a: self._action_priority_score(attacker, opp_team.active, a, state), reverse=True)
            pokemon_actions.append(actions[:3] if actions else [(0, 0)])

        if len(pokemon_actions) == 1:
            return [[action] for action in pokemon_actions[0]]
        elif len(pokemon_actions) == 2:
            combinations = []
            for a1 in pokemon_actions[0]:
                for a2 in pokemon_actions[1]:
                    combinations.append([a1, a2])
            return combinations[:9]
        else:
            combinations = []
            for a1 in pokemon_actions[0][:2]:
                for a2 in pokemon_actions[1][:2]:
                    for a3 in pokemon_actions[2][:2]:
                        combinations.append([a1, a2, a3])
            return combinations[:8]

    def _action_priority_score(self, attacker: BattlingPokemon, targets, action: BattleCommand, state: State) -> float:
        """액션 우선순위 점수"""
        move_idx, target_idx = action

        if target_idx >= len(targets) or targets[target_idx] is None:
            return 0.0

        if move_idx >= len(attacker.battling_moves):
            return 0.0

        move = attacker.battling_moves[move_idx]
        target = targets[target_idx]

        damage = self._calculate_enhanced_damage(attacker, target, move, state)

        score = damage

        if damage >= target.hp:
            score *= 10.0

        priority = getattr(move.constants, 'priority', 0)
        if priority > 0:
            score *= 3.0

        score *= self._get_environment_boost(move, state)

        return score

    def _simulate_action(self, state: State, action: List[BattleCommand]) -> State:
        """액션 시뮬레이션"""
        try:
            new_state = copy_state(state)
            opp_action = self.opponent_evaluator.predict_opponent_action(new_state)
            full_command = (action, opp_action)
            forward(new_state, full_command, self.params)
            return new_state
        except Exception:
            return state

    def _evaluate_state_jirachi(self, new_state: State, original_state: State) -> float:
        """지라치 스타일 상태 평가"""
        try:
            my_team_new = new_state.sides[0].team
            opp_team_new = new_state.sides[1].team

            my_hp_ratio = self._calculate_team_hp_ratio(my_team_new)
            opp_hp_ratio = self._calculate_team_hp_ratio(opp_team_new)

            my_team_orig = original_state.sides[0].team
            opp_team_orig = original_state.sides[1].team

            orig_opp_count = len([p for p in opp_team_orig.active + opp_team_orig.reserve if p.hp > 0])
            new_opp_count = len([p for p in opp_team_new.active + opp_team_new.reserve if p.hp > 0])

            ko_bonus = (orig_opp_count - new_opp_count) * 1000

            environment_bonus = 0
            orig_weather = self._get_current_weather(original_state)
            new_weather = self._get_current_weather(new_state)
            if orig_weather == Weather.CLEAR and new_weather != Weather.CLEAR:
                environment_bonus += 300

            orig_terrain = self._get_current_terrain(original_state)
            new_terrain = self._get_current_terrain(new_state)
            if orig_terrain == Terrain.NONE and new_terrain != Terrain.NONE:
                environment_bonus += 200

            score = (my_hp_ratio - opp_hp_ratio) * 100 + ko_bonus + environment_bonus

            return score

        except Exception:
            return 0.0

    def _calculate_team_hp_ratio(self, team) -> float:
        """팀 HP 비율 계산"""
        try:
            total_hp = 0
            max_hp = 0

            all_pokemon = team.active + team.reserve
            for pokemon in all_pokemon:
                if hasattr(pokemon, 'hp') and hasattr(pokemon.constants, 'stats'):
                    total_hp += pokemon.hp
                    max_hp += pokemon.constants.stats[Stat.MAX_HP]

            return total_hp / max_hp if max_hp > 0 else 0.0

        except Exception:
            return 0.0

    def _calculate_enhanced_damage(self, attacker: BattlingPokemon, defender: BattlingPokemon,
                                   move: BattlingMove, state: State) -> float:
        """지라치 특화 데미지 계산"""
        try:
            cache_key = (id(attacker), id(defender), id(move.constants))
            if cache_key in self.damage_cache:
                return self.damage_cache[cache_key]

            damage = calculate_damage(self.params, 0, move.constants, state, attacker, defender)
            damage *= self._get_environment_boost(move, state)

            base_power = getattr(move.constants, 'base_power', 0)
            if base_power >= 80:
                damage *= 1.1

            self.damage_cache[cache_key] = damage
            return float(damage)

        except Exception:
            base_power = getattr(move.constants, 'base_power', 60)
            return base_power * 1.2


# === Selection 정책들 ===

class JirachiBattleSelectionPolicy(SelectionPolicy):
    """지라치 Battle Track 전용 선택 정책"""

    def decision(self, teams: Tuple[Team, Team], max_size: int) -> SelectionCommand:
        """지라치 1턴킬 기준 포켓몬 선택"""
        try:
            my_team, opp_team = teams

            if len(my_team.members) <= max_size:
                return list(range(len(my_team.members)))

            pokemon_scores = []

            for i, pokemon in enumerate(my_team.members):
                score = self._calculate_jirachi_score(pokemon, opp_team)
                pokemon_scores.append((i, score))

            pokemon_scores.sort(key=lambda x: x[1], reverse=True)
            selected = self._ensure_speed_diversity(pokemon_scores, my_team, max_size)

            print(f"🌟 Jirachi Battle Selection: {selected}")
            return selected

        except Exception as e:
            print(f"❌ Jirachi battle selection error: {e}")
            return list(range(min(max_size, len(teams[0].members))))

    def _calculate_jirachi_score(self, pokemon, opp_team) -> float:
        """지라치 기준 포켓몬 평가"""
        try:
            score = 0.0

            stats = getattr(pokemon, 'stats', None)
            if stats:
                speed = stats[Stat.SPEED]
                attack = stats[Stat.ATTACK]
                sp_attack = stats[Stat.SPECIAL_ATTACK]
                hp = stats[Stat.MAX_HP]

                # 스피드 절대시
                if speed >= 130:
                    score += 500
                elif speed >= 110:
                    score += 350
                elif speed >= 95:
                    score += 200
                elif speed >= 80:
                    score += 100

                # 공격력
                max_offense = max(attack, sp_attack)
                score += max_offense / 1.5

                # 내구력 페널티
                if hp > 250:
                    score -= (hp - 250) / 10

            # 기술 평가
            moves = getattr(pokemon, 'moves', [])
            priority_count = 0
            high_power_count = 0

            for move in moves:
                base_power = getattr(move, 'base_power', 0)
                priority = getattr(move, 'priority', 0)
                accuracy = getattr(move, 'accuracy', 100)

                if priority > 0:
                    priority_count += 1
                    if base_power >= 80:
                        score += 400
                    elif base_power >= 40:
                        score += 250
                    else:
                        score += 150

                if base_power >= 130:
                    high_power_count += 1
                    score += 200
                elif base_power >= 110:
                    score += 150
                elif base_power >= 90:
                    score += 100

                if base_power >= 120 and accuracy <= 80:
                    score += 100

                # 환경 기술 보너스
                weather_keywords = ['rain', 'sun', 'sand', 'hail', 'snow']
                terrain_keywords = ['electric terrain', 'grassy terrain', 'misty terrain', 'psychic terrain']
                move_name = getattr(move, 'name', '').lower()

                if any(keyword in move_name for keyword in weather_keywords + terrain_keywords):
                    score += 50

            if priority_count >= 2:
                score += 200

            if high_power_count >= 2:
                score += 150

            counter_score = self._analyze_counter_potential(pokemon, opp_team)
            score += counter_score

            return score

        except Exception:
            return 0.0

    def _analyze_counter_potential(self, pokemon, opp_team) -> float:
        """상대팀 카운터 잠재력 분석"""
        score = 0.0

        try:
            my_stats = getattr(pokemon, 'stats', None)
            if not my_stats:
                return 0.0

            for opp_pokemon in opp_team.members:
                opp_stats = getattr(opp_pokemon, 'stats', None)
                if not opp_stats:
                    continue

                my_speed = my_stats[Stat.SPEED]
                opp_speed = opp_stats[Stat.SPEED]

                if my_speed > opp_speed * 1.1:
                    score += 50

                my_offense = max(my_stats[Stat.ATTACK], my_stats[Stat.SPECIAL_ATTACK])
                opp_hp = opp_stats[Stat.MAX_HP]
                opp_defense = min(opp_stats[Stat.DEFENSE], opp_stats[Stat.SPECIAL_DEFENSE])

                damage_potential = my_offense * 2.5 / (opp_defense * 0.01)
                if damage_potential >= opp_hp:
                    score += 100

        except Exception:
            pass

        return score

    def _ensure_speed_diversity(self, pokemon_scores, my_team, max_size):
        """스피드 다양성 보장"""
        selected = []
        speed_tiers = []

        for idx, score in pokemon_scores:
            if len(selected) >= max_size:
                break

            pokemon = my_team.members[idx]
            stats = getattr(pokemon, 'stats', None)
            if not stats:
                selected.append(idx)
                continue

            speed = stats[Stat.SPEED]

            if speed >= 120:
                tier = "HYPER_SPEED"
            elif speed >= 100:
                tier = "HIGH_SPEED"
            elif speed >= 85:
                tier = "MID_SPEED"
            else:
                tier = "LOW_SPEED"

            tier_count = speed_tiers.count(tier)
            if tier_count >= 2 and tier != "HYPER_SPEED":
                continue

            selected.append(idx)
            speed_tiers.append(tier)

        while len(selected) < max_size and len(selected) < len(my_team.members):
            for idx, _ in pokemon_scores:
                if idx not in selected:
                    selected.append(idx)
                    break

        return selected


class JirachiChampionshipSelectionPolicy(SelectionPolicy):
    """지라치 Championship Track 전용 선택 정책 - 화력 극대화"""

    def __init__(self):
        # 팀 구성 정보 (팀빌더에서 설정)
        self.team_roles = {
            'main_setter': None,  # 1명: 최고속 환경 설치자
            'main_attackers': [],  # 2명: 환경 부스트 어태커
            'flex_attacker': None,  # 1명: 환경 독립 어태커
            'psychic_counter': None,  # 1명: 사이코 카운터
            'type_counter': None  # 1명: 타입 카운터
        }

        # 타입 상성표
        self.super_effective_map = {
            Type.WATER: [Type.FIRE, Type.GROUND, Type.ROCK],
            Type.ELECTRIC: [Type.WATER, Type.FLYING],
            Type.GRASS: [Type.WATER, Type.GROUND, Type.ROCK],
            Type.FIRE: [Type.GRASS, Type.ICE, Type.BUG, Type.STEEL],
            Type.ICE: [Type.GRASS, Type.GROUND, Type.FLYING, Type.DRAGON],
            Type.FIGHT: [Type.NORMAL, Type.ICE, Type.ROCK, Type.DARK, Type.STEEL],
            Type.POISON: [Type.GRASS, Type.FAIRY],
            Type.GROUND: [Type.FIRE, Type.ELECTRIC, Type.POISON, Type.ROCK, Type.STEEL],
            Type.FLYING: [Type.GRASS, Type.FIGHT, Type.BUG],
            Type.PSYCHIC: [Type.FIGHT, Type.POISON],
            Type.BUG: [Type.GRASS, Type.PSYCHIC, Type.DARK],
            Type.ROCK: [Type.FIRE, Type.ICE, Type.FLYING, Type.BUG],
            Type.GHOST: [Type.PSYCHIC, Type.GHOST],
            Type.DRAGON: [Type.DRAGON],
            Type.DARK: [Type.PSYCHIC, Type.GHOST],
            Type.STEEL: [Type.ICE, Type.ROCK, Type.FAIRY],
            Type.FAIRY: [Type.FIGHT, Type.DRAGON, Type.DARK]
        }

        print("🏆 Jirachi Championship Selection Policy Initialized")
        print("🎯 Strategy: 3가지 명확한 전략 (사이코 긴급 0.8+ / 타입 불리 0.7+ / 환경 극대화)")

    def decision(self, teams: Tuple[Team, Team], max_size: int = 4) -> SelectionCommand:
        """화력 극대화 기반 4명 선택 - 3가지 전략"""
        try:
            my_team, opp_team = teams

            if len(my_team.members) <= max_size:
                return list(range(len(my_team.members)))

            # 위협 분석
            psychic_threat = self._detect_psychic_threat(opp_team)
            type_threat = self._detect_type_threat(my_team, opp_team)

            # 전략 선택
            if psychic_threat >= 0.8:
                strategy = "PSYCHIC_EMERGENCY"
            elif type_threat >= 0.7:
                strategy = "TYPE_COUNTER_FOCUS"
            else:
                strategy = "MAXIMIZE_ENVIRONMENT"

            # 전략에 따른 4명 선택
            selected_4 = self._select_team_by_strategy(strategy, psychic_threat, type_threat)

            print(f"🎯 Selection Strategy: {strategy}")
            print(f"📊 Threats - Psychic: {psychic_threat:.2f}, Type: {type_threat:.2f}")
            print(f"👥 Selected Team (4): {selected_4}")

            return selected_4

        except Exception as e:
            print(f"❌ Championship selection error: {e}")
            return list(range(min(max_size, len(teams[0].members))))

    def _detect_psychic_threat(self, opp_team) -> float:
        """사이코필드/에스퍼 타입 위협 감지"""
        threat_score = 0.0

        for pokemon in opp_team.members:
            # 포켓몬 타입 체크
            pokemon_types = getattr(pokemon, 'types', [])
            if Type.PSYCHIC in pokemon_types:
                threat_score += 0.15

            # 기술 체크
            moves = getattr(pokemon, 'moves', [])
            for move in moves:
                field_start = getattr(move, 'field_start', Terrain.NONE)
                if field_start == Terrain.PSYCHIC_TERRAIN:
                    threat_score += 0.5

                move_type = getattr(move, 'pkm_type', Type.NORMAL)
                base_power = getattr(move, 'base_power', 0)
                if move_type == Type.PSYCHIC:
                    if base_power >= 100:
                        threat_score += 0.2
                    elif base_power >= 80:
                        threat_score += 0.15

                if field_start == Terrain.PSYCHIC_TERRAIN:
                    speed = getattr(pokemon, 'stats', {}).get(Stat.SPEED, 0)
                    if speed >= 120:
                        threat_score += 0.3

        return min(1.0, threat_score)

    def _detect_type_threat(self, my_team, opp_team) -> float:
        """타입 상성 불리 위협 감지"""
        my_main_types = self._analyze_my_main_types(my_team)

        counter_move_count = 0
        total_threatening_moves = 0

        for opp_pokemon in opp_team.members:
            moves = getattr(opp_pokemon, 'moves', [])

            for move in moves:
                move_type = getattr(move, 'pkm_type', Type.NORMAL)
                base_power = getattr(move, 'base_power', 0)

                if base_power >= 80:
                    total_threatening_moves += 1

                    if self._is_counter_move(move_type, list(my_main_types.keys()), base_power):
                        if base_power >= 120:
                            counter_move_count += 1.5
                        else:
                            counter_move_count += 1

        if total_threatening_moves == 0:
            return 0.0

        threat_ratio = counter_move_count / total_threatening_moves
        return min(1.0, threat_ratio)

    def _analyze_my_main_types(self, my_team) -> Dict[Type, int]:
        """내 팀의 주력 타입 분석"""
        type_count = defaultdict(int)

        for pokemon in my_team.members:
            pokemon_types = getattr(pokemon, 'types', [])
            for ptype in pokemon_types:
                type_count[ptype] += 2

            moves = getattr(pokemon, 'moves', [])
            for move in moves:
                move_type = getattr(move, 'pkm_type', Type.NORMAL)
                base_power = getattr(move, 'base_power', 0)

                if base_power >= 80:
                    type_count[move_type] += 1

        return dict(type_count)

    def _is_counter_move(self, move_type: Type, target_types: List[Type], base_power: int) -> bool:
        """카운터 기술 판정"""
        effective_against = self.super_effective_map.get(move_type, [])
        is_super_effective = any(target_type in effective_against for target_type in target_types)

        return (is_super_effective and base_power >= 60) or (base_power >= 100)

    def _select_team_by_strategy(self, strategy: str, psychic_threat: float, type_threat: float) -> List[int]:
        """전략별 4명 선택"""

        if strategy == "PSYCHIC_EMERGENCY":
            return self._psychic_emergency_selection()
        elif strategy == "TYPE_COUNTER_FOCUS":
            return self._type_counter_focus_selection()
        else:  # MAXIMIZE_ENVIRONMENT
            return self._maximize_environment_selection()

    def _psychic_emergency_selection(self) -> List[int]:
        """사이코필드 긴급 대응"""
        selection = []

        if self.team_roles['psychic_counter'] is not None:
            selection.append(self.team_roles['psychic_counter'])

        if self.team_roles['flex_attacker'] is not None:
            selection.append(self.team_roles['flex_attacker'])

        if self.team_roles['main_attackers']:
            best_attacker = max(self.team_roles['main_attackers'],
                                key=lambda x: self._get_pokemon_firepower(x))
            selection.append(best_attacker)

        if len(selection) < 4 and self.team_roles['main_setter'] is not None:
            selection.append(self.team_roles['main_setter'])

        return self._pad_selection_to_4(selection)

    def _type_counter_focus_selection(self) -> List[int]:
        """타입 카운터 중심"""
        selection = []

        if self.team_roles['type_counter'] is not None:
            selection.append(self.team_roles['type_counter'])

        if self.team_roles['flex_attacker'] is not None:
            selection.append(self.team_roles['flex_attacker'])

        for attacker in self.team_roles['main_attackers']:
            if len(selection) < 4:
                selection.append(attacker)

        if len(selection) < 4 and self.team_roles['main_setter'] is not None:
            selection.append(self.team_roles['main_setter'])

        return self._pad_selection_to_4(selection)

    def _maximize_environment_selection(self) -> List[int]:
        """환경 극대화"""
        selection = []

        if self.team_roles['main_setter'] is not None:
            selection.append(self.team_roles['main_setter'])

        for attacker in self.team_roles['main_attackers']:
            if len(selection) < 4:
                selection.append(attacker)

        if len(selection) < 4 and self.team_roles['flex_attacker'] is not None:
            selection.append(self.team_roles['flex_attacker'])

        if len(selection) < 4:
            if self.team_roles['psychic_counter'] is not None:
                selection.append(self.team_roles['psychic_counter'])
            elif self.team_roles['type_counter'] is not None:
                selection.append(self.team_roles['type_counter'])

        return self._pad_selection_to_4(selection)

    def _pad_selection_to_4(self, selection: List[int]) -> List[int]:
        """선택이 4명 미만이면 나머지로 채움"""
        if len(selection) >= 4:
            return selection[:4]

        all_roles = []
        for role_pokemon in self.team_roles.values():
            if isinstance(role_pokemon, list):
                all_roles.extend([p for p in role_pokemon if p is not None])
            elif role_pokemon is not None:
                all_roles.append(role_pokemon)

        for pokemon_idx in all_roles:
            if len(selection) >= 4:
                break
            if pokemon_idx not in selection:
                selection.append(pokemon_idx)

        idx = 0
        while len(selection) < 4:
            if idx not in selection:
                selection.append(idx)
            idx += 1
            if idx >= 6:
                break

        return selection[:4]

    def _get_pokemon_firepower(self, pokemon_idx: int) -> float:
        """포켓몬 화력 추정"""
        return 1000 - pokemon_idx * 10

    def set_team_roles(self, roles: Dict):
        """팀빌더에서 역할 배정 결과 설정"""
        self.team_roles = roles
        print(f"🏗️ Team roles updated: {roles}")


# 메인 정책 클래스들
class SmartJirachiBattlePolicy(AlwaysSmartBeamSearchPolicy):
    """Smart Beam Search 기반 지라치 AI (Battle Track)"""

    def __init__(self, beam_width: int = 3, max_depth: int = 2, time_limit_ms: int = 70):
        super().__init__(time_limit_ms, is_championship=False)
        self.default_beam_width = beam_width
        self.default_max_depth = max_depth

        print("🌟 Smart Jirachi Battle AI Initialized")
        print(f"Config: DefaultBeam={beam_width}, DefaultDepth={max_depth}, Time={time_limit_ms}ms")


class SmartJirachiChampionshipPolicy(AlwaysSmartBeamSearchPolicy):
    """Smart Beam Search 기반 지라치 AI (Championship Track)"""

    def __init__(self, beam_width: int = 3, max_depth: int = 2, time_limit_ms: int = 70):
        super().__init__(time_limit_ms, is_championship=True)
        self.default_beam_width = beam_width
        self.default_max_depth = max_depth

        print("🏆 Smart Jirachi Championship AI Initialized")
        print(f"Config: DefaultBeam={beam_width}, DefaultDepth={max_depth}, Time={time_limit_ms}ms")


# 기존 호환성을 위한 클래스들 (자동 업그레이드)
class JirachiBattlePolicy(SmartJirachiBattlePolicy):
    """기존 지라치 정책 (Smart 버전으로 자동 업그레이드)"""

    def __init__(self):
        super().__init__(beam_width=2, max_depth=1, time_limit_ms=50)


class EnhancedJirachiBattlePolicy(SmartJirachiBattlePolicy):
    """Enhanced 지라치 정책 (Smart 버전으로 자동 업그레이드)"""

    def __init__(self):
        super().__init__(beam_width=3, max_depth=2, time_limit_ms=70)


# 기존 호환성을 위한 별칭
class JirachiSelectionPolicy(JirachiBattleSelectionPolicy):
    """기존 호환성을 위한 별칭 (Battle Track 정책)"""
    pass


# MaxFirepower 별칭 추가
MaxFirepowerSelectionPolicy = JirachiChampionshipSelectionPolicy
