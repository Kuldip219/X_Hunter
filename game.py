"""The Game class: owns all game state and runs the main loop."""

from __future__ import annotations

import random

import pygame

import settings
import ui
from assets import Assets
from audio import AudioManager
from bullet import Bullet
from difficulty import Difficulty
from enemy import Enemy
from explosion import Explosion
from highscores import HighScoreTable
from menus import ControlsScreen, GameOverMenu, HighScoresMenu, MainMenu, OptionsScreen, PauseMenu
from player import Player
from powerup import PowerUp
from settings_store import UserSettings


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.font.init()

        self.screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT))
        pygame.display.set_caption(settings.CAPTION)
        self.clock = pygame.time.Clock()

        self.assets = Assets.load()

        # Persisted user settings (music/SFX volumes). Loaded before the audio
        # manager is built so its volumes are applied before anything plays.
        self.user_settings = UserSettings.load()
        self.audio = AudioManager(settings_store=self.user_settings)

        # Persistent top-10 leaderboard (JSON next to the working dir).
        # last_run_rank tracks where the most recent run landed on it (None
        # when it didn't qualify), used to highlight that row on the
        # high-scores screen.
        self.high_scores = HighScoreTable.load()
        self.last_run_rank = None

        self.main_menu = MainMenu(self.assets, settings.WIDTH, audio=self.audio)
        self.pause_menu = PauseMenu(self.assets, settings.WIDTH, audio=self.audio)
        self.game_over_menu = GameOverMenu(self.assets, settings.WIDTH, audio=self.audio)
        self.options_screen = OptionsScreen(
            self.assets, settings.WIDTH, settings.HEIGHT,
            audio=self.audio, store=self.user_settings,
        )
        self.high_scores_menu = HighScoresMenu(
            self.assets, settings.WIDTH, settings.HEIGHT, table=self.high_scores, audio=self.audio
        )
        self.controls_screen = ControlsScreen(
            self.assets, settings.WIDTH, settings.HEIGHT, audio=self.audio
        )

        self.screen_shake = ui.ScreenShake()
        self.damage_flash = ui.DamageFlash()
        self.fade = ui.FadeTransition((settings.WIDTH, settings.HEIGHT))
        self.shake_offset: tuple[int, int] = (0, 0)
        self.difficulty = Difficulty()

        self.running = True
        self.state = "menu"
        # Fixed-timestep accumulator: banks real elapsed time and drains it in
        # constant FIXED_DT simulation steps (see _advance_simulation).
        self.accumulator = 0.0

        # player, bullets, enemies, explosions, and score are all
        # initialized by reset_game() below.
        self.reset_game()

    # ------------------------------------------------------------------ #
    # State setup
    # ------------------------------------------------------------------ #

    def reset_game(self) -> None:
        """Start a fresh run: new player, new enemy wave, score/health reset."""
        self.player = Player(settings.WIDTH // 2, settings.HEIGHT - 80)
        self.bullets = []
        self.enemies = [
            Enemy.spawn_initial(settings.WIDTH) for _ in range(settings.INITIAL_ENEMY_COUNT)
        ]
        # Power-ups dropped by destroyed enemies (cleared on every restart).
        self.powerups = []
        self.score = 0
        self.screen_shake.timer = 0
        self.damage_flash.timer = 0
        self.explosions = []
        # Difficulty clock: elapsed survival time is measured from here, so a
        # restart always starts the ramp back at baseline (no carryover).
        self.run_start_ticks = pygame.time.get_ticks()
        # Wall-clock time spent OUTSIDE the "game" state since this run
        # started (pause/menus/game_over). Subtracted from the difficulty
        # clock so it only measures in-game time; reset alongside the clock.
        self.paused_ms = 0.0
        # A fresh run hasn't earned a leaderboard rank yet.
        self.last_run_rank = None

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        while self.running:
            # Real elapsed time since the previous rendered frame. The raw dt
            # is capped by MAX_FRAME_DT BEFORE it enters the accumulator, so a
            # huge stall banks at most 0.05 s of catch-up (3 steps) instead of
            # spiraling into dozens of simulation steps in one frame.
            raw_dt = self.clock.tick(settings.FPS) / 1000.0
            keys = pygame.key.get_pressed()
            self._advance_simulation(raw_dt, keys)

            self.screen.fill(settings.BLACK)
            mouse_pos = pygame.mouse.get_pos()

            self._handle_events(mouse_pos)
            self._draw_frame(mouse_pos)

            new_state = self.fade.update()
            if new_state is not None:
                self._change_state(new_state)
            self.fade.draw(self.screen)

            pygame.display.update()

        pygame.quit()

    def _advance_simulation(self, raw_dt: float, keys) -> int:
        """Fixed-timestep accumulator: gameplay always advances in constant
        FIXED_DT steps, decoupled from the render rate.

        Real elapsed time (capped at MAX_FRAME_DT per rendered frame) is
        banked into the accumulator; each full FIXED_DT runs one _update_game
        step. Returns the number of simulation steps run for this rendered
        frame (0..N): a fast render loop runs 0 steps on some frames, and a
        slow one runs several. Rendering, event polling, and state-machine
        transitions stay per-rendered-frame; only the simulation step is
        fixed-rate.

        While the state is not "game" (menu/pause/game_over) no simulation
        runs and the accumulator is cleared, so time spent paused or in a menu
        never fast-forwards gameplay on resume.
        """
        if self.state != "game":
            self.accumulator = 0.0
            # The difficulty clock mirrors the accumulator: it must only
            # measure time spent in the "game" state. Bank every non-game
            # rendered frame's full real duration (uncapped - all of it is
            # paused/menu time) so elapsed survival time freezes during a
            # pause and resumes exactly where it left off.
            self.paused_ms += raw_dt * 1000.0
            return 0

        self.accumulator += min(raw_dt, settings.MAX_FRAME_DT)
        steps = 0
        while self.accumulator >= settings.FIXED_DT:
            self._update_game(keys, settings.FIXED_DT)
            self.accumulator -= settings.FIXED_DT
            steps += 1
        return steps

    def _draw_frame(self, mouse_pos: tuple[int, int]) -> None:
        """Render exactly one frame from current entity state.

        Draws once per rendered frame regardless of how many simulation steps
        ran; no interpolation between steps (kept simple, per design).
        """
        if self.state == "menu":
            self.main_menu.draw(self.screen, mouse_pos)

        elif self.state == "game":
            self._draw_game()

        elif self.state == "options":
            self.options_screen.draw(self.screen, mouse_pos)

        elif self.state == "pause":
            self.pause_menu.draw(self.screen, mouse_pos)

        elif self.state == "game_over":
            self.game_over_menu.draw(self.screen, mouse_pos)

        elif self.state == "high_scores":
            self.high_scores_menu.draw(self.screen, mouse_pos, self.last_run_rank)

        elif self.state == "controls":
            self.controls_screen.draw(self.screen, mouse_pos)

        # Global (non-intrusive) indication that all audio is muted.
        if self.audio.muted:
            self._draw_mute_indicator()

    def _update_and_draw(self, mouse_pos: tuple[int, int], dt: float = 1.0 / settings.FPS) -> None:
        """Simulate one gameplay step at dt, then render one frame.

        This is the direct-drive entry point used by the test suite and the
        preview autopilot (it reproduces exactly one 60 Hz step per call).
        Game.run() uses the fixed-timestep accumulator instead, so gameplay
        stays on constant steps regardless of render rate.
        """
        if self.state == "game":
            keys = pygame.key.get_pressed()
            self._update_game(keys, dt)
        self._draw_frame(mouse_pos)

    def _change_state(self, new_state: str) -> None:
        """Apply a completed state transition and keep the music in sync."""
        self.state = new_state
        # A slider drag must never survive a state change (e.g. ESC mid-drag).
        self.options_screen._dragging = None
        if new_state == "game":
            self.audio.play_music()
        elif new_state == "pause":
            self.audio.pause_music()
        elif new_state in ("menu", "game_over", "high_scores", "controls"):
            self.audio.stop_music()

    def _draw_mute_indicator(self) -> None:
        """Small 'MUTED' label in the top-right corner while audio is off."""
        text = self.assets.font.render("MUTED", True, settings.LIGHT_GRAY)
        rect = text.get_rect(topright=(settings.WIDTH - 10, 10))
        self.screen.blit(text, rect)

    # ------------------------------------------------------------------ #
    # Events
    # ------------------------------------------------------------------ #

    def _handle_events(self, mouse_pos: tuple[int, int]) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_mouse_click(mouse_pos)

            # Slider drag support on the Options screen: motion follows the
            # mouse while a slider is held, release persists the final value.
            if event.type == pygame.MOUSEMOTION and self.state == "options":
                self.options_screen.handle_mouse_motion(event.pos)

            if event.type == pygame.MOUSEBUTTONUP and self.state == "options":
                self.options_screen.handle_mouse_up(event.pos)

            if event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)

    def _handle_mouse_click(self, mouse_pos: tuple[int, int]) -> None:
        if self.state == "menu":
            action = self.main_menu.handle_click(mouse_pos)
            if action:
                self.audio.play("menu_click")
            if action == "play":
                self.reset_game()
                self.fade.start("game")
            elif action == "options":
                self.fade.start("options")
            elif action == "exit":
                self.running = False

        elif self.state == "options":
            # A press on a slider track/handle is grabbed by the slider (no
            # click SFX); otherwise fall through to the HIGH SCORES button.
            if self.options_screen.handle_mouse_down(mouse_pos):
                return
            action = self.options_screen.handle_click(mouse_pos)
            if action:
                self.audio.play("menu_click")
            if action == "high_scores":
                self.fade.start("high_scores")
            elif action == "controls":
                self.fade.start("controls")
            elif action == "back":
                # Same transition as the ESC-from-options path.
                self.fade.start("menu")

        elif self.state == "pause":
            action = self.pause_menu.handle_click(mouse_pos)
            if action:
                self.audio.play("menu_click")
            if action == "continue":
                self.fade.start("game")
            elif action == "quit_to_menu":
                self.fade.start("menu")

        elif self.state == "game_over":
            action = self.game_over_menu.handle_click(mouse_pos)
            if action:
                self.audio.play("menu_click")
            if action == "restart":
                self.reset_game()
                self.fade.start("game")
            elif action == "quit_to_menu":
                self.fade.start("menu")

        elif self.state == "high_scores":
            action = self.high_scores_menu.handle_click(mouse_pos)
            if action:
                self.audio.play("menu_click")
            if action == "back":
                # Reached via Options, so BACK returns one level up (Options),
                # matching the ESC behavior - never straight to the menu.
                self.fade.start("options")

        elif self.state == "controls":
            action = self.controls_screen.handle_click(mouse_pos)
            if action:
                self.audio.play("menu_click")
            if action == "back":
                # Same convention as high_scores: BACK returns to Options.
                self.fade.start("options")

    def _handle_keydown(self, key: int) -> None:
        # Global mute toggle, available in every state.
        if key == pygame.K_m:
            self.audio.toggle_mute()

        # While the player is dead, gameplay is frozen: ESC cannot pause and
        # Space cannot fire until the game-over transition completes.
        if key == pygame.K_ESCAPE and self.state == "game" and not self.player.dead:
            self.fade.start("pause")
        elif key == pygame.K_ESCAPE and self.state == "pause":
            self.fade.start("game")

        if key == pygame.K_ESCAPE and self.state == "options":
            self.fade.start("menu")

        # The high-scores and controls screens are reached via Options, so
        # ESC (like their BACK buttons) returns one level up to Options -
        # consistent with ESC from Options returning to the main menu.
        if key == pygame.K_ESCAPE and self.state == "high_scores":
            self.fade.start("options")
        if key == pygame.K_ESCAPE and self.state == "controls":
            self.fade.start("options")

    # ------------------------------------------------------------------ #
    # "game" state: update
    # ------------------------------------------------------------------ #

    def _update_game(self, keys: pygame.key.ScancodeWrapper, dt: float = 1.0 / settings.FPS) -> None:
        # Once the player is dead, gameplay is fully frozen - no input, no
        # collisions, no bullet/enemy movement - until the state machine has
        # actually transitioned away from "game" (the fade-out to "game_over"
        # is triggered in _draw_game()). The player stays dead throughout; it
        # must never flip back to False and become movable/collidable again.
        if self.player.dead:
            return

        # Clamp defensively (the main loop clamps too): a caller-provided dt
        # larger than MAX_FRAME_DT must not move things further than a capped
        # frame would.
        dt = min(dt, settings.MAX_FRAME_DT)

        self.player.update_invulnerability(dt)
        self.player.update_fire_cooldown(dt)
        self.player.update_powerups(dt)
        self.player.handle_input(keys, dt)
        self.player.clamp_to_screen(settings.WIDTH)

        # Hold-to-fire: while Space is held, fire once per cooldown window.
        # The dead-early-return above freezes all of gameplay, so this can
        # never fire during the death sequence (H1 gating preserved). While
        # RAPID FIRE is active the cooldown is shorter (see
        # Player.fire_cooldown_value) - a refreshed pickup never stacks.
        if keys[pygame.K_SPACE] and self.player.can_fire and not self.player.dead:
            self.bullets.append(self.player.spawn_bullet())
            self.audio.play("shoot")
            self.player.fire_cooldown = self.player.fire_cooldown_value()

        # Difficulty ramp (invisible, smooth): scale enemy speed and the
        # active enemy count off a single blended difficulty value. It runs
        # only while the player is alive - the dead-early-return above keeps
        # it fully frozen during the death sequence (H1 gating preserved).
        # Difficulty clock: real wall time since the run started, minus the
        # time banked outside "game" (see _advance_simulation) - so pausing
        # freezes the elapsed-time half of the difficulty ramp.
        elapsed = (pygame.time.get_ticks() - self.run_start_ticks - self.paused_ms) / 1000.0
        diff = self.difficulty.value(self.score, elapsed)

        enemy_speed = min(
            settings.ENEMY_SPEED_PER_SEC + settings.ENEMY_SPEED_GAIN_PER_SEC * diff,
            settings.ENEMY_MAX_SPEED_PER_SEC,
        )
        for enemy in self.enemies:
            enemy.speed = enemy_speed

        target_count = min(
            settings.INITIAL_ENEMY_COUNT + int(settings.ENEMY_COUNT_GAIN * diff),
            settings.ENEMY_MAX_COUNT,
        )
        while len(self.enemies) < target_count:
            self.enemies.append(Enemy.spawn_initial(settings.WIDTH))

        for bullet in self.bullets[:]:
            bullet.update(dt)
            if bullet.off_screen:
                self.bullets.remove(bullet)

        for enemy in self.enemies:
            enemy.update(dt)

            if enemy.get_rect().colliderect(self.player.get_rect()):
                # take_hit() returns False while the i-frame window is active,
                # so an overlapping enemy neither damages the player nor
                # re-triggers the hit effects during invulnerability.
                if self.player.take_hit():
                    if self.player.dead:
                        self.audio.play("player_death")
                        self.audio.fade_out_music()
                    else:
                        self.audio.play("hit")
                    self.screen_shake.trigger()
                    self.damage_flash.trigger()
                    enemy.respawn(settings.WIDTH)

            if enemy.is_off_screen(settings.HEIGHT):
                enemy.respawn(settings.WIDTH)

        # Power-ups drift down and are auto-collected on contact with the
        # player - no keypress needed, same style as every other collision
        # check. They despawn after their real-time lifetime (or off-screen).
        for powerup in self.powerups[:]:
            powerup.update(dt)
            if powerup.expired(settings.HEIGHT):
                self.powerups.remove(powerup)
            elif powerup.get_rect().colliderect(self.player.get_rect()):
                self.player.apply_powerup(powerup.kind)
                self.audio.play("powerup")
                self.powerups.remove(powerup)

        for bullet in self.bullets[:]:
            for enemy in self.enemies:
                if enemy.get_rect().colliderect(bullet.get_rect()):
                    self.audio.play("explosion")
                    self.explosions.append(
                        Explosion(enemy.x, enemy.y, settings.ENEMY_EXPLOSION_FRAME_DELAY)
                    )
                    if bullet in self.bullets:
                        self.bullets.remove(bullet)
                    # A defeated enemy may drop a power-up at its position
                    # (roll against the configured drop chance). The HEALTH
                    # power-up is a comeback item: while the player is at or
                    # above 80% of their full health bar it is excluded from
                    # the drop pool entirely, so it can never be farmed.
                    if random.random() < settings.POWERUP_DROP_CHANCE:
                        pool = settings.POWERUP_TYPES
                        if self.player.health >= (
                            settings.PLAYER_START_HEALTH * settings.HEALTH_POWERUP_MIN_HEALTH_FRACTION
                        ):
                            pool = tuple(
                                k for k in settings.POWERUP_TYPES
                                if k != settings.POWERUP_KIND_HEALTH
                            )
                        kind = random.choice(pool)
                        self.powerups.append(PowerUp(kind, enemy.x, enemy.y))
                    enemy.respawn(settings.WIDTH)
                    self.score += 1
                    break

        self.shake_offset = self.screen_shake.update()

    # ------------------------------------------------------------------ #
    # "game" state: draw
    # ------------------------------------------------------------------ #

    def _draw_game(self) -> None:
        self.player.draw(self.screen, self.assets.player_img, self.shake_offset)

        for enemy in self.enemies:
            enemy.draw(self.screen, self.assets.enemy_img, self.shake_offset)

        for bullet in self.bullets:
            self.screen.blit(
                self.assets.bullet_img,
                (bullet.x + self.shake_offset[0], bullet.y + self.shake_offset[1]),
            )

        ui.draw_health_bar(self.screen, self.assets.health_images, self.player.health)

        for powerup in self.powerups:
            self.screen.blit(
                self.assets.powerup_images[powerup.kind],
                (powerup.x + self.shake_offset[0], powerup.y + self.shake_offset[1]),
            )

        if self.player.shield_active and not self.player.dead:
            self._draw_shield_aura()

        self._draw_powerup_status()

        self.damage_flash.draw(self.screen)

        for explosion in self.explosions[:]:
            if not explosion.is_finished(len(self.assets.explosion_frames)):
                explosion.draw(self.screen, self.assets.explosion_frames, self.shake_offset)
                explosion.advance()
            else:
                self.explosions.remove(explosion)

        if self.player.dead and self.player.explosion:
            if not self.player.explosion.is_finished(len(self.assets.explosion_frames)):
                # NOTE: drawn without the shake offset, matching the original.
                self.player.explosion.draw(self.screen, self.assets.explosion_frames)
                self.player.explosion.advance()
            elif not self.fade.fading_out:
                # Start the fade to game-over exactly once. The player
                # stays dead (never flips back to False), so gameplay
                # remains frozen until the fade completes and the state
                # switches to "game_over" - no revival, no re-hits during
                # the fade-out (H1).
                self.fade.start("game_over")
                self.player.explosion = None
                # Record the final score on the persistent leaderboard
                # right here, once per run: the score is final (gameplay
                # is frozen) and writing a tiny JSON file is effectively
                # instant and failure-tolerant, so this never delays the
                # fade transition.
                self.last_run_rank = self.high_scores.add(self.score)

        ui.draw_score(self.screen, self.assets.font, self.score)

    def _draw_shield_aura(self) -> None:
        """A translucent cyan bubble around the ship while the shield is up,
        matching the player's position including the screen-shake offset."""
        center = (
            self.player.x + self.player.width // 2 + self.shake_offset[0],
            self.player.y + self.player.height // 2 + self.shake_offset[1],
        )
        radius = max(self.player.width, self.player.height) // 2 + 14
        aura = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(aura, (*settings.SHIELD_AURA_COLOR, 60), (radius, radius), radius)
        pygame.draw.circle(aura, (*settings.SHIELD_AURA_COLOR, 220), (radius, radius), radius, 3)
        self.screen.blit(aura, (center[0] - radius, center[1] - radius))

    def _draw_powerup_status(self) -> None:
        """In-game HUD: timed power-up windows with their remaining time.
        Drawn top-left under the health bar; empty by default so the normal
        HUD is unchanged. (Health restoration needs no indicator - the
        health bar itself shows the change.)"""
        rows = []
        if self.player.shield_active:
            rows.append((f"SHIELD {self.player.shield_timer:.1f}s", settings.SHIELD_AURA_COLOR))
        if self.player.rapid_fire_active:
            rows.append((f"RAPID FIRE {self.player.rapid_fire_timer:.1f}s", settings.RAPID_FIRE_COLOR))
        y = settings.POWERUP_STATUS_Y
        for text, color in rows:
            label = self.assets.font.render(text, True, color)
            self.screen.blit(label, (settings.POWERUP_STATUS_X, y))
            y += settings.POWERUP_STATUS_ROW_GAP
