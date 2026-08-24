"""Power-ups: drop-on-defeat, auto-collect, and the three effects.

Covers the full contract:
- power-ups only drop from destroyed enemies, respecting POWERUP_DROP_CHANCE,
- the HEALTH power-up is gated by a missing-health rule: it is excluded from
  the drop pool while the bar is full, and becomes eligible as soon as the
  player is missing at least HEALTH_POWERUP_MIN_MISSING_SEGMENTS segments
  (shipped default 1, so drops start at 4/5 and stop again at 5/5),
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
from helpers import KeyState, reach_level_2, start_game
from powerup import PowerUp


def _drop_enemy(game):
    """Place an enemy and a bullet guaranteed to hit it this frame."""
    e = Enemy(200, 300)
    game.enemies = [e]
    game.bullets = [Bullet(220, 320)]
    return e


def _drop_gunner(game):
    """Place a bullet guaranteed to destroy a gunner this frame (Level 2).

    The mirror of _drop_enemy for the OTHER kill path. Both funnel through
    _maybe_drop_powerup, so the health gate has to hold for both; nothing
    covered the gunner side until these tests, and deleting its
    ``self._maybe_drop_powerup(gunner.x, gunner.y)`` call left the entire
    suite green.

    The gunner is pinned to a stopped, mid-screen position first. Left as
    spawned it is still descending toward a *random* stop_y, and the frame it
    crosses that line ``update()`` snaps y back to stop_y - a jump of up to
    ~90 px that can slide the gunner out from under the bullet, which would
    make this test flaky rather than wrong. The cooldown is pre-charged so it
    does not fire on the way out and dirty enemy_bullets.
    """
    assert game.gunners, "expected gunners on Level 2"
    g = game.gunners[0]
    game.gunners = [g]
    g.x, g.y = 200.0, 200.0
    g.stop_y = int(g.y)
    g.stopped = True
    g.fire_cooldown = settings.GUNNER_FIRE_COOLDOWN_SECONDS
    game.bullets = [Bullet(g.x + g.width // 2 - 5, g.y + 15)]
    game.enemy_bullets.clear()
    game.powerups.clear()
    return g


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
    # Missing health, so the HEALTH kind is actually in the pool.
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
# Health drop gating (drops while a segment is missing, stops at full)
# ---------------------------------------------------------------------- #


def _pool_on_next_drop(game, monkeypatch):
    """Force one guaranteed drop and return the pool random.choice was handed.

    Inspecting the pool rather than the resulting drop kind means a single
    forced roll proves inclusion/exclusion outright, with no reliance on
    random.choice happening to pick the health kind.
    """
    pools = []
    monkeypatch.setattr(random, "random", lambda: 0.0)  # roll always succeeds
    monkeypatch.setattr(
        random, "choice", lambda seq: pools.append(tuple(seq)) or "shield"
    )
    _drop_enemy(game)
    game._update_game(KeyState())
    assert pools, "no drop was rolled"
    return pools[-1]


def test_health_gate_default_is_one_missing_segment():
    """Shipped tuning: one missing segment is enough to start the drops."""
    assert settings.HEALTH_POWERUP_MIN_MISSING_SEGMENTS == 1


def test_health_powerup_excluded_at_full_health(game, monkeypatch):
    """At 5/5 the heart must never be offered - apply_powerup() clamps at max,
    so it would be a guaranteed wasted drop."""
    start_game(game)
    assert game.player.health == settings.PLAYER_START_HEALTH
    assert settings.POWERUP_KIND_HEALTH not in _pool_on_next_drop(game, monkeypatch)


def test_health_powerup_appears_one_segment_below_full(game, monkeypatch):
    """The boundary: a single missing segment (4/5) is enough to start drops.

    This is the regression. The old gate excluded the heart while
    ``health >= PLAYER_START_HEALTH * 0.8``, and 5 * 0.8 == 4.0, so 4/5 was
    still excluded and the heart did not appear until the bar hit 3/5 -
    despite the rule reading as "drops below 80%".
    """
    start_game(game)
    game.player.health = settings.PLAYER_START_HEALTH - 1
    assert settings.POWERUP_KIND_HEALTH in _pool_on_next_drop(game, monkeypatch)


@pytest.mark.parametrize("missing", [2, 3, 4])
def test_health_powerup_offered_at_every_level_below_full(game, monkeypatch, missing):
    """Once eligible it stays eligible all the way down the bar."""
    start_game(game)
    game.player.health = settings.PLAYER_START_HEALTH - missing
    assert game.player.health >= 1, "test setup would have killed the player"
    assert settings.POWERUP_KIND_HEALTH in _pool_on_next_drop(game, monkeypatch)


def test_health_powerup_stops_again_once_the_bar_is_refilled(game, monkeypatch):
    """The other half of the rule: healing back to full re-excludes the heart.

    Driven through the real pickup path instead of assigning health directly,
    so the gate and Player.apply_powerup's max clamp are exercised together.
    """
    start_game(game)
    game.player.health = settings.PLAYER_START_HEALTH - 1
    assert settings.POWERUP_KIND_HEALTH in _pool_on_next_drop(game, monkeypatch)

    game.player.apply_powerup(settings.POWERUP_KIND_HEALTH)
    assert game.player.health == settings.PLAYER_START_HEALTH
    assert settings.POWERUP_KIND_HEALTH not in _pool_on_next_drop(game, monkeypatch)


@pytest.mark.parametrize("knob", [2, 3])
def test_health_gate_boundary_moves_with_the_constant(game, monkeypatch, knob):
    """The gate must key off whole missing segments read from the constant.

    Each knob value has to place the boundary at exactly that many missing
    segments. No hardcoded number and no fixed fraction of max health can
    satisfy this file: with a 5-segment bar the sibling tests demand a gate
    that excludes 5/5 and includes 4/5, which for a fraction f (eligible while
    health < 5f) means f in (0.8, 1.0]; knob=3 demands exclusion at 3/5 and
    inclusion at 2/5, i.e. f in (0.4, 0.6]. Those ranges do not overlap, so
    only a gate that genuinely reads the constant passes both.

    knob=3 is also what catches the shipped bug: the old fraction of 0.8 made
    health 3/5 eligible, so it fails the exclusion assertion below.
    """
    monkeypatch.setattr(settings, "HEALTH_POWERUP_MIN_MISSING_SEGMENTS", knob)
    start_game(game)

    game.player.health = settings.PLAYER_START_HEALTH - (knob - 1)  # one short
    assert game.player.health >= 1, "test setup would have killed the player"
    assert settings.POWERUP_KIND_HEALTH not in _pool_on_next_drop(game, monkeypatch)

    game.player.health = settings.PLAYER_START_HEALTH - knob  # on the boundary
    assert game.player.health >= 1, "test setup would have killed the player"
    assert settings.POWERUP_KIND_HEALTH in _pool_on_next_drop(game, monkeypatch)


def test_health_powerup_actually_drops_when_eligible(game, monkeypatch):
    """End to end: an eligible roll really does put a heart on the field.

    The fake choice honours the pool it is handed instead of returning
    "health" unconditionally - a fake that ignores its argument bypasses the
    very filter under test and would pass even with the heart excluded.
    """
    start_game(game)
    game.player.health = settings.PLAYER_START_HEALTH - 1  # 4/5
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(
        random,
        "choice",
        lambda seq: (
            settings.POWERUP_KIND_HEALTH
            if settings.POWERUP_KIND_HEALTH in seq
            else seq[0]
        ),
    )
    _drop_enemy(game)

    game._update_game(KeyState())
    assert len(game.powerups) == 1
    assert game.powerups[0].kind == settings.POWERUP_KIND_HEALTH


def test_gunner_kills_also_roll_for_drops(game, monkeypatch):
    """Level 2 gunners drop power-ups too, not just Level 1 falling enemies.

    Pre-existing gap, not one this change introduced: the gunner kill path had
    no drop coverage at all, so deleting its _maybe_drop_powerup call left the
    whole suite green and Level 2 would silently stop dropping anything.
    """
    reach_level_2(game)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    g = _drop_gunner(game)
    before = game.score

    game._update_game(KeyState())
    assert len(game.powerups) == 1, "gunner kill produced no drop"
    assert game.score == before + 1, "gunner was not actually destroyed"
    assert g.y < 0, "gunner should have respawned above the screen"


def test_health_gate_applies_on_the_gunner_path_too(game, monkeypatch):
    """The new rule holds for the enemy that motivates it.

    Gunners are the only enemy that shoots back, so 4/5 is the *normal* Level 2
    state and the heart is the intended comeback - it would be a poor outcome
    if the gate only worked on the path where health is rarely lost.
    """
    reach_level_2(game)
    pools = []
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(
        random, "choice", lambda seq: pools.append(tuple(seq)) or seq[0]
    )

    assert game.player.health == settings.PLAYER_START_HEALTH
    _drop_gunner(game)
    game._update_game(KeyState())
    assert pools, "gunner kill never reached the drop roll"
    assert settings.POWERUP_KIND_HEALTH not in pools[-1]

    game.player.health = settings.PLAYER_START_HEALTH - 1  # 4/5
    _drop_gunner(game)
    game._update_game(KeyState())
    assert settings.POWERUP_KIND_HEALTH in pools[-1]


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


# ---------------------------------------------------------------------- #
# Fall speed + visual sizing
# ---------------------------------------------------------------------- #


def test_fall_speed_is_dt_based():
    """Power-up displacement scales linearly with dt (delta-time based)."""
    p = PowerUp("shield", 100.0, 0.0)
    start_y = p.y
    dt = 0.1  # 100 ms
    p.update(dt)
    expected = settings.POWERUP_FALL_SPEED_PER_SEC * dt
    assert p.y == pytest.approx(start_y + expected, abs=0.1)


def test_fall_speed_constant_reasonable():
    """Fall speed should be noticeable but slower than enemy movement."""
    assert settings.POWERUP_FALL_SPEED_PER_SEC > 100  # not sluggish
    assert settings.POWERUP_FALL_SPEED_PER_SEC < settings.ENEMY_SPEED_PER_SEC  # slower than enemies


def test_all_powerup_icons_same_visual_size(game):
    """All three power-up sprites produce similar visible content sizes
    after the aspect-fit scale step in Assets.load()."""
    for kind in settings.POWERUP_TYPES:
        surf = game.assets.powerup_images[kind]
        assert surf.get_size() == settings.POWERUP_IMG_SIZE, (
            f"{kind}: surface {surf.get_size()} != {settings.POWERUP_IMG_SIZE}"
        )
    # Aspect-fit scale means all visible content fits within
    # POWERUP_VISIBLE_SIZE; the largest dimension of each icon's
    # non-transparent content should be within a few pixels of the
    # others (they won't be identical due to different aspect ratios,
    # but they should all be visually comparable).
    content_sizes = []
    for kind in settings.POWERUP_TYPES:
        bbox = game.assets.powerup_images[kind].get_bounding_rect()
        content_sizes.append((bbox.width, bbox.height))
    # All should fit within POWERUP_VISIBLE_SIZE
    for i, kind in enumerate(settings.POWERUP_TYPES):
        w, h = content_sizes[i]
        assert w <= settings.POWERUP_VISIBLE_SIZE[0] + 2, (
            f"{kind}: width {w} > {settings.POWERUP_VISIBLE_SIZE[0]}"
        )
        assert h <= settings.POWERUP_VISIBLE_SIZE[1] + 2, (
            f"{kind}: height {h} > {settings.POWERUP_VISIBLE_SIZE[1]}"
        )
    # The max dimension across all icons should be within 8px of each
    # other (ensures no icon is dramatically smaller, while allowing
    # for natural aspect-ratio differences between sprites)
    max_dims = [max(w, h) for w, h in content_sizes]
    assert max(max_dims) - min(max_dims) <= 8, (
        f"Content sizes too dissimilar: {content_sizes}"
    )


# ── Icon content cropping (assets._content_crop) ──────────────────────
#
# _content_crop finds the largest contiguous block of opaque pixels, which is
# how the icons get trimmed before being scaled to POWERUP_VISIBLE_SIZE. The
# tests below use synthetic surfaces so they pin the AXIS CONVENTION rather
# than the shipped art: pygame.surfarray arrays are indexed [x][y], and the
# original code named its two axis sums the other way round.


def _stencil(width, height, block, strays=()):
    """A fully transparent surface with one opaque block and optional stray
    opaque single pixels elsewhere."""
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    surf.fill((255, 255, 255, 255), block)
    for pos in strays:
        surf.set_at(pos, (255, 255, 255, 255))
    return surf


def test_content_crop_is_not_transposed(game):
    """The crop must be (x, y, w, h), never (y, x, h, w).

    surfarray arrays are indexed [x][y], so the FIRST axis is width. The
    original code summed axis=1 into a variable it called "per_row" and
    axis=0 into "per_col" - exactly backwards - and returned a transposed
    rect. It never raised, because all three power-up source images happen
    to be square, so the only symptom was a subtly wrong crop. A
    deliberately non-square block catches it outright.
    """
    from assets import _content_crop

    block = pygame.Rect(5, 3, 10, 6)
    got = _content_crop(_stencil(40, 20, block))
    assert tuple(got) == tuple(block), (
        f"got {tuple(got)}, want {tuple(block)} "
        f"(transposed would be {(block.y, block.x, block.h, block.w)})"
    )


def test_content_crop_ignores_stray_corner_pixels(game):
    """The reason this helper exists at all instead of get_bounding_rect():
    sheild.png carries isolated opaque pixels at opposite corners, which make
    the naive bounding rect span the entire canvas."""
    from assets import _content_crop

    block = pygame.Rect(8, 4, 12, 9)
    surf = _stencil(40, 20, block, strays=((0, 0), (39, 19)))
    # The trap the helper exists to avoid:
    assert tuple(surf.get_bounding_rect()) == (0, 0, 40, 20)
    assert tuple(_content_crop(surf)) == tuple(block)


def test_content_crop_leaves_the_surface_unlocked(game):
    """Callers do surf.subsurface(crop_rect) immediately afterwards, which
    needs an unlocked surface.

    A guard, not a reproduction: the original used pixels_alpha(), which locks
    the surface for as long as the returned array lives, and only got away
    with it because CPython refcounting freed that local array on return.
    array_alpha() copies, so the lock never exists in the first place.
    """
    from assets import _content_crop

    surf = _stencil(40, 20, pygame.Rect(5, 3, 10, 6))
    rect = _content_crop(surf)
    assert not surf.get_locked()
    surf.subsurface(rect)  # must not raise


@pytest.mark.parametrize("kind,expected", [
    (settings.POWERUP_KIND_SHIELD, (210, 180, 209, 256)),
    (settings.POWERUP_KIND_RAPID_FIRE, (178, 111, 380, 514)),
    (settings.POWERUP_KIND_HEALTH, (184, 210, 367, 316)),
])
def test_content_crop_of_the_shipped_icons(game, kind, expected):
    """Golden crops for the real art, cross-checked against an independent
    reference implementation after the axis fix. All three are non-square, so
    a re-transposition would fail here too."""
    from assets import _content_crop
    from resource_path import resource_path

    raw = pygame.image.load(
        resource_path("Assets/" + settings.POWERUP_IMG_FILES[kind])
    ).convert_alpha()
    assert tuple(_content_crop(raw)) == expected
    raw.subsurface(_content_crop(raw))  # the crop must be usable as-is
