"""Shared pytest setup.

- Forces pygame's dummy video/audio drivers BEFORE anything imports pygame,
  so the Game class runs headless exactly like the audit's smoke tests.
- Adds the project root to sys.path and chdirs to it (assets are loaded
  relative to the cwd), so `pytest` works from any directory.
- Provides the `game` fixture: a fresh, fully-initialized Game per test.
"""

import os
import sys
from pathlib import Path

# Must be set before pygame is imported anywhere in the test process.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Assets are resolved relative to the cwd (resource_path -> abspath(".")),
# so always run tests from the project root regardless of invocation dir.
os.chdir(PROJECT_ROOT)

import pygame  # noqa: E402

import pytest  # noqa: E402

from game import Game  # noqa: E402


@pytest.fixture()
def game():
    """A fresh Game instance in the initial 'menu' state."""
    g = Game()
    yield g
    pygame.quit()
