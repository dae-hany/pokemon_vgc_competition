from collections import Counter
from random import shuffle

from vgc2.agent import SelectionPolicy, SelectionCommand
from vgc2.battle_engine import Team


class RandomSelectionPolicy(SelectionPolicy):
    """
    Policy that selects team members in a random order.
    """

    def decision(self,
                 teams: tuple[Team, Team],
                 max_size: int) -> SelectionCommand:
        ids = list(set(range(len(teams[0].members))))[:max_size]
        shuffle(ids)
        return ids


class BalancedStatSelectionPolicy(SelectionPolicy):
    """
    Selects Pokémon with high base stats, good move coverage, and diverse typing.
    """

    def decision(self, teams: tuple[Team, Team], max_size: int) -> SelectionCommand:
        team = teams[0]
        type_counter = Counter()
        scored_members = []

        for i, pkm in enumerate(team.members):
            # use only base stats to evaluate total power
            base_stats = getattr(pkm.species, 'base_stats', [0] * 6)
            total_stats = sum(base_stats)

            # pkmn with more available moves
            move_score = len(getattr(pkm, 'moves', []))

            # penalize redundant typing
            types = tuple(sorted(getattr(pkm, 'types', ('Unknown',))))
            type_penalty = sum(type_counter[t] for t in types)

            score = total_stats + move_score * 10 - type_penalty * 15
            scored_members.append((score, i, types))

        # sort by descending score
        sorted_members = sorted(scored_members, reverse=True)

        # prefer diverse typing
        chosen_ids = []
        used_types = set()
        for _, i, types in sorted_members:
            if len(chosen_ids) >= max_size:
                break
            if all(t not in used_types for t in types):
                used_types.update(types)
            chosen_ids.append(i)

        return chosen_ids
