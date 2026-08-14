"""The Game class: owns all game state and runs the main loop."""

from __future__ import annotations

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
from menus import GameOverMenu, HighScoresMenu, MainMenu, OptionsScreen, PauseMenu
from player import Player


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.font.init()

        self.screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT))
        pygame.display.set_caption(settings.CAPTION)
        self.clock = pygame.time.Clock()

        self.assets = Assets.load()

        self.audio = AudioManager()

        # Persistent top-10 leaderboard (JSON next to the working dir).
        # last_run_rank tracks where the most recent run landed on it (None
        # when it didn't qualify), used to highlight that row on the
        # high-scores screen.
        self.high_scores = HighScoreTable.load()
        self.last_run_rank = None

        self.main_menu = MainMenu(self.assets, settings.WIDTH, audio=self.audio)
        self.pause_menu = PauseMenu(self.assets, settings.WIDTH, audio=self.audio)
        self.game_over_menu = GameOverMenu(self.assets, settings.WIDTH, audio=self.audio)
        self.options_screen = OptionsScreen(self.assets, settings.WIDTH, settings.HEIGHT, audio=self.audio)
        self.high_scores_menu = HighScoresMenu(
            self.assets, settings.WIDTH, settings.HEIGHT, table=self.high_scores, audio=self.audio
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
        self.score = 0
        self.screen_shake.timer = 0
        self.damage_flash.timer = 0
        self.explosions = []
        # Difficulty clock: elapsed survival time is measured from here, so a
        # restart always starts the ramp back at baseline (no carryover).
        self.run_start_ticks = pygame.time.get_ticks()
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
        if new_state == "game":
            self.audio.play_music()
        elif new_state == "pause":
            self.audio.pause_music()
        elif new_state in ("menu", "game_over", "high_scores"):
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
            action = self.options_screen.handle_click(mouse_pos)
            if action:
                self.audio.play("menu_click")
            if action == "high_scores":
                self.fade.start("high_scores")

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

        # The high-scores screen is reached via Options, so ESC (like the
        # BACK button) returns one level up to Options - consistent with ESC
        # from Options returning to the main menu.
        if key == pygame.K_ESCAPE and self.state == "high_scores":
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
        self.player.handle_input(keys, dt)
        self.player.clamp_to_screen(settings.WIDTH)

        # Hold-to-fire: while Space is held, fire once per cooldown window.
        # The dead-early-return above freezes all of gameplay, so this can
        # never fire during the death sequence (H1 gating preserved).
        if keys[pygame.K_SPACE] and self.player.can_fire and not self.player.dead:
            self.bullets.append(self.player.spawn_bullet())
            self.audio.play("shoot")
            self.player.fire_cooldown = settings.PLAYER_FIRE_COOLDOWN_SECONDS

        # Difficulty ramp (invisible, smooth): scale enemy speed and the
        # active enemy count off a single blended difficulty value. It runs
        # only while the player is alive - the dead-early-return above keeps
        # it fully frozen during the death sequence (H1 gating preserved).
        elapsed = (pygame.time.get_ticks() - self.run_start_ticks) / 1000.0
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

        for bullet in self.bullets[:]:
            for enemy in self.enemies:
                if enemy.get_rect().colliderect(bullet.get_rect()):
                    self.audio.play("explosion")
                    self.explosions.append(
                        Explosion(enemy.x, enemy.y, settings.ENEMY_EXPLOSION_FRAME_DELAY)
                    )
                    if bullet in self.bullets:
                        self.bullets.remove(bullet)
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
                # Start the fade to game-over exactly once. The player stays
                # dead (never flips back to False), so gameplay remains frozen
                # until the fade completes and the state switches to
                # "game_over" - no revival, no re-hits during the fade-out.
                self.fade.start("game_over")
                self.player.explosion = None
                # Record the final score on the persistent leaderboard right
                # here, once per run: the score is final (gameplay is frozen)
                # and writing a tiny JSON file is effectively instant and
                # failure-tolerant, so this never delays the fade transition.
                self.last_run_rank = self.high_scores.add(self.score)

        ui.draw_score(self.screen, self.assets.font, self.score)
