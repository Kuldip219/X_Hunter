"""UserSettings persistence: round-trip, defensive loading (missing /
corrupted / wrong-shape files never raise), clamping, and atomic writes."""

import json

import pygame

import settings
from helpers import KeyState
from player import Player
from settings_store import UserSettings


def test_defaults_match_out_of_the_box_volumes(tmp_path):
    store = UserSettings.load(str(tmp_path / "settings.json"))
    assert store.music_volume == settings.MUSIC_VOLUME
    assert store.sfx_volume == settings.SFX_VOLUME


def test_save_load_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    store = UserSettings.load(str(path))
    store.set_music_volume(0.9)
    store.set_sfx_volume(0.1)
    store.save()

    fresh = UserSettings.load(str(path))
    assert fresh.music_volume == 0.9
    assert fresh.sfx_volume == 0.1


def test_missing_file_falls_back_to_defaults(tmp_path):
    store = UserSettings.load(str(tmp_path / "nope.json"))
    assert store.music_volume == settings.MUSIC_VOLUME
    assert store.sfx_volume == settings.SFX_VOLUME


def test_corrupted_json_falls_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ not valid json !!!", encoding="utf-8")
    store = UserSettings.load(str(path))
    assert store.music_volume == settings.MUSIC_VOLUME
    assert store.sfx_volume == settings.SFX_VOLUME


def test_wrong_shape_falls_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(["music_volume", 0.5]), encoding="utf-8")
    assert UserSettings.load(str(path)).music_volume == settings.MUSIC_VOLUME

    path.write_text(json.dumps({"music_volume": "loud"}), encoding="utf-8")
    store = UserSettings.load(str(path))
    assert store.music_volume == settings.MUSIC_VOLUME  # non-numeric -> default

    path.write_text(json.dumps({"music_volume": True, "sfx_volume": 0.4}), encoding="utf-8")
    store = UserSettings.load(str(path))
    # Booleans are rejected explicitly: True must not become volume 1.0.
    assert store.music_volume == settings.MUSIC_VOLUME
    assert store.sfx_volume == 0.4


def test_legacy_file_without_new_actions_is_filled_from_defaults(tmp_path):
    """A settings.json written before an action existed must not leave that
    action unbound.

    The repo's own settings.json is exactly this shape: it predates
    move_up/move_down, so it carries only the original six actions. The
    player reads every binding by name each frame, so a missing key here
    would be a KeyError the moment the player moved.
    """
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "music_volume": 0.5,
                "sfx_volume": 0.5,
                "key_bindings": {"fire": pygame.K_j, "move_left": pygame.K_a},
            }
        ),
        encoding="utf-8",
    )
    store = UserSettings.load(str(path))
    # Explicit values are kept...
    assert store.key_bindings["fire"] == pygame.K_j
    assert store.key_bindings["move_left"] == pygame.K_a
    # ...and every action the game reads exists, at its default when absent.
    for action, default in settings.DEFAULT_KEY_BINDINGS.items():
        assert action in store.key_bindings, f"{action} left unbound"
        if action not in ("fire", "move_left"):
            assert store.key_bindings[action] == default, action
    assert store.key_bindings["move_up"] == settings.DEFAULT_KEY_BINDINGS["move_up"]
    assert store.key_bindings["move_down"] == settings.DEFAULT_KEY_BINDINGS["move_down"]


def test_player_moves_using_bindings_loaded_from_a_legacy_file(tmp_path):
    """End-to-end version of the same guarantee: a Player handed the bindings
    loaded from a legacy file still moves on every axis (no KeyError)."""
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"key_bindings": {"fire": pygame.K_j}}), encoding="utf-8")
    bindings = UserSettings.load(str(path)).key_bindings

    up = Player(100, 600, bindings=bindings)
    up.handle_input(KeyState(pygame.K_UP), 1 / 60)
    assert up.y < 600

    down = Player(100, 600, bindings=bindings)
    down.handle_input(KeyState(pygame.K_DOWN), 1 / 60)
    assert down.y > 600

    left = Player(100, 600, bindings=bindings)
    left.handle_input(KeyState(pygame.K_LEFT), 1 / 60)
    assert left.x < 100

    right = Player(100, 600, bindings=bindings)
    right.handle_input(KeyState(pygame.K_RIGHT), 1 / 60)
    assert right.x > 100


def test_values_clamped_on_load(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"music_volume": 7.0, "sfx_volume": -3.0}), encoding="utf-8"
    )
    store = UserSettings.load(str(path))
    assert store.music_volume == 1.0
    assert store.sfx_volume == 0.0


def test_setters_clamp_to_unit_interval(tmp_path):
    store = UserSettings.load(str(tmp_path / "settings.json"))
    assert store.set_music_volume(1.5) == 1.0
    assert store.set_music_volume(-0.5) == 0.0
    assert store.set_sfx_volume(1.5) == 1.0
    assert store.set_sfx_volume(-0.5) == 0.0


def test_save_is_atomic(tmp_path):
    path = tmp_path / "settings.json"
    store = UserSettings.load(str(path))
    store.set_music_volume(0.8)
    store.save()
    # The write went through a temp file + os.replace: no .tmp leftover.
    assert path.exists()
    assert not (tmp_path / "settings.json.tmp").exists()
    assert json.loads(path.read_text(encoding="utf-8"))["music_volume"] == 0.8


def test_unwritable_location_does_not_raise(tmp_path):
    store = UserSettings.load(str(tmp_path / "missing" / "settings.json"))
    store.set_music_volume(0.6)
    store.save()  # parent dir does not exist -> logged, silent, no raise
    assert store.music_volume == 0.6  # value still kept in memory
