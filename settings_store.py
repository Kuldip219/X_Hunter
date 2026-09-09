"""Persistent user settings (audio volumes + key bindings).

Stored in a small JSON file (settings.SETTINGS_FILE, a sibling of
highscores.json in the game's working directory - the project root when
run from source, the folder the game is launched from when packaged) so
volume choices and rebound keys survive restarts.

Every read/write is defensive, mirroring highscores.py: a missing file,
corrupted JSON, or an unwritable location falls back to the sane defaults
(settings.SFX_VOLUME / settings.MUSIC_VOLUME / settings.DEFAULT_KEY_BINDINGS)
or silently drops the write (logged at warning level) - user settings never
crash the game.

File format: a JSON object
{"music_volume": float, "sfx_volume": float, "key_bindings": {action: keycode}}
Volumes are clamped to [0.0, 1.0]; key bindings are validated per-action
against the known action ids and fall back per-action to defaults when a
stored value is missing or not an integer keycode, so a hand-edited file
can never produce an invalid binding.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

import pygame

import settings

logger = logging.getLogger(__name__)


class UserSettings:
    """In-memory user settings with JSON persistence behind it."""

    def __init__(
        self,
        path: str,
        music_volume: Optional[float] = None,
        sfx_volume: Optional[float] = None,
        key_bindings: Optional[dict[str, int]] = None,
    ) -> None:
        self.path = path
        # Defaults match the out-of-the-box game behavior.
        self.music_volume = settings.MUSIC_VOLUME if music_volume is None else music_volume
        self.sfx_volume = settings.SFX_VOLUME if sfx_volume is None else sfx_volume
        self.music_volume = self._clamp(self.music_volume)
        self.sfx_volume = self._clamp(self.sfx_volume)
        # Copy the defaults so later mutations never leak into the module.
        self.key_bindings: dict[str, int] = dict(settings.DEFAULT_KEY_BINDINGS)
        if key_bindings is not None:
            for action, default in settings.DEFAULT_KEY_BINDINGS.items():
                value = key_bindings.get(action)
                if isinstance(value, int) and not isinstance(value, bool):
                    self.key_bindings[action] = value

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
        key_bindings: Optional[dict[str, int]] = None
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
                stored = raw.get("key_bindings")
                if isinstance(stored, dict):
                    key_bindings = {
                        action: value
                        for action, value in stored.items()
                        if action in settings.DEFAULT_KEY_BINDINGS
                        and isinstance(value, int)
                        and not isinstance(value, bool)
                    }
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("[settings] could not load %s (%s); using defaults", path, exc)
        return cls(
            path,
            music_volume=music_volume,
            sfx_volume=sfx_volume,
            key_bindings=key_bindings,
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

    def key_for(self, action: str) -> int:
        """The pygame keycode currently bound to `action`."""
        return self.key_bindings.get(action, settings.DEFAULT_KEY_BINDINGS[action])

    def rebind(self, action: str, key: int) -> bool:
        """Bind `action` to `key`, swapping with any other action currently
        bound to `key` so no action ever ends up unbound. Returns True if a
        change was applied.

        ESC is reserved for non-ESC-default actions: it cancels the capture
        and can never become a binding. For actions that legitimately default
        to ESC (back, pause — see settings.ESC_DEFAULT_ACTIONS), ESC is
        allowed as a capture so the user can return to the default after
        rebinding it away. Rebinding the SAME action to the same key is a
        no-op (returns False) so the UI can drop the capture without a bogus
        persistence write."""
        if action not in settings.REBINDABLE_ACTIONS:
            return False
        if key in settings.RESERVED_KEYS:
            if action not in settings.ESC_DEFAULT_ACTIONS:
                return False
        old = self.key_bindings.get(action)
        if old == key:
            return False
        # Find the other action currently bound to `key` and swap them, so
        # the key the user pressed never leaves an action unbound.
        owner = None
        for act, k in self.key_bindings.items():
            if act != action and k == key:
                owner = act
                break
        if owner is not None:
            self.key_bindings[owner] = old
        self.key_bindings[action] = key
        return True

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
                        "key_bindings": self.key_bindings,
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
