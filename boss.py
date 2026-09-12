"""The Level 3 boss: "The Final Phase".

The boss is a single, much larger enemy with its own state machine:

    entering  -> drops in from above the screen (invulnerable, silent)
    active    -> continuous horizontal drift + gentle vertical bob, firing
                 one of three escalating attack sets depending on its HP
                 fraction (see settings.BOSS_* for every tunable)

It deals no contact damage and has no weak points: one full-sprite rect,
and - unlike normal enemies - no invulnerability window at all. Every
player bullet that overlaps it deals exactly one point of damage, so the
fight is a pure damage race.

The class owns only the boss's own behaviour (movement, phases, attack
timing). It deliberately does not touch the game's bullet/explosion lists:
`update()` returns the bullets it wants spawned plus how many minions to
spawn, and the caller (Game) appends them. That keeps the whole fight
drivable from a unit test with no game loop.
"""

from __future__ import annotations

import math
import random

import pygame

import settings
from enemy_bullet import EnemyBullet


class Boss:
    """The Level 3 boss. See the module docstring for the contract."""

    def __init__(self, screen_width: int, screen_height: int) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height

        self.width = settings.BOSS_IMG_SIZE[0]
        self.height = settings.BOSS_IMG_SIZE[1]
        # Start centered horizontally, fully above the screen.
        self.x = (screen_width - self.width) / 2.0
        self.y = -float(self.height)
        self.base_y = -float(self.height)

        self.max_hp = settings.BOSS_HP
        self.hp = settings.BOSS_HP

        # Entrance state: True until it settles at BOSS_ACTIVE_Y.
        self.entering = True

        # Movement: horizontal drift direction + vertical bob phase.
        self.drift_dir = 1 if random.random() < 0.5 else -1
        self.bob_time = 0.0

        # Attack timers.
        self.spread_cooldown = 0.0
        self.aim_cooldown = 0.0
        self.aim_charge = 0.0  # > 0 while the aimed burst is charging
        self.aim_target_x = screen_width / 2.0
        self.aim_target_y = float(settings.BOSS_AIM_DEFAULT_TARGET_Y)
        self.burst_shots_left = 0
        self.burst_cooldown = 0.0
        self.minion_cooldown = 0.0
        self.minion_spawn_index = 0  # alternates the minion drop point

        # Visual feedback timers (seconds).
        self.hit_flash = 0.0

    # ------------------------------------------------------------------ #
    # State
    # ------------------------------------------------------------------ #

    @property
    def phase(self) -> int:
        """Current attack phase (1, 2 or 3) from the HP fraction.

        At the default 40 HP: phase 1 is HP 27-40, phase 2 is 14-26, and
        phase 3 is 0-13 - the documented thirds of the health bar.
        """
        fraction = self.hp / self.max_hp if self.max_hp > 0 else 0.0
        if fraction > settings.BOSS_PHASE_1_MIN_FRACTION:
            return 1
        if fraction > settings.BOSS_PHASE_2_MIN_FRACTION:
            return 2
        return 3

    @property
    def active(self) -> bool:
        """True once the boss has settled into its fight position."""
        return not self.entering

    def get_rect(self) -> pygame.Rect:
        """Full-sprite collision rect - no weak points, no sub-hitboxes."""
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def take_damage(self, amount: int = 1) -> int:
        """Apply damage unconditionally (no i-frames) and return the new HP."""
        self.hp = max(0, self.hp - amount)
        self.hit_flash = settings.BOSS_HIT_FLASH_SECONDS
        return self.hp

    # ------------------------------------------------------------------ #
    # Simulation
    # ------------------------------------------------------------------ #

    def update(
        self,
        dt: float,
        player_x: float,
        screen_width: int,
        player_y: float | None = None,
    ) -> tuple[list[EnemyBullet], int]:
        """Advance one fixed simulation step.

        Returns ``(bullets, minions)``: the bullets the boss fired this step
        and how many minion enemies it wants spawned.

        ``player_y`` is the row the aimed burst should converge on; it
        defaults to BOSS_AIM_DEFAULT_TARGET_Y (the player's spawn row) so a
        caller that only tracks the player horizontally still gets sane aim.
        """
        self.hit_flash = max(0.0, self.hit_flash - dt)

        if self.entering:
            self.y += settings.BOSS_ENTRY_SPEED_PER_SEC * dt
            self.base_y = self.y
            if self.y >= settings.BOSS_ACTIVE_Y:
                self.y = float(settings.BOSS_ACTIVE_Y)
                self.base_y = self.y
                self.entering = False
                # Don't open fire on the same frame it settles: give the
                # player a beat to register the arrival.
                self.spread_cooldown = settings.BOSS_SPREAD_COOLDOWN_SECONDS[0]
                self.aim_cooldown = max(
                    settings.BOSS_AIM_COOLDOWN_SECONDS[0], self.spread_cooldown
                )
                self.minion_cooldown = settings.BOSS_MINION_INTERVAL_SECONDS
            return [], 0

        self._update_movement(dt, screen_width)

        target_y = (
            settings.BOSS_AIM_DEFAULT_TARGET_Y if player_y is None else player_y
        )
        bullets: list[EnemyBullet] = []
        bullets.extend(self._update_spread(dt))
        bullets.extend(self._update_aimed_burst(dt, player_x, target_y))
        minions = self._update_minions(dt)
        return bullets, minions

    def _update_movement(self, dt: float, screen_width: int) -> None:
        """Bounded horizontal drift + a gentle vertical bob."""
        left = settings.BOSS_DRIFT_MARGIN
        right = screen_width - self.width - settings.BOSS_DRIFT_MARGIN
        if right < left:  # degenerate window; keep it centered
            left = right = (screen_width - self.width) / 2.0

        self.x += settings.BOSS_DRIFT_SPEED_PER_SEC * self.drift_dir * dt
        if self.x <= left:
            self.x = left
            self.drift_dir = 1
        elif self.x >= right:
            self.x = right
            self.drift_dir = -1

        self.bob_time += dt
        self.y = self.base_y + math.sin(
            2.0 * math.pi * self.bob_time / settings.BOSS_BOB_PERIOD_SECONDS
        ) * settings.BOSS_BOB_AMPLITUDE

    # ------------------------------------------------------------------ #
    # Attacks
    # ------------------------------------------------------------------ #

    def _muzzle_center(self) -> tuple[float, float]:
        """The gun: bottom-center of the sprite, in screen coordinates."""
        return (self.x + self.width / 2.0, self.y + self.height * 0.8)

    def _muzzle(self) -> tuple[float, float]:
        """Bullet spawn point: bottom-center of the sprite."""
        cx, cy = self._muzzle_center()
        return (cx - settings.ENEMY_BULLET_IMG_SIZE[0] / 2.0, cy)

    def _update_spread(self, dt: float) -> list[EnemyBullet]:
        """Fan of BOSS_SPREAD_COUNT bullets, always available (all phases)."""
        self.spread_cooldown -= dt
        if self.spread_cooldown > 0:
            return []
        self.spread_cooldown = settings.BOSS_SPREAD_COOLDOWN_SECONDS[self.phase - 1]
        return self._spread_bullets()

    def _spread_bullets(self) -> list[EnemyBullet]:
        count = settings.BOSS_SPREAD_COUNT
        width = settings.BOSS_SPREAD_ANGLE_DEGREES
        x, y = self._muzzle()
        bullets: list[EnemyBullet] = []
        for i in range(count):
            # Evenly spread from -width/2 to +width/2, centered on straight down.
            if count == 1:
                angle = 0.0
            else:
                angle = -width / 2.0 + (width / (count - 1)) * i
            bullets.append(EnemyBullet(x, y, angle_degrees=angle))
        return bullets

    def _update_aimed_burst(
        self, dt: float, player_x: float, player_y: float
    ) -> list[EnemyBullet]:
        """Phase 2+: track the player, telegraph, then fire a quick burst.

        The volley leaves the boss's muzzle aimed at wherever the player was
        when the charge ended - a dodge window the player can read and
        react to.
        """
        if self.phase < 2:
            # Dropping back into phase 1 with a burst in flight is impossible
            # (HP only falls), but keep the timers from going stale anyway.
            self.aim_charge = 0.0
            self.burst_shots_left = 0
            return []

        # Mid-burst: keep firing the queued shots on a short interval. Each
        # shot re-aims from its own muzzle at the position tracked during the
        # charge, so the volley converges on one point instead of drifting off
        # it as the boss moves.
        if self.burst_shots_left > 0:
            self.burst_cooldown -= dt
            if self.burst_cooldown > 0:
                return []
            self.burst_shots_left -= 1
            self.burst_cooldown = settings.BOSS_AIM_BURST_INTERVAL_SECONDS
            return [self._burst_bullet()]

        # Charging: keep tracking the player so the shot lands where they are
        # when it fires, and let the tint telegraph the timing.
        if self.aim_charge > 0:
            self.aim_charge -= dt
            self.aim_target_x = player_x
            self.aim_target_y = player_y
            if self.aim_charge <= 0:
                self.aim_charge = 0.0
                self.aim_target_x = player_x
                self.aim_target_y = player_y
                self.burst_shots_left = settings.BOSS_AIM_BURST_COUNT
                self.burst_cooldown = 0.0
            return []

        # Idle: wait out the cooldown, then begin charging.
        self.aim_cooldown -= dt
        if self.aim_cooldown > 0:
            return []
        self.aim_charge = settings.BOSS_AIM_CHARGE_SECONDS
        self.aim_target_x = player_x
        self.aim_target_y = player_y
        self.aim_cooldown = settings.BOSS_AIM_COOLDOWN_SECONDS[self.phase - 1]
        return []

    def _aim_angle(self) -> float:
        """Angle (degrees) from the boss's muzzle to the tracked target.

        EnemyBullet's convention is 0 = straight down, positive = fanning
        right, so this is just the atan2 of the muzzle-to-target offset
        against the downward axis. Clamped to +-BOSS_AIM_MAX_ANGLE_DEGREES
        so the burst is always a downward volley rather than a flat shot
        when the player is level with (or above) the boss.
        """
        cx, cy = self._muzzle_center()
        dx = self.aim_target_x - cx
        dy = self.aim_target_y - cy
        if dy <= 0:
            return 0.0
        angle = math.degrees(math.atan2(dx, dy))
        limit = settings.BOSS_AIM_MAX_ANGLE_DEGREES
        return max(-limit, min(limit, angle))

    def _burst_bullet(self) -> EnemyBullet:
        """One aimed-burst shot: leaves the boss's own muzzle, on the line to
        the position tracked during the charge.

        The shots must be seen to come FROM the boss - spawning them at the
        tracked column instead made them appear in mid-air beside the ship,
        which reads as a bug (and as if they spawned near the player).
        """
        x, y = self._muzzle()
        return EnemyBullet(x, y, angle_degrees=self._aim_angle())

    def _update_minions(self, dt: float) -> int:
        """Phase 3 only: periodically request one gunner-type minion."""
        if self.phase < 3:
            return 0
        self.minion_cooldown -= dt
        if self.minion_cooldown > 0:
            return 0
        self.minion_cooldown = settings.BOSS_MINION_INTERVAL_SECONDS
        self.minion_spawn_index += 1
        return 1

    def minion_spawn_pos(self) -> tuple[float, float]:
        """Where a requested minion should appear: just under the boss, at a
        point that alternates left/right across the boss's width.

        The drifting boss already moves the drop point between spawns, but at
        the faster phase-3 cadence a boss turning around at an edge could
        drop two minions in nearly the same place. Alternating the offset
        keeps them apart even then.
        """
        offset = settings.BOSS_MINION_SPAWN_SPREAD * self.width
        cx = self.x + self.width / 2.0
        cx += offset if self.minion_spawn_index % 2 else -offset
        x = cx - settings.ENEMY_WIDTH / 2.0
        # Never drop one half off the playfield.
        x = max(0.0, min(float(self.screen_width - settings.ENEMY_WIDTH), x))
        return (x, self.y + self.height)

    # ------------------------------------------------------------------ #
    # Rendering helpers
    # ------------------------------------------------------------------ #

    def aim_target_visible(self) -> bool:
        """True while the aimed burst is charging (the telegraph window)."""
        return self.aim_charge > 0.0
