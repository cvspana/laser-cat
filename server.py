from __future__ import annotations
import argparse, json, random, socket, threading, time
from dataclasses import dataclass, asdict
from itertools import count
from typing import Dict, List, Any, Tuple

# =================== NET HELPERS ===================
ENC = "utf-8"

def send_json(sock: socket.socket, obj: Dict[str, Any]) -> None:
    sock.sendall(json.dumps(obj, separators=(",", ":")).encode(ENC) + b"\n")

class JSONLineReceiver:
    def __init__(self) -> None:
        self._buf = bytearray()
    def feed(self, data: bytes) -> None:
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

# =================== WORLD / SPRITES ===================
WORLD_W, WORLD_H = 800, 600
TICK_HZ = 60

# sprite pixel sizes (from your assets)
CAT_W, CAT_H   = 66, 47
COIN_W, COIN_H = 35, 35
LASER_W, LASER_H = 9, 35

# movement speeds (match your feel)
# 7 px/frame @ 60fps ≈ 420 px/sec
CAT_SPEED = 420.0
# lasers: 5..9 px/frame @ 60fps ≈ 300..540 px/sec
LASER_VEL_MIN, LASER_VEL_MAX = 300.0, 540.0

# =================== DATA MODELS ===================
@dataclass
class Player:
    pid: int
    name: str
    x: float = 383.0
    y: float = 553.0
    facing_right: bool = True
    score: int = 0
    up: bool = False; down: bool = False; left: bool = False; right: bool = False
    alive: bool = True

@dataclass
class Coin:
    x: int
    y: int
    @staticmethod
    def spawn() -> "Coin":
        # x in [0 .. WORLD_W-COIN_W), y in [100 .. WORLD_H-COIN_H)
        return Coin(
            x=random.randrange(WORLD_W - COIN_W),
            y=100 + random.randrange(WORLD_H - 100 - COIN_H),
        )

@dataclass
class Laser:
    x: int
    y: float
    vy: float
    @staticmethod
    def spawn() -> "Laser":
        return Laser(
            x=random.randrange(WORLD_W - LASER_W),
            y=-float(random.randrange(100)),
            vy=random.uniform(LASER_VEL_MIN, LASER_VEL_MAX),
        )

# =================== GAME STATE ===================
class GameState:
    def __init__(self) -> None:
        self.players: Dict[int, Player] = {}
        self.coin: Coin | None = None
        self.lasers: List[Laser] = []
        self.internal_clock = 0
        self.round_active = False
        self.target_tick_spawn = 1800  # add a laser every 1800 ticks
        self.music_flag = False
        random.seed()

    def start_round(self) -> None:
        self.internal_clock = 0
        self.round_active = True
        self.coin = Coin.spawn()
        self.lasers.clear()
        for _ in range(7):
            self.lasers.append(Laser.spawn())
        for p in self.players.values():
            p.x, p.y = 383.0, 553.0
            p.alive = True
        self.music_flag = True

    def end_round(self) -> None:
        self.round_active = False
        self.music_flag = False

    def update(self, dt: float) -> None:
        if not self.round_active:
            return
        self.internal_clock += 1

        # players
        for p in self.players.values():
            if not p.alive:
                continue
            dx = (float(p.right) - float(p.left)) * CAT_SPEED * dt
            dy = (float(p.down)  - float(p.up))   * CAT_SPEED * dt
            p.x = max(0.0, min(WORLD_W - CAT_W, p.x + dx))
            p.y = max(0.0, min(WORLD_H - CAT_H, p.y + dy))
            if p.right and not p.left: p.facing_right = True
            elif p.left and not p.right: p.facing_right = False

        # lasers
        for L in self.lasers:
            L.y += L.vy * dt
            if L.y >= WORLD_H:
                L.x = random.randrange(WORLD_W - LASER_W)
                L.y = -float(random.randrange(100))
                L.vy = random.uniform(LASER_VEL_MIN, LASER_VEL_MAX)

        # periodic extra laser
        if self.internal_clock % self.target_tick_spawn == 0:
            self.lasers.append(Laser.spawn())

        # coin pickup
        if self.coin:
            for p in self.players.values():
                if not p.alive:
                    continue
                if rect_overlap(p.x, p.y, CAT_W, CAT_H,
                                self.coin.x, self.coin.y, COIN_W, COIN_H):
                    self.coin = Coin.spawn()
                    p.score += 1

        # laser hits end the round
        any_hit = False
        for p in self.players.values():
            if not p.alive:
                continue
            for L in self.lasers:
                if rect_overlap(p.x, p.y, CAT_W, CAT_H,
                                L.x, L.y, LASER_W, LASER_H):
                    p.alive = False
                    any_hit = True
                    break
        if any_hit:
            self.end_round()

    def apply_command(self, pid: int, msg: Dict[str, Any]) -> None:
        t = msg.get("type")
        if t == "input" and pid in self.players:
            k = msg.get("keys", {})
            p = self.players[pid]
            p.up    = bool(k.get("up",    p.up))
            p.down  = bool(k.get("down",  p.down))
            p.left  = bool(k.get("left",  p.left))
            p.right = bool(k.get("right", p.right))
        elif t == "start":
            if not self.round_active:
                self.start_round()

    def snapshot(self) -> Dict[str, Any]:
        return {
            "type": "state",
            "world": {"w": WORLD_W, "h": WORLD_H},
            "round_active": self.round_active,
            "music": self.music_flag,
            "tick": self.internal_clock,
            "players": {pid: asdict(p) for pid, p in self.players.items()},
            "coin": asdict(self.coin) if self.coin else None,
            "lasers": [asdict(L) for L in self.lasers],
        }

def rect_overlap(ax, ay, aw, ah, bx, by, bw, bh) -> bool:
    ax, ay, bx, by = float(ax), float(ay), float(bx), float(by)
    return (ax < bx + bw) and (ax + aw > bx) and (ay < by + bh) and (ay + ah > by)

# =================== SERVER RUNTIME ===================
state = GameState()
conns: Dict[int, socket.socket] = {}
lock = threading.Lock()
_next_id = count(1)

def broadcast(payload: Dict[str, Any]) -> None:
    dead = []
    for pid, conn in list(conns.items()):
        try:
            send_json(conn, payload)
        except Exception:
            dead.append(pid)
    if dead:
        handle_disconnects(dead)

def handle_disconnects(pids: List[int]) -> None:
    with lock:
        for pid in pids:
            conns.pop(pid, None)
            state.players.pop(pid, None)
    if pids:
        broadcast({"type": "leave", "pids": pids})

def client_handler(conn: socket.socket, addr: Tuple[str, int]) -> None:
    pid: int | None = None
    recv = JSONLineReceiver()
    conn.settimeout(0.5)
    try:
        # wait for join
        while pid is None:
            data = conn.recv(4096)
            if not data:
                raise ConnectionError("no data on join")
            recv.feed(data)
            for msg in recv.get_messages():
                if msg.get("type") == "join":
                    name = str(msg.get("name", "player"))
                    with lock:
                        pid_local = next(_next_id)
                        state.players[pid_local] = Player(pid=pid_local, name=name[:16])
                        conns[pid_local] = conn
                        snap = state.snapshot()
                    pid = pid_local
                    send_json(conn, {"type": "welcome", "pid": pid})
                    send_json(conn, snap)
                    broadcast({"type": "join", "pid": pid, "name": name})
        # process commands
        while True:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                recv.feed(data)
                for msg in recv.get_messages():
                    with lock:
                        if pid in state.players:
                            state.apply_command(pid, msg)
            except socket.timeout:
                continue
    except Exception:
        pass
    finally:
        if pid is not None:
            handle_disconnects([pid])
        try:
            conn.close()
        except Exception:
            pass

def physics_loop():
    last = time.perf_counter()
    tick = 1.0 / TICK_HZ
    while True:
        now = time.perf_counter()
        dt = now - last
        last = now
        with lock:
            state.update(dt)
            snap = state.snapshot()
        broadcast(snap)
        elapsed = time.perf_counter() - now
        if elapsed < tick:
            time.sleep(tick - elapsed)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=50007)
    args = parser.parse_args()

    threading.Thread(target=physics_loop, daemon=True).start()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((args.host, args.port))
        s.listen()
        print(f"Server listening on {args.host}:{args.port}")
        while True:
            conn, addr = s.accept()
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            threading.Thread(target=client_handler, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()
