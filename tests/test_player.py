"""Player movement and screen-edge clamping."""

import pytest
import pygame

import settings
from helpers import KeyState, reach_boss, start_game, wait_for_boss_active


def test_clamp_at_left_edge(game):
    start_game(game)
    game.player.x = -100
    game.player.clamp_to_screen(settings.WIDTH, settings.HEIGHT, settings.PLAYER_TOP_BOUND)
    assert game.player.x == 0


def test_clamp_at_right_edge(game):
    start_game(game)
    game.player.x = settings.WIDTH + 100
    game.player.clamp_to_screen(settings.WIDTH, settings.HEIGHT, settings.PLAYER_TOP_BOUND)
    assert game.player.x == settings.WIDTH - game.player.width


def test_holding_left_moves_and_clamps_at_zero(game):
    start_game(game)
    p = game.player
    game.enemies = []  # keep the frame free of collisions
    p.y = 600
    p.x = 5
    for _ in range(10):
        game._update_game(KeyState(pygame.K_LEFT))
    assert p.x == 0
    assert not p.invulnerable  # never collided with anything


def test_holding_right_moves_and_clamps_at_right_edge(game):
    start_game(game)
    p = game.player
    game.enemies = []
    p.y = 600
    p.x = settings.WIDTH - p.width - 5
    for _ in range(10):
        game._update_game(KeyState(pygame.K_RIGHT))
    assert p.x == settings.WIDTH - p.width


def test_pressing_both_keys_does_not_move(game):
    start_game(game)
    p = game.player
    game.enemies = []
    p.y = 600
    p.x = 200
    game._update_game(KeyState(pygame.K_LEFT, pygame.K_RIGHT))
    assert p.x == 200


def test_single_tap_fires_once(game):
    start_game(game)
    p = game.player
    game.enemies = []
    p.y = 600
    # One frame of Space held = one shot (hold-to-fire, not auto-repeat).
    game._update_game(KeyState(pygame.K_SPACE))
    assert len(game.bullets) == 1
    # Releasing Space means no further shots, even after many frames.
    for _ in range(30):
        game._update_game(KeyState())
    assert len(game.bullets) == 1


def test_fire_cooldown_gates_rapid_fire(game):
    start_game(game)
    p = game.player
    game.enemies = []
    p.y = 600
    keys = KeyState(pygame.K_SPACE)
    # Frames 0..COOLDOWN-1: only the first shot fires; the cooldown blocks
    # the rest while Space stays held. The cooldown is seconds-based, so the
    # test steps at the target FPS (default dt = 1/60 s per frame).
    cooldown_frames = int(round(settings.PLAYER_FIRE_COOLDOWN_SECONDS * settings.FPS))
    for _ in range(cooldown_frames):
        game._update_game(keys)
    assert len(game.bullets) == 1
    # The frame the cooldown expires, holding Space fires again.
    game._update_game(keys)
    assert len(game.bullets) == 2


def test_holding_space_fires_at_cooldown_cadence(game):
    start_game(game)
    p = game.player
    game.enemies = []
    p.y = 600
    keys = KeyState(pygame.K_SPACE)
    for _ in range(25):
        game._update_game(keys)
    # Shots land on frames 0, 12, 24 -> 3 bullets at 12-frame intervals.
    assert len(game.bullets) == 3


def test_firing_blocked_while_dead(game):
    start_game(game)
    p = game.player
    p.health = 1
    assert p.take_hit() is True
    assert p.dead
    # Holding Space while dead must never produce a bullet (H1 gating).
    for _ in range(10):
        game._update_game(KeyState(pygame.K_SPACE))
    assert game.bullets == []


def test_holding_up_moves_up(game):
    start_game(game)
    p = game.player
    game.enemies = []
    p.x = 200
    p.y = 600.0
    for _ in range(10):
        game._update_game(KeyState(pygame.K_UP))
    # 10 fixed steps at PLAYER_SPEED_PER_SEC: dy = speed * dt * 10.
    expected = 600.0 - 10 * settings.PLAYER_SPEED_PER_SEC * settings.FIXED_DT
    assert abs(p.y - expected) <= 1e-6


def test_holding_down_moves_down(game):
    start_game(game)
    p = game.player
    game.enemies = []
    p.x = 200
    p.y = settings.HEIGHT - p.height - 10.0
    for _ in range(10):
        game._update_game(KeyState(pygame.K_DOWN))
    # Clamped at the bottom edge, so after 10 steps it should not exceed the
    # lower bound.
    expected_max = settings.HEIGHT - p.height + 1e-6
    assert p.y <= expected_max


def test_pressing_both_vertical_keys_does_not_move(game):
    start_game(game)
    p = game.player
    game.enemies = []
    p.x = 200
    p.y = 400.0
    game._update_game(KeyState(pygame.K_UP, pygame.K_DOWN))
    assert p.y == pytest.approx(400.0)


def test_diag_movement_is_additive(game):
    start_game(game)
    p = game.player
    game.enemies = []
    p.x = 200.0
    p.y = settings.HEIGHT // 2
    game._update_game(KeyState(pygame.K_UP, pygame.K_LEFT))
    one_axis = settings.PLAYER_SPEED_PER_SEC * settings.FIXED_DT
    # No normalization: both axes contribute their full speed.
    assert p.x == pytest.approx(200.0 - one_axis)
    assert p.y == pytest.approx(settings.HEIGHT // 2 - one_axis)


# --------------------------------------------------------------------- #
# Vertical bounds
# --------------------------------------------------------------------- #


def _fly_to_the_top(game, keys=(pygame.K_UP,), frames: int = 400) -> None:
    """Hold `keys` until the ship stops moving. Enemy groups are cleared
    every frame so the run is about geometry, never collisions."""
    for _ in range(frames):
        game.enemies = []
        game.gunners = []
        game.player.shield_timer = 99.0  # never die on the way up
        game._update_game(KeyState(*keys))


def test_cannot_move_above_the_upper_bound(game):
    """Holding Up stops with the ship's TOP edge at PLAYER_TOP_BOUND."""
    start_game(game)
    p = game.player
    _fly_to_the_top(game)
    assert p.y == settings.PLAYER_TOP_BOUND


def test_cannot_move_below_the_lower_bound(game):
    """Holding Down stops with the ship's BOTTOM edge on the screen bottom."""
    start_game(game)
    p = game.player
    _fly_to_the_top(game, keys=(pygame.K_DOWN,))
    assert p.y == settings.HEIGHT - p.height


def test_upper_bound_keeps_the_ship_clear_of_the_hud(game):
    """At the bound - and at the left edge, where the top-left HUD lives -
    the ship must not overlap the health bar or either power-up status row.

    This is the guarantee the spec asks for ("stop just below the HUD"); an
    earlier version bounded the ship's bottom edge instead, which let the
    hull ride up level with the status timers.
    """
    start_game(game)
    p = game.player
    game.enemies = []
    # Keep both timed power-ups up so both status rows are really drawn.
    for _ in range(400):
        game.enemies = []
        game.gunners = []
        p.shield_timer = 99.0
        p.rapid_fire_timer = 99.0
        game._update_game(KeyState(pygame.K_UP, pygame.K_LEFT))
    assert p.y == settings.PLAYER_TOP_BOUND
    ship = p.get_rect()
    assert ship.left == 0, "the ship is at the left edge, under the HUD"

    health_bar = pygame.Rect(settings.PLAYER_HEALTH_POS, settings.HEALTH_IMG_SIZE)
    assert not ship.colliderect(health_bar)

    # The status rows exactly as _draw_powerup_status() places them.
    y = settings.POWERUP_STATUS_Y
    for text in ("SHIELD 99.0s", "RAPID FIRE 99.0s"):
        w, h = game.assets.font.size(text)
        row = pygame.Rect(settings.POWERUP_STATUS_X, y, w, h)
        assert not ship.colliderect(row), f"ship overlaps {text!r} row at {row}"
        y += settings.POWERUP_STATUS_ROW_GAP


def test_upper_bound_keeps_the_ship_clear_of_the_boss_health_bar(game):
    """The boss fight is the only time two HUD bars are on screen at once;
    the ship must stop below both of them there too."""
    reach_boss(game)
    assert wait_for_boss_active(game)
    assert game._boss_bar_visible()
    bar = game._boss_bar_rect()
    assert bar.bottom < settings.PLAYER_TOP_BOUND, "boss bar must sit above the bound"

    p = game.player
    for _ in range(400):
        game.enemies = []
        game.gunners = []
        game.enemy_bullets = []
        p.shield_timer = 99.0
        game._update_game(KeyState(pygame.K_UP, pygame.K_LEFT))
    assert p.y == settings.PLAYER_TOP_BOUND
    ship = p.get_rect()
    assert ship.left == 0
    assert not ship.colliderect(bar)
    assert not ship.colliderect(
        pygame.Rect(settings.PLAYER_HEALTH_POS, settings.HEALTH_IMG_SIZE)
    )


def test_diag_is_faster_than_cardinal(game):
    start_game(game)
    p = game.player
    game.enemies = []
    p.x = settings.WIDTH // 2
    p.y = settings.HEIGHT // 2
    game._update_game(KeyState(pygame.K_UP, pygame.K_LEFT))
    one_step_diag = (p.x, p.y)
    game._update_game(KeyState(pygame.K_UP, pygame.K_LEFT))
    two_step_diag = (p.x, p.y)
    # Reset and run pure cardinal.
    p.x, p.y = settings.WIDTH // 2, settings.HEIGHT // 2
    game._update_game(KeyState(pygame.K_UP))
    one_step_card = (p.x, p.y)
    game._update_game(KeyState(pygame.K_UP))
    two_step_card = (p.x, p.y)
    # Each stepped position is a real distance from the start. Two cardinal
    # steps of length L give distance 2L; two additive diagonal steps give
    # 2 * L * sqrt(2). So diag > cardinal.
    card_dist = (two_step_card[1] - settings.HEIGHT // 2) ** 2
    diag_dist = ((two_step_diag[0] - settings.WIDTH // 2) ** 2
                 + (two_step_diag[1] - settings.HEIGHT // 2) ** 2)
    assert diag_dist > card_dist
