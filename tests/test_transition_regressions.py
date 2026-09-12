"""Regressions for the level-transition state machine.

Every test here reproduces a bug that shipped and was confirmed by driving
the real Game state machine (Game._advance_transitions, via pump_run*):

- RESTART after clearing the FINAL level raised IndexError, because the
  checkpoint advanced past the last level before the bounds check and
  reset_game() then indexed LEVEL_SCORE_TARGETS out of range.
- Pausing during the "Level Finished" overlay was ignored: the overlay kept
  advancing in every state, and its completion callback called fade.start()
  which overrode the player's own pause transition.
- Quitting to the menu during that overlay was ignored the same way.
- The "Phase 2" intro text drew over live gameplay: the Level 1 -> 2
  transition never entered the dedicated "level_intro" state, so the ship,
  enemies, health bar and score all rendered behind the text.
"""

import pygame
import pytest

import settings
from helpers import (
    kill_boss,
    pump_run,
    pump_run_until,
    reach_level_2,
    run_ship_exit,
    start_game,
)


def _clear_current_level(game):
    """Hit the current level's score target and run the ship exit +
    "Level Finished" text through to completion. After this call the game
    is in the middle of transitioning to the next level's intro.

    Only valid for the normal (ship-exit) levels - the boss level has no
    "Level Finished" screen (see kill_boss).
    """
    game.score = game.level_score_target
    game._check_level_completion()
    run_ship_exit(game)
    # Run the "Level Finished" fade text to completion (Phase 2).
    for _ in range(300):
        game.fade_text.update()
    game._on_fade_text_done()


def _finish_the_run(game):
    """Clear every level in sequence and land on the end-of-run screen.

    Levels 1-2 end through the normal ship-exit transition; the final level
    is the boss fight, which ends by defeating the boss through the real
    damage path and playing the victory sequence out. Both paths land on the
    same "game_over" state (framed as VICTORY when run_finished is set).
    """
    start_game(game)
    for _ in range(settings.LEVEL_COUNT - 1):
        _clear_current_level(game)
        assert pump_run_until(
            game, lambda g: g.state in ("game", "level_finished") and not g.fade_text.active
            and g.score < g.level_score_target
        ), "level transition never settled"
    assert game.current_level == settings.BOSS_LEVEL_INDEX
    # Clear Level 3's opening wave to reach the boss gate, then fight it.
    game.score = game.level_score_target
    game._check_level_completion()
    assert game.boss is not None, "the score gate should fly the boss in"
    assert kill_boss(game), "boss fight never reached the end-of-run screen"
    assert game.state == "game_over", f"expected game_over, got {game.state!r}"


# ── Clearing the final level, then RESTART ─────────────────────────────


class TestRestartAfterFinishingRun:
    def test_finishing_every_level_reaches_game_over(self, game):
        _finish_the_run(game)
        assert game.run_finished is True

    def test_checkpoint_never_points_past_the_last_level(self, game):
        """reset_game() indexes LEVEL_SCORE_TARGETS[current_level], so a
        checkpoint past the final level is an IndexError waiting to happen."""
        _finish_the_run(game)
        assert game.checkpoint_level <= settings.LEVEL_COUNT - 1
        assert game.checkpoint_level < len(settings.LEVEL_SCORE_TARGETS)

    def test_restart_after_finishing_does_not_crash(self, game):
        """The original bug: IndexError from reset_game() the moment RESTART
        was clicked on the game-over screen of a COMPLETED run."""
        _finish_the_run(game)
        game._handle_mouse_click(game.game_over_menu.restart_rect.center)
        assert game.current_level == 0

    def test_restart_after_finishing_starts_a_fresh_run(self, game):
        """A completed run must not resume at its checkpoint - that level was
        already beaten. RESTART starts over from Level 1 with a clean timer."""
        _finish_the_run(game)
        game._handle_mouse_click(game.game_over_menu.restart_rect.center)
        assert game.current_level == 0
        assert game.checkpoint_level == 0
        assert game.run_timer == 0.0
        assert game.run_finished is False
        assert game.level_score_target == settings.LEVEL_SCORE_TARGETS[0]

    def test_restart_after_finishing_reaches_playable_level_1(self, game):
        _finish_the_run(game)
        game._handle_mouse_click(game.game_over_menu.restart_rect.center)
        assert pump_run_until(
            game, lambda g: g.state == "game" and not g.fade_text.active
        )
        assert game.current_level == 0

    def test_death_restart_still_resumes_at_the_checkpoint(self, game):
        """The fix must not break the checkpoint path it sits next to: dying
        in Level 2 still resumes Level 2 with the run timer preserved."""
        reach_level_2(game)
        game.run_timer = 42.0
        game.state = "game_over"
        game._handle_mouse_click(game.game_over_menu.restart_rect.center)
        assert game.current_level == 1
        assert game.run_timer == pytest.approx(42.0, abs=0.5)


# ── Pausing / quitting during "Level Finished" ─────────────────────────


class TestPauseDuringLevelTransition:
    def _pause_mid_overlay(self, game):
        start_game(game)
        game.score = game.level_score_target
        game._check_level_completion()
        run_ship_exit(game)
        # Advance fade from "game" to "level_finished", then let text start.
        pump_run(game, 60)
        assert game.fade_text.active
        game._handle_keydown(pygame.K_ESCAPE)
        assert pump_run_until(game, lambda g: g.state == "pause")

    def test_escape_during_overlay_reaches_pause(self, game):
        self._pause_mid_overlay(game)
        assert game.state == "pause"

    def test_pause_is_not_overridden_by_the_overlay(self, game):
        """The original bug: the overlay finished while paused, and its
        callback's fade.start("game") threw the player back into gameplay."""
        self._pause_mid_overlay(game)
        pump_run(game, 300)
        assert game.state == "pause"
        assert game.current_level == 0

    def test_pending_transition_is_frozen_not_discarded(self, game):
        self._pause_mid_overlay(game)
        pump_run(game, 300)
        assert game._level_transition_pending is True

    def test_resuming_completes_the_frozen_transition(self, game):
        self._pause_mid_overlay(game)
        pump_run(game, 300)
        game._handle_keydown(pygame.K_ESCAPE)       # unpause
        assert pump_run_until(game, lambda g: g.current_level == 1)
        assert pump_run_until(
            game, lambda g: g.state == "game" and not g.fade_text.active
        )
        assert game.level_score_target == settings.LEVEL_SCORE_TARGETS[1]


class TestQuitToMenuDuringLevelTransition:
    def _quit_mid_overlay(self, game):
        start_game(game)
        game.score = game.level_score_target
        game._check_level_completion()
        run_ship_exit(game)
        # Advance fade from "game" to "level_finished", then let text start.
        pump_run(game, 60)
        game._handle_keydown(pygame.K_ESCAPE)
        assert pump_run_until(game, lambda g: g.state == "pause")
        game._handle_mouse_click(game.pause_menu.quit_rect.center)
        assert pump_run_until(game, lambda g: g.state == "menu")

    def test_quit_during_overlay_reaches_menu(self, game):
        self._quit_mid_overlay(game)
        assert game.state == "menu"

    def test_level_does_not_advance_while_on_the_menu(self, game):
        """The abandoned run must stop advancing the moment it is abandoned."""
        self._quit_mid_overlay(game)
        pump_run(game, 700)
        assert game.current_level == 0
        assert game._level_transition_pending is True

    def test_menu_is_not_overridden_by_the_overlay(self, game):
        """The original bug: the "Level Finished" overlay completed while the
        player sat on the main menu, queued "Phase 2" behind it, and that
        second overlay's callback called fade.start("game") - dropping the
        player into gameplay they never asked for. Needs enough frames for
        BOTH overlay cycles (~210 frames each) to play out.
        """
        self._quit_mid_overlay(game)
        pump_run(game, 700)
        assert game.state == "menu"

    def test_next_play_starts_a_clean_level_1(self, game):
        """The abandoned run's pending transition and stale overlay text must
        not leak into the next run."""
        self._quit_mid_overlay(game)
        pump_run(game, 300)
        game._handle_mouse_click(game.main_menu.play_rect.center)
        assert pump_run_until(game, lambda g: g.state == "level_intro")
        assert game.fade_text.text == "Phase 1"
        assert game._level_transition_pending is False
        assert pump_run_until(
            game, lambda g: g.state == "game" and not g.fade_text.active
        )
        assert game.current_level == 0


# ── "Phase N" gets its own screen ──────────────────────────────────────


class TestPhaseIntroHasOwnScreen:
    def _advance_to_phase_2_intro(self, game):
        start_game(game)
        _clear_current_level(game)
        assert pump_run_until(game, lambda g: g.state == "level_intro")

    def test_level_2_intro_enters_level_intro_state(self, game):
        """The original bug: the Level 1 -> 2 transition left the state on
        "game", so _draw_frame kept rendering gameplay behind the text."""
        self._advance_to_phase_2_intro(game)
        assert game.state == "level_intro"
        assert game.current_level == 1
        assert game.fade_text.text == "Phase 2"
        assert game.fade_text.active

    def test_level_2_intro_screen_draws_nothing_but_the_text(self, game):
        """_draw_frame() must leave the intro screen blank: no ship, no
        gunners, no health bar, no score. The text itself is drawn by run()
        after the fade, so it is absent from this frame."""
        self._advance_to_phase_2_intro(game)
        game.screen.fill(settings.BLACK)
        game._draw_frame((0, 0))
        probes = [
            (15, 15),                              # score
            (60, 70),                              # health bar
            (settings.WIDTH // 2, settings.HEIGHT - 60),   # player ship
            (settings.WIDTH - 30, 20),
            (settings.WIDTH // 2, 200),
        ]
        for p in probes:
            assert game.screen.get_at(p)[:3] == (0, 0, 0), (
                f"level_intro screen is not blank at {p}"
            )

    def test_gameplay_resumes_after_the_phase_2_intro(self, game):
        self._advance_to_phase_2_intro(game)
        assert pump_run_until(
            game, lambda g: g.state == "game" and not g.fade_text.active
        )
        assert game.current_level == 1
        assert game.score == 0
        assert game.gunners and not game.enemies

    def test_simulation_stays_frozen_across_the_transition(self, game):
        """Gameplay must not advance while an overlay or the fade to the intro
        screen is in flight."""
        start_game(game)
        _clear_current_level(game)
        from helpers import KeyState
        keys = KeyState()
        for _ in range(60):
            assert game._advance_simulation(1.0 / settings.FPS, keys) == 0
            game._advance_transitions()
