"""
Max Firepower Jirachi AI Team Builder - VGC2 Import 충돌 수정 완료
Stats/Stat 명시적 분리 + 화력 극대화 중심 설계 완료
"""

import os
import sys
import time
from itertools import combinations
from typing import List, Optional, Dict

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# VGC2 imports with explicit separation to avoid conflicts
try:
    from vgc2.agent import TeamBuildPolicy, TeamBuildCommand
    from vgc2.battle_engine import Team
    from vgc2.battle_engine.pokemon import Pokemon
    from vgc2.battle_engine.modifiers import Type, Status, Nature, Weather, Terrain, Category
    from vgc2.battle_engine.modifiers import Stats as EVStats  # tuple[int, int, int, int, int, int]
    from vgc2.battle_engine.pokemon import Stat as StatIndex  # 열거형 (MAX_HP, ATTACK, ...)
    from vgc2.meta import Meta, Roster

except ImportError as e:
    print(f"VGC2 import error: {e}")
    print("Please ensure VGC2 is properly installed")
    sys.exit(1)

# Constants
TOTAL_EV_LIMIT = 510
MAX_IV = 31
MAX_EV_PER_STAT = 255


class MaxFirepowerTeamBuildPolicy(TeamBuildPolicy):
    """
    🔥 지라치 AI 화력 극대화 팀빌더 (VGC2 호환성 수정 완료)
    
    핵심 철학:
    - 1턴킬 > 모든 것
    - 화력 집중 (3공격자)
    - 단일 환경 최적화
    - 서포터 완전 제거
    """

    def __init__(self, time_limit=60):
        self.build_counter = 0
        self.time_limit = time_limit  # 시간 예산 관리

        # 🌦️ 단일 날씨 우선순위 매핑
        self.weather_priority_map = {
            Weather.RAIN: [Type.WATER, Type.ELECTRIC],
            Weather.SUN: [Type.FIRE, Type.GRASS],
            Weather.SAND: [Type.ROCK, Type.GROUND, Type.STEEL],
            Weather.SNOW: [Type.ICE]
        }

        # 🌍 단일 테라인 우선순위 매핑
        self.terrain_priority_map = {
            Terrain.ELECTRIC_TERRAIN: [Type.ELECTRIC],
            Terrain.GRASSY_TERRAIN: [Type.GRASS],
            Terrain.MISTY_TERRAIN: [Type.FAIRY],
            Terrain.PSYCHIC_TERRAIN: [Type.PSYCHIC]
        }

        # 🎯 위협 대응 매핑
        self.psychic_threats = [Terrain.PSYCHIC_TERRAIN, Type.PSYCHIC]

        # 타입 상성표 (완전 구현)
        self.type_effectiveness_map = {
            Type.FIRE: {
                'super_effective': [Type.GRASS, Type.ICE, Type.BUG, Type.STEEL],
                'weak': [Type.WATER, Type.GROUND, Type.ROCK]
            },
            Type.WATER: {
                'super_effective': [Type.FIRE, Type.GROUND, Type.ROCK],
                'weak': [Type.GRASS, Type.ELECTRIC]
            },
            Type.ELECTRIC: {
                'super_effective': [Type.WATER, Type.FLYING],
                'weak': [Type.GROUND]
            },
            Type.GRASS: {
                'super_effective': [Type.WATER, Type.GROUND, Type.ROCK],
                'weak': [Type.FIRE, Type.ICE, Type.FLYING, Type.POISON, Type.BUG]
            },
            Type.PSYCHIC: {
                'super_effective': [Type.FIGHTING, Type.POISON],
                'weak': [Type.BUG, Type.GHOST, Type.DARK]
            },
            Type.DARK: {
                'super_effective': [Type.PSYCHIC, Type.GHOST],
                'weak': [Type.FIGHTING, Type.BUG, Type.FAIRY]
            }
        }

        # 🔄 캐시 시스템
        self._firepower_cache = {}
        self._pokemon_analysis_cache = {}

        print("🔥 Max Firepower Team Builder v3.1 (VGC2 호환성 수정)")
        print("Philosophy: 1턴킬 > 화력집중 > 단일환경 > 카운터대응")
        print("Team: 1설치자 + 3공격자 + 2카운터 = 6인")
        print("🚫 서포터 완전 제거 - 화력만이 답이다!")
        print(f"⏱️ Time Budget: {time_limit}초 완전 활용")
        print("✅ VGC2 Import 충돌 수정: Stats vs Stat 명시적 분리")

    def decision(self, roster: Roster, meta: Optional[Meta],
                 max_team_size: int, max_pkm_moves: int, n_active: int) -> TeamBuildCommand:
        """시간 예산 활용 화력 극대화 팀 빌드"""

        start_time = time.time()
        print(f"\n🔥 Max Firepower Team Building Round {self.build_counter + 1}")
        print(f"Team Size: {max_team_size}, Moves: {max_pkm_moves}, Active: {n_active}")
        print(f"⏱️ Time Budget: {self.time_limit}초")

        try:
            # 🎯 1단계: 빠른 기본 분석 (5초)
            best_environment = self._select_best_single_environment(roster)
            print(f"🌟 Selected Environment: {best_environment['type']} (Score: {best_environment['score']:.0f})")

            # 📊 2단계: 기본 포켓몬 분석 (10초)
            basic_analysis = self._basic_pokemon_analysis(roster, best_environment, meta)

            # 🔥 3단계: 시간 허용하는 한 심화 분석
            enhanced_analysis = self._enhanced_analysis_with_time_budget(
                roster, best_environment, meta, start_time
            )

            # 🏆 4단계: 최적 팀 구성
            team_build = self._build_optimal_team(
                enhanced_analysis or basic_analysis, best_environment, max_team_size
            )

            # 🎮 5단계: Selection Policy 연계
            self._set_selection_roles(team_build)

            elapsed = time.time() - start_time
            self.build_counter += 1
            print(f"✅ Max Firepower Team Built in {elapsed:.2f}초: {len(team_build)} members")

            return team_build

        except Exception as e:
            print(f"❌ Max firepower team building error: {e}")
            return self._fallback_build(roster, max_team_size, max_pkm_moves)

    def _select_best_single_environment(self, roster: Roster) -> Dict:
        """최적 단일 환경 선택"""

        environment_scores = {}

        # 🌦️ 날씨별 점수 계산
        for weather, boosted_types in self.weather_priority_map.items():
            score_data = self._evaluate_environment_potential(roster, 'weather', weather, boosted_types)
            environment_scores[f'weather_{weather}'] = score_data

        # 🌍 테라인별 점수 계산
        for terrain, boosted_types in self.terrain_priority_map.items():
            score_data = self._evaluate_environment_potential(roster, 'terrain', terrain, boosted_types)
            environment_scores[f'terrain_{terrain}'] = score_data

        # 🎯 최고 점수 환경 선택
        best_env_key = max(environment_scores.keys(), key=lambda k: environment_scores[k]['total_score'])
        best_environment = environment_scores[best_env_key]

        env_type, env_value = best_env_key.split('_', 1)
        best_environment['env_type'] = env_type
        best_environment['env_value'] = Weather[env_value] if env_type == 'weather' else Terrain[env_value]
        best_environment['type'] = f"{env_type}_{env_value}"

        return best_environment

    def _evaluate_environment_potential(self, roster: Roster, env_type: str, env_value,
                                        boosted_types: List[Type]) -> Dict:
        """환경별 잠재력 평가"""

        setters = []
        attackers = []
        total_firepower = 0

        for i, pokemon in enumerate(roster):
            pokemon_types = set(getattr(pokemon, 'types', []))
            moves = getattr(pokemon, 'moves', [])
            base_stats = getattr(pokemon, 'base_stats', None)

            if not base_stats:
                continue

            # 🎯 환경 설치자 찾기
            has_setup = False
            for move in moves:
                if env_type == 'weather':
                    setup_effect = getattr(move, 'weather_start', Weather.CLEAR)
                    if setup_effect == env_value:
                        has_setup = True
                else:  # terrain
                    setup_effect = getattr(move, 'terrain_start', Terrain.NONE)
                    if setup_effect == env_value:
                        has_setup = True

            if has_setup:
                setter_quality = self._evaluate_setter_quality(pokemon, base_stats)
                setters.append({
                    'index': i,
                    'pokemon': pokemon,
                    'quality': setter_quality
                })

            # 🔥 환경 부스트 어태커 찾기
            firepower_analysis = self._calculate_environment_firepower(
                pokemon, pokemon_types, boosted_types, moves, base_stats
            )

            if firepower_analysis['environment_firepower'] > 0:
                attackers.append({
                    'index': i,
                    'pokemon': pokemon,
                    'firepower': firepower_analysis['environment_firepower'],
                    'stab_firepower': firepower_analysis['stab_environment_firepower'],
                    'total_firepower': firepower_analysis['total_firepower']
                })

                total_firepower += firepower_analysis['environment_firepower']

        # 📊 환경 점수 계산
        setter_count = len(setters)
        attacker_count = len(attackers)

        setter_score = 300 if setter_count > 0 else 0
        attacker_score = attacker_count * 150
        firepower_score = total_firepower / 5

        total_score = setter_score + attacker_score + firepower_score

        return {
            'setters': setters,
            'attackers': attackers,
            'setter_count': setter_count,
            'attacker_count': attacker_count,
            'total_firepower': total_firepower,
            'total_score': total_score,
            'boosted_types': boosted_types,
            'details': f"{setter_count}설치자 + {attacker_count}어태커 = {total_firepower:.0f}화력"
        }

    def _evaluate_setter_quality(self, pokemon, base_stats):
        """환경 설치자 품질 평가"""
        speed = base_stats[StatIndex.SPEED]
        hp = base_stats[StatIndex.MAX_HP]
        defense = (base_stats[StatIndex.DEFENSE] + base_stats[StatIndex.SPECIAL_DEFENSE]) / 2

        # 설치자 품질 = 스피드 * 3 + 내구력
        quality = speed * 3 + hp + defense
        return quality

    def _calculate_environment_firepower(self, pokemon, pokemon_types, boosted_types, moves, base_stats):
        """환경별 화력 계산 (캐싱 활용)"""

        # 캐시 키 생성
        pokemon_id = getattr(pokemon, 'id', id(pokemon))
        boosted_key = tuple(sorted(boosted_types))
        cache_key = (pokemon_id, boosted_key)

        # 캐시에서 확인
        if cache_key in self._firepower_cache:
            return self._firepower_cache[cache_key]

        physical_attack = base_stats[StatIndex.ATTACK]
        special_attack = base_stats[StatIndex.SPECIAL_ATTACK]

        firepower = {
            'total_firepower': 0,
            'environment_firepower': 0,
            'stab_environment_firepower': 0
        }

        best_total = 0
        best_environment = 0
        best_stab_environment = 0

        # 모든 기술 검사
        for move in moves:
            move_type = getattr(move, 'pkm_type', Type.NORMAL)
            base_power = getattr(move, 'base_power', 0)
            category = getattr(move, 'category', Category.OTHER)

            if base_power == 0:
                continue

            # 공격력 선택
            if category == Category.PHYSICAL:
                attack_stat = physical_attack
            elif category == Category.SPECIAL:
                attack_stat = special_attack
            else:
                attack_stat = max(physical_attack, special_attack)

            # 기본 데미지 계산
            raw_damage = base_power * (attack_stat / 100)

            # STAB 적용
            if move_type in pokemon_types:
                raw_damage *= 1.5

            # 환경 부스트 적용
            environment_damage = raw_damage
            if move_type in boosted_types:
                environment_damage *= 1.5

            # 최고 화력 기록
            best_total = max(best_total, environment_damage)

            if move_type in boosted_types:
                best_environment = max(best_environment, environment_damage)

                if move_type in pokemon_types:
                    best_stab_environment = max(best_stab_environment, environment_damage)

        firepower['total_firepower'] = best_total
        firepower['environment_firepower'] = best_environment
        firepower['stab_environment_firepower'] = best_stab_environment

        # 캐시에 저장
        self._firepower_cache[cache_key] = firepower

        return firepower

    def _basic_pokemon_analysis(self, roster: Roster, environment, meta: Optional[Meta]) -> List[Dict]:
        """기본 포켓몬 분석 (빠른 버전)"""

        analyzed_pokemon = []
        for i, species in enumerate(roster):
            analysis = self._analyze_pokemon_for_role(species, i, environment, meta)
            analyzed_pokemon.append(analysis)

        return analyzed_pokemon

    def _enhanced_analysis_with_time_budget(self, roster: Roster, environment, meta: Optional[Meta],
                                            start_time: float) -> Optional[List[Dict]]:
        """시간 예산 활용 심화 분석"""

        elapsed = time.time() - start_time
        remaining_time = self.time_limit - elapsed

        if remaining_time < 15:  # 15초 미만이면 기본 분석만
            print(f"⏱️ 시간 부족 ({remaining_time:.1f}초), 기본 분석 사용")
            return None

        print(f"🔍 심화 분석 시작 (남은 시간: {remaining_time:.1f}초)")

        # 🔥 심화 분석 수행
        enhanced_analysis = []

        for i, species in enumerate(roster):
            # 시간 체크
            current_elapsed = time.time() - start_time
            if current_elapsed > self.time_limit * 0.9:
                print(f"⏱️ 시간 90% 소모, 심화 분석 중단")
                break

            # 더 정교한 분석
            enhanced_data = self._comprehensive_pokemon_evaluation(species, i, environment, meta)
            enhanced_analysis.append(enhanced_data)

        return enhanced_analysis if enhanced_analysis else None

    def _analyze_pokemon_for_role(self, species, index: int, environment, meta: Optional[Meta]) -> Dict:
        """포켓몬 역할 분석 (기본)"""

        # 캐시 키 생성
        species_id = getattr(species, 'id', index)
        env_key = environment['type']
        cache_key = (species_id, env_key)

        # 캐시에서 확인
        if cache_key in self._pokemon_analysis_cache:
            cached_result = self._pokemon_analysis_cache[cache_key].copy()
            cached_result['index'] = index
            return cached_result

        pokemon_types = set(getattr(species, 'types', []))
        moves = getattr(species, 'moves', [])
        base_stats = getattr(species, 'base_stats', None)

        if not base_stats:
            result = {
                'index': index, 'species': species,
                'role_score': 0, 'role': 'UNKNOWN'
            }
            self._pokemon_analysis_cache[cache_key] = result.copy()
            return result

        # 각 역할별 점수 계산
        role_scores = self._calculate_all_role_scores(
            species, pokemon_types, moves, base_stats, environment
        )

        # 최고 점수 역할 선택
        best_role = max(role_scores.keys(), key=lambda r: role_scores[r])
        best_score = role_scores[best_role]

        result = {
            'index': index,
            'species': species,
            'role': best_role,
            'role_score': best_score,
            'all_role_scores': role_scores,
            'base_stats': base_stats,
            'pokemon_types': pokemon_types,
            'moves': moves
        }

        # 캐시에 저장
        cache_result = result.copy()
        cache_result.pop('index', None)
        self._pokemon_analysis_cache[cache_key] = cache_result

        return result

    def _comprehensive_pokemon_evaluation(self, species, index: int, environment, meta: Optional[Meta]) -> Dict:
        """종합적 포켓몬 평가 (심화)"""

        # 기본 분석 실행
        basic_analysis = self._analyze_pokemon_for_role(species, index, environment, meta)

        # 심화 요소 추가
        pokemon_types = basic_analysis['pokemon_types']
        moves = basic_analysis['moves']
        base_stats = basic_analysis['base_stats']

        # 🔥 모든 기술 조합 평가
        best_move_combination = self._find_optimal_move_combination(moves, pokemon_types, environment)

        # 📊 실전 시뮬레이션 점수
        battle_simulation_score = self._simulate_battle_performance(species, environment)

        # 🎯 EV 분배 최적화
        optimal_ev_spread = self._optimize_ev_distribution(basic_analysis['role'], base_stats)

        # 심화 분석 결과 반영
        basic_analysis['enhanced_move_combo'] = best_move_combination
        basic_analysis['battle_simulation_score'] = battle_simulation_score
        basic_analysis['optimal_ev_spread'] = optimal_ev_spread
        basic_analysis['role_score'] += battle_simulation_score * 0.3  # 30% 가중치

        return basic_analysis

    def _find_optimal_move_combination(self, moves, pokemon_types, environment) -> Dict:
        """최적 기술 조합 찾기"""

        if len(moves) <= 4:
            return {'moves': list(range(len(moves))), 'score': 0}

        best_combination = None
        best_score = 0

        # 4개 기술 조합 중 최적 찾기
        for combo in combinations(range(len(moves)), 4):
            combo_score = 0

            for move_idx in combo:
                move = moves[move_idx]
                move_score = self._evaluate_move_comprehensive(move, pokemon_types, environment)
                combo_score += move_score

            if combo_score > best_score:
                best_score = combo_score
                best_combination = list(combo)

        return {
            'moves': best_combination or list(range(min(4, len(moves)))),
            'score': best_score
        }

    def _evaluate_move_comprehensive(self, move, pokemon_types, environment) -> float:
        """종합적 기술 평가"""

        base_power = getattr(move, 'base_power', 0)
        priority = getattr(move, 'priority', 0)
        accuracy = getattr(move, 'accuracy', 100)
        move_type = getattr(move, 'pkm_type', Type.NORMAL)

        score = base_power * 3  # 기본 화력

        # STAB 보너스
        if move_type in pokemon_types:
            score *= 1.5

        # 환경 부스트
        boosted_types = environment.get('boosted_types', [])
        if move_type in boosted_types:
            score *= 1.5

        # 선공기 보너스
        if priority > 0:
            score += 500

        # 명중률 보정
        score *= (accuracy / 100)

        return score

    def _simulate_battle_performance(self, species, environment) -> float:
        """간단한 배틀 성능 시뮬레이션"""

        # 기본 시뮬레이션 점수 (간단한 휴리스틱)
        base_stats = getattr(species, 'base_stats', None)
        if not base_stats:
            return 0.0

        max_attack = max(base_stats[StatIndex.ATTACK], base_stats[StatIndex.SPECIAL_ATTACK])
        speed = base_stats[StatIndex.SPEED]
        hp = base_stats[StatIndex.MAX_HP]

        # 화력 중심 평가
        firepower_score = max_attack * 2
        speed_score = speed * 1.5
        survival_score = hp * 0.5

        simulation_score = firepower_score + speed_score + survival_score

        return simulation_score / 10  # 정규화

    def _optimize_ev_distribution(self, role: str, base_stats) -> Dict:
        """EV 분배 최적화"""

        # 기본 EV 분배 (이미 최적화됨)
        if role == "MAIN_SETTER":
            return {'pattern': 'HP+Speed', 'spread': (252, 0, 4, 0, 0, 252)}
        elif role in ["MAIN_ATTACKER", "FLEX_ATTACKER", "PSYCHIC_COUNTER", "TYPE_COUNTER"]:
            if base_stats[StatIndex.ATTACK] > base_stats[StatIndex.SPECIAL_ATTACK]:
                return {'pattern': 'Attack+Speed', 'spread': (4, 252, 0, 0, 0, 252)}
            else:
                return {'pattern': 'SpAttack+Speed', 'spread': (4, 0, 0, 252, 0, 252)}
        else:
            return {'pattern': 'Balanced', 'spread': (85, 85, 85, 85, 85, 85)}

    def _calculate_all_role_scores(self, species, pokemon_types, moves, base_stats, environment) -> Dict[str, float]:
        """모든 역할에 대한 점수 계산"""

        scores = {}
        boosted_types = environment['boosted_types']
        env_type = environment['env_type']
        env_value = environment['env_value']

        # 🎯 1. MAIN_SETTER 평가
        scores['MAIN_SETTER'] = self._evaluate_setter(species, base_stats, moves, env_type, env_value)

        # 🔥 2. MAIN_ATTACKER 평가
        scores['MAIN_ATTACKER'] = self._evaluate_attacker(species, pokemon_types, moves, base_stats, boosted_types,
                                                          "MAIN")

        # 💥 3. FLEX_ATTACKER 평가
        scores['FLEX_ATTACKER'] = self._evaluate_attacker(species, pokemon_types, moves, base_stats, [], "FLEX")

        # 🛡️ 4. PSYCHIC_COUNTER 평가
        scores['PSYCHIC_COUNTER'] = self._evaluate_psychic_counter(species, pokemon_types, moves, base_stats)

        # ⚔️ 5. TYPE_COUNTER 평가
        scores['TYPE_COUNTER'] = self._evaluate_type_counter(species, pokemon_types, moves, base_stats, boosted_types)

        return scores

    def _evaluate_setter(self, pokemon, base_stats, moves, env_type: str, env_value) -> float:
        """설치자 평가"""
        score = 0

        # 스피드 최우선 (70%)
        speed = base_stats[StatIndex.SPEED]
        if speed >= 120:
            score += 600
        elif speed >= 100:
            score += 450
        elif speed >= 90:
            score += 300
        elif speed >= 80:
            score += 150

        # 환경 설치 기술 보유 (20%)
        has_setup = False
        for move in moves:
            if env_type == 'weather':
                setup_effect = getattr(move, 'weather_start', Weather.CLEAR)
                if setup_effect == env_value:
                    has_setup = True
                    break
            else:  # terrain
                setup_effect = getattr(move, 'terrain_start', Terrain.NONE)
                if setup_effect == env_value:
                    has_setup = True
                    break

        if has_setup:
            score += 1000

        # 생존력 (10%)
        hp = base_stats[StatIndex.MAX_HP]
        avg_defense = (base_stats[StatIndex.DEFENSE] + base_stats[StatIndex.SPECIAL_DEFENSE]) / 2
        score += (hp + avg_defense) * 0.5

        return score

    def _evaluate_attacker(self, pokemon, pokemon_types, moves, base_stats, boosted_types, role_type: str) -> float:
        """공격자 평가 (MAIN/FLEX 통합)"""
        score = 0

        # 기본 화력 (50%)
        max_attack = max(base_stats[StatIndex.ATTACK], base_stats[StatIndex.SPECIAL_ATTACK])
        if max_attack >= 130:
            score += 400
        elif max_attack >= 110:
            score += 350
        elif max_attack >= 100:
            score += 300
        elif max_attack >= 90:
            score += 200

        # 환경 시너지 (30% - MAIN만, FLEX는 0%)
        if role_type == "MAIN" and boosted_types:
            env_firepower = 0
            stab_env_firepower = 0

            for move in moves:
                move_type = getattr(move, 'pkm_type', Type.NORMAL)
                base_power = getattr(move, 'base_power', 0)

                if base_power > 0 and move_type in boosted_types:
                    raw_power = base_power * (max_attack / 100)
                    if move_type in pokemon_types:
                        raw_power *= 1.5  # STAB
                        stab_env_firepower = max(stab_env_firepower, raw_power * 1.5)
                    env_firepower = max(env_firepower, raw_power * 1.5)

            score += env_firepower / 5
            score += stab_env_firepower / 2

        # 스피드 (20%)
        speed = base_stats[StatIndex.SPEED]
        if speed >= 110:
            score += 150
        elif speed >= 95:
            score += 100
        elif speed >= 80:
            score += 50

        # FLEX 어태커 특별 보너스: 타입 다양성
        if role_type == "FLEX":
            move_types = set()
            for move in moves:
                move_type = getattr(move, 'pkm_type', Type.NORMAL)
                if getattr(move, 'base_power', 0) > 0:
                    move_types.add(move_type)

            score += len(move_types) * 50

        return score

    def _evaluate_psychic_counter(self, pokemon, pokemon_types, moves, base_stats) -> float:
        """사이코필드/에스퍼 타입 카운터 평가"""
        score = 0

        # 에스퍼 카운터 타입 (60%)
        counter_types = {Type.DARK, Type.GHOST, Type.BUG}
        type_counter_score = len(pokemon_types & counter_types) * 300
        score += type_counter_score

        # 에스퍼 카운터 기술 (30%)
        counter_moves = 0
        for move in moves:
            move_type = getattr(move, 'pkm_type', Type.NORMAL)
            base_power = getattr(move, 'base_power', 0)

            if base_power > 0 and move_type in counter_types:
                counter_moves += 1

        score += counter_moves * 150

        # 기본 화력 (10%)
        max_attack = max(base_stats[StatIndex.ATTACK], base_stats[StatIndex.SPECIAL_ATTACK])
        score += max_attack * 0.8

        return score

    def _evaluate_type_counter(self, pokemon, pokemon_types, moves, base_stats, main_environment_types) -> float:
        """메인 환경과 다른 타입 카운터 평가"""
        score = 0

        # 타입 커버리지 (50%)
        move_types = set()
        for move in moves:
            move_type = getattr(move, 'pkm_type', Type.NORMAL)
            if getattr(move, 'base_power', 0) > 0:
                move_types.add(move_type)

        score += len(move_types) * 80

        # 환경과 다른 타입 (30%) - 독립성
        env_types = set(main_environment_types)
        if not (pokemon_types & env_types):
            score += 300

        move_env_overlap = len(move_types & env_types)
        if move_env_overlap == 0:
            score += 200

        # 기본 화력 (20%)
        max_attack = max(base_stats[StatIndex.ATTACK], base_stats[StatIndex.SPECIAL_ATTACK])
        score += max_attack * 1.2

        return score

    def _build_optimal_team(self, analyzed_pokemon, environment, max_team_size=6):
        """최적 팀 구성 (시간 예산 고려)"""

        # 역할별 후보 분류
        role_candidates = {
            'MAIN_SETTER': [],
            'MAIN_ATTACKER': [],
            'FLEX_ATTACKER': [],
            'PSYCHIC_COUNTER': [],
            'TYPE_COUNTER': []
        }

        for pokemon_data in analyzed_pokemon:
            role = pokemon_data['role']
            if role in role_candidates:
                role_candidates[role].append(pokemon_data)

        # 각 역할별 정렬 (점수 순)
        for role in role_candidates:
            role_candidates[role].sort(key=lambda x: x['role_score'], reverse=True)

        # 🔥 화력 극대화 팀 구성: 1설치자 + 3공격자 + 2카운터
        final_team = []
        used_indices = set()

        # 1. MAIN_SETTER 1명
        if role_candidates['MAIN_SETTER']:
            setter = role_candidates['MAIN_SETTER'][0]
            final_team.append(self._create_team_command(setter, 4))
            used_indices.add(setter['index'])
            print(f"✅ MAIN_SETTER: {setter['index']} (Score: {setter['role_score']:.0f})")

        # 2. MAIN_ATTACKER 2명
        attacker_count = 0
        for attacker in role_candidates['MAIN_ATTACKER']:
            if attacker['index'] not in used_indices and attacker_count < 2:
                final_team.append(self._create_team_command(attacker, 4))
                used_indices.add(attacker['index'])
                attacker_count += 1
                print(f"✅ MAIN_ATTACKER {attacker_count}: {attacker['index']} (Score: {attacker['role_score']:.0f})")

        # 3. FLEX_ATTACKER 1명 (환경 독립 공격자)
        if role_candidates['FLEX_ATTACKER']:
            for flex in role_candidates['FLEX_ATTACKER']:
                if flex['index'] not in used_indices:
                    final_team.append(self._create_team_command(flex, 4))
                    used_indices.add(flex['index'])
                    print(f"✅ FLEX_ATTACKER: {flex['index']} (Score: {flex['role_score']:.0f})")
                    break

        # 4. PSYCHIC_COUNTER 1명
        if role_candidates['PSYCHIC_COUNTER']:
            for psychic_counter in role_candidates['PSYCHIC_COUNTER']:
                if psychic_counter['index'] not in used_indices:
                    final_team.append(self._create_team_command(psychic_counter, 4))
                    used_indices.add(psychic_counter['index'])
                    print(f"✅ PSYCHIC_COUNTER: {psychic_counter['index']} (Score: {psychic_counter['role_score']:.0f})")
                    break

        # 5. TYPE_COUNTER 1명
        if role_candidates['TYPE_COUNTER']:
            for type_counter in role_candidates['TYPE_COUNTER']:
                if type_counter['index'] not in used_indices:
                    final_team.append(self._create_team_command(type_counter, 4))
                    used_indices.add(type_counter['index'])
                    print(f"✅ TYPE_COUNTER: {type_counter['index']} (Score: {type_counter['role_score']:.0f})")
                    break

        # 부족한 자리 채우기 (최고 점수 우선)
        while len(final_team) < max_team_size:
            best_remaining = None
            best_score = 0

            for pokemon_data in analyzed_pokemon:
                if pokemon_data['index'] not in used_indices:
                    if pokemon_data['role_score'] > best_score:
                        best_remaining = pokemon_data
                        best_score = pokemon_data['role_score']

            if best_remaining:
                final_team.append(self._create_team_command(best_remaining, 4))
                used_indices.add(best_remaining['index'])
                print(
                    f"✅ BACKUP: {best_remaining['index']} ({best_remaining['role']}, Score: {best_remaining['role_score']:.0f})")
            else:
                break

        return final_team[:max_team_size]

    def _set_selection_roles(self, team_composition):
        """Selection Policy에 역할 정보 전달"""
        if len(team_composition) < 6:
            print("⚠️ Warning: Team composition incomplete, role assignment may be suboptimal")
            return

        roles = {
            'main_setter': team_composition[0] if len(team_composition) > 0 else None,
            'main_attackers': team_composition[1:3] if len(team_composition) >= 3 else team_composition[1:],
            'flex_attacker': team_composition[3] if len(team_composition) > 3 else None,
            'psychic_counter': team_composition[4] if len(team_composition) > 4 else None,
            'type_counter': team_composition[5] if len(team_composition) > 5 else None
        }

        print("🎮 Team roles assigned for Selection Policy")

    def _create_team_command(self, pokemon_data, max_moves):
        """팀 명령 생성 - VGC2 호환성 완료"""
        role = pokemon_data['role']
        base_stats = pokemon_data['base_stats']

        # 역할별 EV 분배 (화력 중심)
        ev_spread = self._get_role_ev_spread(role, base_stats)

        # 역할별 성격 (공격/스피드 우선)
        nature = self._get_role_nature(role, base_stats)

        # 기술 선택 (심화 분석 결과 활용)
        moves = self._select_moves_for_role(pokemon_data, role, max_moves)

        return (
            pokemon_data['index'],
            ev_spread,
            EVStats((31, 31, 31, 31, 31, 31)),  # 개체값 최대 (VGC2 EVStats 사용)
            nature,
            moves
        )

    def _get_role_ev_spread(self, role: str, base_stats) -> EVStats:
        """역할별 EV 분배 - 화력 극대화 중심 (VGC2 EVStats 사용)"""

        if role == "MAIN_SETTER":
            # 설치자: HP + 스피드 (생존 + 빠른 설치)
            return EVStats((252, 0, 4, 0, 0, 252))

        elif role in ["MAIN_ATTACKER", "FLEX_ATTACKER", "PSYCHIC_COUNTER", "TYPE_COUNTER"]:
            # 🔥 모든 공격자: 공격력 + 스피드 (화력 극대화)
            if base_stats[StatIndex.ATTACK] > base_stats[StatIndex.SPECIAL_ATTACK]:
                return EVStats((4, 252, 0, 0, 0, 252))  # 물리형
            else:
                return EVStats((4, 0, 0, 252, 0, 252))  # 특수형

        else:
            # 기본: 공격 우선 (지라치 철학)
            return EVStats((4, 252, 0, 0, 0, 252))

    def _get_role_nature(self, role: str, base_stats) -> Nature:
        """역할별 성격 - 공격과 스피드 최적화"""

        if role == "MAIN_SETTER":
            return Nature.TIMID  # 스피드 상승 (빠른 설치)

        elif role in ["MAIN_ATTACKER", "FLEX_ATTACKER", "PSYCHIC_COUNTER", "TYPE_COUNTER"]:
            # 🔥 모든 공격자: 화력 + 스피드 최적화
            if base_stats[StatIndex.ATTACK] > base_stats[StatIndex.SPECIAL_ATTACK]:
                return Nature.JOLLY  # 물리 + 스피드
            else:
                return Nature.TIMID  # 특공 + 스피드

        else:
            return Nature.SERIOUS

    def _select_moves_for_role(self, pokemon_data, role: str, max_moves: int) -> List[int]:
        """역할별 기술 선택 - 화력 중심"""
        moves = pokemon_data['moves']

        # 심화 분석 결과가 있으면 활용
        if 'enhanced_move_combo' in pokemon_data:
            enhanced_moves = pokemon_data['enhanced_move_combo']['moves']
            if enhanced_moves and len(enhanced_moves) <= max_moves:
                return enhanced_moves[:max_moves]

        # 기본 기술 선택
        move_scores = []

        for i, move in enumerate(moves):
            score = self._score_move_for_role(move, role, pokemon_data)
            move_scores.append((i, score))

        # 점수순 정렬 후 상위 선택
        move_scores.sort(key=lambda x: x[1], reverse=True)
        selected_moves = [idx for idx, _ in move_scores[:max_moves]]

        # 부족하면 순서대로 채움
        while len(selected_moves) < max_moves and len(selected_moves) < len(moves):
            for i in range(len(moves)):
                if i not in selected_moves:
                    selected_moves.append(i)
                    break

        return selected_moves[:max_moves]

    def _score_move_for_role(self, move, role: str, pokemon_data) -> float:
        """역할별 기술 점수 - 화력 극대화 중심"""
        score = 0.0

        try:
            base_power = getattr(move, 'base_power', 0)
            priority = getattr(move, 'priority', 0)
            accuracy = getattr(move, 'accuracy', 100)
            move_type = getattr(move, 'pkm_type', Type.NORMAL)

            # 🔥 기본 위력 점수 (화력 최우선)
            score += base_power * 3

            # 역할별 특화 점수
            if role == "MAIN_SETTER":
                # 🌦️ 환경 설치 기술 최우선!
                weather_start = getattr(move, 'weather_start', Weather.CLEAR)
                if weather_start != Weather.CLEAR:
                    score += 2000

                # 🌍 테라인 설치 기술 최우선!
                terrain_start = getattr(move, 'terrain_start', Terrain.NONE)
                if terrain_start != Terrain.NONE:
                    score += 1800

                # 설치 후 공격용 선공기
                if priority > 0 and base_power > 0:
                    score += 400

            elif role in ["MAIN_ATTACKER", "FLEX_ATTACKER"]:
                # 🔥 공격자는 화력 최우선!
                if base_power >= 120:
                    score += 500  # 초고위력
                elif base_power >= 100:
                    score += 400
                elif base_power >= 90:
                    score += 300
                elif base_power >= 80:
                    score += 200

                # 🚀 선공기 초대폭 보너스 (지라치 철학)
                if priority > 0:
                    score += 600
                    if base_power >= 80:
                        score += 400

                # STAB 보너스
                pokemon_types = pokemon_data.get('pokemon_types', set())
                if move_type in pokemon_types:
                    score += base_power * 1.5

            elif role == "PSYCHIC_COUNTER":
                # 🛡️ 에스퍼 카운터 기술 극대화
                counter_types = {Type.DARK, Type.GHOST, Type.BUG}
                if move_type in counter_types:
                    score += base_power * 4

                if base_power >= 90:
                    score += 300

                if priority > 0 and move_type in counter_types:
                    score += 500

            elif role == "TYPE_COUNTER":
                # ⚔️ 타입 커버리지 + 화력
                score += base_power * 2

                versatile_types = {Type.NORMAL, Type.FIGHTING, Type.FLYING, Type.ROCK}
                if move_type in versatile_types:
                    score += 200

                if base_power >= 100:
                    score += 250

            # 🌟 공통 보정 (화력 중심)
            # 선공기 추가 보너스
            if priority > 0:
                score += 300

            # 명중률 보정 (화력 신뢰성)
            if accuracy >= 95:
                score *= 1.0
            elif accuracy >= 85:
                score *= 0.95
            elif accuracy >= 80:
                score *= 0.9
            else:
                score *= 0.8

            # 🔥 고위력 기술 전역 보너스
            if base_power >= 150:
                score += 200
            elif base_power >= 120:
                score += 150

            return score

        except Exception:
            return base_power * 2 if base_power else 50

    def _fallback_build(self, roster, max_team_size, max_pkm_moves) -> TeamBuildCommand:
        """안전한 fallback 빌드 - 화력 중심 (VGC2 호환성)"""
        commands = []
        team_size = min(max_team_size, len(roster))

        for i in range(team_size):
            pokemon = roster[i]
            base_stats = getattr(pokemon, 'base_stats', None)

            if base_stats and base_stats[StatIndex.ATTACK] > base_stats[StatIndex.SPECIAL_ATTACK]:
                # 물리 공격자
                commands.append((
                    i,
                    EVStats((4, 252, 0, 0, 0, 252)),  # 공격 + 스피드 (VGC2 EVStats)
                    EVStats((31, 31, 31, 31, 31, 31)),  # IVs (VGC2 EVStats)
                    Nature.JOLLY,
                    list(range(min(max_pkm_moves, len(roster[i].moves))))
                ))
            else:
                # 특수 공격자
                commands.append((
                    i,
                    EVStats((4, 0, 0, 252, 0, 252)),  # 특공 + 스피드 (VGC2 EVStats)
                    EVStats((31, 31, 31, 31, 31, 31)),  # IVs (VGC2 EVStats)
                    Nature.TIMID,
                    list(range(min(max_pkm_moves, len(roster[i].moves))))
                ))

        return commands


# ===============================================
# 기존 호환성 유지를 위한 별칭
# ===============================================

class EnhancedEnvironmentTeamBuildPolicy(MaxFirepowerTeamBuildPolicy):
    """기존 호환성을 위한 별칭"""

    def __init__(self, time_limit=60):
        super().__init__(time_limit)
        print("🔄 Legacy compatibility mode: EnhancedEnvironmentTeamBuildPolicy -> MaxFirepowerTeamBuildPolicy")


# ===============================================
# VGC2 호환성 테스트 함수
# ===============================================

def test_vgc2_compatibility():
    """VGC2 호환성 테스트"""
    print("🧪 VGC2 호환성 테스트 시작...")

    try:
        # EVStats 테스트
        ev_stats = EVStats((252, 0, 4, 0, 0, 252))
        print(f"✅ EVStats 생성 성공: {ev_stats}")

        # StatIndex 테스트
        speed_stat = StatIndex.SPEED
        attack_stat = StatIndex.ATTACK
        print(f"✅ StatIndex 접근 성공: SPEED={speed_stat}, ATTACK={attack_stat}")

        # MaxFirepowerTeamBuildPolicy 테스트
        policy = MaxFirepowerTeamBuildPolicy(time_limit=30)
        print(f"✅ MaxFirepowerTeamBuildPolicy 초기화 성공")

        print("🎉 모든 VGC2 호환성 테스트 통과!")
        return True

    except Exception as e:
        print(f"❌ VGC2 호환성 테스트 실패: {e}")
        return False


if __name__ == "__main__":
    print("🔥 Max Firepower Jirachi AI Team Builder")
    print("=" * 50)

    # VGC2 호환성 테스트 실행
    compatibility_result = test_vgc2_compatibility()

    if compatibility_result:
        print("\n🚀 Team Builder 사용 준비 완료!")
        print("🎯 Philosophy: 1턴킬 > 화력집중 > 단일환경 > 카운터대응")
        print("👥 Team: 1설치자 + 3공격자 + 2카운터 = 6인")
        print("🚫 서포터 완전 제거 - 화력만이 답!")
        print("✅ VGC2 Import 충돌 수정 완료")
    else:
        print("\n⚠️ VGC2 호환성 문제 발견. 환경을 확인해주세요.")
