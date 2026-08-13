"""Headless smoke test for the hitbox/sprite alignment fix.

Verifies:
- Rect dimensions now match the rendered sprites (player 65x80, enemy 50x50,
  bullet 10x20 rect instead of a point).
- Bullet-enemy collisions register at every sprite edge (rect overlap),
  including the previously-missed edge case of a bullet on an enemy's edge.
- Player-enemy collisions register when sprites touch and not when they are
  separated by a 1px gap.
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

import settings  # noqa: E402
from bullet import Bullet  # noqa: E402
from enemy import Enemy  # noqa: E402
from game import Game  # noqa: E402
from player import Player  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        FAILURES.append(name)


# ---------------------------------------------------------------- #
# 1. Rect dimensions: before vs after
# ---------------------------------------------------------------- #
print("--- rect dimensions ---")
player = Player(100, 100)
enemy = Enemy(200, 200)
bullet = Bullet(300, 300)
print(f"BEFORE: player rect 50x50 | enemy rect 40x40 | bullet collision = point (x, y)")
print(f"AFTER : player rect {player.get_rect().size} | "
      f"enemy rect {enemy.get_rect().size} | "
      f"bullet rect {bullet.get_rect().size}")
check("player rect matches sprite (65x80)",
      player.get_rect().size == settings.PLAYER_IMG_SIZE == (65, 80),
      f"rect={player.get_rect().size} sprite={settings.PLAYER_IMG_SIZE}")
check("enemy rect matches sprite (50x50)",
      enemy.get_rect().size == settings.ENEMY_IMG_SIZE == (50, 50),
      f"rect={enemy.get_rect().size} sprite={settings.ENEMY_IMG_SIZE}")
check("bullet has a 10x20 rect (not a point)",
      bullet.get_rect().size == settings.BULLET_IMG_SIZE == (10, 20),
      f"rect={bullet.get_rect().size} sprite={settings.BULLET_IMG_SIZE}")
check("player/enemy rects share the sprite's top-left origin",
      player.get_rect().topleft == (player.x, player.y)
      and enemy.get_rect().topleft == (enemy.x, enemy.y),
      "rect origin == (x, y) means no visual drift")

# ---------------------------------------------------------------- #
# 2. Bullet-enemy collisions at every sprite edge (rect overlap)
# ---------------------------------------------------------------- #
print("--- bullet-enemy edge collisions ---")
ex, ey = 200, 200  # enemy at top-left (200, 200), rect 50x50

def hits(bx, by, label):
    e = Enemy(ex, ey)
    b = Bullet(bx, by)
    return e.get_rect().colliderect(b.get_rect()), label, (e.get_rect(), b.get_rect())

cases = [
    # (bx, by, expected, label)
    (ex + 20, ey + 20, True,  "bullet fully inside enemy"),
    (ex - 5,  ey + 15, True,  "bullet overlapping LEFT edge"),
    (ex - 10, ey + 15, False, "bullet 1px left of enemy (touching, no overlap)"),
    (ex + 45, ey + 15, True,  "bullet overlapping RIGHT edge"),
    (ex + 51, ey + 15, False, "bullet 1px right of enemy (no overlap)"),
    (ex + 20, ey - 5,  True,  "bullet overlapping TOP edge"),
    (ex + 20, ey + 45, True,  "bullet overlapping BOTTOM edge"),
    (ex + 20, ey + 51, False, "bullet 1px below enemy (no overlap)"),
]
for bx, by, expected, label in cases:
    got, _, _ = hits(bx, by, label)
    check(f"bullet-enemy: {label}", got is expected,
          f"bullet@({bx},{by}) -> {got}, expected {expected}")

# integration: a bullet overlapping the enemy's left edge scores +1
g = Game()
enemy0 = g.enemies[0]
enemy0.x, enemy0.y = 200, 300
b = Bullet(200 - 5, 300 + 15)  # 5px overlap on the enemy's left edge
g.bullets.append(b)
score_before = g.score
g._update_game(pygame.key.get_pressed())
check("integration: bullet on enemy's left edge scores",
      g.score == score_before + 1, f"score {score_before}->{g.score}")

# ---------------------------------------------------------------- #
# 3. Player-enemy collisions when sprites touch
# ---------------------------------------------------------------- #
print("--- player-enemy collisions ---")
g2 = Game()
p = g2.player  # the active player after reset_game
p.x, p.y = 100, 600
# drain any i-frames so each collision applies
while p.invulnerable:
    p.update_invulnerability()

e = g2.enemies[0]
# enemy overlapping the player's RIGHT sprite edge by 1px
e.x, e.y = p.x + p.width - 1, p.y + 10
hp = p.health
g2._update_game(pygame.key.get_pressed())
check("enemy touching player's right edge deals damage",
      p.health == hp - 1 and p.invulnerable, f"health {hp}->{p.health}")

# enemy 1px clear of the player's right edge -> no damage
while p.invulnerable:
    p.update_invulnerability()
e.x, e.y = p.x + p.width + 1, p.y + 10
hp = p.health
g2._update_game(pygame.key.get_pressed())
check("enemy 1px clear of player's right edge deals no damage",
      p.health == hp and not p.invulnerable, f"health={p.health}")

# enemy overlapping the player's LEFT sprite edge by 1px
while p.invulnerable:
    p.update_invulnerability()
e.x, e.y = p.x - e.width + 1, p.y + 10
hp = p.health
g2._update_game(pygame.key.get_pressed())
check("enemy touching player's left edge deals damage",
      p.health == hp - 1, f"health {hp}->{p.health}")

# enemy overlapping the player's TOP sprite edge by 1px
while p.invulnerable:
    p.update_invulnerability()
e.x, e.y = p.x + 10, p.y - e.height + 1
hp = p.health
g2._update_game(pygame.key.get_pressed())
check("enemy touching player's top edge deals damage",
      p.health == hp - 1, f"health {hp}->{p.health}")

print()
if FAILURES:
    print(f"RESULT: {len(FAILURES)} FAILURE(S): {FAILURES}")
    sys.exit(1)
print("RESULT: ALL CHECKS PASSED")
