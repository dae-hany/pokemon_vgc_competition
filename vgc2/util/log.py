# GPT generated
"""Prompt:
i have a  boosts: tuple[int, int, int, int, int, int, int, int] that correspond to
class Stat:
    # perm
    MAX_HP = 0
    ATTACK = 1
    DEFENSE = 2
    SPECIAL_ATTACK = 3
    SPECIAL_DEFENSE = 4
    SPEED = 5
    # temp
    EVASION = 6
    ACCURACY = 7
I want to convert  this into a message string that says which stats increased or decreased, and in case the increase or decrease is greater than 1 it should say sharply increased"""

stat_names = [
    "Max HP",
    "Attack",
    "Defense",
    "Special Attack",
    "Special Defense",
    "Speed",
    "Evasion",
    "Accuracy"
]


def format_boosts(boosts: tuple[int, int, int, int, int, int, int, int]) -> str:
    messages = []

    for i, change in enumerate(boosts):
        if change == 0:
            continue
        stat = stat_names[i]
        if change >= 2:
            messages.append(f"{stat} sharply increased!")
        elif change == 1:
            messages.append(f"{stat} increased!")
        elif change <= -2:
            messages.append(f"{stat} sharply decreased!")
        elif change == -1:
            messages.append(f"{stat} decreased!")

    return " ".join(messages) if messages else "No stat changes."
