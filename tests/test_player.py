"""Player movement and screen-edge clamping."""

import pygame

import settings
from helpers import KeyState, start_game


def test_clamp_at_left_edge(game):
    start_game(game)
    game.player.x = -100
    game.player.clamp_to_screen(settings.WIDTH)
    assert game.player.x == 0


def test_clamp_at_right_edge(game):
    start_game(game)
    game.player.x = settings.WIDTH + 100
    game.player.clamp_to_screen(settings.WIDTH)
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
