import numpy as np
from numpy import array

from vgc2.battle_engine.game_state import Side, State
from vgc2.battle_engine.modifiers import Weather, Terrain, Hazard, Status, Type, Category
from vgc2.battle_engine.move import Move, BattlingMove
from vgc2.battle_engine.pokemon import Pokemon, BattlingPokemon, PokemonSpecies
from vgc2.battle_engine.team import Team, BattlingTeam
from vgc2.util.encoding import EncodeContext


def reverse_calculate_stat(final_stat: int, is_hp: bool, level: int = 100,
                           iv: int = 31, ev: int = 85) -> int:
    """
    Reverses the VGC engine stat formula to find the base stat.
    Assumes Nature.SERIOUS (1.0 multiplier).
    """
    # The bonus gained from IVs and EVs
    # Formula part: floor(iv + ev/4)
    stat_bonus = int(iv + (ev / 4))

    if is_hp:
        # Final HP = 2 * Base + Bonus + Level + 10
        base = (final_stat - stat_bonus - level - 10) / 2
    else:
        # Final Other = 2 * Base + Bonus + 5
        base = (final_stat - stat_bonus - 5) / 2

    return int(round(base))


def recover_base_stats(final_stats: list[int], level: int = 100,
                       ivs: tuple = (31,) * 6, evs: tuple = (85,) * 6) -> list[int]:
    """Reconstructs the original base stats list."""
    return [
        reverse_calculate_stat(final_stats[i], i == 0, level, ivs[i], evs[i])
        for i in range(6)
    ]


# Utility decoders for one-hot and multi-hot
def from_one_hot(e: np.ndarray, n: int) -> int:
    for i in range(n):
        if e[i] == 1.0:
            return i
    return -1


def from_multi_hot(e: np.ndarray, n: int) -> list[int]:
    return [j for j in range(n) if e[j] == 1.0]


def decode_move(e: array, ctx: EncodeContext) -> tuple[Move, int]:
    # Extract values from array
    bp = int(round(e[0] * ctx.max_hp))
    acc = e[1]
    pp = int(round(e[2] * ctx.max_pp))
    prio = int(round(e[3] * ctx.max_priority))
    prob = e[4]
    fs, ss, ie, pr = bool(e[5]), bool(e[6]), bool(e[7]), bool(e[8])
    heal, recoil = e[9] * ctx.max_ratio, e[10] * ctx.max_ratio
    tr, refl, ls, tw, ct, dis = bool(e[11]), bool(e[12]), bool(e[13]), bool(e[14]), bool(e[15]), bool(e[16])
    i = 17

    boosts = tuple(int(round(e[i + j] * ctx.max_boost)) for j in range(ctx.n_boosts))
    i += ctx.n_boosts
    # Self-boost flag (-1. if True, 1. if False)
    self_boosts = True if e[i] == -1.0 else False
    i += 1

    pkm_type = Type(from_one_hot(e[i:], ctx.n_types))
    i += ctx.n_types
    cat = Category(from_one_hot(e[i:], ctx.n_category))
    i += ctx.n_category

    w_idx = from_one_hot(e[i:], ctx.n_weather)
    ws = Weather(w_idx + 1) if w_idx != -1 else Weather.CLEAR
    i += ctx.n_weather

    t_idx = from_one_hot(e[i:], ctx.n_terrain)
    fs_terrain = Terrain(t_idx + 1) if t_idx != -1 else Terrain.NONE
    i += ctx.n_terrain

    h_idx = from_one_hot(e[i:], ctx.n_hazard)
    haz = Hazard(h_idx + 1) if h_idx != -1 else Hazard.NONE
    i += ctx.n_hazard

    return Move(pkm_type=pkm_type,
                base_power=bp,
                accuracy=acc,
                max_pp=pp,
                category=cat,
                priority=prio,
                effect_prob=prob,
                force_switch=fs,
                self_switch=ss,
                ignore_evasion=ie,
                protect=pr,
                boosts=boosts,
                self_boosts=self_boosts,
                heal=heal,
                recoil=recoil,
                weather_start=ws,
                field_start=fs_terrain,
                toggle_trickroom=tr,
                toggle_reflect=refl,
                toggle_lightscreen=ls,
                toggle_tailwind=tw,
                hazard=haz,
                disable=dis), i


def decode_battling_move(e: np.ndarray, ctx: EncodeContext) -> tuple[BattlingMove, int]:
    m_const, i = decode_move(e, ctx)
    bm = BattlingMove(m_const)
    bm.disabled = bool(e[i])
    bm.pp = int(round(e[i + 1] * ctx.max_pp))
    return bm, i + 2


def decode_battling_pokemon(e: np.ndarray, ctx: EncodeContext) -> tuple[BattlingPokemon, int]:
    i = 0
    stats = [int(round(e[j] * ctx.max_hp)) for j in range(ctx.n_stats)]
    # Recover Base Stats to feed into the Species constructor
    base_stats = tuple(recover_base_stats(stats))
    i += ctx.n_stats

    battling_moves = []
    moves = []
    for _ in range(4):
        bm, bm_len = decode_battling_move(e[i:], ctx)
        battling_moves.append(bm)
        moves.append(bm.constants)
        i += bm_len

    hp = e[i] * ctx.max_hp
    i += 1
    type_indexes = from_multi_hot(e[i:], ctx.n_types)
    types = []
    for t in type_indexes:
        types += [Type(t)]
    i += ctx.n_types
    boosts = [int(round(e[i + j] * ctx.max_boost)) for j in range(ctx.n_boosts)]
    i += ctx.n_boosts
    s_idx = from_one_hot(e[i:], ctx.n_status) + 1
    status = Status(s_idx) if s_idx != 0 else Status.NONE
    i += ctx.n_status

    prot, wake = bool(e[i]), int(round(e[i + 1] * ctx.max_sleep))
    i += 2

    # Construct constant objects
    species = PokemonSpecies(types=types, base_stats=base_stats, moves=moves)
    pkm = Pokemon(species=species, move_indexes=[0, 1, 2, 3])
    bp = BattlingPokemon(pkm)
    bp.hp, bp.status, bp.boosts, bp.protect, bp._wake_turns = hp, status, boosts, prot, wake
    for j, bm in enumerate(battling_moves):
        bp.battling_moves[j].pp = bm.pp
        bp.battling_moves[j].disabled = bm.disabled
    return bp, i


def decode_pokemon(e: np.ndarray, ctx: EncodeContext) -> tuple[Pokemon, int]:
    i = 0
    # 1. Decode the 4 moves in the fixed movepool
    moves = []
    for _ in range(4):
        m, m_len = decode_move(e[i:], ctx)
        moves.append(m)
        i += m_len

    # 2. Decode the base stats (HP, Atk, Def, SpA, SpD, Spe)
    stats = [int(round(e[i + j] * ctx.max_hp)) for j in range(ctx.n_stats)]
    base_stats = tuple(recover_base_stats(stats))
    i += ctx.n_stats

    # 3. Decode the species types (Multi-hot)
    types = from_multi_hot(e[i:], ctx.n_types)
    i += ctx.n_types

    # 4. Use the proper constructors to rebuild the hierarchy
    species = PokemonSpecies(types=[Type(i) for i in types], base_stats=base_stats, moves=moves)
    pokemon = Pokemon(species=species, move_indexes=[0, 1, 2, 3])

    return pokemon, i


def decode_battling_team(e: np.ndarray, ctx: EncodeContext, n_active: int = 2, n_reserve: int = 2) -> tuple[BattlingTeam, int]:
    # BattlingTeam is usually 1 active, 3 reserve
    active_pkm, reserve_pkm = [], []
    i = 0
    for j in range(n_active):
        active, k = decode_battling_pokemon(e[i:], ctx)
        active_pkm.append(active)
        i += k
    for j in range(n_reserve):
        reserve, k = decode_battling_pokemon(e[i:], ctx)
        reserve_pkm.append(reserve)
        i += k
    team = BattlingTeam(active_pkm, reserve_pkm)
    return team, i


def decode_team(e: np.ndarray, ctx: EncodeContext) -> tuple[Team, int]:
    i = 0
    members = []
    # A standard VGC team consists of 4 Pokémon
    # (Note: Adjust range if your specific competition format uses 6)
    for _ in range(4):
        p, p_len = decode_pokemon(e[i:], ctx)
        members.append(p)
        i += p_len

    # Instantiate using the Team constructor
    # The Team constructor typically takes a list of Pokemon objects
    team = Team(members=members)

    return team, i


def decode_side(e: np.ndarray, ctx: EncodeContext, n_active: int = 2, n_reserve: int = 2) -> tuple[Side, int]:
    team, i = decode_battling_team(e, ctx, n_active, n_reserve)
    side = Side(team)
    side.conditions.reflect = bool(e[i])
    side.conditions.lightscreen = bool(e[i + 1])
    side.conditions.tailwind = bool(e[i + 2])
    side.conditions.stealth_rock = bool(e[i + 3])
    side.conditions.poison_spikes = bool(e[i + 4])
    return side, i + 5


def decode_state(e: np.ndarray, ctx: EncodeContext, n_active: int = 1, n_reserve: int = 3) -> State:
    i = 0
    # The State constructor initializes default sides, but we'll replace them
    # with our decoded Side objects to ensure correct team linking.
    sides = []

    # 1. Decode Both Sides
    for _ in range(2):
        side, side_len = decode_side(e[i:], ctx, n_active, n_reserve)
        sides.append(side)
        i += side_len

    state = State((sides[0].team, sides[1].team))
    state.sides[0].conditions = sides[0].conditions
    state.sides[1].conditions = sides[1].conditions

    # 2. Decode Global Weather
    w_idx = from_one_hot(e[i:], ctx.n_weather)
    state.weather = Weather(w_idx + 1) if w_idx != -1 else Weather.CLEAR
    i += ctx.n_weather

    # 3. Decode Global Terrain
    t_idx = from_one_hot(e[i:], ctx.n_terrain)
    state.field = Terrain(t_idx + 1) if t_idx != -1 else Terrain.NONE
    i += ctx.n_terrain

    # 4. Decode Global Trick Room
    state.trickroom = bool(e[i])

    return state
