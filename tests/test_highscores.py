"""Time-based leaderboard: table logic, persistence, corruption handling,
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


def _fill(entries, start_ts=0.0):
    """Add (time, result) pairs with increasing timestamps."""
    t = _table(entries[0] if False else None)  # placeholder, replaced below
    return t


def _make_table(path, runs, start_ts=0.0):
    """Create a table and fill it with (time_seconds, result) pairs."""
    table = HighScoreTable.load(str(path))
    for i, (t, r) in enumerate(runs):
        table.add(t, result=r, timestamp=start_ts + i)
    return table


# ---------------------------------------------------------------------- #
# Table logic
# ---------------------------------------------------------------------- #


def test_qualifying_run_inserted_in_sorted_position(tmp_path):
    table = _make_table(
        tmp_path / "hs.json",
        [(30.0, "Dead"), (45.0, "Dead"), (60.0, "Dead"), (90.0, "Dead"), (120.0, "Dead")],
    )
    # Dead entries sorted descending: 120, 90, 60, 45, 30.
    # A 50s Dead run lands between 60 and 45.
    rank = table.add(50.0, result="Dead", timestamp=99.0)
    assert rank == 3  # 120, 90, 60, 50, 45, 30
    times = [e.time_seconds for e in table.entries]
    assert times == [120.0, 90.0, 60.0, 50.0, 45.0, 30.0]


def test_finished_ranks_above_dead(tmp_path):
    table = _make_table(
        tmp_path / "hs.json",
        [(30.0, "Dead"), (45.0, "Dead"), (60.0, "Dead")],
    )
    # A Finished run at 50s ranks above all Dead runs.
    rank = table.add(50.0, result="Finished", timestamp=99.0)
    assert rank == 0  # Finished 50s is best
    results = [e.result for e in table.entries]
    assert results[0] == "Finished"
    # Remaining Dead entries sorted by time DESCENDING (longest survival first).
    assert [e.time_seconds for e in table.entries[1:]] == [60.0, 45.0, 30.0]


def test_dead_sorted_by_survival_descending(tmp_path):
    """Longer survival ranks above shorter within the Dead group."""
    table = _make_table(
        tmp_path / "hs.json",
        [(30.0, "Dead"), (90.0, "Dead"), (60.0, "Dead")],
    )
    times = [e.time_seconds for e in table.entries]
    assert times == [90.0, 60.0, 30.0]  # longest first


def test_two_dead_longer_survival_ranks_first(tmp_path):
    """Directly catches the bug: two Dead entries, the longer-survival
    one must rank above the shorter one."""
    table = _make_table(
        tmp_path / "hs.json",
        [(15.0, "Dead"), (45.0, "Dead")],
    )
    times = [e.time_seconds for e in table.entries]
    assert times == [45.0, 15.0]  # 45s survival > 15s survival


def test_non_qualifying_run_not_inserted(tmp_path):
    # Fill with 10 Dead runs (10s-100s survival). Sorted descending,
    # worst is 10s (shortest survival).
    runs = [(float(i * 10), "Dead") for i in range(10, 0, -1)]
    table = _make_table(tmp_path / "hs.json", runs)
    assert len(table.entries) == 10
    # A 5s Dead run has shorter survival than all 10 — doesn't qualify.
    assert table.qualifies(5.0, "Dead") is False
    assert table.add(5.0, result="Dead") is None
    assert len(table.entries) == 10


def test_tie_at_last_place_does_not_qualify(tmp_path):
    runs = [(float(i * 10), "Dead") for i in range(10, 0, -1)]
    table = _make_table(tmp_path / "hs.json", runs)
    # Sorted descending: last place is 10s. A 10s Dead is a tie — doesn't qualify.
    assert table.qualifies(10.0, "Dead") is False


def test_trimmed_to_ten_entries(tmp_path):
    runs = [(float(i * 10), "Dead") for i in range(10, 0, -1)]
    table = _make_table(tmp_path / "hs.json", runs)
    assert len(table.entries) == 10
    # Add a fast Finished run.
    rank = table.add(5.0, result="Finished", timestamp=999.0)
    assert rank == 0
    assert len(table.entries) == settings.HIGHSCORE_MAX == 10
    # The shortest survival (10s) was dropped; last remaining Dead is 20s.
    assert table.entries[-1].time_seconds == 20.0


def test_multiple_finished_sorted_by_time(tmp_path):
    table = _make_table(
        tmp_path / "hs.json",
        [(50.0, "Finished"), (30.0, "Finished"), (40.0, "Finished")],
    )
    times = [e.time_seconds for e in table.entries]
    assert times == [30.0, 40.0, 50.0]


# ---------------------------------------------------------------------- #
# Persistence
# ---------------------------------------------------------------------- #


def test_persistence_survives_restart(tmp_path):
    path = tmp_path / "hs.json"
    table = _make_table(path, [(30.0, "Dead"), (10.0, "Dead"), (20.0, "Dead")])
    fresh = HighScoreTable.load(str(path))
    times = [e.time_seconds for e in fresh.entries]
    # Dead entries sorted descending (longest survival first).
    assert times == [30.0, 20.0, 10.0]


def test_missing_file_loads_empty(tmp_path):
    table = HighScoreTable.load(str(tmp_path / "nope.json"))
    assert table.entries == []
    assert table.qualifies(1.0) is True


def test_corrupted_json_loads_empty(tmp_path):
    path = tmp_path / "hs.json"
    path.write_text("{ this is not valid json !!!", encoding="utf-8")
    table = HighScoreTable.load(str(path))
    assert table.entries == []


def test_wrong_shape_loads_empty_or_filters(tmp_path):
    path = tmp_path / "hs.json"
    # A valid new-format entry survives a bogus sibling; an entry missing
    # its result is rejected.
    path.write_text(
        json.dumps(["bogus", {"time": 7.0, "result": "Dead", "timestamp": 1.0}, {"time": 8.0}]),
        encoding="utf-8",
    )
    table = HighScoreTable.load(str(path))
    assert [e.time_seconds for e in table.entries] == [7.0]

    path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    assert HighScoreTable.load(str(path)).entries == []


def test_old_score_schema_not_migrated(tmp_path):
    """Old score-based entries are silently discarded — no migration."""
    path = tmp_path / "hs.json"
    path.write_text(
        json.dumps([{"score": 42, "timestamp": 1.0}, {"score": 99, "timestamp": 2.0}]),
        encoding="utf-8",
    )
    table = HighScoreTable.load(str(path))
    assert table.entries == []  # old schema ignored


def test_unwritable_location_degrades_gracefully(tmp_path):
    table = HighScoreTable.load(str(tmp_path / "missing" / "hs.json"))
    rank = table.add(10.0, result="Dead", timestamp=1.0)
    assert rank == 0
    assert [e.time_seconds for e in table.entries] == [10.0]


def test_fresh_load_sees_nothing_after_failed_write(tmp_path):
    path = tmp_path / "missing" / "hs.json"
    table = HighScoreTable.load(str(path))
    table.add(10.0, result="Dead", timestamp=1.0)
    assert HighScoreTable.load(str(path)).entries == []


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
    assert not hasattr(game.main_menu, "highscores_rect")


def test_high_scores_not_reachable_from_game_over(game):
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
    game._update_and_draw((0, 0))
    assert game.state == "high_scores"


# ---------------------------------------------------------------------- #
# End-to-end: recording on game over
# ---------------------------------------------------------------------- #


def _die_after_scoring(game, score):
    """Simulate a run that scored some points, then the player dies."""
    start_game(game)
    game.score = score
    game.player.health = 1
    assert game.player.take_hit() is True
    assert game.player.dead
    pump(game)
    assert game.state == "game_over"


def test_dead_entry_recorded_on_game_over(game):
    _die_after_scoring(game, 42)
    entries = game.high_scores.entries
    assert len(entries) == 1
    assert entries[0].result == "Dead"
    assert game.last_run_rank == 0

    # Persisted: a fresh loader reading the same file sees the entry.
    fresh = HighScoreTable.load(game.high_scores.path)
    assert len(fresh.entries) == 1
    assert fresh.entries[0].result == "Dead"


def test_non_qualifying_run_not_recorded(game):
    # Pre-fill with 10 Dead runs (1-10 seconds survival).
    for i in range(10):
        game.high_scores.add(float(i + 1), result="Dead", timestamp=float(i))
    assert len(game.high_scores.entries) == 10

    # Set the run timer to a very short value (0.5s) — shorter survival
    # than the worst entry (1s) — so it doesn't qualify.
    start_game(game)
    game.run_timer = 0.5
    game.player.health = 1
    assert game.player.take_hit() is True
    assert game.player.dead
    pump(game)
    assert game.state == "game_over"

    assert game.last_run_rank is None
    assert len(game.high_scores.entries) == 10


def test_qualifying_run_highlighted_on_high_scores_screen(game):
    _die_after_scoring(game, 42)
    game._handle_mouse_click(game.game_over_menu.quit_rect.center)
    pump_fade(game)
    assert game.state == "menu"
    _enter_high_scores(game)
    assert game.last_run_rank == 0
    game._update_and_draw((0, 0))


def test_entry_recorded_before_restart_resets(game):
    _die_after_scoring(game, 7)
    game._handle_mouse_click(game.game_over_menu.restart_rect.center)
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
    assert game.score == 0
    assert game.last_run_rank is None
    assert len(game.high_scores.entries) == 1
    assert game.high_scores.entries[0].result == "Dead"


# ---------------------------------------------------------------------- #
# Menu banner assets
# ---------------------------------------------------------------------- #


def test_menu_banner_images_load_and_preserve_aspect_ratio(game):
    sw, sh = game.assets.score_img.get_size()
    assert sw <= settings.SCORE_IMG_SIZE[0] and sh <= settings.SCORE_IMG_SIZE[1]
    assert abs(sw / sh - 1489 / 382) < 0.03

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
    assert surf.get_size() == settings.SCORE_IMG_SIZE
