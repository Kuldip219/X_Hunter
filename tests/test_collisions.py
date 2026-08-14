"""Bullet-enemy and player-enemy collisions.

These drive the real _update_game() loop (not the raw methods), so they
cover the full frame: bullet/enemy movement, the collision checks, score,
respawn, and explosion spawning.
"""

import settings
from bullet import Bullet
from enemy import Enemy
from helpers import KeyState, place_enemy_over_player, start_game


def test_bullet_enemy_collision_scores_and_respawns(game):
    start_game(game)
    e = Enemy(200, 300)
    game.enemies = [e]
    # Bullet placed inside the enemy's body; after one frame the enemy moves
    # down 5px and the bullet up 10px, still overlapping.
    game.bullets = [Bullet(220, 320)]

    score0, explosions0 = game.score, len(game.explosions)
    game._update_game(KeyState())

    assert game.score == score0 + 1
    assert len(game.bullets) == 0  # bullet consumed
    assert len(game.explosions) == explosions0 + 1  # explosion spawned
    # Enemy respawned back at the top of the screen, fully on-screen.
    assert settings.RESPAWN_ENEMY_MIN_Y <= e.y <= settings.RESPAWN_ENEMY_MAX_Y
    assert 0 <= e.x <= settings.WIDTH - e.width


def test_bullet_enemy_edge_overlap_hits(game):
    # The H3/L1 fix: a bullet overlapping the enemy's edge by 1px now hits
    # (a strict point-in-rect test used to miss this).
    start_game(game)
    e = Enemy(200, 300)
    game.enemies = [e]
    game.bullets = [Bullet(249, 320)]  # 1px overlap on the enemy's right edge
    score0 = game.score
    game._update_game(KeyState())
    assert game.score == score0 + 1


def test_bullet_enemy_collision_requires_overlap(game):
    start_game(game)
    e = Enemy(200, 300)
    game.enemies = [e]
    # Bullet 1px clear of the enemy's right edge (enemy spans x 200..250).
    game.bullets = [Bullet(251, 320)]
    score0 = game.score
    game._update_game(KeyState())
    assert game.score == score0
    assert len(game.bullets) == 1


def test_player_enemy_collision_applies_damage_once(game):
    start_game(game)
    p = game.player
    p.health = settings.PLAYER_START_HEALTH
    e = place_enemy_over_player(game)

    hp = p.health
    game._update_game(KeyState())
    assert p.health == hp - 1
    assert p.invulnerable

    # Second overlap while the i-frame window is active -> no damage.
    e.x, e.y = p.x + 10, p.y + 5
    game._update_game(KeyState())
    assert p.health == hp - 1
    assert p.invulnerable


def test_no_damage_during_iframe_window_and_resume_after(game):
    start_game(game)
    p = game.player
    p.health = settings.PLAYER_START_HEALTH
    e = place_enemy_over_player(game)

    # (a) First overlap lands the hit and starts the 60-frame window.
    hp = p.health
    game._update_game(KeyState())
    assert p.health == hp - 1
    assert p.invulnerable

    # A second overlap while the window is active does no damage.
    e.x, e.y = p.x + 10, p.y + 5
    game._update_game(KeyState())
    assert p.health == hp - 1
    assert p.invulnerable

    # (b) Keep the enemy clear while the whole window elapses. The window is
    # seconds-based (1.0 s), so step the target FPS to reach it: 60 frames of
    # 1/60 s each at the default dt.
    e.x, e.y = -100, -100
    window_frames = int(round(settings.PLAYER_INVULNERABLE_DURATION_SECONDS * settings.FPS))
    for _ in range(window_frames):
        game._update_game(KeyState())
    assert p.invulnerable_timer == 0  # window fully expired
    assert p.health == hp - 1

    # Once the window has expired, damage resumes on the next overlap.
    e.x, e.y = p.x + 10, p.y + 5
    game._update_game(KeyState())
    assert p.health == hp - 2
    assert p.invulnerable
