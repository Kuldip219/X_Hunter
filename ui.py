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


class FadeText:
    """Reusable centered text that fades in, holds, then fades out.

    Usage::
        ft = FadeText("Phase 1")
        # in the game loop, while ft.active:
        ft.update()  # advance the animation
        ft.draw(screen, font)  # render if visible
        if not ft.active: ...  # move to next phase

    The text is centered on screen. update() and draw() are frame-based
    (FADE_TEXT_SPEED alpha steps per frame) to match the existing
    FadeTransition pattern.
    """

    def __init__(self, text: str) -> None:
        self.text = text
        self.alpha = 0
        self.phase = "in"  # "in" -> "hold" -> "out" -> done
        self.hold_counter = 0
        self.active = True

    def reset(self, text: str | None = None) -> None:
        """Restart the animation, optionally with new text."""
        if text is not None:
            self.text = text
        self.alpha = 0
        self.phase = "in"
        self.hold_counter = 0
        self.active = True

    def update(self) -> None:
        """Advance one frame. Call once per rendered frame while active."""
        if not self.active:
            return
        if self.phase == "in":
            self.alpha = min(255, self.alpha + settings.FADE_TEXT_SPEED)
            if self.alpha >= 255:
                self.phase = "hold"
                self.hold_counter = 0
        elif self.phase == "hold":
            self.hold_counter += 1
            # Convert hold seconds to frames at the game's target FPS.
            hold_frames = int(settings.FADE_TEXT_HOLD_SECONDS * settings.FPS)
            if self.hold_counter >= hold_frames:
                self.phase = "out"
        elif self.phase == "out":
            self.alpha = max(0, self.alpha - settings.FADE_TEXT_SPEED)
            if self.alpha <= 0:
                self.active = False

    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        """Draw the text if visible (alpha > 0)."""
        if not self.active or self.alpha <= 0:
            return
        text_surf = font.render(self.text, True, settings.FADE_TEXT_COLOR)
        text_surf.set_alpha(self.alpha)
        rect = text_surf.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2))
        screen.blit(text_surf, rect)
