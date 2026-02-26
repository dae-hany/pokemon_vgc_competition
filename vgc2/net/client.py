import inspect
from multiprocessing.connection import Client

from vgc2.agent import BattlePolicy, SelectionPolicy, TeamBuildPolicy, MetaBalancePolicy, RuleBalancePolicy
from vgc2.battle_engine import BattleRuleParam
from vgc2.competition import Competitor, DesignCompetitor


def make_proxy_policy_class(base_class):
    class Proxy(base_class):
        def __init__(self, conn: Client):
            self._conn = conn

        # Implement abstract method(s)
        def decision(self, *args, **kwargs):
            self._conn.send({
                "method": f"{base_class.__name__}.decision",
                "args": args,
                "kwargs": kwargs
            })
            return self._conn.recv()

    # Predefine all non-abstract, non-special methods from the base class
    for name, func in inspect.getmembers(base_class, predicate=inspect.isfunction):
        if name not in getattr(base_class, "__abstractmethods__", set()) and not name.startswith("__"):
            def make_remote(n=name):
                def remote_method(self, *args, **kwargs):
                    self._conn.send({
                        "method": f"{base_class.__name__}.{n}",
                        "args": args,
                        "kwargs": kwargs
                    })
                    return self._conn.recv()

                return remote_method

            setattr(Proxy, name, make_remote())

    return Proxy


class ProxyCompetitor(Competitor):

    def __init__(self,
                 conn: Client):
        self.__conn = conn
        self.__battle_policy = make_proxy_policy_class(BattlePolicy)(conn)
        self.__selection_policy = make_proxy_policy_class(SelectionPolicy)(conn)
        self.__team_build_policy = make_proxy_policy_class(TeamBuildPolicy)(conn)

    @property
    def battlepolicy(self) -> BattlePolicy:
        return self.__battle_policy

    @property
    def selectionpolicy(self) -> SelectionPolicy:
        return self.__selection_policy

    @property
    def teambuildpolicy(self) -> TeamBuildPolicy:
        return self.__team_build_policy

    @property
    def name(self) -> str:
        self.__conn.send({
            "method": "Competitor.name",
            "args": (),
            "kwargs": {}
        })
        return self.__conn.recv()

    def set_params(self, params: BattleRuleParam):
        self.__conn.send({
            "method": "Competitor.set_params",
            "args": (params,),
            "kwargs": {}
        })
        return self.__conn.recv()


class ProxyDesignCompetitor(DesignCompetitor):

    def __init__(self,
                 conn: Client):
        self.__conn = conn
        self.__meta_balance = make_proxy_policy_class(MetaBalancePolicy)(conn)
        self.__rule_balance = make_proxy_policy_class(RuleBalancePolicy)(conn)

    @property
    def metabalancepolicy(self) -> MetaBalancePolicy:
        return self.__meta_balance

    @property
    def rulebalancepolicy(self) -> RuleBalancePolicy:
        return self.__rule_balance

    @property
    def name(self) -> str:
        self.__conn.send({
            "method": "DesignCompetitor.name",
            "args": (),
            "kwargs": {}
        })
        return self.__conn.recv()
