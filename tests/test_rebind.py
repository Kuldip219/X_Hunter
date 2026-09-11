"""Editable key bindings on the Controls screen.

Covers the full contract:
- the EDIT button (edit.png) enters edit mode and every rebindable row
  becomes selectable,
- selecting a row enters an "awaiting input" state that captures the next
  keypress as the new binding (swap-with-conflict, so no action is ever
  unbound),
- ESC cancels a pending capture and exits edit mode without rebinding,
- ESC can never be bound to anything,
- the restart row (button-only action) is displayed but never rebindable,
- rebinds persist through the shared UserSettings store and take effect
  in-game immediately (fire/move/mute read the live bindings).
"""

import pygame

import settings
from helpers import pump_fade

from settings_store import UserSettings


def _enter_options(game):
    game._handle_mouse_click(game.main_menu.options_rect.center)
    pump_fade(game)
    assert game.state == "options"
    return game.options_screen


def _enter_controls(game):
    os_ = _enter_options(game)
    game._handle_mouse_click(os_.controls_rect.center)
    pump_fade(game)
    assert game.state == "controls"


def _row_index(action: str) -> int:
    return [a for a, _l in settings.CONTROLS].index(action)


def _enter_edit_mode(game):
    _enter_controls(game)
    screen = game.controls_screen
    game._handle_mouse_click(screen.edit_rect.center)
    assert screen.edit_mode
    return screen


# ---------------------------------------------------------------------- #
# Asset sizing
# ---------------------------------------------------------------------- #


def test_edit_button_same_size_as_back_button(game):
    """The edit button and back button render at identical canvas sizes.
    edit.png is trimmed to its visible content and scaled to match
    back_img's visible content width, on a canvas the same size as back_img."""
    ew, eh = game.assets.edit_img.get_size()
    bw, bh = game.assets.back_img.get_size()
    assert ew == bw
    assert eh == bh
    # The rendered canvas matches the documented footprint constant.
    assert (ew, eh) == settings.EDIT_IMG_SIZE
    # Actual rects on the Controls screen share the same dimensions.
    screen = _enter_edit_mode(game)
    assert screen.edit_rect.width == screen.back_rect.width
    assert screen.edit_rect.height == screen.back_rect.height


def test_edit_button_visible_content_matches_back_button(game):
    """Matching declared canvas sizes is NOT enough - edit.png carries more
    transparent padding than back.png, so equal bounding boxes still produced a
    visibly smaller button (regression: ~202x29 vs ~241x48 visible pixels).
    Assert on the TRIMMED visible content, not the raw surface size."""
    edit = game.assets.edit_img.get_bounding_rect(1)
    back = game.assets.back_img.get_bounding_rect(1)

    # The visible artwork widths now line up (within a rounding pixel).
    assert abs(edit.width - back.width) <= 2
    # And edit is no longer a thin sliver vertically (its artwork is a touch
    # taller than back's by nature, but must be in the same ballpark).
    assert edit.height >= back.height * 0.9
    # Both fill a comparable fraction of their (identically sized) canvases.
    canvas_frac = edit.width * edit.height / (back.width * back.height)
    assert 0.7 <= canvas_frac <= 1.4


def test_edit_button_matches_back_content_width_when_file_missing(monkeypatch, game):
    """The edit banner helper still degrades to a font-rendered button the
    same size as back_img when edit.png is unreadable."""
    from assets import _load_menu_banner_matching_content

    def boom(*args, **kwargs):
        raise pygame.error("file not found")

    monkeypatch.setattr(pygame.image, "load", boom)
    surface = _load_menu_banner_matching_content(
        "Assets/edit.png", game.assets.back_img, game.assets.font, "EDIT"
    )
    assert surface.get_size() == game.assets.back_img.get_size()


# ---------------------------------------------------------------------- #
# Edit mode entry / exit
# ---------------------------------------------------------------------- #


def test_edit_button_enters_edit_mode(game):
    screen = _enter_edit_mode(game)
    # Every rebindable row is selectable (restart is not).
    for action in settings.REBINDABLE_ACTIONS:
        i = _row_index(action)
        assert screen.row_rects[i].collidepoint(screen.row_rects[i].center)


def test_edit_button_toggles_off(game):
    screen = _enter_edit_mode(game)
    game._handle_mouse_click(screen.edit_rect.center)
    assert not screen.edit_mode


def test_back_in_edit_mode_exits_edit_mode_not_navigate(game):
    """While editing, BACK exits edit mode instead of navigating to Options."""
    screen = _enter_edit_mode(game)
    game._handle_mouse_click(screen.back_rect.center)
    assert not screen.edit_mode
    assert game.state == "controls"
    # A second BACK press now navigates as usual.
    game._handle_mouse_click(screen.back_rect.center)
    pump_fade(game)
    assert game.state == "options"


def test_esc_exits_edit_mode(game):
    screen = _enter_edit_mode(game)
    game._handle_keydown(pygame.K_ESCAPE)
    assert not screen.edit_mode
    assert game.state == "controls"


# ---------------------------------------------------------------------- #
# Awaiting-input capture
# ---------------------------------------------------------------------- #


def test_selecting_row_enters_awaiting_and_captures_key(game):
    screen = _enter_edit_mode(game)
    i = _row_index("fire")
    game._handle_mouse_click(screen.row_rects[i].center)
    assert screen.awaiting_row == i
    # Next keypress becomes the new binding.
    game._handle_keydown(pygame.K_j)
    assert screen._bindings()["fire"] == pygame.K_j
    # Capture returns to the edit-mode row list (still editing, row cleared).
    assert screen.edit_mode
    assert screen.awaiting_row is None


def test_esc_cancels_capture_without_rebinding(game):
    screen = _enter_edit_mode(game)
    i = _row_index("fire")
    game._handle_mouse_click(screen.row_rects[i].center)
    assert screen.awaiting_row == i
    game._handle_keydown(pygame.K_ESCAPE)
    assert screen._bindings()["fire"] == settings.DEFAULT_KEY_BINDINGS["fire"]
    assert screen.awaiting_row is None
    # Still in edit mode after a cancelled capture.
    assert screen.edit_mode


def test_esc_never_bindable_for_non_esc_default_actions(game):
    screen = _enter_edit_mode(game)
    i = _row_index("fire")
    game._handle_mouse_click(screen.row_rects[i].center)
    # ESC is reserved for non-ESC-default actions: capture is cancelled,
    # binding unchanged, and the store refuses it outright.
    game._handle_keydown(pygame.K_ESCAPE)
    assert screen._bindings()["fire"] == pygame.K_SPACE
    assert not screen.store.rebind("fire", pygame.K_ESCAPE)


def test_restart_row_not_rebindable(game):
    screen = _enter_edit_mode(game)
    i = _row_index("restart")
    game._handle_mouse_click(screen.row_rects[i].center)
    assert screen.awaiting_row is None
    assert not screen.store.rebind("restart", pygame.K_r)


def test_multiple_rebinds_in_one_edit_session(game):
    """After one capture, the user can immediately rebind another control
    without re-pressing EDIT."""
    screen = _enter_edit_mode(game)
    i_fire = _row_index("fire")
    game._handle_mouse_click(screen.row_rects[i_fire].center)
    game._handle_keydown(pygame.K_j)
    assert screen._bindings()["fire"] == pygame.K_j
    i_mute = _row_index("mute")
    game._handle_mouse_click(screen.row_rects[i_mute].center)
    game._handle_keydown(pygame.K_n)
    assert screen._bindings()["mute"] == pygame.K_n
    assert screen.edit_mode


# ---------------------------------------------------------------------- #
# Conflict handling (swap, never unbound)
# ---------------------------------------------------------------------- #


def test_rebind_to_used_key_swaps(game):
    """Rebinding fire onto M (mute's key) swaps: mute takes fire's old key,
    so both actions stay bound."""
    screen = _enter_edit_mode(game)
    i_fire = _row_index("fire")
    game._handle_mouse_click(screen.row_rects[i_fire].center)
    game._handle_keydown(pygame.K_m)
    bindings = screen._bindings()
    assert bindings["fire"] == pygame.K_m
    assert bindings["mute"] == pygame.K_SPACE  # displaced owner keeps a key
    # Every rebindable action remains bound to a real key. (pause and back
    # may legitimately share ESC by default, so keys are not required to be
    # distinct - only present.) The two swapped actions keep non-reserved
    # keys.
    for action in settings.REBINDABLE_ACTIONS:
        assert bindings[action] is not None
    assert bindings["fire"] not in settings.RESERVED_KEYS
    assert bindings["mute"] not in settings.RESERVED_KEYS


def test_esc_can_be_bound_for_esc_default_actions(game):
    """Actions that default to ESC (back, pause) CAN be rebound to ESC,
    even after being rebound away from it."""
    screen = _enter_edit_mode(game)
    for action in settings.ESC_DEFAULT_ACTIONS:
        i = _row_index(action)
        game._handle_mouse_click(screen.row_rects[i].center)
        # Rebind to a non-ESC key first.
        game._handle_keydown(pygame.K_p)
        assert screen._bindings()[action] == pygame.K_p
        # Now rebind back to ESC — should work.
        game._handle_mouse_click(screen.row_rects[i].center)
        game._handle_keydown(pygame.K_ESCAPE)
        assert screen._bindings()[action] == pygame.K_ESCAPE


def test_esc_default_actions_can_initially_bind_esc(game):
    """ESC_DEFAULT_ACTIONS start with ESC as default; confirming the
    binding is there in the first place (sanity check)."""
    for action in settings.ESC_DEFAULT_ACTIONS:
        assert settings.DEFAULT_KEY_BINDINGS[action] == pygame.K_ESCAPE


def test_rebind_same_key_is_noop(game):
    screen = _enter_edit_mode(game)
    i = _row_index("fire")
    game._handle_mouse_click(screen.row_rects[i].center)
    game._handle_keydown(pygame.K_SPACE)  # already the binding
    assert screen._bindings()["fire"] == pygame.K_SPACE


# ---------------------------------------------------------------------- #
# Persistence
# ---------------------------------------------------------------------- #


def test_rebind_persists_across_reload(tmp_path):
    path = tmp_path / "settings.json"
    store = UserSettings.load(str(path))
    store.rebind("fire", pygame.K_j)
    store.save()
    fresh = UserSettings.load(str(path))
    assert fresh.key_bindings["fire"] == pygame.K_j
    assert fresh.key_bindings["mute"] == pygame.K_m  # untouched default


def test_rebind_saves_immediately(game):
    screen = _enter_edit_mode(game)
    i = _row_index("fire")
    game._handle_mouse_click(screen.row_rects[i].center)
    game._handle_keydown(pygame.K_j)
    # Game fixture redirects SETTINGS_FILE to a temp path; reload proves
    # the rebind was written to disk, not just kept in memory.
    fresh = UserSettings.load()
    assert fresh.key_bindings["fire"] == pygame.K_j


# ---------------------------------------------------------------------- #
# Live game wiring
# ---------------------------------------------------------------------- #


def _exit_edit_mode_to_menu(game):
    """Leave edit mode and navigate controls -> options -> main menu."""
    game.controls_screen.toggle_edit_mode()
    game._handle_keydown(pygame.K_ESCAPE)  # controls -> options (back key)
    pump_fade(game)
    assert game.state == "options"
    game._handle_keydown(pygame.K_ESCAPE)  # options -> menu (back key)
    pump_fade(game)
    assert game.state == "menu"


def test_rebound_fire_key_fires_in_game(game):
    from helpers import KeyState, start_game

    screen = _enter_edit_mode(game)
    i = _row_index("fire")
    game._handle_mouse_click(screen.row_rects[i].center)
    game._handle_keydown(pygame.K_j)

    _exit_edit_mode_to_menu(game)
    start_game(game)
    # Old key no longer fires, new key does.
    game._update_game(KeyState(pygame.K_SPACE))
    assert len(game.bullets) == 0
    game._update_game(KeyState(pygame.K_j))
    assert len(game.bullets) == 1


def test_rebound_move_keys_move_player(game):
    from helpers import KeyState, start_game

    screen = _enter_edit_mode(game)
    for action, key in (("move_left", pygame.K_a), ("move_right", pygame.K_d)):
        i = _row_index(action)
        game._handle_mouse_click(screen.row_rects[i].center)
        game._handle_keydown(key)

    _exit_edit_mode_to_menu(game)
    start_game(game)
    x0 = game.player.x
    game._update_game(KeyState(pygame.K_LEFT))  # old key: no movement
    assert game.player.x == x0
    game._update_game(KeyState(pygame.K_a))
    assert game.player.x < x0
    x1 = game.player.x
    game._update_game(KeyState(pygame.K_d))
    assert game.player.x > x1


def test_rebound_mute_key_toggles_mute(game):
    from helpers import KeyState, start_game

    screen = _enter_edit_mode(game)
    i = _row_index("mute")
    game._handle_mouse_click(screen.row_rects[i].center)
    game._handle_keydown(pygame.K_n)

    _exit_edit_mode_to_menu(game)
    start_game(game)
    muted_before = game.audio.muted
    game._handle_keydown(pygame.K_m)  # old key: no toggle
    assert game.audio.muted == muted_before
    game._handle_keydown(pygame.K_n)
    assert game.audio.muted != muted_before


def test_rebound_back_key_navigates_menus(game):
    screen = _enter_edit_mode(game)
    i = _row_index("back")
    game._handle_mouse_click(screen.row_rects[i].center)
    game._handle_keydown(pygame.K_b)

    game.controls_screen.toggle_edit_mode()
    # With back rebound to B, the new key navigates controls -> options and
    # the old key (ESC) no longer does.
    game._handle_keydown(pygame.K_ESCAPE)
    assert game.state == "controls"  # unchanged - ESC is no longer back
    game._handle_keydown(pygame.K_b)
    pump_fade(game)
    assert game.state == "options"
    # From Options, same: ESC no longer navigates, B does.
    game._handle_keydown(pygame.K_ESCAPE)
    assert game.state == "options"  # unchanged
    game._handle_keydown(pygame.K_b)
    pump_fade(game)
    assert game.state == "menu"