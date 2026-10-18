# client.py — Pygame renderer + input sender for the authoritative server
# Python 3.10 / Pygame 2.x

from __future__ import annotations
import argparse, json, socket, threading, time, os, sys
import pygame

ENC = "utf-8"
# Default world size (the server sends the real one in every state message).
# Game logic always happens in these world units; the View below converts them
# to screen pixels so the game renders at the display's real resolution.
WIDTH, HEIGHT = 800, 600
FPS = 144

# ---------- Networking helpers ----------
def _send_json(sock: socket.socket, obj: dict) -> None:
    try:
        sock.sendall(json.dumps(obj, separators=(",", ":")).encode(ENC) + b"\n")
    except OSError:
        pass  # connection closed

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

# ---------- Client state ----------
latest_state = {
    "type": "state",
    "world": {"w": WIDTH, "h": HEIGHT},
    "round_active": False,
    "music": False,
    "tick": 0,
    "players": {},
    "coin": None,
    "lasers": [],
}
my_pid: int | None = None

# ---------- Networking thread ----------
def net_reader(sock: socket.socket):
    global latest_state, my_pid
    recv = JSONLineReceiver()
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                break
            recv.feed(data)
            for msg in recv.get_messages():
                t = msg.get("type")
                if t == "welcome":
                    my_pid = msg.get("pid")
                elif t == "state":
                    # Shallow update is fine; keys are top-level
                    latest_state.update(msg)
    except OSError:
        pass
    finally:
        # Tell the Pygame loop to quit
        pygame.event.post(pygame.event.Event(pygame.QUIT))

def connect(host: str, port: int, name: str) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.connect((host, port))
    _send_json(sock, {"type": "join", "name": name})
    threading.Thread(target=net_reader, args=(sock,), daemon=True).start()
    return sock

def send_inputs(sock: socket.socket):
    keys = pygame.key.get_pressed()
    payload = {
        "type": "input",
        "keys": {
            "up": bool(keys[pygame.K_UP] or keys[pygame.K_w]),
            "down": bool(keys[pygame.K_DOWN] or keys[pygame.K_s]),
            "left": bool(keys[pygame.K_LEFT] or keys[pygame.K_a]),
            "right": bool(keys[pygame.K_RIGHT] or keys[pygame.K_d]),
        }
    }
    _send_json(sock, payload)

# ---------- Resolution scaling ----------
class View:
    """Maps world coordinates to screen pixels and keeps scaled copies of images.

    The world is letterboxed (black bars) to preserve its aspect ratio, so every
    player sees exactly the same arena regardless of monitor size. Images are
    rescaled from their full-size originals only when the window or world size
    changes, not every frame.
    """
    def __init__(self, sprites: dict[str, pygame.Surface], background: pygame.Surface | None,
                 pixel_art: set[str] = frozenset()):
        self.sprites = sprites
        self.pixel_art = pixel_art  # sprite names scaled nearest-neighbour to keep hard pixel edges
        self.background = background
        self._key = None

    def update(self, screen_size: tuple[int, int], world_size: tuple[int, int]) -> None:
        if (screen_size, world_size) == self._key:
            return
        self._key = (screen_size, world_size)
        sw, sh = screen_size
        ww, wh = world_size
        self.scale = min(sw / ww, sh / wh)
        self.game_rect = pygame.Rect(0, 0, round(ww * self.scale), round(wh * self.scale))
        self.game_rect.center = (sw // 2, sh // 2)

        self.images = {name: self._scaled(img, name in self.pixel_art) for name, img in self.sprites.items()}
        self.bg = (pygame.transform.smoothscale(self.background, self.game_rect.size)
                   if self.background else None)
        self.font = pygame.font.Font(None, max(12, round(24 * self.scale)))

    def _scaled(self, img: pygame.Surface, pixel_art: bool) -> pygame.Surface:
        w, h = img.get_size()
        size = (max(1, round(w * self.scale)), max(1, round(h * self.scale)))
        if pixel_art:
            return pygame.transform.scale(img, size)
        return pygame.transform.smoothscale(img, size)

    def to_screen(self, x: float, y: float) -> tuple[int, int]:
        return (self.game_rect.x + round(x * self.scale),
                self.game_rect.y + round(y * self.scale))

def enable_hidpi() -> None:
    # Without this, Windows display scaling (125%, 150%...) makes SDL see a
    # smaller "virtual" resolution and the OS blurs the upscaled result.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

def set_display(fullscreen: bool, windowed_size: tuple[int, int]) -> pygame.Surface:
    if fullscreen:
        return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)  # native desktop resolution
    return pygame.display.set_mode(windowed_size, pygame.RESIZABLE)

# ---------- Pygame drawing ----------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=50007)
    parser.add_argument("--name", default="Cat")
    parser.add_argument("--music", default="music.mp3")  # optional
    parser.add_argument("--fullscreen", action="store_true", help="start fullscreen (F11 or Alt+Enter toggles)")
    args = parser.parse_args()

    enable_hidpi()
    pygame.init()
    fullscreen = args.fullscreen
    windowed_size = (WIDTH, HEIGHT)
    screen = set_display(fullscreen, windowed_size)
    pygame.display.set_caption("Laser Cat (Client)")
    clock = pygame.time.Clock()

    # Load assets at full size; View makes scaled copies for the current resolution.
    # Background is optional—fall back to solid color if missing
    bg = None
    for candidate in ("background1.jpg", "Background1.jpg", "Background1.png", "background.jpg", "background.png"):
        if os.path.exists(candidate):
            bg = pygame.image.load(candidate).convert()
            break

    view = View({
        "cat_right": pygame.image.load("cat2.png").convert_alpha(),
        "cat_left":  pygame.image.load("cat.png").convert_alpha(),
        "coin":      pygame.image.load("coin_Custom_Custom.png").convert_alpha(),
        "laser":     pygame.image.load("laser.bmp").convert_alpha(),
    }, bg, pixel_art={"cat_right", "cat_left"})

    # Music (client-driven via flag from server)
    mixer_ready = False
    try:
        pygame.mixer.init()
        mixer_ready = True
    except Exception:
        mixer_ready = False  # okay to skip

    have_music_file = mixer_ready and os.path.exists(args.music)

    # Connect to the authoritative server
    sock = connect(args.host, args.port, args.name)

    # Track last input send to throttle a bit
    last_input_send = 0.0
    input_interval = 0.033  # send at least ~12/s, plus on key events

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        # --- events ---
        need_immediate_input_send = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.VIDEORESIZE and not fullscreen:
                windowed_size = event.size  # remember for when we leave fullscreen

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_F11 or (event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT):
                    fullscreen = not fullscreen
                    screen = set_display(fullscreen, windowed_size)
                elif event.key == pygame.K_SPACE:
                    # Request round start
                    _send_json(sock, {"type": "start"})
                # On any keydown/up, send inputs immediately for snappier feel
                need_immediate_input_send = True

            elif event.type == pygame.KEYUP:
                need_immediate_input_send = True

        # --- input sending (throttled + on-change) ---
        now = time.time()
        if need_immediate_input_send or (now - last_input_send) >= input_interval:
            send_inputs(sock)
            last_input_send = now

        # --- music control (optional) ---
        if mixer_ready and have_music_file:
            if latest_state.get("music", False):
                if not pygame.mixer.music.get_busy():
                    try:
                        pygame.mixer.music.load(args.music)
                        pygame.mixer.music.play(-1)
                    except Exception:
                        pass
            else:
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()

        # --- render ---
        screen = pygame.display.get_surface()  # may have been resized
        world = latest_state.get("world") or {}
        view.update(screen.get_size(), (world.get("w", WIDTH), world.get("h", HEIGHT)))

        screen.fill((0, 0, 0))  # letterbox bars
        if view.bg:
            screen.blit(view.bg, view.game_rect)
        else:
            screen.fill((255, 255, 255), view.game_rect)

        # Draw coin
        coin = latest_state.get("coin")
        if coin:
            screen.blit(view.images["coin"], view.to_screen(coin["x"], coin["y"]))

        # Draw lasers
        for L in latest_state.get("lasers", []):
            screen.blit(view.images["laser"], view.to_screen(L["x"], L["y"]))

        # Draw players
        players = latest_state.get("players", {})
        for pid_str, p in players.items():
            img = view.images["cat_right" if p.get("facing_right", True) else "cat_left"]
            screen.blit(img, view.to_screen(p["x"], p["y"]))

        # HUD (simple)
        ra = "ON" if latest_state.get("round_active") else "OFF"
        you = players.get(str(my_pid)) if isinstance(players, dict) else None
        score_text = you.get("score", 0) if isinstance(you, dict) else 0
        hud = view.font.render(f"Round: {ra}  |  You: {args.name}  |  Score: {score_text}  |  FPS: {clock.get_fps():.0f}", True, (20, 20, 20))
        screen.blit(hud, view.to_screen(8, 8))

        pygame.display.flip()

    try:
        sock.close()
    except Exception:
        pass
    pygame.quit()

if __name__ == "__main__":
    main()
