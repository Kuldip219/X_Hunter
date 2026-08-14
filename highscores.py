"""Persistent top-N high-score leaderboard.

Scores are stored in a small JSON file (settings.HIGHSCORE_FILE, kept in
the game's working directory - the project root when run from source, the
folder the game is launched from when packaged) so they survive restarts.

Every read/write is defensive: a missing file, corrupted JSON, or an
unwritable location simply means "no scores yet" or a silently-dropped
write (logged at warning level) - the leaderboard never crashes the game.

File format: a JSON array of {"score": int, "timestamp": float} objects,
kept sorted by score descending (ties broken by earlier timestamp first)
and trimmed to the top settings.HIGHSCORE_MAX entries. A new score
qualifies when the table is not full yet, or when it is strictly higher
than the current last place (a tie at the 10th place does not qualify).
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import settings

logger = logging.getLogger(__name__)


@dataclass
class ScoreEntry:
    """One leaderboard row: the score value and when it was achieved."""

    score: int
    timestamp: float


def _sort_key(entry: ScoreEntry) -> tuple[int, float]:
    """Best score first; on ties the earlier timestamp ranks higher."""
    return (-entry.score, entry.timestamp)


class HighScoreTable:
    """An in-memory top-N score list with JSON persistence behind it."""

    def __init__(self, entries: list[ScoreEntry], path: str) -> None:
        self._scores = list(entries)
        self.path = path

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #

    @classmethod
    def load(cls, path: Optional[str] = None) -> "HighScoreTable":
        """Load scores from `path`, degrading to an empty table on any error
        (missing file, corrupted JSON, unexpected shape). Never raises.

        The path is read at call time (not as a baked-in default argument),
        so a caller/tests can point the table anywhere before loading."""
        if path is None:
            path = settings.HIGHSCORE_FILE
        entries: list[ScoreEntry] = []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if isinstance(raw, list):
                for item in raw:
                    if not isinstance(item, dict):
                        continue
                    score = item.get("score")
                    timestamp = item.get("timestamp")
                    if isinstance(score, int) and isinstance(timestamp, (int, float)):
                        entries.append(ScoreEntry(score=score, timestamp=float(timestamp)))
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("[highscores] could not load %s (%s); starting empty", path, exc)
        entries.sort(key=_sort_key)
        return cls(entries[: settings.HIGHSCORE_MAX], path)

    @property
    def scores(self) -> list[ScoreEntry]:
        """The current top-N scores, sorted best-first (a copy, so callers
        cannot mutate the table through it)."""
        return list(self._scores)

    # ------------------------------------------------------------------ #
    # Insertion
    # ------------------------------------------------------------------ #

    def qualifies(self, score: int) -> bool:
        """A score earns a slot when the table is not full yet, or when it is
        strictly higher than the current last (lowest) place. A tie at the
        10th place does not qualify."""
        if score < 0:
            return False
        if len(self._scores) < settings.HIGHSCORE_MAX:
            return True
        return score > self._scores[-1].score

    def add(self, score: int, timestamp: Optional[float] = None) -> Optional[int]:
        """Record a score if it qualifies, persist immediately, and return its
        new rank (0-based index into the sorted top-N), or None if it did not
        qualify. Persistence failures are logged and otherwise silent - the
        score still lives in memory for this session."""
        if not self.qualifies(score):
            return None
        entry = ScoreEntry(
            score=score,
            timestamp=timestamp if timestamp is not None else time.time(),
        )
        self._scores.append(entry)
        self._scores.sort(key=_sort_key)
        self._scores = self._scores[: settings.HIGHSCORE_MAX]
        self.save()
        return self._scores.index(entry)

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def save(self) -> None:
        """Write the current top-N to disk, atomically (temp file + rename).
        Failures (read-only location, missing directory, ...) are logged and
        otherwise silent - never fatal to the game."""
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(
                    [{"score": e.score, "timestamp": e.timestamp} for e in self._scores],
                    fh,
                    indent=2,
                )
            os.replace(tmp, self.path)
        except (OSError, TypeError, ValueError) as exc:
            logger.warning(
                "[highscores] could not write %s (%s); score kept in memory only",
                self.path,
                exc,
            )
