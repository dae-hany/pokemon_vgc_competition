"""
Entry point for the VGC AI Competition 2026.
Starts the RemoteCompetitorManager server for communication with the competition framework.
"""
import argparse

from competitor import DaehoCompetitor
from vgc2.net.server import RemoteCompetitorManager, BASE_PORT


def main(_args):
    _id = _args.id
    competitor = DaehoCompetitor(name=f"Daeho_AI")
    server = RemoteCompetitorManager(
        competitor,
        port=BASE_PORT + _id,
        authkey=f'Competitor {_id}'.encode('utf-8')
    )
    print(f"[Daeho_AI] Starting server on port {BASE_PORT + _id} (id={_id})")
    server.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Daeho AI - VGC Competition 2026')
    parser.add_argument('--id', type=int, default=0, help='Competitor ID (determines port offset)')
    args = parser.parse_args()
    main(args)
