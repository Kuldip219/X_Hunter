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
        speed: float = settings.PLAYER_SPEED_PER_SEC,
        health: int = settings.PLAYER_START_HEALTH,
    ) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        # Speed is in px/second; per-frame displacement = speed * dt.
        self.speed = speed
        self.health = health
        # Lives remaining including the current one: with the default of 1 a
        # single death ends the run, exactly like the original game. An EXTRA
        # LIFE power-up adds spare lives; dying with a spare burns one and
        # respawns the ship (see respawn()).
        self.lives = settings.PLAYER_START_LIVES
        self.dead = False
        self.explosion: Optional[Explosion] = None
        self.invulnerable_timer = 0.0
        self.fire_cooldown = 0.0
        # Timed power-up windows (seconds, real time, ticked by update_powerups).
        self.shield_timer = 0.0
        self.rapid_fire_timer = 0.0

    def handle_input(self, keys: Sequence[bool], dt: float) -> None:
        """Move left/right based on currently-held keys. No-op while dead.

        Movement is time-based: displacement = speed (px/s) * dt (s), so the
        player covers the same distance per second at any frame rate.
        """
        if self.dead:
            return
        if keys[pygame.K_LEFT]:
            self.x -= self.speed * dt
        if keys[pygame.K_RIGHT]:
            self.x += self.speed * dt

    def clamp_to_screen(self, screen_width: int) -> None:
        self.x = max(0, min(screen_width - self.width, self.x))

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def spawn_bullet(self) -> Bullet:
        return Bullet(self.x + self.width // 2, self.y)

    @staticmethod
    def _tick_down(timer: float, dt: float) -> float:
        """Decrement a seconds-based timer by dt, snapping float residuals
        to exactly 0.0 so a cooldown/window expires at precisely the right
        instant (1e-9 s is far below one frame, so this never fires early)."""
        remaining = max(0.0, timer - dt)
        return 0.0 if remaining <= 1e-9 else remaining

    def update_invulnerability(self, dt: float) -> None:
        """Tick the i-frame window by real time (no-op while safe)."""
        if self.invulnerable_timer > 0:
            self.invulnerable_timer = self._tick_down(self.invulnerable_timer, dt)

    def update_fire_cooldown(self, dt: float) -> None:
        """Tick the hold-to-fire cooldown by real time."""
        if self.fire_cooldown > 0:
            self.fire_cooldown = self._tick_down(self.fire_cooldown, dt)

    def update_powerups(self, dt: float) -> None:
        """Tick the timed power-up windows (shield / rapid fire) by real
        time. Extra life has no timer, so it needs no update here."""
        if self.shield_timer > 0:
            self.shield_timer = self._tick_down(self.shield_timer, dt)
        if self.rapid_fire_timer > 0:
            self.rapid_fire_timer = self._tick_down(self.rapid_fire_timer, dt)

    @property
    def can_fire(self) -> bool:
        """True when the fire cooldown has elapsed and a shot may be fired."""
        return self.fire_cooldown <= 0.0

    @property
    def invulnerable(self) -> bool:
        """True while the post-hit i-frame window is active."""
        return self.invulnerable_timer > 0.0

    @property
    def shield_active(self) -> bool:
        """True while the SHIELD power-up is up (blocks ALL damage)."""
        return self.shield_timer > 0.0

    @property
    def rapid_fire_active(self) -> bool:
        """True while the RAPID FIRE power-up is up."""
        return self.rapid_fire_timer > 0.0

    def fire_cooldown_value(self) -> float:
        """The hold-to-fire cooldown for the next shot: the base value, or
        the rapid-fire value while that power-up is active."""
        cooldown = settings.PLAYER_FIRE_COOLDOWN_SECONDS
        if self.rapid_fire_active:
            cooldown *= settings.RAPID_FIRE_COOLDOWN_MULTIPLIER
        return cooldown

    def apply_powerup(self, kind: str) -> str:
        """Apply a picked-up power-up effect. Returns the kind applied.

        Shield and rapid fire set their (real-time) windows to the full
        duration - collecting another of the same kind while active simply
        refreshes it, never stacks. Extra life adds one spare life with no
        timer involved.
        """
        if kind == settings.POWERUP_KIND_SHIELD:
            self.shield_timer = settings.POWERUP_SHIELD_DURATION_SECONDS
        elif kind == settings.POWERUP_KIND_RAPID_FIRE:
            self.rapid_fire_timer = settings.POWERUP_RAPID_FIRE_DURATION_SECONDS
        elif kind == settings.POWERUP_KIND_LIFE:
            self.lives += 1
        return kind

    def respawn(self, x: float, y: float) -> None:
        """Reset the ship after burning a spare life: full health, back at
        the spawn point, with a short spawn-invulnerability window (visible
        via the existing blink) so the player isn't instantly re-killed by
        enemies still on the field. The death sequence is complete at this
        point, so flipping dead back to False here is the H1-sanctioned
        revival - it never happens during a fade-out."""
        self.x = x
        self.y = y
        self.health = settings.PLAYER_START_HEALTH
        self.dead = False
        self.explosion = None
        self.invulnerable_timer = settings.POWERUP_RESPAWN_INVULNERABLE_SECONDS

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

        # The SHIELD power-up grants full invincibility: it blocks every hit,
        # including a would-be lethal one, for its whole duration. Unlike the
        # post-hit i-frame window (H2), the shield is never bypassed by a
        # killing blow - that is the point of picking it up.
        if self.shield_active:
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
        self.invulnerable_timer = settings.PLAYER_INVULNERABLE_DURATION_SECONDS
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
        """Toggle visibility every PLAYER_BLINK_INTERVAL_SECONDS of remaining
        i-frame time (real time, so the blink rate is frame-rate independent)."""
        phases = int(round(self.invulnerable_timer / settings.PLAYER_BLINK_INTERVAL_SECONDS))
        return phases % 2 == 0
