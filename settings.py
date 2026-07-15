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
PLAYER_WIDTH: int = 50
PLAYER_HEIGHT: int = 50
PLAYER_SPEED: int = 5
PLAYER_START_HEALTH: int = 5
PLAYER_IMG_SIZE: tuple[int, int] = (65, 80)

# --- Bullet --- #
BULLET_SPEED: int = 10
BULLET_IMG_SIZE: tuple[int, int] = (10, 20)
BULLET_OFFSCREEN_Y: int = -20

# --- Enemy --- #
ENEMY_WIDTH: int = 40
ENEMY_HEIGHT: int = 40
ENEMY_SPEED: int = 5
ENEMY_IMG_SIZE: tuple[int, int] = (50, 50)

# NOTE: preserved from the original code exactly as found. The initial wave
# spawned by reset_game() used a margin of 50 (player width) instead of the
# enemy width (40) used everywhere else. This is a pre-existing quirk, kept
# intentionally rather than "fixed", per refactor requirements.
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
