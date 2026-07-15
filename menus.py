"""
Menu screens: main menu, pause menu, game-over menu, and the options
placeholder screen. Each menu knows how to draw itself and how to turn a
mouse click into an action string, keeping that logic out of the main loop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import pygame

import settings

if TYPE_CHECKING:
    # Only needed for type hints - avoids a runtime dependency on assets.py.
    from assets import Assets


def _draw_button(
    screen: pygame.Surface,
    image: pygame.Surface,
    rect: pygame.Rect,
    mouse_pos: tuple[int, int],
) -> None:
    """Draw a button, nudged down slightly while hovered (matches original)."""
    if rect.collidepoint(mouse_pos):
        screen.blit(image, (rect.x, rect.y + settings.BUTTON_HOVER_OFFSET))
    else:
        screen.blit(image, rect)


class MainMenu:
    def __init__(self, assets: "Assets", screen_width: int) -> None:
        self.assets = assets
        self.title_rect = assets.title_img.get_rect(center=(screen_width // 2, 150))
        self.play_rect = assets.play_img.get_rect(center=(screen_width // 2, 300))
        self.options_rect = assets.options_img.get_rect(center=(screen_width // 2, 400))
        self.exit_rect = assets.exit_img.get_rect(center=(screen_width // 2, 500))

    def draw(self, screen: pygame.Surface, mouse_pos: tuple[int, int]) -> None:
        screen.fill(settings.MENU_BG_COLOR)
        screen.blit(self.assets.title_img, self.title_rect)
        _draw_button(screen, self.assets.play_img, self.play_rect, mouse_pos)
        _draw_button(screen, self.assets.options_img, self.options_rect, mouse_pos)
        _draw_button(screen, self.assets.exit_img, self.exit_rect, mouse_pos)

    def handle_click(self, mouse_pos: tuple[int, int]) -> Optional[str]:
        if self.play_rect.collidepoint(mouse_pos):
            return "play"
        if self.options_rect.collidepoint(mouse_pos):
            return "options"
        if self.exit_rect.collidepoint(mouse_pos):
            return "exit"
        return None


class PauseMenu:
    def __init__(self, assets: "Assets", screen_width: int) -> None:
        self.assets = assets
        self.pause_rect = assets.pause_img.get_rect(center=(screen_width // 2, 200))
        self.continue_rect = assets.continue_img.get_rect(center=(screen_width // 2, 350))
        self.quit_rect = assets.quit_img.get_rect(center=(screen_width // 2, 450))

    def draw(self, screen: pygame.Surface, mouse_pos: tuple[int, int]) -> None:
        overlay = pygame.Surface(screen.get_size())
        overlay.set_alpha(settings.PAUSE_OVERLAY_ALPHA)
        overlay.fill(settings.PAUSE_OVERLAY_COLOR)
        screen.blit(overlay, (0, 0))

        screen.blit(self.assets.pause_img, self.pause_rect)
        _draw_button(screen, self.assets.continue_img, self.continue_rect, mouse_pos)
        _draw_button(screen, self.assets.quit_img, self.quit_rect, mouse_pos)

    def handle_click(self, mouse_pos: tuple[int, int]) -> Optional[str]:
        if self.continue_rect.collidepoint(mouse_pos):
            return "continue"
        if self.quit_rect.collidepoint(mouse_pos):
            return "quit_to_menu"
        return None


class GameOverMenu:
    def __init__(self, assets: "Assets", screen_width: int) -> None:
        self.assets = assets
        self.restart_rect = assets.restart_img.get_rect(center=(screen_width // 2, 350))
        self.quit_rect = assets.quit_gameover_img.get_rect(center=(screen_width // 2, 450))

    def draw(self, screen: pygame.Surface, mouse_pos: tuple[int, int]) -> None:
        go_text = self.assets.big_font.render("GAME OVER", True, settings.GAME_OVER_COLOR)
        go_rect = go_text.get_rect(center=(settings.WIDTH // 2, 200))
        go_shadow = self.assets.big_font.render("GAME OVER", True, settings.BLACK)

        screen.blit(go_shadow, (go_rect.x + 5, go_rect.y + 5))
        screen.blit(go_text, go_rect)

        # NOTE: the original code blits this text a second time here (a
        # no-op, since it's the same surface at the same position). Kept
        # verbatim per the decision to preserve all quirks exactly as-is.
        screen.blit(go_text, go_rect)

        _draw_button(screen, self.assets.restart_img, self.restart_rect, mouse_pos)
        _draw_button(screen, self.assets.quit_gameover_img, self.quit_rect, mouse_pos)

    def handle_click(self, mouse_pos: tuple[int, int]) -> Optional[str]:
        if self.restart_rect.collidepoint(mouse_pos):
            return "restart"
        if self.quit_rect.collidepoint(mouse_pos):
            return "quit_to_menu"
        return None


class OptionsScreen:
    def __init__(self, assets: "Assets", screen_width: int, screen_height: int) -> None:
        self.assets = assets
        self.screen_width = screen_width
        self.screen_height = screen_height

    def draw(self, screen: pygame.Surface) -> None:
        text = self.assets.font.render(
            "It's under construction", True, settings.WHITE
        )
        rect = text.get_rect(center=(self.screen_width // 2, self.screen_height // 2))
        screen.blit(text, rect)

        back_text = self.assets.font.render(
            "Press ESC to go back", True, settings.LIGHT_GRAY
        )
        back_rect = back_text.get_rect(
            center=(self.screen_width // 2, self.screen_height // 2 + 50)
        )
        screen.blit(back_text, back_rect)
