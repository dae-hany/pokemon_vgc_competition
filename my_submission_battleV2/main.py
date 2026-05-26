import argparse

from competitor import DaehoV2Competitor
from vgc2.net.server import RemoteCompetitorManager, BASE_PORT


def main(_args):
    competitor = DaehoV2Competitor(name="DaehoV2")
    server = RemoteCompetitorManager(
        competitor,
        port=BASE_PORT + _args.id,
        authkey=f'Competitor {_args.id}'.encode('utf-8')
    )
    print(f"[DaehoV2] Starting server on port {BASE_PORT + _args.id} (id={_args.id})")
    server.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='DaehoV2 AI - VGC Competition 2026')
    parser.add_argument('--id', type=int, default=0, help='Competitor ID (determines port offset)')
    args = parser.parse_args()
    main(args)
