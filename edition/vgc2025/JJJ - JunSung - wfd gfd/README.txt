There are four files included:

- `JJJ.py`: Implements the battle policy for the JJJ agent. It selects moves that maximize estimated damage using greedy focus-fire tactics.
- `JJJTeamPolicy.py`: Defines the team-building policy, prioritizing Pokémon with high HP and strong offensive synergy.
- `JJJCompetitor.py`: Registers the `JJJ` policies as a complete Competitor implementation compatible with the VGC2 framework.
- `main.py`: Provides remote access interface for competition settings, if required.

This agent was developed based on the strategy of Punisher, the champion of the 2024 competition.