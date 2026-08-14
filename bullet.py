"""A single player-fired bullet."""

from __future__ import annotations

import pygame

import settings


class Bullet:
    def __init__(self, x: float, y: float, speed: float = settings.BULLET_SPEED_PER_SEC) -> None:
        self.x = x
        self.y = y
        # Speed is in px/second; per-frame displacement = speed * dt.
        self.speed = speed

    def update(self, dt: float) -> None:
        self.y -= self.speed * dt

    @property
    def off_screen(self) -> bool:
        return self.y < settings.BULLET_OFFSCREEN_Y

    def get_rect(self) -> pygame.Rect:
        """
        Collision rect matching the rendered bullet sprite (10x20), drawn from
        the same top-left corner (x, y) as the image.
        """
        return pygame.Rect(self.x, self.y, *settings.BULLET_IMG_SIZE)
