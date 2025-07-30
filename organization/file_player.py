import sys
import os
from vgc2.net.stream import GodotClient, FilePlayer

if len(sys.argv) > 1:
    replay_filename = sys.argv[1]
    if not os.path.isfile(replay_filename):
        print(f"Error: File '{replay_filename}' does not exist.")
    elif not replay_filename.lower().endswith(".battle"):
        print(f"Error: File '{replay_filename}' is not a .battle file.")
    else:
        client = GodotClient("127.0.0.1", 12345)
        player = FilePlayer(replay_filename, client)
        player.play()
else:
    print("No replay file provided. Skipping playback.")
