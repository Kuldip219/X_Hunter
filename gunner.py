"""Gunner enemy: Level 2 exclusive.

Descends to a random Y position, stops, drifts side-to-side, and fires
straight down on a fixed cooldown.
"""

from __future__ import annotations

import random

import pygame

import settings


class GunnerEnemy:
    """An enemy that descends to a stop position, then drifts and shoots."""

    def __init__(
        self,
        x: float,
        y: float,
        screen_width: int,
        width: int = settings.ENEMY_WIDTH,
        height: int = settings.ENEMY_HEIGHT,
    ) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.screen_width = screen_width

        # Pick a random stop-Y within the max descent bound.
        max_stop_y = settings.HEIGHT * settings.GUNNER_MAX_DESCENT_FRACTION - self.height
        self.stop_y = random.randint(int(max_stop_y * 0.5), int(max_stop_y))

        # Descent speed (px/s downward) — difficulty will override this.
        self.descend_speed: float = settings.GUNNER_DESCEND_SPEED_PER_SEC

        # Drift speed (px/s horizontal) — difficulty will override this.
        self.drift_speed: float = settings.GUNNER_DRIFT_SPEED_PER_SEC

        # Drift direction: 1 = right, -1 = left. Flips on screen edges.
        self.drift_dir: int = 1 if random.random() < 0.5 else -1

        # State: descending → stopped (drifting + shooting)
        self.stopped: bool = False

        # Fire cooldown: fires immediately upon stopping, then on cooldown.
        self.fire_cooldown: float = 0.0

    @classmethod
    def spawn_initial(cls, screen_width: int) -> "GunnerEnemy":
        """Spawn above the screen, ready to descend."""
        x = random.randint(0, screen_width - settings.ENEMY_WIDTH)
        y = random.randint(settings.INITIAL_ENEMY_MIN_Y, settings.INITIAL_ENEMY_MAX_Y)
        return cls(x, y, screen_width)

    def respawn(self, screen_width: int) -> None:
        """Reposition above the screen with a new stop-Y."""
        self.screen_width = screen_width
        self.x = random.randint(0, screen_width - self.width)
        self.y = random.randint(settings.RESPAWN_ENEMY_MIN_Y, settings.RESPAWN_ENEMY_MAX_Y)
        max_stop_y = settings.HEIGHT * settings.GUNNER_MAX_DESCENT_FRACTION - self.height
        self.stop_y = random.randint(int(max_stop_y * 0.5), int(max_stop_y))
        self.stopped = False
        self.fire_cooldown = 0.0
        self.drift_dir = 1 if random.random() < 0.5 else -1

    def update(self, dt: float) -> None:
        if not self.stopped:
            # Descend toward stop_y.
            self.y += self.descend_speed * dt
            if self.y >= self.stop_y:
                self.y = self.stop_y
                self.stopped = True
                self.fire_cooldown = 0.0  # fire immediately
        else:
            # Drift side-to-side, bouncing off screen edges.
            self.x += self.drift_speed * self.drift_dir * dt
            if self.x <= 0:
                self.x = 0
                self.drift_dir = 1
            elif self.x >= self.screen_width - self.width:
                self.x = self.screen_width - self.width
                self.drift_dir = -1

            # Tick fire cooldown.
            if self.fire_cooldown > 0:
                self.fire_cooldown = max(0.0, self.fire_cooldown - dt)

    def can_fire(self) -> bool:
        """True when the gunner should fire this frame (just stopped or
        cooldown has elapsed)."""
        return self.stopped and self.fire_cooldown <= 0.0

    def reset_fire_cooldown(self) -> None:
        """Called after firing to start the cooldown timer."""
        self.fire_cooldown = settings.GUNNER_FIRE_COOLDOWN_SECONDS

    def is_off_screen(self, screen_height: int) -> bool:
        """Gunner enemies don't scroll off the bottom — they stop. But if
        for some reason they end up below screen, treat as off-screen."""
        return self.y > screen_height

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def draw(
        self,
        screen: pygame.Surface,
        image: pygame.Surface,
        offset: tuple[int, int] = (0, 0),
    ) -> None:
        screen.blit(image, (self.x + offset[0], self.y + offset[1]))
