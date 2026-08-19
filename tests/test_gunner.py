"""Gunner enemy (Level 2), enemy bullets, and Level 2 gameplay flow.

Covers:
- GunnerEnemy: spawn, descend-to-stop, drift, fire-on-stop + cooldown.
- EnemyBullet: speed, direction, off-screen cleanup, shield blocking.
- Level 2 spawning: gunners only, no falling enemies.
- Player bullet vs gunner collision (scoring, explosion, power-up drop).
- Full Level 2 flow: Phase 2 intro → gameplay → gunners + bullets.
"""

import pytest
import pygame

import settings
from enemy import Enemy
from enemy_bullet import EnemyBullet
from gunner import GunnerEnemy
from helpers import KeyState, pump_fade, start_game


# ── GunnerEnemy unit tests ────────────────────────────────────────────


class TestGunnerEnemy:
    def test_descends_to_stop_y(self):
        g = GunnerEnemy(100, -600, settings.WIDTH)
        assert g.stopped is False
        # Simulate enough time to descend past stop_y (worst case ~7.3s at
        # 120 px/s from -600 to stop_y ~275).
        for _ in range(int(9 * settings.FPS)):
            g.update(1.0 / settings.FPS)
        assert g.stopped is True
        assert g.y == g.stop_y

    def test_stop_y_within_max_descent(self):
        for _ in range(50):
            g = GunnerEnemy(100, -600, settings.WIDTH)
            max_y = settings.HEIGHT * settings.GUNNER_MAX_DESCENT_FRACTION - g.height
            assert 0 <= g.stop_y <= max_y

    def test_drifts_side_to_side_when_stopped(self):
        g = GunnerEnemy(100, -100, settings.WIDTH)
        g.stopped = True
        g.y = g.stop_y
        initial_x = g.x
        for _ in range(60):
            g.update(1.0 / settings.FPS)
        assert g.x != initial_x  # moved horizontally

    def test_drift_bounces_off_edges(self):
        g = GunnerEnemy(5, -100, settings.WIDTH)
        g.stopped = True
        g.y = g.stop_y
        g.drift_dir = -1  # heading left
        g.drift_speed = 500  # fast enough to hit edge
        for _ in range(60):
            g.update(1.0 / settings.FPS)
        assert g.x >= 0  # clamped, didn't go negative
        assert g.drift_dir == 1  # bounced

    def test_can_fire_immediately_after_stopping(self):
        g = GunnerEnemy(100, -100, settings.WIDTH)
        # Force it to stop.
        g.y = g.stop_y
        g.stopped = True
        g.fire_cooldown = 0.0
        assert g.can_fire() is True

    def test_cooldown_after_firing(self):
        g = GunnerEnemy(100, -100, settings.WIDTH)
        g.stopped = True
        g.y = g.stop_y
        g.fire_cooldown = 0.0
        assert g.can_fire() is True
        g.reset_fire_cooldown()
        assert g.fire_cooldown == settings.GUNNER_FIRE_COOLDOWN_SECONDS
        assert g.can_fire() is False

    def test_can_fire_again_after_cooldown(self):
        g = GunnerEnemy(100, -100, settings.WIDTH)
        g.stopped = True
        g.y = g.stop_y
        g.reset_fire_cooldown()
        # Simulate enough time for cooldown to expire.
        for _ in range(int(settings.GUNNER_FIRE_COOLDOWN_SECONDS * settings.FPS) + 5):
            g.update(1.0 / settings.FPS)
        assert g.can_fire() is True

    def test_respawn_resets_state(self):
        g = GunnerEnemy(100, 500, settings.WIDTH)
        g.stopped = True
        g.fire_cooldown = 5.0
        g.respawn(settings.WIDTH)
        assert g.stopped is False
        assert g.fire_cooldown == 0.0
        assert g.y < 0  # above screen

    def test_get_rect_matches_position(self):
        g = GunnerEnemy(100, 200, settings.WIDTH)
        r = g.get_rect()
        assert r.x == 100
        assert r.y == 200
        assert r.width == settings.ENEMY_WIDTH
        assert r.height == settings.ENEMY_HEIGHT


# ── EnemyBullet unit tests ────────────────────────────────────────────


class TestEnemyBullet:
    def test_travels_downward(self):
        b = EnemyBullet(100, 100)
        initial_y = b.y
        b.update(1.0 / settings.FPS)
        assert b.y > initial_y

    def test_speed_matches_constant(self):
        b = EnemyBullet(100, 100)
        b.update(1.0)  # 1 second
        assert b.y == pytest.approx(100 + settings.ENEMY_BULLET_SPEED_PER_SEC, abs=0.1)

    def test_off_screen_below_threshold(self):
        b = EnemyBullet(100, settings.ENEMY_BULLET_OFFSCREEN_Y + 1)
        assert b.off_screen is True

    def test_not_off_screen_above_threshold(self):
        b = EnemyBullet(100, 0)
        assert b.off_screen is False

    def test_get_rect_matches_size(self):
        b = EnemyBullet(50, 50)
        r = b.get_rect()
        assert r.width == settings.ENEMY_BULLET_IMG_SIZE[0]
        assert r.height == settings.ENEMY_BULLET_IMG_SIZE[1]


# ── Level 2 spawning ─────────────────────────────────────────────────


class TestLevel2Spawning:
    def test_level_2_spawns_gunners_not_enemies(self, game):
        start_game(game)
        # Fast-forward to Level 2.
        game.score = settings.LEVEL_SCORE_TARGETS[0]
        game._check_level_completion()
        for _ in range(200):
            game.fade_text.update()
        game._on_fade_text_done()
        game.fade_text.active = False
        game._level_intro_pending = False

        assert game.current_level == 1
        assert len(game.gunners) > 0
        assert len(game.enemies) == 0

    def test_level_1_has_enemies_not_gunners(self, game):
        start_game(game)
        assert game.current_level == 0
        assert len(game.enemies) > 0
        assert len(game.gunners) == 0

    def test_level_1_never_spawns_gunners_during_gameplay(self, game):
        """After multiple update cycles in Level 1, no gunners appear."""
        start_game(game)
        # Clear fade text so gameplay runs.
        game.fade_text.active = False
        game._level_intro_pending = False
        assert game.current_level == 0

        for _ in range(300):
            game._update_game(KeyState(), 1.0 / settings.FPS)

        assert len(game.enemies) > 0
        assert len(game.gunners) == 0, (
            f"Level 1 should have 0 gunners, got {len(game.gunners)}"
        )

    def test_level_2_never_spawns_enemies_during_gameplay(self, game):
        """After multiple update cycles in Level 2, no falling enemies appear."""
        start_game(game)
        # Fast-forward to Level 2.
        game.score = settings.LEVEL_SCORE_TARGETS[0]
        game._check_level_completion()
        for _ in range(200):
            game.fade_text.update()
        game._on_fade_text_done()
        game.fade_text.active = False
        game._level_intro_pending = False
        assert game.current_level == 1

        for _ in range(300):
            game._update_game(KeyState(), 1.0 / settings.FPS)

        assert len(game.gunners) > 0
        assert len(game.enemies) == 0, (
            f"Level 2 should have 0 falling enemies, got {len(game.enemies)}"
        )


# ── Enemy bullet interactions ─────────────────────────────────────────


class TestEnemyBulletInteractions:
    def test_shield_blocks_enemy_bullet(self, game):
        start_game(game)
        # Place an enemy bullet right on the player.
        p = game.player
        game.enemy_bullets = [EnemyBullet(p.x + 10, p.y + 10)]
        game.player.apply_powerup(settings.POWERUP_KIND_SHIELD)
        initial_health = game.player.health

        game._update_game(KeyState(), 1.0 / settings.FPS)
        assert game.player.health == initial_health  # no damage
        assert len(game.enemy_bullets) == 0  # bullet absorbed

    def test_enemy_bullet_deals_damage_without_shield(self, game):
        start_game(game)
        p = game.player
        initial_health = p.health
        game.enemy_bullets = [EnemyBullet(p.x + 10, p.y + 10)]

        game._update_game(KeyState(), 1.0 / settings.FPS)
        assert p.health == initial_health - 1
        assert len(game.enemy_bullets) == 0  # bullet consumed

    def test_enemy_bullet_triggers_iframes(self, game):
        start_game(game)
        p = game.player
        game.enemy_bullets = [EnemyBullet(p.x + 10, p.y + 10)]

        game._update_game(KeyState(), 1.0 / settings.FPS)
        assert p.invulnerable is True

    def test_enemy_bullet_removed_off_screen(self, game):
        start_game(game)
        game.enemy_bullets = [EnemyBullet(100, settings.ENEMY_BULLET_OFFSCREEN_Y + 10)]
        game._update_game(KeyState(), 1.0 / settings.FPS)
        assert len(game.enemy_bullets) == 0


# ── Gunner firing in game loop ────────────────────────────────────────


class TestGunnerFiring:
    def test_gunner_creates_enemy_bullets(self, game):
        start_game(game)
        # Fast-forward to Level 2.
        game.score = settings.LEVEL_SCORE_TARGETS[0]
        game._check_level_completion()
        for _ in range(200):
            game.fade_text.update()
        game._on_fade_text_done()
        game.fade_text.active = False
        game._level_intro_pending = False

        # Place a gunner at its stop position, ready to fire.
        g = game.gunners[0]
        g.y = g.stop_y
        g.stopped = True
        g.fire_cooldown = 0.0

        game._update_game(KeyState(), 1.0 / settings.FPS)
        assert len(game.enemy_bullets) >= 1

    def test_player_bullet_destroys_gunner(self, game):
        start_game(game)
        # Fast-forward to Level 2.
        game.score = settings.LEVEL_SCORE_TARGETS[0]
        game._check_level_completion()
        for _ in range(200):
            game.fade_text.update()
        game._on_fade_text_done()
        game.fade_text.active = False
        game._level_intro_pending = False

        # Place a gunner well above the player (player top = y=720, so
        # gunner bottom must be below 720 to avoid gunner-player collision
        # which would respawn it before the bullet check runs).
        p = game.player
        g = game.gunners[0]
        g.x = p.x
        g.y = 300  # well above player
        g.stopped = True
        g.drift_speed = 0  # prevent drifting away before collision check
        g.fire_cooldown = 999  # prevent firing

        # Place a player bullet just below the gunner so after one frame
        # of upward movement it overlaps.
        game.bullets = [game.player.spawn_bullet()]
        game.bullets[0].y = g.y + 10

        old_score = game.score
        game._update_game(KeyState(), 1.0 / settings.FPS)
        assert game.score == old_score + 1
