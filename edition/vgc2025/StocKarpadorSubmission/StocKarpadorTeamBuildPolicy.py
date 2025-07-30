import logging
import time
from typing import List

from numpy.random import choice, multinomial

from vgc2.agent import TeamBuildPolicy, TeamBuildCommand
from vgc2.battle_engine.modifiers import Nature
from vgc2.battle_engine.pokemon import calculate_stats
from vgc2.meta import Roster, Meta

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def evaluate_team(roster, team_indices: List[int]) -> float:
    total_score = 0.0

    for i in team_indices:
        pkm = roster[i]
        try:
            stat_score = sum(calculate_stats(pkm.base_stats, level=100))
            move_damages = []
            for move in pkm.moves:
                try:
                    damage = move.base_power * move.accuracy
                    move_damages.append(damage)
                except Exception as me:
                    logger.warning(f"Move error for Pokémon {i}: {me}")
            best_moves_score = sum(sorted(move_damages, reverse=True)[:4])
            total_score += stat_score + best_moves_score
        except Exception as e:
            logger.warning(f"Error evaluating Pokémon {i}: {e}")
            total_score -= 100

    logger.debug(f"Total team score: {total_score}")
    return total_score


def generate_candidate_teams(roster: Roster, team_size: int, n_candidates: int) -> List[List[int]]:
    logger.info(f"Generating {n_candidates} candidate teams from roster of size {len(roster)}")
    candidates = []
    for _ in range(n_candidates):
        try:
            team = list(choice(len(roster), team_size, replace=False))
            candidates.append(team)
        except Exception as e:
            logger.warning(f"Failed to generate team: {e}")
    return candidates


def build_command(roster: Roster, team_indices: List[int], max_pkm_moves: int) -> TeamBuildCommand:
    cmds: TeamBuildCommand = []
    ivs = (31,) * 6
    logger.debug(f"Building commands for team: {team_indices}")

    for i in team_indices:
        pkm = roster[i]
        if len(pkm.moves) == 0:
            logger.warning(f"Pokémon {i} has no moves!")
            continue
        try:
            move_indices = list(choice(len(pkm.moves), min(max_pkm_moves, len(pkm.moves)), replace=False))
            evs = tuple(multinomial(510, [1 / 6] * 6, size=1)[0])
            nature = Nature(choice(len(Nature), 1, False))
            cmds += [(i, evs, ivs, nature, move_indices)]
        except Exception as e:
            logger.warning(f"Error building command for Pokémon {i}: {e}")
    return cmds


class HeuristicTeamBuildPolicy(TeamBuildPolicy):
    def __init__(self, n_candidates: int = 200000):
        self.n_candidates = n_candidates

    def decision(self,
                 roster: Roster,
                 meta: Meta | None,
                 max_team_size: int,
                 max_pkm_moves: int,
                 n_active: int) -> TeamBuildCommand:
        start_time = time.time()
        candidates = generate_candidate_teams(roster, max_team_size, self.n_candidates)
        best_team = max(candidates, key=lambda team: evaluate_team(roster, team))
        logger.info(f"Selected best team: {best_team}")
        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"[team build TIMING] Decision took {elapsed_ms:.2f} ms")
        return build_command(roster, best_team, max_pkm_moves)
