# scenes.py — the screens of the game: menus and gameplay.
#
# The App (main3.py) runs one Scene at a time. Each scene handles its own input,
# updates and drawing, and moves to another screen with app.switch(...).
# Positions are in world units (800x600); the View scales them to the screen.
from __future__ import annotations
import time
import pygame

import server
from connection import Connection, parse_address, lan_ip
from view import View, asset

FONT = asset("visitor1.ttf")
WHITE = (255, 255, 255)
YELLOW = (255, 220, 60)
GREY = (170, 170, 190)
RED = (255, 110, 110)

CENTER_X = server.WORLD_W / 2
INPUT_INTERVAL = 0.033  # resend inputs at least this often, plus on every key change

class Scene:
    show_cursor = True

    def __init__(self, app) -> None:
        self.app = app

    def world_size(self) -> tuple[int, int]:
        return (server.WORLD_W, server.WORLD_H)

    def handle_event(self, event: pygame.event.Event) -> None: pass
    def update(self, dt: float) -> None: pass
    def draw(self, screen: pygame.Surface, view: View) -> None: pass

    def leave(self) -> None:
        """Called when the app switches away from this scene (or quits)."""

def draw_backdrop(screen: pygame.Surface, view: View) -> None:
    screen.fill((0, 0, 0))
    if view.bg:
        screen.blit(view.bg, view.game_rect)
    screen.blit(view.dim, view.game_rect)

# ---------- Menu widgets ----------
class Button:
    def __init__(self, label, action) -> None:
        self.label = label  # a string, or a function returning one (for live values)
        self.action = action

    def text(self, selected: bool) -> str:
        return self.label() if callable(self.label) else self.label

class Option(Button):
    """A setting changed with Left/Right (Enter also steps it forward)."""
    def __init__(self, label, adjust) -> None:
        super().__init__(label, lambda: adjust(+1))
        self.adjust = adjust

    def text(self, selected: bool) -> str:
        value = super().text(selected)
        return f"< {value} >" if selected else value

class TextField:
    def __init__(self, label: str, value: str, max_len: int = 24) -> None:
        self.label = label
        self.value = value
        self.max_len = max_len

    def text(self, selected: bool) -> str:
        cursor = "_" if selected and time.time() % 1 < 0.5 else " "
        return f"{self.label}: {self.value}{cursor}"

class MenuScene(Scene):
    title = ""
    hint = "Arrows + Enter to choose    ESC back    F11 fullscreen"
    title_size = 56

    def __init__(self, app, message: str = "") -> None:
        super().__init__(app)
        self.message = message
        self.items = self.build_items()
        self.index = 0
        self._rects: list[pygame.Rect] = []

    def build_items(self) -> list:
        return []

    def back(self) -> None:
        self.app.switch(MainMenu(self.app))

    def move(self, step: int) -> None:
        self.index = (self.index + step) % len(self.items)

    def activate(self) -> None:
        item = self.items[self.index]
        if isinstance(item, TextField):
            self.move(1)  # Enter in a text box moves on, like a form
        else:
            item.action()

    def handle_event(self, event: pygame.event.Event) -> None:
        item = self.items[self.index]
        typing = isinstance(item, TextField)  # letters type text instead of navigating
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP or (event.key == pygame.K_w and not typing):
                self.move(-1)
            elif event.key == pygame.K_DOWN or (event.key == pygame.K_s and not typing):
                self.move(1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) or (event.key == pygame.K_SPACE and not typing):
                self.activate()
            elif isinstance(item, Option) and event.key in (pygame.K_LEFT, pygame.K_a):
                item.adjust(-1)
            elif isinstance(item, Option) and event.key in (pygame.K_RIGHT, pygame.K_d):
                item.adjust(+1)
            elif typing and event.key == pygame.K_BACKSPACE:
                item.value = item.value[:-1]
            elif event.key == pygame.K_ESCAPE:
                self.back()
        elif event.type == pygame.TEXTINPUT and typing:
            item.value = (item.value + event.text)[:item.max_len]
        elif event.type == pygame.MOUSEMOTION:
            hit = self._item_at(event.pos)
            if hit is not None:
                self.index = hit
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hit = self._item_at(event.pos)
            if hit is not None:
                self.index = hit
                self.activate()

    def _item_at(self, pos) -> int | None:
        for i, rect in enumerate(self._rects):
            if rect.collidepoint(pos):
                return i
        return None

    def draw(self, screen: pygame.Surface, view: View) -> None:
        draw_backdrop(screen, view)
        view.text(screen, self.title, self.title_size, (CENTER_X, 110), YELLOW, file=FONT)
        if self.message:
            view.text(screen, self.message, 20, (CENTER_X, 190), RED, file=FONT)
        self._rects = []
        for i, item in enumerate(self.items):
            selected = i == self.index
            rect = view.text(screen, item.text(selected), 32, (CENTER_X, 250 + i * 50),
                             YELLOW if selected else WHITE, file=FONT)
            self._rects.append(rect)
        view.text(screen, self.hint, 16, (CENTER_X, 570), GREY, file=FONT)

# ---------- Menus ----------
class MainMenu(MenuScene):
    title = "LASER CAT"
    title_size = 80
    hint = "Arrows + Enter to choose    F11 fullscreen"

    def build_items(self) -> list:
        return [
            Button("Single Player", lambda: start_local_game(self.app, public=False)),
            Button("Host Game", lambda: start_local_game(self.app, public=True)),
            Button("Join Game", lambda: self.app.switch(JoinMenu(self.app))),
            Button("Settings", lambda: self.app.switch(SettingsMenu(self.app))),
            Button("Quit", self.app.quit),
        ]

    def back(self) -> None:
        self.app.quit()

class JoinMenu(MenuScene):
    title = "JOIN GAME"

    def __init__(self, app, address: str | None = None, auto_connect: bool = False) -> None:
        self.initial_address = address or app.settings.last_address
        super().__init__(app)
        self._connect_in_frames = 0
        if auto_connect:
            self.connect()

    def build_items(self) -> list:
        self.address = TextField("Address", self.initial_address, 40)
        return [self.address, Button("Connect", self.connect), Button("Back", self.back)]

    def connect(self) -> None:
        # Connecting blocks for a moment, so draw "Connecting..." for a frame first
        self.message = "Connecting..."
        self._connect_in_frames = 2

    def update(self, dt: float) -> None:
        if self._connect_in_frames == 0:
            return
        self._connect_in_frames -= 1
        if self._connect_in_frames > 0:
            return
        try:
            host, port = parse_address(self.address.value, server.DEFAULT_PORT)
        except ValueError:
            self.message = "That address doesn't look right"
            return
        try:
            conn = Connection(host, port, self.app.settings.name)
        except OSError:
            self.message = f"Couldn't reach a game at {host}:{port}"
            return
        self.app.settings.last_address = self.address.value.strip()
        self.app.settings.save()
        self.app.switch(GameScene(self.app, conn))

    def draw(self, screen: pygame.Surface, view: View) -> None:
        super().draw(screen, view)
        view.text(screen, f"Playing as {self.app.settings.name}  (change in Settings)", 18,
                  (CENTER_X, 420), GREY, file=FONT)

class SettingsMenu(MenuScene):
    title = "SETTINGS"
    hint = "Left/Right to change    ESC back"

    def build_items(self) -> list:
        s = self.app.settings
        self.name = TextField("Name", s.name, 16)
        return [
            Option(lambda: f"Fullscreen: {'On' if self.app.fullscreen else 'Off'}",
                   lambda step: self.app.set_fullscreen(not self.app.fullscreen)),
            Option(lambda: f"Music Volume: {round(s.music_volume * 100)}%", self.change_volume),
            self.name,
            Button("Back", self.back),
        ]

    def change_volume(self, step: int) -> None:
        s = self.app.settings
        s.music_volume = min(1.0, max(0.0, round(s.music_volume + step * 0.1, 1)))
        self.app.apply_volume()

    def back(self) -> None:
        self.app.settings.name = self.name.value.strip() or "Cat"
        self.app.settings.save()
        super().back()

# ---------- Gameplay ----------
def start_local_game(app, public: bool) -> None:
    """Run the server inside this process and join it.

    Single player listens only on this computer (on any free port); Host Game
    listens on the network on the standard port so friends can join.
    """
    try:
        if public:
            handle = server.start_server("0.0.0.0", server.DEFAULT_PORT)
        else:
            handle = server.start_server("127.0.0.1", 0)
    except OSError:
        app.switch(MainMenu(app, f"Can't host: port {server.DEFAULT_PORT} is already in use"))
        return
    try:
        conn = Connection("127.0.0.1", handle.port, app.settings.name)
    except OSError:
        handle.stop()
        app.switch(MainMenu(app, "Couldn't start the game"))
        return
    info = f"Hosting at {lan_ip()}:{handle.port}" if public else None
    app.switch(GameScene(app, conn, server_handle=handle, info=info))

class GameScene(Scene):
    show_cursor = False

    def __init__(self, app, conn: Connection, server_handle: server.ServerHandle | None = None,
                 info: str | None = None) -> None:
        super().__init__(app)
        self.conn = conn
        self.server_handle = server_handle  # set when we're running the server ourselves
        self.info = info
        self.last_input_send = 0.0
        self.need_input_send = True

    def world_size(self) -> tuple[int, int]:
        world = self.conn.state.get("world") or {}
        return (world.get("w", server.WORLD_W), world.get("h", server.WORLD_H))

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.switch(MainMenu(self.app))
                return
            if event.key == pygame.K_SPACE:
                self.conn.start_round()
            # On any keydown/up, send inputs immediately for snappier feel
            self.need_input_send = True
        elif event.type == pygame.KEYUP:
            self.need_input_send = True

    def update(self, dt: float) -> None:
        if self.conn.closed:
            self.app.switch(MainMenu(self.app, "Lost connection to the game"))
            return
        now = time.time()
        if self.need_input_send or (now - self.last_input_send) >= INPUT_INTERVAL:
            self.conn.send_inputs()
            self.last_input_send = now
            self.need_input_send = False
        self.app.set_music(self.conn.state.get("music", False))

    def leave(self) -> None:
        self.conn.close()
        if self.server_handle:
            self.server_handle.stop()  # also disconnects anyone who joined us
        self.app.set_music(False)

    def draw(self, screen: pygame.Surface, view: View) -> None:
        state = self.conn.state
        screen.fill((0, 0, 0))  # letterbox bars
        if view.bg:
            screen.blit(view.bg, view.game_rect)
        else:
            screen.fill(WHITE, view.game_rect)

        coin = state.get("coin")
        if coin:
            screen.blit(view.images["coin"], view.to_screen(coin["x"], coin["y"]))

        for L in state.get("lasers", []):
            screen.blit(view.images["laser"], view.to_screen(L["x"], L["y"]))

        players = state.get("players", {})
        for p in players.values():
            img = view.images["cat_right" if p.get("facing_right", True) else "cat_left"]
            screen.blit(img, view.to_screen(p["x"], p["y"]))

        if state.get("round_active"):
            you = players.get(str(self.conn.pid), {})
            hud = (f"You: {self.app.settings.name}  |  Score: {you.get('score', 0)}"
                   f"  |  FPS: {self.app.clock.get_fps():.0f}")
            view.text(screen, hud, 24, (8, 8), (20, 20, 20), anchor="topleft", shadow=False)
        else:
            self.draw_round_overlay(screen, view, players, state.get("tick", 0) > 0)
        if self.info:
            view.text(screen, self.info, 18, (8, 592), WHITE, anchor="bottomleft", file=FONT)

    def draw_round_overlay(self, screen: pygame.Surface, view: View, players: dict, round_over: bool) -> None:
        screen.blit(view.dim, view.game_rect)
        view.text(screen, "ROUND OVER" if round_over else "READY?", 56, (CENTER_X, 190), YELLOW, file=FONT)
        view.text(screen, "Press SPACE to start", 28, (CENTER_X, 260), WHITE, file=FONT)
        view.text(screen, "ESC  Main Menu", 16, (CENTER_X, 295), GREY, file=FONT)
        ranked = sorted(players.values(), key=lambda p: p.get("score", 0), reverse=True)
        for i, p in enumerate(ranked[:6]):
            view.text(screen, f"{p.get('name', '?')}   {p.get('score', 0)}", 22,
                      (CENTER_X, 345 + i * 28), WHITE, file=FONT)
