"""Hitbox/sprite alignment (H3).

Collision rects are built from the PLAYER_WIDTH/HEIGHT and
ENEMY_WIDTH/HEIGHT constants, while sprites are scaled to
PLAYER_IMG_SIZE / ENEMY_IMG_SIZE. These tests pin the two together so a
change to one without the other fails loudly. The rects are also checked
against the actually-loaded asset images (which are what the player sees).
"""

import pygame

import settings
from bullet import Bullet
from enemy import Enemy
from player import Player


def test_player_hitbox_matches_sprite_constants():
    p = Player(0, 0)
    w, h = p.get_rect().size
    assert (w, h) == settings.PLAYER_IMG_SIZE
    assert settings.PLAYER_WIDTH == settings.PLAYER_IMG_SIZE[0]
    assert settings.PLAYER_HEIGHT == settings.PLAYER_IMG_SIZE[1]
    # Authored 65x80, scaled to the live window by settings.px().
    assert settings.PLAYER_WIDTH == settings.px(65)
    assert settings.PLAYER_HEIGHT == settings.px(80)


def test_enemy_hitbox_matches_sprite_constants():
    e = Enemy(0, 0)
    w, h = e.get_rect().size
    assert (w, h) == settings.ENEMY_IMG_SIZE
    assert settings.ENEMY_WIDTH == settings.ENEMY_IMG_SIZE[0]
    assert settings.ENEMY_HEIGHT == settings.ENEMY_IMG_SIZE[1]
    # Authored 50x50, scaled to the live window by settings.px().
    assert settings.ENEMY_IMG_SIZE == (settings.px(50), settings.px(50))


def test_bullet_hitbox_is_rect_matching_sprite():
    b = Bullet(0, 0)
    assert isinstance(b.get_rect(), pygame.Rect)
    assert b.get_rect().size == settings.BULLET_IMG_SIZE
    # Authored 10x20, scaled to the live window by settings.px().
    assert settings.BULLET_IMG_SIZE == (settings.px(10), settings.px(20))


def test_rects_share_sprite_origin():
    """Rects must be centered on the sprite, i.e. share its top-left (x, y)
    origin -- growing a rect from a corner would drift the hitbox."""
    p = Player(123, 456)
    e = Enemy(234, 567)
    b = Bullet(345, 678)
    assert p.get_rect().topleft == (p.x, p.y)
    assert e.get_rect().topleft == (e.x, e.y)
    assert b.get_rect().topleft == (b.x, b.y)


def test_rendered_sprites_match_hitboxes(game):
    """The loaded, scaled sprites that get drawn must be exactly as big as
    the collision rects."""
    assert game.assets.player_img.get_size() == game.player.get_rect().size
    assert game.assets.enemy_img.get_size() == game.enemies[0].get_rect().size
    assert game.assets.bullet_img.get_size() == settings.BULLET_IMG_SIZE
