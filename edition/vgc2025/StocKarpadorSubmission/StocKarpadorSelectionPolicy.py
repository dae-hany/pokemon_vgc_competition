import logging

from vgc2.agent import SelectionPolicy, SelectionCommand
from vgc2.battle_engine import Team, BattlingPokemon, BattleRuleParam, State, BattlingTeam, calculate_damage

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


class HeuristicSelectionPolicy(SelectionPolicy):

    def calc_max_dmg(self, atk_pkm, def_pkm):
        attacker = BattlingPokemon(atk_pkm)
        defender = BattlingPokemon(def_pkm)
        params = BattleRuleParam()
        state = State((BattlingTeam([attacker], []), BattlingTeam([defender], [])))
        logger.info(attacker.battling_moves)
        outcomes = [calculate_damage(params, 0, move.constants, state, attacker, defender) for move in
                    attacker.battling_moves]
        return max(outcomes) if outcomes else -1

    def decision(self,
                 teams: tuple[Team, Team],
                 max_size: int) -> SelectionCommand:
        pokemon_scores = []
        my_team, opp_team = teams

        for i, my_pokemon in enumerate(my_team.members):
            offensive_score = sum(self.calc_max_dmg(my_pokemon, opp_pokemon) for opp_pokemon in opp_team.members)
            defensive_score = sum(self.calc_max_dmg(opp_pokemon, my_pokemon) for opp_pokemon in opp_team.members)
            effectiveness_score = offensive_score - defensive_score

            pokemon_scores.append({'pokemon': i, 'score': effectiveness_score})

        sorted_pokemon = sorted(pokemon_scores, key=lambda x: x['score'], reverse=True)

        best_four_pokemon = [item['pokemon'] for item in sorted_pokemon[:4]]

        return best_four_pokemon
