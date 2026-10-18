# settings.py — player preferences, saved to settings.json next to the game
from __future__ import annotations
import json
from dataclasses import dataclass, asdict, fields

from view import asset

SETTINGS_PATH = asset("settings.json")

@dataclass
class Settings:
    name: str = "Cat"
    fullscreen: bool = False
    music_volume: float = 0.7  # 0.0 .. 1.0
    last_address: str = "127.0.0.1"

    @classmethod
    def load(cls) -> "Settings":
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return cls()  # first run or unreadable file: use defaults
        if not isinstance(data, dict):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self) -> None:
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
        except OSError:
            pass  # not being able to save settings shouldn't crash the game
