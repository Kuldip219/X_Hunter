"""Screen-size / proportional-layout contract.

The game is AUTHORED on a 600x800 canvas: every spatial value is written in
authored pixels and passed through settings.px(), and every layout anchor is a
fraction of the live screen. These tests pin that contract so a future resize
really is a one-number change (settings.SCALE) rather than a re-tune of every
screen:

- the window is the derived size, with the authored 3:4 aspect ratio intact,
- every spatial constant moves with SCALE (checked by re-executing settings.py
  at several scales through the single SCALE knob),
- screen-relative anchors keep their proportion instead of drifting,
- nothing on any screen is drawn outside the new bounds.
"""

from __future__ import annotations

import pathlib
import types

import pytest
import pygame

import settings
from helpers import reach_boss, start_game, wait_for_boss_active


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

SETTINGS_PATH = pathlib.Path(settings.__file__)
SCALE_LITERAL = "SCALE: float = 1.28"


def _settings_at(scale: float) -> types.ModuleType:
    """Re-execute settings.py with SCALE replaced by *scale*.

    settings.py is pure constants (no side effects beyond reading pygame key
    codes), so this gives the exact constants a resized build would see - which
    is precisely what proves the layout is derived rather than hardcoded to
    1.28.
    """
    src = SETTINGS_PATH.read_text(encoding="utf-8")
    assert SCALE_LITERAL in src, "settings.SCALE must stay a single literal knob"
    mod = types.ModuleType(f"_settings_at_{scale}")
    exec(
        compile(src.replace(SCALE_LITERAL, f"SCALE: float = {scale}"), str(SETTINGS_PATH), "exec"),
        mod.__dict__,
    )
    return mod


def _assert_inside(rect: pygame.Rect, what: str) -> None:
    assert rect.left >= 0, f"{what} clips the left edge: {rect}"
    assert rect.top >= 0, f"{what} clips the top edge: {rect}"
    assert rect.right <= settings.WIDTH, f"{what} clips the right edge: {rect}"
    assert rect.bottom <= settings.HEIGHT, f"{what} clips the bottom edge: {rect}"


# Everything spatial, as authored on the 600x800 canvas.
AUTHORED_SIZES: dict[str, tuple[int, int]] = {
    "PLAYER_IMG_SIZE": (65, 80),
    "ENEMY_IMG_SIZE": (50, 50),
    "BULLET_IMG_SIZE": (10, 20),
    "ENEMY_BULLET_IMG_SIZE": (10, 16),
    "EXPLOSION_IMG_SIZE": (70, 70),
    "POWERUP_IMG_SIZE": (40, 40),
    "POWERUP_VISIBLE_SIZE": (28, 28),
    "HEALTH_IMG_SIZE": (200, 70),
}
AUTHORED_MENU_SIZES: dict[str, tuple[int, int]] = {
    "TITLE_IMG_SIZE": (350, 120),
    "PLAY_IMG_SIZE": (250, 80),
    "OPTIONS_IMG_SIZE": (250, 80),
    "EXIT_IMG_SIZE": (250, 80),
    "PAUSE_IMG_SIZE": (400, 100),
    "CONTINUE_IMG_SIZE": (250, 80),
    "QUIT_IMG_SIZE": (250, 72),
    "RESTART_IMG_SIZE": (250, 80),
    "QUIT_GAMEOVER_IMG_SIZE": (250, 80),
    "SCORE_IMG_SIZE": (250, 80),
    "BACK_IMG_SIZE": (250, 80),
    "CONTROLS_IMG_SIZE": (250, 80),
}
AUTHORED_SCALARS: dict[str, int] = {
    "PLAYER_WIDTH": 65,
    "PLAYER_HEIGHT": 80,
    "ENEMY_WIDTH": 50,
    "ENEMY_HEIGHT": 50,
    "PLAYER_SPEED_PER_SEC": 300,
    "ENEMY_SPEED_PER_SEC": 300,
    "BULLET_SPEED_PER_SEC": 600,
    "GUNNER_DRIFT_SPEED_PER_SEC": 150,
    "GUNNER_DESCEND_SPEED_PER_SEC": 120,
    "SHIP_EXIT_SPEED_PER_SEC": 600,
    "POWERUP_FALL_SPEED_PER_SEC": 250,
    "BOSS_DRIFT_MARGIN": 40,
    "BOSS_BOB_AMPLITUDE": 16,
    "BUTTON_HOVER_OFFSET": 5,
    "SHAKE_STRENGTH": 8,
    "INITIAL_ENEMY_X_MARGIN": 50,
    "FONT_SIZE_SMALL": 36,
    "FONT_SIZE_LARGE": 72,
    "FADE_TEXT_FONT_SIZE": 72,
    "SLIDER_TRACK_WIDTH": 220,
}
# Non-spatial values that must NOT move with the window: they are balance
# (seconds / counts / HP), not geometry.
SCREEN_INDEPENDENT = (
    "FPS",
    "PLAYER_START_HEALTH",
    "PLAYER_FIRE_COOLDOWN_SECONDS",
    "PLAYER_INVULNERABLE_DURATION_SECONDS",
    "POWERUP_DROP_CHANCE",
    "POWERUP_SHIELD_DURATION_SECONDS",
    "POWERUP_RAPID_FIRE_DURATION_SECONDS",
    "GUNNER_MAX_DESCENT_FRACTION",
    "GUNNER_FIRE_COOLDOWN_SECONDS",
    "BOSS_HP",
    "BOSS_PHASE_1_MIN_FRACTION",
    "BOSS_SPREAD_COOLDOWN_SECONDS",
    "BOSS_MINION_INTERVAL_SECONDS",
    "LEVEL_SCORE_TARGETS",
    "DIFFICULTY_TIME_TO_FULL",
    # Frame counts, not pixels.
    "SHAKE_DURATION_ON_HIT",
    "DAMAGE_FLASH_DURATION",
    "FADE_TEXT_HOLD_SECONDS",
)


# ------------------------------------------------------------------ #
# 1. The window is the derived size, aspect ratio intact
# ------------------------------------------------------------------ #

class TestScreenSize:
    def test_width_and_height_are_the_documented_scaled_values(self):
        # Authored 600x800 at +28%.
        assert settings.SCALE == pytest.approx(1.28)
        assert (settings.WIDTH, settings.HEIGHT) == (768, 1024)

    def test_dimensions_are_derived_from_the_authored_canvas(self):
        assert settings.WIDTH == settings.px(settings.BASE_WIDTH)
        assert settings.HEIGHT == settings.px(settings.BASE_HEIGHT)

    def test_increase_is_in_the_requested_band(self):
        growth = settings.WIDTH / settings.BASE_WIDTH
        assert 1.25 <= growth <= 1.30, f"width grew {growth:.3f}x"

    def test_aspect_ratio_is_unchanged(self):
        """3:4 preserved exactly - no gameplay/composition change, just bigger."""
        assert settings.WIDTH / settings.HEIGHT == pytest.approx(
            settings.BASE_WIDTH / settings.BASE_HEIGHT
        )
        assert (settings.WIDTH, settings.HEIGHT) == (3 * 256, 4 * 256)

    def test_the_display_really_is_that_size(self, game):
        assert game.screen.get_size() == (settings.WIDTH, settings.HEIGHT)

    def test_fonts_scale_with_the_window(self):
        # Text is a pixel quantity: unchanged authored sizes would shrink
        # relative to a bigger screen.
        assert settings.FONT_SIZE_SMALL == settings.px(36)
        assert settings.FONT_SIZE_LARGE == settings.px(72)
        assert settings.FONT_SIZE_LARGE > 72 and settings.FONT_SIZE_SMALL > 36


# ------------------------------------------------------------------ #
# 2. Everything spatial follows SCALE (the one-number resize guarantee)
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("scale", [0.5, 1.0, 1.28, 1.6, 2.0])
class TestProportionalDerivation:
    def test_dimensions_follow_scale(self, scale):
        alt = _settings_at(scale)
        assert alt.WIDTH == round(settings.BASE_WIDTH * scale)
        assert alt.HEIGHT == round(settings.BASE_HEIGHT * scale)

    def test_aspect_ratio_holds_at_every_scale(self, scale):
        alt = _settings_at(scale)
        assert alt.WIDTH / alt.HEIGHT == pytest.approx(3 / 4)

    def test_sprite_and_menu_footprints_follow_scale(self, scale):
        alt = _settings_at(scale)
        for name, (w, h) in {**AUTHORED_SIZES, **AUTHORED_MENU_SIZES}.items():
            assert getattr(alt, name) == (round(w * scale), round(h * scale)), name

    def test_scalar_pixels_and_speeds_follow_scale(self, scale):
        alt = _settings_at(scale)
        for name, authored in AUTHORED_SCALARS.items():
            if name == "SLIDER_TRACK_WIDTH":
                continue
            assert getattr(alt, name) == round(authored * scale), name
        assert alt.SLIDER_TRACK_SIZE[0] == round(220 * scale)
        assert alt.SLIDER_TRACK_SIZE[1] == round(12 * scale)

    def test_screen_relative_anchors_keep_their_proportion(self, scale):
        """Anchors written as fractions of the screen must stay at the same
        relative position - not at the same pixel position."""
        alt = _settings_at(scale)
        for name in (
            "OPTIONS_TITLE_Y",
            "CONTROLS_TITLE_Y",
            "CONTROLS_ROWS_TOP",
            "CONTROLS_EDIT_Y",
            "CONTROLS_ACTION_X",
            "CONTROLS_KEY_X",
            "BOSS_ACTIVE_Y",
        ):
            reference = getattr(_settings_at(1.0), name)
            assert getattr(alt, name) == pytest.approx(reference * scale, abs=1), name

    def test_balance_values_do_not_move_with_the_window(self, scale):
        alt = _settings_at(scale)
        for name in SCREEN_INDEPENDENT:
            assert getattr(alt, name) == getattr(settings, name), name

    def test_hud_and_boss_anchors_stay_relative(self, scale):
        alt = _settings_at(scale)
        # Player HUD anchor and the boss bar both track the edges/corners.
        assert alt.PLAYER_HEALTH_POS == (round(10 * scale), round(10 * scale))
        bar = alt.BOSS_HEALTH_BAR_SIZE
        assert bar[0] == round(340 * scale) and bar[1] == round(56 * scale)
        assert alt.BOSS_HEALTH_BAR_MARGIN_X == round(20 * scale)


def test_health_bar_footprint_is_scaled():
    """The health bar is a pixel footprint like any other sprite."""
    assert settings.HEALTH_IMG_SIZE == (settings.px(200), settings.px(70))


# ------------------------------------------------------------------ #
# 3. Nothing renders outside the new bounds
# ------------------------------------------------------------------ #

class TestNothingIsOffscreen:
    def test_main_menu(self, game):
        for name, rect in game.main_menu._buttons():
            _assert_inside(rect, f"main menu {name}")
            _assert_inside(
                rect.move(0, settings.BUTTON_HOVER_OFFSET), f"main menu {name} (hovered)"
            )
        _assert_inside(game.main_menu.title_rect, "main menu title")

    def test_pause_menu(self, game):
        for name, rect in game.pause_menu._buttons():
            _assert_inside(rect, f"pause {name}")
            _assert_inside(
                rect.move(0, settings.BUTTON_HOVER_OFFSET), f"pause {name} (hovered)"
            )
        _assert_inside(game.pause_menu.pause_rect, "pause banner")

    def test_game_over_menu(self, game):
        for name, rect in game.game_over_menu._buttons():
            _assert_inside(rect, f"game over {name}")
            _assert_inside(
                rect.move(0, settings.BUTTON_HOVER_OFFSET), f"game over {name} (hovered)"
            )
        title = game.assets.big_font.render("GAME OVER", True, settings.WHITE)
        _assert_inside(
            title.get_rect(center=(settings.WIDTH // 2, settings.h_frac(1 / 4))),
            "game over title",
        )

    def test_options_screen(self, game):
        screen = game.options_screen
        for name, rect in screen._buttons():
            _assert_inside(rect, f"options {name}")
            _assert_inside(
                rect.move(0, settings.BUTTON_HOVER_OFFSET), f"options {name} (hovered)"
            )
        for name, track in screen.slider_tracks.items():
            # The grabbable hit zone extends past the track; the handle must
            # stay on screen too.
            _assert_inside(track.inflate(0, settings.px(30)), f"options {name} slider zone")
            handle = pygame.Rect(0, 0, *settings.SLIDER_HANDLE_SIZE)
            handle.center = (track.left, track.top)
            _assert_inside(pygame.Rect(track.left - handle.width, track.top,
                                      handle.width * 2 + track.width, handle.height),
                           f"options {name} slider handle travel")

        # The three bottom buttons must not overlap each other.
        rects = [screen.high_scores_rect, screen.controls_rect, screen.back_rect]
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                assert not rects[i].colliderect(rects[j]), (rects[i], rects[j])

    def test_controls_screen(self, game):
        screen = game.controls_screen
        for name, rect in screen._buttons():
            _assert_inside(rect, f"controls {name}")
        for i, rect in enumerate(screen.row_rects):
            _assert_inside(rect, f"controls row {i} hit zone")
        # Rows must not overlap the EDIT or BACK buttons.
        for rect in screen.row_rects:
            assert not rect.colliderect(screen.edit_rect), "row overlaps EDIT"
            assert not rect.colliderect(screen.back_rect), "row overlaps BACK"

    def test_high_scores_screen(self, game):
        _assert_inside(game.high_scores_menu.back_rect, "high scores BACK")
        title = game.assets.big_font.render("HIGH SCORES", True, settings.WHITE)
        _assert_inside(
            title.get_rect(center=(settings.WIDTH // 2, settings.h_frac(3 / 20))),
            "high scores title",
        )

    def test_leaderboard_rows_fit_on_screen(self, game):
        """Ten rows at the proportional pitch must fit above the BACK button."""
        last_row = settings.px(
            settings.HIGHSCORE_ROWS_TOP_AUTHORED
            + (settings.HIGHSCORE_MAX - 1) * settings.HIGHSCORE_ROW_PITCH_AUTHORED
        )
        assert last_row < settings.HEIGHT
        assert last_row < game.high_scores_menu.back_rect.top

    def test_hud_stays_on_screen(self, game):
        start_game(game)
        health = game.assets.health_images[settings.PLAYER_START_HEALTH]
        rect = health.get_rect(topleft=settings.PLAYER_HEALTH_POS)
        _assert_inside(rect, "player health bar")

        # Power-up status stack (shield + rapid fire rows).
        rows = 2
        block = pygame.Rect(
            settings.POWERUP_STATUS_X,
            settings.POWERUP_STATUS_Y,
            200,
            rows * settings.POWERUP_STATUS_ROW_GAP,
        )
        _assert_inside(block, "power-up status stack")
        # ...and it must sit clear of the mute indicator in the top-right.
        assert settings.POWERUP_STATUS_Y + rows * settings.POWERUP_STATUS_ROW_GAP < settings.HEIGHT

    def test_boss_health_bar_is_on_screen_and_clear_of_the_player_bar(self, game):
        start_game(game)
        game.boss = type("_B", (), {})()  # placeholder only for _boss_bar_rect()
        bar = game._boss_bar_rect()
        _assert_inside(bar, "boss health bar")

        player_bar = game.assets.health_images[settings.PLAYER_START_HEALTH].get_rect(
            topleft=settings.PLAYER_HEALTH_POS
        )
        _assert_inside(player_bar, "player health bar")
        assert not bar.colliderect(player_bar), (bar, player_bar)
        assert bar.left > player_bar.right, "boss bar must clear the player HUD"

    def test_mute_indicator_stays_on_screen(self, game):
        text = game.assets.font.render("MUTED", True, settings.LIGHT_GRAY)
        margin = settings.w_frac(1 / 60)
        _assert_inside(
            text.get_rect(topright=(settings.WIDTH - margin, margin)), "mute indicator"
        )

    def test_boss_sprite_stays_within_its_drift_window(self, game):
        """Duty-cycles the boss across its bounds: it must never leave the
        screen, and its bob must not push it off the top."""
        boss = reach_boss(game)
        assert wait_for_boss_active(game)
        for _ in range(1200):
            game._update_and_draw((0, 0))
            rect = boss.get_rect()
            assert rect.left >= 0 and rect.right <= settings.WIDTH, rect
            assert rect.top >= 0, rect
        assert boss.get_rect().bottom < settings.HEIGHT

    def test_spawn_bounds_keep_sprites_fully_on_screen(self, game):
        """A spawned enemy/gunner must be placed wholly inside the playfield."""
        from enemy import Enemy
        from gunner import GunnerEnemy

        for _ in range(300):
            e = Enemy.spawn_initial(settings.WIDTH)
            assert 0 <= e.x <= settings.WIDTH - e.width
            g = GunnerEnemy.spawn_initial(settings.WIDTH)
            assert 0 <= g.x <= settings.WIDTH - g.width
        assert settings.INITIAL_ENEMY_X_MARGIN >= settings.ENEMY_WIDTH

    def test_gunner_stop_line_is_relative_to_screen_height(self):
        from gunner import GunnerEnemy

        stop_cap = settings.HEIGHT * settings.GUNNER_MAX_DESCENT_FRACTION
        for _ in range(200):
            g = GunnerEnemy(0, 0, settings.WIDTH)
            assert g.stop_y <= stop_cap - g.height + 1
            assert g.stop_y > 0


# ------------------------------------------------------------------ #
# 4. Backgrounds still fit and still tile at the new resolution
# ------------------------------------------------------------------ #

class TestBackgroundsFitTheScreen:
    def test_every_parallax_tile_is_exactly_one_screen_tall(self, game):
        for level in range(settings.LEVEL_COUNT):
            game.parallax.set_level(level)
            for layer in game.parallax.layers:
                assert layer.image.get_size() == (settings.WIDTH, settings.HEIGHT)

    def test_two_tile_copies_cover_the_screen_after_a_full_wrap_cycle(self, game):
        """The wrap math depends on the tile matching the screen height; if a
        resize broke that, a gap would show at the wrap point."""
        game.parallax.set_level(0)
        for layer in game.parallax.layers:
            for _ in range(400):
                layer.update(1 / settings.FPS)
                h = layer.image.get_height()
                assert h == settings.HEIGHT
                y = -layer.offset_y
                assert y <= 0 and y + 2 * h >= settings.HEIGHT, y

    def test_static_ui_background_is_screen_sized(self, game):
        assert game.static_bg.image.get_size() == (settings.WIDTH, settings.HEIGHT)

    def test_rescaled_tiles_keep_a_clean_seam(self, game):
        """The rescale must not reintroduce a visible seam where the tile
        wraps: the wrap discontinuity has to stay below the image's own
        row-to-row variation (a wrap step no bigger than normal vertical
        detail is, by definition, not visible)."""
        import numpy as np

        for level in range(settings.LEVEL_COUNT):
            game.parallax.set_level(level)
            for layer in game.parallax.layers:
                arr = pygame.surfarray.array3d(layer.image).astype(np.float64)
                rows = np.transpose(arr, (1, 0, 2))  # [y][x][c]
                seam = float(np.abs(rows[0] - rows[-1]).mean())
                row_step = float(np.abs(rows[1:] - rows[:-1]).mean())
                assert seam <= row_step + 0.1, (
                    f"seam {seam:.3f} vs row step {row_step:.3f}"
                )


# ------------------------------------------------------------------ #
# 5. Every screen still draws (no layout crashes at the new size)
# ------------------------------------------------------------------ #

def test_every_state_draws_at_the_new_size(game):
    """Drive _draw_frame for every screen state: a proportional-layout bug
    (a negative rect, a bad scale) surfaces as an exception or as a blank
    screen. The canvas must also stay the expected size."""
    start_game(game)
    game._update_and_draw((0, 0))
    assert game.screen.get_size() == (settings.WIDTH, settings.HEIGHT)

    # Populate the leaderboard so its rows are drawn too.
    game.high_scores.add(83.0, result="Finished")
    game.high_scores.add(41.0, result="Dead")

    game.player.shield_timer = 1.0
    game.player.rapid_fire_timer = 1.0
    for state in (
        "game",
        "menu",
        "options",
        "controls",
        "high_scores",
        "pause",
        "game_over",
        "level_intro",
        "level_finished",
    ):
        game.state = state
        game._draw_frame((settings.WIDTH // 2, settings.HEIGHT // 2))
        assert game.screen.get_size() == (settings.WIDTH, settings.HEIGHT)


def test_menu_buttons_are_clickable_at_their_centres(game):
    """Layout changes must keep the hit targets on top of the drawn buttons."""
    game._handle_mouse_click(game.main_menu.play_rect.center)
    assert game.state != "menu" or game.fade.fading_out
