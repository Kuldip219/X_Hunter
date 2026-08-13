# 🕹 X Hunter — Work Audit & Progress Log

> **What this file is:** a complete record of every change made to the
> project during the AI-assisted collaboration: the original audit, all
> bug fixes, the test suite, dependency/repo hygiene work, and the
> current state of the repository. Generated: Aug 13, 2026.

---

## 1. Project snapshot

| | |
|---|---|
| **Game** | X Hunter — 2D arcade space shooter |
| **Language / runtime** | Python 3.12, **pygame 2.6.1** |
| **Packaging** | PyInstaller (`X Hunter.spec`) → Windows `.exe`, zipped in `dist/` |
| **Entry point** | `main.py` (`Game().run()`) |
| **Architecture** | `game.py` (state machine + main loop), `player.py`, `enemy.py`, `bullet.py`, `explosion.py`, `ui.py` (effects/HUD), `menus.py`, `assets.py`, `settings.py` (all constants), `resource_path.py` |
| **Source size** | 11 modules, ~980 lines |
| **Test suite** | 22 pytest tests, ~505 lines (`tests/`) |

State machine: `menu → game ⇄ pause → game_over → menu`, transitions driven
by a fade-to-black (`ui.FadeTransition`), ~17 frames per fade-out.

---

## 2. Original audit (initial findings)

The first audit (originally `AUDIT.md`) reviewed the freshly handed-over
project and found, in priority order:

1. **🔴 H1 — Death revival bug.** `_draw_game()` set `player.dead = False`
   as soon as the death explosion finished, but the state stayed `"game"`
   for the ~17-frame fade-out. During that window the player could move,
   fire, and be hit again — re-triggering the death animation and delaying
   game over.
2. **🔴 H2 — No invulnerability.** Every overlapping enemy dealt 1 damage
   per frame; several enemies could drain all 5 HP in one screenful.
3. **🔴 H3 — Hitboxes didn't match sprites.** Player 65×80 sprite vs 50×50
   rect, enemy 50×50 vs 40×40, bullet collisions were a single point —
   bullets visibly passed through sprite edges.
4. **🟠 Repo hygiene.** 201 of 252 tracked files were `build/`, `dist/`,
   and `__pycache__` artifacts; `.gitignore` rules were missing/broken.
5. **🟠 No tests, no `requirements.txt`** — changes were unverifiable and
   the environment was not reproducible.
6. **🟡 Polish gaps** — placeholder options screen, no audio, no
   high-score persistence, no difficulty ramp, tap-only shooting,
   frame-rate-dependent movement.

---

## 3. Work completed

### 3.1 H1 — Death-freeze fix ✅
**Bug:** player revived mid fade-out; death animation re-triggered.
**Fix:** `_update_game()` now early-returns while the player is dead
(input, collisions, bullets, enemies all frozen). `_draw_game()` starts
the fade to `game_over` exactly once (guarded by `not fade.fading_out`)
and never flips `dead` back to `False`. ESC/Space are gated on
`not self.player.dead`.
**Files:** `game.py`, `player.py`, `settings.py`.
**Verified:** headless smoke test — player immovable/unable-to-fire/
unhittable during the entire fade; state always reaches `game_over`.

### 3.2 H2 — Invulnerability window (i-frames) ✅
**Bug:** overlapping enemies drained multiple HP per frame.
**Fix:** `Player.take_hit()` returns a bool, starts a 60-frame i-frame
timer after a successful non-lethal hit, and the player blinks every 6
frames while invulnerable. Hit effects (shake/flash/knockback) fire only
when damage actually applies. The initial implementation still refused a
lethal hit during i-frames (see 3.7).
**Files:** `settings.py` (`PLAYER_INVULNERABLE_DURATION = 60`,
`PLAYER_BLINK_INTERVAL = 6`), `player.py`, `game.py`.
**Verified:** headless smoke test — single damage per overlap, no damage
during window, damage resumes after expiry, death unaffected.

### 3.3 H3 — Hitbox/sprite alignment ✅
**Bug:** collision rects smaller than rendered sprites.
**Fix:** collision rects now equal the sprite dimensions and share the
same top-left origin (no visual drift):

| Entity | Rect before | Rect after | Sprite |
|---|---|---|---|
| Player | 50×50 | **65×80** | 65×80 |
| Enemy | 40×40 | **50×50** | 50×50 |
| Bullet | point `(x, y)` | **10×20 `Rect`** | 10×20 |

`Enemy.contains_point()` (strict `>`/`<` checks) removed in favour of
`Rect.colliderect()`; edge-overlapping bullets now hit (the old L1 miss).
Unavoidable side effects: player clamp max X 550→535, enemy respawn range
0–550, bullet spawn now centered on the sprite.
**Files:** `settings.py`, `bullet.py`, `enemy.py`, `game.py`.
**Verified:** 17-check edge-collision smoke test + full re-run of the
death/i-frame suite.

### 3.4 Test suite (22 tests) ✅
Set up a real, repeatable pytest suite (no more throwaway scripts):
- **`tests/conftest.py`** — forces `SDL_VIDEODRIVER/SDL_AUDIODRIVER=dummy`
  before pygame imports (headless), pins project root, `game` fixture.
- **`tests/helpers.py`** — `KeyState`, frame pumping, state-entry helpers.
- **`test_state_flow.py` (3)** — menu → play → game_over → restart.
- **`test_player.py` (5)** — clamping at both edges, held-key movement.
- **`test_collisions.py` (5)** — bullet–enemy score/respawn/explosion,
  edge-overlap hits, player–enemy damage once per i-frame window.
- **`test_death_and_iframes.py` (4)** — H1 death-freeze regression guard,
  H2 killing-blow edge case, no i-frames on death.
- **`test_hitboxes.py` (5)** — rect dimensions vs sprite constants/images.

**Files:** `tests/` (7 files), `pytest.ini`.
**Verified:** `pytest` runs standalone from the project root; confirmed in
a fresh virtualenv.

### 3.5 Dependency manifests + README ✅
- `requirements.txt` → `pygame==2.6.1` (runtime).
- `requirements-dev.txt` → `-r requirements.txt` + `pytest==9.1.1` (dev).
- `Readme.md` — added a "Setup (run from source)" section
  (`pip install -r requirements-dev.txt` → `python main.py` / `pytest`).
**Verified:** fresh virtualenv install from the files followed by
`pytest` succeeds (22 tests run).

### 3.6 Repo hygiene ✅
- **Tracked files: 261 → 62.** Untracked 201 build artifacts (175 `dist/`,
  16 `build/`, 10 `__pycache__/`) plus the stray
  `.freebuff/smoke_test_hitboxes.py` via `git rm --cached` — index only,
  **nothing deleted from disk** (`dist/X Hunter.zip`, 31 MB, still present).
- **`.gitignore` rewritten cleanly:** `__pycache__/`, `*.pyc`, `build/`,
  `dist/`, `.freebuff/`, `venv/`, `.venv/`, `.pytest_cache/`.
  (Replaced an accumulated mess of duplicate rules and blanket
  `*.md`/`*.txt` ignores.)
- **History untouched** — no squashing/rewriting (the initial commit still
  contains the artifacts; purging it is a deliberate decision left to the
  project head).
- **Commits:** `0bc6a69` (.gitignore + untrack artifacts),
  `585d619` (dependency manifests + README + audit).

### 3.7 H2 completion — killing blow bypasses i-frames ✅
**Bug found by the test suite:** `take_hit()` checked
`if self.invulnerable: return False` *before* lethality, so a lethal hit
during i-frames was refused — reachable in real play (a 2→1 HP hit starts
the window; a touch during the blink should kill but didn't).
**Fix (uncommitted, in `player.py`):** order is now `dead-guard → lethal
check → invulnerability check`. A hit bringing HP to ≤0 always applies and
triggers death; i-frames only block non-lethal damage. A dead player can
no longer be re-hit even by a direct `take_hit()` call.
**Verified:** full suite **22/22 passing** + end-to-end game-loop
reproduction (2 HP → hit to 1 HP blinking → lethal touch → death).

### 3.8 Live preview pipeline (dev infra, untracked) 
- `.freebuff/preview_live.py` — runs the *real* `Game` headless with an
  autopilot (menu click → play → shoot → die → restart loop), streaming
  PNG frames.
- `.freebuff/preview/frame.html` — auto-refreshing frame viewer.
- `python -m http.server` on **port 8123** (no project default exists for
  a pygame app).
- `.freebuff/run.md` — reproduction/run doc for future threads.
- URL: `http://127.0.0.1:8123/frame.html`
- Pitfalls solved along the way: pygame `image.save()` writes TGA unless
  the temp filename ends in `.png`; repeated menu clicks reset the fade
  and lock the game on the menu (gate on `fade_idle`); Windows file-lock
  collisions during frame writes; the app kills the registered server pid
  at session teardown while the capture survives (re-register each turn).

---

## 4. Current repository state

```
585d619 Add dependency manifests, README setup instructions, and project audit
0bc6a69 Add .gitignore and stop tracking build artifacts
bd7f013 Add pytest config and game test suite
b2668a7 Align hitboxes to sprites; add smoke test
f54a4a3 Add player i-frames, blinking and death freeze
d6c3b9f Reorganize download and built with sections in README
a9e5b5b Initial commit
```

- **Tracked files:** 62 (11 source modules, 7 test files, 28 assets,
  4 fonts, 3 screenshots, config/docs).
- **Uncommitted changes:**
  - `player.py` — the 3.7 lethal-first `take_hit()` fix (ready to commit).
  - `AUDIT.md` — **deleted from the working tree** (not staged; status
    shows `D`). If that deletion was unintended, restore with
    `git checkout -- AUDIT.md`.
- **Test suite:** 22/22 passing in ~2.4 s, headless.
- **On disk but untracked (by design):** `build/` (15 MB), `dist/`
  (100 MB, includes `X Hunter.zip`), `__pycache__/`, `.freebuff/`,
  `.pytest_cache/`.

---

## 5. Known issues & suggested next steps

Already fixed: H1 (death revival), H2 (i-frames + killing blow), H3
(hitboxes), repo hygiene, test coverage, dependency pinning.

Still open (original polish list, untouched by design):
- **No audio** — zero sound effects or music.
- **Options screen is a placeholder** ("It's under construction").
- **No high-score persistence** — score resets on restart.
- **No difficulty ramp** — enemy speed/count are constant.
- **Tap-only shooting** — Space must be re-pressed; no hold-to-fire.
- **Frame-rate-dependent movement** — no fixed timestep; speeds assume
  60 FPS.
- **History contains 201 artifact files** in the initial commit — purging
  via squash/filter-branch is a deliberate, separate decision.

---

*Generated as part of the AI-assisted maintenance of X Hunter.*
