from vgc2.battle_engine.constants import BattleRuleParam
from vgc2.battle_engine.game_state import State
from vgc2.battle_engine.modifiers import (
    Category,
    MutableStats,
    Status,
    Terrain,
    Type,
    Weather,
)
from vgc2.battle_engine.move import Move
from vgc2.battle_engine.pokemon import BattlingPokemon, Stat

# Pre-compute category to stat mappings for faster lookups
_CATEGORY_TO_ATTACK_STAT = {
    Category.PHYSICAL: Stat.ATTACK,
    Category.SPECIAL: Stat.SPECIAL_ATTACK,
}
_CATEGORY_TO_DEFENSE_STAT = {
    Category.PHYSICAL: Stat.DEFENSE,
    Category.SPECIAL: Stat.SPECIAL_DEFENSE,
}

# Pre-compute type effectiveness for weather defense boosts
_WEATHER_DEFENSE_TYPES = {
    (Weather.SAND, Type.ROCK): Stat.SPECIAL_DEFENSE,
    (Weather.SNOW, Type.ICE): Stat.DEFENSE,
}

# Pre-compute weather modifier lookup
_WEATHER_MODIFIERS = {
    (Weather.SUN, Type.FIRE): 1,  # Will be multiplied by WEATHER_BOOST
    (Weather.SUN, Type.WATER): -1,  # Will be multiplied by WEATHER_UNBOOST
    (Weather.RAIN, Type.WATER): 1,  # Will be multiplied by WEATHER_BOOST
    (Weather.RAIN, Type.FIRE): -1,  # Will be multiplied by WEATHER_UNBOOST
}

# Pre-compute terrain modifiers
_TERRAIN_MODIFIERS = {
    (Terrain.ELECTRIC_TERRAIN, Type.ELECTRIC): 1,  # TERRAIN_DAMAGE_BOOST
    (Terrain.GRASSY_TERRAIN, Type.GRASS): 1,  # TERRAIN_DAMAGE_BOOST
    (Terrain.MISTY_TERRAIN, Type.DRAGON): -1,  # TERRAIN_DAMAGE_UNBOOST
    (Terrain.PSYCHIC_TERRAIN, Type.PSYCHIC): 1,  # TERRAIN_DAMAGE_BOOST
}

# Sand immunity types
_SAND_IMMUNE_TYPES = frozenset([Type.ROCK, Type.GROUND, Type.STEEL])


def calculate_damage(
        params: BattleRuleParam,
        attacking_side: int,
        move: Move,
        state: State,
        attacker: BattlingPokemon,
        defender: BattlingPokemon,
) -> int:
    # Early returns for edge cases
    move_category = move.category
    if move_category not in _CATEGORY_TO_ATTACK_STAT or move.base_power == 0:
        return 0

    # Get stats for damage calculation
    attack_stat = _CATEGORY_TO_ATTACK_STAT[move_category]
    defense_stat = _CATEGORY_TO_DEFENSE_STAT[move_category]

    # Calculate boosted stats using vectorized operations
    attacker_boosts = attacker.boosts
    defender_boosts = defender.boosts
    attacker_base_stats = attacker.constants.stats
    defender_base_stats = defender.constants.stats
    boost_lookup = params.BOOST_MULTIPLIER_LOOKUP

    # Calculate attack and defense with boosts
    attack_power = int(boost_lookup[attacker_boosts[attack_stat]] * attacker_base_stats[attack_stat])
    defense_power = int(boost_lookup[defender_boosts[defense_stat]] * defender_base_stats[defense_stat])

    # Weather defense boost (inlined)
    weather = state.weather
    if weather != Weather.CLEAR:
        for defender_type in defender.types:
            weather_defense_key = (weather, defender_type)
            if weather_defense_key in _WEATHER_DEFENSE_TYPES:
                if _WEATHER_DEFENSE_TYPES[weather_defense_key] == defense_stat:
                    defense_power = int(defense_power * params.WEATHER_BOOST)
                break

    # Core damage formula (inlined level calculation)
    level = attacker.constants.level
    damage = ((2 * level // 5) + 2) * move.base_power
    damage = damage * attack_power // defense_power
    damage = damage // 50 + 2

    # Calculate all modifiers in one pass
    modifier = 1.0

    # Type effectiveness (inlined)
    move_type = move.pkm_type
    if move_type != Type.TYPELESS:
        damage_mult_array = params.DAMAGE_MULTIPLICATION_ARRAY[move_type]
        for defending_type in defender.types:
            modifier *= damage_mult_array[defending_type]

    # Weather modifier (inlined)
    if weather != Weather.CLEAR:
        weather_key = (weather, move_type)
        if weather_key in _WEATHER_MODIFIERS:
            weather_mult = _WEATHER_MODIFIERS[weather_key]
            if weather_mult == 1:
                modifier *= params.WEATHER_BOOST
            else:
                modifier *= params.WEATHER_UNBOOST

    # STAB modifier (inlined)
    if move_type != Type.TYPELESS and move_type in attacker.types:
        modifier *= params.STAB_MODIFIER

    # Burn modifier (inlined)
    if attacker.status == Status.BURN and move_category == Category.PHYSICAL:
        modifier *= params.BURN_DAMAGE_MODIFIER

    # Terrain modifier (inlined)
    terrain = state.field
    if terrain != Terrain.NONE:
        if terrain == Terrain.PSYCHIC_TERRAIN and move.priority > 0:
            return 0  # Priority moves blocked

        terrain_key = (terrain, move_type)
        if terrain_key in _TERRAIN_MODIFIERS:
            terrain_mult = _TERRAIN_MODIFIERS[terrain_key]
            if terrain_mult == 1:
                modifier *= params.TERRAIN_DAMAGE_BOOST
            else:
                modifier *= params.TERRAIN_DAMAGE_UNBOOST

    # Screen modifiers (inlined) - following original implementation
    attacking_side_conditions = state.sides[attacking_side].conditions
    if move_category == Category.SPECIAL and attacking_side_conditions.lightscreen:
        modifier *= params.LIGHT_SCREEN_MODIFIER
    elif move_category == Category.PHYSICAL and attacking_side_conditions.reflect:
        modifier *= params.REFLECT_MODIFIER

    # Apply modifier and return
    return int(damage * modifier)


def calculate_boosted_stats(
        params: BattleRuleParam, pkm: BattlingPokemon
) -> MutableStats:
    # Vectorized stat calculation
    boosts = pkm.boosts
    base_stats = pkm.constants.stats
    boost_lookup = params.BOOST_MULTIPLIER_LOOKUP

    return [
        0,
        int(boost_lookup[boosts[Stat.ATTACK]] * base_stats[Stat.ATTACK]),
        int(boost_lookup[boosts[Stat.DEFENSE]] * base_stats[Stat.DEFENSE]),
        int(boost_lookup[boosts[Stat.SPECIAL_ATTACK]] * base_stats[Stat.SPECIAL_ATTACK]),
        int(boost_lookup[boosts[Stat.SPECIAL_DEFENSE]] * base_stats[Stat.SPECIAL_DEFENSE]),
    ]


def calculate_modifier(
        params: BattleRuleParam,
        attacker: BattlingPokemon,
        defender: BattlingPokemon,
        move: Move,
        state: State,
        attacking_side: int,
) -> float:
    # This function kept for API compatibility but optimized
    modifier = 1.0

    # Type effectiveness
    move_type = move.pkm_type
    if move_type != Type.TYPELESS:
        damage_mult_array = params.DAMAGE_MULTIPLICATION_ARRAY[move_type]
        for defending_type in defender.types:
            modifier *= damage_mult_array[defending_type]

    # Weather modifier
    weather = state.weather
    if weather != Weather.CLEAR:
        weather_key = (weather, move_type)
        if weather_key in _WEATHER_MODIFIERS:
            weather_mult = _WEATHER_MODIFIERS[weather_key]
            if weather_mult == 1:
                modifier *= params.WEATHER_BOOST
            else:
                modifier *= params.WEATHER_UNBOOST

    # STAB modifier
    if move_type != Type.TYPELESS and move_type in attacker.types:
        modifier *= params.STAB_MODIFIER

    # Burn modifier
    if attacker.status == Status.BURN and move.category == Category.PHYSICAL:
        modifier *= params.BURN_DAMAGE_MODIFIER

    # Terrain modifier
    terrain = state.field
    if terrain != Terrain.NONE:
        terrain_key = (terrain, move_type)
        if terrain_key in _TERRAIN_MODIFIERS:
            terrain_mult = _TERRAIN_MODIFIERS[terrain_key]
            if terrain_mult == 1:
                modifier *= params.TERRAIN_DAMAGE_BOOST
            else:
                modifier *= params.TERRAIN_DAMAGE_UNBOOST

    # Screen modifiers - following original implementation
    attacking_side_conditions = state.sides[attacking_side].conditions
    if move.category == Category.SPECIAL and attacking_side_conditions.lightscreen:
        modifier *= params.LIGHT_SCREEN_MODIFIER
    elif move.category == Category.PHYSICAL and attacking_side_conditions.reflect:
        modifier *= params.REFLECT_MODIFIER

    return modifier


def type_effectiveness_modifier(
        params: BattleRuleParam, move_type: Type, defending_types: list[Type]
) -> float:
    if move_type == Type.TYPELESS:
        return 1.0

    damage_mult_array = params.DAMAGE_MULTIPLICATION_ARRAY[move_type]
    modifier = 1.0
    for defending_type in defending_types:
        modifier *= damage_mult_array[defending_type]
    return modifier


def weather_modifier(params: BattleRuleParam, move: Move, weather: Weather) -> float:
    if weather == Weather.CLEAR:
        return 1.0

    weather_key = (weather, move.pkm_type)
    if weather_key in _WEATHER_MODIFIERS:
        weather_mult = _WEATHER_MODIFIERS[weather_key]
        if weather_mult == 1:
            return params.WEATHER_BOOST
        else:
            return params.WEATHER_UNBOOST
    return 1.0


def stab_modifier(
        params: BattleRuleParam, attacker: BattlingPokemon, move: Move
) -> float:
    move_type = move.pkm_type
    if move_type == Type.TYPELESS:
        return 1.0
    return params.STAB_MODIFIER if move_type in attacker.types else 1.0


def burn_modifier(params: BattleRuleParam, attacker: BattlingPokemon, move: Move) -> float:
    return (
        params.BURN_DAMAGE_MODIFIER
        if attacker.status == Status.BURN and move.category == Category.PHYSICAL
        else 1.0
    )


def light_screen_modifier(
        params: BattleRuleParam, move: Move, light_screen: bool
) -> float:
    return (
        params.LIGHT_SCREEN_MODIFIER
        if light_screen and move.category == Category.SPECIAL
        else 1.0
    )


def reflect_modifier(params: BattleRuleParam, move: Move, reflect: bool) -> float:
    return (
        params.REFLECT_MODIFIER if reflect and move.category == Category.PHYSICAL else 1.0
    )


def terrain_modifier(params: BattleRuleParam, move: Move, terrain: Terrain) -> float:
    if terrain == Terrain.NONE:
        return 1.0
    if terrain == Terrain.PSYCHIC_TERRAIN and move.priority > 0:
        return 0.0

    terrain_key = (terrain, move.pkm_type)
    if terrain_key in _TERRAIN_MODIFIERS:
        terrain_mult = _TERRAIN_MODIFIERS[terrain_key]
        if terrain_mult == 1:
            return params.TERRAIN_DAMAGE_BOOST
        else:
            return params.TERRAIN_DAMAGE_UNBOOST
    return 1.0


def calculate_stealth_rock_damage(params: BattleRuleParam, pkm: BattlingPokemon) -> int:
    base_hp = pkm.constants.species.base_stats[Stat.MAX_HP]
    type_effectiveness = type_effectiveness_modifier(params, Type.ROCK, pkm.types)
    return int(base_hp * params.STEALTH_ROCK_MODIFIER * type_effectiveness)


def calculate_poison_damage(params: BattleRuleParam, pkm: BattlingPokemon) -> int:
    return int(pkm.constants.species.base_stats[Stat.MAX_HP] * params.POISON_MODIFIER)


def calculate_burn_damage(params: BattleRuleParam, pkm: BattlingPokemon) -> int:
    return int(pkm.constants.species.base_stats[Stat.MAX_HP] * params.BURN_MODIFIER)


def calculate_sand_damage(params: BattleRuleParam, pkm: BattlingPokemon) -> int:
    # Check immunity using pre-computed set
    for pkm_type in pkm.types:
        if pkm_type in _SAND_IMMUNE_TYPES:
            return 0
    return int(pkm.constants.species.base_stats[Stat.MAX_HP] * params.SAND_MODIFIER)
