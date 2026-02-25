from vgc2.agent import BattlePolicy
from vgc2.battle_engine import BattleEngine, StateView, Move, Category, Type, Team, BattleRuleParam, TeamView, State
from vgc2.battle_engine.game_state import get_battle_teams
from vgc2.battle_engine.pokemon import BattlingPokemon
from vgc2.net.stream import StreamClient

SWITCH = Move(Type.TYPELESS, 0, 1., 0, Category.OTHER)
ActionRollout = list[tuple[Move, Move]]
StateRollout = list[tuple[BattlingPokemon, BattlingPokemon]]


def run_battle(engine: BattleEngine,
               agent: tuple[BattlePolicy, BattlePolicy],
               team_view: tuple[TeamView, TeamView],
               view: tuple[StateView, StateView],
               client: StreamClient | None = None) -> int:
    agent[0].on_new_battle()
    agent[1].on_new_battle()
    while not engine.finished():
        engine.run_turn((agent[0].decision(view[0], team_view[1]), agent[1].decision(view[1], team_view[0])))
        engine.render(client)
    return engine.winning_side


def run_battle_and_count(engine: BattleEngine,
                         agent: tuple[BattlePolicy, BattlePolicy],
                         view: tuple[StateView, StateView],
                         client: StreamClient | None = None) -> tuple[int, ActionRollout, StateRollout]:
    """
    Run a battle and get the action rollout.
    :param engine: a BattleEngine (should only have one active Pokémon on each side).
    :param agent: a pair of BattlePolicy.
    :param view: a pair of StateViews.
    :return: winner side as an integer (0 or 1) and the rollout of action pairs.
    """
    action_rollout: ActionRollout = []
    state_rollout: StateRollout = []
    agent[0].on_new_battle()
    agent[1].on_new_battle()
    while not engine.finished():
        commands = agent[0].decision(view[0]), agent[1].decision(view[1])
        idx0, idx1 = commands[0][0][0], commands[1][0][0]
        action_0 = SWITCH if idx0 == -1 else engine.state.sides[0].team.active[0].battling_moves[idx0].constants
        action_1 = SWITCH if idx1 == -1 else engine.state.sides[1].team.active[0].battling_moves[idx1].constants
        action_rollout.append((action_0, action_1))
        active = (engine.state.sides[0].team.active, engine.state.sides[1].team.active)
        state_rollout.append((active[0][0] if len(active[0]) > 0 else None,
                              active[1][0] if len(active[1]) > 0 else None))
        engine.run_turn(commands)
        engine.render(client)
    return engine.winning_side, action_rollout, state_rollout


def get_rollout(agent: tuple[BattlePolicy, BattlePolicy],
                teams: tuple[Team, Team],
                params: BattleRuleParam,
                team_view: tuple[TeamView, TeamView],
                wins: list[int],
                client: StreamClient | None = None) -> tuple[ActionRollout, StateRollout]:
    """
    Run a game to obtain the action rollout.
    :param agent: Pair of BattlePolicy.
    :param teams: Pair of Pokémon teams.
    :param params: Battle Rules to use.
    :param team_view: view for the pair of teams.
    :param wins: out variable to accumulate the wins of each player.
    :return: the game's action rollout.
    """
    state = State(get_battle_teams(teams, 1))
    state_view = StateView(state, 0, team_view), StateView(state, 1, team_view)
    engine = BattleEngine(state, params)
    winner, action_rollout, state_rollout = run_battle_and_count(engine, agent, state_view, client)
    wins[winner] += 1
    return action_rollout, state_rollout


def calculate_fitness(team_pairs: list[tuple[Team, Team]],
                      #fitness: Fitness,
                      params: BattleRuleParam,
                      team_size: int,
                      n_moves: int,
                      depth: int,
                      target_percentage: float,
                      bonus_value: float,
                      penalty_value: float,
                      target_battle_length: int,
                      length_weight: float) -> float:
    """
    Compute the fitness over a pair of teams.
    :param length_weight:
    :param target_battle_length:
    :param penalty_value:
    :param bonus_value:
    :param target_percentage:
    :param team_pairs: array of pair teams to calculate the fitness over.
    :param fitness: fitness function over a single game run.
    :param params: Battle Rules to use.
    :param team_size: number of Pokémon on each team.
    :param n_moves: numer of moves on each Pokémon.
    :param depth: search depth for a Tree Search agent.
    :return: fitness value; the higher the fitness value, the better.
    """
    fit = 0.
    for teams in team_pairs:
        team_view = TeamView(teams[0]), TeamView(teams[1])
        wins = [0, 0]
        action_rollout, state_rollout = get_rollout(
            (TunedTreeSearchBattlePolicy(team_view[1], team_size, n_moves, depth, params), GreedyBattlePolicy(params)),
            teams, params, team_view, wins)
        fit += fitness(action_rollout, state_rollout, teams, (wins[0], wins[1]), target_percentage, bonus_value,
                       penalty_value, target_battle_length, length_weight)
        wins = [0, 0]
        action_rollout, state_rollout = get_rollout(
            (TunedTreeSearchBattlePolicy(team_view[0], team_size, n_moves, depth, params), GreedyBattlePolicy(params)),
            (teams[1], teams[0]), params, team_view, wins)
        fit += fitness(action_rollout, state_rollout, teams, (wins[0], wins[1]), target_percentage, bonus_value,
                       penalty_value, target_battle_length, length_weight)
    return fit / (2.0 * len(team_pairs))


def gen_targets(_gen_move=boost_gen_move) -> list[tuple[Team, Team]]:
    n_pairs = 8
    team_members = 3
    n_pokemons = 2 * n_pairs * team_members
    moves = gen_move_set(n_pokemons * 16, _gen_move=_gen_move)
    damage = [m for m in moves if m.category != Category.OTHER]
    other = [m for m in moves if m.category == Category.OTHER]
    pokemons = [gen_pkm(gen_pkm_species(other[2 * i:2 * i + 2] + damage[2 * i:2 * i + 2])) for i in range(n_pokemons)]
    normalize(pokemons)
    i = 0
    teams = []
    while i < n_pokemons:
        i += team_members
        teams += [Team(pokemons[i - team_members:i])]
    t = 0
    team_pairs = []
    while t < len(teams) / 2:
        t += 2
        team_pair = (teams[t - 1], teams[t])
        label_teams(team_pair)
        team_pairs += [team_pair]
    return team_pairs


class FixedMatches:

    def __init__(self):
        pass

    def run(self):
        pass
