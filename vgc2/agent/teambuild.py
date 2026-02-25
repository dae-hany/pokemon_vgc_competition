from numpy.random import choice, multinomial

from vgc2.agent import TeamBuildPolicy, TeamBuildCommand
from vgc2.battle_engine.modifiers import Nature
from vgc2.balance import Meta, Roster


class RandomTeamBuildPolicy(TeamBuildPolicy):
    """
    random team builder.
    """

    def decision(self,
                 roster: Roster,
                 meta: Meta | None,
                 max_team_size: int,
                 max_pkm_moves: int,
                 n_active: int) -> TeamBuildCommand:
        ivs = (31,) * 6
        ids = choice(len(roster), 3, False)
        cmds: TeamBuildCommand = []
        for i in range(len(ids)):
            n_moves = len(roster[i].moves)
            moves = list(choice(n_moves, min(max_pkm_moves, n_moves), False))
            evs = tuple(multinomial(510, [1 / 6] * 6, size=1)[0])
            nature = Nature(choice(len(Nature), 1, False))
            cmds += [(i, evs, ivs, nature, moves)]
        return cmds


class TerminalTeamBuild(TeamBuildPolicy):
    """
    Terminal interactive team builder with safe input handling.
    """

    def decision(self,
                 roster: Roster,
                 meta: Meta | None,
                 max_team_size: int,
                 max_pkm_moves: int,
                 n_active: int) -> TeamBuildCommand:

        team_cmd: TeamBuildCommand = []

        print("\n=== TERMINAL TEAM BUILDER ===")
        print(f"Max team size: {max_team_size}")
        print(f"Max moves per Pokémon: {max_pkm_moves}\n")

        # Print roster
        for i, sp in enumerate(roster):
            print(f"[{i}] {str(roster[i])}")

        # Build each team slot
        slot = 0
        while slot < max_team_size:
            print(f"\n--- Select Pokémon for slot {slot+1}/{max_team_size} ---")
            raw_idx = input("Species index (or -1 to stop): ").strip()

            if raw_idx == "":
                print("No input, stopping selection.")
                break

            try:
                idx = int(raw_idx)
            except ValueError:
                print("Invalid input, please enter a number.")
                continue

            if idx < 0:
                print("Stopping team selection.")
                break
            if idx >= len(roster):
                print("Index out of range, try again.")
                continue

            species = roster[idx]
            print(f"Selected: {species.id}")

            # Show moves
            print("\nAvailable moves:")
            for i, mv in enumerate(species.moves):
                print(f" [{i}] {str(mv)}")

            move_indexes = []
            while len(move_indexes) < max_pkm_moves:
                m = input(f"Select move index ({len(move_indexes)+1}/{max_pkm_moves}, blank to stop): ").strip()
                if m == "":
                    break
                try:
                    mi = int(m)
                except ValueError:
                    print("Invalid input, enter a number.")
                    continue
                if 0 <= mi < len(species.moves):
                    move_indexes.append(mi)
                else:
                    print("Move index out of range.")

            # EVs
            while True:
                ev_in = input("\nEnter EVs (6 ints) or blank for default 85 each: ").strip()
                if ev_in == "":
                    evs = (85,) * 6
                    break
                try:
                    evs = tuple(map(int, ev_in.split()))
                    if len(evs) != 6:
                        print("Enter exactly 6 integers for EVs.")
                        continue
                    break
                except ValueError:
                    print("Invalid input, enter 6 integers.")

            # IVs
            while True:
                iv_in = input("\nEnter IVs (6 ints) or blank for default 31 each: ").strip()
                if iv_in == "":
                    ivs = (31,) * 6
                    break
                try:
                    ivs = tuple(map(int, iv_in.split()))
                    if len(ivs) != 6:
                        print("Enter exactly 6 integers for IVs.")
                        continue
                    break
                except ValueError:
                    print("Invalid input, enter 6 integers.")

            # Nature
            print("\nNature (SERIOUS default). Available enum values:")
            print([n.name for n in Nature])
            while True:
                nat_in = input("Nature name: ").strip()
                if nat_in == "":
                    nature = Nature.SERIOUS
                    break
                try:
                    nature = Nature[nat_in.upper()]
                    break
                except KeyError:
                    print("Invalid nature name, try again.")

            # Confirm Pokémon
            print("\nConfirm Pokémon:")
            print(" Species:", species.name)
            print(" Moves:", [str(species.moves[i]) for i in move_indexes])
            print(" EVs:", evs)
            print(" IVs:", ivs)
            print(" Nature:", nature.name)

            ok = input("Accept? (y/n): ").strip().lower()
            if ok != "y":
                print("Discarded, redo slot.")
                continue

            team_cmd.append((idx, evs, ivs, nature, move_indexes))
            slot += 1

        print("\n=== FINAL TEAM BUILD COMMAND ===")
        print(team_cmd)
        return team_cmd
