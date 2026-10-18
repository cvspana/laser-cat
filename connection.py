# connection.py — client side of the JSON-lines protocol spoken by server.py
from __future__ import annotations
import json, socket, threading
import pygame

ENC = "utf-8"

class JSONLineReceiver:
    def __init__(self) -> None:
        self._buf = bytearray()
    def feed(self, data: bytes):
        self._buf.extend(data)
    def get_messages(self):
        while True:
            try:
                i = self._buf.index(0x0A)
            except ValueError:
                return
            line = self._buf[:i]; del self._buf[:i+1]
            if not line:
                continue
            try:
                yield json.loads(line.decode(ENC))
            except json.JSONDecodeError:
                pass

class Connection:
    """A connection to a game server.

    Messages are read on a background thread; the game reads the latest
    snapshot from .state each frame. Raises OSError if the server can't be
    reached within `timeout` seconds.
    """
    def __init__(self, host: str, port: int, name: str, timeout: float = 4.0) -> None:
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(None)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.state: dict = {
            "world": None,
            "round_active": False,
            "music": False,
            "tick": 0,
            "players": {},
            "coin": None,
            "lasers": [],
        }
        self.pid: int | None = None
        self.closed = False
        self.send({"type": "join", "name": name})
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self) -> None:
        recv = JSONLineReceiver()
        try:
            while True:
                data = self.sock.recv(4096)
                if not data:
                    break
                recv.feed(data)
                for msg in recv.get_messages():
                    t = msg.get("type")
                    if t == "welcome":
                        self.pid = msg.get("pid")
                    elif t == "state":
                        # Swap in a new dict so the render loop never sees a half-updated one
                        self.state = {**self.state, **msg}
        except OSError:
            pass
        finally:
            self.closed = True

    def send(self, obj: dict) -> None:
        try:
            self.sock.sendall(json.dumps(obj, separators=(",", ":")).encode(ENC) + b"\n")
        except OSError:
            self.closed = True

    def send_inputs(self) -> None:
        keys = pygame.key.get_pressed()
        self.send({
            "type": "input",
            "keys": {
                "up": bool(keys[pygame.K_UP] or keys[pygame.K_w]),
                "down": bool(keys[pygame.K_DOWN] or keys[pygame.K_s]),
                "left": bool(keys[pygame.K_LEFT] or keys[pygame.K_a]),
                "right": bool(keys[pygame.K_RIGHT] or keys[pygame.K_d]),
            }
        })

    def start_round(self) -> None:
        self.send({"type": "start"})

    def close(self) -> None:
        self.closed = True
        try:
            self.sock.shutdown(socket.SHUT_RDWR)  # wakes the reader thread
        except OSError:
            pass
        self.sock.close()

def parse_address(text: str, default_port: int) -> tuple[str, int]:
    """'192.168.1.5' or '192.168.1.5:50007' -> (host, port). Raises ValueError."""
    text = text.strip()
    host, sep, port = text.rpartition(":")
    if not sep:
        host, port = text, str(default_port)
    if not host or not port.isdigit() or not 0 < int(port) < 65536:
        raise ValueError(text)
    return host, int(port)

def lan_ip() -> str:
    """This computer's address on the local network, for friends to join."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # UDP connect sends nothing; it just picks the outgoing interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()
