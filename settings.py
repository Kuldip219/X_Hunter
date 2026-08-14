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
SFX_VOLUME: float = 0.7
MUSIC_VOLUME: float = 0.45
SFX_FILES: dict[str, str] = {
    "shoot": "shoot.ogg",
    "hit": "hit.ogg",
    "explosion": "explosion.ogg",
    "player_death": "player_death.ogg",
    "menu_hover": "menu_hover.ogg",
    "menu_click": "menu_click.ogg",
}

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

# --- Button hover offset (buttons nudge down 5px on hover) ---
BUTTON_HOVER_OFFSET: int = 5
