import json


class Event:

    def serialize(self) -> str:
        pass


class EventQueue:

    def __init__(self):
        self.events = []

    def push(self,
             event: Event):
        self.events.append(event)

    def insert(self,
               event: Event):
        self.events.insert(0, event)

    def pop(self) -> Event:
        return self.events.pop(0)

    def empty(self):
        self.events = []

    def not_empty(self):
        return len(self.events) > 0


class Battle(Event):

    def __init__(self,
                 teams: tuple):
        self.teams = teams

    def serialize(self) -> str:
        return json.dumps({
            "event": "Battle",
            "teams": [{
                "active": [{
                    "type": int(p.types[0])
                } for p in self.teams[t].active],
                "reserve": [{
                    "type": int(p.types[0])
                } for p in self.teams[t].reserve]
            } for t in (0, 1)]
        })


class Turn(Event):

    def __init__(self,
                 turn: int):
        self.turn = turn

    def serialize(self) -> str:
        return json.dumps({
            "event": "Turn",
            "number": self.turn
        })


class Attack(Event):

    def __init__(self,
                 side: int,
                 attacker: int,
                 move):
        self.side = side
        self.attacker = attacker
        self.move = move

    def serialize(self) -> str:
        return json.dumps({
            "event": "Attack",
            "side": self.side,
            "attacker": self.attacker,
            "category": int(self.move.category)
        })


class Damage(Event):
    def __init__(self,
                 hp_rate: int,
                 side: int,
                 defender: int,
                 ):
        self.hp_rate = hp_rate
        self.side = side
        self.defender = defender

    def serialize(self) -> str:
        return json.dumps({
            "event": "Damage",
            "hp_rate": self.hp_rate,
            "side": self.side,
            "defender": self.defender
        })


class Switch(Event):

    def __init__(self,
                 side: int,
                 switch_in: int,
                 switch_out: int):
        self.side = side
        self.switch_in = switch_in
        self.switch_out = switch_out

    def serialize(self) -> str:
        return json.dumps({
            "event": "Switch",
            "side": self.side,
            "switch_in": self.switch_in,
            "switch_out": self.switch_out
        })


class Faint(Event):

    def __init__(self,
                 side: int,
                 pos: int):
        self.side = side
        self.pos = pos

    def serialize(self) -> str:
        return json.dumps({
            "event": "Faint",
            "side": self.side,
            "pos": self.pos,
        })


class End(Event):

    def __init__(self,
                 side: int):
        self.side = side

    def serialize(self) -> str:
        return json.dumps({
            "event": "End",
            "side": self.side,
        })
