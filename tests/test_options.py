"""Options screen: volume sliders (click/drag, live audio, persistence on
release), mute independence, load-and-apply on launch, the read-only
controls reference, and navigation regression (options -> high_scores ->
options -> menu)."""

import json

import pygame
import pytest

import settings
from game import Game
from helpers import pump_fade


def _enter_options(game):
    game._handle_mouse_click(game.main_menu.options_rect.center)
    pump_fade(game)
    assert game.state == "options"
    return game.options_screen


# ---------------------------------------------------------------------- #
# Sliders: interaction + clamping
# ---------------------------------------------------------------------- #


def test_clicking_track_jumps_to_position(game):
    os_ = _enter_options(game)
    track = os_.slider_tracks["music"]

    os_.handle_mouse_down((track.left, track.centery))
    os_.handle_mouse_up((track.left, track.centery))
    assert game.user_settings.music_volume == 0.0
    assert game.audio.music_volume == 0.0

    # right-1: pygame rects are right-edge exclusive, so an exact right-edge
    # click is (correctly) treated as outside the slider; the pixel just
    # inside lands at 219/220 of the track.
    os_.handle_mouse_down((track.right - 1, track.centery))
    os_.handle_mouse_up((track.right - 1, track.centery))
    assert game.user_settings.music_volume == pytest.approx(1.0, abs=0.01)
    assert game.audio.music_volume == pytest.approx(1.0, abs=0.01)


def test_clicking_track_center_is_halfway(game):
    os_ = _enter_options(game)
    track = os_.slider_tracks["music"]
    os_.handle_mouse_down((track.centerx, track.centery))
    assert 0.45 <= game.user_settings.music_volume <= 0.55


def test_dragging_slider_updates_live_and_persists_on_release(tmp_path, game):
    os_ = _enter_options(game)
    track = os_.slider_tracks["music"]

    os_.handle_mouse_down((track.left + track.width // 2, track.centery))
    os_.handle_mouse_motion((track.right - 1, track.centery))
    assert game.audio.music_volume > 0.9  # applied live during the drag

    os_.handle_mouse_up((track.right - 1, track.centery))
    assert os_._dragging is None
    # Persisted once on release, to the file the conftest fixture pointed at.
    saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert saved["music_volume"] > 0.9


def test_slider_values_clamped_to_unit_interval(game):
    # The mouse path can only produce in-track fractions (a click far outside
    # the slider does not grab it), so the clamp is defensive - exercised
    # through the same _apply_value used by every slider update.
    os_ = _enter_options(game)
    os_._apply_value("music", 1.5)
    assert game.user_settings.music_volume == 1.0
    assert game.audio.music_volume == 1.0
    os_._apply_value("music", -0.5)
    assert game.user_settings.music_volume == 0.0
    assert game.audio.music_volume == 0.0


def test_sfx_slider_reaches_audio_manager(game):
    os_ = _enter_options(game)
    track = os_.slider_tracks["sfx"]
    os_.handle_mouse_down((track.right - 1, track.centery))
    assert game.user_settings.sfx_volume == pytest.approx(1.0, abs=0.01)
    assert game.audio.sfx_volume == pytest.approx(1.0, abs=0.01)
    os_.handle_mouse_up((track.right - 1, track.centery))


def test_click_off_sliders_does_not_grab(game):
    os_ = _enter_options(game)
    # The HIGH SCORES banner area is a button, not a slider.
    assert os_.handle_mouse_down((10, 10)) is False


def test_slider_drag_via_pygame_event_loop(game):
    os_ = _enter_options(game)
    track = os_.slider_tracks["music"]
    # Real events through Game._handle_events: down on the track, motion to
    # the far right, release.
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(track.centerx, track.centery)))
    pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=(track.right, track.centery)))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(track.right, track.centery)))
    game._handle_events((track.centerx, track.centery))
    assert game.audio.music_volume > 0.9
    assert os_._dragging is None


def test_drag_state_cleared_on_state_change(game):
    os_ = _enter_options(game)
    track = os_.slider_tracks["music"]
    os_.handle_mouse_down((track.centerx, track.centery))
    assert os_._dragging == "music"
    game._change_state("menu")  # e.g. ESC mid-drag; a state change must clear it
    assert os_._dragging is None


# ---------------------------------------------------------------------- #
# Mute independence
# ---------------------------------------------------------------------- #


def test_mute_does_not_alter_saved_volumes(game):
    game.user_settings.set_music_volume(0.7)
    game.user_settings.set_sfx_volume(0.3)
    game.audio.set_music_volume(0.7)
    game.audio.set_sfx_volume(0.3)

    game.audio.set_muted(True)
    assert game.user_settings.music_volume == 0.7
    assert game.user_settings.sfx_volume == 0.3
    assert game.audio.music_volume == 0.7  # preserved while muted

    game.audio.set_muted(False)
    assert game.audio.music_volume == 0.7  # restored exactly


def test_mute_key_toggle_keeps_slider_values(game):
    game.user_settings.set_music_volume(0.66)
    game.audio.set_music_volume(0.66)
    game._handle_keydown(pygame.K_m)
    assert game.audio.muted
    game._handle_keydown(pygame.K_m)
    assert not game.audio.muted
    assert game.user_settings.music_volume == 0.66
    assert game.audio.music_volume == 0.66


# ---------------------------------------------------------------------- #
# Load-and-apply on launch
# ---------------------------------------------------------------------- #


def test_persisted_volumes_applied_on_launch(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"music_volume": 0.9, "sfx_volume": 0.2}), encoding="utf-8"
    )
    monkeypatch.setattr(settings, "SETTINGS_FILE", str(path))
    monkeypatch.setattr(settings, "HIGHSCORE_FILE", str(tmp_path / "hs.json"))
    g = Game()
    try:
        assert g.audio.music_volume == 0.9
        assert g.audio.sfx_volume == 0.2
    finally:
        pygame.quit()


# ---------------------------------------------------------------------- #
# Controls reference + rendering smoke
# ---------------------------------------------------------------------- #


def test_controls_reference_matches_real_bindings():
    rows = dict(settings.CONTROLS)
    # Sourced from the real input handling: K_LEFT/K_RIGHT (player.py),
    # K_SPACE held (game.py), K_m and K_ESCAPE (game.py _handle_keydown).
    assert rows["Move"] == "LEFT / RIGHT"
    assert rows["Fire (hold)"] == "SPACE"
    assert rows["Pause / Resume"] == "ESC"
    assert rows["Mute / Unmute"] == "M"
    assert rows["Back (menus)"] == "ESC"


def test_options_screen_draws_without_crashing(game):
    os_ = _enter_options(game)
    game._update_and_draw((0, 0))  # render the full screen (sliders + controls)
    assert game.state == "options"
    assert game.user_settings.music_volume == settings.MUSIC_VOLUME  # untouched


# ---------------------------------------------------------------------- #
# Navigation regression
# ---------------------------------------------------------------------- #


def test_options_to_high_scores_and_back(game):
    os_ = _enter_options(game)
    game._handle_mouse_click(os_.high_scores_rect.center)
    pump_fade(game)
    assert game.state == "high_scores"
    game._handle_mouse_click(game.high_scores_menu.back_rect.center)
    pump_fade(game)
    assert game.state == "options"


def test_esc_from_options_returns_to_menu(game):
    _enter_options(game)
    game._handle_keydown(pygame.K_ESCAPE)
    pump_fade(game)
    assert game.state == "menu"


def test_back_button_returns_to_menu(game):
    os_ = _enter_options(game)
    game._handle_mouse_click(os_.back_rect.center)
    assert game.fade.next_state == "menu"
    pump_fade(game)
    assert game.state == "menu"


def test_back_button_uses_same_transition_as_esc(game):
    os_ = _enter_options(game)
    game._handle_mouse_click(os_.back_rect.center)
    # Identical fade-out to the ESC path: same target state, same mechanism.
    assert game.fade.fading_out
    assert game.fade.next_state == "menu"
    assert game.state == "options"  # switch happens only when the fade completes
