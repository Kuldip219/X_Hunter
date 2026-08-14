"""The dedicated controls (keybinds) screen: reachable from the Options
screen via the new CONTROLS button, returns to Options on BACK/ESC, shows
the real bindings from settings.CONTROLS, and uses the controls.png banner
asset (with the standard font fallback when the file is missing)."""

import pygame

import settings
from helpers import pump_fade


def _enter_options(game):
    game._handle_mouse_click(game.main_menu.options_rect.center)
    pump_fade(game)
    assert game.state == "options"
    return game.options_screen


def _enter_controls(game):
    os_ = _enter_options(game)
    game._handle_mouse_click(os_.controls_rect.center)
    assert game.fade.next_state == "controls"
    pump_fade(game)
    assert game.state == "controls"


# ---------------------------------------------------------------------- #
# Navigation
# ---------------------------------------------------------------------- #


def test_controls_reachable_from_options(game):
    _enter_controls(game)


def test_controls_back_button_returns_to_options(game):
    _enter_controls(game)
    game._handle_mouse_click(game.controls_screen.back_rect.center)
    assert game.fade.next_state == "options"
    pump_fade(game)
    assert game.state == "options"


def test_controls_esc_returns_to_options(game):
    _enter_controls(game)
    game._handle_keydown(pygame.K_ESCAPE)
    pump_fade(game)
    assert game.state == "options"


def test_controls_to_options_to_menu_loop(game):
    _enter_controls(game)
    game._handle_keydown(pygame.K_ESCAPE)
    pump_fade(game)
    assert game.state == "options"
    game._handle_keydown(pygame.K_ESCAPE)
    pump_fade(game)
    assert game.state == "menu"


# ---------------------------------------------------------------------- #
# Content
# ---------------------------------------------------------------------- #


def test_controls_screen_content_matches_real_bindings(game):
    """The screen renders exactly the bindings from settings.CONTROLS (the
    source of truth pulled from the real input-handling code)."""
    screen = game.controls_screen
    assert len(screen.row_ys) == len(settings.CONTROLS)
    rows = dict(settings.CONTROLS)
    assert rows["Move"] == "LEFT / RIGHT"
    assert rows["Fire (hold)"] == "SPACE"
    assert rows["Pause / Resume"] == "ESC"
    assert rows["Mute / Unmute"] == "M"
    assert rows["Back (menus)"] == "ESC"
    assert rows["Restart"] == "RESTART button"
    # Renders without crashing.
    _enter_controls(game)
    game._update_and_draw((0, 0))
    assert game.state == "controls"


def test_controls_rows_single_column_generous_spacing(game):
    """The full-screen layout uses one binding per row with the comfortable
    CONTROLS_ROW_GAP between rows (no 2x3 grid needed anymore)."""
    ys = game.controls_screen.row_ys
    assert len(ys) == len(settings.CONTROLS)
    for a, b in zip(ys, ys[1:]):
        assert b - a == settings.CONTROLS_ROW_GAP


# ---------------------------------------------------------------------- #
# Asset loading
# ---------------------------------------------------------------------- #


def test_controls_banner_loads_and_preserves_aspect_ratio(game):
    # controls.png is 1168x273; it must fit the 250x80 footprint without
    # distortion.
    w, h = game.assets.controls_img.get_size()
    assert w <= settings.CONTROLS_IMG_SIZE[0] and h <= settings.CONTROLS_IMG_SIZE[1]
    assert abs(w / h - 1168 / 273) < 0.05  # pixel truncation allows ~3%


def test_controls_banner_falls_back_when_file_missing(monkeypatch, game):
    from assets import _load_menu_banner

    def boom(*args, **kwargs):
        raise pygame.error("file not found")

    monkeypatch.setattr(pygame.image, "load", boom)
    surf = _load_menu_banner(
        "Assets/controls.png", settings.CONTROLS_IMG_SIZE, game.assets.font, "CONTROLS"
    )
    assert surf.get_size() == settings.CONTROLS_IMG_SIZE


def test_options_controls_button_uses_image_asset(game):
    # The Options CONTROLS button is an image button (controls_img), not a
    # font-rendered one - same loading helper as score.png/back.png.
    assert game.options_screen.controls_rect.width == game.assets.controls_img.get_width()
    assert game.assets.controls_img is not None
