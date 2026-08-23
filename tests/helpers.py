"""Shared helpers for driving the Game class headlessly in tests."""

import pygame


class KeyState:
    """Subscriptable fake for pygame.key.get_pressed().

    handle_input() reads `keys[pygame.K_LEFT]` / `keys[pygame.K_RIGHT]`,
    so any object whose __getitem__ answers those keys works.
    """

    def __init__(self, *pressed: int) -> None:
        self.pressed = set(pressed)

    def __getitem__(self, key: int) -> bool:
        return key in self.pressed


def pump_fade(game, frames: int = 200) -> None:
    """Advance the fade transition one step per frame, applying any
    completed state change -- mirrors what Game.run() does each loop."""
    for _ in range(frames):
        new_state = game.fade.update()
        if new_state is not None:
            game.state = new_state


def pump(game, frames: int = 200, keys=None) -> None:
    """Simulate full frames: update + draw (which advances explosions and
    triggers the death fade), then advance the fade transition."""
    keys = keys if keys is not None else KeyState()
    for _ in range(frames):
        game._update_and_draw((0, 0))
        new_state = game.fade.update()
        if new_state is not None:
            game.state = new_state


def start_game(game) -> None:
    """Click Play on the main menu and wait for gameplay to begin.

    Flow: menu -> fade -> level_intro -> fade text -> fade -> game.
    Tests bypass the run() loop, so we pump the fade and text manually.
    """
    assert game.state == "menu"
    game._handle_mouse_click(game.main_menu.play_rect.center)
    # Phase 1: fade from menu to level_intro.
    pump_fade(game)
    assert game.state == "level_intro"
    # Phase 2: play through the "Phase N" fade text until it finishes,
    # then pump the fade from level_intro to game.
    for _ in range(300):
        game.fade_text.update()
        if not game.fade_text.active:
            game._on_fade_text_done()
            break
    pump_fade(game)
    assert game.state == "game"


def pump_run(game, frames: int = 200) -> None:
    """Advance Game's real state machine for `frames` frames.

    Unlike pump_fade(), this drives Game._advance_transitions() - the exact
    code run() uses - so the fade transition AND the fade text advance under
    the production guards. Tests covering pause/quit during a level transition
    need that fidelity: driving fade_text.update() by hand bypasses the guards
    that keep a finishing overlay from overriding the player's own transition.
    """
    for _ in range(frames):
        game._advance_transitions()


def pump_run_until(game, predicate, cap: int = 1500) -> bool:
    """Advance the real state machine until predicate(game) holds.

    Returns whether it held within `cap` frames, so tests can assert on it
    instead of silently passing when nothing ever happened.
    """
    for _ in range(cap):
        if predicate(game):
            return True
        game._advance_transitions()
    return predicate(game)


def reach_level_2(game) -> None:
    """Clear Level 1 by score and play the transition through to gameplay.

    Leaves the game in the "game" state on Level 2 with no overlay active.
    """
    start_game(game)
    game.score = game.level_score_target
    game._check_level_completion()
    assert pump_run_until(
        game, lambda g: g.state == "game" and g.current_level == 1
        and not g.fade_text.active
    ), "never reached Level 2 gameplay"


def place_enemy_over_player(game, dx: int = 10, dy: int = 5) -> "Enemy":
    """Replace the enemy list with a single enemy overlapping the player's
    sprite. The +5 dy accounts for enemy.update() moving it down 5px (300 px/s
    * the default 1/60 s dt) before the collision check runs."""
    from enemy import Enemy

    p = game.player
    e = Enemy(p.x + dx, p.y + dy)
    game.enemies = [e]
    return e
