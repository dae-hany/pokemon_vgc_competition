import heapq
import random

import numpy as np
from numpy.random import choice

from vgc2.agent import TeamBuildPolicy, TeamBuildCommand
from vgc2.battle_engine.modifiers import Nature
from vgc2.balance import Meta, Roster


class PeachTeamBuildPolicy(TeamBuildPolicy):
    """
    build a team considering different base stats
    """

    def decision(self,
                 roster: Roster,
                 meta: Meta | None,
                 max_team_size: int,
                 max_pkm_moves: int,
                 n_active: int) -> TeamBuildCommand:
        ivs = (31,) * 6
        # build team_test nr of different teams and choose the best one
        team_test = 15
        cmds: TeamBuildCommand = []

        # create list that contains roster index and relevant stats for a pokemon
        indexed_roster = []
        for i in range(len(roster)):
            status_move_count = 0
            # count status moves
            for move in roster[i].moves:
                if move.status != 0:
                    status_move_count += 1
            indexed_roster.append((roster[i], i, roster[i].base_stats[5], roster[i].base_stats[0],
                                   roster[i].base_stats[1], roster[i].base_stats[3], status_move_count))

        # select the x fastest pokemon needed to build team_test amount of teams from the roster
        speedy_pkm = heapq.nlargest(max_team_size * team_test, indexed_roster, key=lambda x: x[2])

        teams = []

        # create team_test amount of teams from the fast pokemon
        for i in range(team_test):
            teams.append((random.sample(speedy_pkm, max_team_size)))

        # calculate score for each team: add up the hp, attack, special_attack and amount of status moves, with attack and status moves weighed more heavily
        teamsums = np.zeros(team_test)
        for j in range(team_test):
            for i in range(max_team_size):
                teamsums[j] += teams[j][i][3] + 10 * teams[j][i][4] + teams[j][i][5] + 50 * teams[j][i][6]

        # select team with highest score
        max_team = np.argmax(teamsums)

        # add moves/evs/nature 
        for i in range(max_team_size):
            id = teams[max_team][i][1]
            n_moves = len(roster[id].moves)
            moves = list(choice(n_moves, min(max_pkm_moves, n_moves), False))
            # increase stats that were already high according to score
            evs = tuple([170, 140, 0, 100, 0, 100])
            # nature: adamant: raise attack, lower special attack
            nature = Nature(3)
            cmds += [(id, evs, ivs, nature, moves)]

        return cmds
