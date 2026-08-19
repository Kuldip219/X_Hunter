"""
Loads and scales every image and font the game uses.

All loading happens explicitly via Assets.load(), not at import time, so
pygame must already be initialized (and a display mode set) before this
is called - exactly matching the original script's order of operations.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from resource_path import resource_path
import numpy as np
import pygame
import settings


def _content_crop(surf: pygame.Surface) -> pygame.Rect:
    """Return the bounding rect of the largest contiguous block of opaque
    pixels in *surf*.  Simple ``get_bounding_rect()`` fails on sprites with
    stray corner pixels (e.g. sheild.png has isolated opaque pixels at two
    opposite corners that span the full canvas).  This helper finds the
    main icon content by identifying the longest uninterrupted run of
    rows/columns that each contain at least one opaque pixel.
    """
    alpha = pygame.surfarray.pixels_alpha(surf)
    opaque_per_row = np.sum(alpha > 128, axis=1)  # type: ignore[no-untyped-call]
    opaque_per_col = np.sum(alpha > 128, axis=0)  # type: ignore[no-untyped-call]

    def _longest_run(mask: np.ndarray) -> tuple[int, int]:  # type: ignore[type-arg]
        runs: list[tuple[int, int, int]] = []
        start: int | None = None
        for i, v in enumerate(mask):
            if v and start is None:
                start = i
            elif not v and start is not None:
                runs.append((start, i - 1, i - start))
                start = None
        if start is not None:
            runs.append((start, len(mask) - 1, len(mask) - start))
        if not runs:
            return (0, 0)
        best = max(runs, key=lambda r: r[2])
        return (best[0], best[1])

    y0, y1 = _longest_run(opaque_per_row > 0)
    x0, x1 = _longest_run(opaque_per_col > 0)
    return pygame.Rect(x0, y0, x1 - x0 + 1, y1 - y0 + 1)


@dataclass
class Assets:
    font: pygame.font.Font
    big_font: pygame.font.Font

    player_img: pygame.Surface
    enemy_img: pygame.Surface
    bullet_img: pygame.Surface
    enemy_bullet_img: pygame.Surface
    gunner_img: pygame.Surface

    health_images: list[pygame.Surface] = field(default_factory=list)
    explosion_frames: list[pygame.Surface] = field(default_factory=list)
    powerup_images: dict[str, pygame.Surface] = field(default_factory=dict)

    title_img: pygame.Surface = None
    play_img: pygame.Surface = None
    options_img: pygame.Surface = None
    exit_img: pygame.Surface = None
    pause_img: pygame.Surface = None
    continue_img: pygame.Surface = None
    quit_img: pygame.Surface = None
    restart_img: pygame.Surface = None
    quit_gameover_img: pygame.Surface = None
    score_img: pygame.Surface = None
    back_img: pygame.Surface = None
    controls_img: pygame.Surface = None

    @classmethod
    def load(cls) -> "Assets":
        """Load, scale, and return every game asset in one call."""

        font = pygame.font.Font(
            resource_path(settings.FONT_PATH),
            settings.FONT_SIZE_SMALL
        )
        big_font = pygame.font.Font(
            resource_path(settings.FONT_PATH),
            settings.FONT_SIZE_LARGE
        )

        player_img = pygame.transform.scale(
            pygame.image.load(resource_path("Assets/Playership1.png")), settings.PLAYER_IMG_SIZE
        )
        enemy_img = pygame.transform.scale(
            pygame.image.load(resource_path("Assets/Enemyship.png")), settings.ENEMY_IMG_SIZE
        )
        bullet_img = pygame.transform.scale(
            pygame.image.load(resource_path("Assets/Bullet1.png")), settings.BULLET_IMG_SIZE
        )

        # Enemy bullet: recolor the player bullet sprite to red by swapping
        # the blue channel out and boosting red, then scale to the enemy
        # bullet size.  The original is kept untouched for the player.
        raw_ebullet = pygame.image.load(resource_path("Assets/Bullet1.png")).convert_alpha()
        ebullet_recolored = raw_ebullet.copy()
        # Tint red: set R=255, G=G*0.3, B=B*0.2 on non-transparent pixels.
        for px in range(ebullet_recolored.get_width()):
            for py in range(ebullet_recolored.get_height()):
                r, g, b, a = ebullet_recolored.get_at((px, py))
                if a > 0:
                    ebullet_recolored.set_at((px, py), (255, int(g * 0.3), int(b * 0.2), a))
        enemy_bullet_img = pygame.transform.scale(
            ebullet_recolored, settings.ENEMY_BULLET_IMG_SIZE
        )

        # Gunner: reuse the enemy sprite.
        gunner_img = enemy_img

        health_images = [
            pygame.image.load(resource_path(f"Assets/health_{i}.png")) for i in range(6)
        ]
        health_images = [
            pygame.transform.scale(img, (200, 70)) for img in health_images
        ]

        explosion_frames = []
        for i in range(1, 9):
            img = pygame.image.load(resource_path(f"Assets/explosion_{i}.png"))
            img = pygame.transform.scale(img, settings.EXPLOSION_IMG_SIZE)
            explosion_frames.append(img)

        title_img = pygame.transform.scale(
            pygame.image.load(resource_path("Assets/title.png")), settings.TITLE_IMG_SIZE
        )
        play_img = pygame.transform.scale(
            pygame.image.load(resource_path("Assets/play.png")), settings.PLAY_IMG_SIZE
        )
        options_img = pygame.transform.scale(
            pygame.image.load(resource_path("Assets/options.png")), settings.OPTIONS_IMG_SIZE
        )
        exit_img = pygame.transform.scale(
            pygame.image.load(resource_path("Assets/exit.png")), settings.EXIT_IMG_SIZE
        )
        pause_img = pygame.transform.scale(
            pygame.image.load(resource_path("Assets/menu.png")), settings.PAUSE_IMG_SIZE
        )
        continue_img = pygame.transform.scale(
            pygame.image.load(resource_path("Assets/continue.png")), settings.CONTINUE_IMG_SIZE
        )
        quit_img = pygame.transform.scale(
            pygame.image.load(resource_path("Assets/quit.png")), settings.QUIT_IMG_SIZE
        )
        restart_img = pygame.transform.scale(
            pygame.image.load(resource_path("Assets/restart.png")), settings.RESTART_IMG_SIZE
        )
        quit_gameover_img = pygame.transform.scale(
            pygame.image.load(resource_path("Assets/quitt.png")), settings.QUIT_GAMEOVER_IMG_SIZE
        )
        powerup_images = {}
        for kind, filename in settings.POWERUP_IMG_FILES.items():
            raw = pygame.image.load(resource_path(f"Assets/{filename}")).convert_alpha()
            # Crop to the largest contiguous block of opaque pixels, then
            # aspect-fit scale within POWERUP_VISIBLE_SIZE.  Simple
            # bounding-rect crops fail on sprites with stray corner pixels
            # (e.g. sheild.png has isolated opaque pixels at two corners
            # that span the full canvas).  The contiguous-block approach
            # finds the main icon content and ignores disconnected artifacts.
            crop = _content_crop(raw)
            content = raw.subsurface(crop)
            vis = settings.POWERUP_VISIBLE_SIZE
            w, h = content.get_size()
            scale = min(vis[0] / w, vis[1] / h)
            new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
            scaled = pygame.transform.smoothscale(content, new_size)
            surf = pygame.Surface(settings.POWERUP_IMG_SIZE, pygame.SRCALPHA)
            ox = (settings.POWERUP_IMG_SIZE[0] - new_size[0]) // 2
            oy = (settings.POWERUP_IMG_SIZE[1] - new_size[1]) // 2
            surf.blit(scaled, (ox, oy))
            powerup_images[kind] = surf

        score_img = _load_menu_banner("Assets/score.png", settings.SCORE_IMG_SIZE, font, "HIGH SCORES")
        back_img = _load_menu_banner("Assets/back.png", settings.BACK_IMG_SIZE, font, "BACK")
        controls_img = _load_menu_banner("Assets/controls.png", settings.CONTROLS_IMG_SIZE, font, "CONTROLS")

        return cls(
            font=font,
            big_font=big_font,
            player_img=player_img,
            enemy_img=enemy_img,
            bullet_img=bullet_img,
            enemy_bullet_img=enemy_bullet_img,
            gunner_img=gunner_img,
            health_images=health_images,
            explosion_frames=explosion_frames,
            powerup_images=powerup_images,
            title_img=title_img,
            play_img=play_img,
            options_img=options_img,
            exit_img=exit_img,
            pause_img=pause_img,
            continue_img=continue_img,
            quit_img=quit_img,
            restart_img=restart_img,
            quit_gameover_img=quit_gameover_img,
            score_img=score_img,
            back_img=back_img,
            controls_img=controls_img,
        )


def _load_menu_banner(
    path: str,
    footprint: tuple[int, int],
    font: pygame.font.Font,
    label: str,
) -> pygame.Surface:
    """Load a menu banner image scaled to FIT WITHIN `footprint`, preserving
    its aspect ratio (never stretched/distorted). If the file is missing or
    unreadable, fall back to a font-rendered button so the game still boots
    - consistent with the game's non-fatal asset handling elsewhere.
    """
    try:
        img = pygame.image.load(resource_path(path))
    except (pygame.error, FileNotFoundError):
        print(f"WARNING: could not load {path}; using font-rendered '{label}' button")
        surface = pygame.Surface(footprint, pygame.SRCALPHA)
        surface.fill((45, 45, 45, 255))
        text = font.render(label, True, settings.WHITE)
        surface.blit(text, text.get_rect(center=(footprint[0] // 2, footprint[1] // 2)))
        return surface
    w, h = img.get_size()
    scale = min(footprint[0] / w, footprint[1] / h)
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return pygame.transform.scale(img, new_size)
