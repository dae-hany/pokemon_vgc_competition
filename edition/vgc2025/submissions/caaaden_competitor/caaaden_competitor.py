from typing import Optional

from vgc2.agent import BattlePolicy, SelectionPolicy, TeamBuildPolicy, TeamBuildCommand
from vgc2.battle_engine import State, BattleCommand, calculate_damage, BattleRuleParam
from vgc2.battle_engine.modifiers import Type, Status, Nature
from vgc2.battle_engine.team import Team
from vgc2.battle_engine.view import TeamView
from vgc2.competition import Competitor
from vgc2.meta import Meta, Roster


class CaaadenBattlePolicy(BattlePolicy):

    def __init__(self):
        self.battle_params = BattleRuleParam()

    def decision(self, state: State, opp_view: Optional[TeamView] = None) -> list[BattleCommand]:
        my_team = state.sides[0].team
        opp_team = state.sides[1].team

        commands = []
        for i, pokemon in enumerate(my_team.active):
            if pokemon.fainted():
                # 가능한 리저브로 교체
                switch_target = self._find_best_switch(my_team)
                commands.append((-1, switch_target))
            else:
                # 최고의 기술 선택
                best_move, best_target = self._find_best_move(pokemon, opp_team.active, state)
                commands.append((best_move, best_target))

        return commands

    def _find_best_switch(self, team):
        """교체할 최적 포켓몬 찾기"""
        for i, pokemon in enumerate(team.reserve):
            if not pokemon.fainted():
                return i
        return 0

    def _find_best_move(self, attacker, defenders, state):
        """최적 기술과 타겟 찾기"""
        best_score = -1
        best_move = 0
        best_target = 0

        # 각 기술을 각 타겟에 대해 평가
        for move_idx, move in enumerate(attacker.battling_moves):
            if move.pp <= 0 or move.disabled:
                continue

            for target_idx, defender in enumerate(defenders):
                if defender.fainted():
                    continue

                # 기술 효과도 계산
                score = self._evaluate_move(attacker, move, defender, state)

                if score > best_score:
                    best_score = score
                    best_move = move_idx
                    best_target = target_idx

        return best_move, best_target

    def _evaluate_move(self, attacker, move, defender, state):
        """기술 효과도 평가"""
        try:
            # 기본 데미지
            damage = calculate_damage(self.battle_params, 0, move.constants, state, attacker, defender)
            score = damage

            # KO 보너스
            if damage >= defender.hp:
                score += 1000

            # 타입 상성 보너스
            type_mult = self._get_type_effectiveness(move.constants.pkm_type, defender.types)
            score *= type_mult

            # 선제기 보너스
            if move.constants.priority > 0:
                score += 100

            return score

        except Exception:
            return move.constants.base_power  # 대체값

    def _get_type_effectiveness(self, move_type, defending_types):
        """타입 상성 계산"""
        if move_type == Type.TYPELESS:
            return 1.0

        effectiveness = 1.0
        for def_type in defending_types:
            effectiveness *= self.battle_params.DAMAGE_MULTIPLICATION_ARRAY[move_type][def_type]
        return effectiveness


class CaaadenSelectionPolicy(SelectionPolicy):

    def decision(self, teams: tuple[Team, Team], max_size: int) -> list[int]:
        my_team = teams[0]
        opp_team = teams[1]

        # 상대방 타입 분석
        opp_types = set()
        for pokemon in opp_team.members:
            opp_types.update(pokemon.species.types)

        # 우리 포켓몬을 상대방에 대해 점수 매기기
        pokemon_scores = []
        for i, pokemon in enumerate(my_team.members):
            score = self._score_pokemon(pokemon, opp_types)
            pokemon_scores.append((i, score))

        # 점수순으로 정렬 후 최고 선택
        pokemon_scores.sort(key=lambda x: x[1], reverse=True)
        selected = [idx for idx, _ in pokemon_scores[:max_size]]

        return selected

    def _score_pokemon(self, pokemon, opp_types):
        """상대 팀에 대한 포켓몬 점수 계산"""
        score = 0

        # 기본 스탯 보너스
        score += sum(pokemon.stats[1:6]) * 0.1  # HP 제외
        score += pokemon.stats[0] * 0.05  # HP 요소

        # 상대방에 대한 타입 우위
        for move in pokemon.moves:
            for opp_type in opp_types:
                effectiveness = self._get_move_effectiveness(move.pkm_type, opp_type)
                if effectiveness >= 2.0:
                    score += 200
                elif effectiveness >= 1.5:
                    score += 100

        # 방어 타이핑
        for my_type in pokemon.species.types:
            for opp_type in opp_types:
                # 저항 보너스
                battle_params = BattleRuleParam()
                resistance = battle_params.DAMAGE_MULTIPLICATION_ARRAY[opp_type][my_type]
                if resistance <= 0.5:
                    score += 150

        return score

    def _get_move_effectiveness(self, move_type, defending_type):
        """타입 효과도 확인"""
        battle_params = BattleRuleParam()
        return battle_params.DAMAGE_MULTIPLICATION_ARRAY[move_type][defending_type]


class CaaadenTeamBuildPolicy(TeamBuildPolicy):

    def decision(self, roster: Roster, meta: Meta | None, max_team_size: int,
                 max_pkm_moves: int, n_active: int) -> TeamBuildCommand:

        # 로스터에서 다양한 포켓몬 선택
        selected_species = self._select_species(roster, max_team_size)

        # 팀 구성 생성
        team_command = []
        for species_idx in selected_species:
            species = roster[species_idx]
            config = self._build_pokemon_config(species, species_idx, max_pkm_moves)
            team_command.append(config)

        return team_command

    def _select_species(self, roster: Roster, max_size: int):
        """다양하고 강한 종족 선택 (대회 규칙: 최대 팀 크기 6)"""
        # 최대 팀 크기 6을 초과하지 않도록 보장
        max_size = min(max_size, 6)

        species_scores = []

        for i, species in enumerate(roster):
            score = self._evaluate_species(species)
            species_scores.append((i, score))

        # 점수순 정렬
        species_scores.sort(key=lambda x: x[1], reverse=True)

        # 타입 다양성을 고려한 최고 종족 선택
        selected = []
        used_types = set()

        for idx, score in species_scores:
            species = roster[idx]
            species_types = set(species.types)

            # 타입 다양성 선호
            if len(selected) < 2 or len(species_types & used_types) == 0:
                selected.append(idx)
                used_types.update(species_types)

                if len(selected) >= max_size:
                    break

        # 필요시 남은 슬롯 채우기
        for idx, score in species_scores:
            if len(selected) >= max_size:
                break
            if idx not in selected:
                selected.append(idx)

        return selected[:max_size]

    def _evaluate_species(self, species):
        """종족 강함 평가"""
        # 기본 스탯 합계
        score = sum(species.base_stats)

        # 타입 다양성 보너스
        if len(species.types) == 2:
            score += 50

        # 기술 품질
        for move in species.moves:
            score += move.base_power * 0.5
            if move.status != Status.NONE:
                score += 30
            if move.priority > 0:
                score += 40

        return score

    def _build_pokemon_config(self, species, species_idx: int, max_moves: int):
        """최적화된 포켓몬 구성 생성 (대회 규칙 준수)"""

        # 최고 기술 선택
        moves = self._select_moves(species, max_moves)

        # 스탯 기반 성격과 노력치 결정
        nature, evs = self._optimize_build(species)

        # 완벽한 개체값 (규칙: 1-31 범위의 최대값 31)
        ivs = (31, 31, 31, 31, 31, 31)

        return (species_idx, evs, ivs, nature, moves)

    def _select_moves(self, species, max_moves):
        """포켓몬의 최고 기술 선택 (대회 규칙: 최대 4기술)"""
        # 포켓몬당 최대 기술 수 4개를 초과하지 않도록 보장
        max_moves = min(max_moves, 4)

        move_scores = []

        for i, move in enumerate(species.moves):
            score = move.base_power * 2
            score += move.accuracy * 100
            score += move.max_pp * 5

            if move.priority > 0:
                score += 150
            if move.status != Status.NONE:
                score += 100
            if any(boost != 0 for boost in move.boosts):
                score += 80

            # 자속 보너스
            if move.pkm_type in species.types:
                score += 100

            move_scores.append((i, score))

        # 정렬 후 최고 기술 선택
        move_scores.sort(key=lambda x: x[1], reverse=True)
        return [idx for idx, _ in move_scores[:max_moves]]

    def _optimize_build(self, species):
        """최적 성격과 노력치 분배 결정"""
        base_stats = species.base_stats

        # 스탯 기반 역할 결정
        max_offensive = max(base_stats[1], base_stats[3])  # 공격 vs 특공
        max_defensive = max(base_stats[2], base_stats[4])  # 방어 vs 특방
        speed = base_stats[5]

        # 역할 기반 성격과 노력치 선택 (총 노력치 = 510, 스탯당 최대 255)
        if max_offensive >= 100 and speed >= 90:  # 어태커
            if base_stats[1] > base_stats[3]:  # 물리
                nature = Nature.ADAMANT
                evs = (6, 252, 0, 0, 0, 252)  # HP/공격/스피드 (합계: 510)
            else:  # 특수
                nature = Nature.MODEST
                evs = (6, 0, 0, 252, 0, 252)  # HP/특공/스피드 (합계: 510)
        elif max_defensive >= 100:  # 탱커
            nature = Nature.BOLD
            evs = (252, 0, 252, 0, 6, 0)  # HP/방어/특방 (합계: 510)
        else:  # 밸런스
            nature = Nature.SERIOUS
            evs = (85, 85, 85, 85, 85, 85)  # 균형 (합계: 510)

        return nature, evs


class CaaadenCompetitor(Competitor):

    def __init__(self, name: str = "Caaaden_AI"):
        self.__name = name
        self.__battle_policy = CaaadenBattlePolicy()
        self.__selection_policy = CaaadenSelectionPolicy()
        self.__team_build_policy = CaaadenTeamBuildPolicy()

    @property
    def battlepolicy(self) -> BattlePolicy:
        return self.__battle_policy

    @property
    def selectionpolicy(self) -> SelectionPolicy:
        return self.__selection_policy

    @property
    def teambuildpolicy(self) -> TeamBuildPolicy:
        return self.__team_build_policy

    @property
    def name(self) -> str:
        return self.__name
