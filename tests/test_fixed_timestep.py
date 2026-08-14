"""Fixed-timestep accumulator.

Game.run() banks real elapsed time (capped at MAX_FRAME_DT per rendered
frame) into an accumulator and drains it in constant FIXED_DT simulation
steps, so gameplay advances identically no matter how choppy or fast the
render rate is. These tests pin the accumulator's contract:

- choppy real frame times produce the same simulated time/displacement,
- a lag spike is capped before it enters the accumulator (no catch-up burst),
- one rendered frame can run multiple steps, or zero (render-only),
- time outside the "game" state never banks (no fast-forward on resume),
- the direct-drive _update_and_draw path still simulates exactly one step.
"""

import pygame
import pytest

import settings
from enemy import Enemy
from helpers import KeyState, start_game


def test_fixed_dt_is_60hz():
    assert settings.FIXED_DT == pytest.approx(1.0 / 60.0)


def _parked_field(game, speed: float = 50.0):
    """Put the player into a collision-free, non-clamping starting state."""
    game.enemies = [Enemy(0, -2000) for _ in range(settings.INITIAL_ENEMY_COUNT)]
    p = game.player
    p.speed = speed  # keep total displacement below the screen edge
    p.x, p.y = 100, 600
    game.bullets = []
    return p


def test_choppy_frame_times_produce_same_simulated_time(game):
    """~5 s of gameplay regardless of whether the real frames are uniform
    60 Hz or a choppy mix of slow (1/30) and fast (1/144) frame times."""
    start_game(game)
    keys = KeyState(pygame.K_RIGHT)

    speed = 50.0

    def run_pattern(dts, n):
        game.reset_game()
        p = _parked_field(game, speed=speed)
        steps = 0
        for i in range(n):
            steps += game._advance_simulation(dts[i % len(dts)], keys)
        return steps, p.x - 100  # displacement

    # Uniform 60 fps for 5 s: exactly 300 simulation steps.
    steps_u, dx_u = run_pattern([1.0 / settings.FPS], 300)
    assert steps_u == 300
    assert dx_u == pytest.approx(300 * speed * settings.FIXED_DT, abs=0.01)

    # Choppy: 124 pairs of (1/30 + 1/144) ~= 5.0 s of banked real time.
    # Each individual dt is under MAX_FRAME_DT, so nothing is clamped away.
    dts = [1.0 / 30, 1.0 / 144]
    steps_c, dx_c = run_pattern(dts, 248)

    # Same simulated seconds (within one FIXED_DT of leftover) -> same motion.
    assert steps_c == pytest.approx(steps_u, abs=2)
    assert dx_c == pytest.approx(dx_u, abs=2 * speed * settings.FIXED_DT)


def test_lag_spike_capped_before_accumulator(game):
    """A 1 s stall banks only MAX_FRAME_DT worth: ceil(0.05 / FIXED_DT) = 3
    catch-up steps, never a burst of dozens."""
    start_game(game)
    _parked_field(game)
    game.accumulator = 0.0

    steps = game._advance_simulation(1.0, KeyState())
    assert steps == 3
    assert game.accumulator == pytest.approx(0.0, abs=1e-9)

    # Even repeated spikes only add the capped amount each frame.
    total = 0
    for _ in range(10):
        total += game._advance_simulation(1.0, KeyState())
    assert total == 30


def test_multiple_steps_for_one_rendered_frame(game):
    start_game(game)
    p = _parked_field(game)
    keys = KeyState(pygame.K_RIGHT)

    # Bank 2.5 * FIXED_DT in a single rendered frame -> exactly 2 steps.
    steps = game._advance_simulation(2.5 * settings.FIXED_DT, keys)
    assert steps == 2
    assert game.accumulator == pytest.approx(0.5 * settings.FIXED_DT, abs=1e-9)
    # Two simulation steps of movement happened in that one render.
    assert p.x == pytest.approx(100 + 2 * p.speed * settings.FIXED_DT, abs=1e-9)


def test_zero_steps_render_only_frame(game):
    start_game(game)
    p = _parked_field(game)
    game.accumulator = 0.0

    # Bank less than one FIXED_DT: no simulation step this rendered frame.
    steps = game._advance_simulation(0.5 * settings.FIXED_DT, KeyState(pygame.K_RIGHT))
    assert steps == 0
    assert p.x == 100  # nothing moved; the frame renders only
    assert game.accumulator == pytest.approx(0.5 * settings.FIXED_DT, abs=1e-9)


def test_accumulator_cleared_outside_game_state(game):
    # The fixture starts in "menu": time must never bank while not simulating.
    assert game.state == "menu"
    steps = game._advance_simulation(5.0, KeyState())
    assert steps == 0
    assert game.accumulator == 0.0


def test_update_and_draw_simulates_exactly_one_step(game):
    """The direct-drive path (tests, preview autopilot) still simulates one
    60 Hz step per call even though run() now uses the accumulator."""
    start_game(game)
    p = _parked_field(game)

    real_get_pressed = pygame.key.get_pressed
    pygame.key.get_pressed = lambda: KeyState(pygame.K_RIGHT)
    try:
        game._update_and_draw((0, 0))
    finally:
        pygame.key.get_pressed = real_get_pressed

    assert p.x == pytest.approx(100 + p.speed * settings.FIXED_DT, abs=1e-9)
    assert game.accumulator == 0.0  # direct path doesn't touch the accumulator


def test_run_loop_executes_with_accumulator(game):
    """Smoke: run() completes a full iteration (bank -> step -> render ->
    fade) without error. A QUIT event posted before starting ends the loop
    after the first rendered frame."""
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    game.run()
    assert not game.running
