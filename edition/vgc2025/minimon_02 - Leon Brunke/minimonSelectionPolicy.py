from vgc2.agent import SelectionPolicy, SelectionCommand
from vgc2.battle_engine import Team


class BasicSelectionPolicy(SelectionPolicy):
    """
    Policy that selects team members in order.
    """

    def decision(self,
                 teams: tuple[Team, Team],
                 max_size: int) -> SelectionCommand:
        return list(set(range(len(teams[0].members))))[:max_size]


class DiverseTypeSelectionPolicy(SelectionPolicy):
    """
    Selection policy that prefers Pokemon with unique type combinations.
    """

    def decision(self,
                 teams: tuple[Team, Team],
                 max_size: int) -> SelectionCommand:
        team = teams[0].members
        selected = []
        seen_types = set()

        # Auswahl mit verschiedenen Typen
        for idx, pkm in enumerate(team):
            type_combo = tuple(sorted([t.value for t in pkm.species.types]))
            if type_combo not in seen_types:
                selected.append(idx)
                seen_types.add(type_combo)
            if len(selected) == max_size:
                break

        # Wenn nicht genug verschiedene Typen gefunden wurden
        if len(selected) < max_size:
            remaining = [i for i in range(len(team)) if i not in selected]
            selected += remaining[:max_size - len(selected)]

        return selected
