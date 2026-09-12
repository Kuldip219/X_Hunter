# X Hunter — Project Audit & Work Log

Status: **306 tests passing** · last updated September 11, 2026.

## 1. Project snapshot

- **Stack:** Python 3.12 + pygame 2.6.1 (SDL 2.28.4); PyInstaller for the Windows build.
- **Architecture:** a single `Game` class (`game.py`) owns state and runs the main loop;
  entities are plain classes (`player.py`, `enemy.py`, `bullet.py`, `gunner.py`,
  `enemy_bullet.py`, `explosion.py`, `powerup.py`);
  `menus.py`/`ui.py` handle UI and screen effects; `assets.py` loads sprites/fonts;
  `settings.py` holds every constant; `audio.py` wraps the mixer; `difficulty.py`
  computes the invisible difficulty ramp; `highscores.py` manages the time-based
  leaderboard; `settings_store.py` persists user volume settings **and key
  bindings**; `background.py` provides two-layer parallax scrolling and a static
  UI backdrop.
- **Input:** every binding comes from `settings.DEFAULT_KEY_BINDINGS` and is
  loaded/persisted through `UserSettings` (`settings_store.py`); the Controls
  screen's EDIT mode rebinds them in-game with conflict-safe swaps.
- **State machine:** `menu → level_intro → game ⇄ pause → game_over`, with dedicated
  states for `options`, `high_scores`, `controls`, and `level_finished` off the menu.
  Level transitions route through `level_intro` (black screen + fade text) before
  resuming gameplay. On level completion, a ship-exit animation plays within the
  `"game"` state before fading to `level_finished` ("Level Finished" text), then
  into the next level's `level_intro`. All state changes driven by `FadeTransition`
  (fade-out → state switch → fade-in).
- **Levels:** two-level structure — Level 1 (falling enemies, score target 100) and
  Level 2 (gunner enemies + enemy bullets, score target 150). Run timer tracks total
  time across both levels (pauses during menus/pause). Checkpoint restart on death:
  Level 1 death → full reset; Level 2 death → restart at Level 2, timer preserved.
- **Code size:** ~3,800 source lines across root modules; **113 tracked files**
  (all source/assets/tests — build artifacts are untracked and ignored).
- **Entry point:** `python main.py` (headless-safe: `SDL_VIDEODRIVER=dummy`).

## 2. Original findings (first audit, `AUDIT.md`)

| ID | Finding |
|----|---------|
| **H1** | Death-revival bug: during the game-over fade-out the player could move/fire/re-collide, re-triggering the death animation and delaying game over. |
| **H2** | No invulnerability window: overlapping enemies drained HP every frame, multiple enemies cost multiple HP in one frame. |
| **H3** | Hitboxes smaller than sprites: bullets visually passed through enemy edges; a bullet landing exactly on an edge was missed (point-based collision). |
| — | Repo hygiene: 201 build/dist/`__pycache__` artifacts committed; `.gitignore` broken (over-broad `*.md`/`*.txt`/`*.log` rules hid real files). |
| — | No test framework; every change was verified with throwaway headless smoke scripts. |

## 3. Work completed (chronological)

### 3.1 H1 — death-freeze fix (`ef34719`)
`_update_game()` now early-returns while the player is dead, so input, firing, and
collisions stay frozen until the state machine leaves `"game"`. The player never
flips back to alive during the fade-out.

### 3.2 H3 — hitbox alignment (`5e7a76f`)
Collision rects resized to match the rendered sprites, all drawn from the same
top-left origin (no drift):

| Entity | Collision rect before | After | Sprite |
|--------|----------------------|-------|--------|
| Player | 50×50 | **65×80** | 65×80 |
| Enemy | 40×40 | **50×50** | 50×50 |
| Bullet | single point | **10×20 `pygame.Rect`** | 10×20 |

Bullet–enemy collision switched from `Enemy.contains_point` (strict `>`/`<`) to
`Rect.colliderect`, fixing the edge-overlap miss (L1).

### 3.3 Test suite (`7eaedd2`)
`pytest` + `tests/` with `conftest.py` forcing dummy SDL drivers and a fresh `Game`
fixture. 22 tests covering state flow, movement clamping, bullet/enemy and
player/enemy collisions, the i-frame window, the death sequence (H1), the
killing-blow edge case (H2), and hitbox dimensions (H3).

### 3.4 Dependencies + README (`6011cea`)
`requirements.txt` (runtime: `pygame==2.6.1`), `requirements-dev.txt`
(`-r requirements.txt` + `pytest==9.1.1`), and a README Setup section.

### 3.5 Repo hygiene (`83a6409`)
Clean `.gitignore` (`__pycache__/`, `*.pyc`, `build/`, `dist/`, `.freebuff/`,
`venv/`, `.venv/`, `.pytest_cache/`); 201 build/dist/bytecode artifacts untracked
via `git rm --cached` (kept on disk — the built `dist/X Hunter.zip` survives).
Tracked files: **261 → 62**.

### 3.6 H2 completion — lethal hits bypass i-frames (`718c540`)
`Player.take_hit()` reordered to **dead-guard → lethal check → invulnerability
check**: a hit that would bring HP to 0 always applies and kills, even mid-window;
only non-lethal hits are blocked during i-frames. Found by the test suite (one
failing test surfaced the bug; fixed only after approval).

### 3.7 Audit docs (`9016f9a`)
`AUDIT.md` (original findings) and `PROGRESS.md` (this document). `AUDIT.md` was
later folded into this file and deleted (`8413966`); §2 preserves its original
findings.

### 3.8 Audio (`7c1de0f`) — 33 tests
- **Assets** (`Assets/audio/`, all CC0): 6 Kenney.nl SFX (shoot, hit, explosion,
  player death, menu hover, menu click) + an original public-domain 14.55 s
  chiptune loop (`gameplay_music.wav`, generated by
  `Assets/audio/generate_gameplay_music.py`). Attribution in `SOURCES.md` +
  `LICENSE-kenney-CC0.txt`.
- **`audio.py` `AudioManager`**: mixer/SFX/music loading, all wrapped in
  try/except — audio failure degrades to silent no-ops, never crashes.
- Wired: shoot (fire), hit (non-lethal), explosion (enemy destroyed), player
  death + music fade, menu hover/click; music plays on `game`, pauses on `pause`,
  stops on `menu`/`game_over`.
- **Mute:** `M` toggles all audio globally; a small "MUTED" label shows top-right.

### 3.9 Hold-to-fire (`8d2a989`) — 37 tests
`PLAYER_FIRE_COOLDOWN = 12` frames (5 shots/s). Firing moved from KEYDOWN-only
into `_update_game`: Space held + cooldown expired → fire. H1 gating intact
(firing blocked while dead, enforced at the update-loop level).

### 3.10 Difficulty ramp (`71cdcba`) — 47 tests
`difficulty.py`: `difficulty = min(0.5·min(t/180,1) + 0.5·min(score/50,1), 1.0)`.
Both survival time and score matter (each alone reaches only its weighted share);
capped at 1.0. Enemy speed scales `5 + 4·d` capped at 9 px/frame; enemy count
scales `5 + 5·d` capped at 10. Invisible (no UI). Resets to baseline on restart;
frozen while dead (H1).

### 3.11 Delta-time movement — **54 tests** (details in §4)

### 3.12 Fixed-timestep accumulator (`79c6fc9`) — **62 tests** (details in §4.7)

## 4. Delta-time conversion (latest work)

### 4.1 The problem
All movement was px/frame, implicitly assuming a fixed frame rate — any frame
drop or hardware variance changed actual game speed.

### 4.2 dt plumbing
`Game.run()` computes `dt = clock.tick(FPS)/1000.0` each frame and passes it down:
`_update_and_draw(mouse_pos, dt)` → `_update_game(keys, dt)` →
`Player.handle_input/dat updates`, `Enemy.update(dt)`, `Bullet.update(dt)`.
Update methods default to `dt = 1/FPS`, so test callers and the preview autopilot
get exactly the old per-frame behavior.

**Clamp: `MAX_FRAME_DT = 0.05` s** — 3 frames at 60 FPS, but also a full frame at
20 FPS. Caps the worst-case jump after a lag spike/tab switch/breakpoint pause
(no teleporting, no bullet bursts) without throttling low frame rates. Applied in
`run()` and defensively inside `_update_game()`.

### 4.3 Constants converted (old px/frame → new px/s)

| Constant | Old | New |
|----------|-----|-----|
| `PLAYER_SPEED` → `PLAYER_SPEED_PER_SEC` | 5 | 300 |
| `ENEMY_SPEED` → `ENEMY_SPEED_PER_SEC` | 5 | 300 |
| `ENEMY_SPEED_GAIN` → `ENEMY_SPEED_GAIN_PER_SEC` | 4 | 240 |
| `ENEMY_MAX_SPEED` → `ENEMY_MAX_SPEED_PER_SEC` | 9 | 540 |
| `BULLET_SPEED` → `BULLET_SPEED_PER_SEC` | 10 | 600 |

All are `old × 60`, so gameplay feel at the target FPS is unchanged (verified by
a regression test: one `Enemy.update(1/60)` still lands at exactly `y == 5`).

### 4.4 Timers checked
- **Hold-to-fire cooldown** — was frame-counted → `PLAYER_FIRE_COOLDOWN_SECONDS = 0.2`
  (still 5 shots/s; dt-accumulated).
- **i-frames** — was frame-counted (60) → `PLAYER_INVULNERABLE_DURATION_SECONDS = 1.0`;
  blink interval → `PLAYER_BLINK_INTERVAL_SECONDS = 0.1`. Converted for the same
  frame-rate independence; tested behavior at 60 FPS preserved exactly.
- **Difficulty clock** — already real-time (`get_ticks()`); untouched.
- **Spawn logic** — no spawn-interval timers exist (respawns are instant);
  nothing to convert.
- **Left frame-based deliberately:** explosion animation frame delays and the
  `FadeTransition` — visual animation / the H1 mechanism itself.
- **Float hygiene:** timers snap residuals ≤1e-9 s to exactly 0.0, so windows and
  cooldowns expire at precisely the same frame as before at any frame rate.

### 4.5 Verified behavior preserved
H1 death-freeze gating, i-frames, and hitbox logic unchanged — only displacement
scaling changed. All 47 prior tests pass unmodified in behavior (constant-name
updates only).

### 4.6 Delta-time tests (`tests/test_delta_time.py`, 7 new)
- Player/enemy/bullet cover the same distance per simulated second at 30 vs 60 fps.
- dt clamp caps movement after a 1 s spike (single + repeated).
- px/s constants == old px/frame × FPS; one 60 FPS frame reproduces old motion
  (5/5/10 px) exactly.
- Fire cadence: 5 shots per held second at both 30 and 60 fps (no burst-fire).
- i-frame window expires on real time across mixed frame rates.

### 4.7 Fixed-timestep accumulator (latest work)

**The problem:** after the dt conversion, *distance per step* is correct, but the
simulation still ran once per rendered frame — at very low/high display rates the
step size still varied (collision tunneling at low fps, numerical drift at high
fps).

**The fix — `FIXED_DT = 1.0/60.0` (60 Hz) accumulator in `Game`:**

- `Game.run()` computes raw dt from `clock.tick()`, banks `min(raw_dt, MAX_FRAME_DT)`
  into `self.accumulator`, and drains it in constant `FIXED_DT` steps via
  `_advance_simulation(raw_dt, keys)`. Each full `FIXED_DT` runs one
  `_update_game(keys, FIXED_DT)`; a rendered frame can therefore run 0, 1, or
  several simulation steps.
- **MAX_FRAME_DT interaction:** the clamp now happens *before* time enters the
  accumulator, so a huge stall banks at most 0.05 s → exactly 3 catch-up steps
  (verified), never a spiral of death.
- **Rendering decoupled:** `_draw_frame()` renders once per rendered frame from
  current entity state; no interpolation. Input polling, events, and state
  transitions stay per-rendered-frame — only the simulation step is fixed-rate.
- **No banking outside gameplay:** in menu/pause/game_over the accumulator is
  cleared, so paused time never fast-forwards gameplay on resume. (While the
  player is dead but state is still "game", `_update_game`'s H1 early-return
  makes the steps no-ops.)
- **`_update_and_draw`** (the direct-drive entry the tests/preview use) still
  simulates exactly one 60 Hz step per call, so it reproduces the accumulator
  at a perfect 60 Hz render rate.

**Verified unaffected:** H1 death-freeze, i-frames, hitbox logic, hold-to-fire
cadence, and the difficulty ramp all pass unchanged — they were already dt-based,
so stepping at constant FIXED_DT falls out for free (all 54 prior tests green,
behavior identical). Difficulty elapsed time uses real `get_ticks()`, which now
matches accumulator time exactly.

**Tests (`tests/test_fixed_timestep.py`, 8 new):** choppy real frame times
(alternating 1/30 and 1/144) produce the same simulated seconds/displacement as
uniform 60 Hz; a 1 s lag spike banks at most 3 steps (and repeated spikes stay
capped); one rendered frame runs 2 steps from 2.5×FIXED_DT banked; a sub-step
frame runs 0 steps (render-only); no banking in menu; `_update_and_draw` still
simulates exactly one step; and a real `run()` loop smoke test.

### 3.13 High-score leaderboard (`d7162b3`) — **83 tests** (details in §7)

Persistent top-10 leaderboard with a dedicated `high_scores` state (see §7).

### 3.14 High-scores navigation: entry moved to Options (committed) — **86 tests**

Per project-head direction, the standalone HIGH SCORES buttons were removed
from the main menu and the game-over screen; the leaderboard is now reached
only via the Options screen (which previously existed as a placeholder). The
`score.png` banner (1489×382) is the Options entry button and `back.png`
(1491×354) is the high-scores screen's BACK button; both load through the
standard `assets.py` path, scale to fit the 250×80 footprint preserving aspect
ratio, and fall back to font-rendered buttons if missing (non-fatal). BACK
and ESC on the high-scores screen return to Options (one level up), matching
ESC-from-Options → main menu. Leaderboard logic/storage untouched.

### 3.15 Menu button spacing restored (committed)

Removing the HIGH SCORES button (§3.14) left stale y-positions: the game-over
QUIT button sat at 490 (a leftover from when a third button lived at 410),
and the main menu had 90px/180px gaps where a 100px rhythm used to be. Both
menus restored to the original uniform 100px center-to-center spacing: game
over restart 330→350 / quit 490→450, main play 290→300 / options 380→400 /
exit 560→500 (pause was already 350/450). Pure layout change, no logic or
navigation touched.

### 3.16 Options screen: volume sliders + controls reference (`20a071e`) — **110 tests**

Replaced the options placeholder with a real screen: two live volume sliders
(music / SFX, 0-100%), a read-only controls reference (sourced from the actual
bindings: LEFT/RIGHT, SPACE hold-to-fire, ESC pause/back, M mute, RESTART
button), the HIGH SCORES banner, and the ESC hint. New `settings_store.py`
(`UserSettings`, mirroring `highscores.py`'s defensive load + atomic save)
persists `music_volume`/`sfx_volume` to `settings.json` (gitignored); defaults
are the existing out-of-the-box volumes (0.45 / 0.7). Sliders are draggable
(mouse-down grabs, motion follows, release persists once); changes apply live
via new `AudioManager.set_music_volume` / `set_sfx_volume` (both live in
pygame — music via `mixer.music.set_volume`, SFX via `Sound.set_volume` on
every loaded sound). Volumes are applied on launch before any audio plays, and
mute (M) stays independent of the slider values (unmuting restores exactly
where they were). `game.py` gained MOUSEMOTION/MOUSEBUTTONUP handling for
slider drags in the options state.

### 3.17 Options BACK button (`e3e8e83`) — **112 tests**

Added the shared `back.png` banner (same `_load_menu_banner` helper the
high-scores screen already uses) to the Options screen at center y=765, below
the HIGH SCORES banner (moved 700→680 to make room); the now-redundant
"Press ESC to go back" hint text was removed (the high-scores screen has no
such hint either). Clicking BACK triggers exactly the same fade to the main
menu as ESC — additive, ESC unchanged, and BACK is hover-SFX tracked like the
other buttons.

### 3.18 Options screen spacing system (`f7f033f`) — **112 tests**

Audited the incremental layout: control rows sat ~1px apart, the CONTROLS
heading touched row 1, the last row OVERLAPPED the HIGH SCORES banner by
12px, and the bottom margin was 5px. Established a two-value spacing system
in settings.py — `OPTIONS_SECTION_GAP = 50` (between unrelated sections) and
`OPTIONS_ITEM_GAP = 24` (between related rows) — and recomputed every
Options y-position top-down from measured text heights (no magic numbers,
so the rhythm can't drift when an element is added). Six full-width control
rows cannot fit 600×800 with breathing room, so the controls reference
became a 2×3 grid (two bindings per row: Move/Fire, Pause/Mute,
Back/Restart) with per-cell action/key anchor columns
(`OPTIONS_GRID_X`). Pure repositioning — no element, font, asset, or logic
changed; all 112 tests pass unmodified (none hardcode coordinates).

### 3.19 Dedicated controls screen + three-button Options (`fb4fd92`) — **123 tests**

Moved the keybind reference off Options onto a new `controls` state
(following the high_scores pattern: FadeTransition, reachable only via
Options, BACK/ESC return to Options). The ControlsScreen now has a full
screen, so the list went back to one binding per row with generous
`CONTROLS_ROW_GAP = 60` spacing (`CONTROLS_ACTION_X`/`CONTROLS_KEY_X`
anchors), same source-of-truth `settings.CONTROLS`. The Options bottom
became three evenly-spaced image buttons — HIGH SCORES (score.png),
CONTROLS (controls.png, new 1168×273 asset loaded via the same
`_load_menu_banner` helper with font fallback), BACK (back.png) — each
`OPTIONS_ITEM_GAP = 24` apart (equal gaps), sitting in the space the
controls list vacated. Slider logic, persistence, and high_scores logic
untouched.

### 3.20 Power-up system (`c1252f1`) + health-regen pickup (`ab5dba3`) — **140 tests**

**Power-ups (committed in `c1252f1`):** shield, rapid fire, and (initially)
extra life. They only drop from destroyed enemies (12% per kill,
`POWERUP_DROP_CHANCE`, uniform kind), drift down at 120 px/s, auto-collect
on contact with the player (no keypress), and despawn after an 8 s
real-time lifetime. All timers are dt-based under the fixed-timestep
simulation. Sprites: `shield_gold.png` + `bolt_gold.png` from Kenney
"Space Shooter Redux" (CC0); pickup SFX `powerUp2.ogg` from Kenney
"Digital Audio" (CC0, same pack as the existing SFX). Attribution in
`Assets/SOURCES.md` + `Assets/LICENSE-kenney-CC0.txt`.

- **Shield** (`POWERUP_SHIELD_DURATION_SECONDS = 8.0`): full invincibility
  via a separate `shield_timer` on the player. Unlike the post-hit i-frame
  window (H2), the shield blocks even lethal hits — checked in `take_hit()`
  before the lethality check. Rendered as a translucent cyan aura around
  the ship + a `SHIELD X.Xs` HUD countdown.
- **Rapid fire** (`POWERUP_RAPID_FIRE_DURATION_SECONDS = 8.0`): the
  hold-to-fire cooldown is multiplied by `RAPID_FIRE_COOLDOWN_MULTIPLIER =
  0.3` (0.2 s → 0.06 s, ~16 shots/s) via `Player.fire_cooldown_value()`;
  collecting another while active REFRESHES the window, never stacks.
  Yellow `RAPID FIRE X.Xs` HUD countdown.
- **Health-regen pickup (this change, replaces the interim extra life):**
  the third kind is now HEALTH — a heart icon that restores exactly one
  health-bar segment (the game uses a segmented 5-HP bar,
  `PLAYER_START_HEALTH = 5`, rendered via `health_0..5.png`; there is no
  lives system). Gated using a fractional threshold
  (`HEALTH_POWERUP_MIN_HEALTH_FRACTION = 0.8`): excluded from the drop
  pool while `health >= PLAYER_START_HEALTH * 0.8` (at or above 80%
it never drops), and drops normally below that.
  `Player.apply_powerup` clamps `health = min(health + 1, MAX)` so it can
  never overheal, and it has no timer. The extra-life `lives` counter and
  respawn-on-death mechanic were removed entirely (they existed only to
  support the extra-life pickup; death → game_over is back to the original
  single-death flow, H1 unchanged). Icon: `emote_heart.png` (Style 8,
  standalone pixel heart) from Kenney "Emotes Pack" (CC0).

**Preview fix (same session):** the autopilot (`preview_live.py`) drives
`_update_and_draw` directly, which never clears the screen (`screen.fill`
lives only in `Game.run()`), so frames accumulated permanent ghost trails
and a burned-in damage flash. Added the missing per-frame
`g.screen.fill(settings.BLACK)` mirroring `run()`; also killed a stale
capture process from a previous session that was fighting the new one over
frame.png.

### 3.21 Custom power-up sprites + icon sizing + fall speed + shorter durations — **143 tests**

**Custom sprites (uncommitted):** user replaced all three Kenney power-up
icons with their own artwork: `bolt.png` (rapid fire, 736×736),
`heart.png` (health, 736×736), `sheild.png` (shield, 626×626 — note
"sheild" typo is intentional, kept in filenames). Old Kenney sprites
(`powerup_shield.png`, `powerup_rapid.png`, `powerup_health.png`) removed
from git. Attribution updated in `Assets/SOURCES.md`.

**Icon sizing fix:** the user-reported size mismatch (shield visually
smaller than bolt/heart) was caused by `sheild.png` having stray opaque
pixels at two opposite corners (bottom-left y=582–625, top-right y=0–15)
disconnected from the main shield icon (x=180–435, y=210–418). Simple
`get_bounding_rect()` returned the full 626×626 canvas, making the crop
useless. Fixed with a `_content_crop()` helper in `assets.py` that finds
the **largest contiguous block** of opaque rows/columns (ignoring
disconnected artifacts), then aspect-fit scales within `POWERUP_VISIBLE_SIZE`
(28×28). All three icons now render at comparable visible sizes:
shield 24×22, bolt 20×20, heart 24×26. Hitbox stays `POWERUP_IMG_SIZE`
(40×40) — only the visual changed. Requires `numpy` (added to
`requirements.txt`) for the alpha-channel scan.

**Fall speed:** increased from 120 to 250 px/sec (`POWERUP_FALL_SPEED_PER_SEC`).
Still well below enemy speed (300 px/s) and bullet speed (600 px/s), but
fast enough that drops feel responsive rather than drifting.

**Duration constants changed:** both `POWERUP_SHIELD_DURATION_SECONDS` and
`POWERUP_RAPID_FIRE_DURATION_SECONDS` changed from 8.0 to 3.0 seconds.
Uses the existing dt-based timer system (no frame-count changes). The
refresh-not-stack behavior for rapid fire is unchanged. The on-screen
countdown (`SHIELD X.Xs` / `RAPID FIRE X.Xs`) updates automatically.

**Tests:** `test_all_powerup_icons_same_visual_size` verifies all icons
fit within `POWERUP_VISIBLE_SIZE` with max dimension difference ≤ 8 px.
`test_fall_speed_is_dt_based` and `test_fall_speed_constant_reasonable`
verify the speed change.

### 3.22 Options screen: volume sliders + persistent settings (`20a071e`) — **110 tests**
Replaced the options placeholder with two live volume sliders (music / SFX,
0–100%), a read-only controls reference, the HIGH SCORES banner, and an ESC
hint. New `settings_store.py` (`UserSettings`) persists `music_volume`/
`sfx_volume` to `settings.json` (gitignored) with defensive load/atomic write;
defaults are 0.45 / 0.7. Sliders are mouse-draggable; changes apply live via
`AudioManager.set_music_volume` / `set_sfx_volume`. Mute stays independent of
slider values (unmuting restores exactly where they were).

### 3.23 Options BACK button (`e3e8e83`) — **112 tests**
Added `back.png` banner to the Options screen (center y=765, same
`_load_menu_banner` helper as high_scores). Clicking triggers the same fade to
main menu as ESC. Hover-SFX tracked like other buttons.

### 3.24 Options spacing system (`f7f033f`) — **112 tests**
Established `OPTIONS_SECTION_GAP = 50` and `OPTIONS_ITEM_GAP = 24` in
`settings.py`; recomputed all Options y-positions top-down. Controls list became
a 2×3 grid. Pure repositioning — no logic or behavior changed.

### 3.25 Dedicated controls screen + three-button Options (`fb4fd92`) — **123 tests**
Moved the keybind reference off Options onto a new `controls` state (FadeTransition,
BACK/ESC return to Options). ControlsScreen has a full screen with generous
`CONTROLS_ROW_GAP = 60` spacing. Options bottom became three evenly-spaced image
buttons — HIGH SCORES (`score.png`), CONTROLS (`controls.png`), BACK (`back.png`).

### 3.26 Difficulty clock paused (`091fdf4`)
Fixed the difficulty formula's elapsed-time component so it stops counting while
the game is paused (mirrored the existing accumulator pattern). A test confirms
the clock does not advance during pause and resumes correctly on unpause.

### 3.27 PyInstaller spec removed (`2e4b56f`)
Removed `X Hunter.spec` from tracking and added `*.spec` to `.gitignore`. The
build/dist folders were already untracked; this completed the cleanup.

### 3.28 Power-up system (`c1252f1`) — **140 tests**
Shield (3 s invincibility), rapid fire (3× fire rate, refresh-not-stack), and
extra life. 12% drop chance from enemies, 250 px/s fall speed, auto-collect on
contact, 8 s lifetime. Sprites from Kenney "Space Shooter Redux" (CC0).
Separate `shield_timer` on player for shield vs i-frame distinction.

### 3.29 Health-regen pickup (`ab5dba3`)
Replaced the extra-life pickup with a health-regen heart that restores one
health-bar segment (game uses a 5-segment health bar, no lives system). Gated
using a fractional threshold (`HEALTH_POWERUP_MIN_HEALTH_FRACTION = 0.8`),
intended to drop at 4/5 health but actually dropping only at 3/5 due to an
off-by-one in the integer comparison (fixed in §3.37). Icon: `emote_heart.png`
from Kenney "Emotes Pack" (CC0). Extra-life `lives` counter removed entirely.

### 3.30 Custom power-up sprites + sizing + fall speed + shorter durations (`f518275`, `5821a1a`) — **143 tests**
User replaced all three Kenney power-up icons with their own artwork: `bolt.png`,
`heart.png`, `sheild.png` (typo intentional). Fixed icon sizing mismatch via
`_content_crop()` helper (largest-contiguous-block approach for alpha-channel
scanning). Fall speed: 120→250 px/sec. Both durations: 8.0→3.0 seconds.
Requires `numpy` (added to `requirements.txt`).

### 3.31 Level system + FadeText + power-up cropping (`1d72aaf`) — **168 tests**
Added a two-level structure: Level 1 (falling enemies, score target 200) and
Level 2 placeholder (score target 100). `FadeText` component in `ui.py` provides
reusable fade-in/hold/fade-out text overlays for "Phase 1", "Level Finished",
"Phase 2". Run timer tracks total game time (pauses during menus/pause/game_over,
continues through level transitions). Checkpoint restart: Level 1 death → full
reset (level + timer); Level 2 death → restart at Level 2, timer preserved.
25 new tests covering fade text lifecycle, level transitions, run timer, and
checkpoint restart.

### 3.32 Level-exclusive enemy spawning (`b020549`)
Fixed a bug where both Level 1 and Level 2 were spawning a mix of falling enemies
and gunners. Wrapped the replenishment loops in `_update_game()` with
`if self.current_level == 0:` / `if self.current_level == 1:` guards. Level 1:
only falling enemies. Level 2: only gunners. Two new tests explicitly assert
enemy type per level.

### 3.33 Gunner enemies + enemy bullets + time-based leaderboard (`76c718a`) — **192 tests**
**Gunner enemy** (`gunner.py`): spawns in Level 2 only, descends to a random Y
within `GUNNER_MAX_DESCENT_FRACTION = 0.55` of screen height, stops, drifts
side-to-side at 150 px/s (bounces off edges), fires straight down every 2 s.
`GUNNER_DESCEND_SPEED_PER_SEC = 120`.

**Enemy bullets** (`enemy_bullet.py`): red-tinted player bullet sprite, 400 px/s
straight down. Shield blocks them; otherwise triggers i-frame damage. Cleaned up
off-screen.

**Leaderboard rework** (score→time): entries are `{"time": float, "result":
"Finished"|"Dead", "timestamp": float}`. Finished ranks above Dead as a group;
within Finished, fastest first (ascending); within Dead, longest survival first
(descending). Old score-based entries silently discarded on load. UI shows mm:ss
+ colored result label.

**Phase 2 text:** confirmed working with real Level 2 content. `HighScoresMenu`
updated for time display.

### 3.34 Dead-entry sort fix (`23cb64f`) — **193 tests**
Fixed `_sort_key()` in `highscores.py` so Dead entries sort by descending time
(longest survival first) instead of ascending. Added regression test
`test_two_dead_longer_survival_ranks_first`.

### 3.35 Level intro screens (`276daca`) — **202 tests**
New `"level_intro"` state: dedicated black screen showing only the fade text
(no gameplay HUD, entities, or simulation). Gameplay entities are instantiated
but never drawn or updated during the intro. Applies to both Level 1 start and
Level 1→Level 2 transitions. "Phase N" text fades in after a short delay
(`FADE_TEXT_START_DELAY = 18` frames). `_on_fade_text_done()` transitions from
"level_intro" → "game". 7 new tests covering state behavior, simulation freeze,
entity draw suppression, input blocking, and timer pause.

### 3.36 Asset crop + level-transition state machine fix (`c49bfaf`)
Fixed the power-up content crop helper to handle the shield icon's stray corner
pixels correctly. Fixed level-transition state routing so `reset_game()` and
`_on_fade_text_done()` correctly set state to "level_intro" (not "game") and
use `fade.start("level_intro")`.

### 3.37 Health power-up gating off-by-one fix (`dfeeaf3`) — **238 tests**
Fixed a genuine bug in the health-regen drop gate introduced in §3.29 (`ab5dba3`).
The original fractional gate `health >= PLAYER_START_HEALTH * 0.8` (i.e.
`health >= 4.0`) excluded health pickups at BOTH 5/5 and 4/5 health because
the integer comparison was `>=`, not `>`. This meant hearts only dropped at
3/5 or below, one segment lower than the intended 4/5 threshold. Replaced
with a discrete segment-count check: `HEALTH_POWERUP_MIN_MISSING_SEGMENTS = 1`,
using `missing = PLAYER_START_HEALTH - player.health`. Now correctly drops
when health drops to 4/5 (missing = 1) and stops at 5/5 (missing = 0).
Added tests for the gating logic, boundary behavior, and segment-count
correctness to prevent regression.

### 3.38 Ship-exit phase + `level_finished` screen (`58849ea`, `705975e`) — **251 tests**
**Ship exit:** when a level's score target is reached, the player ship flies upward
and off the top of the screen under a scripted exit animation (`SHIP_EXIT_SPEED_PER_SEC =
600`, ~1.3 s at 60 Hz). Handled as a boolean sub-flag `_ship_exit_active` inside the
`"game"` state — player input, firing, and collision checks are frozen; enemies are
cleared; the player is invulnerable. Parallax scrolling continues during ship exit
(it is still live gameplay). The run timer keeps counting.

**Level-finished screen:** once the ship clears y=0, the game fades into a new
`"level_finished"` state — a dedicated black screen showing only "Level Finished"
fade text (same FadeText component as level_intro). No gameplay entities rendered.
After the text completes, transitions into the next level's `level_intro` flow.
Applies to both Level 1 → Level 2 and Level 2 → game complete.

**Player repositioning:** player x/y are reset to the default start position in
`_on_fade_text_done()` when advancing levels, so the ship appears correctly on-screen
at Level 2 start. Invulnerability timer is cleared at ship exit start to prevent
blink-invisibility during the animation.

**Pause during ship exit:** ESC on the `level_finished` screen works, using a
`_state_before_pause` flag so resume returns to the correct pre-pause state.

### 3.39 Parallax scrolling backgrounds + static UI backdrop (`f3671a3`, `db150d2`) — **272 tests**
**New module:** `background.py` with three classes:
- `_ScrollingLayer` — single tile, dt-based vertical scroll (downward), offset wraps
  via modulo for seamless looping.
- `ParallaxBackground` — owns far + near layers per level, swaps on level change,
  updates only during `state == "game"` (including ship-exit sub-state).
- `StaticBackground` — non-scrolling backdrop with file-missing fallback.

**Gameplay layers (2-layer parallax per level):**

| Layer | File | Speed | Visual |
|-------|------|-------|--------|
| L1 far | `l1_far.png` | 40 px/s | Dim, sparse stars, faint purple nebula |
| L1 near | `l1_near.png` | 120 px/s | Brighter stars, purple wisps, sparkle stars |
| L2 far | `l2_far.png` | 45 px/s | Deeper space, magenta tint |
| L2 near | `l2_near.png` | 130 px/s | Magenta wisps, debris, faint planet silhouettes |

All 600×800 (matching screen), seamlessly tileable top-to-bottom (verified: max
pixel diff at seam ≤16/255). Scrolled downward (ship flying forward through space).

**Static UI background:** `ui_bg.png` — same palette, 2–3 visible planets, drawn
behind all menu/UI screens (main menu, options, high_scores, controls, pause,
game_over, level_intro, level_finished). Originally drawn behind main menu but
 MainMenu/ControlsScreen/HighScoresMenu overwrote it with `screen.fill(MENU_BG_COLOR)`;
 this was fixed by removing the overwriting fills.

**Assets:** procedurally generated using pygame drawing primitives for exact palette
control and guaranteed seamless tiling. Deep navy-blue base, wispy purple/magenta
nebula, white/pale-blue stars with brighter sparkle accents. Attributed as original
work in `Assets/SOURCES.md`.

### 3.40 Hide in-game score HUD (`01a0e9b`) — **276 tests**
Removed `ui.draw_score()` call from `_draw_game()`. Score logic is completely
untouched — increments on same triggers, level thresholds still fire, difficulty
scaling still reads `game.score`, leaderboard still records the real score, score
still resets between levels. Game-over and high-scores screens still display score
(they render independently, not via `ui.draw_score`). No layout dependency found
(score was at (10,10), health bar at (10,50), power-up status at y=135 — all
independently positioned).

### 3.41 HUD repositioning (`465c12c`) — **278 tests**
Shifted health bar up by 40 px (from (10,50) to (10,10)) and power-up status up
by 40 px (from y=135 to y=95 via `POWERUP_STATUS_Y`), closing the gap left by
the removed score bar. `POWERUP_STATUS_ROW_GAP` unchanged (30 px). All HUD elements
independent of each other — no cascading layout changes.

### 3.42 Level-score-target test fix
Updated `test_level_1_target_is_200`/`test_level_2_target_is_250` in
`test_levels.py` to match the current values (`[100, 150]`). These tests were
stale after the target values were changed but the tests were not updated.

### 3.43 Dedicated gunner sprite + level-score retune (`f6d9ecd`) — **282 tests**
**Gunner sprite:** `Assets/shooter.png` (325×345, project creator's original art)
is now loaded in `assets.py` and scaled to `ENEMY_IMG_SIZE` (50×50), so
`gunner_img` is a distinct surface from `enemy_img`. Level 2 gunners render with
their own ship; Level 1 falling enemies keep `Assets/Enemyship.png`. The 50×50
collision hitbox is unchanged (sprite was scaled to the hitbox, never the
reverse).

**Orientation:** the sprite was first flipped vertically on a guess (the source's
opaque-pixel density is higher in its top half), but that was backwards in-game —
the artwork is drawn facing the player already. The flip was removed; `gunner_img`
is now the raw scaled source with **no transform**, matching how `enemy_img` is
handled. Attributed as user-provided original art in `Assets/SOURCES.md`.

**Level targets:** `LEVEL_SCORE_TARGETS` retuned `[200, 250]` → `[100, 150]`, with
the stale target tests updated to match. `LEVEL_COUNT` is derived from the list
length (never hand-maintained).

**Tests:** 4 in `TestGunnerSprite` (`test_gunner.py`) — gunner image is a distinct
object from the enemy image, matches the 50×50 hitbox, is **not** flipped, and
Level 1 enemies still use the original sprite.

### 3.44 Editable key bindings on the Controls screen (`99f6317`) — **302 tests**
Added an EDIT button (`Assets/edit.png`, user-provided original art) to the
Controls screen plus a full rebinding flow; movement, firing, mute, pause, and
menu-back all read the live bindings so a rebind takes effect immediately in-game.

**Bindings source of truth:** `settings.DEFAULT_KEY_BINDINGS` — `move_left` (LEFT),
`move_right` (RIGHT), `fire` (SPACE), `pause` (ESC), `mute` (M), `back` (ESC).
The RESTART row is displayed but is a button-only action, never rebindable.
`player.py` now reads `move_left`/`move_right`; `game.py` reads `fire`/`mute`/
`pause`/`back` from `user_settings.key_bindings`.

**Flow:** the EDIT button toggles edit mode (all keyboard rows become clickable);
clicking a row enters a per-row "awaiting input" state showing *Press any key…*;
the next keypress becomes that row's binding, and **edit mode stays on** so more
rows can be rebound in one session; EDIT again (or BACK/ESC) exits back to the
normal list with updated labels.

**Conflict handling (documented decision):** rebinding to an already-used key
**swaps** the two actions (the displaced action takes the old key), so no action is
ever left unbound. Note `pause` and `back` both default to ESC, so key uniqueness
is not guaranteed by design — only "never unbound" is.

**Escape key (documented decision):** ESC is in `RESERVED_KEYS` and is normally
never capturable (pressing it cancels the pending capture). To avoid trapping
players who had rebound `back`/`pause` away from ESC, ESC **is** capturable for
the actions in `ESC_DEFAULT_ACTIONS = ("back", "pause")`. While edit mode is
active the Controls screen owns the keyboard (mute/pause/navigation suppressed);
once edit mode exits, normal ESC handling resumes unchanged.

**Persistence:** reuses the existing `settings_store.py` pattern — `UserSettings`
now carries `key_bindings` (action → keycode) in `settings.json`, loaded
defensively per-action (missing/invalid entries fall back per-action to defaults)
and saved atomically on every rebind.

**Tests:** 20 new in `tests/test_rebind.py` (plus one pre-existing banner test
retargeted in each of `test_highscores.py`/`test_controls.py`) — edit-mode
entry/toggle, back/ESC exit edit mode without navigating, row-select → capture,
ESC cancels capture, ESC never bindable for non-ESC-default actions, ESC
bindable for `back`/`pause`, restart not rebindable, multi-rebind in one session,
swap-on-conflict, same-key no-op, persistence across reload, immediate save, and
live-wiring tests proving the rebound fire/move/mute/back keys work in-game and
the old keys no longer do. `test_controls.py` and `test_options.py` updated for
the new bindings source of truth.

### 3.45 Menu banner sizing: aspect-ratio restore + edit-button content match (`9fccc1b`, `418d15d`) — **306 tests**
Two follow-up fixes after the EDIT button was reported as visibly smaller than the
BACK button on the same screen.

**`9fccc1b` — revert the over-correction:** an earlier attempt made
`_load_menu_banner()` scale images to the **exact footprint** (stretching), which
resized *every* banner button, not just EDIT. Reverted to the original
aspect-ratio-preserving fit (`scale = min(fw/w, fh/h)`), so score/back/controls
returned to their pre-fix appearance, and added `test_menu_banner_sizes_pinned`
pinning every banner's exact rendered pixel size so this can't silently drift
again.

**`418d15d` — match *visible content*, not canvas size:** equal declared sizes were
still not enough. `edit.png` (2048×768) carries far more transparent padding than
`back.png` (1491×354), and its canvas was being stretched non-uniformly to
250×59, so its visible artwork rendered at only **~202×29** vs BACK's **~241×48**
— about 16% narrower *and* 40% shorter. Fix: new
`_load_menu_banner_matching_content()` in `assets.py` (used **only** for
edit.png): `convert_alpha()`, trim to the near-opaque content bbox
(`min_alpha=250`, which also discards edit.png's stray faint pixels — one at
`(996,767)` with alpha 128–249), `smoothscale` the trimmed art preserving aspect
ratio so its width matches `back_img`'s visible content width, and centre it on a
canvas the same size as `back_img` so `edit_rect`/layout is unaffected. Result:
EDIT visible content **239×55** vs BACK 241×48 (width within 2px). The shared
`_load_menu_banner()` was not touched, so every other button keeps its original
loading and size (`score` 249×64, `back` 250×59, `controls` 250×58).

**Tests:** 3 new + 1 updated — `test_edit_button_visible_content_matches_back_button`
(asserts *trimmed* content width within 2px and height ≥ 90% of BACK's; would have
failed before), `test_edit_button_matches_back_content_width_when_file_missing`
(font fallback keeps back_img's size), `test_menu_banner_visible_content_pinned`
(pins the shared-loader buttons' visible content), and
`test_edit_button_same_size_as_back_button` (canvas equality, docstring corrected).

## 5. Current repo state

```
418d15d Fix menu button sizing regression
9fccc1b Preserve banner aspect ratio and pin menu sizes
99f6317 Add editable key rebinding
f6d9ecd Use dedicated gunner sprite; update level targets
465c12c Shift HUD elements up (health bar & power-up)
01a0e9b Hide in-game score HUD during gameplay
db150d2 Fix parallax scroll + menu bg
f3671a3 Add parallax & static backgrounds
705975e Reset player position & visibility on level change
58849ea Add ship-exit phase for level completion
dfeeaf3 Gate health powerups by missing segments
c49bfaf Fix asset crop & level-transition state machine
276daca Add level intro screens before gameplay
b020549 Restrict enemy and gunner updates to their levels
23cb64f Rank Dead entries by longer survival first
76c718a Add Gunner enemies, enemy bullets, time highscores
1d72aaf Add level system, FadeText, and power-up cropping
5821a1a Crop and center power-up images; increase fall speed
f518275 Replace Kenney power-up sprites with user icons
ab5dba3 Replace extra-life power-up with health pickup
c1252f1 Add power-up system: shield, rapid-fire, life
091fdf4 Freeze difficulty clock while paused
2e4b56f Remove PyInstaller spec and ignore .spec files
fb4fd92 Add dedicated Controls screen and Options buttons
f7f033f Add options screen spacing system
e3e8e83 Add BACK button to Options screen
20a071e Add options sliders and persistent settings
d7162b3 Add persistent high-score leaderboard and UI
79c6fc9 Add fixed-timestep accumulator and tests
8413966 Convert game to delta-time (px/s) and update tests
71cdcba Add difficulty ramp and integrate into game
8d2a989 Implement hold-to-fire with cooldown
7c1de0f Add audio manager and integrate SFX/music
9016f9a Add progress and work audit document
718c540 fix: lethal hits now bypass i-frames instead of being refused
6011cea Add dependency manifests, README setup instructions, and project audit
83a6409 Add .gitignore and stop tracking build artifacts
7eaedd2 Add pytest config and game test suite
5e7a76f Align hitboxes to sprites; add smoke test
ef34719 Add player i-frames, blinking and death freeze
398d9e3 Reorganize download and built with sections in README
044af23 Initial commit
```

- **Tracked files:** 113 (all source/assets/tests — build artifacts untracked).
- **Tests:** 306 passing, 1 warning (the intentional mixer-failure test) in ~70 s.
- **Source modules:** `game.py`, `player.py`, `enemy.py`, `gunner.py`, `bullet.py`,
  `enemy_bullet.py`, `explosion.py`, `powerup.py`, `menus.py`, `ui.py`, `assets.py`,
  `settings.py`, `audio.py`, `difficulty.py`, `highscores.py`, `settings_store.py`,
  `resource_path.py`, `background.py`, `main.py`.
- **Test files:** 19 test modules in `tests/` + `conftest.py` + `helpers.py`
  (21 files; 301 `def test_` functions → **306 collected tests** with
  parametrisation).
- **Dependencies:** `requirements.txt` pins `pygame==2.6.1` and `numpy==2.1.1`
  (numpy is used by the power-up alpha-channel content crop); `requirements-dev.txt`
  adds `pytest==9.1.1`.
- **Clean tree:** no uncommitted changes (HEAD = `418d15d`).
- **History rewrite note:** The early commits (before `091fdf4`) were rewritten
  via `git rebase --root` (or equivalent). The original hashes (`f54a4a3` through
  `6c92ca9`) still exist in the git object store but are orphaned (not ancestors
  of HEAD). The current hashes (`ef34719` through `71cdcba`) are the correct
  references. The commit order and messages are identical in both chains (12
  commits, same sequence). The rebase stripped build/ and dist/ directories
  (191 files) from the initial commit through position 5, and removed
  `X Hunter.spec` (44-line file) from all 12 commits. All parent pointers were
  rewritten to chain the new commits together. §6's "artifact history purge"
  note is therefore resolved — the purge already happened.

## 6. Still open / suggested next steps

- **FPS counter** in the HUD to verify dt/accumulator behavior by eye.
- **Interpolation between sim steps** for perfectly smooth rendering at high
  refresh rates (currently render shows the latest fixed step's state).
- **Options screen** — volumes and key rebinding are done; remaining ideas:
  difficulty tuning and per-channel volume vs. master mute.
- **Audio for the menu** (calmer loop, nice-to-have).
- **Hold-to-fire cadence tuning** (`PLAYER_FIRE_COOLDOWN_SECONDS` is a single constant).
- **Pause menu OPTIONS button** — currently players must quit to access volume
  sliders; adding an OPTIONS entry to the pause menu would let them adjust
  settings mid-game.
- **More levels** — Level 2 currently consists of gunner enemies only; additional
  enemy types, boss fights, or procedural level generation could extend the
  two-level structure (`LEVEL_SCORE_TARGETS` already handles arbitrary counts).
- **Parallax background assets** — currently procedurally generated; replacing
  with hand-drawn or Kenney CC0 pack art would improve visual quality.
- **Level-score targets** — retuned to `[100, 150]` in §3.43; may need further
  tuning based on playtesting.
- **Stray committed asset** — `Assets/ChatGPT Image Sep 9, 2026, 06_16_10 PM.png`
  (671 KB) was committed alongside the rebinding work in `99f6317` and is not
  referenced by any code. As of this update it is deleted in the working tree
  (unstaged); decide whether to stage that deletion so it also leaves the history
  of the current tree.
- **Doc hygiene** — §3.16–§3.21 and §3.22–§3.30 describe overlapping work
  (the Options/controls screens and the power-up rework were written up twice
  during incremental sessions). The later-numbered sections are the
  authoritative versions; a consolidation pass would remove the duplication.
- ~~Artifact history purge~~ — build/dist and `X Hunter.spec` were removed
  from history via a full rebase (see §5 history rewrite note). No longer
  needed.

Resolved since last update (§3.43–§3.45):
- ~~Difficulty clock paused during pause~~ — fixed in §3.26.
- ~~Power-up sprites + sizing + durations~~ — committed in §3.30.
- ~~requirements.txt for numpy~~ — added in §3.30.
- ~~Ship-exit animation + level-finished screen~~ — implemented in §3.38.
- ~~Parallax scrolling backgrounds + static UI backdrop~~ — implemented in §3.39.
- ~~Hide in-game score HUD~~ — implemented in §3.40.
- ~~HUD repositioning after score hide~~ — implemented in §3.41.
- ~~Level-score-target test staleness~~ — fixed in §3.42.
- ~~Gunner enemies sharing the Level 1 enemy sprite~~ — dedicated `shooter.png`,
  §3.43.
- ~~Editable key bindings~~ — implemented and persisted, §3.44.
- ~~ESC un-capturable (couldn't rebind back/pause to ESC)~~ — resolved in §3.44;
  ESC is capturable for `back`/`pause`.
- ~~Edit button rendering smaller than back button~~ — visible-content sizing
  fix, §3.45.

## 7. High-score leaderboard (time-based, reworked in §3.33)

### 7.1 Storage (documented choice)

- **Path:** `highscores.json` in the game's **working directory** — the project
  root when run from source, the folder the game is launched from when
  packaged. Kept simple and portable, matching how assets already resolve
  relative to the cwd; no app-data plumbing. Gitignored (it is runtime user
  data, not source).
- **Format:** a JSON array of `{"time": float_seconds, "result":
  "Finished"|"Dead", "timestamp": float}`, kept sorted by `_sort_key()` and
  trimmed to the top `HIGHSCORE_MAX = 10` entries.
- **Defensive everywhere:** a missing file, corrupted JSON, wrong shape
  (non-list / non-dict / missing fields) all load as "no scores yet"; a
  failed write (read-only or missing directory) is logged and the entry stays
  in memory for the session. Writes are atomic (temp file + `os.replace`).
  `highscores.py` never raises to the game.
- Old score-based entries are silently discarded on load (structurally
  incompatible with the new schema — no migration attempted).

### 7.2 Qualify / insert / trim / sort

- **Sort key:** `(0, time)` for Finished (ascending — fastest clear ranks best);
  `(1, -time)` for Dead (descending via negation — longest survival ranks best).
  Finished entries always rank above Dead entries as a group.
- `qualifies(time, result)`: table not full → any entry qualifies; otherwise
  the new entry must rank above the current 10th-place entry per `_sort_key()`.
- `add(time, result, timestamp)`: insert, re-sort, trim to 10, persist
  immediately, return the 0-based rank of the new entry (or `None` if it didn't
  qualify).

### 7.3 Where it hooks in (game.py)

- A run submits an entry in **both** cases: level completion → `add(run_timer,
  result="Finished")`; player death → `add(run_timer, result="Dead")`. Both
  happen in `_draw_game()` at the moment the death explosion finishes / level
  ends — the JSON write is effectively instant, so the fade is never delayed.
  `last_run_rank` stores the rank (or `None`) and `reset_game()` clears it.
- **State `high_scores`**: reached only via the Options screen (`score.png`
  banner button). BACK button (`back.png`) and ESC both return to Options.
  Uses `FadeTransition`; music stops on entry; accumulator never banks.
- The `HighScoresMenu` lists ranks 1–10 with mm:ss time + colored result label
  (green "Finished" / red "Dead") and marks the just-finished run's row with
  a yellow `NEW` badge.

### 7.4 Tests (`tests/test_highscores.py`, 29 tests)

Table logic (sorted insertion, Finished-above-Dead grouping, ascending Finished
sort, descending Dead sort, non-qualifying rejection, tie-at-10 rejection, trim
to 10, longer Dead survival ranks first), persistence round-trip, missing/corrupt/
wrong-shape/unwritable degradation, state navigation (leaderboard NOT directly
reachable from main menu or game-over; reachable via Options; BACK and ESC
return to Options), banner-asset coverage, and end-to-end recording (both
Finished and Dead entries recorded on game over; non-qualifying run not recorded;
NEW-row highlight; restart resets rank but keeps the table).
