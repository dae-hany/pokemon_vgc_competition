"""
Weather-aware Dual-Plan Selection Policy (VGC 2026).

Selects 4 out of 6 by exhaustive search over all C(6,4)=15 combinations.

Design goals:
- Robust performance across possible weather states (CLEAR/RAIN/SUN/SAND/SNOW).
- Preserve "option value" from team building: pick a coherent 4 that can actually execute
  Rain/Sun plans when advantageous, without hard-locking into one weather.
- Safety: never crash due to missing attributes; always return valid indices.

Important engine facts (vgc2/battle_engine/damage_calculator.py):
- Offensive weather modifier only affects FIRE/WATER moves in SUN/RAIN.
- Defensive boosts:
  - SAND: ROCK types get boosted SPDEF (approx handled in our heuristic)
  - SNOW: ICE types get boosted DEF
- Sand end-of-turn chip exists in engine, but is not modeled here (kept simple).

This policy uses a simplified damage-ratio model similar to your current selection policy,
but extended to weather.
"""
from __future__ import annotations

from itertools import combinations
from typing import List, Iterable, Optional

# pyrefly: ignore [missing-import]
import numpy as np

from vgc2.agent import SelectionPolicy, SelectionCommand
from vgc2.battle_engine.constants import BattleRuleParam
from vgc2.battle_engine.modifiers import Stat, Category, Type, Weather
from vgc2.battle_engine.pokemon import Pokemon
from vgc2.battle_engine.team import Team


# --- Type chart (same as your current one) ---
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
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
], dtype=float)


WEATHERS = (Weather.CLEAR, Weather.RAIN, Weather.SUN, Weather.SAND, Weather.SNOW)


def _safe_types(pkm: Pokemon) -> list[int]:
    # types stored under pkm.species.types in this engine; be defensive anyway
    t = getattr(getattr(pkm, "species", None), "types", None)
    if t is None:
        t = getattr(pkm, "types", None)
    return list(t) if t is not None else []


def _safe_moves(pkm: Pokemon) -> list:
    # Pokemon in selection stage usually has .moves (Move constants)
    mv = getattr(pkm, "moves", None)
    if mv is None:
        # fallback if it somehow is a battling pokemon-like
        mv = getattr(pkm, "battling_moves", None)
        if mv is not None:
            # battling moves may wrap constants in .constants
            out = []
            for bm in mv:
                out.append(getattr(bm, "constants", bm))
            return out
    return list(mv) if mv is not None else []


def _weather_move_multiplier(params: BattleRuleParam, move_type: int, weather: Weather) -> float:
    # Match engine logic (damage_calculator.weather_modifier)
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


def _type_effectiveness(move_type: int, defender_types: Iterable[int]) -> float:
    eff = 1.0
    for dt in defender_types:
        if 0 <= int(move_type) < TYPE_CHART.shape[0] and 0 <= int(dt) < TYPE_CHART.shape[1]:
            eff *= float(TYPE_CHART[int(move_type), int(dt)])
    return eff


def _estimate_damage_ratio_weather(attacker: Pokemon, defender: Pokemon, weather: Weather, params: BattleRuleParam) -> float:
    moves = _safe_moves(attacker)
    if not moves:
        return 0.0

    atk_types = _safe_types(attacker)
    def_types = _safe_types(defender)

    # Defensive boosts approximation (as in engine)
    # - SAND boosts ROCK SPDEF
    # - SNOW boosts ICE DEF
    sand_spdef_mult = 1.0
    snow_def_mult = 1.0
    if weather == Weather.SAND and Type.ROCK in def_types:
        sand_spdef_mult = float(params.WEATHER_BOOST)
    if weather == Weather.SNOW and Type.ICE in def_types:
        snow_def_mult = float(params.WEATHER_BOOST)

    best = 0.0
    for move in moves:
        cat = getattr(move, "category", Category.OTHER)
        if cat not in (Category.PHYSICAL, Category.SPECIAL):
            continue

        base_power = float(getattr(move, "base_power", 0))
        priority = float(getattr(move, "priority", 0))
        base_power = base_power + max(0.0, priority) * 10.0
        if base_power <= 0:
            continue

        # stats
        # selection-stage Pokemon has .stats (actual stats, not base_stats)
        a_stats = getattr(attacker, "stats", None)
        d_stats = getattr(defender, "stats", None)
        if not a_stats or not d_stats:
            continue

        if cat == Category.PHYSICAL:
            atk_stat = float(a_stats[Stat.ATTACK])
            def_stat = float(d_stats[Stat.DEFENSE]) * snow_def_mult
        else:
            atk_stat = float(a_stats[Stat.SPECIAL_ATTACK])
            def_stat = float(d_stats[Stat.SPECIAL_DEFENSE]) * sand_spdef_mult

        def_stat = max(def_stat, 1.0)

        mtype = getattr(move, "pkm_type", Type.TYPELESS)
        stab = 1.5 if mtype in atk_types else 1.0
        eff = _type_effectiveness(int(mtype), def_types)
        wmult = _weather_move_multiplier(params, int(mtype), weather)

        # simplified level 50 formula
        dmg = int((2 * 50 / 5) + 2)
        dmg = int(dmg * base_power)
        dmg = int(dmg * atk_stat / def_stat)
        dmg = int(dmg / 50) + 2
        final = int(dmg * stab * eff * wmult)

        hp = float(d_stats[Stat.MAX_HP]) if d_stats else 1.0
        hp = max(hp, 1.0)
        ratio = float(final) / hp
        if ratio > best:
            best = ratio

    return float(best)


def _is_weather_setter(pkm: Pokemon, target_weather: Weather) -> bool:
    for m in _safe_moves(pkm):
        w = getattr(m, "weather_start", Weather.CLEAR)
        if w == target_weather:
            return True
    return False


def _beneficiary_score(pkm: Pokemon, weather: Weather) -> float:
    # "no knowledge" beneficiary: look for strong FIRE/WATER moves depending on weather
    if weather not in (Weather.RAIN, Weather.SUN):
        return 0.0
    target_type = Type.WATER if weather == Weather.RAIN else Type.FIRE
    best = 0.0
    for m in _safe_moves(pkm):
        cat = getattr(m, "category", Category.OTHER)
        if cat not in (Category.PHYSICAL, Category.SPECIAL):
            continue
        mtype = getattr(m, "pkm_type", Type.TYPELESS)
        if mtype != target_type:
            continue
        bp = float(getattr(m, "base_power", 0))
        if bp <= 0:
            continue
        acc = float(getattr(m, "accuracy", 1.0))
        pr = float(getattr(m, "priority", 0))
        bp = bp + max(0.0, pr) * 10.0
        # mild STAB proxy
        stab = 1.0 + (0.5 if target_type in _safe_types(pkm) else 0.0)
        best = max(best, bp * acc * stab)
    return best


def _robust_coverage_score(
    my4: list[Pokemon],
    opp6: list[Pokemon],
    params: BattleRuleParam,
    min_w: float = 0.7,
    mean_w: float = 0.3
) -> float:
    """
    Compute robust coverage of my4 vs opp6 across weathers.
    We use weak-tail mean (bottom 25%) of per-opponent best-response coverage.
    """
    k = max(1, len(opp6))
    q = max(1, int(0.25 * k))

    per_weather_scores = []
    for w in WEATHERS:
        # For each opponent pokemon, compute best (max) ratio among my4
        cov = []
        for o in opp6:
            best_vs_o = 0.0
            for a in my4:
                best_vs_o = max(best_vs_o, _estimate_damage_ratio_weather(a, o, w, params))
            cov.append(best_vs_o)

        cov = np.array(cov, dtype=float)
        tail = float(np.mean(np.partition(cov, q - 1)[:q]))
        per_weather_scores.append(tail)

    per_weather_scores = np.array(per_weather_scores, dtype=float)
    return min_w * float(per_weather_scores.min()) + mean_w * float(per_weather_scores.mean())


def _dual_plan_bonus(my4: list[Pokemon]) -> float:
    """
    Encourage a coherent dual plan in the selected 4:
    - Prefer having at least one RAIN setter and one SUN setter.
    - Prefer 1~2 beneficiaries for each plan.
    - Penalize over-investing (too many setters / too many beneficiaries).
    """
    rain_set = sum(1 for p in my4 if _is_weather_setter(p, Weather.RAIN))
    sun_set = sum(1 for p in my4 if _is_weather_setter(p, Weather.SUN))

    # beneficiaries (simple threshold)
    rain_b = sum(1 for p in my4 if _beneficiary_score(p, Weather.RAIN) > 0)
    sun_b = sum(1 for p in my4 if _beneficiary_score(p, Weather.SUN) > 0)

    bonus = 0.0

    # setters
    if rain_set > 0 and sun_set > 0:
        bonus += 6.0
    elif rain_set > 0 or sun_set > 0:
        bonus += 1.5

    # avoid too many setters in a 4
    setters_total = rain_set + sun_set
    if setters_total >= 3:
        bonus -= 2.0 * (setters_total - 2)

    # beneficiary shaping: prefer up to 2 each
    def benef_term(b: int) -> float:
        if b <= 2:
            return 0.9 * b
        return 0.9 * 2 - 1.2 * (b - 2)

    bonus += benef_term(rain_b)
    bonus += benef_term(sun_b)

    return bonus


def _safe_fallback_indices(n: int, max_size: int) -> List[int]:
    return list(range(min(max_size, n)))


class CoverageSelectionPolicy(SelectionPolicy):
    """
    Drop-in replacement selection policy.

    - Never returns invalid indices
    - Exhaustive search over all 4-combinations
    """

    def __init__(self):
        self.params = BattleRuleParam()

    def decision(self, teams: tuple[Team, Team], max_size: int) -> SelectionCommand:
        try:
            my_team = list(getattr(teams[0], "members", []))
            opp_team = list(getattr(teams[1], "members", []))
            m = len(my_team)

            if m == 0:
                return []

            if max_size >= m:
                return list(range(m))

            # If opponent team is empty for some reason, just pick top-4 by bulk-ish heuristic
            if not opp_team:
                return _safe_fallback_indices(m, max_size)

            # Evaluate all combinations (C(6,4)=15 typical)
            best_combo = None
            best_score = -1e18

            for combo in combinations(range(m), max_size):
                my4 = [my_team[i] for i in combo]

                cov_score = _robust_coverage_score(my4, opp_team, self.params)
                plan_bonus = _dual_plan_bonus(my4)

                # Mild bulk bonus to avoid selecting 4 glass cannons
                bulk = 0.0
                for p in my4:
                    st = getattr(p, "stats", None)
                    if st:
                        # normalize roughly
                        hp = float(st[Stat.MAX_HP]) / 402.0
                        df = float(st[Stat.DEFENSE]) / 257.0
                        sd = float(st[Stat.SPECIAL_DEFENSE]) / 257.0
                        bulk += (hp * df * sd)
                bulk *= 0.08

                score = 1.6 * cov_score + plan_bonus + bulk

                if score > best_score:
                    best_score = score
                    best_combo = combo

            if best_combo is None:
                return _safe_fallback_indices(m, max_size)

            return list(best_combo)

        except Exception:
            # hard safety: never crash benchmark
            n = len(getattr(teams[0], "members", []))
            return _safe_fallback_indices(n, max_size)