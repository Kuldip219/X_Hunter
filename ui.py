"""
Screen effects and HUD elements: screen shake, damage flash, the
fade-between-states transition, health bar, and score display.
"""

from __future__ import annotations

import random
from typing import Optional

import pygame

import settings


class ScreenShake:
    def __init__(self, strength: int = settings.SHAKE_STRENGTH) -> None:
        self.strength = strength
        self.timer = 0

    def trigger(self, duration: int = settings.SHAKE_DURATION_ON_HIT) -> None:
        self.timer = duration

    def update(self) -> tuple[int, int]:
        """Decrement the timer (if active) and return this frame's offset."""
        if self.timer > 0:
            self.timer -= 1
            return (
                random.randint(-self.strength, self.strength),
                random.randint(-self.strength, self.strength),
            )
        return (0, 0)


class DamageFlash:
    def __init__(
        self,
        color: tuple[int, int, int] = settings.DAMAGE_FLASH_COLOR,
        alpha: int = settings.DAMAGE_FLASH_ALPHA,
    ) -> None:
        self.color = color
        self.alpha = alpha
        self.timer = 0

    def trigger(self, duration: int = settings.DAMAGE_FLASH_DURATION) -> None:
        self.timer = duration

    def draw(self, screen: pygame.Surface) -> None:
        """Draw the flash overlay (if active) and decrement the timer."""
        if self.timer > 0:
            flash = pygame.Surface(screen.get_size())
            flash.set_alpha(self.alpha)
            flash.fill(self.color)
            screen.blit(flash, (0, 0))
            self.timer -= 1


class FadeTransition:
    """
    Handles fading to black between game states.

    start(target_state) begins a fade-out; once it completes, update()
    returns the target state (once) so the caller can switch game_state,
    then automatically begins fading back in - matching the original
    fading_in / fading_out / next_state logic.
    """

    def __init__(
        self,
        size: tuple[int, int],
        speed: int = settings.FADE_SPEED,
        color: tuple[int, int, int] = settings.BLACK,
    ) -> None:
        self.surface = pygame.Surface(size)
        self.surface.fill(color)
        self.speed = speed
        self.alpha = 255
        self.fading_in = True
        self.fading_out = False
        self.next_state: Optional[str] = None

    def start(self, target_state: str) -> None:
        self.fading_out = True
        self.fading_in = False
        self.next_state = target_state
        self.alpha = 0

    def update(self) -> Optional[str]:
        """Advance the fade. Returns the new state exactly once, on the
        frame a fade-out completes; otherwise returns None."""
        if self.fading_in:
            self.alpha -= self.speed
            if self.alpha <= 0:
                self.alpha = 0
                self.fading_in = False

        if self.fading_out:
            self.alpha += self.speed
            if self.alpha >= 255:
                self.alpha = 255
                self.fading_out = False
                self.fading_in = True
                return self.next_state

        return None

    def draw(self, screen: pygame.Surface) -> None:
        self.surface.set_alpha(self.alpha)
        screen.blit(self.surface, (0, 0))


def draw_health_bar(
    screen: pygame.Surface,
    health_images: list[pygame.Surface],
    health: int,
    pos: tuple[int, int] = (10, 50),
) -> None:
    screen.blit(health_images[health], pos)


def draw_score(
    screen: pygame.Surface,
    font: pygame.font.Font,
    score: int,
    pos: tuple[int, int] = (10, 10),
    color: tuple[int, int, int] = settings.SCORE_COLOR,
) -> None:
    text = font.render(f"Score: {score}", True, color)
    screen.blit(text, pos)
