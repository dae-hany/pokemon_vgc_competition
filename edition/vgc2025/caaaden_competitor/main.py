import argparse

from caaaden_competitor import CaaadenCompetitor
from vgc2.net.server import RemoteCompetitorManager, BASE_PORT


def main(_args):
    _id = _args.id
    _name = f"Caaaden"
    caaaden = CaaadenCompetitor(name=_name)
    port = BASE_PORT + _id
    authkey = f'Competitor {_id}'.encode('utf-8')
    server = RemoteCompetitorManager(
        competitor=caaaden,
        port=port,
        authkey=authkey
    )
    server.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--id',
        type=int,
        default=0
    )
    args = parser.parse_args()
    main(args)
