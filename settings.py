"""
Central place for every constant used across the game.

Nothing in here has side effects (no pygame calls), so this module is safe
to import from anywhere without worrying about import order. The only
pygame usage is reading key constants for the default key bindings.
"""

import pygame

# --- Screen --- #
WIDTH: int = 600
HEIGHT: int = 800
FPS: int = 60
CAPTION: str = "X Hunter"

# --- Fonts --- #
FONT_PATH: str = "Fonts/pixeltype.ttf"
FONT_SIZE_SMALL: int = 36
FONT_SIZE_LARGE: int = 72

# --- Delta time --- #
# Movement and gameplay timers are expressed in real time (seconds) and
# scaled by the per-frame delta time, so game speed is independent of the
# actual frame rate. MAX_FRAME_DT clamps a single frame's dt after a lag
# spike, tab switch, or breakpoint pause so a huge dt cannot teleport
# entities or burst-fire a wall of bullets: 0.05 s = 3 frames at 60 FPS,
# but also a full frame at 20 FPS - it caps the worst-case jump while
# still letting low frame rates run smoothly.
MAX_FRAME_DT: float = 0.05

# Fixed simulation timestep: the gameplay simulation always advances in
# constant FIXED_DT steps (60 Hz), decoupled from the render rate. Real
# elapsed time (capped by MAX_FRAME_DT per rendered frame) is banked into
# an accumulator in Game.run(); each full FIXED_DT runs one _update_game
# step, so a rendered frame can run 0, 1, or several simulation steps
# depending on how far behind real time the render loop is. This keeps
# collision checks and timers on constant-size steps at any frame rate.
FIXED_DT: float = 1.0 / 60.0

# --- Player --- #
# Collision rect dimensions. These must match PLAYER_IMG_SIZE so the hitbox
# coincides exactly with the rendered sprite (both drawn from the top-left
# corner (x, y)).
PLAYER_WIDTH: int = 65
PLAYER_HEIGHT: int = 80
# 5 px/frame at 60 FPS = 300 px/s (feel unchanged at the target frame rate).
PLAYER_SPEED_PER_SEC: int = 300
PLAYER_START_HEALTH: int = 5
PLAYER_IMG_SIZE: tuple[int, int] = (65, 80)

# Fire cooldown between shots while Space is held: 0.2 s = 12 frames at
# 60 FPS = 5 shots/s - classic arcade cadence, not a machine gun.
PLAYER_FIRE_COOLDOWN_SECONDS: float = 0.2

# --- Invulnerability (i-frames) --- #
# After taking a hit the player is immune for this long (1.0 s = 60 frames
# at 60 FPS) and blinks every PLAYER_BLINK_INTERVAL_SECONDS to show they
# are safe. Both are real time, not frame counts.
PLAYER_INVULNERABLE_DURATION_SECONDS: float = 1.0
PLAYER_BLINK_INTERVAL_SECONDS: float = 0.1

# --- Bullet --- #
# 10 px/frame at 60 FPS = 600 px/s.
BULLET_SPEED_PER_SEC: int = 600
BULLET_IMG_SIZE: tuple[int, int] = (10, 20)
BULLET_OFFSCREEN_Y: int = -20

# --- Enemy --- #
# Collision rect dimensions. These must match ENEMY_IMG_SIZE so the hitbox
# coincides exactly with the rendered sprite (both drawn from the top-left
# corner (x, y)).
ENEMY_WIDTH: int = 50
ENEMY_HEIGHT: int = 50
# 5 px/frame at 60 FPS = 300 px/s.
ENEMY_SPEED_PER_SEC: int = 300
ENEMY_IMG_SIZE: tuple[int, int] = (50, 50)

# --- Difficulty ramp --- #
# Difficulty is a single value in [0, DIFFICULTY_MAX] blended from two
# saturated terms:
#   time_term  = min(elapsed_seconds / DIFFICULTY_TIME_TO_FULL, 1)
#   score_term = min(score / DIFFICULTY_SCORE_TO_FULL, 1)
#   difficulty = min(time_weight*time_term + score_weight*score_term, MAX)
# Each input alone reaches only its weighted share, so both survival time
# AND scoring matter throughout; the cap keeps the game fair. This ramps
# invisibly (no UI) - the player just feels it get harder.
DIFFICULTY_TIME_WEIGHT: float = 0.5
DIFFICULTY_SCORE_WEIGHT: float = 0.5
DIFFICULTY_TIME_TO_FULL: float = 180.0  # seconds of survival to saturate the time term
DIFFICULTY_SCORE_TO_FULL: float = 50.0  # score to saturate the score term
DIFFICULTY_MAX: float = 1.0

# Enemy speed scales as:
#   min(ENEMY_SPEED_PER_SEC + ENEMY_SPEED_GAIN_PER_SEC*difficulty, ENEMY_MAX_SPEED_PER_SEC)
# At max difficulty: 300 + 240 = 540 px/s (9 px/frame at 60 FPS) - faster
# but still reactable.
ENEMY_SPEED_GAIN_PER_SEC: int = 240
ENEMY_MAX_SPEED_PER_SEC: int = 540

# Active enemy count scales as: min(INITIAL_ENEMY_COUNT + ENEMY_COUNT_GAIN*difficulty, ENEMY_MAX_COUNT)
# At max difficulty the field doubles from 5 to 10 enemies.
ENEMY_COUNT_GAIN: int = 5
ENEMY_MAX_COUNT: int = 10

# NOTE: the initial wave spawned by reset_game() uses a fixed X margin of 50.
# Since the enemy hitbox was resized to match the sprite (ENEMY_WIDTH 40 -> 50),
# respawn() now uses the same 50px margin, so the two spawn paths line up.
INITIAL_ENEMY_COUNT: int = 5
INITIAL_ENEMY_X_MARGIN: int = 50
INITIAL_ENEMY_MIN_Y: int = -600
INITIAL_ENEMY_MAX_Y: int = 0

RESPAWN_ENEMY_MIN_Y: int = -200
RESPAWN_ENEMY_MAX_Y: int = 0

# --- Gunner enemy (Level 2 exclusive) ---
# The gunner descends to a random stop-Y within this fraction of screen
# height, then drifts side-to-side and fires straight down on a cooldown.
# Exposed as named constants so we can tune the feel after seeing it live.
GUNNER_MAX_DESCENT_FRACTION: float = 0.55  # never past 55% of screen height
GUNNER_DRIFT_SPEED_PER_SEC: int = 150  # side-to-side px/s once stopped
GUNNER_FIRE_COOLDOWN_SECONDS: float = 2.0  # seconds between shots after stopping
GUNNER_DESCEND_SPEED_PER_SEC: int = 120  # px/s while descending to stop-Y

# --- Enemy bullets ---
# Fired straight down by gunner enemies. Visually recolored from the
# player bullet sprite (red tint) at load time in assets.py.
ENEMY_BULLET_SPEED_PER_SEC: int = 400  # px/s downward
ENEMY_BULLET_IMG_SIZE: tuple[int, int] = (10, 16)
ENEMY_BULLET_OFFSCREEN_Y: int = 820  # below screen bottom

# --- Explosions ---
EXPLOSION_IMG_SIZE: tuple[int, int] = (70, 70)
EXPLOSION_FRAME_COUNT: int = 8
ENEMY_EXPLOSION_FRAME_DELAY: int = 3
PLAYER_EXPLOSION_FRAME_DELAY: int = 5

# --- Audio --- #
# Sound effect files live under AUDIO_DIR (relative to the project root or
# PyInstaller bundle). Each SFX maps a logical event name to its filename.
AUDIO_DIR: str = "Assets/audio"
MUSIC_FILE: str = "gameplay_music.wav"
# Default volumes (0.0-1.0) - the out-of-the-box balance. These are also the
# defaults the persisted user settings (settings.json) fall back to when the
# file is missing or corrupted; the Options screen sliders adjust them live.
SFX_VOLUME: float = 0.7
MUSIC_VOLUME: float = 0.45

# User settings persistence: volumes live in SETTINGS_FILE (a JSON sibling of
# highscores.json in the game's working directory), gitignored like it.
SETTINGS_FILE: str = "settings.json"

# --- Options screen --- #
# Horizontal volume sliders: track size (width x height) and the grab handle
# footprint. The handle travels along the track; value = handle position /
# track width, clamped to [0, 1].
SLIDER_TRACK_SIZE: tuple[int, int] = (220, 12)
SLIDER_HANDLE_SIZE: tuple[int, int] = (18, 26)

# Vertical spacing system for the Options screen: related rows sit
# OPTIONS_ITEM_GAP apart (edge to edge) and unrelated sections sit
# OPTIONS_SECTION_GAP apart, giving the whole screen one consistent rhythm
# (generous between sections, tighter within a section). Every y-position is
# computed top-down in OptionsScreen from measured text heights using these
# constants - no magic numbers - so adding an element can't silently break
# the layout again.
OPTIONS_TITLE_Y: int = 100
OPTIONS_SECTION_GAP: int = 50
OPTIONS_ITEM_GAP: int = 24
# Menu banner images scale to fit WITHIN their footprints, preserving
# aspect ratio (never stretched/distorted). controls.png is the CONTROLS
# button on the Options screen.
CONTROLS_IMG_SIZE: tuple[int, int] = (250, 80)

# --- Controls screen --- #
# The keybind reference got its own full screen, so it can breathe: one
# binding per row, CONTROLS_ROW_GAP apart (center-to-center), first row at
# CONTROLS_ROWS_TOP. Each row draws its action label midleft at
# CONTROLS_ACTION_X and its key midright at CONTROLS_KEY_X. In edit mode
# (activated by the edit.png button) every keyboard row is clickable and
# can be rebound; the EDIT button sits at CONTROLS_EDIT_Y.
CONTROLS_TITLE_Y: int = 120
CONTROLS_ROWS_TOP: int = 220
CONTROLS_ROW_GAP: int = 55
CONTROLS_ACTION_X: int = 120
CONTROLS_KEY_X: int = 470
CONTROLS_EDIT_Y: int = 635

# --- Default key bindings --- #
# Action id -> default pygame key. This is the source of truth for input:
# player movement (player.py handle_input), firing (game.py _update_game),
# and mute/pause/back (game.py _handle_keydown) all read these bindings
# (via the persisted UserSettings copy). ESC is reserved (never bindable - it
# cancels an in-progress rebind instead), but pause/back may keep ESC as a
# default and be rebound away from it.
DEFAULT_KEY_BINDINGS: dict[str, int] = {
    "move_left": pygame.K_LEFT,
    "move_right": pygame.K_RIGHT,
    "fire": pygame.K_SPACE,
    "pause": pygame.K_ESCAPE,
    "mute": pygame.K_m,
    "back": pygame.K_ESCAPE,
}

# --- Controls reference --- #
# Ordered display list of (action id, label) rows, pulled from the real
# bindings. "restart" has no keyboard binding (it is the RESTART button on
# the game-over screen), so it is displayed but never rebindable.
CONTROLS: list[tuple[str, str]] = [
    ("move_left", "Move Left"),
    ("move_right", "Move Right"),
    ("fire", "Fire (hold)"),
    ("pause", "Pause / Resume"),
    ("mute", "Mute / Unmute"),
    ("back", "Back (menus)"),
    ("restart", "Restart"),
]
# Actions that can be rebound from the Controls screen (restart excluded).
REBINDABLE_ACTIONS: tuple[str, ...] = (
    "move_left",
    "move_right",
    "fire",
    "pause",
    "mute",
    "back",
)
# ESC is reserved for cancelling captures, but can be rebound for actions
# that legitimately default to it (back, pause) — rebind IS allowed in
# those cases so the user can return to the default.
ESC_DEFAULT_ACTIONS: tuple[str, ...] = ("back", "pause")
RESERVED_KEYS: tuple[int, ...] = (pygame.K_ESCAPE,)
SFX_FILES: dict[str, str] = {
    "shoot": "shoot.ogg",
    "hit": "hit.ogg",
    "explosion": "explosion.ogg",
    "player_death": "player_death.ogg",
    "menu_hover": "menu_hover.ogg",
    "menu_click": "menu_click.ogg",
    "powerup": "powerup.ogg",
}

# --- Power-ups --- #
# Power-up kinds (string keys used across powerup.py, player.py, assets.py
# and the HUD). HEALTH restores one health-bar segment (no timer); SHIELD
# grants temporary full invincibility; RAPID_FIRE temporarily boosts the
# hold-to-fire cadence.
POWERUP_KIND_SHIELD: str = "shield"
POWERUP_KIND_RAPID_FIRE: str = "rapid_fire"
POWERUP_KIND_HEALTH: str = "health"
POWERUP_TYPES: tuple[str, str, str] = (
    POWERUP_KIND_SHIELD,
    POWERUP_KIND_RAPID_FIRE,
    POWERUP_KIND_HEALTH,
)

# Power-ups only drop from destroyed enemies (never spawned freely on the
# field). Drop chance is 12% per kill - common enough to matter, rare
# enough that the difficulty ramp stays meaningful. They drift down at
# POWERUP_FALL_SPEED_PER_SEC and despawn after POWERUP_LIFETIME_SECONDS
# (both real time, ticked by dt) if the player never touches them.
POWERUP_DROP_CHANCE: float = 0.12
POWERUP_FALL_SPEED_PER_SEC: int = 250
POWERUP_LIFETIME_SECONDS: float = 8.0
# Uniform drop icons scaled to this footprint (kept centered on the drop
# point, matching how the enemy sprite was centered on its hitbox).
POWERUP_IMG_SIZE: tuple[int, int] = (40, 40)
# Visible content size after cropping transparent padding. Each icon is
# cropped to its non-transparent bounding rect then scaled to this size
# and centered on a POWERUP_IMG_SIZE surface, so all three appear the
# same visual size regardless of how much padding their source art has.
POWERUP_VISIBLE_SIZE: tuple[int, int] = (28, 28)
POWERUP_IMG_FILES: dict[str, str] = {
    POWERUP_KIND_SHIELD: "sheild.png",
    POWERUP_KIND_RAPID_FIRE: "bolt.png",
    POWERUP_KIND_HEALTH: "heart.png",
}

# The HEALTH power-up is a comeback item: it is excluded from the drop pool
# until the player is actually missing health, so it can never be farmed at
# full health. Health is a segmented bar (PLAYER_START_HEALTH = 5 segments),
# so the window is measured in whole MISSING segments: with the default of 1
# the heart starts dropping as soon as the bar falls to 4/5, and stops the
# moment it is topped back up to 5/5.
#
# This replaces a HEALTH_POWERUP_MIN_HEALTH_FRACTION of 0.8. That excluded
# the drop while health >= 5 * 0.8 == 4, so despite reading as "below 80%"
# it never actually appeared until 3/5. Counting segments states the rule
# directly: a fraction cannot express "missing at least N segments" without
# depending on where the float multiply happens to land for a given max.
HEALTH_POWERUP_MIN_MISSING_SEGMENTS: int = 1

# Shield: full temporary invincibility for the duration. Unlike the post-hit
# i-frame window (H2), the shield blocks even a would-be lethal hit - that
# is the entire point of picking it up. It is time-based, never consumed by
# a single hit.
POWERUP_SHIELD_DURATION_SECONDS: float = 3.0

# Rapid fire: while active, the hold-to-fire cooldown is multiplied by
# RAPID_FIRE_COOLDOWN_MULTIPLIER (0.2 s -> 0.06 s, ~16 shots/s). Collecting
# another rapid-fire pickup while one is active refreshes the duration
# rather than stacking.
POWERUP_RAPID_FIRE_DURATION_SECONDS: float = 3.0
RAPID_FIRE_COOLDOWN_MULTIPLIER: float = 0.3

# Power-up HUD + shield aura colors (cyan shield bubble, yellow rapid).
SHIELD_AURA_COLOR: tuple[int, int, int] = (0, 220, 255)
RAPID_FIRE_COLOR: tuple[int, int, int] = (255, 220, 0)
POWERUP_STATUS_X: int = 10
POWERUP_STATUS_Y: int = 95
POWERUP_STATUS_ROW_GAP: int = 30

# --- Effects ---
SHAKE_STRENGTH: int = 8
SHAKE_DURATION_ON_HIT: int = 40
DAMAGE_FLASH_DURATION: int = 25
DAMAGE_FLASH_ALPHA: int = 80

# --- Fade transition ---
FADE_SPEED: int = 15

# --- Menu image sizes ---
TITLE_IMG_SIZE: tuple[int, int] = (350, 120)
PLAY_IMG_SIZE: tuple[int, int] = (250, 80)
OPTIONS_IMG_SIZE: tuple[int, int] = (250, 80)
EXIT_IMG_SIZE: tuple[int, int] = (250, 80)
PAUSE_IMG_SIZE: tuple[int, int] = (400, 100)
CONTINUE_IMG_SIZE: tuple[int, int] = (250, 80)
QUIT_IMG_SIZE: tuple[int, int] = (250, 72)
RESTART_IMG_SIZE: tuple[int, int] = (250, 80)
QUIT_GAMEOVER_IMG_SIZE: tuple[int, int] = (250, 80)

# --- Colors ---
BLACK: tuple[int, int, int] = (0, 0, 0)
MENU_BG_COLOR: tuple[int, int, int] = (30, 30, 30)
SCORE_COLOR: tuple[int, int, int] = (255, 255, 0)
WHITE: tuple[int, int, int] = (255, 255, 255)
LIGHT_GRAY: tuple[int, int, int] = (200, 200, 200)
GAME_OVER_COLOR: tuple[int, int, int] = (255, 50, 50)
DAMAGE_FLASH_COLOR: tuple[int, int, int] = (255, 0, 0)
PAUSE_OVERLAY_COLOR: tuple[int, int, int] = (30, 30, 30)
PAUSE_OVERLAY_ALPHA: int = 180

# --- High scores --- #
# Persistent top-N leaderboard. Scores are stored in HIGHSCORE_FILE (a JSON
# file next to the game's working directory - the project root when run from
# source) so they survive restarts. A score earns a slot when the table is
# not full, or when it is strictly higher than the current last place; the
# list is always kept sorted best-first and trimmed to HIGHSCORE_MAX entries.
HIGHSCORE_MAX: int = 10
HIGHSCORE_FILE: str = "highscores.json"

# Menu banner images (score.png / back.png) scale to fit WITHIN these
# footprints, preserving their aspect ratio so they never distort: score.png
# is the High Scores button on the Options screen, back.png the Back button
# on the high-scores screen.
SCORE_IMG_SIZE: tuple[int, int] = (250, 80)
BACK_IMG_SIZE: tuple[int, int] = (250, 80)
# The EDIT button on the Controls screen (edit.png).
# Matches BACK_IMG_SIZE so both buttons render at the same size.
EDIT_IMG_SIZE: tuple[int, int] = (250, 80)

# --- Levels ---
# The game is split into discrete levels. Each level has a score target
# that triggers a transition to the next level (or ends the run if it's
# the last implemented level). Score resets on transition; the run timer
# continues across levels.
#
# Level 2 asks for MORE kills than Level 1 even though gunners die slower.
# Measured headlessly with an aim-and-hold autopilot: Level 1 kills ~2.5
# enemies/sec (200 target ~= 80 s), Level 2 only ~2.0 gunners/sec, because
# the active gunner count scales at half the Level 1 rate (see _update_game).
# 250 therefore makes Level 2 the longer half of the run (~125 s) on top of
# gunners shooting back, instead of the shorter one it used to be at 100.
LEVEL_SCORE_TARGETS: list[int] = [100, 150]  # Level 1 target, Level 2 target
# Derived, never hand-maintained: when LEVEL_COUNT was its own literal it
# could exceed the number of targets, and reset_game() then indexed past the
# end of the list (IndexError on RESTART after clearing the final level).
LEVEL_COUNT: int = len(LEVEL_SCORE_TARGETS)

# Ship exit animation: when a level's score target is reached, the player
# ship flies upward and off the top of the screen before the "Level Finished"
# screen appears. Speed is in px/second (dt-based, consistent with the rest
# of the movement system). At 600 px/s the 800px screen takes ~1.3s to
# traverse — fast enough to feel decisive, slow enough to be readable.
SHIP_EXIT_SPEED_PER_SEC: int = 600

# Fade text: displayed centered on screen, fades in, holds, fades out.
# Used for "Phase 1", "Level Finished", "Phase 2".
FADE_TEXT_FONT_SIZE: int = 72
FADE_TEXT_HOLD_SECONDS: float = 1.5  # how long the text stays fully visible
FADE_TEXT_SPEED: int = 5  # alpha change per frame (255 / ~51 frames ≈ 0.85s fade in/out)
# Delay before fade text begins its alpha animation (frames). Gives the
# screen time to reach full black during a FadeTransition before the text
# starts appearing, so the player sees: fade-to-black -> text -> text fades
# out -> fade-to-gameplay (instead of text and menu overlapping).
FADE_TEXT_START_DELAY: int = 18  # ~0.3s at 60 FPS
FADE_TEXT_COLOR: tuple[int, int, int] = (255, 255, 255)

# Run timer: measures total in-game time across all levels. Pauses on
# non-game states (menu, pause, game_over) using the same paused_ms
# pattern as the difficulty clock.

# --- Parallax backgrounds ---
# Two-layer vertical-scroll parallax per level, plus a static UI backdrop.
# Each layer image is exactly one screen tall (WIDTH x HEIGHT) and tiles
# seamlessly top-to-bottom. Two copies are drawn stacked; the scroll offset
# wraps when a copy fully exits the bottom so the loop is invisible.
# Speeds are in px/second (dt-based). The far layer scrolls slowly (dim,
# sparse stars), the near layer scrolls faster (brighter, more detail).
BG_L1_FAR_SPEED: int = 40   # px/s — dim, faint nebula
BG_L1_NEAR_SPEED: int = 120  # px/s — brighter stars, wisps
BG_L2_FAR_SPEED: int = 45   # px/s — slightly faster, deeper space
BG_L2_NEAR_SPEED: int = 130  # px/s — magenta wisps, debris

# Static UI background: drawn behind all menu/UI screens (non-scrolling).
# Same palette family as gameplay backgrounds but includes planet(s).
BG_UI_PATH: str = "Assets/backgrounds/ui_bg.png"

# Gameplay background layer file paths (per level, far + near).
BG_LAYERS: list[list[str]] = [
    ["Assets/backgrounds/l1_far.png", "Assets/backgrounds/l1_near.png"],  # Level 1
    ["Assets/backgrounds/l2_far.png", "Assets/backgrounds/l2_near.png"],  # Level 2
]

# --- Button hover offset (buttons nudge down 5px on hover) ---
BUTTON_HOVER_OFFSET: int = 5
