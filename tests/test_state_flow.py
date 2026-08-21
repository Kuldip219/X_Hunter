"""Full state machine flow: menu -> play -> game_over -> restart.

The game switches states through the FadeTransition: a click starts a
fade-out, and the state only changes when that fade-out completes (17
frames at FADE_SPEED=15 over 255 alpha levels).
"""

import settings
from helpers import pump, pump_fade, start_game


def test_game_starts_in_menu(game):
    assert game.state == "menu"
    assert not game.player.dead


def test_menu_play_click_starts_fade_then_enters_game(game):
    assert game.state == "menu"
    game._handle_mouse_click(game.main_menu.play_rect.center)

    # The fade-out is in progress; the state switch happens on completion.
    assert game.state == "menu"
    assert game.fade.fading_out
    assert game.fade.next_state == "level_intro"

    pump_fade(game)
    assert game.state == "level_intro"
    assert game.fade_text.active
    assert game.fade_text.text.startswith("Phase")

    # Play through the intro text to reach gameplay.
    for _ in range(300):
        game.fade_text.update()
        if not game.fade_text.active:
            game._on_fade_text_done()
            break
    pump_fade(game)
    assert game.state == "game"
    assert not game.player.dead
    assert game.score == 0


def test_play_to_game_over_and_restart(game):
    start_game(game)

    # Kill the player: bring it to 1 HP and land the killing blow.
    player = game.player
    player.health = 1
    assert player.take_hit() is True
    assert player.dead

    # Pump full frames: the death explosion plays out, the fade-out to
    # game_over completes, and the state switches.
    pump(game)
    assert game.state == "game_over"

    # The dead player is never revived during the transition.
    assert game.player.dead is True
    assert game.player.health == 0

    # Restart from the game-over menu -> fade -> level_intro -> fade -> game.
    game._handle_mouse_click(game.game_over_menu.restart_rect.center)
    assert game.state == "game_over"  # fade-out still in progress
    assert game.fade.fading_out

    pump_fade(game)
    assert game.state == "level_intro"

    # Play through the intro text to reach gameplay.
    for _ in range(300):
        game.fade_text.update()
        if not game.fade_text.active:
            game._on_fade_text_done()
            break
    pump_fade(game)
    assert game.state == "game"
    assert not game.player.dead
    assert game.player.health == settings.PLAYER_START_HEALTH
    assert game.score == 0
    assert game.bullets == []
    assert game.explosions == []
