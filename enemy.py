"""A single enemy ship."""

from __future__ import annotations

import random

import pygame

import settings


class Enemy:
    def __init__(
        self,
        x: float,
        y: float,
        width: int = settings.ENEMY_WIDTH,
        height: int = settings.ENEMY_HEIGHT,
        speed: int = settings.ENEMY_SPEED,
    ) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.speed = speed

    @classmethod
    def spawn_initial(cls, screen_width: int) -> "Enemy":
        """
        Spawn used only for the first wave created by reset_game().

        NOTE: preserved from the original code, which used an X margin of 50
        (player width) here instead of the enemy width (40) used by
        respawn() below. Kept intentionally for identical behavior.
        """
        x = random.randint(0, screen_width - settings.INITIAL_ENEMY_X_MARGIN)
        y = random.randint(settings.INITIAL_ENEMY_MIN_Y, settings.INITIAL_ENEMY_MAX_Y)
        return cls(x, y)

    def respawn(self, screen_width: int) -> None:
        """Used when an enemy goes off-screen or hits the player."""
        self.y = random.randint(settings.RESPAWN_ENEMY_MIN_Y, settings.RESPAWN_ENEMY_MAX_Y)
        self.x = random.randint(0, screen_width - self.width)

    def update(self) -> None:
        self.y += self.speed

    def is_off_screen(self, screen_height: int) -> bool:
        return self.y > screen_height

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def contains_point(self, x: float, y: float) -> bool:
        """
        Point-in-rect test matching the original's manual comparison
        (strictly exclusive on both edges), used for bullet collisions.
        """
        return (
            x > self.x
            and x < self.x + self.width
            and y > self.y
            and y < self.y + self.height
        )

    def draw(
        self,
        screen: pygame.Surface,
        image: pygame.Surface,
        offset: tuple[int, int] = (0, 0),
    ) -> None:
        screen.blit(image, (self.x + offset[0], self.y + offset[1]))
