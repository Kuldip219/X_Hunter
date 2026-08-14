"""Delta-time conversion: gameplay speed must be independent of frame rate.

All movement is now px/second scaled by per-frame dt, and the gameplay
timers (fire cooldown, i-frames) are seconds-based too. These tests pin:

- same displacement per simulated second at 30 fps vs 60 fps,
- the MAX_FRAME_DT clamp capping movement after a huge dt spike,
- the new px/s constants reproducing the old px/frame motion at 60 FPS,
- fire cadence and the i-frame window expiring on real time, not frames.
"""

import pytest
import pygame

import settings
from bullet import Bullet
from enemy import Enemy
from player import Player
from helpers import KeyState, start_game


# --------------------------------------------------------------------- #
# Movement is frame-rate independent
# --------------------------------------------------------------------- #

def test_player_moves_same_distance_at_30_and_60_fps():
    # 1 simulated second at 60 fps (60 frames of 1/60 s)...
    a = Player(100, 600)
    for _ in range(60):
        a.handle_input(KeyState(pygame.K_RIGHT), 1.0 / 60)
        a.clamp_to_screen(settings.WIDTH)

    # ...versus 1 second at 30 fps (30 frames of 1/30 s).
    b = Player(100, 600)
    for _ in range(30):
        b.handle_input(KeyState(pygame.K_RIGHT), 1.0 / 30)
        b.clamp_to_screen(settings.WIDTH)

    assert a.x == pytest.approx(b.x, abs=0.01)
    # Both moved exactly speed (px/s) * 1 s.
    assert a.x == pytest.approx(100 + settings.PLAYER_SPEED_PER_SEC, abs=0.01)


def test_enemy_and_bullet_same_distance_at_30_and_60_fps():
    e60 = Enemy(0, 0)
    b60 = Bullet(0, 1000)
    for _ in range(60):
        e60.update(1.0 / 60)
        b60.update(1.0 / 60)

    e30 = Enemy(0, 0)
    b30 = Bullet(0, 1000)
    for _ in range(30):
        e30.update(1.0 / 30)
        b30.update(1.0 / 30)

    assert e60.y == pytest.approx(e30.y, abs=0.01)
    assert e60.y == pytest.approx(settings.ENEMY_SPEED_PER_SEC, abs=0.01)
    assert b60.y == pytest.approx(b30.y, abs=0.01)


# --------------------------------------------------------------------- #
# dt clamping
# --------------------------------------------------------------------- #

def test_dt_clamp_caps_movement_after_large_spike(game):
    start_game(game)
    p = game.player
    p.x, p.y = 100, 600
    game.enemies = []

    # A 1 s dt spike (e.g. a breakpoint pause or tab switch) must move the
    # player only MAX_FRAME_DT worth, not a full second.
    game._update_game(KeyState(pygame.K_RIGHT), dt=1.0)
    assert p.x == pytest.approx(
        100 + settings.PLAYER_SPEED_PER_SEC * settings.MAX_FRAME_DT, abs=0.001
    )

    # Multiple spiked frames still only accrue the capped amount each.
    x0 = p.x
    for _ in range(5):
        game._update_game(KeyState(pygame.K_RIGHT), dt=1.0)
    assert p.x == pytest.approx(
        x0 + 5 * settings.PLAYER_SPEED_PER_SEC * settings.MAX_FRAME_DT, abs=0.001
    )


# --------------------------------------------------------------------- #
# Old px/frame feel preserved at the target FPS (regression check)
# --------------------------------------------------------------------- #

def test_px_per_second_constants_match_old_px_per_frame_at_target_fps():
    # Old frame-based values (px/frame) this conversion preserves at 60 FPS:
    # new px/s must equal old px/frame * FPS exactly.
    old_per_frame = {
        settings.PLAYER_SPEED_PER_SEC: 5,
        settings.ENEMY_SPEED_PER_SEC: 5,
        settings.BULLET_SPEED_PER_SEC: 10,
        settings.ENEMY_SPEED_GAIN_PER_SEC: 4,
        settings.ENEMY_MAX_SPEED_PER_SEC: 9,
    }
    for per_sec, per_frame in old_per_frame.items():
        assert per_sec == per_frame * settings.FPS


def test_motion_matches_old_per_frame_behavior_at_target_fps():
    # One frame at 60 FPS under the new scheme moves exactly as far as one
    # frame of the old px/frame scheme did.
    e = Enemy(0, 0)
    e.update(1.0 / settings.FPS)
    assert e.y == 5.0  # old ENEMY_SPEED

    b = Bullet(0, 100)
    b.update(1.0 / settings.FPS)
    assert b.y == 90.0  # old BULLET_SPEED = 10, moving up

    p = Player(100, 600)
    p.handle_input(KeyState(pygame.K_RIGHT), 1.0 / settings.FPS)
    assert p.x == 105.0  # old PLAYER_SPEED = 5


# --------------------------------------------------------------------- #
# Timers are real-time based, not frame-counted
# --------------------------------------------------------------------- #

def test_fire_cadence_same_shots_per_second_at_30_and_60_fps(game):
    start_game(game)
    keys = KeyState(pygame.K_SPACE)

    def parked_field(game):
        # The difficulty ramp re-fills an empty enemy list with random spawns
        # that could consume bullets mid-count; park a full field far above
        # the action instead (deterministic, no collisions possible).
        game.enemies = [
            Enemy(0, -2000) for _ in range(settings.INITIAL_ENEMY_COUNT)
        ]
        game.player.y = 600
        game.bullets = []

    # 1 simulated second of holding fire at 60 fps: shots at t = 0, .2, .4,
    # .6, .8 s -> 5 bullets.
    parked_field(game)
    for _ in range(60):
        game._update_game(keys, dt=1.0 / 60)
    shots_60 = len(game.bullets)

    # 1 simulated second at 30 fps: same cadence in real time -> 5 bullets.
    game.reset_game()
    parked_field(game)
    for _ in range(30):
        game._update_game(keys, dt=1.0 / 30)
    shots_30 = len(game.bullets)

    assert shots_60 == shots_30 == 5
    # No burst-fire at any frame rate: the cooldown is seconds, not frames.
    assert shots_60 <= settings.FPS * settings.PLAYER_FIRE_COOLDOWN_SECONDS


def test_iframe_window_expires_on_real_time_not_frames():
    p = Player(100, 100)
    p.health = 3
    assert p.take_hit() is True
    assert p.invulnerable

    # Half the window at 60 fps (0.5 s of updates)...
    for _ in range(30):
        p.update_invulnerability(1.0 / 60)
    assert p.invulnerable

    # ...then the other half at 30 fps (0.5 s). Window fully expired.
    for _ in range(15):
        p.update_invulnerability(1.0 / 30)
    assert p.invulnerable_timer == 0.0
    assert not p.invulnerable
