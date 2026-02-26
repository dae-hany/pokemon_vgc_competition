from vgc2.agent import BattlePolicy
from vgc2.battle_engine import BattleEngine, StateView, Move, Category, Type, Team, BattleRuleParam, TeamView, State
from vgc2.battle_engine.game_state import get_battle_teams
from vgc2.net.stream import StreamClient
from vgc2.util.generator import gen_team, TeamGenerator

SWITCH = Move(Type.TYPELESS, 0, 1., 0, Category.OTHER)
ActionRollout = list[tuple[Move, Move]]


def run_battle_and_count(engine: BattleEngine,
                         agent: tuple[BattlePolicy, BattlePolicy],
                         view: tuple[StateView, StateView],
                         client: StreamClient | None = None) -> tuple[int, ActionRollout]:
    """
    Run a battle and get the action rollout.
    :param engine: a BattleEngine (should only have one active Pokémon on each side).
    :param agent: a pair of BattlePolicy.
    :param view: a pair of StateViews.
    :param client:
    :return: winner side as an integer (0 or 1) and the rollout of action pairs.
    """
    action_rollout: ActionRollout = []
    agent[0].on_new_battle()
    agent[1].on_new_battle()
    while not engine.finished():
        commands = agent[0].decision(view[0]), agent[1].decision(view[1])
        idx0, idx1 = commands[0][0][0], commands[1][0][0]
        action_0 = SWITCH if idx0 == -1 else engine.state.sides[0].team.active[0].battling_moves[idx0].constants
        action_1 = SWITCH if idx1 == -1 else engine.state.sides[1].team.active[0].battling_moves[idx1].constants
        action_rollout.append((action_0, action_1))
        engine.run_turn(commands)
        engine.render(client)
    return engine.winning_side, action_rollout


def get_rollout(agent: tuple[BattlePolicy, BattlePolicy],
                teams: tuple[Team, Team],
                params: BattleRuleParam,
                team_view: tuple[TeamView, TeamView],
                wins: list[int],
                client: StreamClient | None = None) -> ActionRollout:
    """
    Run a game to obtain the action rollout.
    :param agent: Pair of BattlePolicy.
    :param teams: Pair of Pokémon teams.
    :param params: Battle Rules to use.
    :param team_view: view for the pair of teams.
    :param wins: out variable to accumulate the wins of each player.
    :param client:
    :return: the game's action rollout.
    """
    state = State(get_battle_teams(teams, 1))
    state_view = StateView(state, 0, team_view), StateView(state, 1, team_view)
    engine = BattleEngine(state, params)
    winner, action_rollout = run_battle_and_count(engine, agent, state_view, client)
    wins[winner] += 1
    return action_rollout


def get_rollouts(team_pairs: list[tuple[Team, Team]],
                 agent_pair: tuple[BattlePolicy, BattlePolicy],
                 params: BattleRuleParam) -> tuple[list[ActionRollout], list[list[int]]]:
    """
    Compute the fitness over a pair of teams.
    :param team_pairs: array of pair teams to calculate the fitness over.
    :param agent_pair: a pair of BattlePolicy.
    :param params: Battle Rules to use.
    :return: fitness value; the higher the fitness value, the better.
    """
    rollouts = []
    results = []
    agent_pair[0].set_params(params)
    agent_pair[1].set_params(params)
    for team_pair in team_pairs:
        team_view = TeamView(team_pair[0]), TeamView(team_pair[1])
        wins = [0, 0]
        rollouts.append(get_rollout(agent_pair, team_pair, params, team_view, wins))
        results.append(wins)
        wins = [0, 0]
        rollouts.append(get_rollout(agent_pair, (team_pair[1], team_pair[0]), params, team_view, wins))
        results.append(wins)
    return rollouts, results


class FixedMatches:

    def __init__(self,
                 agent_pair: tuple[BattlePolicy, BattlePolicy],
                 n_team_pairs: int = 8,
                 team_gen: TeamGenerator = gen_team):
        self.params = BattleRuleParam()
        self.agent_pair = agent_pair
        self.team_pairs = [(team_gen(), team_gen()) for _ in range(n_team_pairs)]
        self.rollouts = []
        self.results = []

    def set_params(self, params: BattleRuleParam):
        self.params = params

    def run(self):
        self.rollouts, self.results = get_rollouts(self.team_pairs, self.agent_pair, self.params)
