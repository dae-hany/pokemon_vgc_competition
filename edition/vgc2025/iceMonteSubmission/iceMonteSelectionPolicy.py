from itertools import combinations
from typing import Tuple, List

from vgc2.agent import SelectionPolicy, SelectionCommand
from vgc2.battle_engine import BattleRuleParam
from vgc2.battle_engine import Team
from vgc2.battle_engine.modifiers import Stat


class IceMonteSelectionPolicy(SelectionPolicy):

    def evaluate_pair(self, pair, enemies) -> float:
        score = 0

        for p in pair:
            for enemy in enemies:
                score += self.type_advantage(p, enemy)

        for p in pair:
            if p.stats[Stat.SPEED] > max(e.stats[Stat.SPEED] for e in enemies):
                score += 1

        for p in pair:
            if (p.stats[Stat.MAX_HP] + p.stats[Stat.DEFENSE] + p.stats[Stat.SPECIAL_DEFENSE]) > 300:
                score += 1

        for p in pair:
            for move in p.moves:
                if move.protect or move.toggle_tailwind:
                    score += 1

        return score

    def type_advantage(self, attacker, defender) -> float:
        advantage = 0
        for move in attacker.moves:
            if self.is_super_effective(move.pkm_type, defender.species.types):
                advantage += 1
        return min(2, advantage)

    def is_super_effective(self, move_type: str, target_types: List[str]) -> bool:
        params = BattleRuleParam()
        for t in target_types:
            eff = params.DAMAGE_MULTIPLICATION_ARRAY[move_type][t]
            if eff == 2:
                return True

    def decision(self, teams: Tuple[Team, Team], max_size: int) -> SelectionCommand:
        team, opp = teams

        best_score = float('-inf')
        best_pair = []

        for pair in combinations(enumerate(team.members), max_size):
            indices, pokemons = zip(*pair)
            score = self.evaluate_pair(pokemons, opp.members)
            if score > best_score:
                best_score = score
                best_pair = indices
        return SelectionCommand(list(best_pair))
