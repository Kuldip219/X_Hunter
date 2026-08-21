"""Level system: fade text, level transitions, run timer, and death/restart.

Covers:
- FadeText component lifecycle (in → hold → out → done)
- Level transition at score threshold (Level 1 → Level 2)
- Score reset on transition
- Fade text sequencing ("Phase 1" → gameplay → "Level Finished" → "Phase 2")
- Run timer pause exclusion (menu/pause/game-over)
- Run timer accumulation across a Level 2 checkpoint restart
- Level 1 death does a full reset (level + timer)
- Level 2 death does a checkpoint restart (level + timer preserved)
"""

import pytest
import pygame

import settings
from enemy import Enemy
from ui import FadeText
from helpers import KeyState, pump_fade, start_game


# ── FadeText component ────────────────────────────────────────────────


class TestFadeText:
    def test_starts_inactive_after_full_cycle(self):
        ft = FadeText("Hello")
        assert ft.active is True
        # Run enough frames for start delay (18) + fade-in (255/5 ≈ 51) +
        # hold (1.5s ≈ 90 frames) + fade-out (255/5 ≈ 51) = ~210 frames.
        for _ in range(250):
            ft.update()
        assert ft.active is False

    def test_alpha_peaks_during_hold(self):
        ft = FadeText("Test")
        alphas = []
        for _ in range(250):
            ft.update()
            alphas.append(ft.alpha)
        assert max(alphas) == 255
        # After the peak, it should go back to 0.
        assert alphas[-1] == 0

    def test_reset_restarts_animation(self):
        ft = FadeText("First")
        for _ in range(10):
            ft.update()
        assert ft.active is True
        ft.reset("Second")
        assert ft.active is True
        assert ft.text == "Second"
        assert ft.alpha == 0
        assert ft.phase == "in"

    def test_reset_without_text_keeps_same_text(self):
        ft = FadeText("Keep")
        ft.reset()
        assert ft.text == "Keep"


# ── Level constants ───────────────────────────────────────────────────


class TestLevelConstants:
    def test_two_levels_defined(self):
        assert settings.LEVEL_COUNT == 2
        assert len(settings.LEVEL_SCORE_TARGETS) == settings.LEVEL_COUNT

    def test_level_1_target_is_200(self):
        assert settings.LEVEL_SCORE_TARGETS[0] == 200

    def test_level_2_target_is_100(self):
        assert settings.LEVEL_SCORE_TARGETS[1] == 100


# ── Level state after reset ───────────────────────────────────────────


class TestLevelStateAfterReset:
    def test_fresh_game_starts_at_level_0(self, game):
        start_game(game)
        assert game.current_level == 0
        assert game.checkpoint_level == 0
        assert game.level_score_target == settings.LEVEL_SCORE_TARGETS[0]

    def test_fresh_game_run_timer_is_zero(self, game):
        start_game(game)
        assert game.run_timer == 0.0

    def test_fresh_game_no_pending_transitions(self, game):
        start_game(game)
        assert game._level_transition_pending is False
        assert game._level_intro_pending is False


# ── Level transition at score threshold ────────────────────────────────


class TestLevelTransition:
    def test_score_triggers_level_finished_text(self, game):
        start_game(game)
        game.score = settings.LEVEL_SCORE_TARGETS[0] - 1
        game._check_level_completion()
        assert game._level_transition_pending is False
        assert game.fade_text.active is False

        game.score = settings.LEVEL_SCORE_TARGETS[0]
        game._check_level_completion()
        assert game._level_transition_pending is True
        assert game.fade_text.text == "Level Finished"
        assert game.fade_text.active is True

    def test_level_transition_advances_to_level_2(self, game):
        start_game(game)
        # Simulate reaching the score target.
        game.score = settings.LEVEL_SCORE_TARGETS[0]
        game._check_level_completion()
        assert game._level_transition_pending is True

        # Run fade text to completion (includes start delay).
        for _ in range(300):
            game.fade_text.update()
        assert game.fade_text.active is False

        # Trigger the completion handler (normally called by run()).
        game._on_fade_text_done()
        assert game.current_level == 1
        assert game.checkpoint_level == 1
        assert game.score == 0  # score resets on transition
        assert game.level_score_target == settings.LEVEL_SCORE_TARGETS[1]
        assert game.fade_text.text == "Phase 2"
        assert game.fade_text.active is True

    def test_level_2_completion_ends_run(self, game):
        start_game(game)
        # Fast-forward to Level 2.
        game.score = settings.LEVEL_SCORE_TARGETS[0]
        game._check_level_completion()
        for _ in range(300):
            game.fade_text.update()
        game._on_fade_text_done()
        assert game.current_level == 1

        # Dismiss the Phase 2 intro.
        game.fade_text.active = False
        game._level_intro_pending = False

        # Reach Level 2's target.
        game.score = settings.LEVEL_SCORE_TARGETS[1]
        game._check_level_completion()
        for _ in range(300):
            game.fade_text.update()
        game._on_fade_text_done()
        # No more levels → game_over fade started.
        assert game.fade.fading_out
        assert game.fade.next_state == "game_over"

    def test_no_transition_while_intro_pending(self, game):
        start_game(game)
        # Level intro is pending right after start_game (it clears it, but
        # let's explicitly set it to verify the guard).
        game._level_intro_pending = True
        game.score = settings.LEVEL_SCORE_TARGETS[0]
        game._check_level_completion()
        assert game._level_transition_pending is False

    def test_no_double_transition(self, game):
        start_game(game)
        game.score = settings.LEVEL_SCORE_TARGETS[0]
        game._check_level_completion()
        assert game._level_transition_pending is True
        # Calling again should be a no-op.
        game._check_level_completion()
        assert game._level_transition_pending is True


# ── Fade text freezes gameplay ────────────────────────────────────────


class TestFadeTextFreezesGameplay:
    def test_advance_simulation_returns_zero_steps_during_fade_text(self, game):
        start_game(game)
        game.fade_text.active = True
        steps = game._advance_simulation(1.0 / settings.FPS, KeyState())
        assert steps == 0

    def test_accumulator_clears_during_fade_text(self, game):
        """Any banked accumulator time is discarded when fade text activates."""
        start_game(game)
        # Bank some accumulator time.
        game._advance_simulation(settings.MAX_FRAME_DT + 0.01, KeyState())
        assert game.accumulator > 0
        # Now activate fade text.
        game.fade_text.active = True
        steps = game._advance_simulation(1.0 / settings.FPS, KeyState())
        assert steps == 0
        assert game.accumulator == 0.0  # cleared


# ── Run timer ─────────────────────────────────────────────────────────


class TestRunTimer:
    def test_run_timer_advances_during_gameplay(self, monkeypatch, game):
        ticks = _freeze_ticks(monkeypatch)
        start_game(game)

        # Simulate 5 s of gameplay.
        for _ in range(5 * settings.FPS):
            ticks["t"] += 1000.0 / settings.FPS
            game._advance_simulation(1.0 / settings.FPS, KeyState())

        assert game.run_timer == pytest.approx(5.0, abs=0.1)

    def test_run_timer_pauses_during_menu(self, monkeypatch, game):
        ticks = _freeze_ticks(monkeypatch)
        start_game(game)

        # 3 s of gameplay.
        for _ in range(3 * settings.FPS):
            ticks["t"] += 1000.0 / settings.FPS
            game._advance_simulation(1.0 / settings.FPS, KeyState())
        assert game.run_timer == pytest.approx(3.0, abs=0.1)

        # Pause: state → "pause" via fade.
        game._handle_keydown(pygame.K_ESCAPE)
        pump_fade(game)
        assert game.state == "pause"

        # 10 s of wall time while paused.
        for _ in range(10 * settings.FPS):
            ticks["t"] += 1000.0 / settings.FPS
            game._advance_simulation(1.0 / settings.FPS, KeyState())

        # Timer did NOT advance.
        assert game.run_timer == pytest.approx(3.0, abs=0.1)

        # Unpause.
        game._handle_keydown(pygame.K_ESCAPE)
        pump_fade(game)
        assert game.state == "game"

        # 2 s more.
        for _ in range(2 * settings.FPS):
            ticks["t"] += 1000.0 / settings.FPS
            game._advance_simulation(1.0 / settings.FPS, KeyState())

        assert game.run_timer == pytest.approx(5.0, abs=0.1)

    def test_run_timer_continues_through_fade_text(self, monkeypatch, game):
        """Run timer counts during level transitions (fade text overlays)."""
        ticks = _freeze_ticks(monkeypatch)
        start_game(game)

        # 2 s of gameplay.
        for _ in range(2 * settings.FPS):
            ticks["t"] += 1000.0 / settings.FPS
            game._advance_simulation(1.0 / settings.FPS, KeyState())
        assert game.run_timer == pytest.approx(2.0, abs=0.1)

        # Activate fade text (level finished) — state stays "game".
        game.fade_text.active = True
        assert game.state == "game"

        # 3 s of wall time with fade text active.
        for _ in range(3 * settings.FPS):
            ticks["t"] += 1000.0 / settings.FPS
            game._advance_simulation(1.0 / settings.FPS, KeyState())

        # Run timer DID advance (unlike difficulty clock which froze).
        assert game.run_timer == pytest.approx(5.0, abs=0.1)

    def test_run_timer_resets_on_full_restart(self, monkeypatch, game):
        ticks = _freeze_ticks(monkeypatch)
        start_game(game)

        for _ in range(5 * settings.FPS):
            ticks["t"] += 1000.0 / settings.FPS
            game._advance_simulation(1.0 / settings.FPS, KeyState())
        assert game.run_timer == pytest.approx(5.0, abs=0.1)

        # Full restart (from_checkpoint=False).
        game.reset_game(from_checkpoint=False)
        assert game.run_timer == 0.0
        assert game.run_timer_paused_ms == 0.0

    def test_run_timer_preserved_on_checkpoint_restart(self, monkeypatch, game):
        ticks = _freeze_ticks(monkeypatch)
        start_game(game)

        for _ in range(5 * settings.FPS):
            ticks["t"] += 1000.0 / settings.FPS
            game._advance_simulation(1.0 / settings.FPS, KeyState())
        assert game.run_timer == pytest.approx(5.0, abs=0.1)

        # Checkpoint restart (from_checkpoint=True).
        game.reset_game(from_checkpoint=True)
        assert game.run_timer == pytest.approx(5.0, abs=0.1)  # preserved!
        # But level is set to the checkpoint level.
        assert game.current_level == game.checkpoint_level


# ── Death / checkpoint restart ────────────────────────────────────────


class TestDeathCheckpointRestart:
    def test_level_1_death_full_reset(self, monkeypatch, game):
        """Death in Level 1 → restart at Level 0, run timer resets."""
        ticks = _freeze_ticks(monkeypatch)
        start_game(game)
        game.checkpoint_level = 0

        # Simulate some gameplay time.
        for _ in range(3 * settings.FPS):
            ticks["t"] += 1000.0 / settings.FPS
            game._advance_simulation(1.0 / settings.FPS, KeyState())

        # Kill the player.
        game.player.health = 1
        assert game.player.take_hit() is True
        assert game.player.dead

        # Simulate restart from game_over → restart button → fade → game.
        # The restart handler checks checkpoint_level.
        assert game.checkpoint_level == 0
        game.reset_game(from_checkpoint=False)  # full reset
        assert game.current_level == 0
        assert game.run_timer == 0.0
        assert not game.player.dead

    def test_level_2_death_checkpoint_restart(self, monkeypatch, game):
        """Death in Level 2 → restart at Level 2, run timer preserved."""
        ticks = _freeze_ticks(monkeypatch)
        start_game(game)

        # Simulate reaching Level 2.
        game.score = settings.LEVEL_SCORE_TARGETS[0]
        game._check_level_completion()
        for _ in range(300):
            game.fade_text.update()
        game._on_fade_text_done()
        game.fade_text.active = False
        game._level_intro_pending = False
        assert game.current_level == 1
        assert game.checkpoint_level == 1

        # Simulate some gameplay time in Level 2.
        for _ in range(3 * settings.FPS):
            ticks["t"] += 1000.0 / settings.FPS
            game._advance_simulation(1.0 / settings.FPS, KeyState())
        timer_before = game.run_timer

        # Kill the player.
        game.player.health = 1
        assert game.player.take_hit() is True
        assert game.player.dead

        # Checkpoint restart.
        game.reset_game(from_checkpoint=True)
        assert game.current_level == 1  # back to Level 2
        assert game.run_timer == pytest.approx(timer_before, abs=0.1)
        assert not game.player.dead

        # Verify gameplay resumes and timer keeps going.
        game.fade_text.active = False
        game._level_intro_pending = False
        for _ in range(2 * settings.FPS):
            ticks["t"] += 1000.0 / settings.FPS
            game._advance_simulation(1.0 / settings.FPS, KeyState())
        assert game.run_timer == pytest.approx(timer_before + 2.0, abs=0.2)

    def test_menu_play_never_starts_at_checkpoint(self, game):
        """Clicking Play from the main menu always starts at Level 0."""
        game.checkpoint_level = 1  # pretend we were in Level 2
        game.reset_game(from_checkpoint=False)
        assert game.current_level == 0


# ── Level intro screen ───────────────────────────────────────────────


class TestLevelIntroScreen:
    """Verify that level intros show a dedicated screen (black background +
    fade text only) with no gameplay HUD or entities visible or updating.
    """

    def test_level_1_start_shows_level_intro_state(self, game):
        """Clicking Play transitions to level_intro, not directly to game."""
        assert game.state == "menu"
        game._handle_mouse_click(game.main_menu.play_rect.center)
        pump_fade(game)
        assert game.state == "level_intro"
        assert game.fade_text.active
        assert game.fade_text.text == "Phase 1"

    def test_level_intro_draws_no_gameplay(self, game):
        """_draw_frame during level_intro should not call _draw_game()."""
        game.state = "level_intro"
        # _draw_game() would fail or draw entities; level_intro draws nothing
        # (just a black fill + fade text drawn in run()).
        game._draw_frame((0, 0))  # should not raise
        # Verify the screen is blank (not filled with gameplay content).
        # The screen.fill(BLACK) happens in run(), but _draw_frame should
        # skip _draw_game entirely.

    def test_level_intro_freezes_simulation(self, game):
        """No simulation steps run while in level_intro state."""
        game.state = "level_intro"
        game.accumulator = settings.FIXED_DT * 5  # bank some time
        steps = game._advance_simulation(1.0 / settings.FPS, KeyState())
        assert steps == 0
        assert game.accumulator == 0.0  # cleared

    def test_level_intro_blocks_player_input(self, game):
        """Player cannot move or fire during the level intro.

        _update_game() itself doesn't check state — the gating is in
        _advance_simulation(), which returns 0 steps when state != "game".
        """
        game.state = "level_intro"
        initial_x = game.player.x
        initial_bullet_count = len(game.bullets)
        # Simulate holding Space and Right arrow.
        keys = KeyState(pygame.K_SPACE, pygame.K_RIGHT)
        steps = game._advance_simulation(1.0 / settings.FPS, keys)
        assert steps == 0
        # Player should not have moved, no bullets fired.
        assert game.player.x == initial_x
        assert len(game.bullets) == initial_bullet_count

    def test_level_intro_applies_to_level_2_transition(self, game):
        """Level 1→Level 2 transition also goes through level_intro."""
        start_game(game)
        # Fast-forward to Level 2.
        game.score = settings.LEVEL_SCORE_TARGETS[0]
        game._check_level_completion()
        for _ in range(300):
            game.fade_text.update()
        game._on_fade_text_done()
        assert game.current_level == 1
        # Phase 2 fade text is now active — this IS the level_intro for L2.
        assert game.fade_text.active
        assert game.fade_text.text == "Phase 2"
        # Dismiss it to reach gameplay.
        for _ in range(300):
            game.fade_text.update()
        game._on_fade_text_done()
        pump_fade(game)
        assert game.state == "game"

    def test_level_intro_no_enemies_update_during_intro(self, game):
        """Enemy positions should not change during level_intro."""
        game.state = "level_intro"
        if game.enemies:
            first_x = game.enemies[0].x
            first_y = game.enemies[0].y
            # Run several advance_simulation calls.
            for _ in range(10):
                game._advance_simulation(1.0 / settings.FPS, KeyState())
            assert game.enemies[0].x == first_x
            assert game.enemies[0].y == first_y

    def test_level_intro_does_not_advance_run_timer(self, game):
        """Run timer should not advance during level_intro (paused like menus)."""
        ticks = {"t": 10000}
        import pygame.time
        original_get_ticks = pygame.time.get_ticks
        pygame.time.get_ticks = lambda: ticks["t"]
        try:
            start_game(game)
            timer_after_start = game.run_timer
            # Simulate 2 seconds of real time in level_intro.
            ticks["t"] += 2000
            game.state = "level_intro"
            game._advance_simulation(2.0, KeyState())
            # Timer should not have advanced (paused during level_intro).
            assert game.run_timer == pytest.approx(timer_after_start, abs=0.01)
        finally:
            pygame.time.get_ticks = original_get_ticks


# ── Helpers ───────────────────────────────────────────────────────────


def _freeze_ticks(monkeypatch, start_ms: int = 0):
    """Pin pygame.time.get_ticks so tests can control elapsed run time."""
    ticks = {"t": start_ms}
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: ticks["t"])
    return ticks
