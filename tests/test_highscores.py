"""High-score leaderboard: table logic, persistence, corruption handling,
state-machine navigation, and end-to-end recording on game over.

The `game` fixture redirects settings.HIGHSCORE_FILE into a per-test temp
dir (see conftest.py), so writes here never touch the real checkout.
"""

import json

import pygame

import settings
from helpers import pump, pump_fade, start_game
from highscores import HighScoreTable


def _table(path):
    return HighScoreTable.load(str(path))


def _fill(table, scores, start_ts=0.0):
    """Add `scores` in order with increasing timestamps; returns the table."""
    for i, s in enumerate(scores):
        table.add(s, timestamp=start_ts + i)
    return table


# ---------------------------------------------------------------------- #
# Table logic
# ---------------------------------------------------------------------- #


def test_qualifying_score_inserted_in_sorted_position(tmp_path):
    table = _fill(_table(tmp_path / "hs.json"), [50, 40, 30, 20, 10])
    rank = table.add(25, timestamp=99.0)
    assert rank == 3  # 50, 40, 30, 25, 20, 10
    assert [e.score for e in table.scores] == [50, 40, 30, 25, 20, 10]


def test_qualifying_score_lands_at_top(tmp_path):
    table = _fill(_table(tmp_path / "hs.json"), [100, 90, 80])
    rank = table.add(500, timestamp=99.0)
    assert rank == 0
    assert table.scores[0].score == 500


def test_non_qualifying_score_not_inserted(tmp_path):
    table = _fill(_table(tmp_path / "hs.json"), list(range(100, 90, -1)))  # 10 entries
    assert table.qualifies(5) is False
    assert table.add(5) is None
    assert [e.score for e in table.scores] == list(range(100, 90, -1))


def test_tie_at_last_place_does_not_qualify(tmp_path):
    table = _fill(_table(tmp_path / "hs.json"), list(range(100, 90, -1)))
    assert table.qualifies(91) is False  # equal to the 10th place


def test_trimmed_to_ten_entries(tmp_path):
    table = _fill(_table(tmp_path / "hs.json"), list(range(100, 90, -1)))
    assert len(table.scores) == 10
    rank = table.add(250, timestamp=999.0)
    assert rank == 0
    scores = table.scores
    assert len(scores) == settings.HIGHSCORE_MAX == 10
    # The lowest (91) was dropped; the new top score is present.
    assert scores[0].score == 250
    assert 91 not in [e.score for e in scores]
    assert [e.score for e in scores] == [250, 100, 99, 98, 97, 96, 95, 94, 93, 92]


def test_ties_sort_earlier_timestamp_first(tmp_path):
    table = _table(tmp_path / "hs.json")
    table.add(10, timestamp=100.0)
    table.add(10, timestamp=50.0)
    assert [e.timestamp for e in table.scores] == [50.0, 100.0]


# ---------------------------------------------------------------------- #
# Persistence
# ---------------------------------------------------------------------- #


def test_persistence_survives_restart(tmp_path):
    path = tmp_path / "hs.json"
    table = _fill(_table(path), [30, 10, 20])
    # add() persists immediately; a fresh loader must see the same top list.
    fresh = HighScoreTable.load(str(path))
    assert [e.score for e in fresh.scores] == [30, 20, 10]


def test_missing_file_loads_empty(tmp_path):
    table = HighScoreTable.load(str(tmp_path / "nope.json"))
    assert table.scores == []
    assert table.qualifies(1) is True  # not full -> any score qualifies


def test_corrupted_json_loads_empty(tmp_path):
    path = tmp_path / "hs.json"
    path.write_text("{ this is not valid json !!!", encoding="utf-8")
    table = HighScoreTable.load(str(path))
    assert table.scores == []


def test_wrong_shape_loads_empty_or_filters(tmp_path):
    path = tmp_path / "hs.json"
    # A valid entry survives a bogus sibling; an entry missing its
    # timestamp is rejected (the loader requires both fields).
    path.write_text(
        json.dumps(["bogus", {"score": 7, "timestamp": 1.0}, {"score": 8}]),
        encoding="utf-8",
    )
    table = HighScoreTable.load(str(path))
    assert [e.score for e in table.scores] == [7]

    path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    assert HighScoreTable.load(str(path)).scores == []


def test_unwritable_location_degrades_gracefully(tmp_path):
    # Parent directory does not exist -> the write fails, but add() still
    # keeps the score in memory for this session and never raises.
    table = _table(tmp_path / "missing" / "hs.json")
    rank = table.add(42, timestamp=1.0)
    assert rank == 0
    assert [e.score for e in table.scores] == [42]


def test_fresh_load_sees_nothing_after_failed_write(tmp_path):
    path = tmp_path / "missing" / "hs.json"
    table = _table(path)
    table.add(42, timestamp=1.0)
    assert HighScoreTable.load(str(path)).scores == []


# ---------------------------------------------------------------------- #
# State machine navigation
# ---------------------------------------------------------------------- #


def _enter_high_scores(game):
    """Main menu -> options -> high_scores (the only entry point now)."""
    game._handle_mouse_click(game.main_menu.options_rect.center)
    pump_fade(game)
    assert game.state == "options"
    game._handle_mouse_click(game.options_screen.high_scores_rect.center)
    assert game.fade.next_state == "high_scores"
    pump_fade(game)
    assert game.state == "high_scores"


def test_high_scores_not_reachable_directly_from_main_menu(game):
    # The standalone HIGH SCORES button was removed from the main menu: no
    # rect exists, so the leaderboard is only reachable via Options.
    assert not hasattr(game.main_menu, "highscores_rect")


def test_high_scores_not_reachable_from_game_over(game):
    # Likewise removed from the game-over screen.
    assert not hasattr(game.game_over_menu, "highscores_rect")


def test_high_scores_reachable_via_options(game):
    _enter_high_scores(game)


def test_high_scores_back_button_returns_to_options(game):
    _enter_high_scores(game)
    game._handle_mouse_click(game.high_scores_menu.back_rect.center)
    assert game.fade.next_state == "options"
    pump_fade(game)
    assert game.state == "options"


def test_high_scores_esc_returns_to_options(game):
    _enter_high_scores(game)
    game._handle_keydown(pygame.K_ESCAPE)
    pump_fade(game)
    assert game.state == "options"


def test_high_scores_menu_draws_without_crashing(game):
    _enter_high_scores(game)
    game._update_and_draw((0, 0))  # render-only frame in the new state
    assert game.state == "high_scores"


# ---------------------------------------------------------------------- #
# End-to-end: recording on game over
# ---------------------------------------------------------------------- #


def _die_after_scoring(game, score):
    start_game(game)
    game.score = score
    game.player.health = 1
    assert game.player.take_hit() is True
    assert game.player.dead
    pump(game)  # explosion plays out -> fade starts -> score recorded
    assert game.state == "game_over"


def test_final_score_recorded_on_game_over(game):
    _die_after_scoring(game, 42)
    assert [e.score for e in game.high_scores.scores] == [42]
    assert game.last_run_rank == 0

    # Persisted: a fresh loader reading the same file sees the score.
    fresh = HighScoreTable.load(game.high_scores.path)
    assert [e.score for e in fresh.scores] == [42]


def test_non_qualifying_run_not_recorded(game):
    # Pre-fill the table with 10 perfect scores.
    for i in range(10):
        game.high_scores.add(100, timestamp=float(i))
    assert len(game.high_scores.scores) == 10

    _die_after_scoring(game, 5)
    assert game.last_run_rank is None
    assert 5 not in [e.score for e in game.high_scores.scores]
    assert len(game.high_scores.scores) == 10


def test_qualifying_run_highlighted_on_high_scores_screen(game):
    _die_after_scoring(game, 42)
    # Navigate: game_over -> menu -> options -> high_scores. The NEW badge
    # must still mark the just-finished run's rank 0.
    game._handle_mouse_click(game.game_over_menu.quit_rect.center)
    pump_fade(game)
    assert game.state == "menu"
    _enter_high_scores(game)
    assert game.last_run_rank == 0
    game._update_and_draw((0, 0))  # renders the list without crashing


def test_score_recorded_before_restart_resets(game):
    _die_after_scoring(game, 7)
    game._handle_mouse_click(game.game_over_menu.restart_rect.center)
    pump_fade(game)
    assert game.state == "game"  # fresh run: score reset, rank cleared
    assert game.score == 0
    assert game.last_run_rank is None
    assert [e.score for e in game.high_scores.scores] == [7]


# ---------------------------------------------------------------------- #
# Menu banner assets
# ---------------------------------------------------------------------- #


def test_menu_banner_images_load_and_preserve_aspect_ratio(game):
    # score.png (1489x382) and back.png (1491x354) load without crashing and
    # scale to fit within the 250x80 footprint, preserving aspect ratio (no
    # stretch/distortion).
    sw, sh = game.assets.score_img.get_size()
    assert sw <= settings.SCORE_IMG_SIZE[0] and sh <= settings.SCORE_IMG_SIZE[1]
    assert abs(sw / sh - 1489 / 382) < 0.03  # pixel truncation allows ~0.4%

    bw, bh = game.assets.back_img.get_size()
    assert bw <= settings.BACK_IMG_SIZE[0] and bh <= settings.BACK_IMG_SIZE[1]
    assert abs(bw / bh - 1491 / 354) < 0.03


def test_menu_banner_falls_back_when_file_missing(monkeypatch, game):
    from assets import _load_menu_banner

    def boom(*args, **kwargs):
        raise pygame.error("file not found")

    monkeypatch.setattr(pygame.image, "load", boom)
    surf = _load_menu_banner(
        "Assets/score.png", settings.SCORE_IMG_SIZE, game.assets.font, "HIGH SCORES"
    )
    # The fallback is a font-rendered button filling the full footprint.
    assert surf.get_size() == settings.SCORE_IMG_SIZE
