"""Parallax scrolling backgrounds for gameplay and a static UI backdrop.

Two-layer parallax (far + near) scrolls vertically during gameplay, one
pair per level.  Each layer image is exactly one screen tall and tiles
seamlessly top-to-bottom: two copies are drawn stacked, the scroll
offset wraps when a copy fully exits the bottom.

A single static (non-scrolling) image is used behind all menu/UI screens.

All movement is dt-based (px/second), consistent with the rest of the
game's delta-time / fixed-timestep architecture.
"""

from __future__ import annotations

import pygame
import settings
from resource_path import resource_path


class _ScrollingLayer:
    """A single vertically-scrolling tile layer.

    The image is drawn twice stacked (offset by its height).  When the
    top copy scrolls completely past the bottom edge, the offset wraps
    by one tile height so the loop is seamless.
    """

    def __init__(self, image: pygame.Surface, speed_px_sec: int) -> None:
        self.image = image  # one screen-height tile
        self.speed = speed_px_sec  # px/s (scrolls downward)
        self.offset_y: float = 0.0  # current scroll offset in pixels

    def update(self, dt: float) -> None:
        """Advance the scroll offset by *dt* seconds.

        The offset decreases (goes negative) so that ``y = -offset_y``
        moves the tile downward on screen, matching the visual of the
        ship flying forward through space.
        """
        self.offset_y -= self.speed * dt
        h = self.image.get_height()
        if h > 0:
            self.offset_y %= h

    def draw(self, surface: pygame.Surface, shake: tuple[int, int] = (0, 0)) -> None:
        """Draw two stacked copies of the tile, scrolled by *offset_y*."""
        h = self.image.get_height()
        y = -self.offset_y + shake[1]
        surface.blit(self.image, (shake[0], y))
        surface.blit(self.image, (shake[0], y + h))

    def reset(self) -> None:
        """Reset scroll position to the top (fresh level start)."""
        self.offset_y = 0.0


class ParallaxBackground:
    """Two-layer parallax background for gameplay.

    Owns a far and near layer; both scroll downward independently.
    Swapped when the level changes.
    """

    def __init__(self) -> None:
        self.layers: list[_ScrollingLayer] = []
        self._current_level: int = -1  # force initial load

    def _load_level(self, level: int) -> None:
        """Load the layer pair for the given level index."""
        paths = settings.BG_LAYERS[level]
        speeds = [
            settings.BG_L1_FAR_SPEED if level == 0 else settings.BG_L2_FAR_SPEED,
            settings.BG_L1_NEAR_SPEED if level == 0 else settings.BG_L2_NEAR_SPEED,
        ]
        self.layers = []
        for path, speed in zip(paths, speeds):
            img = pygame.image.load(resource_path(path)).convert()
            self.layers.append(_ScrollingLayer(img, speed))
        self._current_level = level

    def set_level(self, level: int) -> None:
        """Switch to a different level's background pair.

        Resets scroll position to 0 for the new level.
        """
        if level != self._current_level:
            self._load_level(level)
            for layer in self.layers:
                layer.reset()

    def update(self, dt: float) -> None:
        """Advance all layers by *dt* seconds."""
        for layer in self.layers:
            layer.update(dt)

    def draw(self, surface: pygame.Surface, shake: tuple[int, int] = (0, 0)) -> None:
        """Draw both layers (far first, then near on top)."""
        for layer in self.layers:
            layer.draw(surface, shake)

    def reset(self) -> None:
        """Reset scroll positions (e.g. on restart)."""
        for layer in self.layers:
            layer.reset()

    @property
    def current_level(self) -> int:
        return self._current_level


class StaticBackground:
    """Non-scrolling backdrop for all menu/UI screens.

    Drawn once per frame at (0, 0); no update logic needed.
    """

    def __init__(self) -> None:
        self.image: pygame.Surface | None = None

    def load(self) -> None:
        """Load the static UI background image."""
        try:
            self.image = pygame.image.load(resource_path(settings.BG_UI_PATH)).convert()
        except (pygame.error, FileNotFoundError):
            # Fallback: solid dark color if image is missing.
            self.image = pygame.Surface((settings.WIDTH, settings.HEIGHT))
            self.image.fill(settings.BLACK)

    def draw(self, surface: pygame.Surface) -> None:
        """Blit the static background at (0, 0)."""
        if self.image is not None:
            surface.blit(self.image, (0, 0))
