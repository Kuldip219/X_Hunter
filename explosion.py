"""
A single explosion animation instance.

Used both for enemy-kill explosions (frame_delay=3 in the original code)
and the player's death explosion (frame_delay=5), which is why frame_delay
is a constructor parameter rather than a hardcoded constant.
"""

from __future__ import annotations

import pygame


class Explosion:
    def __init__(self, x: float, y: float, frame_delay: int) -> None:
        self.x = x
        self.y = y
        self.frame = 0
        self.timer = 0
        self.frame_delay = frame_delay

    def is_finished(self, total_frames: int) -> bool:
        return self.frame >= total_frames

    def draw(
        self,
        screen: pygame.Surface,
        frames: list[pygame.Surface],
        offset: tuple[int, int] = (0, 0),
    ) -> None:
        """Blit the current frame. Caller must check is_finished() first."""
        screen.blit(frames[self.frame], (self.x + offset[0], self.y + offset[1]))

    def advance(self) -> None:
        """Advance the internal timer, moving to the next frame when due."""
        self.timer += 1
        if self.timer >= self.frame_delay:
            self.frame += 1
            self.timer = 0
