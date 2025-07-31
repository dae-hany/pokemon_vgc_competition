import itertools
import time

from numpy.random import choice

from vgc2.agent import TeamBuildPolicy, TeamBuildCommand
from vgc2.battle_engine.modifiers import Nature, Stat, Category, Hazard, Status
from vgc2.meta import Meta, Roster


def analyze_pokemon(pokemon):
    roles = set()
    coverage = set()

    atk = pokemon.base_stats[Stat.ATTACK]
    spa = pokemon.base_stats[Stat.SPECIAL_ATTACK]
    spe = pokemon.base_stats[Stat.SPEED]

    if atk > spa and atk > 100:
        roles.add("physical_attacker")
    elif spa > atk and spa > 100:
        roles.add("special_attacker")

    if spe > 100:
        roles.add("fast")
    for move in pokemon.moves:
        move_type = move.pkm_type
        move_cat = move.category

        if move_cat in (Category.SPECIAL, Category.PHYSICAL):
            coverage.add(move_type)

        if move.priority > 0:
            roles.add("priority_user")

        if move.heal > 0:
            roles.add("healer")
            roles.add("support")

        if move.toggle_tailwind or move.toggle_trickroom:
            roles.add("speed_control")

        if move.toggle_reflect or move.toggle_lightscreen:
            roles.add("screen_support")

        if move.hazard != Hazard.NONE:
            roles.add("hazard_setter")

        if move.status != Status.NONE:
            roles.add("status_spreader")

        if move.force_switch:
            roles.add("switcher")

        if move.category == Category.OTHER and not move.heal:
            roles.add("disruptor")

        return {
            "name": pokemon.name,
            "types": pokemon.types,
            "roles": sorted(roles),
            "coverage": sorted(coverage)
        }


def calulate_score(ids, roster):
    types = set()
    roles = set()
    coverage = set()
    score = 0.0
    for i in ids:
        pokemon_species = roster[i]
        analytics = analyze_pokemon(pokemon_species)
        types.update(analytics["types"])
        roles.update(analytics["roles"])
        coverage.update(analytics["coverage"])

    score += len(types) * 0.5
    score += len(roles) * 1.0
    score += len(coverage) * 0.3
    return score


def select_strong_team(roster, max_team_size):
    best_team = None
    best_score = -1
    start_time = time.time()
    for combo in itertools.combinations(range(len(roster)), max_team_size):
        score = calulate_score(combo, roster)
        if score > best_score:
            best_score = score
            best_team = combo
        if score >= 10:
            break
        if time.time() - start_time >= 59.5:
            break
    return best_team


def auto_assign_evs_and_nature(pokemon):
    roles = analyze_pokemon(pokemon)['roles']
    evs = [0] * 6
    nature = None

    # Index mapping
    HP, ATK, DEF, SPA, SPD, SPE = range(6)

    # Simple rule-based allocation
    if "physical_attacker" in roles:
        evs[ATK] = 252
        if "fast" in roles:
            evs[SPE] = 252
            nature = Nature.JOLLY
        else:
            evs[HP] = 252
            nature = Nature.ADAMANT
    elif "special_attacker" in roles:
        evs[SPA] = 252
        if "fast" in roles:
            evs[SPE] = 252
            nature = Nature.TIMID
        else:
            evs[HP] = 252
            nature = Nature.MODEST
    elif "fast" in roles:
        evs[SPE] = 252
        evs[HP] = 252
        nature = Nature.TIMID
    elif "support" in roles:
        evs[HP] = 252
        evs[SPD] = 252
        nature = Nature.CAREFUL
    else:
        evs[HP] = 252
        evs[DEF] = 128
        evs[SPD] = 128
        nature = Nature.CALM

    # Remainder to fill 510 total
    remainder = 510 - sum(evs)
    for i in range(6):
        if remainder <= 0:
            break
        add = min(remainder, 252 - evs[i])
        evs[i] += add
        remainder -= add

    return tuple(evs), (31,) * 6, nature


class IceMonteTeamBuildPolicy(TeamBuildPolicy):

    def decision(
            self,
            roster: Roster,
            meta: Meta | None,
            max_team_size: int,
            max_pkm_moves: int,
            n_active: int,
    ) -> TeamBuildCommand:
        start = time.time()
        team = select_strong_team(roster, 6)
        print(time.time() - start)
        cmds: TeamBuildCommand = []
        for i in team:
            n_moves = len(roster[i].moves)
            moves = list(choice(n_moves, min(max_pkm_moves, n_moves), False))
            pokemon = roster[i]
            evs, ivs, nature = auto_assign_evs_and_nature(pokemon)
            cmds += [(i, evs, ivs, nature, moves)]
        return cmds
