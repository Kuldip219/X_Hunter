"""A single player-fired bullet."""

from __future__ import annotations

import settings


class Bullet:
    def __init__(self, x: float, y: float, speed: int = settings.BULLET_SPEED) -> None:
        self.x = x
        self.y = y
        self.speed = speed

    def update(self) -> None:
        self.y -= self.speed

    @property
    def off_screen(self) -> bool:
        return self.y < settings.BULLET_OFFSCREEN_Y
