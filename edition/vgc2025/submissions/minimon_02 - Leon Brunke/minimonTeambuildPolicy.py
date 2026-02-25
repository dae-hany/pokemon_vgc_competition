from numpy.random import choice, multinomial

from vgc2.agent import TeamBuildPolicy, TeamBuildCommand
from vgc2.battle_engine.modifiers import Type, Nature
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


class TypeAnalyzer:
    def __init__(self):
        self.avg_off = {
            Type.NORMAL: 0.895,
            Type.FIRE: 1.105,
            Type.WATER: 1.0,
            Type.ELECTRIC: 0.895,
            Type.GRASS: 0.974,
            Type.ICE: 0.974,
            Type.FIGHT: 1.237,
            Type.POISON: 0.816,
            Type.GROUND: 1.132,
            Type.FLYING: 1.026,
            Type.PSYCHIC: 1.026,
            Type.BUG: 0.895,
            Type.ROCK: 1.158,
            Type.GHOST: 1.0,
            Type.DRAGON: 1.053,
            Type.DARK: 1.079,
            Type.STEEL: 0.895,
            Type.FAIRY: 1.053,
            Type.TYPELESS: 1.0,
        }

        self.avg_rec = {
            Type.NORMAL: 1.0,
            Type.FIRE: 1.0,
            Type.WATER: 0.974,
            Type.ELECTRIC: 0.895,
            Type.GRASS: 1.0,
            Type.ICE: 1.132,
            Type.FIGHT: 1.132,
            Type.POISON: 0.921,
            Type.GROUND: 1.026,
            Type.FLYING: 1.0,
            Type.PSYCHIC: 1.0,
            Type.BUG: 0.895,
            Type.ROCK: 1.053,
            Type.GHOST: 1.0,
            Type.DRAGON: 1.053,
            Type.DARK: 1.026,
            Type.STEEL: 0.895,
            Type.FAIRY: 1.0,
            Type.TYPELESS: 1.0,
        }

    def offensive_score(self, types: list[Type]) -> float:
        return sum(self.avg_off[t] for t in types) / len(types)

    def defensive_score(self, types: list[Type]) -> float:
        return sum(self.avg_rec[t] for t in types) / len(types)

    def combined_score(self, types: list[Type], weight_off: float = 0.5) -> float:
        off = self.offensive_score(types)
        rec = self.defensive_score(types)
        return weight_off * off + (1 - weight_off) * (1 / rec)


class StrongestTeamBuildPolicy(TeamBuildPolicy):

    def decision(self,
                 roster: Roster,
                 meta: Meta | None,
                 max_team_size: int,
                 max_pkm_moves: int,
                 n_active: int) -> TeamBuildCommand:

        analyzer = TypeAnalyzer()

        MAX_STATS_SUM = max(sum(p.base_stats) for p in roster)
        # print("Max Stats Sum: " + str(MAX_STATS_SUM))

        # Berechne Summe aller Base Stats für jedes pokemon
        stat_sums = [(i, sum(p.base_stats)) for i, p in enumerate(roster)]
        # Sortiere nach höchsten Stats
        best_ids = sorted(range(len(roster)),
                          key=lambda i: self.pokemon_overall_score(roster[i], analyzer, MAX_STATS_SUM),
                          reverse=True)[:max_team_size]

        cmds: TeamBuildCommand = []
        ivs = (31,) * 6  # maximale IVs für alle Stats

        for i in best_ids:
            p = roster[i]

            # print(sum(p.base_stats))
            # print(p.types)
            # Wähle bis zu max_pkm_moves zufällige Moves
            # n_moves = len(p.moves)
            # moves = list(choice(n_moves, min(max_pkm_moves, n_moves), replace=False))

            # moves = self.select_best_moves(p, analyzer, max_pkm_moves)
            # move_ids = [p.moves.index(m) for m in moves]

            n_moves = len(roster[i].moves)
            moves = list(choice(n_moves, min(max_pkm_moves, n_moves), False))

            # move_ids = [m.id for m in moves]
            # moves = list(choice(n_moves, min(max_pkm_moves, n_moves), False))  # nur Indizes!
            # print(f"{p.name}: {[m.pkm_type for m in moves]}")
            # print(move_ids)

            # EVs und Nature bestimmen
            evs, nature = self.choose_evs_and_nature(p.base_stats)

            cmds.append((i, evs, ivs, nature, moves))

        return cmds

    def pokemon_overall_score(self, pkm, analyser: TypeAnalyzer, MAX_STATS_SUM, w_o=0.1, w_d=0.2, w_s=0.7):

        types = pkm.types
        # Offensive Typ-Mittel
        off = analyser.offensive_score(types)
        # Defensive Typ-Mittel
        de = 1 - analyser.defensive_score(types)
        # Stats-Normalisierung
        stats = sum(pkm.base_stats) / MAX_STATS_SUM

        # if(sum(pkm.base_stats) == MAX_STATS_SUM): #Test
        # w_o = 0.5
        # w_s = 0.5
        # print("stats: " + str(pkm.base_stats))
        # print("sum: " + str(sum(pkm.base_stats)))
        # print("Ergebnis: " + str(w_o * off + w_d * de + w_s * stats) + "  Typ: " + str(types))

        return w_o * off + w_d * de + w_s * stats

    def choose_evs_and_nature(self, base_stats: list[int]) -> tuple[tuple[int, int, int, int, int, int], Nature]:
        hp, atk, def_, sp_atk, sp_def, speed = base_stats

        # Rollenlogik
        if atk > 10 + sp_atk and atk + speed > hp + def_ + sp_def:
            # Physischer Sweeper
            return (6, 252, 0, 0, 0, 252), Nature.ADAMANT
        elif sp_atk > 10 + atk and sp_atk + speed > hp + def_ + sp_def:
            # Spezieller Sweeper
            return (6, 0, 0, 252, 0, 252), Nature.MODEST
        elif atk > 10 + sp_atk and hp + def_ > atk + sp_atk + speed:
            # Physischer Tank
            return (252, 0, 252, 0, 6, 0), Nature.IMPISH
        elif hp + def_ > atk + sp_atk + speed:
            # Physischer Tank
            return (252, 0, 252, 0, 6, 0), Nature.BOLD
        elif atk > 10 + sp_atk and hp + sp_def > atk + sp_atk + speed:
            # Spezieller Tank
            return (252, 0, 0, 0, 252, 6), Nature.CAREFUL
        elif hp + sp_def > atk + sp_atk + speed:
            # Spezieller Tank
            return (252, 0, 0, 0, 252, 6), Nature.CALM
        else:
            # Mixed Allrounder
            return (252, 128, 0, 128, 0, 2), Nature.HARDY

    def select_best_moves(self, pkm_specimen, analyser: TypeAnalyzer, max_moves=4, exclude_support=True):
        moves = pkm_specimen.moves
        best_offensive = []
        seen_types = set()

        # Moves nach Base Power sortieren
        damaging_moves = [m for m in moves if m.base_power > 0 and m.category.name in ("PHYSICAL", "SPECIAL")]

        if exclude_support:
            # keine Support-Moves
            damaging_moves = [m for m in damaging_moves if m.category.name != "OTHER"]

        damaging_moves.sort(key=lambda m: (
                    m.base_power * (1.5 if m.pkm_type in pkm_specimen.types else 1.0) * analyser.offensive_score(
                pkm_specimen.types)), reverse=True)
        damages = [(m.base_power, m.pkm_type) for m in damaging_moves]
        # print(damages)
        for move in damaging_moves:
            if move.pkm_type not in seen_types:
                best_offensive.append(move)
                seen_types.add(move.pkm_type)
            if len(best_offensive) == max_moves:
                return best_offensive
        damages = [(m.base_power, m.pkm_type) for m in best_offensive]
        # print(damages)
        return best_offensive
