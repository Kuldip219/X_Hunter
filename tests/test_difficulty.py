"""Difficulty ramp: formula behaviour (monotonic, capped, both inputs
matter), enemy speed/count scaling through the real game loop, clean
reset on restart, and no interference with the death-freeze (H1)."""

import pytest
import pygame

import settings
from difficulty import Difficulty
from enemy import Enemy
from helpers import KeyState, pump_fade, start_game


def test_difficulty_starts_at_zero():
    assert Difficulty().value(0, 0) == 0.0


def test_difficulty_is_non_decreasing_with_time():
    d = Difficulty()
    prev = 0.0
    for t in range(0, int(settings.DIFFICULTY_TIME_TO_FULL) + 30, 10):
        v = d.value(0, t)
        assert v >= prev
        prev = v


def test_difficulty_is_non_decreasing_with_score():
    d = Difficulty()
    prev = 0.0
    for s in range(0, int(settings.DIFFICULTY_SCORE_TO_FULL) + 5, 5):
        v = d.value(s, 0)
        assert v >= prev
        prev = v


def test_both_inputs_matter():
    """Survival or scoring alone each reach only their weighted share;
    both together reach the cap."""
    d = Difficulty()
    assert d.value(0, settings.DIFFICULTY_TIME_TO_FULL) == settings.DIFFICULTY_TIME_WEIGHT
    assert d.value(settings.DIFFICULTY_SCORE_TO_FULL, 0) == settings.DIFFICULTY_SCORE_WEIGHT
    assert (
        d.value(settings.DIFFICULTY_SCORE_TO_FULL, settings.DIFFICULTY_TIME_TO_FULL)
        == settings.DIFFICULTY_MAX
    )


def test_difficulty_capped_at_max_for_extreme_inputs():
    d = Difficulty()
    extreme = d.value(10_000, 1_000_000)
    assert extreme == settings.DIFFICULTY_MAX
    assert extreme <= settings.DIFFICULTY_MAX
    assert 0.0 <= extreme <= settings.DIFFICULTY_MAX


def _freeze_ticks(monkeypatch, start_ms: int = 0):
    """Pin pygame.time.get_ticks so tests can control elapsed run time."""
    ticks = {"t": start_ms}
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: ticks["t"])
    return ticks


def test_enemy_speed_scales_with_difficulty(monkeypatch, game):
    ticks = _freeze_ticks(monkeypatch)
    start_game(game)  # reset_game sets run_start_ticks = 0

    assert game.enemies[0].speed == settings.ENEMY_SPEED_PER_SEC  # baseline

    # Score alone at its saturated value (no time yet) -> halfway ramp.
    game.score = int(settings.DIFFICULTY_SCORE_TO_FULL)
    game._update_game(KeyState())
    expected = settings.ENEMY_SPEED_PER_SEC + settings.ENEMY_SPEED_GAIN_PER_SEC * settings.DIFFICULTY_SCORE_WEIGHT
    assert game.enemies[0].speed == expected

    # Time + score both saturated -> full ramp, capped at max speed.
    ticks["t"] = int(settings.DIFFICULTY_TIME_TO_FULL * 1000)
    game.score = int(settings.DIFFICULTY_SCORE_TO_FULL)
    game._update_game(KeyState())
    assert game.enemies[0].speed == settings.ENEMY_MAX_SPEED_PER_SEC
    assert game.enemies[0].speed <= settings.ENEMY_MAX_SPEED_PER_SEC


def test_enemy_count_scales_with_difficulty(monkeypatch, game):
    ticks = _freeze_ticks(monkeypatch)
    start_game(game)
    assert len(game.enemies) == settings.INITIAL_ENEMY_COUNT

    ticks["t"] = int(settings.DIFFICULTY_TIME_TO_FULL * 1000)
    game.score = int(settings.DIFFICULTY_SCORE_TO_FULL)
    game._update_game(KeyState())
    assert len(game.enemies) == settings.ENEMY_MAX_COUNT
    assert len(game.enemies) <= settings.ENEMY_MAX_COUNT


def test_speed_ramps_smoothly_and_stays_capped(monkeypatch, game):
    ticks = _freeze_ticks(monkeypatch)
    start_game(game)
    speeds = []
    for step in range(10):
        ticks["t"] = step * int(settings.DIFFICULTY_TIME_TO_FULL * 1000 / 9)
        game.score = int(settings.DIFFICULTY_SCORE_TO_FULL * step / 9)
        game._update_game(KeyState())
        speeds.append(game.enemies[0].speed)
    assert speeds == sorted(speeds)  # non-decreasing over the ramp
    assert speeds[-1] == settings.ENEMY_MAX_SPEED_PER_SEC
    assert all(s <= settings.ENEMY_MAX_SPEED_PER_SEC for s in speeds)


def test_difficulty_resets_on_restart(monkeypatch, game):
    ticks = _freeze_ticks(monkeypatch)
    start_game(game)
    ticks["t"] = int(settings.DIFFICULTY_TIME_TO_FULL * 1000)
    game.score = int(settings.DIFFICULTY_SCORE_TO_FULL)
    game._update_game(KeyState())
    assert len(game.enemies) == settings.ENEMY_MAX_COUNT
    assert game.enemies[0].speed == settings.ENEMY_MAX_SPEED_PER_SEC

    # Restart (e.g. a new run): score resets and the clock restarts, so the
    # next frame is back at baseline - no carryover from the previous run.
    game.reset_game()
    assert game.score == 0
    game._update_game(KeyState())
    assert len(game.enemies) == settings.INITIAL_ENEMY_COUNT
    assert game.enemies[0].speed == settings.ENEMY_SPEED_PER_SEC


def test_difficulty_frozen_while_dead(monkeypatch, game):
    """The ramp must not run during the death sequence (H1 interplay)."""
    ticks = _freeze_ticks(monkeypatch)
    start_game(game)
    p = game.player
    p.health = 1
    assert p.take_hit() is True
    assert p.dead

    ticks["t"] = int(settings.DIFFICULTY_TIME_TO_FULL * 1000)
    game.score = int(settings.DIFFICULTY_SCORE_TO_FULL)
    game._update_game(KeyState())  # early-return: no difficulty scaling
    assert game.enemies[0].speed == settings.ENEMY_SPEED_PER_SEC
    assert len(game.enemies) == settings.INITIAL_ENEMY_COUNT


def test_difficulty_clock_frozen_while_paused(monkeypatch, game):
    """The elapsed-time half of the ramp must not advance while paused.

    Mirrors the fixed-timestep accumulator: real wall time spent outside the
    "game" state is banked (paused_ms) and subtracted from the difficulty
    clock, so a 30 s pause adds zero seconds to the ramp, and the clock
    resumes from where it froze once unpaused.
    """
    ticks = _freeze_ticks(monkeypatch)
    start_game(game)
    # Collision-free field so the long simulated run can't kill the player.
    game.enemies = [Enemy(0, -2000) for _ in range(settings.INITIAL_ENEMY_COUNT)]
    game.score = 0  # isolate the time half of the formula

    def elapsed() -> float:
        # The game computes elapsed identically inside _update_game.
        return (ticks["t"] - game.run_start_ticks - game.paused_ms) / 1000.0

    def run(seconds: float) -> None:
        # Advance get_ticks in exact sync with the raw_dt passed to
        # _advance_simulation (1000/FPS ms per 1/FPS s frame), so the clock
        # and the accumulator bank precisely the same time.
        for _ in range(int(round(seconds * settings.FPS))):
            ticks["t"] += 1000.0 / settings.FPS
            game._advance_simulation(1.0 / settings.FPS, KeyState())

    # 10 s of gameplay: the clock runs and the ramp starts climbing.
    run(10)
    assert elapsed() == pytest.approx(10.0, abs=0.05)
    speed_before = game.enemies[0].speed
    assert speed_before > settings.ENEMY_SPEED_PER_SEC  # ramp has begun

    # Pause (ESC) and let 30 s of real time pass while paused.
    game._handle_keydown(pygame.K_ESCAPE)
    pump_fade(game)
    assert game.state == "pause"
    for _ in range(30 * settings.FPS):
        ticks["t"] += 1000.0 / settings.FPS
        game._advance_simulation(1.0 / settings.FPS, KeyState())

    # The clock did NOT advance during the pause.
    assert elapsed() == pytest.approx(10.0, abs=0.05)

    # Unpause (ESC): the clock resumes from where it froze, not from +30 s.
    game._handle_keydown(pygame.K_ESCAPE)
    pump_fade(game)
    assert game.state == "game"
    run(5)
    assert elapsed() == pytest.approx(15.0, abs=0.05)
    speed_after = game.enemies[0].speed
    assert speed_after > speed_before  # ramp resumes climbing after unpause
