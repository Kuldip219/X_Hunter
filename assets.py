"""
Loads and scales every image and font the game uses.

All loading happens explicitly via Assets.load(), not at import time, so
pygame must already be initialized (and a display mode set) before this
is called - exactly matching the original script's order of operations.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from resource_path import resource_path
import pygame
import settings


@dataclass
class Assets:
    font: pygame.font.Font
    big_font: pygame.font.Font

    player_img: pygame.Surface
    enemy_img: pygame.Surface
    bullet_img: pygame.Surface

    health_images: list[pygame.Surface] = field(default_factory=list)
    explosion_frames: list[pygame.Surface] = field(default_factory=list)

    title_img: pygame.Surface = None
    play_img: pygame.Surface = None
    options_img: pygame.Surface = None
    exit_img: pygame.Surface = None
    pause_img: pygame.Surface = None
    continue_img: pygame.Surface = None
    quit_img: pygame.Surface = None
    restart_img: pygame.Surface = None
    quit_gameover_img: pygame.Surface = None

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

        return cls(
            font=font,
            big_font=big_font,
            player_img=player_img,
            enemy_img=enemy_img,
            bullet_img=bullet_img,
            health_images=health_images,
            explosion_frames=explosion_frames,
            title_img=title_img,
            play_img=play_img,
            options_img=options_img,
            exit_img=exit_img,
            pause_img=pause_img,
            continue_img=continue_img,
            quit_img=quit_img,
            restart_img=restart_img,
            quit_gameover_img=quit_gameover_img,
        )
