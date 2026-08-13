"""Audio: loads and plays all sound effects and music via pygame.mixer.

Every audio operation is failure-tolerant. If the mixer is unavailable
(e.g. headless CI runs, machines without audio hardware) or a file fails
to load, a warning is printed and the game continues silently -- audio is
never fatal. See Assets/audio/SOURCES.md for asset origins and licenses.
"""

from __future__ import annotations

import os
import warnings

import pygame

import settings
from resource_path import resource_path


class AudioManager:
    """Owns every sound effect, the music loop, and the global mute state."""

    def __init__(self) -> None:
        self.available = False
        self.muted = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.music_loaded = False
        self._music_paused = False

        self._init_mixer()
        if self.available:
            self._load_sounds()
            self._load_music()

    # ------------------------------------------------------------------ #
    # Setup (all failures are non-fatal)
    # ------------------------------------------------------------------ #

    def _init_mixer(self) -> None:
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            self.available = pygame.mixer.get_init() is not None
        except pygame.error as exc:
            warnings.warn(f"[audio] mixer unavailable ({exc}); audio disabled")
            self.available = False

    def _load_sounds(self) -> None:
        for name, filename in settings.SFX_FILES.items():
            path = resource_path(os.path.join(settings.AUDIO_DIR, filename))
            try:
                sound = pygame.mixer.Sound(path)
            except (pygame.error, FileNotFoundError, OSError) as exc:
                warnings.warn(f"[audio] could not load '{filename}': {exc}")
                continue
            sound.set_volume(settings.SFX_VOLUME)
            self.sounds[name] = sound

    def _load_music(self) -> None:
        path = resource_path(os.path.join(settings.AUDIO_DIR, settings.MUSIC_FILE))
        try:
            pygame.mixer.music.load(path)
            self.music_loaded = True
        except (pygame.error, FileNotFoundError, OSError) as exc:
            warnings.warn(f"[audio] could not load music '{settings.MUSIC_FILE}': {exc}")

    # ------------------------------------------------------------------ #
    # Sound effects
    # ------------------------------------------------------------------ #

    def play(self, name: str) -> None:
        """Play a named SFX. No-op when audio is unavailable or muted."""
        if not self.available or self.muted:
            return
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    # ------------------------------------------------------------------ #
    # Music
    # ------------------------------------------------------------------ #

    def play_music(self) -> None:
        """Start the gameplay music loop, or unpause it if it was paused."""
        if not self.available or self.muted or not self.music_loaded:
            return
        if self._music_paused:
            pygame.mixer.music.unpause()
            self._music_paused = False
            return
        if not pygame.mixer.music.get_busy():
            try:
                pygame.mixer.music.set_volume(settings.MUSIC_VOLUME)
                pygame.mixer.music.play(-1)
            except pygame.error as exc:
                warnings.warn(f"[audio] could not start music: {exc}")

    def pause_music(self) -> None:
        if self.available and pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            self._music_paused = True

    def stop_music(self) -> None:
        if self.available:
            pygame.mixer.music.stop()
            self._music_paused = False

    def fade_out_music(self) -> None:
        if self.available:
            pygame.mixer.music.fadeout(500)

    # ------------------------------------------------------------------ #
    # Global mute
    # ------------------------------------------------------------------ #

    def set_muted(self, muted: bool) -> None:
        """Mute/unmute everything. Music already playing is silenced via
        its volume so the toggle takes effect immediately."""
        self.muted = muted
        if self.available:
            try:
                pygame.mixer.music.set_volume(0 if muted else settings.MUSIC_VOLUME)
            except pygame.error:
                pass

    def toggle_mute(self) -> bool:
        """Flip the mute state and return the new state."""
        self.set_muted(not self.muted)
        return self.muted
