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
        self.invulnerable_timer = 0

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

    def update_invulnerability(self) -> None:
        """Decrement the i-frame timer once per frame (no-op while safe)."""
        if self.invulnerable_timer > 0:
            self.invulnerable_timer -= 1

    @property
    def invulnerable(self) -> bool:
        """True while the post-hit i-frame window is active."""
        return self.invulnerable_timer > 0

    def take_hit(self) -> bool:
        """
        Apply one hit of damage. Returns True if damage was actually applied.

        Lethality is checked first: a hit that would bring health to 0 (or
        below) always applies and triggers death, even while the player is
        invulnerable - the i-frame window never protects the death sequence
        itself. Only non-lethal hits are blocked during the window, so
        overlapping enemies can no longer drain multiple HP per frame. The
        player is teleported off-screen and hidden while its death explosion
        plays out, exactly matching the original logic.
        """
        # A dead player cannot be hit again: the death sequence must never
        # re-trigger, no matter who calls take_hit.
        if self.dead:
            return False

        # A lethal hit always lands, regardless of the invulnerability state.
        if self.health <= 1:
            self.health = 0

            self.explosion = Explosion(
                self.x - 10, self.y - 10, frame_delay=settings.PLAYER_EXPLOSION_FRAME_DELAY
            )

            self.x = -1000
            self.y = -1000

            self.dead = True
            return True

        if self.invulnerable:
            return False

        self.health -= 1
        self.invulnerable_timer = settings.PLAYER_INVULNERABLE_DURATION
        return True

    def draw(
        self,
        screen: pygame.Surface,
        image: pygame.Surface,
        offset: tuple[int, int] = (0, 0),
    ) -> None:
        if self.dead:
            return
        # Blink while invulnerable so the temporary safety is visible.
        if self.invulnerable and not self._blink_visible():
            return
        screen.blit(image, (self.x + offset[0], self.y + offset[1]))

    def _blink_visible(self) -> bool:
        """Toggle visibility every PLAYER_BLINK_INTERVAL frames while invulnerable."""
        return (self.invulnerable_timer // settings.PLAYER_BLINK_INTERVAL) % 2 == 0
