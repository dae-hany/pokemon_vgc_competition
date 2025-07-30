from vgc2.agent.battle import greedy_double_battle_decision
from vgc2.battle_engine import BattleCommand, calculate_damage
from vgc2.battle_engine.constants import BattleRuleParam
from vgc2.battle_engine.damage_calculator import terrain_modifier
from vgc2.battle_engine.damage_calculator import weather_modifier
from vgc2.battle_engine.modifiers import Stat, Type, Weather
from vgc2.battle_engine.pokemon import calculate_stats
from vgc2.battle_engine.priority_calculator import priority_calculator


class HelperFunctions:
    def __init__(self):
        pass

    def checkForValue(cmds):
        if cmds is not None and cmds[0] is not None and cmds[1] is not None:
            return cmds
        return None

    def relativeHP(pkm):
        return pkm.hp / pkm.constants.stats[Stat.MAX_HP]

    def relativeTypeStrength(moves, pkmEnemies):
        type_stength = 0

        for enemy in pkmEnemies:
            for type in enemy.types:
                for move in moves:
                    if HelperFunctions.compareTypes(move.constants.pkm_type, type) > type_stength:
                        type_stength = HelperFunctions.compareTypes(move.constants.pkm_type, type)

        return type_stength / 2

    def relativePower(moves):
        power = 0

        for move in moves:
            if power < move.constants.base_power:
                power = move.constants.base_power / 140

        return round(power, 4)

    def findWeakestEnemy(pkmTeam):  # Searches for the enemy with the lowest hp
        hp = pkmTeam.active[0].hp
        target = 0

        n_pkm = len(pkmTeam.active)

        for enemy in range(n_pkm):

            if pkmTeam.active[enemy].hp < hp:
                hp = pkmTeam.active[enemy].hp
                target = enemy

        return target

    def findStrongestPhysicalPkm(pkmTeam):
        physicalAttack = 0
        n_pkm = len(pkmTeam.active)

        for pkm in range(n_pkm):
            if pkmTeam.active[pkm].stats[1] > physicalAttack:
                physicalAttack = pkmTeam.active[pkm].stats[1]
                strongest = pkm

        return strongest

    def findWeakestPhysicalPkm(pkmTeam):  # Searches for the enemy with the lowest physical defense
        physicalDefense = pkmTeam.active[0].constants.stats[2]
        weakest = 0

        n_pkm = len(pkmTeam.active)

        for pkm in range(n_pkm):
            if pkmTeam.active[pkm].constants.stats[2] < physicalDefense:
                physicalDefense = pkmTeam.active[pkm].constants.stats[2]
                weakest = pkm

        return weakest

    def findWeakestSpecialPkm(pkmTeam):  # Searches for the enemy with the lowest special defense
        specialDefense = pkmTeam.active[0].constants.stats[4]
        weakest = 0

        n_pkm = len(pkmTeam.active)

        for pkm in range(n_pkm):
            if pkmTeam.active[pkm].constants.stats[4] < specialDefense:
                specialDefense = pkmTeam.active[pkm].constants.stats[4]
                weakest = pkm

        return weakest

    def findTypeWeaknesses(pkm, pkmEnemies):
        n_types = len(pkm.types)
        n_attacker = len(pkmEnemies.active)

        weaknesses = None
        moves = None

        for enemy in range(n_attacker):
            moves = 0
            weaknesses = 0

            enemyMoves = pkmEnemies.active[enemy].battling_moves
            n_moves = len(enemyMoves)

            moves += n_moves

            for move in range(n_moves):

                for type in range(n_types):
                    weaknesses += HelperFunctions.compareTypes(enemyMoves[move].constants.pkm_type, pkm.types[type])
        if moves == 0:
            return 0
        return weaknesses / (moves * 2)

    def findPowerStrength(pkm):
        power = 0
        n_moves = len(pkm.battling_moves)

        for move in range(n_moves):
            power += pkm.battling_moves[move].constants.base_power

        return round(power / (140 * n_moves), 4)

    def findLowPP(pkm):
        pp = 0
        n_moves = len(pkm.battling_moves)

        for move in range(n_moves):
            pp += pkm.battling_moves[move].constants.max_pp

        return round(pp / (20 * n_moves), 4)

    def compareTypes(moveType, pkmType):
        battle_rule = BattleRuleParam()
        typeMultiplier = battle_rule.DAMAGE_MULTIPLICATION_ARRAY[moveType][pkmType]
        return typeMultiplier

    def compareWeatherMove(move, weather):
        battle_rule = BattleRuleParam()
        weatherMultiplier = weather_modifier(battle_rule, move, weather)
        if weatherMultiplier > 1:
            return True
        return False

    def compareWeatherType(pkm, state):
        for pkmType in pkm.types:
            if (pkmType == Type.ROCK and state.weather == Weather.SAND) or (
                    pkmType == Type.ICE and state.weather == Weather.SNOW):
                return 1
        return 0

    def strongestTypeAttack(pkm,
                            pkmEnemies):  # Searches for the attack that is the most effective against a specific weak type of an enemy pokemon
        n_targets = len(pkmEnemies.active)
        n_moves = len(pkm.battling_moves)

        typeMultiplier = [0] * n_targets
        bestAction = [0] * n_targets

        cmds: BattleCommand = ()

        for enemy in range(n_targets):
            n_types = len(pkmEnemies.active[enemy].types)

            for move in range(n_moves):

                for type in range(n_types):

                    curTypeMultiplier = HelperFunctions.compareTypes(pkm.battling_moves[move].constants.pkm_type,
                                                                     pkmEnemies.active[enemy].types[type])

                    if curTypeMultiplier > typeMultiplier[enemy]:
                        bestAction[enemy] = move
                        typeMultiplier[enemy] = curTypeMultiplier

        for multiplier in range(len(typeMultiplier)):
            if multiplier > 0:
                if typeMultiplier[multiplier] > typeMultiplier[multiplier - 1]:
                    target = multiplier
                    action = bestAction[multiplier]
            else:
                target = 0
                action = 0

        cmds += (action, target)

        return cmds

    def strongestPowerAttack(pkm):  # Searches for the attack with the highest power stat
        power = 0
        action = None
        n_moves = len(pkm.battling_moves)

        for move in range(n_moves):

            if pkm.battling_moves[move].constants.base_power > power:
                action = move
                power = pkm.battling_moves[move].constants.base_power

        return action

    def strongestPhysicalAttack(pkm, pkmEnemies):  # Searches for the strongest physical attack
        power = 0
        action = None

        cmds: BattleCommand = ()

        n_moves = len(pkm.battling_moves)

        for move in range(n_moves):
            if pkm.battling_moves[move].constants.base_power > power and pkm.battling_moves[
                move].constants.category == 1:
                action = move
                power = pkm.battling_moves[move].constants.base_power

        target = HelperFunctions.findWeakestPhysicalPkm(pkmEnemies)

        cmds += (action, target)
        return cmds

    def strongestSpecialAttack(pkm, pkmEnemies):  # Searches for the strongest special attack
        power = 0
        action = None

        cmds: BattleCommand = ()

        n_moves = len(pkm.battling_moves)

        for move in range(n_moves):
            if pkm.battling_moves[move].constants.base_power > power and pkm.battling_moves[
                move].constants.category == 2:
                action = move
                power = pkm.battling_moves[move].constants.base_power

        target = HelperFunctions.findWeakestSpecialPkm(pkmEnemies)
        cmds += (action, target)

        return cmds

    def strongestWeatherAttack(pkm, state):
        power = 0
        action = None
        n_moves = len(pkm.constants.moves)

        for move in range(n_moves):
            if HelperFunctions.compareWeatherMove(pkm.constants.moves[move], state.weather) and pkm.constants.moves[
                move].base_power > power:
                action = move
                power = pkm.constants.moves[move].base_power

        return action

    def healAttack(pkm):
        action = None
        n_moves = len(pkm.constants.moves)

        for move in range(n_moves):
            if pkm.constants.moves[move].heal > 0:
                action = move

        return action

    def findHighestStat(statid, pkmTeam):
        stat = 0
        n_pkm = len(pkmTeam)

        for pkm in range(n_pkm):
            if pkmTeam[pkm].constants.stats[statid] > stat:
                stat = pkmTeam[pkm].constants.stats[statid]
                highest = pkm

        return highest

    def calculateMaxStat(statid):
        stats = (160, 120, 120, 120, 120, 120)
        maxStats = calculate_stats(stats, 100, (31, 31, 31, 31, 31, 31), (255, 255, 255, 255, 255, 255), 0)
        return maxStats[statid] * 1.1

    def relativeStat(statid, pkm):
        stat = pkm.constants.stats[statid]
        maxStat = HelperFunctions.calculateMaxStat(statid)
        return stat / maxStat

    def noNegativeEffect(team):
        n_pkm = len(team)
        for pkm in range(n_pkm):
            if team[pkm].status == 0:
                return pkm
        return None

    def getTerrainAdvantage(pkm, terrain):
        advantage = 0
        battle_rule = BattleRuleParam()

        for move in pkm.constants.moves:
            advantage += terrain_modifier(battle_rule, move, terrain) / battle_rule.TERRAIN_DAMAGE_BOOST

        return advantage / len(pkm.constants.moves)

    def highestTerrainAdvantage(team, terrain):
        n_pkm = len(team)
        highest = 0
        advantage = 0

        for pkm in range(n_pkm):
            curAdvantage = HelperFunctions.getTerrainAdvantage(team[pkm], terrain)
            if curAdvantage > advantage:
                advantage = curAdvantage
                highest = pkm

        return highest

    def getPrioAdvantage(pkm, state):
        advantage = 1 if state.trickroom else 0
        battle_rule = BattleRuleParam()

        for move in pkm.constants.moves:
            advantage += priority_calculator(battle_rule, move, pkm, state) / 2500  # 2500 is the maximum priority value

        return advantage / len(pkm.constants.moves)

    def highestPrioAdvantage(team, state):
        n_pkm = len(team)
        highest = 0
        advantage = 0

        for pkm in range(n_pkm):
            curAdvantage = HelperFunctions.getPrioAdvantage(team[pkm], state)
            if curAdvantage > advantage:
                advantage = curAdvantage
                highest = pkm

        return highest

    def getGreedyAttack(state):
        move = greedy_double_battle_decision(BattleRuleParam(), state)

        return move

    def getRelativeDamage(pkm, target, move, state, attacking_side):
        damage = calculate_damage(BattleRuleParam(), attacking_side, pkm.constants.moves[move], state, pkm, target)
        relative_damage = damage / 3000
        return relative_damage

    def getGreedyDamageAgainstPokemon(state, pkm_id):
        enemy_moves_with_damage = []
        enemy_moves_against_pkm = []

        for i in range(len(state.sides[0].team.active)):
            try:
                enemy_moves = HelperFunctions.getGreedyAttack(state)
                for move in enemy_moves:
                    damage = HelperFunctions.getRelativeDamage(state.sides[1].team.active[i],
                                                               state.sides[0].team.active[move[1]], move[0], state, 1)
                    enemy_moves_with_damage.append([move[0]] + [move[1]] + [damage])
            except Exception as e:
                continue

        for move in enemy_moves_with_damage:
            if move[0] == pkm_id:
                enemy_moves_against_pkm.append(move)
        return enemy_moves_against_pkm
