from typing import Optional

from vgc2.agent import BattlePolicy
from vgc2.battle_engine import State, BattleCommand
from vgc2.battle_engine import TeamView, calculate_damage, BattleRuleParam
from vgc2.battle_engine.modifiers import Status


class GreedyIceBattlePolicy(BattlePolicy):

    def __init__(self, switch_prob: float = 0.15):
        self.swapped = False
        self.params = BattleRuleParam()

    def chooseSwapPokemon(self, state):
        teamReserve = state.sides[0].team.reserve
        enemyTeam = state.sides[1].team.active
        bestEffectiveness = -100
        bestPkm = 0
        if teamReserve[0].fainted():
            bestPkm = 1
        # if teamReserve[1].fainted() and teamReserve[0].fainted():
        #    bestPkm = -1
        for i in range(len(teamReserve)):
            pkm = teamReserve[i]
            effectiveness = 0
            for j in range(len(enemyTeam)):
                enemy = enemyTeam[j]
                for move in pkm.battling_moves:
                    # effectiveness += ((attack * utils.COUNTER_MATRIX[moveType][enemy.types[0]]) / defense) * (pkm.hp / pkm.constants.stats[Stat.MAX_HP])
                    effectiveness += calculate_damage(self.params, 0, move.constants, state, pkm, enemy)

            if effectiveness > bestEffectiveness:
                bestEffectiveness = effectiveness
                bestPkm = i
        return bestPkm

    def chooseBestMove(self, state, pkm):
        possibleMoves = pkm.battling_moves
        currentEnemyTeam = state.sides[1].team.active
        bestMove = 0
        bestEffectiveness = -1000
        bestEnemy = 0
        for i in range(len(possibleMoves)):
            move = possibleMoves[i]
            moveType = move.constants.pkm_type
            status = move.constants.status
            for j in range(len(currentEnemyTeam)):
                enemy = currentEnemyTeam[j]
                effectiveness = calculate_damage(self.params, 0, move.constants, state, pkm, enemy)
                # effectiveness = ((attack * utils.COUNTER_MATRIX[moveType][enemy.types[0]]) / defense)
                if (status != Status.NONE and status != Status.PARALYZED) and enemy.status == Status:
                    return i, j, 1
                if effectiveness > bestEffectiveness and move.constants.base_power > 0 and move.pp >= 1 and not move.disabled:
                    bestMove = i
                    bestEnemy = j
                    bestEffectiveness = effectiveness
        return (bestMove, bestEnemy, bestEffectiveness)

    def decision(
            self, state: State, opp_view: Optional[TeamView] = None
    ) -> list[BattleCommand]:
        team = state.sides[0].team
        cmds: list[BattleCommand] = []
        if len(team.active) == 0:
            return cmds
        for i in range(len(team.active)):
            pkm = team.active[i]
            if pkm.status != Status.NONE or pkm.hp < 40:
                toSwap = self.chooseSwapPokemon(state)
                if toSwap != -1:
                    cmds += [(-1, toSwap)]
                    self.swapped = True
            bestMove, bestEnemy, bestEffectiveness = self.chooseBestMove(state, pkm)
            if bestEffectiveness > 0:
                cmds += [(bestMove, bestEnemy)]
                self.swapped = False
            elif not self.swapped:
                toSwap = self.chooseSwapPokemon(state)
                if toSwap != -1:
                    cmds += [(-1, toSwap)]
                    self.swapped = True
            else:
                cmds += [(bestMove, bestEnemy)]
                self.swapped = False
        return cmds
