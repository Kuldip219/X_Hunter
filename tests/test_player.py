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
