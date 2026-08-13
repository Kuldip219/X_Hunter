# 🚀 X Hunter — Project Audit

**Audit date:** 2026-08-13
**Auditor:** Buffy (AI coding agent, on handover from the original author)

---

## 1. Project Overview

**X Hunter** is a 2D arcade-style space shooter. The player controls a ship at the bottom of the screen, dodges and destroys falling enemy ships, and survives as long as possible to rack up score. The game has a main menu, pause menu, game-over menu, and a placeholder options screen, with screen-shake, damage-flash, explosion, and fade-transition effects.

The codebase was recently refactored from a single script into clean, module-per-class files. The refactor is documented as intentionally preserving several quirks of the original code (marked with `NOTE:` comments) so behavior stayed identical.

---

## 2. Tech Stack & Frameworks

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.12.3 |
| Game framework | pygame | 2.6.1 (SDL 2.28.4) |
| Packaging | PyInstaller | Spec file `X Hunter.spec` (Windows .exe) |
| Version control | git | Single branch `main` |
| Assets | PNG sprites, TTF fonts (Pixeltype, Nabla) | — |
| Tests | **None** | — |

**Verified environment:** `python --version` → 3.12.3, `import pygame` → 2.6.1. The game boots and runs headless without errors (smoke-tested below).

---

## 3. How Much Work Has Been Done

### 3.1 Codebase size
- **11 Python modules, 920 lines total**, all in the project root:

| File | Role |
|------|------|
| `main.py` | Entry point |
| `game.py` | `Game` class: state machine, main loop, event handling, collision |
| `settings.py` | Every constant in one place (safe to import anywhere) |
| `assets.py` | Central asset loader (images, fonts, scaling) |
| `player.py` | Player movement, clamping, health, shooting, death |
| `enemy.py` | Enemy spawn/respawn, movement, collision helpers |
| `bullet.py` | Bullet movement + off-screen detection |
| `explosion.py` | Frame-based explosion animation |
| `menus.py` | Main / pause / game-over menus + options screen |
| `ui.py` | Screen shake, damage flash, fade transition, HUD |
| `resource_path.py` | Path resolution for PyInstaller frozen mode |

### 3.2 Features implemented (all verified working)
- ✅ Main menu with title + Play / Options / Exit buttons, hover nudge effect
- ✅ Player movement (← →), clamped to screen
- ✅ Shooting (Space), bullets despawn off-screen
- ✅ Enemy spawning (initial wave + respawns when killed or off-screen)
- ✅ Player–enemy collision → damage + screen shake + red flash
- ✅ Bullet–enemy collision → enemy respawn, score +1, explosion animation
- ✅ Health system: 5 HP with 6-frame health-bar images (0–5)
- ✅ Player death animation → game-over screen
- ✅ Pause menu (ESC), resume, quit-to-menu
- ✅ Game-over menu: restart / quit-to-menu
- ✅ Options screen (placeholder: "under construction")
- ✅ Fade transitions between all states
- ✅ PyInstaller build (Windows exe) — `dist/X Hunter.zip` exists
- ✅ README with controls, screenshots, download instructions
- ✅ MIT License, `.gitattributes`

### 3.3 Verification performed during this audit
- **Smoke test:** 120 consecutive game frames simulated → no errors
- **Full state flow:** menu → play → death → game-over → restart → all transitions ran without crashing
- **Git state:** clean working tree (only untracked `.freebuff/`), 2 commits

---

## 4. Problems & Errors

### 🔴 High priority

#### H1 — Death bug: the player revives during the fade-out to "game over"
In `game.py`, `_draw_game()` sets `self.player.dead = False` the moment the death explosion finishes and starts the fade to `game_over`. But the state stays `"game"` for the ~17 frames the fade-out takes, so during that window:

- The player can be **moved with arrow keys** (hidden at `(-1000, -1000)`, then clamped back on-screen by `clamp_to_screen`).
- Enemies can still collide with the player; `take_hit()` runs again on a 0-HP player, which **re-triggers the death explosion and restarts the whole death animation**, delaying game over.
- Space still fires bullets from off-screen.

**Fix direction:** gate player input/collision on `dead` staying true until the state actually switches, or skip `_update_game` while the fade-out is in progress.

#### H2 — No invulnerability window after a hit
Every frame, *any* enemy overlapping the player deals 1 damage. With 5 enemies and 5 HP, death can come almost instantly, and two enemies touching in the same frame cost 2 HP at once. There's no i-frame period, no knockback, and no per-hit cooldown.

**Fix direction:** add a short invulnerability timer (and a blinking/flash effect) after each hit; ignore collisions while active.

#### H3 — Hitboxes don't match the sprites
| Entity | Rendered sprite | Collision rect |
|--------|----------------|----------------|
| Player | 65 × 80 | 50 × 50 |
| Enemy | 50 × 50 | 40 × 40 |
| Bullet | 10 × 20 | point (x, y) |

The collision boxes are smaller than what's drawn, so bullets visually pass through the edges of enemies, and the player takes damage from enemies that *look* like they're not touching. This is the most likely source of "unfair" gameplay feel. Either resize the rects to match the sprites, or keep small hitboxes deliberately and make it a documented design choice.

### 🟠 Medium priority

#### M1 — No tests at all
There is no test framework, no test files, and no CI. For a project being actively extended, this is the biggest long-term risk — every refactor (like the one just done) is unverifiable.

#### M2 — No `requirements.txt`
`pygame` version is not pinned anywhere, so the environment can't be reproduced. Add `requirements.txt` with `pygame==2.6.1` (or similar) and a note in the README.

#### M3 — Repo hygiene: 201 build artifacts committed
Of **252 tracked files, 201 are `build/`, `dist/`, and `__pycache__/*.pyc`** — committed in the initial commit. The `.gitignore` file is **empty**. The repo history is also a single giant initial commit (no record of the month of work).

**Fix direction:** populate `.gitignore` (`__pycache__/`, `build/`, `dist/`, `*.pyc`, `.freebuff/`), remove the artifacts from tracking, and squash/rewrite history if you want a clean repo before going public.

#### M4 — Options screen is a placeholder
`OptionsScreen` only renders "It's under construction" and "Press ESC to go back". If Options is advertised on the main menu, it should do *something* (volume, resolution, key rebinding).

#### M5 — No audio at all
No music, no sound effects (shooting, explosion, hit). For an arcade shooter this is a big missing piece of game feel.

#### M6 — No score persistence / high score
Score resets to 0 every run and is never saved. A simple high-score table (JSON file or `pygame`'s no-dependency file write) would add a lot of replay value.

#### M7 — No difficulty progression
Enemy count is fixed at 5 forever (`INITIAL_ENEMY_COUNT`), speed is constant, and score never affects spawn rate or speed. The game doesn't get harder, so runs feel flat.

#### M8 — Misleading type annotations in `assets.py`
`title_img: pygame.Surface = None` (and the other menu images) lie to type checkers — the fields are `Optional` at construction time but typed as non-optional. Either use `Optional[pygame.Surface]` or construct them in `__post_init__`.

### 🟡 Low priority / polish

- **L1 — Strict bullet collision bounds:** `Enemy.contains_point` uses strictly exclusive `>` / `<`, so a bullet landing exactly on the enemy's right/bottom edge misses. Cosmetic in practice, but `pygame.Rect.collidepoint` would be simpler and correct.
- **L2 — Duplicate blit in `GameOverMenu.draw`:** "GAME OVER" is blitted twice at the same position (a documented no-op preserved from the original). Harmless; can be removed.
- **L3 — Spawn margin inconsistency:** `spawn_initial` uses an X margin of 50 (player width) while `respawn` uses 40 (enemy width). Documented as intentionally preserved — worth cleaning up now that it's been flagged twice.
- **L4 — Frame-rate dependent movement:** all speeds are pixels-per-frame at a hardcoded 60 FPS. If FPS dips, the game slows down. Delta-time based movement would decouple this.
- **L5 — ESC during a fade race:** pressing ESC while a fade-out is mid-flight can override the fade's target state (e.g., ESC during the fade to pause re-targets the fade to "game"). Edge case, low impact.
- **L6 — Space must be tapped, not held:** shooting is bound to `KEYDOWN` only, so there's no auto-fire while holding Space. Many players expect hold-to-fire.
- **L7 — Fixed window, no icon, no resolution options:** 600×800 hardcoded; no window icon; the Options screen can't offer resolution changes until it's built.
- **L8 — Enemies can overlap:** no enemy–enemy collision; two ships can occupy the same spot and look glitchy.
- **L9 — `.gitattributes` vs CRLF:** source files use mixed line endings (some `\r\n` from Windows, some `\n`). Not a bug, but standardizing on LF avoids noisy diffs.

---

## 5. Recommended Priorities

1. **Fix H1 (death revival bug)** — it's a real gameplay bug that can loop the death animation.
2. **Add i-frames (H2)** and **align hitboxes (H3)** — biggest gameplay-feel wins.
3. **Write tests** (M1) — a simple test suite that drives `Game` headless (as the audit smoke test did) protects every future change.
4. **Clean up the repo** (M3) — `.gitignore` + drop build artifacts.
5. **Add `requirements.txt`** (M2).
6. Then pick a feature from the "next work" list: sound, high score, difficulty ramp, or a real Options screen.

---

## 6. Suggested Next Features (not started yet)

- Sound effects & background music
- High-score persistence (best score shown on menu + game over)
- Difficulty curve (enemy speed/spawn rate scale with score or time)
- Power-ups (spread shot, shield, extra life)
- Enemy shooting back
- Real options menu (volume, resolution, key bindings)
- Delta-time based movement
- Full-screen / resolution scaling
