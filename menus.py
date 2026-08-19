"""
Menu screens: main menu, pause menu, game-over menu, the options screen
(volume sliders + three image buttons), the controls keybind screen, and
the high-scores leaderboard screen. Each menu knows how to draw itself
and how to turn mouse input into actions, keeping that logic out of the
main loop.
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
        # Uniform 100px center-to-center spacing (the original layout):
        # play -> options -> exit. Positions were temporarily re-spaced for
        # a third button (HIGH SCORES) and never restored when it was removed.
        self.play_rect = assets.play_img.get_rect(center=(screen_width // 2, 300))
        self.options_rect = assets.options_img.get_rect(center=(screen_width // 2, 400))
        self.exit_rect = assets.exit_img.get_rect(center=(screen_width // 2, 500))

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
        # Uniform 100px center-to-center spacing (matches the pause menu and
        # the original game-over layout): restart -> quit. The 490 position
        # was a leftover from when a HIGH SCORES button sat between them at
        # 410 - removed without recomputing QUIT's position.
        self.restart_rect = assets.restart_img.get_rect(center=(screen_width // 2, 350))
        self.quit_rect = assets.quit_gameover_img.get_rect(center=(screen_width // 2, 450))

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
    """Options: two live volume sliders (music / SFX) and a row of three
    image buttons - HIGH SCORES (score.png), CONTROLS (controls.png) and
    BACK (back.png) - evenly spaced with the OPTIONS_ITEM_GAP rhythm.

    Sliders are mouse-draggable: clicking anywhere on a track jumps the
    handle there, and the handle drags while the button is held. Values are
    applied live to the AudioManager on every change and persisted to the
    settings store on mouse-up (the store is only saved once per gesture).
    """

    def __init__(
        self,
        assets: "Assets",
        screen_width: int,
        screen_height: int,
        audio=None,
        store=None,
    ) -> None:
        self.assets = assets
        self.audio = audio
        self.store = store
        self._last_hovered = None
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._dragging: Optional[str] = None  # "music" | "sfx" | None

        # --- Vertical layout, computed top-down from measured text heights
        # using the OPTIONS_ITEM_GAP / OPTIONS_SECTION_GAP rhythm --- #
        title_h = self.assets.big_font.size("OPTIONS")[1]
        label_h = self.assets.font.size("Music Volume")[1]
        self.title_y = settings.OPTIONS_TITLE_Y

        # Volume slider rows: the label and track share one anchor y; the
        # two sliders are related items, so ITEM_GAP apart.
        track_size = settings.SLIDER_TRACK_SIZE
        self.slider_tracks: dict[str, pygame.Rect] = {}
        self.slider_labels: dict[str, tuple[str, int]] = {}
        y = self.title_y + title_h // 2 + settings.OPTIONS_SECTION_GAP
        for name, label in (("music", "Music Volume"), ("sfx", "SFX Volume")):
            anchor = y + label_h // 2
            track = pygame.Rect(0, 0, track_size[0], track_size[1])
            track.center = (screen_width // 2 + 50, anchor)
            self.slider_tracks[name] = track
            self.slider_labels[name] = (label, anchor)
            y += label_h + settings.OPTIONS_ITEM_GAP

        # Three image buttons (HIGH SCORES, CONTROLS, BACK) sit in the space
        # the controls list used to occupy: SECTION_GAP below the sliders,
        # each button ITEM_GAP apart so all three gaps are equal.
        banner_h = self.assets.score_img.get_height()
        controls_h = self.assets.controls_img.get_height()
        back_h = self.assets.back_img.get_height()
        y += settings.OPTIONS_SECTION_GAP - settings.OPTIONS_ITEM_GAP
        self.high_scores_rect = assets.score_img.get_rect(
            center=(screen_width // 2, y + banner_h // 2)
        )
        y += banner_h + settings.OPTIONS_ITEM_GAP
        self.controls_rect = assets.controls_img.get_rect(
            center=(screen_width // 2, y + controls_h // 2)
        )
        y += controls_h + settings.OPTIONS_ITEM_GAP
        self.back_rect = assets.back_img.get_rect(
            center=(screen_width // 2, y + back_h // 2)
        )

    # ------------------------------------------------------------------ #
    # Buttons (hover SFX + high-scores entry)
    # ------------------------------------------------------------------ #

    def _buttons(self) -> list[tuple[str, pygame.Rect]]:
        return [
            ("high_scores", self.high_scores_rect),
            ("controls", self.controls_rect),
            ("back", self.back_rect),
        ]

    def handle_click(self, mouse_pos: tuple[int, int]) -> Optional[str]:
        if self.high_scores_rect.collidepoint(mouse_pos):
            return "high_scores"
        if self.controls_rect.collidepoint(mouse_pos):
            return "controls"
        if self.back_rect.collidepoint(mouse_pos):
            return "back"
        return None

    # ------------------------------------------------------------------ #
    # Sliders
    # ------------------------------------------------------------------ #

    def _fraction_at(self, track: pygame.Rect, x: int) -> float:
        """Slider value (0.0-1.0) for a mouse x within the track."""
        return max(0.0, min(1.0, (x - track.left) / track.width))

    def _apply_value(self, name: str, fraction: float) -> None:
        """Clamp and apply a slider value to the store (live) and audio."""
        fraction = max(0.0, min(1.0, fraction))
        if self.store is not None:
            if name == "music":
                self.store.set_music_volume(fraction)
            else:
                self.store.set_sfx_volume(fraction)
        if self.audio is not None:
            if name == "music":
                self.audio.set_music_volume(fraction)
            else:
                self.audio.set_sfx_volume(fraction)

    def _hit_slider(self, pos: tuple[int, int]) -> Optional[str]:
        """Which slider (if any) the mouse is on. The hit zone extends above
        and below the track so the handle is grabbable too."""
        for name, track in self.slider_tracks.items():
            if track.inflate(0, 30).collidepoint(pos):
                return name
        return None

    def handle_mouse_down(self, pos: tuple[int, int]) -> bool:
        """Grab a slider if the click is on it; returns True when a slider
        owns this press (so the caller skips normal button handling)."""
        name = self._hit_slider(pos)
        if name is None:
            return False
        self._dragging = name
        self._apply_value(name, self._fraction_at(self.slider_tracks[name], pos[0]))
        return True

    def handle_mouse_motion(self, pos: tuple[int, int]) -> None:
        """While a slider is held, follow the mouse (standard drag)."""
        if self._dragging is not None:
            track = self.slider_tracks[self._dragging]
            self._apply_value(self._dragging, self._fraction_at(track, pos[0]))

    def handle_mouse_up(self, pos: tuple[int, int]) -> None:
        """Release the slider: apply the final value and persist it once."""
        if self._dragging is not None:
            track = self.slider_tracks[self._dragging]
            self._apply_value(self._dragging, self._fraction_at(track, pos[0]))
            self._dragging = None
            if self.store is not None:
                self.store.save()

    # ------------------------------------------------------------------ #
    # Drawing
    # ------------------------------------------------------------------ #

    def _draw_slider(self, screen: pygame.Surface, name: str) -> None:
        label, y = self.slider_labels[name]
        track = self.slider_tracks[name]
        value = 0.5
        if self.store is not None:
            value = (
                self.store.music_volume if name == "music" else self.store.sfx_volume
            )

        label_img = self.assets.font.render(label, True, settings.WHITE)
        screen.blit(label_img, label_img.get_rect(midleft=(70, y)))

        # Track: dark bar with a lighter border.
        pygame.draw.rect(screen, (45, 45, 45), track)
        pygame.draw.rect(screen, settings.LIGHT_GRAY, track, 2)

        # Handle: a small rounded box positioned by the current value.
        handle = pygame.Rect(0, 0, *settings.SLIDER_HANDLE_SIZE)
        handle.center = (track.left + int(value * track.width), y)
        pygame.draw.rect(screen, settings.WHITE, handle)

        pct_img = self.assets.font.render(f"{int(round(value * 100))}%", True, settings.LIGHT_GRAY)
        screen.blit(pct_img, pct_img.get_rect(midright=(570, y)))

    def draw(self, screen: pygame.Surface, mouse_pos: tuple[int, int]) -> None:
        title = self.assets.big_font.render("OPTIONS", True, settings.WHITE)
        screen.blit(title, title.get_rect(center=(self.screen_width // 2, self.title_y)))

        self._draw_slider(screen, "music")
        self._draw_slider(screen, "sfx")

        _draw_button(screen, self.assets.score_img, self.high_scores_rect, mouse_pos)
        _draw_button(screen, self.assets.controls_img, self.controls_rect, mouse_pos)
        _draw_button(screen, self.assets.back_img, self.back_rect, mouse_pos)
        _track_hover(self, mouse_pos)


class ControlsScreen:
    """Read-only keybind reference, moved off the Options screen so it can
    breathe: one binding per row in a single column. Reached only via the
    Options screen (controls.png button); its BACK button (back.png) returns
    to Options, one level up - same convention as the high-scores screen.
    """

    def __init__(
        self,
        assets: "Assets",
        screen_width: int,
        screen_height: int,
        audio=None,
    ) -> None:
        self.assets = assets
        self.audio = audio
        self._last_hovered = None
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.back_img = assets.back_img
        self.back_rect = self.back_img.get_rect(
            center=(screen_width // 2, screen_height - 70)
        )
        self.title_y = settings.CONTROLS_TITLE_Y
        self.row_ys = [
            settings.CONTROLS_ROWS_TOP + i * settings.CONTROLS_ROW_GAP
            for i in range(len(settings.CONTROLS))
        ]

    def _buttons(self) -> list[tuple[str, pygame.Rect]]:
        return [("back", self.back_rect)]

    def draw(self, screen: pygame.Surface, mouse_pos: tuple[int, int]) -> None:
        screen.fill(settings.MENU_BG_COLOR)
        title = self.assets.big_font.render("CONTROLS", True, settings.WHITE)
        screen.blit(title, title.get_rect(center=(self.screen_width // 2, self.title_y)))

        for (action, key), y in zip(settings.CONTROLS, self.row_ys):
            action_img = self.assets.font.render(action, True, settings.WHITE)
            screen.blit(
                action_img,
                action_img.get_rect(midleft=(settings.CONTROLS_ACTION_X, y)),
            )
            key_img = self.assets.font.render(key, True, settings.LIGHT_GRAY)
            screen.blit(
                key_img,
                key_img.get_rect(midright=(settings.CONTROLS_KEY_X, y)),
            )

        _draw_button(screen, self.back_img, self.back_rect, mouse_pos)
        _track_hover(self, mouse_pos)

    def handle_click(self, mouse_pos: tuple[int, int]) -> Optional[str]:
        if self.back_rect.collidepoint(mouse_pos):
            return "back"
        return None


def _format_time(seconds: float) -> str:
    """Format seconds as mm:ss (e.g. 125.3 -> '2:05')."""
    mins = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{mins}:{secs:02d}"


class HighScoresMenu:
    """The persistent leaderboard screen: shows the top-10 runs ranked by
    time.  "Finished" entries rank above "Dead" entries; within each group
    shorter time ranks first.  Reached via the Options screen; its BACK
    button returns to Options."""

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
        """Draw the ranked run list. The row at `highlight_rank` (the rank
        the just-finished run earned, if it qualified) is drawn highlighted."""
        screen.fill(settings.MENU_BG_COLOR)
        title = self.assets.big_font.render("HIGH SCORES", True, settings.WHITE)
        screen.blit(title, title.get_rect(center=(self.screen_width // 2, 120)))

        entries = self.table.entries if self.table is not None else []
        if not entries:
            empty = self.assets.font.render("No runs yet", True, settings.LIGHT_GRAY)
            screen.blit(empty, empty.get_rect(center=(self.screen_width // 2, 300)))
        else:
            for i, entry in enumerate(entries[: settings.HIGHSCORE_MAX]):
                highlighted = highlight_rank is not None and i == highlight_rank
                color = settings.SCORE_COLOR if highlighted else settings.WHITE
                rank_img = self.assets.font.render(f"{i + 1}.", True, color)
                time_img = self.assets.font.render(_format_time(entry.time_seconds), True, color)
                result_color = (
                    (100, 255, 100) if entry.result == "Finished" else (255, 100, 100)
                )
                result_img = self.assets.font.render(entry.result, True, result_color)
                row_y = 200 + i * 42
                screen.blit(rank_img, rank_img.get_rect(midleft=(120, row_y)))
                screen.blit(time_img, time_img.get_rect(midleft=(190, row_y)))
                screen.blit(result_img, result_img.get_rect(midright=(480, row_y)))
                if highlighted:
                    new_img = self.assets.font.render("NEW", True, settings.SCORE_COLOR)
                    screen.blit(new_img, new_img.get_rect(midright=(560, row_y)))

        _draw_button(screen, self.back_img, self.back_rect, mouse_pos)
        _track_hover(self, mouse_pos)

    def handle_click(self, mouse_pos: tuple[int, int]) -> Optional[str]:
        if self.back_rect.collidepoint(mouse_pos):
            return "back"
        return None
