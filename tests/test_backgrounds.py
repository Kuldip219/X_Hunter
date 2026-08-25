"""Tests for parallax scrolling backgrounds and the static UI backdrop.

Covers the contract:
- wrap-around correctness (seamless tiling math),
- background does NOT update/scroll while state is anything other than "game",
- correct layer pair is active for Level 1 vs Level 2, swap on transition,
- static UI background renders behind menu screens without affecting layout.
"""

import pytest
import pygame

# Headless video driver — must be set before any pygame init.
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import settings
from background import ParallaxBackground, StaticBackground, _ScrollingLayer
from tests.helpers import KeyState, start_game, reach_level_2, pump_fade


@pytest.fixture(autouse=True)
def _init_pygame():
    """Ensure pygame is initialised with a dummy display for every test."""
    pygame.init()
    pygame.display.set_mode((settings.WIDTH, settings.HEIGHT))
    yield
    pygame.quit()


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _make_layer(speed: int = 100) -> _ScrollingLayer:
    """Create a test scrolling layer with a solid-colour tile."""
    surf = pygame.Surface((settings.WIDTH, settings.HEIGHT))
    surf.fill((30, 30, 60))
    return _ScrollingLayer(surf, speed)


def _make_parallax() -> ParallaxBackground:
    """Create a ParallaxBackground and force-load Level 0."""
    pb = ParallaxBackground()
    pb.set_level(0)
    return pb


def _make_game():
    """Create a Game instance (headless, dummy display)."""
    from game import Game
    return Game()


# ------------------------------------------------------------------ #
# 1. Wrap-around correctness
# ------------------------------------------------------------------ #

class TestWrapAround:
    """After enough elapsed dt, each layer's two tile copies remain
    seamlessly positioned (no gap, no overlap, no visible jump)."""

    def test_offset_wraps_at_tile_height(self):
        """Offset modulo tile_height stays within [0, tile_height)."""
        layer = _make_layer(speed=200)
        h = layer.image.get_height()  # == settings.HEIGHT
        dt = 1.0 / settings.FPS

        # Simulate 300 frames (~5 seconds at 60 FPS).
        for _ in range(300):
            layer.update(dt)
            assert 0 <= layer.offset_y < h, (
                f"offset_y {layer.offset_y} out of [0, {h})"
            )

    def test_two_copies_cover_screen(self):
        """Two stacked copies always cover the full screen height."""
        layer = _make_layer(speed=150)
        h = layer.image.get_height()
        dt = 1.0 / settings.FPS

        for _ in range(300):
            layer.update(dt)
            y_top = -layer.offset_y
            # Top copy covers [y_top, y_top + h).
            # Bottom copy covers [y_top + h, y_top + 2h).
            # Together they cover [y_top, y_top + 2h).
            # Screen is [0, HEIGHT). We need y_top <= 0 and y_top + 2h >= HEIGHT.
            assert y_top <= 0, f"gap at top: y_top={y_top}"
            assert y_top + 2 * h >= settings.HEIGHT, (
                f"gap at bottom: y_top + 2h = {y_top + 2 * h} < {settings.HEIGHT}"
            )

    def test_offset_wraps_full_tile(self):
        """After a full tile of downward scroll, offset wraps via modulo."""
        layer = _make_layer(speed=300)
        h = layer.image.get_height()
        dt = 1.0 / settings.FPS

        # Run enough frames for two full wraps.
        frames_to_wrap = int(2 * h / (layer.speed * dt)) + 4
        offsets = []
        for _ in range(frames_to_wrap):
            layer.update(dt)
            offsets.append(layer.offset_y)

        # Offset starts at 0, decreases (wraps to near h via modulo on
        # the first step), then continues decreasing toward 0, then
        # wraps again — confirming downward scroll direction.
        assert offsets[1] > h * 0.9, (
            f"first step didn't wrap downward: offsets[1]={offsets[1]}"
        )
        # After two full wraps, offset should have wrapped at least once
        # and be back near h (second wrap point).
        assert offsets[-1] > h * 0.9, (
            f"offset didn't complete second wrap: offsets[-1]={offsets[-1]}"
        )


# ------------------------------------------------------------------ #
# 2. Background does NOT update while not in "game" state
# ------------------------------------------------------------------ #

class TestFreezeDuringNonGame:
    """Parallax position is unchanged across ticks when state != 'game'."""

    def test_parallax_frozen_during_menu(self):
        game = _make_game()
        assert game.state == "menu"
        game.parallax.set_level(0)
        # Advance a few simulation steps — should not move parallax.
        initial_offsets = [l.offset_y for l in game.parallax.layers]
        for _ in range(60):
            game._advance_simulation(1.0 / settings.FPS, KeyState())
        for i, layer in enumerate(game.parallax.layers):
            assert layer.offset_y == initial_offsets[i], (
                f"Layer {i} moved during menu state"
            )

    def test_parallax_frozen_during_pause(self):
        game = _make_game()
        start_game(game)
        assert game.state == "game"
        game.parallax.set_level(0)
        # Let it scroll a bit.
        for _ in range(30):
            game._advance_simulation(1.0 / settings.FPS, KeyState())
        offsets_before = [l.offset_y for l in game.parallax.layers]
        # Pause.
        game.fade.start("pause")
        pump_fade(game)
        assert game.state == "pause"
        # Simulate more frames — parallax should not move.
        for _ in range(60):
            game._advance_simulation(1.0 / settings.FPS, KeyState())
        for i, layer in enumerate(game.parallax.layers):
            assert layer.offset_y == offsets_before[i], (
                f"Layer {i} moved during pause"
            )

    def test_parallax_frozen_during_game_over(self):
        game = _make_game()
        start_game(game)
        assert game.state == "game"
        game.parallax.set_level(0)
        for _ in range(30):
            game._advance_simulation(1.0 / settings.FPS, KeyState())
        offsets_before = [l.offset_y for l in game.parallax.layers]
        # Simulate death and game_over.
        game.player.health = 0
        game.player.take_hit()
        game.player.dead = True
        game.fade.start("game_over")
        pump_fade(game)
        assert game.state == "game_over"
        for _ in range(60):
            game._advance_simulation(1.0 / settings.FPS, KeyState())
        for i, layer in enumerate(game.parallax.layers):
            assert layer.offset_y == offsets_before[i], (
                f"Layer {i} moved during game_over"
            )

    def test_parallax_frozen_during_level_intro(self):
        game = _make_game()
        start_game(game)
        assert game.state == "game"
        game.parallax.set_level(0)
        for _ in range(30):
            game._advance_simulation(1.0 / settings.FPS, KeyState())
        offsets_before = [l.offset_y for l in game.parallax.layers]
        # Simulate level_intro state.
        game.state = "level_intro"
        for _ in range(60):
            game._advance_simulation(1.0 / settings.FPS, KeyState())
        for i, layer in enumerate(game.parallax.layers):
            assert layer.offset_y == offsets_before[i], (
                f"Layer {i} moved during level_intro"
            )

    def test_parallax_frozen_during_level_finished(self):
        game = _make_game()
        start_game(game)
        assert game.state == "game"
        game.parallax.set_level(0)
        for _ in range(30):
            game._advance_simulation(1.0 / settings.FPS, KeyState())
        offsets_before = [l.offset_y for l in game.parallax.layers]
        # Simulate level_finished state.
        game.state = "level_finished"
        for _ in range(60):
            game._advance_simulation(1.0 / settings.FPS, KeyState())
        for i, layer in enumerate(game.parallax.layers):
            assert layer.offset_y == offsets_before[i], (
                f"Layer {i} moved during level_finished"
            )

    def test_parallax_continues_during_ship_exit(self):
        """Ship exit is a sub-flag inside state=='game', so parallax
        must keep scrolling — it's still live gameplay."""
        game = _make_game()
        start_game(game)
        assert game.state == "game"
        game.parallax.set_level(0)
        # Scroll a few frames to get a non-zero offset.
        for _ in range(10):
            game._advance_simulation(1.0 / settings.FPS, KeyState())
        # Trigger ship exit.
        game.score = game.level_score_target
        game._check_level_completion()
        assert game._ship_exit_active
        assert game.state == "game", "ship exit must be inside game state"
        offsets_before = [l.offset_y for l in game.parallax.layers]
        # Simulate frames during ship exit — parallax should advance.
        for _ in range(30):
            game._advance_simulation(1.0 / settings.FPS, KeyState())
        for i, layer in enumerate(game.parallax.layers):
            assert layer.offset_y != offsets_before[i], (
                f"Layer {i} froze during ship exit (sub-state of game)"
            )


# ------------------------------------------------------------------ #
# 3. Correct layer pair per level + swap on transition
# ------------------------------------------------------------------ #

class TestLayerSwap:
    """Level 1 and Level 2 use different layer images; swap happens at
    the right transition point."""

    def test_level_0_uses_l1_layers(self):
        pb = _make_parallax()
        assert pb.current_level == 0
        assert len(pb.layers) == 2
        # Layer images should be different from Level 2's.
        l1_imgs = [l.image for l in pb.layers]

        pb.set_level(1)
        l2_imgs = [l.image for l in pb.layers]

        # At least one layer should be a different surface.
        assert any(l1 is not l2 for l1, l2 in zip(l1_imgs, l2_imgs)), (
            "Level 0 and Level 1 use the same layer images"
        )

    def test_level_swap_resets_offset(self):
        pb = _make_parallax()
        # Scroll Level 0 a bit.
        for _ in range(60):
            pb.update(1.0 / settings.FPS)
        assert pb.layers[0].offset_y > 0

        # Swap to Level 1 — offset should reset.
        pb.set_level(1)
        for layer in pb.layers:
            assert layer.offset_y == 0.0, "offset not reset on level swap"

    def test_same_level_swap_noop(self):
        """Calling set_level with the current level doesn't reload."""
        pb = _make_parallax()
        old_layer_ids = [id(l) for l in pb.layers]
        pb.set_level(0)  # same level
        new_layer_ids = [id(l) for l in pb.layers]
        assert old_layer_ids == new_layer_ids, "layers were reloaded on same-level swap"

    def test_game_starts_with_correct_level(self):
        game = _make_game()
        start_game(game)
        assert game.state == "game"
        assert game.parallax.current_level == game.current_level

    def test_parallax_swaps_on_level_transition(self):
        game = _make_game()
        reach_level_2(game)
        assert game.state == "game"
        assert game.current_level == 1
        assert game.parallax.current_level == 1


# ------------------------------------------------------------------ #
# 4. Static UI background
# ------------------------------------------------------------------ #

class TestStaticUIBackground:
    """The static UI background renders behind menu screens without
    affecting existing button/text positioning or layout."""

    def test_loads_without_crash(self):
        sb = StaticBackground()
        sb.load()
        assert sb.image is not None
        assert sb.image.get_size() == (settings.WIDTH, settings.HEIGHT)

    def test_draw_does_not_crash(self):
        sb = StaticBackground()
        sb.load()
        surface = pygame.Surface((settings.WIDTH, settings.HEIGHT))
        sb.draw(surface)  # should not raise

    def test_draw_fills_screen(self):
        """After drawing, the screen should not be all-black (the bg has colour)."""
        sb = StaticBackground()
        sb.load()
        surface = pygame.Surface((settings.WIDTH, settings.HEIGHT))
        surface.fill(settings.BLACK)
        sb.draw(surface)
        # Sample a few pixels — the UI bg has non-black stars/nebula.
        samples = [surface.get_at((x, y))[:3]
                   for x, y in [(100, 100), (300, 400), (500, 200)]]
        assert any(c != (0, 0, 0) for c in samples), (
            "Static background appears entirely black"
        )

    def test_game_initializes_static_bg(self):
        game = _make_game()
        assert game.static_bg is not None
        assert game.static_bg.image is not None

    def test_static_bg_does_not_affect_menu_layout(self):
        """Clicking Play after static bg is drawn still works (state transitions)."""
        game = _make_game()
        assert game.state == "menu"
        # Draw the menu (which now includes static_bg underneath).
        game._draw_frame(game.main_menu.play_rect.center)
        # Click play — should still transition.
        game._handle_mouse_click(game.main_menu.play_rect.center)
        pump_fade(game)
        assert game.state == "level_intro"

    def test_static_bg_drawn_on_main_menu(self):
        """Regression: the main menu must show the static background,
        not a solid MENU_BG_COLOR fill."""
        game = _make_game()
        assert game.state == "menu"
        # Draw one frame — static_bg should paint before the menu.
        game._draw_frame(game.main_menu.play_rect.center)
        # Sample pixels in the background area (corners, away from buttons).
        corners = [(10, 10), (590, 10), (10, 790), (590, 790)]
        for x, y in corners:
            r, g, b = game.screen.get_at((x, y))[:3]
            # MENU_BG_COLOR is (30, 30, 30). If we see that, the bg was overwritten.
            assert (r, g, b) != (30, 30, 30), (
                f"Main menu pixel ({x},{y}) is MENU_BG_COLOR — static bg missing"
            )

    def test_static_bg_fallback_on_missing_file(self, tmp_path, monkeypatch):
        """If the background file is missing, it falls back to a black surface."""
        sb = StaticBackground()
        monkeypatch.setattr(settings, "BG_UI_PATH", str(tmp_path / "nonexistent.png"))
        sb.load()
        assert sb.image is not None
        assert sb.image.get_size() == (settings.WIDTH, settings.HEIGHT)
        # Should be all black (fallback).
        assert sb.image.get_at((0, 0))[:3] == (0, 0, 0)
