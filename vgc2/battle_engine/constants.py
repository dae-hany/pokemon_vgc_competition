from vgc2.battle_engine.modifiers import Stat, Nature, Type

NATURES = {
    Nature.LONELY: {
        'plus': Stat.ATTACK,
        'minus': Stat.DEFENSE
    },
    Nature.ADAMANT: {
        'plus': Stat.ATTACK,
        'minus': Stat.SPECIAL_ATTACK
    },
    Nature.NAUGHTY: {
        'plus': Stat.ATTACK,
        'minus': Stat.SPECIAL_DEFENSE
    },
    Nature.BRAVE: {
        'plus': Stat.ATTACK,
        'minus': Stat.SPEED
    },
    Nature.BOLD: {
        'plus': Stat.DEFENSE,
        'minus': Stat.ATTACK
    },
    Nature.IMPISH: {
        'plus': Stat.DEFENSE,
        'minus': Stat.SPECIAL_ATTACK
    },
    Nature.LAX: {
        'plus': Stat.DEFENSE,
        'minus': Stat.SPECIAL_DEFENSE
    },
    Nature.RELAXED: {
        'plus': Stat.DEFENSE,
        'minus': Stat.SPEED
    },
    Nature.MODEST: {
        'plus': Stat.SPECIAL_ATTACK,
        'minus': Stat.ATTACK
    },
    Nature.MILD: {
        'plus': Stat.SPECIAL_ATTACK,
        'minus': Stat.DEFENSE
    },
    Nature.RASH: {
        'plus': Stat.SPECIAL_ATTACK,
        'minus': Stat.SPECIAL_DEFENSE
    },
    Nature.QUIET: {
        'plus': Stat.SPECIAL_ATTACK,
        'minus': Stat.SPEED
    },
    Nature.CALM: {
        'plus': Stat.SPECIAL_DEFENSE,
        'minus': Stat.ATTACK
    },
    Nature.GENTLE: {
        'plus': Stat.SPECIAL_DEFENSE,
        'minus': Stat.DEFENSE
    },
    Nature.CAREFUL: {
        'plus': Stat.SPECIAL_DEFENSE,
        'minus': Stat.SPECIAL_ATTACK
    },
    Nature.SASSY: {
        'plus': Stat.SPECIAL_DEFENSE,
        'minus': Stat.SPEED
    },
    Nature.TIMID: {
        'plus': Stat.SPEED,
        'minus': Stat.ATTACK
    },
    Nature.HASTY: {
        'plus': Stat.SPEED,
        'minus': Stat.DEFENSE
    },
    Nature.JOLLY: {
        'plus': Stat.SPEED,
        'minus': Stat.SPECIAL_ATTACK
    },
    Nature.NAIVE: {
        'plus': Stat.SPEED,
        'minus': Stat.SPECIAL_DEFENSE
    },
}


class BattleRuleParam:

    __slots__ = ('DAMAGE_MULTIPLICATION_ARRAY', 'BOOST_MULTIPLIER_LOOKUP', 'ACCURACY_MULTIPLIER_LOOKUP',
                 'TRICKROOM_TURNS', 'WEATHER_TURNS', 'TERRAIN_TURNS', 'REFLECT_TURNS', 'LIGHTSCREEN_TURNS',
                 'TAILWIND_TURNS', 'PARALYSIS_MODIFIER', 'TRICKROOM_MODIFIER', 'PROTECT_MODIFIER', 'THAW_THRESHOLD',
                 'PARALYSIS_THRESHOLD', 'WEATHER_BOOST', 'WEATHER_UNBOOST', 'STAB_MODIFIER', 'BURN_DAMAGE_MODIFIER',
                 'LIGHT_SCREEN_MODIFIER', 'REFLECT_MODIFIER', 'TERRAIN_DAMAGE_BOOST', 'TERRAIN_DAMAGE_UNBOOST',
                 'STEALTH_ROCK_MODIFIER', 'POISON_MODIFIER', 'BURN_MODIFIER', 'SAND_MODIFIER')

    def __init__(self):
        self.DAMAGE_MULTIPLICATION_ARRAY = [[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, .5, 0, 1, 1, .5, 1, 1],
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
                                            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]]
        self.BOOST_MULTIPLIER_LOOKUP = {
            -6: 2 / 8,
            -5: 2 / 7,
            -4: 2 / 6,
            -3: 2 / 5,
            -2: 2 / 4,
            -1: 2 / 3,
            0: 2 / 2,
            1: 3 / 2,
            2: 4 / 2,
            3: 5 / 2,
            4: 6 / 2,
            5: 7 / 2,
            6: 8 / 2
        }
        self.ACCURACY_MULTIPLIER_LOOKUP = {
            -6: 3 / 9,
            -5: 3 / 8,
            -4: 3 / 7,
            -3: 3 / 6,
            -2: 3 / 5,
            -1: 3 / 4,
            0: 3 / 3,
            1: 4 / 3,
            2: 5 / 3,
            3: 6 / 3,
            4: 7 / 3,
            5: 8 / 3,
            6: 9 / 3
        }
        self.TRICKROOM_TURNS = 5
        self.WEATHER_TURNS = 5
        self.TERRAIN_TURNS = 5
        self.REFLECT_TURNS = 5
        self.LIGHTSCREEN_TURNS = 5
        self.TAILWIND_TURNS = 5
        # PRIORITY MODIFIERS
        self.PARALYSIS_MODIFIER = .5
        self.TRICKROOM_MODIFIER = -1.
        # THRESHOLD MODIFIERS
        self.PROTECT_MODIFIER = 1 / 3
        self.THAW_THRESHOLD = .2
        self.PARALYSIS_THRESHOLD = .25
        # DAMAGE MODIFIER
        self.WEATHER_BOOST = 1.5
        self.WEATHER_UNBOOST = .5
        self.STAB_MODIFIER = 1.5
        self.BURN_DAMAGE_MODIFIER = .5
        self.LIGHT_SCREEN_MODIFIER = .5
        self.REFLECT_MODIFIER = .5
        self.TERRAIN_DAMAGE_BOOST = 1.3
        self.TERRAIN_DAMAGE_UNBOOST = .5
        self.STEALTH_ROCK_MODIFIER = .125
        self.POISON_MODIFIER = .125
        self.BURN_MODIFIER = .0625
        self.SAND_MODIFIER = .125

    def print_delta(self, reference=None):
        """Prints differences using __slots__ instead of __dict__."""
        if reference is None:
            reference = BattleRuleParam()

        print(f"{'ATTRIBUTE':<25} | {'ORIGINAL':<10} | {'NEW':<10} | {'CHANGE'}")
        print("-" * 75)

        # We iterate over __slots__ instead of __dict__.items()
        for attr in self.__slots__:
            value = getattr(self, attr)

            # 1. Handle Simple Numerical Attributes
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                orig_val = getattr(reference, attr)
                if value != orig_val:
                    diff = value - orig_val
                    print(f"{attr:<25} | {orig_val:<10.4f} | {value:<10.4f} | {diff:+.4f}")

        # 2. Compare Type Matrix (Directly access by name since it's in slots)
        print("\n--- TYPE CHART CHANGES ---")
        type_changes = 0
        for r in range(len(self.DAMAGE_MULTIPLICATION_ARRAY)):
            for c in range(len(self.DAMAGE_MULTIPLICATION_ARRAY[0])):
                new_v = self.DAMAGE_MULTIPLICATION_ARRAY[r][c]
                old_v = reference.DAMAGE_MULTIPLICATION_ARRAY[r][c]
                if new_v != old_v:
                    print(f"Type {Type(r).name} vs Type {Type(c).name}: {old_v} -> {new_v}")
                    type_changes += 1

        if type_changes == 0:
            print("No changes found in type effectiveness.")
