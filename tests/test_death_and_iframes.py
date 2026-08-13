"""Death sequence (H1) and killing-blow i-frame edge case (H2).

These encode the two earlier bug fixes as regression tests:

H1: once death starts, gameplay (input, firing, collisions) stays frozen
    until the state machine actually leaves "game". The player must never
    flip back to alive during the fade-out, and the game-over state must
    always be reached.
H2: the invulnerability timer never protects the death sequence -- a hit
    that would bring HP to 0 always kills.
"""

import pygame

import settings
from enemy import Enemy
from helpers import KeyState, pump, start_game


def _pump_until_death_fade(game, max_frames: int = 200):
    """Pump full frames until the fade-out to game_over has started
    (state is still 'game' at that point) or max_frames elapse."""
    for _ in range(max_frames):
        game._update_and_draw((0, 0))
        new_state = game.fade.update()
        if new_state is not None:
            game.state = new_state
        if game.fade.fading_out and game.state == "game":
            return True
    return False


def test_death_starts_explosion_and_hides_player(game):
    start_game(game)
    p = game.player
    p.x, p.y = 300, 600
    p.health = 1
    assert p.take_hit() is True
    assert p.dead
    assert p.health == 0
    assert p.explosion is not None
    # Hidden off-screen while the death animation plays out.
    assert p.x < 0 and p.y < 0
    assert not p.invulnerable  # death does not grant i-frames


def test_gameplay_frozen_during_death_fade_until_game_over(game):
    start_game(game)
    p = game.player
    p.x, p.y = 300, 600
    p.health = 1
    assert p.take_hit() is True
    assert p.dead

    # Pump until the fade-out to game_over has started but the state is
    # still "game" -- this is the window H1 protects.
    assert _pump_until_death_fade(game)
    assert game.fade.fading_out
    assert game.state == "game"
    assert p.dead is True

    # --- Freeze checks during the fade-out window ---
    x0, y0 = p.x, p.y
    hp0 = p.health
    bullets0 = len(game.bullets)
    explosions0 = len(game.explosions)

    # Hold LEFT, mash SPACE and ESC for a few frames.
    for _ in range(5):
        game._update_and_draw((0, 0))
        game._handle_keydown(pygame.K_SPACE)
        game._handle_keydown(pygame.K_ESCAPE)
        new_state = game.fade.update()
        if new_state is not None:
            game.state = new_state

    assert p.dead is True  # never revived
    assert (p.x, p.y) == (x0, y0)  # immovable (arrow keys ignored)
    assert p.health == hp0  # no further damage
    assert len(game.bullets) == bullets0  # cannot fire
    assert len(game.explosions) == explosions0  # no re-triggered death anim

    # Even an enemy overlapping the hidden player cannot re-trigger death:
    # _update_game early-returns while the player is dead, so no collision
    # checks run at all.
    e = Enemy(p.x + 10, p.y + 10)
    game.enemies = [e]
    for _ in range(3):
        game._update_and_draw((0, 0))
        new_state = game.fade.update()
        if new_state is not None:
            game.state = new_state
    assert p.dead is True
    assert p.explosion is None  # no new death animation
    assert len(game.explosions) == explosions0

    # The game always reaches game_over with the player still dead.
    pump(game)
    assert game.state == "game_over"
    assert game.player.dead is True
    assert game.player.health == 0


def test_killing_blow_does_not_start_iframes(game):
    """A normal killing blow (from 1 HP) kills immediately and does not
    grant an i-frame window -- death is never delayed by invulnerability."""
    start_game(game)
    p = game.player
    p.health = 1
    assert p.take_hit() is True
    assert p.dead
    assert p.health == 0
    assert not p.invulnerable
    assert p.explosion is not None


def test_lethal_hit_bypasses_active_iframes(game):
    """H2 edge case: i-frames protect against non-lethal damage only.

    A player at 1 HP who is mid-i-frame window and takes another hit must
    still die -- the invulnerability timer must never block the death
    sequence itself.
    """
    start_game(game)
    p = game.player
    p.health = 1
    p.invulnerable_timer = settings.PLAYER_INVULNERABLE_DURATION // 2
    assert p.invulnerable

    result = p.take_hit()
    assert result is True, "a lethal hit must apply even during i-frames"
    assert p.dead
    assert p.health == 0
