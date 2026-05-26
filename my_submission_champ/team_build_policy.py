"""
Weather-aware Dual-Plan Team Build Policy (VGC 2026).

Goal:
- Build a robust 6-mon team from a 50-mon roster.
- Prefer a dual weather plan (RAIN + SUN) WITHOUT hard-locking into a single weather.
- Optimize for robust performance across all weather states, while keeping option value.

Key engine facts (vgc2/battle_engine/damage_calculator.py):
- Offensive weather modifiers only affect FIRE/WATER moves in SUN/RAIN.
- Defensive boosts:
  - SAND: ROCK types get boosted SPDEF (WEATHER_BOOST)
  - SNOW: ICE types get boosted DEF (WEATHER_BOOST)
- End-of-turn chip: only SAND is implemented in engine.

이 정책은:
- 5가지 날씨 상태(CLEAR/RAIN/SUN/SAND/SNOW)에 대한 데미지 매트릭스를 미리 계산.
- 3분(170초) 예산을 활용하는 다중 재시작 Greedy + 로컬 스왑 개선.
  1. 모든 가능한 시작점(n개)에서 greedy를 실행해 최선 팀 탐색.
  2. 시간이 남으면 로컬 스왑(팀 멤버 1명씩 교체 시도)으로 추가 개선.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Optional, Iterable

# pyrefly: ignore [missing-import]
import numpy as np

from vgc2.agent import TeamBuildPolicy, TeamBuildCommand
from vgc2.balance.meta import Meta, Roster
from vgc2.battle_engine.constants import BattleRuleParam
from vgc2.battle_engine.modifiers import Nature, Type, Category, Stat, Weather


# ----------- Local (fast) type chart for damage effectiveness -----------
TYPE_CHART = np.array([
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, .5, 0, 1, 1, .5, 1, 1],
    [1, .5, .5, 1, 2, 2, 1, 1, 1, 1, 1, 2, .5, 1, .5, 1, 2, 1, 1],
    [1, 2, .5, 1, .5, 1, 1, 1, 2, 1, 1, 1, 2, 1, .5, 1, 1, 1, 1],
    [1, 1, 2, .5, .5, 1, 1, 1, 0, 2, 1, 1, 1, 1, .5, 1, 1, 1, 1],
    [1, .5, 2, 1, .5, 1, 1, .5, 2, .5, 1, .5, 2, 1, .5, 1, .5, 1, 1],
    [1, .5, .5, 1, 2, .5, 1, 1, 2, 2, 1, 1, 1, 1, 2, 1, .5, 1, 1],
    [2, 1, 1, 1, 1, 2, 1, .5, 1, .5, .5, .5, 2, 0, 1, 2, 2, .5, 1],
    [1, 1, 1, 1, 2, 1, 1, .5, .5, 1, 1, 1, .5, .5, 1, 1, 0, 2, 1],
    [1, 2, 1, 2, .5, 1, 1, 2, 1, 0, 1, .5, 2, 1, 1, 1, 2, 1, 1],
    [1, 1, 1, .5, 2, 1, 2, 1, 1, 1, 1, 2, .5, 1, 1, 1, .5, 1, 1],
    [1, 1, 1, 1, 1, 1, 2, 2, 1, 1, .5, 1, 1, 1, 1, 0, .5, 1, 1],
    [1, .5, 1, 1, 2, 1, .5, .5, 1, .5, 2, 1, 1, .5, 1, 2, .5, .5, 1],
    [1, 2, 1, 1, 1, 2, .5, 1, .5, 2, 1, 2, 1, 1, 1, 1, .5, 1, 1],
    [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 2, 1, .5, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, .5, 0, 1],
    [1, 1, 1, 1, 1, 1, .5, 1, 1, 1, 2, 1, 1, 2, 1, .5, 1, .5, 1],
    [1, .5, .5, .5, 1, 2, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, .5, 2, 1],
    [1, .5, 1, 1, 1, 1, 2, .5, 1, 1, 1, 1, 1, 1, 2, 2, .5, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
], dtype=float)


WEATHER_STATES = (Weather.CLEAR, Weather.RAIN, Weather.SUN, Weather.SAND, Weather.SNOW)


def _weather_move_multiplier(params: BattleRuleParam, move_type: Type, weather: Weather) -> float:
    """Match vgc2/battle_engine/damage_calculator.weather_modifier() behavior."""
    if weather == Weather.CLEAR:
        return 1.0
    if weather == Weather.SUN and move_type == Type.FIRE:
        return float(params.WEATHER_BOOST)
    if weather == Weather.SUN and move_type == Type.WATER:
        return float(params.WEATHER_UNBOOST)
    if weather == Weather.RAIN and move_type == Type.WATER:
        return float(params.WEATHER_BOOST)
    if weather == Weather.RAIN and move_type == Type.FIRE:
        return float(params.WEATHER_UNBOOST)
    return 1.0


def _type_effectiveness(move_type: Type, defender_types: Iterable[Type]) -> float:
    eff = 1.0
    for dt in defender_types:
        eff *= float(TYPE_CHART[int(move_type), int(dt)])
    return eff


def _best_damage_ratio_weather(attacker, defender, weather: Weather, params: BattleRuleParam) -> float:
    best = 0.0
    atk_types = attacker.types
    def_types = defender.types

    def_stat_sand_snow_mult_spdef = 1.0
    def_stat_sand_snow_mult_def = 1.0
    if weather == Weather.SAND and Type.ROCK in def_types:
        def_stat_sand_snow_mult_spdef = float(params.WEATHER_BOOST)
    elif weather == Weather.SNOW and Type.ICE in def_types:
        def_stat_sand_snow_mult_def = float(params.WEATHER_BOOST)

    for move in attacker.moves:
        if move.category not in (Category.PHYSICAL, Category.SPECIAL):
            continue

        base_power = move.base_power + max(0, move.priority) * 10
        if base_power <= 0:
            continue

        if move.category == Category.PHYSICAL:
            atk_stat = attacker.base_stats[Stat.ATTACK]
            def_stat = defender.base_stats[Stat.DEFENSE]
            def_stat = int(def_stat * def_stat_sand_snow_mult_def)
        else:
            atk_stat = attacker.base_stats[Stat.SPECIAL_ATTACK]
            def_stat = defender.base_stats[Stat.SPECIAL_DEFENSE]
            def_stat = int(def_stat * def_stat_sand_snow_mult_spdef)

        def_stat = max(def_stat, 1)

        stab = 1.5 if move.pkm_type in atk_types else 1.0
        eff = _type_effectiveness(move.pkm_type, def_types)
        wmult = _weather_move_multiplier(params, move.pkm_type, weather)

        dmg = int((2 * 50 / 5) + 2)
        dmg = int(dmg * base_power)
        dmg = int(dmg * atk_stat / def_stat)
        dmg = int(dmg / 50) + 2
        final = int(dmg * stab * eff * wmult)

        max_hp = max(defender.base_stats[Stat.MAX_HP], 1)
        ratio = final / max_hp
        best = max(best, ratio)

    return best


def _score_bulk(species) -> float:
    hp_ratio = max(species.base_stats[Stat.MAX_HP], 1) / 150
    def_ratio = max(species.base_stats[Stat.DEFENSE], 1) / 150
    spd_ratio = max(species.base_stats[Stat.SPECIAL_DEFENSE], 1) / 150
    return hp_ratio * def_ratio * spd_ratio


def _determine_orientation(species):
    phy_total = sum(m.base_power * species.base_stats[Stat.ATTACK] for m in species.moves if m.category == Category.PHYSICAL)
    spc_total = sum(m.base_power * species.base_stats[Stat.SPECIAL_ATTACK] for m in species.moves if m.category == Category.SPECIAL)
    if phy_total > spc_total * 1.2:
        return 'physical'
    elif spc_total > phy_total * 1.2:
        return 'special'
    return 'mixed'


def _select_best_moves(species, max_moves: int) -> list[int]:
    scores = []
    for i, move in enumerate(species.moves):
        score = 0.0
        if move.category in (Category.PHYSICAL, Category.SPECIAL):
            stab = 1.5 if move.pkm_type in species.types else 1.0
            atk = species.base_stats[Stat.ATTACK] if move.category == Category.PHYSICAL else species.base_stats[Stat.SPECIAL_ATTACK]
            score = move.base_power * move.accuracy * stab * atk / 100.0
            if move.priority > 0:
                score *= 1.2
        else:
            score = 30.0
            if move.protect:
                score = 150.0
            if move.toggle_tailwind:
                score = 100.0
            if move.toggle_reflect or move.toggle_lightscreen:
                score = 80.0
            if any(b != 0 for b in move.boosts):
                score = 60.0
            if getattr(move, "weather_start", Weather.CLEAR) != Weather.CLEAR:
                score = max(score, 90.0)

        scores.append((i, score))

    scores.sort(key=lambda x: x[1], reverse=True)

    selected = []
    selected_types = set()

    for idx, _sc in scores:
        if len(selected) >= max_moves:
            break
        move = species.moves[idx]
        if move.pkm_type not in selected_types:
            selected.append(idx)
            if move.category in (Category.PHYSICAL, Category.SPECIAL):
                selected_types.add(move.pkm_type)

    if len(selected) < max_moves:
        for idx, _sc in scores:
            if len(selected) >= max_moves:
                break
            if idx not in selected:
                selected.append(idx)

    return selected


def _species_weather_set(s) -> set[Weather]:
    out: set[Weather] = set()
    for m in s.moves:
        w = getattr(m, "weather_start", Weather.CLEAR)
        if w != Weather.CLEAR:
            out.add(w)
    return out


def _offense_benefit_score(s, weather: Weather) -> float:
    if weather not in (Weather.RAIN, Weather.SUN):
        return 0.0
    target_type = Type.WATER if weather == Weather.RAIN else Type.FIRE

    best = 0.0
    for m in s.moves:
        if m.category not in (Category.PHYSICAL, Category.SPECIAL):
            continue
        if m.pkm_type != target_type:
            continue
        base_power = m.base_power + max(0, m.priority) * 10
        if base_power <= 0:
            continue
        stab = 1.0 + (0.5 if target_type in s.types else 0.0)
        best = max(best, float(base_power) * float(m.accuracy) * stab)
    return best


@dataclass
class DualPlanConfig:
    # Robust weighting
    robust_min_w: float = 0.7
    robust_mean_w: float = 0.3

    # Dual-plan preference
    prefer_dual_setters: float = 8.0
    prefer_single_setter: float = 2.0
    too_many_setters_penalty: float = 2.0

    # Beneficiaries caps
    beneficiary_cap: int = 2
    beneficiary_bonus: float = 1.2
    beneficiary_overcap_penalty: float = 1.5

    # Greedy selection mix
    coverage_weight: float = 1.3
    base_score_weight: float = 1.0
    shared_weakness_penalty: float = 0.18

    # 시간 예산 (초): 3분 제한에서 10초 버퍼
    time_budget_s: float = 170.0


class SmartTeamBuildPolicy(TeamBuildPolicy):
    """
    3분 예산을 최대한 활용하는 팀 빌드 정책.

    1단계: 모든 시작 포켓몬에서 Greedy를 실행해 최선 팀 탐색.
    2단계: 시간이 남으면 로컬 스왑(멤버 1명 교체)으로 추가 개선.
    """

    def __init__(self, cfg: DualPlanConfig | None = None):
        self.cfg = cfg or DualPlanConfig()
        self.params = BattleRuleParam()

    def _eval_team_score(
        self,
        selected: list[int],
        n: int,
        dmg: np.ndarray,
        base_scores: np.ndarray,
        species_weather: list[set],
        rain_benef: np.ndarray,
        sun_benef: np.ndarray,
        roster,
    ) -> float:
        """
        팀의 절대적 품질 점수. 서로 다른 greedy 실행 결과를 비교하는 데 사용.
        """
        cfg = self.cfg
        q = max(1, int(0.2 * n))

        # 날씨별 robust coverage (하위 20% 평균 기준)
        tail_scores = []
        for wi in range(len(WEATHER_STATES)):
            cov = np.zeros(n)
            for i in selected:
                np.maximum(cov, dmg[wi, i, :], out=cov)
            tail_scores.append(float(np.mean(np.partition(cov, q - 1)[:q])))
        tail_arr = np.array(tail_scores)
        cov_score = cfg.robust_min_w * tail_arr.min() + cfg.robust_mean_w * tail_arr.mean()

        # 팀 평균 개체 점수
        base_avg = float(np.mean([base_scores[i] for i in selected]))

        # 날씨 세터 보너스
        has_rain = any(Weather.RAIN in species_weather[i] for i in selected)
        has_sun = any(Weather.SUN in species_weather[i] for i in selected)
        if has_rain and has_sun:
            setter_bonus = cfg.prefer_dual_setters
        elif has_rain or has_sun:
            setter_bonus = cfg.prefer_single_setter
        else:
            setter_bonus = 0.0

        n_setters = sum(1 for i in selected if len(species_weather[i]) > 0)
        if n_setters >= 3:
            setter_bonus -= cfg.too_many_setters_penalty * (n_setters - 2)

        # 수혜자 보너스
        rain_b = sum(1 for i in selected if rain_benef[i] > 0)
        sun_b = sum(1 for i in selected if sun_benef[i] > 0)
        benef_bonus = 0.0
        for b in (rain_b, sun_b):
            if b <= cfg.beneficiary_cap:
                benef_bonus += cfg.beneficiary_bonus * b
            else:
                benef_bonus += cfg.beneficiary_bonus * cfg.beneficiary_cap
                benef_bonus -= cfg.beneficiary_overcap_penalty * (b - cfg.beneficiary_cap)

        # 방어 약점 공유 패널티 (팀 내 모든 쌍 기준)
        sw = 0
        sel_list = list(selected)
        for a in range(len(sel_list)):
            for b_idx in range(a + 1, len(sel_list)):
                for atk_type in range(18):
                    eff1, eff2 = 1.0, 1.0
                    for dt in roster[sel_list[a]].types:
                        eff1 *= TYPE_CHART[atk_type, int(dt)]
                    for dt in roster[sel_list[b_idx]].types:
                        eff2 *= TYPE_CHART[atk_type, int(dt)]
                    if eff1 > 1.0 and eff2 > 1.0:
                        sw += 1

        return (cfg.coverage_weight * cov_score +
                cfg.base_score_weight * base_avg +
                setter_bonus + benef_bonus -
                cfg.shared_weakness_penalty * float(sw))

    def decision(
        self,
        roster: Roster,
        meta: Meta | None,
        max_team_size: int,
        max_pkm_moves: int,
        n_active: int
    ) -> TeamBuildCommand:
        n = len(roster)
        if n == 0:
            return []

        cfg = self.cfg
        start_time = time.perf_counter()

        # ── 1. 한 번만 수행하는 사전 계산 ──────────────────────────────────
        species_weather = [_species_weather_set(roster[i]) for i in range(n)]
        rain_benef = np.array([_offense_benefit_score(roster[i], Weather.RAIN) for i in range(n)], dtype=float)
        sun_benef = np.array([_offense_benefit_score(roster[i], Weather.SUN) for i in range(n)], dtype=float)

        # 5(날씨) × n × n 데미지 비율 매트릭스
        dmg = np.zeros((len(WEATHER_STATES), n, n), dtype=float)
        for wi, w in enumerate(WEATHER_STATES):
            for i in range(n):
                for j in range(n):
                    dmg[wi, i, j] = _best_damage_ratio_weather(roster[i], roster[j], w, self.params)

        clear_idx = WEATHER_STATES.index(Weather.CLEAR)
        base_scores = np.zeros(n, dtype=float)
        for i in range(n):
            firepower = float(np.mean(dmg[clear_idx, i]))
            bulk = _score_bulk(roster[i])
            speed = roster[i].base_stats[Stat.SPEED] / 150.0
            base_scores[i] = 1.0 * firepower + 0.5 * bulk + 0.3 * speed

        # ── 2. Greedy 한 번 실행하는 내부 함수 ────────────────────────────
        def run_greedy(start_idx: int) -> list[int]:
            """주어진 시작 포켓몬에서 Greedy로 팀 구성."""
            selected = [start_idx]
            coverage = dmg[:, start_idx, :].copy()  # shape (W, n)
            candidates = set(range(n)) - {start_idx}

            def team_has_setter(weather: Weather, ids: list[int]) -> bool:
                return any(weather in species_weather[i] for i in ids)

            def count_setters(ids: list[int]) -> int:
                return sum(1 for i in ids if len(species_weather[i]) > 0)

            def count_beneficiaries(ids: list[int], weather: Weather) -> int:
                scores = rain_benef if weather == Weather.RAIN else sun_benef
                return sum(1 for i in ids if scores[i] > 0)

            def shared_def_weakness(team_ids: list[int], cand: int) -> int:
                shared = 0
                for sel in team_ids:
                    for atk_type in range(18):
                        eff1, eff2 = 1.0, 1.0
                        for dt in roster[sel].types:
                            eff1 *= TYPE_CHART[atk_type, int(dt)]
                        for dt in roster[cand].types:
                            eff2 *= TYPE_CHART[atk_type, int(dt)]
                        if eff1 > 1.0 and eff2 > 1.0:
                            shared += 1
                return shared

            def robust_improvement(old_cov_w: np.ndarray, new_cov_w: np.ndarray) -> float:
                q = max(1, int(0.2 * n))
                old_tail, new_tail, old_range, new_range = [], [], [], []
                for wi in range(len(WEATHER_STATES)):
                    oc, nc = old_cov_w[wi], new_cov_w[wi]
                    old_tail.append(float(np.mean(np.partition(oc, q - 1)[:q])))
                    new_tail.append(float(np.mean(np.partition(nc, q - 1)[:q])))
                    old_range.append(float(oc.max() - oc.min()))
                    new_range.append(float(nc.max() - nc.min()))
                old_tail_a = np.array(old_tail)
                new_tail_a = np.array(new_tail)
                old_range_a = np.array(old_range)
                new_range_a = np.array(new_range)
                per_w = 1.0 * (new_tail_a - old_tail_a) + 0.35 * (old_range_a - new_range_a)
                return cfg.robust_min_w * float(per_w.min()) + cfg.robust_mean_w * float(per_w.mean())

            for _ in range(1, min(max_team_size, n)):
                best_i, best_val = None, -1e18

                for i in candidates:
                    new_cov = coverage + dmg[:, i, :]
                    cov_val = robust_improvement(coverage, new_cov)

                    before_rain = team_has_setter(Weather.RAIN, selected)
                    before_sun = team_has_setter(Weather.SUN, selected)
                    after_rain = before_rain or (Weather.RAIN in species_weather[i])
                    after_sun = before_sun or (Weather.SUN in species_weather[i])

                    setter_bonus = 0.0
                    if after_rain and after_sun:
                        setter_bonus += cfg.prefer_dual_setters
                    elif after_rain or after_sun:
                        setter_bonus += cfg.prefer_single_setter

                    setters_after = count_setters(selected + [i])
                    if setters_after >= 3:
                        setter_bonus -= cfg.too_many_setters_penalty * (setters_after - 2)

                    rain_b = count_beneficiaries(selected + [i], Weather.RAIN)
                    sun_b = count_beneficiaries(selected + [i], Weather.SUN)
                    benef_bonus = 0.0
                    for b in (rain_b, sun_b):
                        if b <= cfg.beneficiary_cap:
                            benef_bonus += cfg.beneficiary_bonus * b
                        else:
                            benef_bonus += cfg.beneficiary_bonus * cfg.beneficiary_cap
                            benef_bonus -= cfg.beneficiary_overcap_penalty * (b - cfg.beneficiary_cap)

                    sw = shared_def_weakness(selected, i)
                    val = (cfg.coverage_weight * cov_val +
                           cfg.base_score_weight * float(base_scores[i]) +
                           setter_bonus + benef_bonus -
                           cfg.shared_weakness_penalty * float(sw))

                    if val > best_val:
                        best_val = val
                        best_i = i

                if best_i is None:
                    break
                selected.append(best_i)
                coverage += dmg[:, best_i, :]
                candidates.remove(best_i)

            return selected

        def eval_team(team: list[int]) -> float:
            return self._eval_team_score(
                team, n, dmg, base_scores, species_weather, rain_benef, sun_benef, roster
            )

        # ── 3. 단계 1: 모든 시작점에서 Greedy 실행 ────────────────────────
        first = int(np.argmax(base_scores))
        best_team = run_greedy(first)
        best_score = eval_team(best_team)

        # 나머지 시작점들을 무작위 순서로 시도
        all_starts = list(range(n))
        random.shuffle(all_starts)

        for start_idx in all_starts:
            if time.perf_counter() - start_time >= cfg.time_budget_s:
                break
            if start_idx == first:
                continue
            team = run_greedy(start_idx)
            score = eval_team(team)
            if score > best_score:
                best_score = score
                best_team = team

        # ── 4. 단계 2: 로컬 스왑 개선 (남은 시간 활용) ────────────────────
        # 팀 멤버 1명을 로스터의 다른 포켓몬으로 교체했을 때 점수가 오르면 수락.
        # 개선이 없을 때까지 또는 시간 초과까지 반복.
        non_members = set(range(n)) - set(best_team)
        improved = True
        while improved and time.perf_counter() - start_time < cfg.time_budget_s:
            improved = False
            for slot_idx in range(len(best_team)):
                if time.perf_counter() - start_time >= cfg.time_budget_s:
                    break
                old_member = best_team[slot_idx]
                for new_member in list(non_members):
                    if time.perf_counter() - start_time >= cfg.time_budget_s:
                        break
                    trial = list(best_team)
                    trial[slot_idx] = new_member
                    trial_score = eval_team(trial)
                    if trial_score > best_score:
                        best_score = trial_score
                        best_team = trial
                        non_members.remove(new_member)
                        non_members.add(old_member)
                        improved = True
                        break  # 이 슬롯 개선 완료, 다음 슬롯으로
                if improved:
                    break  # 전체 팀 재평가를 위해 외부 루프 재시작

        # ── 5. 커맨드 생성 (EV/IV/Nature/기술 배정) ───────────────────────
        cmds: TeamBuildCommand = []
        for idx in best_team:
            species = roster[idx]
            orientation = _determine_orientation(species)

            if orientation == 'physical':
                evs, nature = (252, 252, 0, 0, 0, 4), Nature.ADAMANT
            elif orientation == 'special':
                evs, nature = (252, 0, 0, 252, 0, 4), Nature.MODEST
            else:
                evs, nature = (252, 126, 0, 126, 0, 4), Nature.HASTY

            ivs = (31,) * 6
            move_indices = _select_best_moves(species, max_pkm_moves)
            cmds.append((idx, evs, ivs, nature, move_indices))

        return cmds
