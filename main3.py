# main3.py — Laser Cat launcher: opens the main menu and runs the game's scenes
# Python 3.10 / Pygame 2.x
#
#   python main3.py                       open the main menu
#   python main3.py --join 192.168.1.5    skip the menu and join a game
#   python main3.py --fullscreen          start fullscreen (F11 / Alt+Enter toggles)

from __future__ import annotations
import argparse, os
import pygame

import server
from scenes import MainMenu, JoinMenu
from settings import Settings
from view import View, asset, enable_hidpi, set_display

FPS = 144

class App:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        enable_hidpi()
        pygame.init()
        self.fullscreen = settings.fullscreen
        self.windowed_size = (server.WORLD_W, server.WORLD_H)
        set_display(self.fullscreen, self.windowed_size)
        pygame.display.set_caption("Laser Cat")
        self.clock = pygame.time.Clock()

        # Load assets at full size; View makes scaled copies for the current resolution.
        # Background is optional—fall back to solid color if missing
        bg = None
        for candidate in ("background1.jpg", "Background1.jpg", "Background1.png", "background.jpg", "background.png"):
            if os.path.exists(asset(candidate)):
                bg = pygame.image.load(asset(candidate)).convert()
                break

        self.view = View({
            "cat_right": pygame.image.load(asset("cat2.png")).convert_alpha(),
            "cat_left":  pygame.image.load(asset("cat.png")).convert_alpha(),
            "coin":      pygame.image.load(asset("coin_Custom_Custom.png")).convert_alpha(),
            "laser":     pygame.image.load(asset("laser.bmp")).convert_alpha(),
        }, bg, pixel_art={"cat_right", "cat_left"})

        # Music is optional—skip it if there's no audio device or file
        try:
            pygame.mixer.init()
            self.music_file = asset("music.mp3") if os.path.exists(asset("music.mp3")) else None
        except pygame.error:
            self.music_file = None

        self.running = True
        self.scene = MainMenu(self)

    # ---------- used by scenes ----------
    def switch(self, scene) -> None:
        self.scene.leave()
        self.scene = scene
        pygame.mouse.set_visible(scene.show_cursor)

    def quit(self) -> None:
        self.running = False

    def set_fullscreen(self, on: bool) -> None:
        self.fullscreen = on
        set_display(on, self.windowed_size)
        self.settings.fullscreen = on
        self.settings.save()

    def set_music(self, playing: bool) -> None:
        if not self.music_file:
            return
        if playing and not pygame.mixer.music.get_busy():
            try:
                pygame.mixer.music.load(self.music_file)
                pygame.mixer.music.play(-1)
                self.apply_volume()
            except pygame.error:
                self.music_file = None
        elif not playing and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()

    def apply_volume(self) -> None:
        if self.music_file:
            pygame.mixer.music.set_volume(self.settings.music_volume)

    # ---------- main loop ----------
    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
                    self.windowed_size = event.size  # remember for when we leave fullscreen
                elif event.type == pygame.KEYDOWN and (
                        event.key == pygame.K_F11 or (event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT)):
                    self.set_fullscreen(not self.fullscreen)
                else:
                    self.scene.handle_event(event)

            self.scene.update(dt)

            screen = pygame.display.get_surface()  # may have been resized
            self.view.update(screen.get_size(), self.scene.world_size())
            self.scene.draw(screen, self.view)
            pygame.display.flip()

        self.scene.leave()  # disconnect / stop a hosted server
        pygame.quit()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--join", metavar="ADDRESS", help="skip the menu and join HOST or HOST:PORT")
    parser.add_argument("--name", help="player name")
    parser.add_argument("--fullscreen", action="store_true", help="start fullscreen (F11 or Alt+Enter toggles)")
    args = parser.parse_args()

    settings = Settings.load()
    if args.name:
        settings.name = args.name[:16]
    if args.fullscreen:
        settings.fullscreen = True

    app = App(settings)
    if args.join:
        app.scene = JoinMenu(app, address=args.join, auto_connect=True)
    app.run()

if __name__ == "__main__":
    main()
