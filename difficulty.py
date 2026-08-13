"""Difficulty ramp: a smooth, invisible difficulty curve.

Difficulty is a pure function of (score, elapsed_seconds) returning a
single value in [0, DIFFICULTY_MAX]. Both inputs matter throughout:
surviving long with little scoring, or scoring fast early on, each push
the ramp up on their own, and together they reach the ceiling. There is
no UI for this - the player simply feels the game get harder.
"""

from __future__ import annotations

import settings


class Difficulty:
    """Compute the current difficulty from score and survival time.

    The formula (see settings.py for the constants):

        time_term  = min(elapsed_seconds / DIFFICULTY_TIME_TO_FULL, 1)
        score_term = min(score / DIFFICULTY_SCORE_TO_FULL, 1)
        value      = min(TIME_WEIGHT*time_term + SCORE_WEIGHT*score_term, MAX)

    Weights sum to 1, so difficulty is always within [0, DIFFICULTY_MAX];
    neither input alone can reach the cap, keeping both meaningful.
    """

    def __init__(self) -> None:
        self.time_weight = settings.DIFFICULTY_TIME_WEIGHT
        self.score_weight = settings.DIFFICULTY_SCORE_WEIGHT
        self.time_to_full = settings.DIFFICULTY_TIME_TO_FULL
        self.score_to_full = settings.DIFFICULTY_SCORE_TO_FULL
        self.max_value = settings.DIFFICULTY_MAX

    def value(self, score: int, elapsed_seconds: float) -> float:
        """Difficulty in [0, DIFFICULTY_MAX] for the given run state."""
        time_term = min(elapsed_seconds / self.time_to_full, 1.0)
        score_term = min(score / self.score_to_full, 1.0)
        raw = self.time_weight * time_term + self.score_weight * score_term
        return min(raw, self.max_value)
