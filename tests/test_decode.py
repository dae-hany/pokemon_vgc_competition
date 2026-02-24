import numpy as np
import pytest

from vgc2.battle_engine import Move, Type, Category, BattlingMove, Status, Team, State, Weather, BattlingTeam, Side, \
    Terrain
from vgc2.battle_engine.pokemon import PokemonSpecies, Pokemon, BattlingPokemon
from vgc2.util.decoding import decode_move, decode_battling_move, decode_battling_pokemon, decode_pokemon, decode_team, \
    decode_state, decode_battling_team, decode_side
from vgc2.util.encoding import EncodeContext, encode_move, encode_battling_move, encode_battling_pokemon, \
    encode_pokemon, encode_team, encode_state, encode_battling_team, encode_side


@pytest.fixture
def ctx():
    """Provides a standard encoding context."""
    return EncodeContext()


@pytest.fixture
def buffer():
    """Provides a clean buffer for encoding."""
    return np.zeros(10000)


def test_move_roundtrip(ctx, buffer):
    original = Move(pkm_type=Type.FIRE, base_power=90, accuracy=0.9, max_pp=15, category=Category.SPECIAL)
    encode_move(buffer, original, ctx)
    decoded, _ = decode_move(buffer, ctx)
    assert decoded.pkm_type == Type.FIRE
    assert decoded.base_power == 90
    assert decoded.accuracy == 0.9
    assert decoded.max_pp == 15
    assert decoded.category == Category.SPECIAL


def test_battling_move_roundtrip(ctx, buffer):
    # 1. Create a base Move (Constant data)
    base_move = Move(
        pkm_type=Type.ELECTRIC,  # e.g., Electric
        base_power=95,
        accuracy=1.0,
        max_pp=15,
        category=Category.SPECIAL,  # Special
        priority=0,
        name="Thunderbolt"
    )

    # 2. Create the BattlingMove (Dynamic data)
    original_bm = BattlingMove(base_move)
    original_bm.pp = 12  # Used 3 PP
    original_bm.disabled = True

    # 3. Round-trip
    encode_battling_move(buffer, original_bm, ctx)
    decoded_bm, length = decode_battling_move(buffer, ctx)

    # 4. Assertions - Dynamic State
    assert decoded_bm.pp == 12
    assert decoded_bm.disabled is True

    # 5. Assertions - Constant State (Constructor check)
    assert decoded_bm.constants.base_power == 95
    assert decoded_bm.constants.pkm_type == 3
    assert decoded_bm.constants.max_pp == 15
    assert decoded_bm.constants.category == 2


def test_battling_pokemon_roundtrip(ctx, buffer):
    # 1. Setup Constant Data (The Pokemon base)
    moves = [Move(pkm_type=Type.NORMAL, base_power=40, accuracy=1.0, max_pp=20, category=Category.PHYSICAL) for _ in
             range(4)]
    species = PokemonSpecies(types=[Type.NORMAL, Type.DARK], base_stats=(100, 80, 90, 110, 100, 110), moves=moves)
    # Give it 4 moves
    base_pkm = Pokemon(species=species, move_indexes=[0, 1, 2, 3])

    # 2. Setup Battling State (The dynamic data)
    original_bp = BattlingPokemon(base_pkm)
    original_bp.hp = 75.0  # Current HP
    original_bp.status = Status.SLEEP
    original_bp._wake_turns = 2
    original_bp.boosts[0] = 2  # +2 Attack
    original_bp.boosts[1] = -1  # -1 Defense
    original_bp.protect = True

    # Set PP for the first move
    original_bp.battling_moves[0].pp = 15

    # 3. Round-trip
    encode_battling_pokemon(buffer, original_bp, ctx)
    decoded_bp, length = decode_battling_pokemon(buffer, ctx)

    # 4. Assertions - Core Stats & Types
    assert decoded_bp.hp == pytest.approx(75.0)
    assert set(decoded_bp.types) == {Type.NORMAL, Type.DARK}
    assert decoded_bp.status == Status.SLEEP
    assert decoded_bp._wake_turns == 2

    # 5. Assertions - Boosts
    assert decoded_bp.boosts[0] == 2
    assert decoded_bp.boosts[1] == -1

    # 6. Assertions - Move State
    assert decoded_bp.battling_moves[0].pp == 15
    assert decoded_bp.protect is True

    # 7. Assertions - Constant Data Integrity
    assert decoded_bp.constants.species.base_stats == (100, 80, 90, 110, 100, 110)


def test_pokemon_roundtrip(ctx, buffer):
    species = PokemonSpecies(types=[Type.NORMAL, Type.ICE], base_stats=(100,) * 6,
                             moves=[Move(Type.NORMAL, 50, 1, 20, Category.PHYSICAL)] * 4)
    original = Pokemon(species=species, move_indexes=[0, 1, 2, 3])
    encode_pokemon(buffer, original, ctx)
    decoded, _ = decode_pokemon(buffer, ctx)
    assert decoded.species.base_stats == (100,) * 6
    assert set(decoded.species.types) == {Type.NORMAL, Type.ICE}
    assert decoded.moves[0].base_power == 50
    assert decoded.moves[0].max_pp == 20
    assert decoded.moves[0].category == Category.PHYSICAL


def test_battling_team_roundtrip(ctx, buffer):
    # 1. Create a helper to generate unique Pokemon
    def create_test_pkm(p_type, hp_val):
        moves = [Move(pkm_type=p_type, base_power=40, accuracy=1.0, max_pp=20,
                      category=Category.PHYSICAL) for _ in range(4)]
        # Use a distinctive base stat for each to verify they don't mix up
        species = PokemonSpecies(types=[p_type],
                                 base_stats=(hp_val, 80, 80, 80, 80, 80),
                                 moves=moves)
        return Pokemon(species=species, move_indexes=[0, 1, 2, 3])

    # 2. Setup the Team
    active = [BattlingPokemon(create_test_pkm(Type.FIRE, 100))]

    # Setup 3 Reserves (e.g., Water, Grass, Electric)
    res_types = [Type.WATER, Type.GRASS, Type.ELECTRIC]
    res_hps = [110, 120, 130]
    reserve = []
    for t, h in zip(res_types, res_hps):
        bp = BattlingPokemon(create_test_pkm(t, h))
        reserve.append(bp)

    original_team = BattlingTeam(active, reserve)
    original_team.active[0].hp = 50.0  # Damaged


    # 3. Round-trip
    total_len = encode_battling_team(buffer, original_team, ctx)
    decoded_team, decoded_len = decode_battling_team(buffer, ctx, 1, 3)

    # 4. Assertions
    assert decoded_len == total_len

    # Check Active
    assert decoded_team.active[0].types == [Type.FIRE]
    assert decoded_team.active[0].hp == 50
    assert decoded_team.active[0].constants.species.base_stats[0] == 100

    # Check Reserves
    assert len(decoded_team.reserve) == 3
    for i in range(3):
        assert decoded_team.reserve[i].types == [res_types[i]]
        assert decoded_team.reserve[i].constants.species.base_stats[0] == res_hps[i]


def test_team_roundtrip(ctx, buffer):
    moves = [Move(Type.NORMAL, 40, 1, 20, Category.PHYSICAL)] * 4
    p = Pokemon(species=PokemonSpecies(types=[Type.NORMAL], base_stats=(100,) * 6, moves=moves),
                move_indexes=[0, 1, 2, 3])
    original = Team(members=[p, p, p, p])
    encode_team(buffer, original, ctx)
    decoded, _ = decode_team(buffer, ctx)
    assert len(decoded.members) == 4
    assert decoded.members[0].species.base_stats[0] == 100


def test_side_roundtrip(ctx, buffer):
    # 1. Helper to create a standard Pokemon for the team
    def create_simple_pkm(p_type, hp_base):
        moves = [Move(pkm_type=p_type, base_power=40, accuracy=1.0, max_pp=20,
                      category=Category.PHYSICAL) for _ in range(4)]
        species = PokemonSpecies(types=[p_type],
                                 base_stats=(hp_base, 80, 80, 80, 80, 80),
                                 moves=moves)
        return Pokemon(species=species, move_indexes=[0, 1, 2, 3])

    # 2. Setup the Team (1 Active, 3 Reserve)
    active = [BattlingPokemon(create_simple_pkm(Type.FIRE, 100))]
    reserve = [BattlingPokemon(create_simple_pkm(Type.WATER, 110)) for _ in range(3)]
    team = BattlingTeam(active, reserve)

    # 3. Setup the Side and specific Conditions
    original_side = Side(team)
    original_side.conditions.reflect = True
    original_side.conditions.lightscreen = False
    original_side.conditions.tailwind = True
    original_side.conditions.stealth_rock = False
    original_side.conditions.poison_spikes = True

    # 4. Round-trip
    total_len = encode_side(buffer, original_side, ctx)
    # Ensure your decode_side passes the correct (1, 3) count to decode_battling_team
    decoded_side, decoded_len = decode_side(buffer, ctx, 1, 3)

    # 5. Assertions - Length and Team Integrity
    assert decoded_len == total_len
    assert decoded_side.team.active[0].types == [Type.FIRE]
    assert len(decoded_side.team.reserve) == 3

    # 6. Assertions - Side Conditions (The "Footer" of the side encoding)
    assert decoded_side.conditions.reflect is True
    assert decoded_side.conditions.lightscreen is False
    assert decoded_side.conditions.tailwind is True
    assert decoded_side.conditions.stealth_rock is False
    assert decoded_side.conditions.poison_spikes is True


def create_pkm(p_type: Type, hp_base: int):
    moves = [Move(pkm_type=p_type, base_power=40, accuracy=1.0, max_pp=20,
                  category=Category.PHYSICAL) for _ in range(4)]
    species = PokemonSpecies(types=[p_type], base_stats=(hp_base, 80, 80, 80, 80, 80), moves=moves)
    return Pokemon(species=species, move_indexes=[0, 1, 2, 3])


def test_state_roundtrip(ctx, buffer):
    # Setup Side 0 (Fire)
    p0 = create_pkm(Type.FIRE, 100)
    team0 = BattlingTeam([BattlingPokemon(p0)], [BattlingPokemon(p0) for _ in range(3)])

    # Setup Side 1 (Water)
    p1 = create_pkm(Type.WATER, 120)
    team1 = BattlingTeam([BattlingPokemon(p1)], [BattlingPokemon(p1) for _ in range(3)])

    # 1. Setup State
    original_state = State((team0, team1))
    original_state.sides[0].conditions.reflect = True
    original_state.sides[1].conditions.tailwind = True

    # Setup Global Effects
    original_state.weather = Weather.SAND
    original_state.field = Terrain.GRASSY_TERRAIN
    original_state.trickroom = True

    # 2. Round-trip
    encode_state(buffer, original_state, ctx)
    # Using 1 active and 3 reserve to match the setup above
    decoded_state = decode_state(buffer, ctx, n_active=1, n_reserve=3)

    # 3. Assertions - Environmental
    assert decoded_state.weather == Weather.SAND
    assert decoded_state.field == Terrain.GRASSY_TERRAIN
    assert decoded_state.trickroom is True

    # 4. Assertions - Side 0
    assert decoded_state.sides[0].team.active[0].types == [Type.FIRE]
    assert decoded_state.sides[0].conditions.reflect is True

    # 5. Assertions - Side 1 (The critical offset check)
    assert decoded_state.sides[1].team.active[0].types == [Type.WATER]
    assert decoded_state.sides[1].conditions.tailwind is True
    assert decoded_state.sides[1].team.active[0].constants.species.base_stats[0] == 120
