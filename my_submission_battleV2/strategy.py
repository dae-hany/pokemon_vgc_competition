from dataclasses import dataclass
from enum import Enum, auto

import numpy as np

from vgc2.battle_engine.modifiers import Weather, Type, Stat, Category
from vgc2.battle_engine.pokemon import Pokemon

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


class Strategy(Enum):
    TRICK_ROOM    = auto()
    WEATHER_RAIN  = auto()
    WEATHER_SUN   = auto()
    WEATHER_SAND  = auto()
    WEATHER_SNOW  = auto()
    HYPER_OFFENSE = auto()
    BALANCED      = auto()


@dataclass
class StrategyPlan:
    strategy: Strategy
    setter_idx: int         # TR/날씨 설정자 인덱스 (-1이면 없음)
    lead_idxs: list[int]    # 선발 2마리 (members[:2] → active)
    reserve_idxs: list[int] # 후보 2마리 (members[2:] → reserve)


STRATEGY_TO_WEATHER = {
    Strategy.WEATHER_RAIN: Weather.RAIN,
    Strategy.WEATHER_SUN:  Weather.SUN,
    Strategy.WEATHER_SAND: Weather.SAND,
    Strategy.WEATHER_SNOW: Weather.SNOW,
}

_WEATHER_TO_STRATEGY = {v: k for k, v in STRATEGY_TO_WEATHER.items()}

# Rain → Water 타입 공격 1.5x, Sun → Fire 타입 공격 1.5x
_WEATHER_BENEFICIARY_TYPE = {
    Weather.RAIN: Type.WATER,
    Weather.SUN:  Type.FIRE,
}

_TRICK_ROOM_SPE_THRESHOLD = 70
_FAST_SPE_THRESHOLD = 100


def _estimate_damage_ratio(attacker: Pokemon, defender: Pokemon) -> float:
    best = 0.0
    for move in attacker.moves:
        if move.category not in (Category.PHYSICAL, Category.SPECIAL):
            continue
        base_power = move.base_power + max(0, move.priority) * 10
        if base_power <= 0:
            continue
        atk = attacker.stats[Stat.ATTACK] if move.category == Category.PHYSICAL else attacker.stats[Stat.SPECIAL_ATTACK]
        def_ = defender.stats[Stat.DEFENSE] if move.category == Category.PHYSICAL else defender.stats[Stat.SPECIAL_DEFENSE]
        stab = 1.5 if move.pkm_type in attacker.species.types else 1.0
        eff = 1.0
        for dt in defender.species.types:
            eff *= TYPE_CHART[move.pkm_type, dt]
        dmg = int((2 * 50 / 5) + 2)
        dmg = int(dmg * base_power)
        dmg = int(dmg * atk / max(def_, 1))
        dmg = int(dmg / 50) + 2
        ratio = int(dmg * stab * eff) / max(defender.stats[Stat.MAX_HP], 1)
        best = max(best, ratio)
    return best


def _score_attacker(pkm: Pokemon, enemy_team: list[Pokemon]) -> float:
    total = sum(_estimate_damage_ratio(pkm, e) for e in enemy_team)
    hp_r = pkm.stats[Stat.MAX_HP] / 402
    def_r = pkm.stats[Stat.DEFENSE] / 257
    spd_r = pkm.stats[Stat.SPEED] / 257
    return 1.07 * total + 0.30 * (hp_r * def_r) + 0.55 * spd_r


def _pick_best_n(candidate_idxs: list[int], my_team: list[Pokemon],
                 enemy_team: list[Pokemon], n: int) -> list[int]:
    if len(candidate_idxs) <= n:
        return list(candidate_idxs)
    m = len(my_team)
    k = len(enemy_team)
    dmg = np.zeros((m, k), dtype=float)
    for i in candidate_idxs:
        for j, dfn in enumerate(enemy_team):
            dmg[i, j] = _estimate_damage_ratio(my_team[i], dfn)
    scores = {i: _score_attacker(my_team[i], enemy_team) for i in candidate_idxs}
    selected = []
    first = max(candidate_idxs, key=lambda i: scores[i])
    selected.append(first)
    coverage = dmg[first].copy()
    remaining = [i for i in candidate_idxs if i != first]
    while len(selected) < n and remaining:
        old_range = coverage.max() - coverage.min()
        best_i, best_val = None, float('-inf')
        for i in remaining:
            new_cov = coverage + dmg[i]
            delta = old_range - (new_cov.max() - new_cov.min())
            val = 1.25 * delta + 0.74 * scores[i]
            if val > best_val:
                best_val, best_i = val, i
        selected.append(best_i)
        coverage += dmg[best_i]
        remaining.remove(best_i)
    return selected


def identify_strategy(my_team: list[Pokemon], enemy_team: list[Pokemon]) -> StrategyPlan:
    n = len(my_team)

    tr_setter_idx = -1
    weather_setters: dict[Weather, int] = {}

    for i, pkm in enumerate(my_team):
        for mv in pkm.moves:
            if mv.toggle_trickroom and tr_setter_idx == -1:
                tr_setter_idx = i
            if mv.weather_start != Weather.CLEAR and mv.weather_start not in weather_setters:
                weather_setters[mv.weather_start] = i

    # TRICK_ROOM: TR 설정자 있고 + 느린 공격수가 있으면
    if tr_setter_idx != -1:
        slow_idxs = [i for i in range(n)
                     if my_team[i].stats[Stat.SPEED] < _TRICK_ROOM_SPE_THRESHOLD and i != tr_setter_idx]
        if slow_idxs:
            best_slow = max(slow_idxs, key=lambda i: _score_attacker(my_team[i], enemy_team))
            lead = [tr_setter_idx, best_slow]
            reserve = _pick_best_n([i for i in range(n) if i not in lead], my_team, enemy_team, n=2)
            return StrategyPlan(Strategy.TRICK_ROOM, tr_setter_idx, lead, reserve)

    # WEATHER: 날씨 설정자 + 수혜 포켓몬
    for weather, setter_idx in weather_setters.items():
        beneficiary_type = _WEATHER_BENEFICIARY_TYPE.get(weather)
        if beneficiary_type:
            beneficiaries = [i for i in range(n)
                             if beneficiary_type in my_team[i].species.types and i != setter_idx]
            if beneficiaries:
                best_ben = max(beneficiaries, key=lambda i: _score_attacker(my_team[i], enemy_team))
                lead = [setter_idx, best_ben]
                reserve = _pick_best_n([i for i in range(n) if i not in lead], my_team, enemy_team, n=2)
                return StrategyPlan(_WEATHER_TO_STRATEGY[weather], setter_idx, lead, reserve)
        # SAND/SNOW: 수혜 타입 없어도 날씨 설정 자체가 방어 강화 → 최고 공격수와 페어
        best_partner_idxs = [i for i in range(n) if i != setter_idx]
        if best_partner_idxs:
            best_partner = max(best_partner_idxs, key=lambda i: _score_attacker(my_team[i], enemy_team))
            lead = [setter_idx, best_partner]
            reserve = _pick_best_n([i for i in range(n) if i not in lead], my_team, enemy_team, n=2)
            return StrategyPlan(_WEATHER_TO_STRATEGY[weather], setter_idx, lead, reserve)

    # HYPER_OFFENSE: 빠른 포켓몬 2마리 이상
    fast_idxs = [i for i in range(n) if my_team[i].stats[Stat.SPEED] >= _FAST_SPE_THRESHOLD]
    if len(fast_idxs) >= 2:
        lead = sorted(fast_idxs, key=lambda i: my_team[i].stats[Stat.SPEED], reverse=True)[:2]
        reserve = _pick_best_n([i for i in range(n) if i not in lead], my_team, enemy_team, n=2)
        return StrategyPlan(Strategy.HYPER_OFFENSE, -1, lead, reserve)

    # BALANCED fallback (JJJ 커버리지 최적화)
    selected = _pick_best_n(list(range(n)), my_team, enemy_team, n=4)
    return StrategyPlan(Strategy.BALANCED, -1, selected[:2], selected[2:])
