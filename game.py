"""The Game class: owns all game state and runs the main loop."""

from __future__ import annotations

import random

import pygame

import settings
import ui
from assets import Assets
from ui import FadeText
from audio import AudioManager
from boss import Boss
from bullet import Bullet
from difficulty import Difficulty
from enemy import Enemy
from enemy_bullet import EnemyBullet
from explosion import Explosion
from gunner import GunnerEnemy
from highscores import HighScoreTable
from menus import ControlsScreen, GameOverMenu, HighScoresMenu, MainMenu, OptionsScreen, PauseMenu
from player import Player
from powerup import PowerUp
from settings_store import UserSettings
from background import ParallaxBackground, StaticBackground


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
            self.assets, settings.WIDTH, settings.HEIGHT,
            audio=self.audio, store=self.user_settings,
        )

        self.screen_shake = ui.ScreenShake()
        self.damage_flash = ui.DamageFlash()
        # White full-screen flash for the boss's final hit (reuses the same
        # DamageFlash component the red hit-flash uses, just with its own
        # colour/alpha so the two never share a timer).
        self.victory_flash = ui.DamageFlash(
            settings.BOSS_VICTORY_FLASH_COLOR, settings.BOSS_VICTORY_FLASH_ALPHA
        )
        # Cache of pre-tinted boss sprites (hit flash / aim telegraph), keyed
        # by (image, colour, alpha, additive) so a charge doesn't allocate a
        # copy every frame.
        self._tint_cache: dict[tuple[int, tuple[int, int, int], int, bool], pygame.Surface] = {}
        self.fade = ui.FadeTransition((settings.WIDTH, settings.HEIGHT))
        self.fade_text = FadeText("")
        self.shake_offset: tuple[int, int] = (0, 0)
        self.difficulty = Difficulty()

        # Parallax backgrounds: one pair per level, updated during gameplay.
        self.parallax = self.assets.parallax
        # Static UI background: drawn behind all menu/UI screens.
        self.static_bg = self.assets.static_bg

        self.running = True
        self.state = "menu"
        # Fixed-timestep accumulator: banks real elapsed time and drains it in
        # constant FIXED_DT simulation steps (see _advance_simulation).
        self.accumulator = 0.0

        # Level state: current level number (0-indexed), its score target,
        # and the checkpoint level for death/restart (Level 1 death resets
        # to 0, Level 2 death restarts at 1).
        self.current_level: int = 0
        self.checkpoint_level: int = 0
        self.level_score_target: int = settings.LEVEL_SCORE_TARGETS[0]
        # True once every level has been cleared. Distinguishes "reached
        # game_over by winning" from "reached it by dying", which decides
        # whether RESTART resumes at the checkpoint or starts a fresh run.
        self.run_finished: bool = False

        # Run timer: total in-game seconds across all levels. Pauses on
        # non-game states (menu/pause/game_over) using the same paused_ms
        # pattern as the difficulty clock. Continues through level
        # transitions and fade text overlays.
        self.run_timer: float = 0.0
        self.run_timer_paused_ms: float = 0.0

        # Flag set when a level's score target is reached; freezes gameplay
        # while the "Level Finished" fade text plays. Cleared when the
        # transition completes.
        self._level_transition_pending: bool = False

        # Flag set during the ship-exit animation (Phase 1 of level
        # completion). While True the ship flies upward off-screen,
        # enemy replenishment is stopped, and player input is blocked.
        self._ship_exit_active: bool = False

        # Flag set at the start of a level to show "Phase N" intro text.
        # Cleared when the text finishes.
        self._level_intro_pending: bool = False

        # --- Level 3 boss state --- #
        # The boss object exists only once the score gate is reached; it is
        # None during every other level and during Level 3's opening wave.
        self.boss: Boss | None = None
        # True from the moment the score gate is reached: normal enemy
        # replenishment stops for the rest of the level.
        self.boss_phase_active: bool = False
        # True while the staggered death-explosion chain is playing.
        self.boss_dying: bool = False
        self.boss_death_timer: float = 0.0
        self.boss_death_chain: list[tuple[float, float, float, float]] = []
        self.boss_death_duration: float = 0.0
        # Flag set so the victory fade text's completion hands off to the
        # end-of-run (game_over) state instead of a level transition.
        self._victory_pending: bool = False

        # player, bullets, enemies, explosions, and score are all
        # initialized by reset_game() below.
        self.reset_game()

    # ------------------------------------------------------------------ #
    # State setup
    # ------------------------------------------------------------------ #

    def reset_game(self, from_checkpoint: bool = False) -> None:
        """Start a fresh run or resume from a checkpoint.

        from_checkpoint=False (default): full reset — new player, new enemy
        wave, score/health reset, difficulty clock reset, run timer reset,
        back to Level 1.

        from_checkpoint=True: restart at the checkpoint level (Level 2 on
        death in Level 2). Score resets and the run timer keeps its
        accumulated value. NOTE: the difficulty clock is derived from the
        preserved run timer, so a checkpoint restart resumes at the
        difficulty the run had already reached rather than at baseline.
        The "Phase N" intro text plays for the checkpoint level.
        """
        self.player = Player(
            settings.WIDTH // 2,
            settings.HEIGHT - 80,
            bindings=self.user_settings.key_bindings,
        )
        self.bullets = []
        self.enemy_bullets = []
        # Level 1: falling enemies.  Level 2: gunner enemies (set after
        # level state is initialized below).
        self.enemies = []
        self.gunners = []
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
        # Any previous run's "cleared everything" flag must not leak into
        # this one, or RESTART would keep refusing to use the checkpoint.
        self.run_finished = False

        # Boss state: a restart (full or checkpoint) always rebuilds the
        # boss level from its opening wave - the boss is never inherited
        # mid-fight, and no death sequence carries over.
        self.boss = None
        self.boss_phase_active = False
        self.boss_dying = False
        self.boss_death_timer = 0.0
        self.boss_death_chain = []
        self.boss_death_duration = 0.0
        self._victory_pending = False
        self.victory_flash.timer = 0

        # Level state: full reset goes to Level 0; checkpoint preserves
        # the level that was active when the player died.
        if from_checkpoint:
            self.current_level = self.checkpoint_level
            # Preserve the run timer: shift run_start_ticks backward by
            # the accumulated seconds so the formula
            #   (get_ticks() - run_start_ticks - run_timer_paused_ms) / 1000
            # produces the correct total once paused_ms and
            # run_timer_paused_ms are reset to 0.
            saved_timer = self.run_timer
            self.paused_ms = 0.0
            self.run_timer_paused_ms = 0.0
            self.run_start_ticks = pygame.time.get_ticks() - int(saved_timer * 1000)
            self.run_timer = saved_timer
        else:
            self.current_level = 0
            self.checkpoint_level = 0
            self.run_timer = 0.0
            self.run_timer_paused_ms = 0.0
        self.level_score_target = settings.LEVEL_SCORE_TARGETS[self.current_level]

        # Spawn the initial enemy wave for the current level.
        self._spawn_level_wave()

        # Freeze gameplay during the intro fade text. The state will
        # transition to "level_intro" via fade.start() in the caller
        # (menu click or restart handler), keeping the smooth fade from
        # the previous screen.
        self._level_transition_pending = False
        self._level_intro_pending = True
        self._ship_exit_active = False
        phase_num = self.current_level + 1
        self.fade_text.reset(f"Phase {phase_num}")

        # Load the correct parallax background pair for this level.
        self.parallax.set_level(self.current_level)
        self.parallax.reset()

    def _spawn_level_wave(self) -> None:
        """Populate the opening enemy wave for `current_level`.

        Level 1 (index 0): falling enemies only.
        Level 2 (index 1): gunner enemies only.
        Level 3 (index 2, the boss level): a MIXED wave - everything the
        player has faced so far - before the boss gate is reached. Once the
        gate is hit the boss replaces all of it (see _start_boss_phase).
        """
        if self.current_level == 0:
            self.enemies = [
                Enemy.spawn_initial(settings.WIDTH) for _ in range(settings.INITIAL_ENEMY_COUNT)
            ]
            self.gunners = []
        elif self.current_level == 1:
            self.enemies = []
            self.gunners = [
                GunnerEnemy.spawn_initial(settings.WIDTH)
                for _ in range(settings.INITIAL_ENEMY_COUNT)
            ]
        else:
            # Boss level opening wave: both types, each at its own level's
            # baseline count/scaling (see _replenish_enemies).
            self.enemies = [
                Enemy.spawn_initial(settings.WIDTH) for _ in range(settings.INITIAL_ENEMY_COUNT)
            ]
            self.gunners = [
                GunnerEnemy.spawn_initial(settings.WIDTH)
                for _ in range(settings.INITIAL_ENEMY_COUNT)
            ]

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

            self._advance_transitions()
            self.fade.draw(self.screen)
            if self._fade_text_owns_screen():
                # The victory screen uses its own gold styling so it reads as
                # a distinctly bigger moment than a normal "Level Finished".
                color = (
                    settings.BOSS_VICTORY_COLOR
                    if self.state == "victory"
                    else None
                )
                self.fade_text.draw(self.screen, self.assets.big_font, color)

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

        The run timer mirrors the difficulty clock: it only measures time
        spent in the "game" state, pausing during menu/pause/game_over.
        Unlike the difficulty clock, it continues through level transitions
        (fade text overlays) since those happen while state == "game".
        """
        if self.state not in ("game", "level_finished"):
            self.accumulator = 0.0
            # Bank non-game time for both the difficulty clock and the run
            # timer so both freeze during menu/pause/game_over.
            self.paused_ms += raw_dt * 1000.0
            self.run_timer_paused_ms += raw_dt * 1000.0
            return 0

        # level_finished: same as level_intro — simulation frozen, but
        # the run timer keeps counting (level transitions happen while
        # state is "game" or "level_finished").
        if self.state == "level_finished" and self.fade_text.active:
            self.paused_ms += raw_dt * 1000.0
            self.accumulator = 0.0
            self.run_timer = (
                (pygame.time.get_ticks() - self.run_start_ticks - self.run_timer_paused_ms)
                / 1000.0
            )
            return 0

        # While the fade text is active (level intro or level finished),
        # freeze the simulation but keep the run timer counting (level
        # transitions happen within the "game" state).
        if self.fade_text.active:
            self.paused_ms += raw_dt * 1000.0
            self.accumulator = 0.0
            # Update the run timer here since _update_game won't run.
            self.run_timer = (
                (pygame.time.get_ticks() - self.run_start_ticks - self.run_timer_paused_ms)
                / 1000.0
            )
            return 0

        # Update parallax scrolling while gameplay is active.
        # This runs before the accumulator so the background moves
        # smoothly even when the sim steps are behind.
        if self.state == "game":
            self.parallax.update(min(raw_dt, settings.MAX_FRAME_DT))

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
            self.static_bg.draw(self.screen)
            self.main_menu.draw(self.screen, mouse_pos)

        elif self.state == "game":
            self._draw_game()

        elif self.state in ("level_intro", "level_finished", "victory"):
            # Black screen with only the fade text — no gameplay HUD,
            # entities, or background. The text itself is drawn later in
            # run() (after the fade transition), same as for other states.
            pass

        elif self.state == "options":
            self.static_bg.draw(self.screen)
            self.options_screen.draw(self.screen, mouse_pos)

        elif self.state == "pause":
            self.static_bg.draw(self.screen)
            self.pause_menu.draw(self.screen, mouse_pos)

        elif self.state == "game_over":
            self.static_bg.draw(self.screen)
            # A run that beat the final boss gets VICTORY rather than
            # GAME OVER - same screen, same buttons, different framing.
            title, color = (
                ("VICTORY", settings.BOSS_VICTORY_COLOR)
                if self.run_finished
                else ("GAME OVER", settings.GAME_OVER_COLOR)
            )
            self.game_over_menu.draw(self.screen, mouse_pos, title=title, color=color)

        elif self.state == "high_scores":
            self.static_bg.draw(self.screen)
            self.high_scores_menu.draw(self.screen, mouse_pos, self.last_run_rank)

        elif self.state == "controls":
            self.static_bg.draw(self.screen)
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

    def _fade_text_owns_screen(self) -> bool:
        """True while the fade text overlay may advance and be drawn.

        The text only runs when the run genuinely owns the screen AND no state
        change is already in flight. Both guards matter, because finishing the
        text calls fade.start() itself (see _on_fade_text_done): letting it
        complete while the player is pausing or quitting to the menu would
        override wherever they asked to go. Freezing it mid-animation is
        harmless - it resumes on unpause, and reset_game() clears it for a
        new run.
        """
        return (
            self.fade_text.active
            and self.state in ("game", "level_intro", "level_finished", "victory")
            and not self.fade.fading_out
        )

    def _advance_transitions(self) -> None:
        """One frame of state-machine progress: the fade transition, then the
        fade text overlay.

        Split out of run() so the test suite can drive exactly this logic
        without the render loop - the pause/quit-during-level-transition
        regressions are only reproducible through the real guards.
        """
        new_state = self.fade.update()
        if new_state is not None:
            self._change_state(new_state)

        if self._fade_text_owns_screen():
            self.fade_text.update()
            if not self.fade_text.active:
                self._on_fade_text_done()

    def _change_state(self, new_state: str) -> None:
        """Apply a completed state transition and keep the music in sync."""
        self.state = new_state
        # A slider drag must never survive a state change (e.g. ESC mid-drag).
        self.options_screen._dragging = None
        if new_state == "game":
            self.audio.play_music()
        elif new_state == "pause":
            self.audio.pause_music()
        elif new_state in (
            "menu",
            "game_over",
            "high_scores",
            "controls",
            "level_intro",
            "level_finished",
            "victory",
        ):
            self.audio.stop_music()

    def _on_fade_text_done(self) -> None:
        """Called when a fade text overlay finishes. Handles level intro
        completion (resume gameplay), the boss victory screen (end the run),
        and the level finished transition (advance to next level or end run).
        """
        if self._level_intro_pending:
            # Intro text finished — transition from level_intro to gameplay.
            self._level_intro_pending = False
            self.fade.start("game")
        elif self._victory_pending:
            # Boss victory screen finished — the run is over and COMPLETE.
            # Same end-state as a fully-cleared run (game_over, framed as
            # VICTORY by the run_finished flag) so RESTART/QUIT work exactly
            # as they already do after the last level.
            self._victory_pending = False
            self.fade.start("game_over")
            self.last_run_rank = self.high_scores.add(
                self.run_timer, result="Finished"
            )
        elif self._level_transition_pending:
            # Level finished text finished — advance to next level.
            self._level_transition_pending = False
            self.current_level += 1
            if self.current_level >= settings.LEVEL_COUNT:
                # No more levels — end the run as Finished. current_level now
                # sits PAST the last level, so checkpoint_level is deliberately
                # left on the level just cleared: reset_game() indexes
                # LEVEL_SCORE_TARGETS[current_level], and advancing the
                # checkpoint here used to make RESTART raise IndexError.
                self.run_finished = True
                self.fade.start("game_over")
                self.last_run_rank = self.high_scores.add(
                    self.run_timer, result="Finished"
                )
            else:
                # Advance the checkpoint so death in the new level restarts
                # here instead of at the beginning of the run.
                self.checkpoint_level = self.current_level
                # Start the next level: reset score, set new target,
                # spawn the appropriate enemy type, show "Phase N" intro.
                self.score = 0
                self.level_score_target = settings.LEVEL_SCORE_TARGETS[self.current_level]

                # Fresh wave for the new level (Level 3 opens with a mixed
                # wave and its boss gate, not the ship-exit path).
                self._spawn_level_wave()
                self.enemy_bullets = []
                self.powerups = []
                # No boss is inherited between levels: Level 3 always starts
                # from its opening wave with the boss gated behind score.
                self.boss = None
                self.boss_phase_active = False
                self.boss_dying = False
                self.boss_death_chain = []

                # Reposition the player to the default starting position.
                # After ship exit, player.y is off-screen (< -80). Without
                # this reset the player stays invisible for the entire next
                # level.
                self.player.x = settings.WIDTH // 2 - self.player.width // 2
                self.player.y = settings.HEIGHT - 80

                self._level_intro_pending = True
                phase_num = self.current_level + 1
                self.fade_text.reset(f"Phase {phase_num}")
                # Load the next level's parallax background pair.
                self.parallax.set_level(self.current_level)
                # Leave gameplay for the dedicated black intro screen. Without
                # this the state stays "game", so _draw_frame keeps rendering
                # the ship, enemies, health bar and score behind the
                # "Phase N" text - the exact thing level_intro exists to stop.
                self.fade.start("level_intro")

    def _check_level_completion(self) -> None:
        """Check if the current level's score target has been reached.

        Normal levels: start the ship-exit animation (Phase 1) - enemy
        replenishment stops, player input is blocked, and the ship flies
        upward off-screen.

        The boss level: the same score target is the BOSS GATE. Reaching it
        stops normal spawning and flies the boss in instead; there is no
        ship exit and no "Level Finished" screen (the boss's own victory
        sequence ends the run).
        """
        if self._level_transition_pending or self._level_intro_pending or self._ship_exit_active:
            return
        if self.player.dead:
            # A dying player's final bullet can still reach the target in the
            # same simulation step that killed them. The death sequence owns
            # the run from here, so don't queue a level transition behind it.
            return
        if self.boss_phase_active or self.boss is not None or self.boss_dying:
            # The boss gate is one-shot: once the fight is under way, score
            # changes (there are none for boss hits) must not re-trigger it.
            return
        if self.score >= self.level_score_target:
            if self.current_level == settings.BOSS_LEVEL_INDEX:
                self._start_boss_phase()
                return
            self._ship_exit_active = True
            # Clear the field: no more enemies, bullets, or power-ups while
            # the ship exits. The player is invulnerable during this phase.
            self.enemies.clear()
            self.gunners.clear()
            self.enemy_bullets.clear()
            self.bullets.clear()
            self.powerups.clear()
            # Clear the i-frame timer so the player is always visible during
            # the exit animation. Without this, a frozen invulnerable_timer
            # could lock _blink_visible() into an invisible phase for the
            # entire exit, making the ship disappear instantly.
            self.player.invulnerable_timer = 0.0

    # ------------------------------------------------------------------ #
    # Level 3: boss
    # ------------------------------------------------------------------ #

    def _start_boss_phase(self) -> None:
        """Score gate reached on the boss level.

        Normal spawning stops for the rest of the level. Falling enemies
        have a natural exit (they scroll off the bottom), so they are left to
        finish their descent; gunners stop mid-screen and would otherwise
        fire forever, so they are cleared outright, along with the shots they
        already fired. The boss then flies in.
        """
        self.boss_phase_active = True
        self.gunners.clear()
        self.enemy_bullets.clear()
        self.boss = Boss(settings.WIDTH, settings.HEIGHT)
        self.audio.play("explosion")

    def _begin_boss_death(self) -> None:
        """Boss HP hit 0: flash, then a staggered explosion chain.

        The chain is scheduled up-front as (time, x, y, scale) entries so it
        is driven purely by accumulated dt in the fixed-step simulation - no
        frame counting, and reproducible in a test.
        """
        self.boss_dying = True
        self.boss_death_timer = 0.0
        # The run is WON the instant the boss hits 0 HP - not when the victory
        # screen finishes. Setting it here means a player killed in the same
        # step (or during the chain) can't turn a win into a death: the
        # dead-player path below is gated on this flag, and RESTART already
        # treats a finished run as "start fresh from Level 1".
        self.run_finished = True
        self.victory_flash.trigger()
        self.enemy_bullets.clear()

        interval = settings.BOSS_DEATH_EXPLOSION_INTERVAL_SECONDS
        frame_w, frame_h = settings.EXPLOSION_IMG_SIZE
        chain: list[tuple[float, float, float, float]] = []
        if self.boss is not None:
            for i in range(settings.BOSS_DEATH_EXPLOSION_COUNT):
                # Scatter blasts across the sprite's footprint.
                x = self.boss.x + random.uniform(0, self.boss.width) - frame_w / 2
                y = self.boss.y + random.uniform(0, self.boss.height) - frame_h / 2
                chain.append((i * interval, x, y, 1.0))
            # Final, bigger blast centered on the sprite, after the chain.
            scale = settings.BOSS_DEATH_FINAL_EXPLOSION_SCALE
            chain.append(
                (
                    settings.BOSS_DEATH_EXPLOSION_COUNT * interval,
                    self.boss.x + self.boss.width / 2 - frame_w * scale / 2,
                    self.boss.y + self.boss.height / 2 - frame_h * scale / 2,
                    scale,
                )
            )
        chain.sort(key=lambda entry: entry[0])
        self.boss_death_chain = chain
        last_time = chain[-1][0] if chain else 0.0
        self.boss_death_duration = last_time + settings.BOSS_DEATH_HOLD_SECONDS

    def _update_boss_death(self, dt: float) -> None:
        """Tick the death chain; hand off to the victory screen when done."""
        self.boss_death_timer += dt
        while self.boss_death_chain and self.boss_death_chain[0][0] <= self.boss_death_timer:
            _t, x, y, scale = self.boss_death_chain.pop(0)
            self.explosions.append(
                Explosion(x, y, settings.ENEMY_EXPLOSION_FRAME_DELAY, scale=scale)
            )
            self.audio.play("explosion")

        if self.boss_death_chain or self.boss_death_timer < self.boss_death_duration:
            return

        # Chain finished: the boss is gone and the run is complete. The
        # victory text is a dedicated screen (state "victory"), then the
        # normal end-of-run game_over state takes over.
        self.boss_dying = False
        self.boss = None
        # run_finished was already set when the boss hit 0 HP - the run is won
        # from that instant, not from the end of the animation.
        self._victory_pending = True
        self.fade_text.reset(settings.BOSS_VICTORY_TEXT)
        self.fade.start("victory")

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
                self.fade.start("level_intro")
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
                self.fade.start(getattr(self, "_state_before_pause", "game"))
            elif action == "quit_to_menu":
                self.fade.start("menu")

        elif self.state == "game_over":
            action = self.game_over_menu.handle_click(mouse_pos)
            if action:
                self.audio.play("menu_click")
            if action == "restart":
                # Resume at the checkpoint only when the run ended in death
                # partway through. A COMPLETED run starts fresh from Level 1:
                # its current_level sits past the last level, and its
                # checkpoint points at a level the player already cleared.
                self.reset_game(
                    from_checkpoint=self.checkpoint_level > 0 and not self.run_finished
                )
                self.fade.start("level_intro")
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
        # Controls screen in edit mode owns the keyboard: a row awaiting
        # input captures the next keypress (ESC cancels); ESC otherwise
        # exits edit mode back to the normal controls screen. Nothing else
        # (mute toggle, pause, navigation) runs while editing.
        if self.state == "controls" and self.controls_screen.in_edit_mode():
            self.controls_screen.handle_keydown(key)
            return

        bindings = self.user_settings.key_bindings

        # Global mute toggle, available in every state.
        if key == bindings["mute"]:
            self.audio.toggle_mute()

        # While the player is dead, gameplay is frozen: ESC cannot pause and
        # the fire key cannot fire until the game-over transition completes.
        if key == bindings["pause"] and self.state in ("game", "level_finished") and not self.player.dead:
            self._state_before_pause = self.state
            self.fade.start("pause")
        elif key == bindings["pause"] and self.state == "pause":
            self.fade.start(getattr(self, "_state_before_pause", "game"))

        if key == bindings["back"] and self.state == "options":
            self.fade.start("menu")

        # The high-scores and controls screens are reached via Options, so
        # their back key (like their BACK buttons) returns one level up to
        # Options - consistent with back from Options returning to the menu.
        if key == bindings["back"] and self.state == "high_scores":
            self.fade.start("options")
        if key == bindings["back"] and self.state == "controls":
            self.fade.start("options")

    # ------------------------------------------------------------------ #
    # "game" state: update
    # ------------------------------------------------------------------ #

    def _update_game(self, keys: pygame.key.ScancodeWrapper, dt: float = 1.0 / settings.FPS) -> None:
        # The boss's death sequence owns the run from the moment the boss hits
        # 0 HP: it has to finish, because the run is already WON and run_finished
        # is set. Handled before the dead-player freeze so a player killed in
        # the same step can never strand the victory half-played.
        if self.boss_dying:
            self._update_boss_death(dt)
            return

        # Once the player is dead, gameplay is fully frozen - no input, no
        # collisions, no bullet/enemy movement - until the state machine has
        # actually transitioned away from "game" (the fade-out to "game_over"
        # is triggered in _draw_game()). The player stays dead throughout; it
        # must never flip back to False and become movable/collidable again.
        if self.player.dead:
            return

        # Ship exit animation (Phase 1 of level completion): the ship flies
        # upward off the top of the screen. Player input is blocked,
        # enemies are cleared, and the player is invulnerable. When the
        # ship reaches the top, transition to the "level_finished" state.
        if self._ship_exit_active:
            self.player.y -= settings.SHIP_EXIT_SPEED_PER_SEC * dt
            # Run timer keeps counting during ship exit.
            self.run_timer = (
                (pygame.time.get_ticks() - self.run_start_ticks - self.run_timer_paused_ms)
                / 1000.0
            )
            if self.player.y + self.player.height < 0:
                self._ship_exit_active = False
                self._level_transition_pending = True
                self.fade.start("level_finished")
                self.fade_text.reset("Level Finished")
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
        if keys[self.user_settings.key_bindings["fire"]] and self.player.can_fire and not self.player.dead:
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

        # Run timer: total in-game seconds across all levels. Uses the same
        # get_ticks pattern but subtracts run_timer_paused_ms (time outside
        # "game" state) rather than paused_ms (which also freezes during
        # fade text overlays, where the run timer keeps counting).
        self.run_timer = (pygame.time.get_ticks() - self.run_start_ticks - self.run_timer_paused_ms) / 1000.0

        # --- Enemy wave: difficulty scaling + replenishment ---
        # Skipped entirely once the boss gate is hit: that is what stops new
        # falling/gunner enemies from spawning for the rest of the level.
        if not self.boss_phase_active:
            self._scale_and_replenish_wave(diff)

        # --- Player bullets ---
        for bullet in self.bullets[:]:
            bullet.update(dt)
            if bullet.off_screen:
                self.bullets.remove(bullet)

        # --- Falling enemies: movement + collision ---
        # Iterating a copy so the boss-phase "remove instead of respawn" path
        # below cannot skip the next enemy in the list.
        for enemy in self.enemies[:]:
            enemy.update(dt)

            if enemy.get_rect().colliderect(self.player.get_rect()):
                if self.player.take_hit():
                    if self.player.dead:
                        self.audio.play("player_death")
                        self.audio.fade_out_music()
                    else:
                        self.audio.play("hit")
                    self.screen_shake.trigger()
                    self.damage_flash.trigger()
                    if self.boss_phase_active:
                        self.enemies.remove(enemy)
                    else:
                        enemy.respawn(settings.WIDTH)

            if enemy.is_off_screen(settings.HEIGHT):
                # During the boss fight the field empties out instead of
                # recycling: leftover enemies finish their descent and are
                # simply gone (no new spawns once the gate is hit).
                if self.boss_phase_active:
                    self.enemies.remove(enemy)
                else:
                    enemy.respawn(settings.WIDTH)

        # --- Gunner enemies (Level 2): movement + firing ---
        for gunner in self.gunners:
            gunner.update(dt)

            if gunner.can_fire():
                # Fire from the center of the gunner.
                bx = gunner.x + gunner.width // 2 - settings.ENEMY_BULLET_IMG_SIZE[0] // 2
                by = gunner.y + gunner.height
                self.enemy_bullets.append(EnemyBullet(bx, by))
                gunner.reset_fire_cooldown()

            # Gunner-player collision (same as falling enemy).
            if gunner.get_rect().colliderect(self.player.get_rect()):
                if self.player.take_hit():
                    if self.player.dead:
                        self.audio.play("player_death")
                        self.audio.fade_out_music()
                    else:
                        self.audio.play("hit")
                    self.screen_shake.trigger()
                    self.damage_flash.trigger()
                    gunner.respawn(settings.WIDTH)

        # --- Enemy bullets: movement + cleanup + player collision ---
        for ebullet in self.enemy_bullets[:]:
            ebullet.update(dt)
            if ebullet.off_screen:
                self.enemy_bullets.remove(ebullet)
                continue
            if ebullet.get_rect().colliderect(self.player.get_rect()):
                self.enemy_bullets.remove(ebullet)
                if self.player.shield_active:
                    # Shield absorbs the bullet — no damage, no SFX.
                    pass
                elif self.player.take_hit():
                    if self.player.dead:
                        self.audio.play("player_death")
                        self.audio.fade_out_music()
                    else:
                        self.audio.play("hit")
                    self.screen_shake.trigger()
                    self.damage_flash.trigger()

        # --- Boss (Level 3) ---
        # Updated after the enemy-bullet pass so the bullets it fires this
        # step are moved (and can hit the player) starting next step, not
        # twice in one step.
        if self.boss is not None:
            if self.boss_dying:
                self._update_boss_death(dt)
            else:
                boss_bullets, minion_count = self.boss.update(
                    dt,
                    self._player_center_x(),
                    settings.WIDTH,
                    self._player_center_y(),
                )
                self.enemy_bullets.extend(boss_bullets)
                for _ in range(minion_count):
                    # Phase-3 minions are gunners that descend from the boss
                    # itself and then behave exactly like normal gunners.
                    mx, my = self.boss.minion_spawn_pos()
                    self.gunners.append(GunnerEnemy(mx, my, settings.WIDTH))

        # --- Power-ups ---
        for powerup in self.powerups[:]:
            powerup.update(dt)
            if powerup.expired(settings.HEIGHT):
                self.powerups.remove(powerup)
            elif powerup.get_rect().colliderect(self.player.get_rect()):
                self.player.apply_powerup(powerup.kind)
                self.audio.play("powerup")
                self.powerups.remove(powerup)

        # --- Player bullets vs falling enemies ---
        for bullet in self.bullets[:]:
            for enemy in self.enemies[:]:
                if enemy.get_rect().colliderect(bullet.get_rect()):
                    self.audio.play("explosion")
                    self.explosions.append(
                        Explosion(enemy.x, enemy.y, settings.ENEMY_EXPLOSION_FRAME_DELAY)
                    )
                    if bullet in self.bullets:
                        self.bullets.remove(bullet)
                    self._maybe_drop_powerup(enemy.x, enemy.y)
                    if self.boss_phase_active:
                        # No recycling during the boss fight: the kill clears
                        # the field rather than putting a new enemy back in.
                        self.enemies.remove(enemy)
                    else:
                        enemy.respawn(settings.WIDTH)
                    self.score += 1
                    self._check_level_completion()
                    break

        # --- Player bullets vs gunners ---
        for bullet in self.bullets[:]:
            for gunner in self.gunners[:]:
                if gunner.get_rect().colliderect(bullet.get_rect()):
                    self.audio.play("explosion")
                    self.explosions.append(
                        Explosion(gunner.x, gunner.y, settings.ENEMY_EXPLOSION_FRAME_DELAY)
                    )
                    if bullet in self.bullets:
                        self.bullets.remove(bullet)
                    self._maybe_drop_powerup(gunner.x, gunner.y)
                    if self.boss_phase_active:
                        self.gunners.remove(gunner)
                    else:
                        gunner.respawn(settings.WIDTH)
                    self.score += 1
                    self._check_level_completion()
                    break

        # --- Player bullets vs the boss ---
        # Full-sprite rect, no weak points, and no invulnerability window: a
        # connecting bullet ALWAYS deals one damage (the fight is a pure
        # damage race). Boss hits award no score, so they can never feed
        # _check_level_completion and re-trigger the level gate.
        if self.boss is not None and not self.boss_dying and not self.boss.entering:
            for bullet in self.bullets[:]:
                if self.boss.get_rect().colliderect(bullet.get_rect()):
                    if bullet in self.bullets:
                        self.bullets.remove(bullet)
                    self.audio.play("explosion")
                    self.explosions.append(
                        Explosion(
                            bullet.x - settings.EXPLOSION_IMG_SIZE[0] // 2,
                            bullet.y - settings.EXPLOSION_IMG_SIZE[1] // 2,
                            settings.ENEMY_EXPLOSION_FRAME_DELAY,
                        )
                    )
                    self.boss.take_damage(1)
                    if self.boss.hp <= 0:
                        self._begin_boss_death()
                        break

        self.shake_offset = self.screen_shake.update()

    def _player_center_x(self) -> float:
        """The player's horizontal center, used by the boss's aimed burst."""
        return self.player.x + self.player.width / 2.0

    def _player_center_y(self) -> float:
        """The player's vertical center: the row the boss's aimed burst
        converges on, so the volley is fired at the ship rather than at a
        fixed screen row."""
        return self.player.y + self.player.height / 2.0

    def _scale_and_replenish_wave(self, diff: float) -> None:
        """Difficulty-scaled speeds + top-up for the current level's wave.

        Level 1 uses falling enemies, Level 2 uses gunners, and the boss
        level's opening wave mixes both (each type scaled at the rate its
        own level established). Never called once the boss gate is hit -
        that is exactly what stops replenishment for the rest of the level.
        """
        use_falling = self.current_level in (0, settings.BOSS_LEVEL_INDEX)
        use_gunners = self.current_level in (1, settings.BOSS_LEVEL_INDEX)

        if use_falling:
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

        if use_gunners:
            gunner_speed = min(
                settings.GUNNER_DESCEND_SPEED_PER_SEC + int(settings.ENEMY_SPEED_GAIN_PER_SEC * diff * 0.5),
                settings.ENEMY_MAX_SPEED_PER_SEC,
            )
            gunner_drift = min(
                settings.GUNNER_DRIFT_SPEED_PER_SEC + int(settings.ENEMY_SPEED_GAIN_PER_SEC * diff * 0.3),
                300,
            )
            for gunner in self.gunners:
                gunner.descend_speed = gunner_speed
                gunner.drift_speed = gunner_drift

            target_gunner_count = min(
                settings.INITIAL_ENEMY_COUNT + int(settings.ENEMY_COUNT_GAIN * diff * 0.5),
                settings.ENEMY_MAX_COUNT,
            )
            while len(self.gunners) < target_gunner_count:
                self.gunners.append(GunnerEnemy.spawn_initial(settings.WIDTH))

    def _maybe_drop_powerup(self, x: float, y: float) -> None:
        """Roll for a power-up drop at the given position (shared by both
        falling-enemy and gunner kill paths).

        The HEALTH kind is filtered out of the pool unless the player is
        missing at least HEALTH_POWERUP_MIN_MISSING_SEGMENTS bar segments, so
        hearts appear the moment the bar drops to 4/5 and stop as soon as it
        is back to full. Integer segments, not a fraction of max health: the
        bar is discrete, and the old fractional threshold silently landed a
        segment lower than it read.
        """
        if random.random() < settings.POWERUP_DROP_CHANCE:
            pool = settings.POWERUP_TYPES
            missing = settings.PLAYER_START_HEALTH - self.player.health
            if missing < settings.HEALTH_POWERUP_MIN_MISSING_SEGMENTS:
                pool = tuple(
                    k for k in settings.POWERUP_TYPES
                    if k != settings.POWERUP_KIND_HEALTH
                )
            kind = random.choice(pool)
            self.powerups.append(PowerUp(kind, x, y))

    # ------------------------------------------------------------------ #
    # "game" state: draw
    # ------------------------------------------------------------------ #

    def _draw_game(self) -> None:
        # Parallax background layers (far first, near on top).
        # Ensure the correct level's layers are loaded (handles edge
        # cases where draw runs before reset_game on a new level).
        if self.parallax.current_level != self.current_level:
            self.parallax.set_level(self.current_level)
        self.parallax.draw(self.screen, self.shake_offset)

        self.player.draw(self.screen, self.assets.player_img, self.shake_offset)

        for enemy in self.enemies:
            enemy.draw(self.screen, self.assets.enemy_img, self.shake_offset)

        for gunner in self.gunners:
            gunner.draw(self.screen, self.assets.gunner_img, self.shake_offset)

        if self.boss is not None:
            self._draw_boss()

        # Enemy bullets (red, below player bullets in draw order).
        for ebullet in self.enemy_bullets:
            self.screen.blit(
                self.assets.enemy_bullet_img,
                (ebullet.x + self.shake_offset[0], ebullet.y + self.shake_offset[1]),
            )

        for bullet in self.bullets:
            self.screen.blit(
                self.assets.bullet_img,
                (bullet.x + self.shake_offset[0], bullet.y + self.shake_offset[1]),
            )

        ui.draw_health_bar(
            self.screen,
            self.assets.health_images,
            self.player.health,
            settings.PLAYER_HEALTH_POS,
        )

        for powerup in self.powerups:
            self.screen.blit(
                self.assets.powerup_images[powerup.kind],
                (powerup.x + self.shake_offset[0], powerup.y + self.shake_offset[1]),
            )

        if self.player.shield_active and not self.player.dead:
            self._draw_shield_aura()

        self._draw_powerup_status()

        # Boss health bar: appears only once the boss is actually active in
        # its fight position (not while it is still flying in, and not once
        # the death chain has begun).
        if self._boss_bar_visible():
            self._draw_boss_health_bar()

        self.damage_flash.draw(self.screen)
        self.victory_flash.draw(self.screen)

        for explosion in self.explosions[:]:
            if not explosion.is_finished(len(self.assets.explosion_frames)):
                explosion.draw(self.screen, self.assets.explosion_frames, self.shake_offset)
                explosion.advance()
            else:
                self.explosions.remove(explosion)

        # A player explosion only owns the screen on a run that hasn't already
        # been won: after the boss dies, run_finished is set and the victory
        # sequence must not be hijacked by the death fade.
        if self.player.dead and self.player.explosion and not self.run_finished:
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
                # Record the run on the persistent leaderboard: the run is
                # final (gameplay is frozen) and writing a tiny JSON file is
                # effectively instant and failure-tolerant.
                self.last_run_rank = self.high_scores.add(
                    self.run_timer, result="Dead"
                )


    def _draw_boss(self) -> None:
        """Draw the boss sprite, tinted for its current telegraph state."""
        img = self.assets.boss_img
        pos = (
            int(self.boss.x + self.shake_offset[0]),
            int(self.boss.y + self.shake_offset[1]),
        )
        self.screen.blit(img, pos)
        if self.boss.hit_flash > 0:
            # Just took a hit: quick white pop (additive - brightens).
            self._blit_tint(
                img, pos, (255, 255, 255), settings.BOSS_HIT_FLASH_ALPHA, additive=True
            )
        elif self.boss.aim_target_visible():
            # Charging the aimed burst: the boss turns red (multiplicative -
            # colour-shifts). Distinguishable from the hit flash at a glance.
            self._blit_tint(
                img, pos, settings.BOSS_AIM_TINT_COLOR, 255, additive=False
            )

    def _blit_tint(
        self,
        image: pygame.Surface,
        pos: tuple[int, int],
        color: tuple[int, int, int],
        alpha: int,
        additive: bool = True,
    ) -> None:
        """Blit a translucent colour wash that respects the sprite's shape.

        additive=True adds the colour (brightens - the hit pop).
        additive=False multiplies it in (colour-shifts - the red telegraph),
        which keeps the sprite's own alpha silhouette either way.

        The tint surface is cached: it is rebuilt only when the boss image,
        colour or mode changes, not on every frame of a charge.
        """
        key = (id(image), color, alpha, additive)
        tint = self._tint_cache.get(key)
        if tint is None:
            tint = image.copy()
            if additive:
                tint.fill(color, special_flags=pygame.BLEND_RGB_ADD)
                tint.set_alpha(alpha)
            else:
                wash = pygame.Surface(image.get_size(), pygame.SRCALPHA)
                wash.fill((*color, alpha))
                tint.blit(wash, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            self._tint_cache[key] = tint
        self.screen.blit(tint, pos)

    @staticmethod
    def _boss_bar_fill_width(hp: int, max_hp: int, total_width: int) -> int:
        """Width in px of the boss bar's fill at the current HP.

        0 at 0 HP, the full bar width at max HP, rounded - the same function
        of live HP that the draw call uses, so it can be asserted directly.
        """
        if max_hp <= 0:
            fraction = 0.0
        else:
            fraction = max(0.0, min(1.0, hp / max_hp))
        return int(round(total_width * fraction))

    def _boss_bar_rect(self) -> pygame.Rect:
        """Where the boss bar is drawn: top-right, clear of the player's HUD.

        Top-left belongs to the player's health bar and the power-up status
        list, so the boss bar is right-aligned instead of centred - a centred
        bar is wide enough on a 600 px screen to draw straight over them.
        """
        return self.assets.boss_health_full_img.get_rect(
            topright=(
                settings.WIDTH - settings.BOSS_HEALTH_BAR_MARGIN_X,
                settings.BOSS_HEALTH_BAR_Y,
            )
        )

    def _boss_bar_visible(self) -> bool:
        """True only while the boss is in its active fight position.

        The bar must not appear during the entrance (it belongs to the fight,
        not the arrival) nor once the death chain has started.
        """
        return self.boss is not None and not self.boss.entering and not self.boss_dying

    def _draw_boss_health_bar(self) -> None:
        """Boss health bar: the empty artwork as the track, with the full
        artwork wiped over it to the current HP fraction.

        The bar is redrawn from live HP every frame (nothing about it is
        cached at boss entry).

        Why a wipe rather than the crossfade this used to do: the two assets
        are a filled bar and a hollow frame of the SAME size, so crossfading
        them does not shorten the bar - it dissolves the fill in place over
        its whole length, leaving a full-length bar that only fades as HP
        drops. Over a starfield (which shows through the transparent frame)
        that is very hard to read as damage. Wiping the fill makes the loss
        of HP unambiguous.
        """
        if self.boss is None:
            return
        rect = self._boss_bar_rect()
        self.screen.blit(self.assets.boss_health_empty_img, rect)
        fill = self._boss_bar_fill_width(self.boss.hp, self.boss.max_hp, rect.width)
        if fill > 0:
            self.screen.blit(
                self.assets.boss_health_full_img,
                rect,
                area=pygame.Rect(0, 0, fill, rect.height),
            )

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
