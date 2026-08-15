"""Audio: the game must boot and run headless with SDL_AUDIODRIVER=dummy
(forced by conftest), and every sound-triggering code path must be safe
when audio is unavailable or muted. Audio failures are never fatal."""

import pygame

from audio import AudioManager
from bullet import Bullet
from enemy import Enemy
from helpers import KeyState, place_enemy_over_player, start_game


def test_game_boots_with_audio_manager(game):
    assert game.audio is not None
    # With the dummy driver the mixer initializes; either way, loading all
    # sounds and the music must not crash.
    assert isinstance(game.audio.available, bool)


def test_all_sfx_and_music_loaded_with_dummy_driver(game):
    if game.audio.available:
        assert set(game.audio.sounds) == {
            "shoot",
            "hit",
            "explosion",
            "player_death",
            "menu_hover",
            "menu_click",
            "powerup",
        }
        assert game.audio.music_loaded


def test_mute_toggle_flips_state(game):
    audio = game.audio
    was = audio.muted
    assert audio.toggle_mute() is not was
    assert audio.muted is not was
    audio.toggle_mute()
    assert audio.muted is was


def test_playing_unknown_sound_is_a_noop(game):
    # Unknown names must never raise, whether muted or not.
    game.audio.play("does_not_exist")
    game.audio.set_muted(True)
    game.audio.play("does_not_exist")
    game.audio.set_muted(False)


def test_muted_playback_does_not_crash(game):
    game.audio.set_muted(True)
    game.audio.play("shoot")
    game.audio.play_music()
    game.audio.toggle_mute()  # unmute
    game.audio.play("shoot")


def test_shooting_fires_sound_and_bullet(game):
    start_game(game)
    game.enemies = []
    game.player.y = 600
    n_bullets = len(game.bullets)
    game._update_game(KeyState(pygame.K_SPACE))  # hold Space -> shoot sound path
    assert len(game.bullets) == n_bullets + 1  # sound path ran without crashing


def test_hit_and_death_paths_do_not_crash(game):
    start_game(game)
    p = game.player
    p.health = 2
    e = place_enemy_over_player(game)

    game._update_game(KeyState())  # non-lethal hit -> "hit" sound path
    assert p.health == 1

    e.x, e.y = p.x + 10, p.y + 5
    game._update_game(KeyState())  # lethal hit while invulnerable -> death + fade-out
    assert p.dead


def test_enemy_explosion_path_does_not_crash(game):
    start_game(game)
    e = Enemy(200, 300)
    game.enemies = [e]
    game.bullets = [Bullet(220, 320)]
    score0 = game.score
    game._update_game(KeyState())  # bullet hits enemy -> "explosion" sound path
    assert game.score == score0 + 1


def test_menu_hover_and_click_paths_do_not_crash(game):
    # Hovering the play button (hover SFX) then clicking it (click SFX).
    pos = game.main_menu.play_rect.center
    game.main_menu.draw(game.screen, pos)
    game._handle_mouse_click(pos)
    assert game.fade.fading_out


def test_music_lifecycle_does_not_crash(game):
    start_game(game)
    game.audio.play_music()
    game.audio.pause_music()
    game.audio.play_music()
    game.audio.fade_out_music()
    game.audio.stop_music()


def test_audio_manager_survives_mixer_failure(monkeypatch):
    """Simulate a machine with no usable audio device: the manager must
    report unavailable and every play() must be a safe no-op."""

    def _no_mixer():
        raise pygame.error("no audio device")

    monkeypatch.setattr(pygame.mixer, "get_init", lambda: None)
    monkeypatch.setattr(pygame.mixer, "init", _no_mixer)

    mgr = AudioManager()
    assert mgr.available is False
    assert mgr.sounds == {}

    mgr.play("shoot")  # no-op
    mgr.play_music()  # no-op
    mgr.pause_music()
    mgr.fade_out_music()
    mgr.set_muted(True)
    mgr.toggle_mute()
