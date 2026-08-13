"""The Game class: owns all game state and runs the main loop."""

from __future__ import annotations

import pygame

import settings
import ui
from assets import Assets
from audio import AudioManager
from bullet import Bullet
from enemy import Enemy
from explosion import Explosion
from menus import GameOverMenu, MainMenu, OptionsScreen, PauseMenu
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

        self.main_menu = MainMenu(self.assets, settings.WIDTH, audio=self.audio)
        self.pause_menu = PauseMenu(self.assets, settings.WIDTH, audio=self.audio)
        self.game_over_menu = GameOverMenu(self.assets, settings.WIDTH, audio=self.audio)
        self.options_screen = OptionsScreen(self.assets, settings.WIDTH, settings.HEIGHT)

        self.screen_shake = ui.ScreenShake()
        self.damage_flash = ui.DamageFlash()
        self.fade = ui.FadeTransition((settings.WIDTH, settings.HEIGHT))
        self.shake_offset: tuple[int, int] = (0, 0)

        self.running = True
        self.state = "menu"

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

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        while self.running:
            self.screen.fill(settings.BLACK)
            mouse_pos = pygame.mouse.get_pos()

            self._handle_events(mouse_pos)
            self._update_and_draw(mouse_pos)

            new_state = self.fade.update()
            if new_state is not None:
                self._change_state(new_state)
            self.fade.draw(self.screen)

            pygame.display.update()
            self.clock.tick(settings.FPS)

        pygame.quit()

    def _update_and_draw(self, mouse_pos: tuple[int, int]) -> None:
        if self.state == "menu":
            self.main_menu.draw(self.screen, mouse_pos)

        elif self.state == "game":
            keys = pygame.key.get_pressed()
            self._update_game(keys)
            self._draw_game()

        elif self.state == "options":
            self.options_screen.draw(self.screen)

        elif self.state == "pause":
            self.pause_menu.draw(self.screen, mouse_pos)

        elif self.state == "game_over":
            self.game_over_menu.draw(self.screen, mouse_pos)

        # Global (non-intrusive) indication that all audio is muted.
        if self.audio.muted:
            self._draw_mute_indicator()

    def _change_state(self, new_state: str) -> None:
        """Apply a completed state transition and keep the music in sync."""
        self.state = new_state
        if new_state == "game":
            self.audio.play_music()
        elif new_state == "pause":
            self.audio.pause_music()
        elif new_state in ("menu", "game_over"):
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

    # ------------------------------------------------------------------ #
    # "game" state: update
    # ------------------------------------------------------------------ #

    def _update_game(self, keys: pygame.key.ScancodeWrapper) -> None:
        # Once the player is dead, gameplay is fully frozen - no input, no
        # collisions, no bullet/enemy movement - until the state machine has
        # actually transitioned away from "game" (the fade-out to "game_over"
        # is triggered in _draw_game()). The player stays dead throughout; it
        # must never flip back to False and become movable/collidable again.
        if self.player.dead:
            return

        self.player.update_invulnerability()
        self.player.update_fire_cooldown()
        self.player.handle_input(keys)
        self.player.clamp_to_screen(settings.WIDTH)

        # Hold-to-fire: while Space is held, fire once per cooldown window.
        # The dead-early-return above freezes all of gameplay, so this can
        # never fire during the death sequence (H1 gating preserved).
        if keys[pygame.K_SPACE] and self.player.can_fire and not self.player.dead:
            self.bullets.append(self.player.spawn_bullet())
            self.audio.play("shoot")
            self.player.fire_cooldown = settings.PLAYER_FIRE_COOLDOWN

        for bullet in self.bullets[:]:
            bullet.update()
            if bullet.off_screen:
                self.bullets.remove(bullet)

        for enemy in self.enemies:
            enemy.update()

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

        ui.draw_score(self.screen, self.assets.font, self.score)
