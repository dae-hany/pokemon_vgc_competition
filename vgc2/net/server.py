from abc import ABC
from multiprocessing.connection import Listener

from vgc2.competition import Competitor, DesignCompetitor

DEFAULT_ADDRESS = 'localhost'
BASE_PORT = 5000


class RemoteManager(ABC):

    def __init__(self, authkey, address=DEFAULT_ADDRESS, port=BASE_PORT):
        self.authkey = authkey
        self.address = address
        self.port = port
        self.conn = None
        self.competitor = None

    def run(self):
        while True:
            listener = Listener((self.address, self.port), authkey=self.authkey)
            print('Waiting...')
            self.conn = listener.accept()
            print('Connection accepted from', listener.last_accepted)
            while True:
                try:
                    msg = self.conn.recv()
                except EOFError:
                    self.conn.close()
                    break
                self._run_method(msg)
            listener.close()

    def _run_method(self, msg):
        class_name, method_name = msg["method"].split('.')

        if class_name == "Competitor":
            target = self.competitor
        else:
            target = getattr(self.competitor, class_name.lower())

        attr = getattr(target, method_name)

        if callable(attr):
            result = attr(*msg["args"], **msg["kwargs"])
        else:
            # It's a property or simple attribute
            result = attr

        self.conn.send(result)


class RemoteCompetitorManager(RemoteManager):

    def __init__(self, competitor: Competitor, authkey, address=DEFAULT_ADDRESS, port=BASE_PORT):
        super().__init__(authkey, address, port)
        self.competitor = competitor


class RemoteDesignCompetitorManager(RemoteManager):

    def __init__(self, competitor: DesignCompetitor, authkey, address=DEFAULT_ADDRESS, port=BASE_PORT):
        super().__init__(authkey, address, port)
        self.competitor = competitor
