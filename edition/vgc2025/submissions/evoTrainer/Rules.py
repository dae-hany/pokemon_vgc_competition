import copy

from HelperFunctions import HelperFunctions as hf


class Rules:

    def GreedyAttack(self, state, id, damage_threshold, health_threshold):
        pkm = state.sides[0].team.active[id]

        move = hf.getGreedyAttack(state)
        target = state.sides[1].team.active[move[id][1]]
        relative_damage = hf.getRelativeDamage(pkm, target, move[id][0], state, 0)

        cmds = None

        if relative_damage > damage_threshold and hf.relativeHP(pkm) > health_threshold:
            cmds = move[id]

        return hf.checkForValue(cmds)

    def switchAttacked(self, state, id, hp_threshold, damage_threshold):
        pkm = state.sides[0].team.active[id]
        team = state.sides[0].team.reserve
        n_switches = len(team)

        action = -1
        target = None

        switchedTeamStates = copy.copy(state)
        switchedTeamStates.sides = state.sides[::-1]

        enemy_moves_against_pkm = hf.getGreedyDamageAgainstPokemon(switchedTeamStates, id)

        for move_against_pkm in enemy_moves_against_pkm:
            if hf.relativeHP(pkm) < hp_threshold or move_against_pkm[2] > damage_threshold:
                for switch in range(n_switches):
                    switchedTeamStates.sides[0].team.active[0] = team[switch]
                    enemy_moves_against_switch = hf.getGreedyDamageAgainstPokemon(switchedTeamStates, 0)
                    for move_against_switch in enemy_moves_against_switch:
                        if hf.relativeHP(team[switch]) > hp_threshold and move_against_switch[2] < damage_threshold:
                            target = switch

        return hf.checkForValue((action, target))

    def heal(self, state, id, threshold_self, threshold_ally):
        pkm = state.sides[0].team.active[id]
        action = hf.healAttack(pkm)
        target = None
        if len(state.sides[0].team.active) > 1:
            pkm0, pkm1 = state.sides[0].team.active[0], state.sides[0].team.active[1]

            if hf.relativeHP(pkm0) < threshold_self or hf.relativeHP(pkm1) < threshold_ally:
                if pkm0.hp < pkm1.hp:
                    target = 0
                else:
                    target = 1
        return hf.checkForValue((action, target))
