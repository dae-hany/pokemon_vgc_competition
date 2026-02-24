import pytest
import numpy as np
from vgc2.util.generator import gen_move_set, gen_pkm_roster, gen_team_from_roster
from vgc2.meta import BasicMeta


@pytest.fixture
def vgc_env():
    """Sets up real framework objects using vgc2 generator functions."""
    # IEEE CoG standard often uses 100 moves and 100 species for small rosters
    move_set = gen_move_set(100)
    roster = gen_pkm_roster(100, move_set)
    rng = np.random.default_rng(42)  # Seeded for reproducibility

    # n=3 or n=4 is standard for VGC AI depending on the specific track
    # n_moves=4 is the standard Pokemon move count
    team0 = gen_team_from_roster(roster, n=3, n_moves=4, rng=rng)
    team1 = gen_team_from_roster(roster, n=3, n_moves=4, rng=rng)

    return roster, move_set, team0, team1


def test_usage_calculation_accuracy(vgc_env):
    roster, move_set, team0, team1 = vgc_env
    meta = BasicMeta(move_set, roster, limit=2)

    # Record Match: Team 0 vs Team 1
    meta.add_match((team0, team1), winner=0, elo=(1200, 1180))

    # 1. Test Pokemon Usage by ID
    test_p_species = team0.members[0].species
    # Count how many teams in this match contained this species ID
    # (Matches * 2 teams per match = 2 total team slots)
    count = 0
    for team in (team0, team1):
        if any(p.species.id == test_p_species.id for p in team.members):
            count += 1

    expected_p_usage = count / 2.0
    assert meta.usage_rate_pokemon(test_p_species) == expected_p_usage

    # 2. Test Move Usage by ID
    test_move = team0.members[0].moves[0]
    move_count = 0
    for team in (team0, team1):
        # We check if any pokemon in the team has a move with matching ID
        move_in_team = False
        for p in team.members:
            if any(m.id == test_move.id for m in p.moves):
                move_in_team = True
                break
        if move_in_team:
            move_count += 1

    expected_m_usage = move_count / 2.0
    assert meta.usage_rate_move(test_move) == expected_m_usage


def test_sliding_window_eviction(vgc_env):
    roster, move_set, team0, team1 = vgc_env
    # Limit of 1: The second match must completely overwrite the first
    meta = BasicMeta(move_set, roster, limit=1)

    # Match 1: Two Team 0s (Uses only Team 0 species)
    meta.add_match((team0, team0), 0, (1000, 1000))

    # Match 2: Two Team 1s (Evicts Match 1)
    meta.add_match((team1, team1), 0, (1000, 1000))

    # Identify species IDs present in Team 1 to avoid false positives
    t1_species_ids = {p.species.id for p in team1.members}

    for p in team0.members:
        # If this species from the old match isn't in the new match...
        if p.species.id not in t1_species_ids:
            # ...its usage must be 0.0 because Match 1 was popped.
            assert meta.usage_rate_pokemon(p.species) == 0.0


def test_team_usage_rate(vgc_env):
    roster, move_set, team0, team1 = vgc_env
    meta = BasicMeta(move_set, roster, limit=1)
    meta.add_match((team0, team1), 0, (1000, 1000))

    # usage_rate_team averages the pokemon usage rates
    # If all pokemon in team0 are unique to team0, their individual rates are 0.5
    # The team average should therefore be 0.5
    t0_unique = True
    t1_ids = [p.species.id for p in team1.members]
    for p in team0.members:
        if p.species.id in t1_ids:
            t0_unique = False

    if t0_unique:
        assert meta.usage_rate_team(team0) == 0.5


def test_meta_usage_exhaustive(vgc_env):
    roster, move_set, _, _ = vgc_env
    # Limit is higher than match count so no eviction happens yet
    meta = BasicMeta(move_set, roster, limit=100)
    rng = np.random.default_rng(123)

    # Ground Truth Trackers
    expected_pokemon_counts = {s.id: 0 for s in roster}
    expected_move_counts = {m.id: 0 for m in move_set}
    num_matches = 10

    for _ in range(num_matches):
        # Generate two random teams (4 pkmn each, 4 moves each)
        t0 = gen_team_from_roster(roster, n=4, n_moves=4, rng=rng)
        t1 = gen_team_from_roster(roster, n=4, n_moves=4, rng=rng)

        meta.add_match((t0, t1), winner=0, elo=(1000, 1000))

        # Manually update Ground Truth for these two teams
        for team in [t0, t1]:
            # Count unique species IDs in team
            unique_species = {p.species.id for p in team.members}
            for sid in unique_species:
                expected_pokemon_counts[sid] += 1

            # Count unique move IDs in team
            unique_moves = set()
            for p in team.members:
                for m in p.moves:
                    unique_moves.add(m.id)
            for mid in unique_moves:
                expected_move_counts[mid] += 1

    # Validation
    total_team_appearances = num_matches * 2

    # Verify every species
    for s in roster:
        expected_rate = expected_pokemon_counts[s.id] / total_team_appearances
        assert meta.usage_rate_pokemon(s) == pytest.approx(expected_rate)

    # Verify every move
    for m in move_set:
        expected_rate = expected_move_counts[m.id] / total_team_appearances
        assert meta.usage_rate_move(m) == pytest.approx(expected_rate)
