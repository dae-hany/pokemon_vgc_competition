from vgc2.agent import SelectionPolicy, SelectionCommand, TeamBuildPolicy
from vgc2.battle_engine import Team
from vgc2.meta import Roster, Meta


def unique_crop_filter(lst, max_size):
    seen = set()
    result = []
    for item in lst:
        if item >= max_size:  # skip elements too large
            continue
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result[:max_size]


def sanitized_selection_decision(agent: SelectionPolicy,
                                 teams: tuple[Team, Team],
                                 max_size: int) -> SelectionCommand:
    return unique_crop_filter(agent.decision(teams, max_size), max_size)


def fix_builds(builds, max_team_size, max_pkm_moves):
    fixed_builds = []

    for build in builds[:max_team_size]:  # limit team size
        poke_id, evs, ivs, nature, moves = build

        # Convert to lists for mutability
        evs = list(evs)
        ivs = list(ivs)

        # 1. Clamp EVs to 255
        evs = [min(ev, 255) for ev in evs]

        # 2. If total EVs > 510, normalize
        total_evs = sum(evs)
        if total_evs > 510:
            ratio = 510 / total_evs
            evs = [int(ev * ratio) for ev in evs]

            # Fix rounding loss by distributing leftover points
            leftover = 510 - sum(evs)
            i = 0
            while leftover > 0:
                if evs[i] < 255:  # don't go over 255
                    evs[i] += 1
                    leftover -= 1
                i = (i + 1) % len(evs)

        # 3. Clamp IVs to 31
        ivs = [min(iv, 31) for iv in ivs]

        # 4. Limit moves to max_pkm_moves
        moves = moves[:max_pkm_moves]

        fixed_builds.append((poke_id, tuple(evs), tuple(ivs), nature, moves))

    return fixed_builds


def sanitized_team_build_decision(agent: TeamBuildPolicy,
                                  roster: Roster,
                                  meta: Meta | None,
                                  max_team_size: int,
                                  max_pkm_moves: int,
                                  n_active: int):
    return fix_builds(agent.decision(roster, meta, max_team_size, max_pkm_moves, n_active), max_team_size,
                      max_pkm_moves)
