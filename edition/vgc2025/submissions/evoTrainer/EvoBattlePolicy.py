import inspect
import traceback
from typing import Optional

import numpy as np

from RuleObserver import RuleObserver
from Rules import Rules
from vgc2.agent import BattlePolicy
from vgc2.agent.battle import greedy_double_battle_decision
from vgc2.battle_engine import State, BattleCommand
from vgc2.battle_engine.constants import BattleRuleParam
from vgc2.battle_engine.view import TeamView


class EvoBattlePolicy(BattlePolicy):
    """
    Policy, die alle Regeln durchprobiert und zählt, welche Regel erfolgreich (≠ None) war.
    Fallback ist randomAttack.
    """

    def __init__(self):
        self.genes = np.load('genes.npy', allow_pickle=True)
        self.rules = Rules()
        self.observer = RuleObserver()

    def call_methods_with_genes(self, obj, state, pkm_id, genes):
        # Alle public Methoden im Objekt auflisten (ohne __ und _)
        methods = [getattr(obj, name) for name in dir(obj)
                   if callable(getattr(obj, name)) and not name.startswith("_")]

        i = 0
        while i < len(genes):
            func_idx = genes[i]
            i += 1

            if func_idx < 0 or func_idx >= len(methods):
                print(f"Ungültiger Funktionsindex: {func_idx}")
                continue

            method = methods[func_idx]
            sig = inspect.signature(method)
            threshold_count = len(sig.parameters)

            if threshold_count == 3:
                if i < len(genes):
                    threshold1 = genes[i]
                    i += 2
                    try:
                        result = method(state, pkm_id, threshold1)
                        if result is not None:
                            self.observer.track_success(method.__name__)
                            return result
                    except Exception as e:
                        # +print(f"Fehler beim Aufruf von {method.__name__}: {e}")
                        traceback.print_exc()
            elif threshold_count == 4:
                if i + 1 < len(genes):
                    threshold1 = genes[i]
                    threshold2 = genes[i + 1]
                    i += 2
                    try:
                        result = method(state, pkm_id, threshold1, threshold2)
                        if result is not None:
                            self.observer.track_success(method.__name__)
                            return result
                    except Exception as e:
                        # print(f"Fehler beim Aufruf von {method.__name__}: {e}")
                        traceback.print_exc()
            else:
                print(f"Nicht unterstützte parameteranzahl ({threshold_count}) für Methode {method.__name__}")

        return greedy_double_battle_decision(BattleRuleParam(), state)[pkm_id]

    def decision(self, state: State, opp_view: Optional[TeamView] = None) -> list[BattleCommand]:
        cmdPkm1 = self.call_methods_with_genes(self.rules, state, 0, self.genes)
        if len(state.sides[0].team.active) > 1:
            cmdPkm2 = self.call_methods_with_genes(self.rules, state, 1, self.genes)
            return [cmdPkm1, cmdPkm2]
        return [cmdPkm1]

    def show_rule_usage(self, name):
        self.observer.plot(name)
