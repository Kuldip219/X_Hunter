"""Power-ups: drop-on-defeat, auto-collect, and the three effects.

Covers the full contract:
- power-ups only drop from destroyed enemies, respecting POWERUP_DROP_CHANCE,
- the HEALTH power-up is gated by a health threshold: it is excluded from
  the drop pool while the player is at or above 80% of their full health
  bar, and drops normally below it,
- pickup is automatic on collision (no keypress) and removes the drop,
- SHIELD grants full temporary invincibility (including lethal hits) that
  expires after its real-time duration,
- RAPID FIRE shortens the hold-to-fire cooldown and REFRESHES (never stacks),
- HEALTH restores exactly one health-bar segment, capped at max, with no
  timer involved,
- drops expire after their on-field lifetime and clear on restart,
- the in-game HUD renders while power-ups are active without crashing.
"""

import random

import pygame
import pytest

import settings
from bullet import Bullet
from enemy import Enemy
from helpers import KeyState, start_game
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
    # Below the health threshold so the HEALTH kind is actually in the pool.
    game.player.health = settings.PLAYER_START_HEALTH - 2
    monkeypatch.setattr(random, "random", lambda: 0.0)
    seen = set()
    for kind in settings.POWERUP_TYPES:
        monkeypatch.setattr(random, "choice", lambda seq, k=kind: k)
        _drop_enemy(game)
        game._update_game(KeyState())
        seen.add(game.powerups[-1].kind)
    assert seen == set(settings.POWERUP_TYPES)


# ---------------------------------------------------------------------- #
# Health drop gating (the 80%-threshold rule)
# ---------------------------------------------------------------------- #


def test_health_powerup_excluded_from_pool_at_or_above_80_percent(game, monkeypatch):
    start_game(game)
    monkeypatch.setattr(random, "random", lambda: 0.0)  # force a drop roll
    pools = []
    monkeypatch.setattr(
        random, "choice", lambda seq: pools.append(tuple(seq)) or "shield"
    )

    # At full health (5/5 = 100%): HEALTH must not be in the drop pool.
    _drop_enemy(game)
    game._update_game(KeyState())
    assert settings.POWERUP_KIND_HEALTH not in pools[-1]

    # At exactly 80% of max (4/5): still excluded.
    game.player.health = int(
        settings.PLAYER_START_HEALTH * settings.HEALTH_POWERUP_MIN_HEALTH_FRACTION
    )
    _drop_enemy(game)
    game._update_game(KeyState())
    assert settings.POWERUP_KIND_HEALTH not in pools[-1]

    # Below 80% (3/5): HEALTH is back in the pool.
    game.player.health = (
        int(settings.PLAYER_START_HEALTH * settings.HEALTH_POWERUP_MIN_HEALTH_FRACTION) - 1
    )
    _drop_enemy(game)
    game._update_game(KeyState())
    assert settings.POWERUP_KIND_HEALTH in pools[-1]


def test_health_powerup_drops_below_threshold(game, monkeypatch):
    start_game(game)
    game.player.health = settings.PLAYER_START_HEALTH - 2  # 3/5, below 80%
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: "health")
    _drop_enemy(game)

    game._update_game(KeyState())
    assert len(game.powerups) == 1
    assert game.powerups[0].kind == "health"


# ---------------------------------------------------------------------- #
# Pickup
# ---------------------------------------------------------------------- #


def test_pickup_is_automatic_on_collision_and_removes_drop(game):
    start_game(game)
    p = game.player
    p.y = 600

    # Shield
    game.powerups = [PowerUp("shield", p.x, p.y)]
    game._update_game(KeyState())  # no keypress, no movement
    assert game.powerups == []
    assert p.shield_active

    # Rapid fire
    game.powerups = [PowerUp("rapid_fire", p.x, p.y)]
    game._update_game(KeyState())
    assert game.powerups == []
    assert p.rapid_fire_active

    # Health: below max so the restoration is observable.
    p.health = settings.PLAYER_START_HEALTH - 2
    game.powerups = [PowerUp("health", p.x, p.y)]
    game._update_game(KeyState())
    assert game.powerups == []
    assert p.health == settings.PLAYER_START_HEALTH - 1


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
    game.powerups = [PowerUp("health", 100, 100)]
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
# Health
# ---------------------------------------------------------------------- #


def test_health_restores_one_segment_capped_at_max(game):
    start_game(game)
    p = game.player

    # Mid-damage: restores exactly one segment.
    p.health = 2
    p.apply_powerup("health")
    assert p.health == 3

    # One below max: restores to max, never overheals.
    p.health = settings.PLAYER_START_HEALTH - 1
    p.apply_powerup("health")
    assert p.health == settings.PLAYER_START_HEALTH

    # At max: no change (capped).
    p.apply_powerup("health")
    assert p.health == settings.PLAYER_START_HEALTH


def test_health_has_no_timer(game):
    start_game(game)
    p = game.player
    p.health = 1
    p.apply_powerup("health")
    assert p.health == 2
    # Nothing decays: health is unchanged no matter how long we tick.
    for _ in range(10 * settings.FPS):
        p.update_powerups(1.0 / settings.FPS)
    assert p.health == 2


# ---------------------------------------------------------------------- #
# HUD
# ---------------------------------------------------------------------- #


def test_powerup_hud_renders_while_active(game):
    start_game(game)
    p = game.player
    p.apply_powerup("shield")
    p.apply_powerup("rapid_fire")
    game._draw_game()  # shield aura + status rows must render without crashing
    assert p.shield_active
    assert p.rapid_fire_active
