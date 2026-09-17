"""Level 3 boss: 'The Final Phase'.

Covers the whole contract:
- the score gate (200) stops normal spawning and flies the boss in,
- the boss exists only on the boss level (Levels 1-2 still end via ship exit),
- Level 3's opening wave mixes both enemy types; Levels 1-2 stay single-type,
- entrance, bounded drift + vertical bob, full-sprite hitbox, HP 40,
- the three attack phases at the documented HP thirds,
- spread fan + telegraphed aimed burst (phases 2+), minions (phase 3 only),
- boss bullets behave exactly like gunner bullets (shield blocks, i-frames),
- no i-frame gap: every connecting bullet deals damage,
- the victory sequence: flash, a multi-stage explosion chain across the
  sprite's body, the boss's removal, the ship exit (the SAME shared
  transition a normal level ends with), then the end-of-run screen (there
  is deliberately no dedicated victory screen).
"""

import numpy as np
import pytest
import pygame

import menus
import settings
from boss import Boss
from bullet import Bullet
from enemy import Enemy
from enemy_bullet import EnemyBullet
from game import Game
from gunner import GunnerEnemy
from helpers import (
    KeyState,
    kill_boss,
    pump,
    pump_fade,
    pump_run_until,
    reach_boss,
    start_game,
    wait_for_boss_active,
)
from menus import _render_fitted_title

DT = settings.FIXED_DT


# ── Helpers ───────────────────────────────────────────────────────────


def _active_boss(hp: int | None = None) -> Boss:
    """A settled (non-entering) boss for pure behaviour tests."""
    boss = Boss(settings.WIDTH, settings.HEIGHT)
    boss.y = float(settings.BOSS_ACTIVE_Y)
    boss.base_y = boss.y
    boss.entering = False
    if hp is not None:
        boss.hp = hp
    return boss


# Screen coordinates in this suite are authored on the 600x800 canvas and
# passed through settings.px(), so the scenarios below describe the same
# relative geometry at any window size (a raw literal would silently become
# a different position once the resolution changed).
PX = settings.px


def _run_boss(boss: Boss, seconds: float, player_x: float = PX(300)):
    """Advance a boss for `seconds` of fixed steps.

    Returns (bullets, minions, charge_seen, burst_seen).
    """
    bullets: list[EnemyBullet] = []
    minions = 0
    charge_seen = False
    burst_seen = False
    for _ in range(int(seconds / DT)):
        fired, spawned = boss.update(DT, player_x, settings.WIDTH)
        bullets.extend(fired)
        minions += spawned
        charge_seen = charge_seen or boss.aim_charge > 0
        burst_seen = burst_seen or boss.burst_shots_left > 0
    return bullets, minions, charge_seen, burst_seen


def _burst_volley(
    boss: Boss, player_x: float, player_y: float, seconds: float = 20.0
) -> list[tuple[tuple[float, float], EnemyBullet]]:
    """Run a boss until one aimed burst comes out.

    The spread shot is suppressed so the only bullets in flight are the
    burst's, and each shot is returned paired with the muzzle position it
    left from (read in the same step it was fired, since the boss keeps
    drifting between shots).
    """
    boss.spread_cooldown = 10_000.0
    shots: list[tuple[tuple[float, float], EnemyBullet]] = []
    for _ in range(int(seconds / DT)):
        fired, _minions = boss.update(DT, player_x, settings.WIDTH, player_y)
        muzzle = boss._muzzle()
        for bullet in fired:
            shots.append((muzzle, bullet))
        if len(shots) >= settings.BOSS_AIM_BURST_COUNT:
            break
    return shots


def _shot_crossing_x(bullet: EnemyBullet, row_y: float) -> float:
    """Where a bullet's centre crosses the given row (exact, no stepping)."""
    travelled = (row_y - bullet.y) * (bullet.vx / bullet.vy)
    return bullet.x + settings.ENEMY_BULLET_IMG_SIZE[0] / 2.0 + travelled


def _no_enemies(game) -> None:
    """Clear the field so a collision test only sees what it places."""
    game.enemies = []
    game.gunners = []
    game.enemy_bullets = []
    game.bullets = []


def _draw_on_black(game) -> None:
    game.screen.fill(settings.BLACK)


class _BlitRecorder:
    """A stand-in screen that records which surfaces get blitted to it."""

    def __init__(self, inner: pygame.Surface) -> None:
        self._inner = inner
        self.calls: list[pygame.Surface] = []

    def blit(self, source, dest, *args, **kwargs):
        self.calls.append(source)
        return self._inner.blit(source, dest, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def count(self, surface: pygame.Surface) -> int:
        return sum(1 for blitted in self.calls if blitted is surface)


def _dilate(mask: "np.ndarray") -> "np.ndarray":
    """Grow a boolean mask by one pixel on each side.

    Antialiased glyph edges only partly cover their pixels, so a rendered
    glyph's ink can spill a pixel past its own alpha mask.
    """
    out = mask.copy()
    out[1:, :] |= mask[:-1, :]
    out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    return out


# The end-of-run screen has two variants: a run that beat the final boss
# (gold, "Wanna go again....?") and a death (red, "GAME OVER").
# (finished, expected heading text, expected heading colour)
_END_OF_RUN_VARIANTS = [
    (True, settings.GAME_COMPLETE_TITLE, settings.GAME_COMPLETE_COLOR),
    (False, "GAME OVER", settings.GAME_OVER_COLOR),
]


# ── Stats, hitbox, phase thresholds ───────────────────────────────────


class TestBossStats:
    def test_hp_is_40(self):
        assert settings.BOSS_HP == 40
        assert _active_boss().hp == 40

    def test_hitbox_is_the_full_sprite(self):
        boss = _active_boss()
        rect = boss.get_rect()
        assert (rect.width, rect.height) == settings.BOSS_IMG_SIZE
        assert rect.x == int(boss.x) and rect.y == int(boss.y)

    def test_visibly_bigger_than_a_normal_enemy(self):
        assert settings.BOSS_IMG_SIZE[0] > settings.ENEMY_IMG_SIZE[0]
        assert settings.BOSS_IMG_SIZE[1] > settings.ENEMY_IMG_SIZE[1]

    def test_phase_thresholds_match_the_documented_thirds(self):
        # HP 40: phase 1 = 27-40, phase 2 = 14-26, phase 3 = 0-13.
        cases = {40: 1, 27: 1, 26: 2, 14: 2, 13: 3, 1: 3, 0: 3}
        for hp, expected in cases.items():
            assert _active_boss(hp).phase == expected, f"HP {hp}"


# ── Entrance ──────────────────────────────────────────────────────────


class TestEntrance:
    def test_starts_off_screen_above_and_entering(self):
        boss = Boss(settings.WIDTH, settings.HEIGHT)
        assert boss.entering is True
        assert boss.y + boss.height <= 0, 'boss should start fully off-screen'

    def test_flies_down_to_the_active_y(self):
        boss = Boss(settings.WIDTH, settings.HEIGHT)
        previous = boss.y
        steps = 0
        while boss.entering and steps < 600:
            bullets, minions = boss.update(DT, PX(300), settings.WIDTH)
            assert bullets == [] and minions == 0, 'the boss must not attack while entering'
            assert boss.y >= previous, 'entrance must be monotonically downward'
            previous = boss.y
            steps += 1
        assert not boss.entering
        assert boss.y == pytest.approx(settings.BOSS_ACTIVE_Y, abs=1.0)
        assert steps > 10, 'entrance must be an animation, not a teleport'

    def test_entrance_is_horizontal_stable(self):
        boss = Boss(settings.WIDTH, settings.HEIGHT)
        x0 = boss.x
        for _ in range(120):
            if not boss.entering:
                break
            boss.update(DT, PX(300), settings.WIDTH)
        assert boss.x == x0, 'the boss should drop straight in, not drift while entering'


# ── Movement ──────────────────────────────────────────────────────────


class TestMovement:
    def test_drift_stays_within_the_bounded_band(self):
        boss = _active_boss()
        left = settings.BOSS_DRIFT_MARGIN
        right = settings.WIDTH - boss.width - settings.BOSS_DRIFT_MARGIN
        xs = []
        for _ in range(int(20 / DT)):
            boss.update(DT, PX(300), settings.WIDTH)
            xs.append(boss.x)
        assert min(xs) >= left - 1e-6
        assert max(xs) <= right + 1e-6
        assert max(xs) - min(xs) > 100, 'the boss should actually traverse the band'

    def test_drift_reverses_at_the_left_edge(self):
        boss = _active_boss()
        boss.x = settings.BOSS_DRIFT_MARGIN
        boss.drift_dir = -1
        boss.update(DT, 300.0, settings.WIDTH)
        assert boss.x >= settings.BOSS_DRIFT_MARGIN
        assert boss.drift_dir == 1

    def test_drift_reverses_at_the_right_edge(self):
        boss = _active_boss()
        boss.x = settings.WIDTH - boss.width - settings.BOSS_DRIFT_MARGIN
        boss.drift_dir = 1
        boss.update(DT, 300.0, settings.WIDTH)
        assert boss.x <= settings.WIDTH - boss.width - settings.BOSS_DRIFT_MARGIN
        assert boss.drift_dir == -1

    def test_vertical_bob_rises_and_falls_around_the_base(self):
        boss = _active_boss()
        offsets = []
        for _ in range(int(settings.BOSS_BOB_PERIOD_SECONDS / DT) + 2):
            boss.update(DT, PX(300), settings.WIDTH)
            offsets.append(boss.y - boss.base_y)
        assert max(offsets) > 1, 'boss should bob above its base'
        assert min(offsets) < -1, 'boss should bob below its base'
        assert max(abs(o) for o in offsets) <= settings.BOSS_BOB_AMPLITUDE + 0.5

    def test_movement_is_not_stop_and_shoot(self):
        """Unlike a gunner the boss never freezes: it keeps drifting while
        it fires."""
        boss = _active_boss(hp=10)
        xs = []
        fired_while_moving = False
        last_x = boss.x
        for _ in range(int(6 / DT)):
            bullets, _minions, _c, _b = _run_boss(boss, DT, PX(300))
            xs.append(boss.x)
            if bullets and abs(boss.x - last_x) > 0:
                fired_while_moving = True
            last_x = boss.x
        assert fired_while_moving
        assert len(set(round(x, 3) for x in xs)) > 10


# ── Attacks by phase ──────────────────────────────────────────────────


class TestAttackPhases:
    def test_phase_1_is_spread_only(self):
        boss = _active_boss(hp=40)
        assert boss.phase == 1
        bullets, minions, charge_seen, burst_seen = _run_boss(boss, 12.0)
        assert bullets, 'phase 1 must still fire the spread shot'
        assert charge_seen is False, 'no aimed burst before phase 2'
        assert burst_seen is False
        assert minions == 0, 'no minions before phase 3'
        # Every bullet must be part of a downward fan (never upward).
        assert all(b.vy > 0 for b in bullets)

    def test_spread_fan_shape(self):
        boss = _active_boss(hp=40)
        bullets = boss._spread_bullets()
        assert len(bullets) == settings.BOSS_SPREAD_COUNT
        angles = sorted(b.angle_degrees for b in bullets)
        # Symmetric fan around straight down.
        assert angles[0] == pytest.approx(-settings.BOSS_SPREAD_ANGLE_DEGREES / 2)
        assert angles[-1] == pytest.approx(settings.BOSS_SPREAD_ANGLE_DEGREES / 2)
        assert angles[len(angles) // 2] == pytest.approx(0.0)
        # Fanning out means the outer bullets move sideways as well as down.
        assert any(b.vx < 0 for b in bullets)
        assert any(b.vx > 0 for b in bullets)

    def test_phase_2_adds_the_aimed_burst(self):
        boss = _active_boss(hp=20)
        assert boss.phase == 2
        bullets, minions, charge_seen, burst_seen = _run_boss(boss, 12.0)
        assert bullets
        assert charge_seen, 'phase 2 must telegraph the aimed burst'
        assert burst_seen, 'phase 2 must actually fire the burst'
        assert minions == 0, 'no minions before phase 3'

    def test_burst_shots_spawn_at_the_boss_muzzle(self):
        """The volley must visibly leave the boss - not materialise at the
        tracked column, which is often a ship-width away in mid-air."""
        boss = _active_boss(hp=20)
        player_x, player_y = float(PX(120)), float(PX(700))
        shots = _burst_volley(boss, player_x, player_y)
        assert len(shots) == settings.BOSS_AIM_BURST_COUNT
        for (muzzle_x, muzzle_y), bullet in shots:
            assert bullet.x == pytest.approx(muzzle_x, abs=2.0)
            assert bullet.y == pytest.approx(muzzle_y, abs=2.0)
            # The muzzle is the boss's own bottom-centre, nowhere near the
            # player's column in this scenario.
            assert abs(bullet.x - player_x) > boss.width / 4

    def test_burst_shots_still_converge_on_the_tracked_position(self):
        boss = _active_boss(hp=20)
        player_x, player_y = float(PX(120)), float(PX(700))
        shots = _burst_volley(boss, player_x, player_y)
        assert shots
        for _muzzle, bullet in shots:
            assert bullet.vy > 0, 'the burst must travel downward'
            assert _shot_crossing_x(bullet, player_y) == pytest.approx(
                player_x, abs=2.0
            )

    def test_burst_stays_a_tight_volley_not_a_spread(self):
        """The three shots leave on nearly the same line - re-aiming per shot
        must not turn the burst into a fan of its own."""
        boss = _active_boss(hp=20)
        shots = _burst_volley(boss, float(PX(120)), float(PX(700)))
        angles = [b.angle_degrees for _m, b in shots]
        assert max(angles) - min(angles) < 5.0

    def test_burst_angle_is_clamped_to_a_downward_shot(self):
        boss = _active_boss(hp=20)
        # A target far off to the side must not produce a flat/horizontal shot.
        boss.aim_target_x = -5_000.0
        boss.aim_target_y = float(PX(760))
        assert boss._aim_angle() == pytest.approx(
            -settings.BOSS_AIM_MAX_ANGLE_DEGREES
        )
        # A target level with (or above) the muzzle falls back to straight down.
        boss.aim_target_x = boss.x
        boss.aim_target_y = boss._muzzle_center()[1] - 10.0
        assert boss._aim_angle() == 0.0

    def test_burst_falls_back_to_the_players_row_without_a_player_y(self):
        """Callers that only track the player horizontally still get a
        sensibly aimed volley (no horizontal spray)."""
        boss = _active_boss(hp=20)
        shots = _burst_volley(boss, float(PX(520)), settings.BOSS_AIM_DEFAULT_TARGET_Y)
        assert shots
        for _muzzle, bullet in shots:
            assert bullet.vy > 0
            assert _shot_crossing_x(
                bullet, settings.BOSS_AIM_DEFAULT_TARGET_Y
            ) == pytest.approx(PX(520), abs=2.0)

    def test_burst_tracks_the_player_until_it_fires(self):
        """The charge window re-tracks every step, so a moving player is
        aimed at where they are when the shot leaves - not where they were
        when the charge began."""
        boss = _active_boss(hp=20)
        boss.spread_cooldown = 10_000.0
        boss.aim_charge = settings.BOSS_AIM_CHARGE_SECONDS
        # Move the player across the screen during the charge.
        for i in range(int(settings.BOSS_AIM_CHARGE_SECONDS / DT) - 1):
            boss.update(DT, PX(100) + i * PX(10), settings.WIDTH, PX(700))
        # The charge completes on this step: the target locks to the 500 mark.
        boss.update(DT, PX(500), settings.WIDTH, PX(700))
        fired: list[EnemyBullet] = []
        for _ in range(30):
            fired, _m, _c, _b = _run_boss(boss, DT, PX(999))
            if fired:
                break
        assert fired, 'the burst should fire once the charge completes'
        assert _shot_crossing_x(fired[0], PX(700)) == pytest.approx(PX(500), abs=2.0)

    def test_aim_charge_is_the_telegraph_window(self):
        boss = _active_boss(hp=20)
        boss.aim_cooldown = 0.0
        _run_boss(boss, DT)  # one step starts the charge
        assert boss.aim_target_visible(), 'charge should be visible right after it starts'
        # Charge lasts about BOSS_AIM_CHARGE_SECONDS of simulated time.
        steps = 0
        while boss.aim_target_visible() and steps < 1000:
            boss.update(DT, PX(300), settings.WIDTH)
            steps += 1
        assert steps == pytest.approx(
            settings.BOSS_AIM_CHARGE_SECONDS / DT, abs=2
        )

    def test_phase_3_adds_minions(self):
        boss = _active_boss(hp=5)
        assert boss.phase == 3
        _bullets, minions, charge_seen, _burst = _run_boss(boss, 12.0)
        assert minions >= 2, 'phase 3 should periodically request minions'
        assert charge_seen

    def test_minions_only_in_phase_3(self):
        for hp, expected_phase in ((40, 1), (20, 2)):
            boss = _active_boss(hp=hp)
            assert boss.phase == expected_phase
            _b, minions, _c, _s = _run_boss(boss, 12.0)
            assert minions == 0, f'HP {hp} must not spawn minions'

    def test_minion_interval_matches_the_constant(self):
        duration = settings.BOSS_MINION_INTERVAL_SECONDS * 2.5
        boss = _active_boss(hp=5)
        # A freshly-active boss has no minion cooldown pending, so the first
        # minion comes immediately and the rest follow one interval apart.
        _b, minions, _c, _s = _run_boss(boss, duration)
        assert minions == 1 + int(duration // settings.BOSS_MINION_INTERVAL_SECONDS)
        assert minions < duration / DT / 10, 'minions must not spawn every step'

    def test_minion_interval_is_three_seconds(self):
        """Phase 3 is meant to feel urgent: 3 s, not the original 5 s."""
        assert settings.BOSS_MINION_INTERVAL_SECONDS == pytest.approx(3.0)
        assert settings.BOSS_MINION_INTERVAL_SECONDS < 5.0

    def test_minions_actually_spawn_three_seconds_apart(self):
        boss = _active_boss(hp=5)
        times: list[float] = []
        elapsed = 0.0
        for _ in range(int(10.0 / DT)):
            _bullets, minions = boss.update(DT, 300.0, settings.WIDTH)
            if minions:
                times.append(elapsed)
            elapsed += DT
        assert len(times) >= 3, 'phase 3 should keep requesting minions'
        assert times[0] == pytest.approx(0.0, abs=DT * 2)
        for earlier, later in zip(times, times[1:]):
            assert later - earlier == pytest.approx(
                settings.BOSS_MINION_INTERVAL_SECONDS, abs=DT * 2
            )

    def test_minions_never_spawn_on_top_of_each_other(self):
        """Even with the boss frozen in place (the worst case for pile-up)
        consecutive drops are a half a boss-width apart."""
        boss = _active_boss(hp=5)
        boss.drift_dir = 0  # hold the boss still
        positions: list[tuple[float, float, float]] = []
        for _ in range(int(12.0 / DT)):
            _bullets, minions = boss.update(DT, 300.0, settings.WIDTH)
            if minions:
                x, y = boss.minion_spawn_pos()
                positions.append((x, y, boss.y))
        assert len(positions) >= 3
        expected_gap = 2.0 * settings.BOSS_MINION_SPAWN_SPREAD * boss.width
        for earlier, later in zip(positions, positions[1:]):
            assert abs(later[0] - earlier[0]) == pytest.approx(expected_gap)
        # Every spawn stays inside the playfield, just under the boss (whose
        # bob moves that edge up and down between drops).
        for x, y, boss_y in positions:
            assert 0 <= x <= settings.WIDTH - settings.ENEMY_WIDTH
            assert y == pytest.approx(boss_y + boss.height)

    def test_cooldowns_tighten_by_phase(self):
        assert (
            settings.BOSS_SPREAD_COOLDOWN_SECONDS[0]
            > settings.BOSS_SPREAD_COOLDOWN_SECONDS[1]
            > settings.BOSS_SPREAD_COOLDOWN_SECONDS[2]
        )
        assert (
            settings.BOSS_AIM_COOLDOWN_SECONDS[1]
            > settings.BOSS_AIM_COOLDOWN_SECONDS[2]
        )


# ── Damage rules ──────────────────────────────────────────────────────


class TestDamage:
    def test_take_damage_has_no_cooldown(self):
        boss = _active_boss()
        for expected in range(39, -1, -1):
            assert boss.take_damage(1) == expected
        assert boss.hp == 0

    def test_health_never_goes_negative(self):
        boss = _active_boss(hp=2)
        boss.take_damage(5)
        assert boss.hp == 0

    def test_every_overlapping_bullet_deals_damage_in_one_step(self, game):
        start_game(game)
        _no_enemies(game)
        game.boss = _active_boss()
        game.boss_phase_active = True
        rect = game.boss.get_rect()
        game.bullets = [
            # Already inside the boss's rect before this step moves them.
            Bullet(rect.centerx + dx, rect.centery)
            for dx in (-40, -20, 0, 20, 40)
        ]
        before = game.boss.hp
        game._update_game(KeyState(), DT)
        assert game.boss.hp == before - 5, 'no i-frame gap between connecting hits'
        assert game.bullets == [], 'each connecting bullet is consumed'

    def test_boss_hits_award_no_score(self, game):
        start_game(game)
        _no_enemies(game)
        game.boss = _active_boss()
        game.boss_phase_active = True
        rect = game.boss.get_rect()
        game.bullets = [Bullet(rect.centerx, rect.centery)]
        score_before = game.score
        game._update_game(KeyState(), DT)
        assert game.score == score_before

    def test_bullets_pass_through_while_entering(self, game):
        start_game(game)
        _no_enemies(game)
        boss = Boss(settings.WIDTH, settings.HEIGHT)
        boss.y = -50.0  # still entering, partially on-screen
        boss.base_y = boss.y
        game.boss = boss
        game.boss_phase_active = True
        game.bullets = [Bullet(boss.x + 10, boss.y + 10)]
        hp_before = boss.hp
        game._update_game(KeyState(), DT)
        assert boss.entering
        assert boss.hp == hp_before, 'the boss is invulnerable while flying in'

    def test_killing_hit_starts_the_death_sequence(self, game):
        start_game(game)
        _no_enemies(game)
        game.boss = _active_boss(hp=1)
        game.boss_phase_active = True
        rect = game.boss.get_rect()
        game.bullets = [Bullet(rect.centerx, rect.centery)]
        game._update_game(KeyState(), DT)
        assert game.boss.hp == 0
        assert game.boss_dying is True


# ── Boss level: gate, spawning, exclusivity ───────────────────────────


class TestBossLevelGate:
    def test_gate_starts_the_boss_phase(self, game):
        reach_boss(game)
        assert game.boss_phase_active is True
        assert game.boss is not None
        assert game.boss.entering is True, 'the boss flies in after the gate'

    def test_gate_clears_gunners_and_their_bullets(self, game):
        reach_boss(game)
        assert game.gunners == [], 'gunners have no natural exit; they are cleared'
        assert game.enemy_bullets == []

    def test_leftover_falling_enemies_finish_and_do_not_respawn(self, game):
        reach_boss(game)
        # Force a leftover falling enemy just above the bottom edge.
        game.enemies = [Enemy(100, settings.HEIGHT - 5)]
        steps = 0
        while game.enemies and steps < 200:
            game._update_game(KeyState(), DT)
            steps += 1
        assert game.enemies == [], 'leftover enemies should fall out, not recycle'

    def test_no_new_enemies_spawn_after_the_gate(self, game):
        reach_boss(game)
        counts = [len(game.enemies), len(game.gunners)]
        for _ in range(600):
            game._update_game(KeyState(), DT)
            counts[0] = max(counts[0], len(game.enemies))
            counts[1] = max(counts[1], len(game.gunners))
        # Falling enemies only ever leave; gunners only arrive from minions
        # (phase 3), which a full-HP boss never reaches here.
        assert counts[0] <= settings.INITIAL_ENEMY_COUNT
        assert counts[1] == 0

    def test_boss_level_never_ship_exits(self, game):
        reach_boss(game)
        game.score = 9999
        game._check_level_completion()
        assert game._ship_exit_active is False
        assert game.boss is not None

    def test_gate_is_one_shot(self, game):
        reach_boss(game)
        boss = game.boss
        game._check_level_completion()
        game._check_level_completion()
        assert game.boss is boss, 'the boss must not be replaced by re-gating'

    def test_normal_levels_still_ship_exit(self, game):
        start_game(game)
        assert game.current_level == 0
        game.score = game.level_score_target
        game._check_level_completion()
        assert game._ship_exit_active is True
        assert game.boss is None


class TestEnemyMixPerLevel:
    def test_level_1_wave_is_falling_enemies_only(self, game):
        game.current_level = 0
        game._spawn_level_wave()
        assert game.enemies and game.gunners == []

    def test_level_2_wave_is_gunners_only(self, game):
        game.current_level = 1
        game._spawn_level_wave()
        assert game.gunners and game.enemies == []

    def test_level_3_wave_mixes_both_types(self, game):
        game.current_level = settings.BOSS_LEVEL_INDEX
        game._spawn_level_wave()
        assert game.enemies and game.gunners

    def test_replenishment_keeps_the_mix_level_exclusive(self, game):
        """Running the replenish pass with maximum difficulty must never
        introduce the other level's enemy type."""
        game.current_level = 0
        game._spawn_level_wave()
        game._scale_and_replenish_wave(1.0)
        assert all(isinstance(e, Enemy) for e in game.enemies)
        assert game.gunners == []

        game.current_level = 1
        game._spawn_level_wave()
        game._scale_and_replenish_wave(1.0)
        assert all(isinstance(e, GunnerEnemy) for e in game.gunners)
        assert game.enemies == []

        game.current_level = settings.BOSS_LEVEL_INDEX
        game._spawn_level_wave()
        game._scale_and_replenish_wave(1.0)
        assert game.enemies and game.gunners


class TestPhase3MinionsInGame:
    def test_minions_spawn_as_gunner_type_only(self, game):
        reach_boss(game)
        assert wait_for_boss_active(game)
        game.boss.hp = 5  # phase 3
        game.gunners = []
        game.enemies = []
        spawned = 0
        for _ in range(int((settings.BOSS_MINION_INTERVAL_SECONDS + 1.0) / DT)):
            game._update_game(KeyState(), DT)
            spawned = len(game.gunners)
            if spawned:
                break
        assert spawned >= 1, 'phase 3 should have spawned a minion'
        assert all(isinstance(g, GunnerEnemy) for g in game.gunners)
        assert game.enemies == [], 'minions are gunner-type only'


# ── Boss bullets: same rules as gunner bullets ────────────────────────


class TestBossBullets:
    def test_angled_bullet_travels_and_cleans_up_off_screen(self):
        b = EnemyBullet(settings.WIDTH // 2, 0, angle_degrees=45.0)
        for _ in range(400):
            b.update(DT)
            if b.off_screen:
                break
        assert b.off_screen, 'an angled bullet must eventually leave the screen'
        assert b.x > settings.WIDTH

    def test_straight_bullet_still_despawns_below_screen(self):
        b = EnemyBullet(settings.WIDTH // 2, 0)
        for _ in range(400):
            b.update(DT)
            if b.off_screen:
                break
        assert b.off_screen

    def test_shield_blocks_a_boss_bullet(self, game):
        start_game(game)
        _no_enemies(game)
        p = game.player
        p.x, p.y = 100.0, 500.0
        p.shield_timer = 2.0
        shot = EnemyBullet(p.x, p.y)
        game.enemy_bullets = [shot]
        health = p.health
        game._update_game(KeyState(), DT)
        assert p.health == health, 'shield must absorb the bullet entirely'
        assert shot not in game.enemy_bullets

    def test_unblocked_boss_bullet_damages_and_starts_iframes(self, game):
        start_game(game)
        _no_enemies(game)
        p = game.player
        p.x, p.y = 100.0, 500.0
        shot = EnemyBullet(p.x, p.y)
        game.enemy_bullets = [shot]
        health = p.health
        game._update_game(KeyState(), DT)
        assert p.health == health - 1
        assert p.invulnerable_timer > 0


# ── Health bar ────────────────────────────────────────────────────────


class TestBossHealthBar:
    def test_assets_are_loaded_at_the_configured_size(self, game):
        assert game.assets.boss_img.get_size() == settings.BOSS_IMG_SIZE
        assert (
            game.assets.boss_health_full_img.get_size()
            == settings.BOSS_HEALTH_BAR_SIZE
        )
        assert (
            game.assets.boss_health_empty_img.get_size()
            == settings.BOSS_HEALTH_BAR_SIZE
        )

    def test_missing_boss_asset_falls_back_to_a_placeholder(self, monkeypatch):
        from assets import _load_scaled_image_or_placeholder

        surf = _load_scaled_image_or_placeholder(
            'Assets/definitely-not-here.png', (12, 34), (1, 2, 3, 255)
        )
        assert surf.get_size() == (12, 34)
        assert surf.get_at((0, 0))[:3] == (1, 2, 3)

    def test_fill_width_tracks_hp(self):
        width = settings.BOSS_HEALTH_BAR_SIZE[0]
        assert Game._boss_bar_fill_width(40, 40, width) == width
        assert Game._boss_bar_fill_width(0, 40, width) == 0
        # Half HP fills half the bar (round() covers an odd bar width).
        assert Game._boss_bar_fill_width(20, 40, width) == round(width / 2)
        # Monotonic: more HP is never a shorter fill.
        widths = [Game._boss_bar_fill_width(hp, 40, width) for hp in range(41)]
        assert widths == sorted(widths)
        assert all(0 <= w <= width for w in widths)
        # Defensive: out-of-range / zero max must not divide by zero.
        assert Game._boss_bar_fill_width(99, 40, width) == width
        assert Game._boss_bar_fill_width(-5, 40, width) == 0
        assert Game._boss_bar_fill_width(0, 0, width) == 0

    def test_bar_does_not_overlap_the_player_health_bar(self, game):
        """The boss fight is the only place both bars are on screen at once,
        so their real rects must not intersect."""
        start_game(game)
        game.boss = _active_boss()
        bar = game._boss_bar_rect()
        player_bar = game.assets.health_images[0].get_rect(
            topleft=settings.PLAYER_HEALTH_POS
        )
        assert not bar.colliderect(player_bar)
        assert bar.left > player_bar.right, 'the bars are side by side, not stacked'
        assert bar.left >= 0 and bar.right <= settings.WIDTH
        assert bar.top >= 0 and bar.bottom <= settings.HEIGHT

    def test_bar_is_redrawn_from_live_hp(self, game):
        """The rendered fill must shrink as the boss takes damage - the
        alpha crossfade this replaced kept a full-length bar that only
        faded, so it never read as HP loss."""
        start_game(game)
        _no_enemies(game)
        game.boss = _active_boss(hp=settings.BOSS_HP)
        rect = game._boss_bar_rect()

        def fill_pixels(hp: int) -> int:
            game.boss.hp = hp
            game.screen.fill(settings.BLACK)
            game._draw_boss_health_bar()
            found = 0
            for x in range(rect.left, rect.right):
                for y in range(rect.top, rect.bottom):
                    r, g, b = game.screen.get_at((x, y))[:3]
                    if r > g + 20 and r > b + 20:
                        found += 1
            return found

        full = fill_pixels(settings.BOSS_HP)
        half = fill_pixels(settings.BOSS_HP // 2)
        low = fill_pixels(4)
        assert full > 0, 'the bar must actually render a fill'
        assert half < full * 0.75, 'half HP must look like half a bar'
        assert low < half * 0.5, 'near-death must look nearly empty'
        assert fill_pixels(0) == 0, 'no fill at all at 0 HP'

    def test_bar_renders_in_its_new_place_while_active(self, game):
        start_game(game)
        _no_enemies(game)
        game.boss = _active_boss(hp=settings.BOSS_HP)
        game.screen.fill(settings.BLACK)
        game._draw_boss_health_bar()
        rect = game._boss_bar_rect()
        painted = sum(
            1
            for x in range(rect.left, rect.right, 3)
            for y in range(rect.top, rect.bottom, 3)
            if game.screen.get_at((x, y))[:3] != (0, 0, 0)
        )
        assert painted > 50, 'the bar should be drawn inside its own rect'

    def test_bar_is_visible_only_once_the_boss_is_active(self, game):
        start_game(game)
        _no_enemies(game)
        assert game._boss_bar_visible() is False, 'no boss, no bar'

        game.boss = Boss(settings.WIDTH, settings.HEIGHT)
        assert game._boss_bar_visible() is False, 'no bar during the entrance'

        game.boss.y = float(settings.BOSS_ACTIVE_Y)
        game.boss.base_y = game.boss.y
        game.boss.entering = False
        assert game._boss_bar_visible() is True

        game.boss_dying = True
        assert game._boss_bar_visible() is False, 'no bar during the death chain'

    def test_bar_draws_without_crashing_while_active(self, game):
        start_game(game)
        _no_enemies(game)
        game.boss = _active_boss()
        game._draw_frame((0, 0))


# ── Victory sequence ──────────────────────────────────────────────────


class TestVictorySequence:
    def test_killing_hit_flashes_and_schedules_a_staggered_chain(self, game):
        start_game(game)
        _no_enemies(game)
        game.boss = _active_boss()
        game._begin_boss_death()
        assert game.boss_dying is True
        assert game.victory_flash.timer > 0, 'the killing hit flashes the screen first'

        chain = game.boss_death_chain
        assert len(chain) == settings.BOSS_DEATH_EXPLOSION_COUNT + 1
        times = [entry[0] for entry in chain]
        # Evenly staggered by the configured interval, ending with the final
        # full-sprite blast (the 4-5 s total is asserted separately).
        for a, b in zip(times, times[1:]):
            assert b - a == pytest.approx(settings.BOSS_DEATH_EXPLOSION_INTERVAL_SECONDS)
        assert chain[-1][3] > 1.0, 'the final blast is bigger than the chain blasts'
        assert chain[-1][0] == pytest.approx(
            settings.BOSS_DEATH_EXPLOSION_COUNT
            * settings.BOSS_DEATH_EXPLOSION_INTERVAL_SECONDS
        )

    def test_chain_explosions_actually_fire_over_several_steps(self, game):
        start_game(game)
        _no_enemies(game)
        game.boss = _active_boss()
        game._begin_boss_death()

        spawn_times = []
        previous = 0
        for _ in range(int(5.0 / DT)):
            game._update_boss_death(DT)
            if len(game.explosions) > previous:
                spawn_times.append(game.boss_death_timer)
                previous = len(game.explosions)
        assert len(spawn_times) == settings.BOSS_DEATH_EXPLOSION_COUNT + 1
        gaps = [b - a for a, b in zip(spawn_times, spawn_times[1:])]
        for gap in gaps:
            assert gap == pytest.approx(settings.BOSS_DEATH_EXPLOSION_INTERVAL_SECONDS, abs=DT * 2)

    def test_clear_flow_goes_straight_to_the_end_of_run_screen(self, game):
        """No dedicated victory screen: the flash + staggered chain + ship
        exit hand off to the restart/quit screen."""
        start_game(game)
        _no_enemies(game)
        game.boss = _active_boss()
        game._begin_boss_death()

        seen: list[str] = []
        for _ in range(int(20.0 / DT)):
            game._update_game(KeyState(), DT)
            game._advance_transitions()
            if not seen or seen[-1] != game.state:
                seen.append(game.state)
            if game.state == 'game_over':
                break

        assert game.state == 'game_over', f'never reached the end of the run: {seen}'
        assert 'victory' not in seen, f'a victory screen must not play, saw {seen}'
        # The chain hands off with no text overlay at all (that overlay WAS the
        # removed screen).
        assert game.fade_text.active is False
        assert game.run_finished is True
        assert game.boss is None, 'the boss is gone once the chain finishes'
        # ...which is not the end of the sequence: the ship then flies out
        # through the shared exit before the screen appears.
        assert game._ship_exit_leads_to == 'game_over'
        assert game.player.y + game.player.height < 0, 'the ship left the screen'
        # The completed run is still recorded on the time leaderboard, even
        # though the screen that used to write it is gone.
        entries = game.high_scores.entries
        assert entries and entries[0].result == 'Finished'
        assert game.last_run_rank is not None

    def test_full_fight_reaches_the_end_of_run(self, game):
        reach_boss(game)
        assert kill_boss(game), 'the boss fight never reached the end-of-run screen'
        assert game.state == 'game_over'
        assert game.run_finished is True

    def test_the_boss_gate_itself_has_no_ship_exit_transition(self, game):
        """Reaching the score gate starts the boss, not the ship exit: at the
        gate there is no exit and no 'Level Finished' overlay. The exit only
        happens much later, once the boss is dead and has finished exploding."""
        reach_boss(game)
        assert game._ship_exit_active is False
        assert game._level_transition_pending is False
        assert game.fade_text.text != 'Level Finished'


# ── The multi-stage death sequence ────────────────────────────────────


class TestBossDeathSequence:
    """Boss death is a sequence, not a single hand-off: 4-5 s of explosions
    scattered across the sprite's body, then the boss is removed, then the
    ship leaves the screen through the SAME exit other levels use, and only
    then does the end-of-run screen appear."""

    def _kill(self, game) -> None:
        """Start the death sequence through the real damage path (one bullet
        on a 1-HP boss), leaving the player at its normal starting position."""
        start_game(game)
        _no_enemies(game)
        game.boss = _active_boss(hp=1)
        rect = game.boss.get_rect()
        game.bullets.append(
            Bullet(rect.centerx - settings.BULLET_IMG_SIZE[0] // 2, rect.centery)
        )
        game._update_game(KeyState(), DT)
        assert game.boss_dying, 'the killing hit starts the death sequence'

    def _run_out_the_chain(self, game) -> None:
        while game.boss_dying:
            game._update_game(KeyState(), DT)

    def _drive_to_the_end_of_the_run(self, game, cap: int = 1200) -> list[str]:
        """Drive real frames to the end-of-run screen, returning the ordered
        milestones of the sequence."""
        log: list[str] = []
        was_exiting = False
        for _ in range(cap):
            game._update_and_draw((0, 0))
            game._advance_transitions()
            if game.boss_dying and 'chain' not in log:
                log.append('chain')
            elif game.boss is None and 'boss removed' not in log:
                log.append('boss removed')
            if game._ship_exit_active and not was_exiting and 'ship exit' not in log:
                log.append('ship exit')
            was_exiting = game._ship_exit_active
            if game.state == 'game_over':
                log.append('game_over')
                break
        return log

    # ---- duration and the shape of the chain ------------------------- #

    def test_sequence_duration_lands_in_the_four_to_five_second_window(self, game):
        """The whole explosion sequence is 4-5 s, and that total is derived
        from the three tunable constants rather than hardcoded anywhere."""
        self._kill(game)
        expected = (
            settings.BOSS_DEATH_EXPLOSION_COUNT
            * settings.BOSS_DEATH_EXPLOSION_INTERVAL_SECONDS
            + settings.BOSS_DEATH_HOLD_SECONDS
        )
        assert game.boss_death_duration == pytest.approx(expected)
        assert 4.0 <= game.boss_death_duration <= 5.0, game.boss_death_duration

    def test_bursts_are_spread_across_the_boss_body(self, game):
        """One burst per grid cell over the sprite's footprint: the set must
        span most of the body rather than clumping the way independent
        uniform samples do."""
        self._kill(game)
        boss = game.boss
        positions = game._boss_death_positions()
        assert len(positions) == settings.BOSS_DEATH_EXPLOSION_COUNT

        frame_w, frame_h = settings.EXPLOSION_IMG_SIZE
        for x, y in positions:
            cx, cy = x + frame_w / 2, y + frame_h / 2
            assert boss.x - frame_w <= cx <= boss.x + boss.width + frame_w, (x, y)
            assert boss.y - frame_h <= cy <= boss.y + boss.height + frame_h, (x, y)

        xs = [x for x, _ in positions]
        ys = [y for _, y in positions]
        assert max(xs) - min(xs) > boss.width / 2, 'bursts must span the width'
        assert max(ys) - min(ys) > boss.height / 2, 'bursts must span the height'

    def test_boss_is_present_for_the_whole_chain_and_removed_only_at_the_end(self, game):
        self._kill(game)
        # Two seconds in - barely half way - the sprite is still there.
        for _ in range(int(2.0 / DT)):
            game._update_game(KeyState(), DT)
        assert game.boss_dying is True
        assert game.boss is not None, 'the sprite must not vanish mid-chain'

        self._run_out_the_chain(game)
        assert game.boss is None, 'removed once the chain finishes'
        assert game.boss_death_chain == []
        assert game.boss_death_timer >= game.boss_death_duration

    # ---- the hand-off: shared ship exit, then the end-of-run screen --- #

    def test_chain_hands_off_to_the_shared_ship_exit(self, game, monkeypatch):
        """The boss ending flies the ship out through the SAME helpers a
        normal level uses. Spying on them is the proof that this is shared
        code and not a second, parallel implementation."""
        calls: list[tuple[str, str | None]] = []
        begin = Game._begin_ship_exit
        advance = Game._advance_ship_exit
        monkeypatch.setattr(
            Game,
            '_begin_ship_exit',
            lambda self, leads_to: (calls.append(('begin', leads_to)), begin(self, leads_to))[1],
        )
        monkeypatch.setattr(
            Game,
            '_advance_ship_exit',
            lambda self, dt: (calls.append(('advance', None)), advance(self, dt))[1],
        )

        self._kill(game)
        log = self._drive_to_the_end_of_the_run(game)

        assert ('begin', 'game_over') in calls, 'the boss ending must use the shared exit'
        assert ('advance', None) in calls, 'and the shared per-frame motion'
        assert log.index('boss removed') < log.index('ship exit') < len(log) - 1, log
        assert log[-1] == 'game_over', log

    def test_a_normal_level_clear_uses_the_same_helpers(self, game, monkeypatch):
        """The other half of the shared behaviour, so the two can never drift
        apart: an ordinary level's clear calls the same helpers."""
        calls: list[str] = []
        begin = Game._begin_ship_exit
        monkeypatch.setattr(
            Game,
            '_begin_ship_exit',
            lambda self, leads_to: (calls.append(leads_to), begin(self, leads_to))[1],
        )
        start_game(game)
        game.score = game.level_score_target
        game._check_level_completion()
        assert calls == ['level_finished']

    def test_ship_exit_moves_at_the_shared_speed_and_is_dt_based(self, game):
        self._kill(game)
        self._run_out_the_chain(game)
        assert game._ship_exit_active, 'the exit starts once the boss is gone'

        start_y = game.player.y
        game._update_game(KeyState(), DT)
        assert game.player.y == pytest.approx(
            start_y - settings.SHIP_EXIT_SPEED_PER_SEC * DT
        )
        # Halving dt halves the step: speed is px/sec, never px/frame.
        game.player.y = start_y
        game._update_game(KeyState(), DT / 2)
        assert game.player.y == pytest.approx(
            start_y - settings.SHIP_EXIT_SPEED_PER_SEC * DT / 2
        )

        steps = 0
        while game._ship_exit_active and steps < 600:
            game._update_game(KeyState(), DT)
            steps += 1
        assert game.player.y + game.player.height < 0, 'off-screen to finish'

    def test_the_ship_does_not_snap_back_during_the_hand_off_fade(self, game):
        """Regression: the ship used to be re-clamped back into the playfield
        for the frames between the exit finishing and the state changing, so
        it visibly popped back on top of an empty screen just before the
        end-of-run screen appeared."""
        self._kill(game)
        self._run_out_the_chain(game)
        while game._ship_exit_active:
            game._update_game(KeyState(), DT)
            game._advance_transitions()
        assert game.player.y + game.player.height < 0

        while game.state == 'game':
            game._update_game(KeyState(), DT)
            game._advance_transitions()
            assert game.player.y + game.player.height < 0, (
                'the ship must stay gone until the state changes'
            )
        assert game.state == 'game_over'

    def test_leaderboard_write_happens_after_the_ship_leaves(self, game, monkeypatch):
        """The Finished entry moved later with the sequence: writing it at
        boss death would record a time that misses the closing animation."""
        writes: list[tuple] = []
        add = game.high_scores.add

        def spy(time_seconds, result, timestamp=None):
            writes.append((result, game.player.y, game._ship_exit_active))
            return add(time_seconds, result, timestamp)

        monkeypatch.setattr(game.high_scores, 'add', spy)
        self._kill(game)
        self._drive_to_the_end_of_the_run(game)

        assert len(writes) == 1, f'exactly one write, got {writes}'
        result, y_at_write, exiting = writes[0]
        assert result == 'Finished'
        assert not exiting, 'the write must not happen while the ship is still leaving'
        assert y_at_write + game.player.height < 0, 'the ship had already left the screen'
        assert game.last_run_rank is not None

    def test_pause_during_the_hand_off_still_ends_the_run(self, game):
        """Pausing mid-hand-off cancels the fade to the end-of-run screen.
        The run must re-issue it instead of sitting frozen in an empty,
        unwinnable level."""
        self._kill(game)
        self._run_out_the_chain(game)
        while game._ship_exit_active:
            game._update_game(KeyState(), DT)
            game._advance_transitions()
        assert game._run_ending is True

        game._handle_keydown(pygame.K_ESCAPE)          # pause, cancelling the fade
        assert pump_run_until(game, lambda g: g.state == 'pause')
        game._handle_keydown(pygame.K_ESCAPE)          # resume
        pump(game, 400)
        assert game.state == 'game_over', 'the run must still end'
        finished = [e for e in game.high_scores.entries if e.result == 'Finished']
        assert len(finished) == 1, 'and be recorded exactly once'

    def test_player_killed_on_the_killing_step_still_ends_the_run(self, game):
        """A player killed in the same step as the boss has no ship left to
        fly out; the run must still end rather than stall on an exit that can
        never advance (the dead-player freeze returns before it)."""
        self._kill(game)
        game.player.dead = True
        self._run_out_the_chain(game)

        assert game._ship_exit_active is False, 'nothing to fly out'
        assert game._run_ending is True
        log = self._drive_to_the_end_of_the_run(game)
        assert log[-1] == 'game_over', log
        assert [e.result for e in game.high_scores.entries] == ['Finished']


# ── End-of-run screen (the boss-clear landing screen) ─────────────────


class TestEndOfRunScreen:
    def _show(self, game, finished: bool) -> None:
        """Put the end-of-run screen on the canvas for a death / a clear."""
        start_game(game)
        game.run_finished = finished
        game.state = 'game_over'
        _draw_on_black(game)
        game._draw_frame((0, 0))

    def test_heading_is_the_game_complete_copy_for_a_cleared_run(self, game):
        assert settings.GAME_COMPLETE_TITLE == 'Wanna go again....?'
        self._show(game, finished=True)

        limit = settings.WIDTH - 2 * settings.GAME_TITLE_MARGIN_X
        expected = _render_fitted_title(
            game.assets.big_font, settings.GAME_COMPLETE_TITLE, limit,
            settings.GAME_COMPLETE_COLOR,
        )
        rect = expected.get_rect(
            center=(settings.WIDTH // 2, settings.h_frac(1 / 4))
        )
        alpha = pygame.surfarray.array_alpha(expected)
        actual = pygame.surfarray.array3d(game.screen.subsurface(rect))
        wanted = pygame.surfarray.array3d(expected)
        # Compare only fully-opaque glyph pixels (alpha == 255): antialiased
        # edges deliberately blend with the background. The mask used to be
        # alpha > 250, which was only pixel-exact while the heading was
        # blitted twice - the redundant blit re-blended those edge pixels
        # onto the source colour (see
        # test_heading_is_rendered_and_blitted_once).
        mask = alpha == 255
        assert mask.any(), 'the heading should render solid glyph pixels'
        assert (actual[mask] == wanted[mask]).all(), (
            'the cleared-run heading is not the game-complete copy in its gold'
        )

    def test_heading_is_game_over_for_a_death(self, game):
        self._show(game, finished=False)
        limit = settings.WIDTH - 2 * settings.GAME_TITLE_MARGIN_X
        expected = _render_fitted_title(
            game.assets.big_font, 'GAME OVER', limit, settings.GAME_OVER_COLOR
        )
        rect = expected.get_rect(
            center=(settings.WIDTH // 2, settings.h_frac(1 / 4))
        )
        alpha = pygame.surfarray.array_alpha(expected)
        actual = pygame.surfarray.array3d(game.screen.subsurface(rect))
        wanted = pygame.surfarray.array3d(expected)
        # Fully-opaque glyph cores only - the antialiased edges blend with
        # the background (see test_heading_is_rendered_and_blitted_once).
        mask = alpha == 255
        assert mask.any()
        assert (actual[mask] == wanted[mask]).all(), 'a death still reads GAME OVER'

    def test_heading_is_distinct_from_the_death_screen(self, game):
        """The gold + different copy is what still marks a cleared run as a
        WIN now that the dedicated victory screen is gone."""
        assert settings.GAME_COMPLETE_TITLE != 'GAME OVER'
        assert settings.GAME_COMPLETE_COLOR != settings.GAME_OVER_COLOR
        assert settings.GAME_COMPLETE_TITLE != 'Level Finished'

    def test_heading_fits_on_screen(self, game):
        """The heading must leave the documented margin, not run off the edges."""
        limit = settings.WIDTH - 2 * settings.GAME_TITLE_MARGIN_X
        assert game.assets.big_font.size(settings.GAME_COMPLETE_TITLE)[0] <= limit

    def test_over_long_heading_is_shrunk_to_fit(self, game):
        """Regression for the reported bug: the old victory copy rendered
        779px wide on a 768px screen, so it ran off both edges."""
        long_copy = 'THE FINAL PHASE CLEARED'
        assert game.assets.big_font.size(long_copy)[0] > settings.WIDTH, (
            'this copy is only a useful regression case while it overflows'
        )
        limit = settings.WIDTH - 2 * settings.GAME_TITLE_MARGIN_X
        fitted = _render_fitted_title(
            game.assets.big_font, long_copy, limit, settings.GAME_COMPLETE_COLOR
        )
        assert fitted.get_width() <= limit
        # A heading that already fits is returned untouched (no gratuitous
        # downscaling of the real copy).
        normal = _render_fitted_title(
            game.assets.big_font, settings.GAME_COMPLETE_TITLE, limit,
            settings.GAME_COMPLETE_COLOR,
        )
        assert normal.get_size() == game.assets.big_font.size(
            settings.GAME_COMPLETE_TITLE
        )

    def test_button_positions_are_unchanged_by_the_heading(self, game):
        """Text-only change: RESTART/QUIT must not move."""
        start_game(game)
        menu = game.game_over_menu
        reference = (menu.restart_rect.copy(), menu.quit_rect.copy())
        for finished in (False, True):
            game.run_finished = finished
            game.state = 'game_over'
            game._draw_frame((0, 0))
            assert menu.restart_rect == reference[0]
            assert menu.quit_rect == reference[1]

    def test_button_positions_match_the_documented_layout(self, game):
        """Pin the positions themselves: centred, on the uniform 100/800
        screen-height rhythm (7/16 and 9/16 down)."""
        menu = game.game_over_menu
        assert menu.restart_rect.centerx == settings.WIDTH // 2
        assert menu.quit_rect.centerx == settings.WIDTH // 2
        assert menu.restart_rect.centery == settings.h_frac(7 / 16)
        assert menu.quit_rect.centery == settings.h_frac(9 / 16)
        assert menu.restart_rect.size == game.assets.restart_img.get_size()
        assert menu.quit_rect.size == game.assets.quit_gameover_img.get_size()

    def test_restart_from_the_cleared_run_screen_starts_a_fresh_run(self, game):
        reach_boss(game)
        assert kill_boss(game)
        assert game.run_finished is True
        game._handle_mouse_click(game.game_over_menu.restart_rect.center)
        assert game.current_level == 0, 'a completed run restarts from Level 1'
        assert game.checkpoint_level == 0
        assert game.run_finished is False
        assert game.boss is None
        assert game.boss_phase_active is False
        assert game.run_timer == 0.0, 'a completed run restarts the timer'

    def test_quit_from_the_cleared_run_screen_returns_to_the_menu(self, game):
        reach_boss(game)
        assert kill_boss(game)
        assert game.state == 'game_over'
        game._handle_mouse_click(game.game_over_menu.quit_rect.center)
        pump_fade(game)
        assert game.state == 'menu'

    @pytest.mark.parametrize('finished, title, color', _END_OF_RUN_VARIANTS)
    def test_heading_is_rendered_and_blitted_once(
        self, game, monkeypatch, finished, title, color
    ):
        """Exactly one heading render and one heading blit, both variants.

        Regression for the reported black-text artifact: `draw()` rendered
        the heading twice - a black drop shadow built from the *hardcoded*
        string "GAME OVER" (so a cleared run got black "GAME OVER" glyphs
        behind its gold heading), plus a duplicate blit of the heading
        surface itself.
        """
        renders: list[tuple[str, tuple[int, int, int], pygame.Surface]] = []
        original = menus._render_fitted_title

        def spy(font, text, max_width, render_color):
            surface = original(font, text, max_width, render_color)
            renders.append((text, render_color, surface))
            return surface

        monkeypatch.setattr(menus, '_render_fitted_title', spy)
        recorder = _BlitRecorder(game.screen)
        game.game_over_menu.draw(recorder, (0, 0), title=title, color=color)

        assert len(renders) == 1, f'the heading was rendered {len(renders)} times'
        rendered_text, rendered_color, surface = renders[0]
        assert rendered_text == title, 'the screen rendered a different string'
        assert rendered_color == color
        assert recorder.count(surface) == 1, 'the heading was blitted more than once'
        assert recorder.calls, 'the screen drew nothing at all'

    @pytest.mark.parametrize('finished, title, color', _END_OF_RUN_VARIANTS)
    def test_only_the_headings_own_glyphs_are_drawn(
        self, game, finished, title, color
    ):
        """Nothing is drawn in the heading band except the heading's glyphs.

        The reported artifact was a black ghost showing through the gaps of
        the gold heading - the old shadow, rendered from a hardcoded "GAME
        OVER". Everything the heading contributes is isolated here by
        re-rendering the identical screen with the heading suppressed and
        diffing the two frames.
        """
        game.run_finished = finished
        game.state = 'game_over'
        _draw_on_black(game)
        game._draw_frame((0, 0))
        with_heading = pygame.surfarray.array3d(game.screen).astype(int)

        menu = game.game_over_menu
        original_draw = menu.draw

        def headingless(screen, mouse_pos, title='GAME OVER', color=None):
            return original_draw(screen, mouse_pos, title='', color=color)

        menu.draw = headingless
        try:
            _draw_on_black(game)
            game._draw_frame((0, 0))
            without_heading = pygame.surfarray.array3d(game.screen).astype(int)
        finally:
            del menu.draw

        delta = np.abs(with_heading - without_heading).max(axis=2) > 8
        assert delta.any(), 'the heading itself should have been drawn'

        surface = _render_fitted_title(
            game.assets.big_font,
            title,
            settings.WIDTH - 2 * settings.GAME_TITLE_MARGIN_X,
            color,
        )
        rect = surface.get_rect(center=(settings.WIDTH // 2, settings.h_frac(1 / 4)))
        alpha = pygame.surfarray.array_alpha(surface)
        glyphs = np.zeros((settings.WIDTH, settings.HEIGHT), bool)
        glyphs[rect.left:rect.right, rect.top:rect.bottom] = alpha > 0
        glyphs = _dilate(glyphs)

        stray = int((delta & ~glyphs).sum())
        assert stray == 0, (
            f'{stray} px of ink outside the heading\'s own glyphs - a ghost '
            f'glyph such as the old hardcoded "GAME OVER" shadow'
        )
