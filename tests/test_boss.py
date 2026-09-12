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
- the victory sequence: flash, staggered chain, victory screen, end of run.
"""

import pytest

import settings
from boss import Boss
from bullet import Bullet
from enemy import Enemy
from enemy_bullet import EnemyBullet
from game import Game
from gunner import GunnerEnemy
from helpers import KeyState, kill_boss, reach_boss, start_game, wait_for_boss_active

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


def _run_boss(boss: Boss, seconds: float, player_x: float = 300.0):
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
            bullets, minions = boss.update(DT, 300.0, settings.WIDTH)
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
            boss.update(DT, 300.0, settings.WIDTH)
        assert boss.x == x0, 'the boss should drop straight in, not drift while entering'


# ── Movement ──────────────────────────────────────────────────────────


class TestMovement:
    def test_drift_stays_within_the_bounded_band(self):
        boss = _active_boss()
        left = settings.BOSS_DRIFT_MARGIN
        right = settings.WIDTH - boss.width - settings.BOSS_DRIFT_MARGIN
        xs = []
        for _ in range(int(20 / DT)):
            boss.update(DT, 300.0, settings.WIDTH)
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
            boss.update(DT, 300.0, settings.WIDTH)
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
            bullets, _minions, _c, _b = _run_boss(boss, DT, 300.0)
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
        player_x, player_y = 120.0, 700.0
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
        player_x, player_y = 120.0, 700.0
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
        shots = _burst_volley(boss, 120.0, 700.0)
        angles = [b.angle_degrees for _m, b in shots]
        assert max(angles) - min(angles) < 5.0

    def test_burst_angle_is_clamped_to_a_downward_shot(self):
        boss = _active_boss(hp=20)
        # A target far off to the side must not produce a flat/horizontal shot.
        boss.aim_target_x = -5_000.0
        boss.aim_target_y = 760.0
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
        shots = _burst_volley(boss, 520.0, settings.BOSS_AIM_DEFAULT_TARGET_Y)
        assert shots
        for _muzzle, bullet in shots:
            assert bullet.vy > 0
            assert _shot_crossing_x(
                bullet, settings.BOSS_AIM_DEFAULT_TARGET_Y
            ) == pytest.approx(520.0, abs=2.0)

    def test_burst_tracks_the_player_until_it_fires(self):
        """The charge window re-tracks every step, so a moving player is
        aimed at where they are when the shot leaves - not where they were
        when the charge began."""
        boss = _active_boss(hp=20)
        boss.spread_cooldown = 10_000.0
        boss.aim_charge = settings.BOSS_AIM_CHARGE_SECONDS
        # Move the player across the screen during the charge.
        for i in range(int(settings.BOSS_AIM_CHARGE_SECONDS / DT) - 1):
            boss.update(DT, 100.0 + i * 10.0, settings.WIDTH, 700.0)
        # The charge completes on this step: the target locks to x=500.
        boss.update(DT, 500.0, settings.WIDTH, 700.0)
        fired: list[EnemyBullet] = []
        for _ in range(30):
            fired, _m, _c, _b = _run_boss(boss, DT, 999.0)
            if fired:
                break
        assert fired, 'the burst should fire once the charge completes'
        assert _shot_crossing_x(fired[0], 700.0) == pytest.approx(500.0, abs=2.0)

    def test_aim_charge_is_the_telegraph_window(self):
        boss = _active_boss(hp=20)
        boss.aim_cooldown = 0.0
        _run_boss(boss, DT)  # one step starts the charge
        assert boss.aim_target_visible(), 'charge should be visible right after it starts'
        # Charge lasts about BOSS_AIM_CHARGE_SECONDS of simulated time.
        steps = 0
        while boss.aim_target_visible() and steps < 1000:
            boss.update(DT, 300.0, settings.WIDTH)
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
        assert Game._boss_bar_fill_width(20, 40, width) == width // 2
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
        # Staggered ~150 ms apart, ending with the final full-sprite blast.
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

    def test_sequence_ends_at_the_victory_screen_then_game_over(self, game):
        start_game(game)
        _no_enemies(game)
        game.boss = _active_boss()
        game._begin_boss_death()

        seen_victory = False
        for _ in range(int(20.0 / DT)):
            game._update_game(KeyState(), DT)
            game._advance_transitions()
            if game.state == 'victory':
                seen_victory = True
                assert game.fade_text.text == settings.BOSS_VICTORY_TEXT
            if game.state == 'game_over':
                break
        assert seen_victory, 'a dedicated victory screen must play'
        assert game.state == 'game_over'
        assert game.run_finished is True
        assert game.boss is None, 'the boss is gone once the chain finishes'
        entries = game.high_scores.entries
        assert entries and entries[0].result == 'Finished'

    def test_victory_screen_is_blank_black(self, game):
        start_game(game)
        game.state = 'victory'
        _draw_on_black(game)
        game._draw_frame((0, 0))
        for x in range(0, settings.WIDTH, 50):
            for y in range(0, settings.HEIGHT, 50):
                assert game.screen.get_at((x, y))[:3] == (0, 0, 0)

    def test_victory_text_is_distinct_and_gold(self, game):
        assert settings.BOSS_VICTORY_TEXT != 'Level Finished'
        assert settings.BOSS_VICTORY_COLOR != settings.FADE_TEXT_COLOR
        game.fade_text.reset(settings.BOSS_VICTORY_TEXT)
        game.fade_text.alpha = 255
        game.screen.fill(settings.BLACK)
        game.fade_text.draw(game.screen, game.assets.big_font, settings.BOSS_VICTORY_COLOR)
        found = False
        for x in range(0, settings.WIDTH, 3):
            for y in range(0, settings.HEIGHT, 3):
                if game.screen.get_at((x, y))[:3] == settings.BOSS_VICTORY_COLOR:
                    found = True
                    break
            if found:
                break
        assert found, 'the victory text should render in its own gold'

    def test_full_fight_reaches_the_end_of_run(self, game):
        reach_boss(game)
        assert kill_boss(game), 'the boss fight never reached the end-of-run screen'
        assert game.state == 'game_over'
        assert game.run_finished is True

    def test_restart_after_victory_starts_a_fresh_run(self, game):
        reach_boss(game)
        assert kill_boss(game)
        game._handle_mouse_click(game.game_over_menu.restart_rect.center)
        assert game.current_level == 0
        assert game.checkpoint_level == 0
        assert game.run_finished is False
        assert game.boss is None
        assert game.boss_phase_active is False

    def test_boss_level_has_no_ship_exit_transition(self, game):
        """The boss level deliberately skips the ship-exit + 'Level Finished'
        flow other levels use."""
        reach_boss(game)
        assert game._ship_exit_active is False
        assert game._level_transition_pending is False
        assert game.fade_text.text != 'Level Finished'
