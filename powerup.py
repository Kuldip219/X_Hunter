"""A falling power-up dropped by destroyed enemies.

Power-ups never spawn freely on the field: each one comes from a defeated
enemy (a roll against settings.POWERUP_DROP_CHANCE in the bullet-enemy
collision). They drift down slowly and are auto-collected on contact with
the player (no extra keypress), then despawn after a real-time lifetime if
never touched. All timers are seconds-based and ticked by dt, so they stay
frame-rate independent under the fixed-timestep simulation.
"""

from __future__ import annotations

import pygame

import settings


class PowerUp:
    """A single falling pick-up. `kind` is one of settings.POWERUP_TYPES."""

    def __init__(
        self,
        kind: str,
        x: float,
        y: float,
        width: int = settings.POWERUP_IMG_SIZE[0],
        height: int = settings.POWERUP_IMG_SIZE[1],
        speed: float = settings.POWERUP_FALL_SPEED_PER_SEC,
        lifetime: float = settings.POWERUP_LIFETIME_SECONDS,
    ) -> None:
        self.kind = kind
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        # Drift speed is px/second; per-step displacement = speed * dt.
        self.speed = speed
        # Real-time on-field lifetime in seconds; expires even if untouched.
        self.lifetime = lifetime

    def update(self, dt: float) -> None:
        """Fall and tick the lifetime by real time."""
        self.y += self.speed * dt
        if self.lifetime > 0:
            self.lifetime = max(0.0, self.lifetime - dt)

    def expired(self, screen_height: int) -> bool:
        """True once the lifetime has run out or the icon drifted off-screen."""
        return self.lifetime <= 0 or self.y > screen_height

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(self.x, self.y, self.width, self.height)
