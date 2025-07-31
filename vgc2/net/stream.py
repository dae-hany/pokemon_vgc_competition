import os
import socket
import time
from abc import ABC, abstractmethod


class StreamClient(ABC):
    @abstractmethod
    def send(self, msg: str) -> bool:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def start_stream(self,
                     name: str = "log") -> None:
        """Prepare for a new stream of messages (e.g., new game run)."""
        pass


class GodotClient(StreamClient):
    def __init__(self,
                 host="127.0.0.1",
                 port=12345):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.host = host
        self.port = port

    def send(self,
             msg: str) -> bool:
        try:
            self.sock.sendto(msg.encode("utf-8"), (self.host, self.port))
            return True
        except Exception as e:
            print(f"[Send Error] {e}")
            return False

    def close(self) -> None:
        self.sock.close()

    def start_stream(self,
                     name: str = "log") -> None:
        pass  # No action needed

    def __del__(self):
        self.close()


class FileClient(StreamClient):
    def __init__(self):
        self._file = None
        os.makedirs("record", exist_ok=True)
        self.id = 0

    def start_stream(self,
                     name: str = "log") -> None:
        self.close()  # Close previous stream
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"record/{timestamp}_{self.id}_{name}.battle"
        self._file = open(filename, "w", encoding="utf-8")
        self.id += 1

    def send(self,
             msg: str) -> bool:
        if not self._file:
            print("[FileClient Warning] Stream not started")
            return False
        try:
            self._file.write(msg + "\n")
            self._file.flush()
            return True
        except Exception as e:
            print(f"[File Write Error] {e}")
            return False

    def close(self) -> None:
        if self._file and not self._file.closed:
            self._file.close()
        self._file = None

    def __del__(self):
        self.close()


class FileAndGodotClient(StreamClient):
    def __init__(self):
        self._file = FileClient()
        self._godot = GodotClient()

    def start_stream(self,
                     name: str = "log") -> None:
        self._file.start_stream(name)
        self._godot.start_stream(name)

    def send(self,
             msg: str) -> bool:
        return self._file.send(msg) and self._godot.send(msg)

    def close(self) -> None:
        self._file.close()
        self._godot.close()

    def __del__(self):
        self.close()


class FilePlayer:
    def __init__(self, filename: str, _client: GodotClient):
        self.filename = filename
        self.client = _client

    def play(self) -> None:
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                for line in f:
                    msg = line.strip()
                    if msg:
                        success = self.client.send(msg)
                        if not success:
                            print(f"[Play Warning] Failed to send: {msg}")
        except Exception as e:
            print(f"[FilePlayer Error] {e}")
