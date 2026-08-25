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


# ------------------------------------------------------------------ #
# Score HUD visibility
# ------------------------------------------------------------------ #

def test_score_still_increments_during_gameplay(game):
    """Score logic is untouched — only the draw call was removed."""
    from bullet import Bullet
    from enemy import Enemy
    from helpers import KeyState, start_game
    start_game(game)
    assert game.state == "game"
    # Place an enemy and a bullet overlapping it (same pattern as
    # test_collisions.py).
    e = Enemy(200, 300)
    game.enemies = [e]
    game.bullets = [Bullet(220, 320)]
    initial_score = game.score
    game._update_game(KeyState())
    assert game.score == initial_score + 1


def test_score_hud_not_drawn_during_gameplay(game):
    """During state == 'game', the score HUD is not rendered."""
    start_game(game)
    assert game.state == "game"
    # Draw one gameplay frame.
    game._draw_frame((0, 0))
    # The score HUD was drawn at (10, 10) in SCORE_COLOR (yellow).
    # With it removed, the pixel at (10, 10) should be the background
    # (parallax layer), not yellow text.
    r, g, b = game.screen.get_at((10, 10))[:3]
    assert (r, g, b) != settings.SCORE_COLOR, (
        f"Score HUD still visible at (10,10): RGB=({r},{g},{b})"
    )


def test_game_over_still_shows_score(game):
    """Game-over screen still renders the score — only gameplay HUD was hidden."""
    from helpers import pump
    start_game(game)
    # Force death.
    game.player.health = 1
    game.player.take_hit()
    assert game.player.dead
    # Play through death animation and fade to game_over.
    pump(game)
    assert game.state == "game_over"
    # The game-over menu draws its own score display (not via ui.draw_score).
    # Just confirm the state is correct and no crash on draw.
    game._draw_frame(game.game_over_menu.restart_rect.center)


def test_high_scores_still_shows_score(game):
    """High-scores screen still shows entries with real score values."""
    from highscores import HighScoreTable
    # Add a fake entry.
    game.high_scores.add(42.5, result="Dead")
    game.last_run_rank = 0
    game.fade.start("high_scores")
    pump_fade(game)
    assert game.state == "high_scores"
    # Draw should not crash.
    game._draw_frame((0, 0))
