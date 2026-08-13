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

# --- Player --- #
# Collision rect dimensions. These must match PLAYER_IMG_SIZE so the hitbox
# coincides exactly with the rendered sprite (both drawn from the top-left
# corner (x, y)).
PLAYER_WIDTH: int = 65
PLAYER_HEIGHT: int = 80
PLAYER_SPEED: int = 5
PLAYER_START_HEALTH: int = 5
PLAYER_IMG_SIZE: tuple[int, int] = (65, 80)

# --- Invulnerability (i-frames) --- #
# After taking a hit the player is immune for this many frames (~1 s at 60 FPS)
# and blinks every PLAYER_BLINK_INTERVAL frames to show they are safe.
PLAYER_INVULNERABLE_DURATION: int = 60
PLAYER_BLINK_INTERVAL: int = 6

# --- Bullet --- #
BULLET_SPEED: int = 10
BULLET_IMG_SIZE: tuple[int, int] = (10, 20)
BULLET_OFFSCREEN_Y: int = -20

# --- Enemy --- #
# Collision rect dimensions. These must match ENEMY_IMG_SIZE so the hitbox
# coincides exactly with the rendered sprite (both drawn from the top-left
# corner (x, y)).
ENEMY_WIDTH: int = 50
ENEMY_HEIGHT: int = 50
ENEMY_SPEED: int = 5
ENEMY_IMG_SIZE: tuple[int, int] = (50, 50)

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
