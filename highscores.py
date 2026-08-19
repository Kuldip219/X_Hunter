"""Persistent top-N time-based leaderboard.

Runs are stored in a small JSON file (settings.HIGHSCORE_FILE) so they
survive restarts.  Every read/write is defensive: a missing file,
corrupted JSON, or unwritable location simply means "no entries yet" or a
silently-dropped write (logged at warning level) — the leaderboard never
crashes the game.

Entry = {"time": float_seconds, "result": "Finished"|"Dead", "timestamp": float}
Sorting: "Finished" entries rank above "Dead" entries as a group; within
each group, sort by time ascending (shortest/best first — longer survival
before dying ranks better within the Dead group).  Top 10 entries kept.

The old score-based schema is not migrated — if an existing highscores.json
from the old format is found, it is silently replaced with a fresh table
(the old entries are not compatible with the new schema).
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
class RunEntry:
    """One leaderboard row: the run's time and result."""

    time_seconds: float
    result: str  # "Finished" or "Dead"
    timestamp: float  # wall-clock time the entry was recorded


def _sort_key(entry: RunEntry) -> tuple[int, float]:
    """"Finished" (0) ranks above "Dead" (1); within each group, shorter
    time ranks first (ascending)."""
    result_penalty = 0 if entry.result == "Finished" else 1
    return (result_penalty, entry.time_seconds)


class HighScoreTable:
    """An in-memory top-N run list with JSON persistence behind it."""

    def __init__(self, entries: list[RunEntry], path: str) -> None:
        self._entries = list(entries)
        self.path = path

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #

    @classmethod
    def load(cls, path: Optional[str] = None) -> "HighScoreTable":
        """Load entries from `path`, degrading to an empty table on any
        error (missing file, corrupted JSON, wrong schema).  Never raises.

        The old score-based schema is not compatible — if detected, the
        file is treated as empty (will be overwritten on the next save)."""
        if path is None:
            path = settings.HIGHSCORE_FILE
        entries: list[RunEntry] = []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if isinstance(raw, list):
                for item in raw:
                    if not isinstance(item, dict):
                        continue
                    t = item.get("time")
                    r = item.get("result")
                    ts = item.get("timestamp")
                    # Reject old score-based entries (they have "score" not "time").
                    if "score" in item and "time" not in item:
                        continue
                    if (
                        isinstance(t, (int, float))
                        and isinstance(r, str)
                        and r in ("Finished", "Dead")
                        and isinstance(ts, (int, float))
                    ):
                        entries.append(
                            RunEntry(time_seconds=float(t), result=r, timestamp=float(ts))
                        )
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("[highscores] could not load %s (%s); starting empty", path, exc)
        entries.sort(key=_sort_key)
        return cls(entries[: settings.HIGHSCORE_MAX], path)

    @property
    def entries(self) -> list[RunEntry]:
        """The current top-N entries, sorted best-first (a copy)."""
        return list(self._entries)

    # ------------------------------------------------------------------ #
    # Insertion
    # ------------------------------------------------------------------ #

    def qualifies(self, time_seconds: float, result: str = "Finished") -> bool:
        """A run qualifies when the table is not full, or when the entry
        would rank above the current worst entry.  Ties at the 10th place
        do not qualify (same as before)."""
        if time_seconds < 0:
            return False
        if len(self._entries) < settings.HIGHSCORE_MAX:
            return True
        worst = self._entries[-1]
        candidate = _sort_key(RunEntry(time_seconds, result, 0))
        return candidate < _sort_key(worst)

    def add(
        self,
        time_seconds: float,
        result: str,
        timestamp: Optional[float] = None,
    ) -> Optional[int]:
        """Record a run if it qualifies, persist immediately, and return its
        new rank (0-based index), or None if it did not qualify."""
        if not self.qualifies(time_seconds, result):
            return None
        entry = RunEntry(
            time_seconds=time_seconds,
            result=result,
            timestamp=timestamp if timestamp is not None else time.time(),
        )
        self._entries.append(entry)
        self._entries.sort(key=_sort_key)
        self._entries = self._entries[: settings.HIGHSCORE_MAX]
        self.save()
        return self._entries.index(entry)

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def save(self) -> None:
        """Write the current top-N to disk, atomically (temp file + rename).
        Failures are logged and otherwise silent."""
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(
                    [
                        {"time": e.time_seconds, "result": e.result, "timestamp": e.timestamp}
                        for e in self._entries
                    ],
                    fh,
                    indent=2,
                )
            os.replace(tmp, self.path)
        except (OSError, TypeError, ValueError) as exc:
            logger.warning(
                "[highscores] could not write %s (%s); entry kept in memory only",
                self.path,
                exc,
            )
