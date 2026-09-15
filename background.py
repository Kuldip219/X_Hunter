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


def _fit_to_screen(image: pygame.Surface) -> pygame.Surface:
    """Return *image* rescaled to exactly one screen (WIDTH x HEIGHT).

    Used for the static UI backdrop, which is drawn once and not tiled, so it
    gets a plain (border-clamped) rescale.

    Returns the original surface unchanged when it already matches, so this
    is a no-op at the authored resolution.
    """
    target = (settings.WIDTH, settings.HEIGHT)
    if image.get_size() == target:
        return image
    try:
        return pygame.transform.smoothscale(image, target)
    except (pygame.error, ValueError):
        return pygame.transform.scale(image, target)


def _fit_tile_to_screen(image: pygame.Surface) -> pygame.Surface:
    """Rescale a vertically TILING background tile to one screen.

    A plain rescale filters each edge against clamped border pixels, which
    re-introduces a faint seam where the tile wraps (measured: the wrap
    discontinuity roughly doubled on the smooth l2_far layer). Because the
    tile is seamless, its top and bottom edges are continuous content, so we
    can give the filter the real neighbours: stack three copies, rescale the
    stack, and keep the MIDDLE copy. Both of that copy's edges are then
    interior pixels filtered against the actual wrap-around content, and the
    result is uniformly scaled (WIDTH/HEIGHT preserves the authored aspect
    ratio) so the tiling still works and the two stacked copies still cover
    the whole screen.

    Measured at 768x1024: every layer's wrap discontinuity dropped by >40%,
    leaving all four gameplay layers with a seam step no larger than 0.81x an
    ordinary row-to-row step (i.e. no discontinuity at all as far as the eye
    is concerned).

    Returns the original surface unchanged when it already matches, so this
    is a no-op at the authored resolution.
    """
    target = (settings.WIDTH, settings.HEIGHT)
    if image.get_size() == target:
        return image

    w, h = image.get_size()
    tw, th = target
    stack = pygame.Surface((w, h * 3))
    for i in range(3):
        stack.blit(image, (0, i * h))
    try:
        stack = pygame.transform.smoothscale(stack, (tw, th * 3))
    except (pygame.error, ValueError):
        stack = pygame.transform.scale(stack, (tw, th * 3))
    tile = pygame.Surface(target)
    tile.blit(stack, (0, -th))
    return tile


class _ScrollingLayer:
    """A single vertically-scrolling tile layer.

    The image is one screen tall (rescaled to WIDTH x HEIGHT at load time,
    whatever the source art's size) and is drawn twice stacked (offset by
    its height).  When the top copy scrolls completely past the bottom
    edge, the offset wraps by one tile height so the loop is seamless.
    """

    def __init__(self, image: pygame.Surface, speed_px_sec: int) -> None:
        self.image = _fit_tile_to_screen(image)  # exactly one screen-tall tile
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
        # Per-layer speeds come from settings (one (far, near) pair per
        # level) so adding a level never needs a new branch here.
        speeds = settings.BG_LAYER_SPEEDS[level]
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
        """Load the static UI background image, fitted to the screen."""
        try:
            self.image = _fit_to_screen(
                pygame.image.load(resource_path(settings.BG_UI_PATH)).convert()
            )
        except (pygame.error, FileNotFoundError):
            # Fallback: solid dark color if image is missing.
            self.image = pygame.Surface((settings.WIDTH, settings.HEIGHT))
            self.image.fill(settings.BLACK)

    def draw(self, surface: pygame.Surface) -> None:
        """Blit the static background at (0, 0)."""
        if self.image is not None:
            surface.blit(self.image, (0, 0))
