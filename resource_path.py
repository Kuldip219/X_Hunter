import os
import sys


def resource_path(relative_path):
    """Get absolute path to a read-only bundled resource.

    Frozen (PyInstaller): the bundle's extraction directory, so every asset
    shipped inside the executable is found no matter where it was launched
    from. From source: the working directory, as always.
    """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def user_data_path(filename):
    """Absolute path to a writable user-data file (settings, leaderboard).

    These files are written at runtime, so they must never live inside the
    bundle (which is read-only, and re-extracted to a fresh temp directory on
    every launch). In a frozen build they sit next to the executable, so a
    player's volumes, key bindings and leaderboard persist and belong to them,
    even when the game is launched from a shortcut whose "Start in" folder is
    somewhere else entirely (or from an elevated console, whose working
    directory is System32).

    From source the plain filename is returned unchanged: it resolves against
    the working directory exactly as before - the project root in normal use,
    and whatever path a caller or test points the store at.
    """
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(os.path.abspath(sys.executable)), filename)
    return filename