extends Node

enum Type {
    NORMAL,
    FIRE,
    WATER,
    ELECTRIC,
    GRASS,
    ICE,
    FIGHT,
    POISON,
    GROUND,
    FLYING,
    PSYCHIC,
    BUG,
    ROCK,
    GHOST,
    DRAGON,
    DARK,
    STEEL,
    FAIRY,
    TYPELESS
}

const TYPE_TO_STRINGS := {
    Type.NORMAL: ["0_1.png", "0_2.png", "0_3.png"],
    Type.FIRE: ["1_1.png", "1_2.png", "1_3.png"],
    Type.WATER: ["2_1.png", "2_2.png", "2_3.png"],
    Type.ELECTRIC: ["3_1.png", "3_2.png", "3_3.png"],
    Type.GRASS: ["4_1.png", "4_2.png", "4_3.png"],
    Type.ICE: ["5_1.png", "5_2.png", "5_3.png"],
    Type.FIGHT: ["6_1.png", "6_2.png", "6_3.png"],
    Type.POISON: ["7_1.png", "7_2.png", "7_3.png"],
    Type.GROUND: ["8_1.png", "8_2.png", "8_3.png"],
    Type.FLYING: ["9_1.png", "9_2.png", "9_3.png"],
    Type.PSYCHIC: ["10_1.png", "10_2.png", "10_3.png"],
    Type.BUG: ["11_1.png", "11_2.png", "11_3.png"],
    Type.ROCK: ["12_1.png", "12_2.png", "12_3.png"],
    Type.GHOST: ["13_1.png", "13_2.png", "13_3.png"],
    Type.DRAGON: ["14_1.png", "14_2.png", "14_3.png"],
    Type.DARK: ["15_1.png", "15_2.png", "15_3.png"],
    Type.STEEL: ["16_1.png", "16_2.png", "16_3.png"],
    Type.FAIRY: ["17_1.png", "17_2.png", "17_3.png"]
}
