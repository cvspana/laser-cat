# view.py — resolution scaling and display helpers shared by every scene
from __future__ import annotations
import os, sys
import pygame

ASSET_DIR = os.path.dirname(os.path.abspath(__file__))

def asset(name: str) -> str:
    """Path to a file next to the game, so it runs from any working directory."""
    return os.path.join(ASSET_DIR, name)

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
        self._fonts: dict[tuple[str | None, int], pygame.font.Font] = {}

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
        self.dim = pygame.Surface(self.game_rect.size, pygame.SRCALPHA)
        self.dim.fill((0, 0, 0, 150))  # darkens the game behind menus/overlays
        self._fonts.clear()

    def _scaled(self, img: pygame.Surface, pixel_art: bool) -> pygame.Surface:
        w, h = img.get_size()
        size = (max(1, round(w * self.scale)), max(1, round(h * self.scale)))
        if pixel_art:
            return pygame.transform.scale(img, size)
        return pygame.transform.smoothscale(img, size)

    def to_screen(self, x: float, y: float) -> tuple[int, int]:
        return (self.game_rect.x + round(x * self.scale),
                self.game_rect.y + round(y * self.scale))

    def font(self, size: int, file: str | None = None) -> pygame.font.Font:
        """A font whose size is given in world units, rendered at screen resolution."""
        key = (file, size)
        if key not in self._fonts:
            self._fonts[key] = pygame.font.Font(file, max(8, round(size * self.scale)))
        return self._fonts[key]

    def text(self, screen: pygame.Surface, msg: str, size: int, pos: tuple[float, float],
             color=(255, 255, 255), anchor: str = "center", file: str | None = None,
             shadow: bool = True) -> pygame.Rect:
        """Draw text at a world position and return its screen rect (for mouse hit tests)."""
        font = self.font(size, file)
        img = font.render(msg, True, color)
        rect = img.get_rect(**{anchor: self.to_screen(*pos)})
        if shadow:
            offset = max(1, round(2 * self.scale))
            screen.blit(font.render(msg, True, (0, 0, 0)), rect.move(offset, offset))
        screen.blit(img, rect)
        return rect

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
