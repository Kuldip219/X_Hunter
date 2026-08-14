"""Persistent user settings (currently: audio volumes).

Stored in a small JSON file (settings.SETTINGS_FILE, a sibling of
highscores.json in the game's working directory - the project root when
run from source, the folder the game is launched from when packaged) so
volume choices survive restarts.

Every read/write is defensive, mirroring highscores.py: a missing file,
corrupted JSON, or an unwritable location falls back to the sane defaults
(settings.SFX_VOLUME / settings.MUSIC_VOLUME) or silently drops the write
(logged at warning level) - user settings never crash the game.

File format: a JSON object {"music_volume": float, "sfx_volume": float},
each clamped to [0.0, 1.0]. Values outside that range are clamped on load
so a hand-edited file can never drive the mixer out of bounds.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

import settings

logger = logging.getLogger(__name__)


class UserSettings:
    """In-memory user settings with JSON persistence behind it."""

    def __init__(
        self,
        path: str,
        music_volume: Optional[float] = None,
        sfx_volume: Optional[float] = None,
    ) -> None:
        self.path = path
        # Defaults match the out-of-the-box game behavior.
        self.music_volume = settings.MUSIC_VOLUME if music_volume is None else music_volume
        self.sfx_volume = settings.SFX_VOLUME if sfx_volume is None else sfx_volume
        self.music_volume = self._clamp(self.music_volume)
        self.sfx_volume = self._clamp(self.sfx_volume)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #

    @classmethod
    def load(cls, path: Optional[str] = None) -> "UserSettings":
        """Load settings from `path`, degrading to defaults on any error
        (missing file, corrupted JSON, unexpected shape). Never raises.

        The path is read at call time (not a baked-in default argument), so
        callers/tests can point the store anywhere before loading."""
        if path is None:
            path = settings.SETTINGS_FILE
        music_volume: Optional[float] = None
        sfx_volume: Optional[float] = None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if isinstance(raw, dict):
                for attr in ("music_volume", "sfx_volume"):
                    value = raw.get(attr)
                    # Booleans are ints in Python; reject them explicitly so a
                    # hand-edited `true` cannot become a volume of 1.0.
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        if attr == "music_volume":
                            music_volume = float(value)
                        else:
                            sfx_volume = float(value)
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("[settings] could not load %s (%s); using defaults", path, exc)
        return cls(
            path,
            music_volume=music_volume,
            sfx_volume=sfx_volume,
        )

    # ------------------------------------------------------------------ #
    # Mutation
    # ------------------------------------------------------------------ #

    def set_music_volume(self, value: float) -> float:
        """Set and clamp the music volume; returns the stored value."""
        self.music_volume = self._clamp(value)
        return self.music_volume

    def set_sfx_volume(self, value: float) -> float:
        """Set and clamp the SFX volume; returns the stored value."""
        self.sfx_volume = self._clamp(value)
        return self.sfx_volume

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def save(self) -> None:
        """Write the current settings to disk, atomically (temp file +
        rename). Failures (read-only location, missing directory, ...) are
        logged and otherwise silent - never fatal to the game."""
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "music_volume": self.music_volume,
                        "sfx_volume": self.sfx_volume,
                    },
                    fh,
                    indent=2,
                )
            os.replace(tmp, self.path)
        except (OSError, TypeError, ValueError) as exc:
            logger.warning(
                "[settings] could not write %s (%s); kept in memory only",
                self.path,
                exc,
            )
