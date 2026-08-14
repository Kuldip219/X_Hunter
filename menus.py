"""
Menu screens: main menu, pause menu, game-over menu, the options
placeholder screen, and the high-scores leaderboard screen. Each menu
knows how to draw itself and how to turn a mouse click into an action
string, keeping that logic out of the main loop.
"""

from __future__ import annotations

import time
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


def _track_hover(menu, mouse_pos: tuple[int, int]) -> None:
    """Play the hover SFX when the mouse moves onto a different button."""
    hovered = None
    for name, rect in menu._buttons():
        if rect.collidepoint(mouse_pos):
            hovered = name
            break
    if hovered != menu._last_hovered:
        menu._last_hovered = hovered
        if hovered is not None and menu.audio is not None:
            menu.audio.play("menu_hover")


class MainMenu:
    def __init__(
        self, assets: "Assets", screen_width: int, audio=None
    ) -> None:
        self.assets = assets
        self.audio = audio
        self._last_hovered = None
        self.title_rect = assets.title_img.get_rect(center=(screen_width // 2, 150))
        self.play_rect = assets.play_img.get_rect(center=(screen_width // 2, 290))
        self.options_rect = assets.options_img.get_rect(center=(screen_width // 2, 380))
        self.exit_rect = assets.exit_img.get_rect(center=(screen_width // 2, 560))

    def _buttons(self) -> list[tuple[str, pygame.Rect]]:
        return [
            ("play", self.play_rect),
            ("options", self.options_rect),
            ("exit", self.exit_rect),
        ]

    def draw(self, screen: pygame.Surface, mouse_pos: tuple[int, int]) -> None:
        screen.fill(settings.MENU_BG_COLOR)
        screen.blit(self.assets.title_img, self.title_rect)
        _draw_button(screen, self.assets.play_img, self.play_rect, mouse_pos)
        _draw_button(screen, self.assets.options_img, self.options_rect, mouse_pos)
        _draw_button(screen, self.assets.exit_img, self.exit_rect, mouse_pos)
        _track_hover(self, mouse_pos)

    def handle_click(self, mouse_pos: tuple[int, int]) -> Optional[str]:
        if self.play_rect.collidepoint(mouse_pos):
            return "play"
        if self.options_rect.collidepoint(mouse_pos):
            return "options"
        if self.exit_rect.collidepoint(mouse_pos):
            return "exit"
        return None


class PauseMenu:
    def __init__(
        self, assets: "Assets", screen_width: int, audio=None
    ) -> None:
        self.assets = assets
        self.audio = audio
        self._last_hovered = None
        self.pause_rect = assets.pause_img.get_rect(center=(screen_width // 2, 200))
        self.continue_rect = assets.continue_img.get_rect(center=(screen_width // 2, 350))
        self.quit_rect = assets.quit_img.get_rect(center=(screen_width // 2, 450))

    def _buttons(self) -> list[tuple[str, pygame.Rect]]:
        return [("continue", self.continue_rect), ("quit", self.quit_rect)]

    def draw(self, screen: pygame.Surface, mouse_pos: tuple[int, int]) -> None:
        overlay = pygame.Surface(screen.get_size())
        overlay.set_alpha(settings.PAUSE_OVERLAY_ALPHA)
        overlay.fill(settings.PAUSE_OVERLAY_COLOR)
        screen.blit(overlay, (0, 0))

        screen.blit(self.assets.pause_img, self.pause_rect)
        _draw_button(screen, self.assets.continue_img, self.continue_rect, mouse_pos)
        _draw_button(screen, self.assets.quit_img, self.quit_rect, mouse_pos)
        _track_hover(self, mouse_pos)

    def handle_click(self, mouse_pos: tuple[int, int]) -> Optional[str]:
        if self.continue_rect.collidepoint(mouse_pos):
            return "continue"
        if self.quit_rect.collidepoint(mouse_pos):
            return "quit_to_menu"
        return None


class GameOverMenu:
    def __init__(
        self, assets: "Assets", screen_width: int, audio=None
    ) -> None:
        self.assets = assets
        self.audio = audio
        self._last_hovered = None
        self.restart_rect = assets.restart_img.get_rect(center=(screen_width // 2, 330))
        self.quit_rect = assets.quit_gameover_img.get_rect(center=(screen_width // 2, 490))

    def _buttons(self) -> list[tuple[str, pygame.Rect]]:
        return [
            ("restart", self.restart_rect),
            ("quit", self.quit_rect),
        ]

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
        _track_hover(self, mouse_pos)

    def handle_click(self, mouse_pos: tuple[int, int]) -> Optional[str]:
        if self.restart_rect.collidepoint(mouse_pos):
            return "restart"
        if self.quit_rect.collidepoint(mouse_pos):
            return "quit_to_menu"
        return None


class OptionsScreen:
    """The (still mostly placeholder) options screen. It keeps its original
    "under construction" text and ESC hint, and now hosts the HIGH SCORES
    button (score.png) - the leaderboard's only entry point."""

    def __init__(
        self, assets: "Assets", screen_width: int, screen_height: int, audio=None
    ) -> None:
        self.assets = assets
        self.audio = audio
        self._last_hovered = None
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.high_scores_rect = assets.score_img.get_rect(
            center=(screen_width // 2, 520)
        )

    def _buttons(self) -> list[tuple[str, pygame.Rect]]:
        return [("high_scores", self.high_scores_rect)]

    def draw(self, screen: pygame.Surface, mouse_pos: tuple[int, int]) -> None:
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

        _draw_button(screen, self.assets.score_img, self.high_scores_rect, mouse_pos)
        _track_hover(self, mouse_pos)

    def handle_click(self, mouse_pos: tuple[int, int]) -> Optional[str]:
        if self.high_scores_rect.collidepoint(mouse_pos):
            return "high_scores"
        return None


class HighScoresMenu:
    """The persistent leaderboard screen: shows the top-10 scores ranked.
    Reached only via the Options screen (score.png button); its BACK button
    (back.png) returns to Options, one level up."""

    def __init__(
        self,
        assets: "Assets",
        screen_width: int,
        screen_height: int,
        table=None,
        audio=None,
    ) -> None:
        self.assets = assets
        self.audio = audio
        self.table = table
        self._last_hovered = None
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.back_img = assets.back_img
        self.back_rect = self.back_img.get_rect(
            center=(screen_width // 2, screen_height - 70)
        )

    def _buttons(self) -> list[tuple[str, pygame.Rect]]:
        return [("back", self.back_rect)]

    def draw(
        self,
        screen: pygame.Surface,
        mouse_pos: tuple[int, int],
        highlight_rank: Optional[int] = None,
    ) -> None:
        """Draw the ranked score list. The row at `highlight_rank` (the rank
        the just-finished run earned, if it qualified) is drawn highlighted."""
        screen.fill(settings.MENU_BG_COLOR)
        title = self.assets.big_font.render("HIGH SCORES", True, settings.WHITE)
        screen.blit(title, title.get_rect(center=(self.screen_width // 2, 120)))

        entries = self.table.scores if self.table is not None else []
        if not entries:
            empty = self.assets.font.render("No scores yet", True, settings.LIGHT_GRAY)
            screen.blit(empty, empty.get_rect(center=(self.screen_width // 2, 300)))
        else:
            for i, entry in enumerate(entries[: settings.HIGHSCORE_MAX]):
                highlighted = highlight_rank is not None and i == highlight_rank
                color = settings.SCORE_COLOR if highlighted else settings.WHITE
                rank_img = self.assets.font.render(f"{i + 1}.", True, color)
                score_img = self.assets.font.render(str(entry.score), True, color)
                date_img = self.assets.font.render(
                    time.strftime("%Y-%m-%d", time.localtime(entry.timestamp)),
                    True,
                    settings.LIGHT_GRAY,
                )
                row_y = 200 + i * 42
                screen.blit(rank_img, rank_img.get_rect(midleft=(160, row_y)))
                screen.blit(score_img, score_img.get_rect(midleft=(230, row_y)))
                screen.blit(date_img, date_img.get_rect(midright=(440, row_y)))
                if highlighted:
                    new_img = self.assets.font.render("NEW", True, settings.SCORE_COLOR)
                    screen.blit(new_img, new_img.get_rect(midright=(540, row_y)))

        _draw_button(screen, self.back_img, self.back_rect, mouse_pos)
        _track_hover(self, mouse_pos)

    def handle_click(self, mouse_pos: tuple[int, int]) -> Optional[str]:
        if self.back_rect.collidepoint(mouse_pos):
            return "back"
        return None
