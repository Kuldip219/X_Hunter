"""The player-controlled ship."""

from __future__ import annotations
from typing import Optional, Sequence
from bullet import Bullet
from explosion import Explosion
import settings
import pygame


class Player:
    def __init__(
        self,
        x: float,
        y: float,
        width: int = settings.PLAYER_WIDTH,
        height: int = settings.PLAYER_HEIGHT,
        speed: int = settings.PLAYER_SPEED,
        health: int = settings.PLAYER_START_HEALTH,
    ) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.speed = speed
        self.health = health
        self.dead = False
        self.explosion: Optional[Explosion] = None

    def handle_input(self, keys: Sequence[bool]) -> None:
        """Move left/right based on currently-held keys. No-op while dead."""
        if self.dead:
            return
        if keys[pygame.K_LEFT]:
            self.x -= self.speed
        if keys[pygame.K_RIGHT]:
            self.x += self.speed

    def clamp_to_screen(self, screen_width: int) -> None:
        self.x = max(0, min(screen_width - self.width, self.x))

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def spawn_bullet(self) -> Bullet:
        return Bullet(self.x + self.width // 2, self.y)

    def take_hit(self) -> None:
        """
        Apply one hit of damage. If health drops to 0, kill the player and
        create the death explosion, exactly matching the original logic
        (player is teleported off-screen and hidden while its explosion
        plays out).
        """
        self.health -= 1

        if self.health <= 0:
            self.health = 0

            self.explosion = Explosion(
                self.x - 10, self.y - 10, frame_delay=settings.PLAYER_EXPLOSION_FRAME_DELAY
            )

            self.x = -1000
            self.y = -1000

            self.dead = True

    def draw(
        self,
        screen: pygame.Surface,
        image: pygame.Surface,
        offset: tuple[int, int] = (0, 0),
    ) -> None:
        if not self.dead:
            screen.blit(image, (self.x + offset[0], self.y + offset[1]))
