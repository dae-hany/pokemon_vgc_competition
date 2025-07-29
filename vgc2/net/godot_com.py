import socket


class GodotClient:
    def __init__(self,
                 host="127.0.0.1",
                 port=12345):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.host = host
        self.port = port

    def send_message(self,
                     msg: str) -> bool:
        try:
            self.sock.sendto(msg.encode("utf-8"), (self.host, self.port))
            return True
        except Exception as e:
            print(f"[Send Error] {e}")
            return False
