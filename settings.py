"""
Central place for every constant used across the game.

Nothing in here has side effects (no pygame calls), so this module is safe
to import from anywhere without worrying about import order.
"""

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
# CONTROLS_ACTION_X and its key midright at CONTROLS_KEY_X.
CONTROLS_TITLE_Y: int = 120
CONTROLS_ROWS_TOP: int = 280
CONTROLS_ROW_GAP: int = 60
CONTROLS_ACTION_X: int = 120
CONTROLS_KEY_X: int = 470

# --- Controls reference (read-only, sourced from the real bindings) --- #
# Each row is (action, key). These match the actual input handling: player
# movement reads K_LEFT/K_RIGHT (player.py handle_input), firing is K_SPACE
# held (game.py _update_game), mute is K_m and pause/back are K_ESCAPE
# (game.py _handle_keydown). Restart has no keyboard binding - it is the
# RESTART button on the game-over screen.
CONTROLS: list[tuple[str, str]] = [
    ("Move", "LEFT / RIGHT"),
    ("Fire (hold)", "SPACE"),
    ("Pause / Resume", "ESC"),
    ("Mute / Unmute", "M"),
    ("Back (menus)", "ESC"),
    ("Restart", "RESTART button"),
]
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

# The HEALTH power-up is a comeback item: it only becomes eligible to drop
# once the player has lost at least 20% of their full health bar (health
# strictly BELOW 80% of max). At full health or exactly 80% it is excluded
# from the drop pool entirely, so it can never be farmed at high health.
# Health is a segmented bar (PLAYER_START_HEALTH = 5 segments), so with the
# default max this means health < 4.
HEALTH_POWERUP_MIN_HEALTH_FRACTION: float = 0.8

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
POWERUP_STATUS_Y: int = 135
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

# --- Levels ---
# The game is split into discrete levels. Each level has a score target
# that triggers a transition to the next level (or ends the run if it's
# the last implemented level). Score resets on transition; the run timer
# continues across levels.
LEVEL_COUNT: int = 2
LEVEL_SCORE_TARGETS: list[int] = [200, 100]  # Level 1 target, Level 2 target (placeholder)

# Fade text: displayed centered on screen, fades in, holds, fades out.
# Used for "Phase 1", "Level Finished", "Phase 2" (placeholder for L2).
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

# --- Button hover offset (buttons nudge down 5px on hover) ---
BUTTON_HOVER_OFFSET: int = 5
