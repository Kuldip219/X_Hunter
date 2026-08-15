"""Power-ups: drop-on-defeat, auto-collect, and the three effects.

Covers the full contract:
- power-ups only drop from destroyed enemies, respecting POWERUP_DROP_CHANCE,
- pickup is automatic on collision (no keypress) and removes the drop,
- SHIELD grants full temporary invincibility (including lethal hits) that
  expires after its real-time duration,
- RAPID FIRE shortens the hold-to-fire cooldown and REFRESHES (never stacks),
- EXTRA LIFE increments the life count with no timer,
- dying with a spare life respawns the ship; dying with the last life ends
  the run (the default 1-life behavior is unchanged),
- drops expire after their on-field lifetime and clear on restart,
- the in-game HUD renders while power-ups are active without crashing.
"""

import random

import pygame
import pytest

import settings
from bullet import Bullet
from enemy import Enemy
from helpers import KeyState, pump, start_game
from powerup import PowerUp


def _drop_enemy(game):
    """Place an enemy and a bullet guaranteed to hit it this frame."""
    e = Enemy(200, 300)
    game.enemies = [e]
    game.bullets = [Bullet(220, 320)]
    return e


# ---------------------------------------------------------------------- #
# Drops
# ---------------------------------------------------------------------- #


def test_drop_chance_is_within_reasonable_range():
    assert 0.10 <= settings.POWERUP_DROP_CHANCE <= 0.15


def test_powerup_drops_on_enemy_defeat_when_roll_succeeds(game, monkeypatch):
    start_game(game)
    monkeypatch.setattr(random, "random", lambda: 0.0)  # roll always succeeds
    monkeypatch.setattr(random, "choice", lambda seq: "shield")
    e = _drop_enemy(game)
    # Capture the destroyed position: the enemy is respawned right after the
    # drop, so compare against its pre-update position plus its 5 px drop.
    drop_x, drop_y = e.x, e.y + settings.ENEMY_SPEED_PER_SEC / settings.FPS

    game._update_game(KeyState())
    assert len(game.powerups) == 1
    pu = game.powerups[0]
    assert pu.kind == "shield"
    # Dropped exactly where the enemy was destroyed (post-update position).
    assert pu.x == drop_x and pu.y == pytest.approx(drop_y)


def test_no_drop_when_roll_fails(game, monkeypatch):
    start_game(game)
    monkeypatch.setattr(random, "random", lambda: 0.99)  # roll always fails
    _drop_enemy(game)

    game._update_game(KeyState())
    assert game.powerups == []


def test_all_three_kinds_can_drop(game, monkeypatch):
    start_game(game)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    seen = set()
    for kind in settings.POWERUP_TYPES:
        monkeypatch.setattr(random, "choice", lambda seq, k=kind: k)
        _drop_enemy(game)
        game._update_game(KeyState())
        seen.add(game.powerups[-1].kind)
    assert seen == set(settings.POWERUP_TYPES)


# ---------------------------------------------------------------------- #
# Pickup
# ---------------------------------------------------------------------- #


def test_pickup_is_automatic_on_collision_and_removes_drop(game):
    start_game(game)
    p = game.player
    p.y = 600
    cases = [
        ("shield", lambda: p.shield_active),
        ("rapid_fire", lambda: p.rapid_fire_active),
        ("life", lambda: p.lives == settings.PLAYER_START_LIVES + 1),
    ]
    for kind, check in cases:
        game.powerups = [PowerUp(kind, p.x, p.y)]
        game._update_game(KeyState())  # no keypress, no movement
        assert game.powerups == []  # consumed on contact
        assert check(), f"{kind} effect did not apply on pickup"


def test_drop_falls_toward_player_and_expires_uncollected(game):
    start_game(game)
    game.enemies = []  # keep the field collision-free
    game.bullets = []
    p = game.player
    p.y = 600
    # Far from the player (x=0 vs player at 300..365) so it is never
    # collected; must despawn after its real-time lifetime.
    game.powerups = [PowerUp("shield", 0, 100)]
    frames = int(round(settings.POWERUP_LIFETIME_SECONDS * settings.FPS)) + 5
    for _ in range(frames):
        game._update_game(KeyState())
    assert game.powerups == []


def test_powerups_cleared_on_restart(game):
    start_game(game)
    game.powerups = [PowerUp("life", 100, 100)]
    game.reset_game()
    assert game.powerups == []


# ---------------------------------------------------------------------- #
# Shield
# ---------------------------------------------------------------------- #


def test_shield_blocks_damage_including_lethal_hits(game):
    start_game(game)
    p = game.player
    p.apply_powerup("shield")
    p.health = 1

    assert p.shield_active
    # A would-be killing blow is blocked while the shield is up.
    assert p.take_hit() is False
    assert not p.dead
    assert p.health == 1

    # Once the shield is gone, the same hit kills (lethal check first).
    p.shield_timer = 0.0
    assert p.take_hit() is True
    assert p.dead


def test_shield_expires_after_duration(game):
    start_game(game)
    p = game.player
    p.apply_powerup("shield")
    frames = int(round(settings.POWERUP_SHIELD_DURATION_SECONDS * settings.FPS))
    for _ in range(frames):
        p.update_powerups(1.0 / settings.FPS)
    assert not p.shield_active
    assert p.shield_timer == 0.0


# ---------------------------------------------------------------------- #
# Rapid fire
# ---------------------------------------------------------------------- #


def test_rapid_fire_shortens_cooldown_and_refreshes_not_stacks(game):
    start_game(game)
    p = game.player
    p.apply_powerup("rapid_fire")
    expected = (
        settings.PLAYER_FIRE_COOLDOWN_SECONDS * settings.RAPID_FIRE_COOLDOWN_MULTIPLIER
    )
    assert p.rapid_fire_active
    assert p.fire_cooldown_value() == pytest.approx(expected)

    # Collecting another while active refreshes the window to full duration
    # rather than extending/stacking it.
    p.rapid_fire_timer = 2.0
    p.apply_powerup("rapid_fire")
    assert p.rapid_fire_timer == pytest.approx(
        settings.POWERUP_RAPID_FIRE_DURATION_SECONDS
    )

    # After the window elapses the base cadence returns.
    frames = int(round(settings.POWERUP_RAPID_FIRE_DURATION_SECONDS * settings.FPS))
    for _ in range(frames):
        p.update_powerups(1.0 / settings.FPS)
    assert not p.rapid_fire_active
    assert p.fire_cooldown_value() == settings.PLAYER_FIRE_COOLDOWN_SECONDS


def test_rapid_fire_fires_more_bullets_than_normal_cadence(game):
    start_game(game)
    game.enemies = []
    p = game.player
    p.y = 600
    keys = KeyState(pygame.K_SPACE)

    # Normal cadence: shots at frames 0, 12, 24 -> 3 bullets in 25 frames.
    game._update_game(keys)
    for _ in range(24):
        game._update_game(keys)
    normal = len(game.bullets)
    assert normal == 3

    # Rapid cadence over the same window: cooldown is 0.2*0.3 = 0.06 s, so a
    # shot lands roughly every 4 frames -> well above the normal count.
    p.fire_cooldown = 0.0
    p.apply_powerup("rapid_fire")
    game.bullets = []
    for _ in range(25):
        game._update_game(keys)
    rapid = len(game.bullets)
    assert rapid > normal
    assert rapid >= 6


# ---------------------------------------------------------------------- #
# Extra life
# ---------------------------------------------------------------------- #


def test_extra_life_increments_count_with_no_timer(game):
    start_game(game)
    p = game.player
    assert p.lives == settings.PLAYER_START_LIVES
    p.apply_powerup("life")
    assert p.lives == settings.PLAYER_START_LIVES + 1
    # No duration/timer: lives never decay, no matter how long we tick.
    for _ in range(10 * settings.FPS):
        p.update_powerups(1.0 / settings.FPS)
    assert p.lives == settings.PLAYER_START_LIVES + 1


# ---------------------------------------------------------------------- #
# Lives & respawn
# ---------------------------------------------------------------------- #


def test_dying_with_spare_life_respawns_and_continues_run(game):
    start_game(game)
    p = game.player
    p.lives = 2
    p.health = 1
    assert p.take_hit() is True
    assert p.dead
    score0 = game.score

    # The death explosion plays, then the spare life is burned: the ship
    # respawns in place with full health and never leaves the "game" state.
    pump(game, frames=100)
    assert game.state == "game"
    assert not p.dead
    assert p.health == settings.PLAYER_START_HEALTH
    assert p.lives == 1  # one spare consumed
    assert p.invulnerable  # spawn protection
    assert game.score == score0  # the run continues, score untouched
    assert game.last_run_rank is None  # no leaderboard entry on a respawn


def test_dying_with_last_life_is_game_over(game):
    start_game(game)
    p = game.player
    assert p.lives == settings.PLAYER_START_LIVES  # default: 1
    p.health = 1
    assert p.take_hit() is True
    pump(game, frames=100)
    assert game.state == "game_over"
    assert p.dead


# ---------------------------------------------------------------------- #
# HUD
# ---------------------------------------------------------------------- #


def test_powerup_hud_renders_while_active(game):
    start_game(game)
    p = game.player
    p.apply_powerup("shield")
    p.apply_powerup("rapid_fire")
    p.lives = 3
    game._draw_game()  # shield aura + status rows must render without crashing
    assert p.shield_active
    assert p.rapid_fire_active
