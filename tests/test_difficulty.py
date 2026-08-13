"""Difficulty ramp: formula behaviour (monotonic, capped, both inputs
matter), enemy speed/count scaling through the real game loop, clean
reset on restart, and no interference with the death-freeze (H1)."""

import pygame

import settings
from difficulty import Difficulty
from helpers import KeyState, start_game


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

    assert game.enemies[0].speed == settings.ENEMY_SPEED  # baseline

    # Score alone at its saturated value (no time yet) -> halfway ramp.
    game.score = int(settings.DIFFICULTY_SCORE_TO_FULL)
    game._update_game(KeyState())
    expected = settings.ENEMY_SPEED + settings.ENEMY_SPEED_GAIN * settings.DIFFICULTY_SCORE_WEIGHT
    assert game.enemies[0].speed == expected

    # Time + score both saturated -> full ramp, capped at max speed.
    ticks["t"] = int(settings.DIFFICULTY_TIME_TO_FULL * 1000)
    game.score = int(settings.DIFFICULTY_SCORE_TO_FULL)
    game._update_game(KeyState())
    assert game.enemies[0].speed == settings.ENEMY_MAX_SPEED
    assert game.enemies[0].speed <= settings.ENEMY_MAX_SPEED


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
    assert speeds[-1] == settings.ENEMY_MAX_SPEED
    assert all(s <= settings.ENEMY_MAX_SPEED for s in speeds)


def test_difficulty_resets_on_restart(monkeypatch, game):
    ticks = _freeze_ticks(monkeypatch)
    start_game(game)
    ticks["t"] = int(settings.DIFFICULTY_TIME_TO_FULL * 1000)
    game.score = int(settings.DIFFICULTY_SCORE_TO_FULL)
    game._update_game(KeyState())
    assert len(game.enemies) == settings.ENEMY_MAX_COUNT
    assert game.enemies[0].speed == settings.ENEMY_MAX_SPEED

    # Restart (e.g. a new run): score resets and the clock restarts, so the
    # next frame is back at baseline - no carryover from the previous run.
    game.reset_game()
    assert game.score == 0
    game._update_game(KeyState())
    assert len(game.enemies) == settings.INITIAL_ENEMY_COUNT
    assert game.enemies[0].speed == settings.ENEMY_SPEED


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
    assert game.enemies[0].speed == settings.ENEMY_SPEED
    assert len(game.enemies) == settings.INITIAL_ENEMY_COUNT
