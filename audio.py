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
    """Owns every sound effect, the music loop, and the global mute state.

    Volumes are instance state (`music_volume` / `sfx_volume`) so the
    Options screen sliders can adjust them live. If a `settings_store`
    (a UserSettings object) is passed in, its persisted volumes are applied
    at construction - before any audio plays. Mute is independent of the
    volumes: it silences output without modifying the stored values, so
    unmuting restores exactly where the sliders were.
    """

    def __init__(self, settings_store=None) -> None:
        self.available = False
        self.muted = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.music_loaded = False
        self._music_paused = False
        # Current effective volumes, seeded from the persisted settings (or
        # the out-of-the-box defaults when no store / no file is present).
        if settings_store is not None:
            self.music_volume = settings_store.music_volume
            self.sfx_volume = settings_store.sfx_volume
        else:
            self.music_volume = settings.MUSIC_VOLUME
            self.sfx_volume = settings.SFX_VOLUME

        self._init_mixer()
        if self.available:
            self._load_sounds()
            self._load_music()
            # Apply persisted volumes now, before anything can play.
            self.set_sfx_volume(self.sfx_volume)
            self.set_music_volume(self.music_volume)

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
            sound.set_volume(self.sfx_volume)
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
    # Volume control (live, from the Options screen sliders)
    # ------------------------------------------------------------------ #

    def set_music_volume(self, value: float) -> None:
        """Set the music volume (0.0-1.0), clamped. Applied immediately to
        currently-playing music (pygame.mixer.music.set_volume is live).
        While muted the mixer stays at 0 but `music_volume` is preserved,
        so unmuting restores exactly this value."""
        self.music_volume = max(0.0, min(1.0, float(value)))
        if self.available:
            try:
                pygame.mixer.music.set_volume(0 if self.muted else self.music_volume)
            except pygame.error:
                pass

    def set_sfx_volume(self, value: float) -> None:
        """Set the SFX volume (0.0-1.0), clamped. Applied to every loaded
        Sound object; pygame's Sound.set_volume is live, so sounds already
        playing are adjusted immediately, not just on the next play()."""
        self.sfx_volume = max(0.0, min(1.0, float(value)))
        if self.available:
            for sound in self.sounds.values():
                try:
                    sound.set_volume(self.sfx_volume)
                except pygame.error:
                    pass

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
                pygame.mixer.music.set_volume(self.music_volume)
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
        """Mute/unmute everything. Music already playing is silenced via its
        volume so the toggle takes effect immediately. Muting does NOT change
        `music_volume` / `sfx_volume` - the slider values are preserved and
        restored on unmute."""
        self.muted = muted
        self.set_music_volume(self.music_volume)  # applies 0 while muted

    def toggle_mute(self) -> bool:
        """Flip the mute state and return the new state."""
        self.set_muted(not self.muted)
        return self.muted
