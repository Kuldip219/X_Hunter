"""A single enemy-fired bullet.

Gunner enemies fire straight down (the default). The Level 3 boss reuses
this same bullet class for its spread shot by passing an angle: 0 degrees
is straight down, positive angles fan to the right.
"""

from __future__ import annotations

import math

import pygame

import settings


class EnemyBullet:
    """Bullet fired by enemies. Travels in a straight line at a fixed speed
    and is destroyed when it leaves the screen."""

    def __init__(
        self,
        x: float,
        y: float,
        speed: float = settings.ENEMY_BULLET_SPEED_PER_SEC,
        angle_degrees: float = 0.0,
    ) -> None:
        self.x = x
        self.y = y
        self.speed = speed
        # angle 0 = straight down. Positive = fanned to the right.
        self.angle_degrees = angle_degrees
        radians = math.radians(angle_degrees)
        # Velocity components (px/s). angle 0 -> (0, +speed): unchanged
        # straight-down behaviour for every existing caller.
        self.vx = math.sin(radians) * speed
        self.vy = math.cos(radians) * speed

    def update(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt

    @property
    def off_screen(self) -> bool:
        """Gone once it leaves the bottom or either side. The horizontal
        bounds only matter for angled (boss) bullets, but the check is
        harmless for straight-down ones."""
        return (
            self.y > settings.ENEMY_BULLET_OFFSCREEN_Y
            or self.x < -settings.ENEMY_BULLET_OFFSCREEN_X_MARGIN
            or self.x > settings.WIDTH + settings.ENEMY_BULLET_OFFSCREEN_X_MARGIN
        )

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(self.x, self.y, *settings.ENEMY_BULLET_IMG_SIZE)
