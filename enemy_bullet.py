"""A single enemy-fired bullet."""

from __future__ import annotations

import pygame

import settings


class EnemyBullet:
    """Bullet fired by gunner enemies. Travels straight down at a fixed
    speed and is destroyed when it leaves the screen."""

    def __init__(
        self,
        x: float,
        y: float,
        speed: float = settings.ENEMY_BULLET_SPEED_PER_SEC,
    ) -> None:
        self.x = x
        self.y = y
        self.speed = speed

    def update(self, dt: float) -> None:
        self.y += self.speed * dt

    @property
    def off_screen(self) -> bool:
        return self.y > settings.ENEMY_BULLET_OFFSCREEN_Y

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(self.x, self.y, *settings.ENEMY_BULLET_IMG_SIZE)
