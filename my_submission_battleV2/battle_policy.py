from vgc2.agent import BattlePolicy
from vgc2.battle_engine import BattleCommand
from vgc2.battle_engine.game_state import State
from vgc2.battle_engine.view import TeamView
from vgc2.battle_engine.modifiers import Category, Stat, Status
from vgc2.battle_engine.damage_calculator import calculate_damage

_BOOST_TABLE = {-6: 0.25, -5: 0.286, -4: 0.333, -3: 0.4, -2: 0.5, -1: 0.667,
                0: 1.0, 1: 1.5, 2: 2.0, 3: 2.5, 4: 3.0, 5: 3.5, 6: 4.0}


def _effective_speed(pkm, state: State) -> float:
    spd = pkm.constants.stats[Stat.SPEED] * _BOOST_TABLE.get(pkm.boosts[Stat.SPEED], 1.0)
    if pkm.status == Status.PARALYZED:
        spd *= 0.5
    if state.trickroom:
        spd = -spd
    return spd


def _best_move(params, state: State, slot: int) -> BattleCommand:
    pkm = state.sides[0].team.active[slot]
    opp_active = state.sides[1].team.active
    best_dmg, best_cmd = -1, (0, 0)
    for di, d in enumerate(opp_active):
        for mi, bm in enumerate(pkm.battling_moves):
            if bm.pp == 0 or bm.disabled or bm.constants.category not in (Category.PHYSICAL, Category.SPECIAL):
                continue
            dmg = calculate_damage(params, 0, bm.constants, state, pkm, d)
            if bm.constants.priority > 0 and dmg >= d.hp:
                return (mi, di)
            if dmg > best_dmg:
                best_dmg, best_cmd = dmg, (mi, di)
    return best_cmd if best_dmg >= 0 else (0, 0)


def _try_survival_switch(params, state: State, slot: int) -> BattleCommand | None:
    pkm = state.sides[0].team.active[slot]
    if pkm.hp / max(pkm.constants.stats[Stat.MAX_HP], 1) >= 0.25:
        return None

    opp_active = state.sides[1].team.active
    total_incoming = 0
    for opp in opp_active:
        total_incoming += max(
            (calculate_damage(params, 1, bm.constants, state, opp, pkm)
             for bm in opp.battling_moves
             if bm.pp > 0 and bm.constants.category in (Category.PHYSICAL, Category.SPECIAL)),
            default=0
        )

    if total_incoming < pkm.hp:
        return None

    all_reserve = state.sides[0].team.reserve
    alive = [r for r in all_reserve if r.hp > 0]
    if not alive:
        return None

    best_ri, best_score = None, -1
    for ri, r in enumerate(alive):
        switch_in_threat = sum(
            max(
                (calculate_damage(params, 1, bm.constants, state, opp, r)
                 for bm in opp.battling_moves
                 if bm.pp > 0 and bm.constants.category in (Category.PHYSICAL, Category.SPECIAL)),
                default=0
            )
            for opp in opp_active
        )
        if switch_in_threat >= r.hp:
            continue
        score = sum(
            calculate_damage(params, 0, bm.constants, state, r, opp)
            for opp in opp_active
            for bm in r.battling_moves
            if bm.pp > 0 and bm.constants.category in (Category.PHYSICAL, Category.SPECIAL)
        )
        if score > best_score:
            best_score, best_ri = score, ri

    if best_ri is None:
        return None

    actual_idx = all_reserve.index(alive[best_ri])
    return (-1, actual_idx)


def _best_assignment(params, state: State) -> list[BattleCommand]:
    """
    Solo KO 가능할 때는 파트너를 다른 타겟으로 리다이렉트 (split).
    Solo KO 불가 시에는 합산 KO 보너스 기반 focus-fire.
    """
    active = state.sides[0].team.active
    opp_active = state.sides[1].team.active

    best_dmg    = [[-1]    * len(opp_active) for _ in range(2)]
    best_mi     = [[-1]    * len(opp_active) for _ in range(2)]
    best_is_pko = [[False] * len(opp_active) for _ in range(2)]
    for ai in range(2):
        for di, d in enumerate(opp_active):
            for mi, bm in enumerate(active[ai].battling_moves):
                if bm.pp == 0 or bm.disabled or bm.constants.category not in (Category.PHYSICAL, Category.SPECIAL):
                    continue
                dmg = calculate_damage(params, 0, bm.constants, state, active[ai], d)
                is_pko = bm.constants.priority > 0 and dmg >= d.hp
                if is_pko and not best_is_pko[ai][di]:
                    best_dmg[ai][di], best_mi[ai][di], best_is_pko[ai][di] = dmg, mi, True
                elif is_pko and dmg > best_dmg[ai][di]:
                    best_dmg[ai][di], best_mi[ai][di] = dmg, mi
                elif not best_is_pko[ai][di] and dmg > best_dmg[ai][di]:
                    best_dmg[ai][di], best_mi[ai][di] = dmg, mi

    # Solo KO 기반 split: 한 쪽이 solo KO 가능하면 파트너는 다른 타겟 공격
    if len(opp_active) == 2:
        best_split_score = -1.0
        best_split_cmds = None
        for ai, partner in [(0, 1), (1, 0)]:
            for di in range(2):
                if best_dmg[ai][di] < opp_active[di].hp or best_mi[ai][di] < 0:
                    continue
                other_di = 1 - di
                od = opp_active[other_di]
                ko_partner = 10000 if best_mi[partner][other_di] >= 0 and best_dmg[partner][other_di] >= od.hp else 0
                partner_dmg = max(best_dmg[partner][other_di], 0)
                score = ((best_dmg[ai][di] + 10000) / max(opp_active[di].constants.stats[Stat.MAX_HP], 1) +
                         (partner_dmg + ko_partner) / max(od.constants.stats[Stat.MAX_HP], 1))
                if score > best_split_score:
                    best_split_score = score
                    if ai == 0:
                        best_split_cmds = [(best_mi[0][di], di), (best_mi[1][other_di], other_di)]
                    else:
                        best_split_cmds = [(best_mi[0][other_di], other_di), (best_mi[1][di], di)]

        # Focus-fire KO 점수와 비교해 split이 더 유리할 때만 사용
        if best_split_cmds is not None:
            ff_score = -1.0
            for di, d in enumerate(opp_active):
                combined = max(best_dmg[0][di], 0) + max(best_dmg[1][di], 0)
                ko_bonus = 10000 if combined >= d.hp else 0
                s = (combined + ko_bonus) / max(d.constants.stats[Stat.MAX_HP], 1)
                if s > ff_score:
                    ff_score = s
            if best_split_score >= ff_score:
                return best_split_cmds

    # Fallback: 위협도 가중 focus-fire
    my_spd = [_effective_speed(active[ai], state) for ai in range(2)]

    best_score = -1.0
    best_cmds = [(0, 0), (0, 0)]
    for di, d in enumerate(opp_active):
        opp_spd = _effective_speed(d, state)
        speed_clean = my_spd[0] > opp_spd or my_spd[1] > opp_spd

        threat_d = max(
            (calculate_damage(params, 1, bm.constants, state, d, active[ai])
             for ai in range(2)
             for bm in d.battling_moves
             if bm.pp > 0 and bm.constants.category in (Category.PHYSICAL, Category.SPECIAL)),
            default=0
        )

        for i1, bm1 in enumerate(active[0].battling_moves):
            if bm1.pp == 0 or bm1.disabled or bm1.constants.category not in (Category.PHYSICAL, Category.SPECIAL):
                continue
            dmg1 = calculate_damage(params, 0, bm1.constants, state, active[0], d)
            for i2, bm2 in enumerate(active[1].battling_moves):
                if bm2.pp == 0 or bm2.disabled or bm2.constants.category not in (Category.PHYSICAL, Category.SPECIAL):
                    continue
                dmg2 = calculate_damage(params, 0, bm2.constants, state, active[1], d)
                combined = dmg1 + dmg2
                will_ko = combined >= d.hp
                ko_bonus = (13000 if speed_clean else 10000) if will_ko else 0
                pko_bonus = ((20000 if bm1.constants.priority > 0 and dmg1 >= d.hp else 0) +
                             (20000 if bm2.constants.priority > 0 and dmg2 >= d.hp else 0))
                danger_bonus = threat_d if will_ko else 0
                score = (combined + ko_bonus + pko_bonus) / max(d.constants.stats[Stat.MAX_HP], 1) + danger_bonus * 0.001
                if score > best_score:
                    best_score = score
                    best_cmds = [(i1, di), (i2, di)]
    return best_cmds


def _greedy_single(params, state: State) -> BattleCommand:
    pkm = state.sides[0].team.active[0]
    opp_active = [d for d in state.sides[1].team.active if d is not None]
    if not opp_active:
        return (0, 0)
    best_dmg, best_cmd = -1, (0, 0)
    for di, d in enumerate(opp_active):
        for mi, bm in enumerate(pkm.battling_moves):
            if bm.pp == 0 or bm.disabled or bm.constants.category not in (Category.PHYSICAL, Category.SPECIAL):
                continue
            dmg = calculate_damage(params, 0, bm.constants, state, pkm, d)
            if dmg > best_dmg:
                best_dmg, best_cmd = dmg, (mi, di)
    return best_cmd if best_dmg >= 0 else (0, 0)


def _can_solo_ko(params, state: State, slot: int) -> bool:
    pkm = state.sides[0].team.active[slot]
    for d in state.sides[1].team.active:
        for bm in pkm.battling_moves:
            if bm.pp == 0 or bm.disabled or bm.constants.category not in (Category.PHYSICAL, Category.SPECIAL):
                continue
            if calculate_damage(params, 0, bm.constants, state, pkm, d) >= d.hp:
                return True
    return False


def _partner_can_ko(params, state: State, slot: int) -> bool:
    active = state.sides[0].team.active
    partner_slot = 1 - slot
    if partner_slot >= len(active):
        return False
    partner = active[partner_slot]
    for opp in state.sides[1].team.active:
        for bm in partner.battling_moves:
            if bm.pp > 0 and not bm.disabled and bm.constants.category in (Category.PHYSICAL, Category.SPECIAL):
                if calculate_damage(params, 0, bm.constants, state, partner, opp) >= opp.hp:
                    return True
    return False


def _partner_can_ko_specific(params, state: State, slot: int, opp_di: int) -> bool:
    active = state.sides[0].team.active
    partner_slot = 1 - slot
    if partner_slot >= len(active):
        return False
    partner = active[partner_slot]
    opp = state.sides[1].team.active[opp_di]
    for bm in partner.battling_moves:
        if bm.pp > 0 and not bm.disabled and bm.constants.category in (Category.PHYSICAL, Category.SPECIAL):
            if calculate_damage(params, 0, bm.constants, state, partner, opp) >= opp.hp:
                return True
    return False


def _will_be_koed_first(params, state: State, slot: int) -> bool:
    pkm = state.sides[0].team.active[slot]
    my_spd = _effective_speed(pkm, state)
    for opp in state.sides[1].team.active:
        opp_spd = _effective_speed(opp, state)
        if opp_spd <= my_spd:
            continue
        incoming = max(
            (calculate_damage(params, 1, bm.constants, state, opp, pkm)
             for bm in opp.battling_moves
             if bm.pp > 0 and bm.constants.category in (Category.PHYSICAL, Category.SPECIAL)),
            default=0
        )
        if incoming >= pkm.hp:
            return True
    return False


def _try_protect(params, state: State, slot: int) -> BattleCommand | None:
    pkm = state.sides[0].team.active[slot]

    if pkm._consecutive_protect > 0:
        return None

    protect_idx = None
    for i, bm in enumerate(pkm.battling_moves):
        if bm.constants.protect and bm.pp > 0 and not bm.disabled:
            protect_idx = i
            break
    if protect_idx is None:
        return None

    active = state.sides[0].team.active
    opp_active = state.sides[1].team.active

    # incoming[si]: total max damage from all opponents to slot si
    # incoming_by_opp[di]: max damage from opponent di specifically to our slot
    incoming = [0, 0]
    incoming_by_opp = [0] * len(opp_active)
    for di, d in enumerate(opp_active):
        for si in range(len(active)):
            best = max(
                (calculate_damage(params, 1, bm.constants, state, d, active[si])
                 for bm in d.battling_moves
                 if bm.pp > 0 and bm.constants.category in (Category.PHYSICAL, Category.SPECIAL)),
                default=0
            )
            incoming[si] += best
            if si == slot:
                incoming_by_opp[di] = best

    other = 1 - slot
    if incoming[slot] <= incoming[other]:
        return None

    max_hp = pkm.constants.stats[Stat.MAX_HP]
    primary_di = max(range(len(opp_active)), key=lambda di: incoming_by_opp[di])

    # Survival protect: would be KO'd
    if incoming[slot] >= pkm.hp:
        # Skip protect only if partner can KO the specific primary threat
        if _partner_can_ko_specific(params, state, slot, primary_di):
            return None
        return (protect_idx, 0)

    # Tactical protect: primary threat deals ≥50% HP and partner can KO that same threat
    if (incoming_by_opp[primary_di] >= 0.5 * max_hp and
            _partner_can_ko_specific(params, state, slot, primary_di)):
        return (protect_idx, 0)

    return None


class StrategyBattlePolicy(BattlePolicy):
    def __init__(self, plan_holder: list):
        self._plan_holder = plan_holder

    def decision(self, state: State, opp_view: TeamView | None = None) -> list[BattleCommand]:
        active = state.sides[0].team.active
        if len(active) == 1:
            return [_greedy_single(self.params, state)]

        cmds = [None, None]

        # 1. 위협 슬롯 처리: solo KO 가능하면 공격 위임, 아니면 Protect → switch 순
        for slot in range(2):
            if _can_solo_ko(self.params, state, slot) and not _will_be_koed_first(self.params, state, slot):
                continue
            pt = _try_protect(self.params, state, slot)
            if pt is not None:
                cmds[slot] = pt
                continue
            sw = _try_survival_switch(self.params, state, slot)
            if sw is not None:
                cmds[slot] = sw

        # 2. 자유 슬롯 처리
        free = [s for s in range(2) if cmds[s] is None]
        if len(free) == 2:
            return _best_assignment(self.params, state)
        for slot in free:
            cmds[slot] = _best_move(self.params, state, slot)

        return cmds
