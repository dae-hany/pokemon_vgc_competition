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

This policy:
- Builds weather-aware damage matrices for 5 weather states: CLEAR/RAIN/SUN/SAND/SNOW.
- Uses a robust objective: 0.7 * min_weather + 0.3 * mean_weather on coverage improvement.
- Adds soft constraints/bonuses to encourage selecting:
  - at least one RAIN setter and one SUN setter (dual plan)
  - 1~2 beneficiaries per weather (avoid over-investing)
  - avoid too many setters (over-investing)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Iterable
# pyrefly: ignore [missing-import]
import numpy as np

from vgc2.agent import TeamBuildPolicy, TeamBuildCommand
from vgc2.balance.meta import Meta, Roster
from vgc2.battle_engine.constants import BattleRuleParam
from vgc2.battle_engine.modifiers import Nature, Type, Category, Stat, Weather


# ----------- Local (fast) type chart for damage effectiveness -----------
# NOTE: Kept as in your previous implementation to avoid relying on params internals.
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
    """
    Simplified expected best damage ratio attacker->defender under a given weather.
    This is *not* engine-exact, but matches the engine's weather multipliers for FIRE/WATER
    and preserves your previous heuristic style.

    attacker/defender: roster species-like objects (as in your original code).
      - attacker.moves: list of Move constants-like objects
      - attacker.base_stats[Stat.*]
      - attacker.types, defender.types
    """
    best = 0.0
    atk_types = attacker.types
    def_types = defender.types

    # Defense boosts in SAND/SNOW (engine applies to defender's boosted stats).
    # We approximate by scaling the relevant defending stat.
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

        # choose stats
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

        # Simplified level 50 formula (same structure as your old code)
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
    # unchanged from your original heuristic (kept simple)
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
    # keep your previous implementation (with small prioritization for weather-setters)
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

            # New: mildly encourage carrying a weather-setting move if present
            if getattr(move, "weather_start", Weather.CLEAR) != Weather.CLEAR:
                score = max(score, 90.0)

        scores.append((i, score))

    scores.sort(key=lambda x: x[1], reverse=True)

    selected = []
    selected_types = set()

    # Pass 1: Prioritize unique types to maximize coverage
    for idx, _sc in scores:
        if len(selected) >= max_moves:
            break
        move = species.moves[idx]
        if move.pkm_type not in selected_types:
            selected.append(idx)
            if move.category in (Category.PHYSICAL, Category.SPECIAL):
                selected_types.add(move.pkm_type)

    # Pass 2: Fill remaining slots with the best moves regardless of type
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
    """
    Rough 'beneficiary' score without Pokémon knowledge:
    - If weather boosts FIRE or WATER, look for strong moves of that type.
    - Otherwise small/no bonus.
    """
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
    prefer_dual_setters: float = 8.0   # bonus if team has both RAIN and SUN setters
    prefer_single_setter: float = 2.0 # bonus if team has at least one of them
    too_many_setters_penalty: float = 2.0

    # Beneficiaries caps (avoid over-investing)
    beneficiary_cap: int = 2
    beneficiary_bonus: float = 1.2
    beneficiary_overcap_penalty: float = 1.5

    # Greedy selection mix
    coverage_weight: float = 1.3
    base_score_weight: float = 1.0
    shared_weakness_penalty: float = 0.18


class SmartTeamBuildPolicy(TeamBuildPolicy):
    """
    Drop-in replacement for your SmartTeamBuildPolicy with weather-aware dual-plan.
    """

    def __init__(self, cfg: DualPlanConfig | None = None):
        self.cfg = cfg or DualPlanConfig()
        self.params = BattleRuleParam()

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

        # Precompute weather-set capabilities and offense beneficiary scores
        species_weather = [ _species_weather_set(roster[i]) for i in range(n) ]
        rain_benef = np.array([_offense_benefit_score(roster[i], Weather.RAIN) for i in range(n)], dtype=float)
        sun_benef = np.array([_offense_benefit_score(roster[i], Weather.SUN) for i in range(n)], dtype=float)

        # Build weather-specific damage matrices
        # dmg[w_idx][i][j] = best ratio i->j in weather w
        dmg = np.zeros((len(WEATHER_STATES), n, n), dtype=float)
        for wi, w in enumerate(WEATHER_STATES):
            for i in range(n):
                ai = roster[i]
                for j in range(n):
                    dj = roster[j]
                    dmg[wi, i, j] = _best_damage_ratio_weather(ai, dj, w, self.params)

        # Base scores (use CLEAR to remain "reasonable" without weather)
        base_scores = np.zeros(n, dtype=float)
        clear_idx = WEATHER_STATES.index(Weather.CLEAR)
        for i in range(n):
            firepower = float(np.mean(dmg[clear_idx, i]))  # average vs roster under CLEAR
            bulk = _score_bulk(roster[i])
            speed = roster[i].base_stats[Stat.SPEED] / 150.0
            base_scores[i] = 1.0 * firepower + 0.5 * bulk + 0.3 * speed

        # Pick first by base_scores (as before)
        selected: list[int] = []
        first = int(np.argmax(base_scores))
        selected.append(first)

        # coverage per weather: sum of selected attackers' row vectors
        coverage = dmg[:, first, :].copy()  # shape (W, n)
        candidates = set(range(n)) - {first}

        def team_has_setter(weather: Weather, team_ids: list[int]) -> bool:
            return any(weather in species_weather[i] for i in team_ids)

        def count_setters(team_ids: list[int]) -> int:
            return sum(1 for i in team_ids if len(species_weather[i]) > 0)

        def count_beneficiaries(team_ids: list[int], weather: Weather) -> int:
            if weather == Weather.RAIN:
                scores = rain_benef
            elif weather == Weather.SUN:
                scores = sun_benef
            else:
                return 0
            # beneficiary = has non-trivial score
            return sum(1 for i in team_ids if scores[i] > 0)

        def shared_def_weakness(team_ids: list[int], cand: int) -> int:
            # reuse your previous style, just slightly simplified and bounded
            shared = 0
            for sel in team_ids:
                for atk_type in range(18):
                    eff1 = 1.0
                    for dt in roster[sel].types:
                        eff1 *= TYPE_CHART[atk_type, dt]
                    eff2 = 1.0
                    for dt in roster[cand].types:
                        eff2 *= TYPE_CHART[atk_type, dt]
                    if eff1 > 1.0 and eff2 > 1.0:
                        shared += 1
            return shared

        def robust_improvement(old_cov_w: np.ndarray, new_cov_w: np.ndarray) -> float:
            """
            old_cov_w/new_cov_w: shape (W, n)
            We'll measure improvement as:
              + (weak_tail_mean increase) - (range increase penalty)
            using robust aggregation across weathers.
            """
            # weak-tail: mean of bottom 20% coverage values (per weather)
            q = max(1, int(0.2 * n))
            old_tail = []
            new_tail = []
            old_range = []
            new_range = []
            for wi in range(len(WEATHER_STATES)):
                oc = old_cov_w[wi]
                nc = new_cov_w[wi]
                old_tail.append(float(np.mean(np.partition(oc, q - 1)[:q])))
                new_tail.append(float(np.mean(np.partition(nc, q - 1)[:q])))
                old_range.append(float(oc.max() - oc.min()))
                new_range.append(float(nc.max() - nc.min()))

            old_tail = np.array(old_tail)
            new_tail = np.array(new_tail)
            old_range = np.array(old_range)
            new_range = np.array(new_range)

            tail_gain = new_tail - old_tail
            range_gain = old_range - new_range  # prefer decreasing range

            # aggregate per weather into a single value
            per_w = 1.0 * tail_gain + 0.35 * range_gain
            return (self.cfg.robust_min_w * float(per_w.min()) +
                    self.cfg.robust_mean_w * float(per_w.mean()))

        for _ in range(1, min(max_team_size, n)):
            best_i = None
            best_val = -1e18

            for i in candidates:
                new_cov = coverage + dmg[:, i, :]
                cov_val = robust_improvement(coverage, new_cov)

                # dual-plan setter shaping
                before_rain = team_has_setter(Weather.RAIN, selected)
                before_sun = team_has_setter(Weather.SUN, selected)
                after_rain = before_rain or (Weather.RAIN in species_weather[i])
                after_sun = before_sun or (Weather.SUN in species_weather[i])

                setter_bonus = 0.0
                if after_rain and after_sun:
                    setter_bonus += self.cfg.prefer_dual_setters
                elif after_rain or after_sun:
                    setter_bonus += self.cfg.prefer_single_setter

                # penalize too many setters (over-invest)
                setters_after = count_setters(selected + [i])
                if setters_after >= 3:
                    setter_bonus -= self.cfg.too_many_setters_penalty * (setters_after - 2)

                # beneficiary shaping (soft, capped)
                rain_b = count_beneficiaries(selected + [i], Weather.RAIN)
                sun_b = count_beneficiaries(selected + [i], Weather.SUN)
                benef_bonus = 0.0
                for b in (rain_b, sun_b):
                    if b <= self.cfg.beneficiary_cap:
                        benef_bonus += self.cfg.beneficiary_bonus * b
                    else:
                        benef_bonus += self.cfg.beneficiary_bonus * self.cfg.beneficiary_cap
                        benef_bonus -= self.cfg.beneficiary_overcap_penalty * (b - self.cfg.beneficiary_cap)

                # defensive weakness penalty (as before)
                sw = shared_def_weakness(selected, i)

                val = (self.cfg.coverage_weight * cov_val +
                       self.cfg.base_score_weight * float(base_scores[i]) +
                       setter_bonus + benef_bonus -
                       self.cfg.shared_weakness_penalty * float(sw))

                if val > best_val:
                    best_val = val
                    best_i = i

            selected.append(best_i)
            coverage += dmg[:, best_i, :]
            candidates.remove(best_i)

        # Build commands with EV/nature + move selection (same as before)
        cmds: TeamBuildCommand = []
        for idx in selected:
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