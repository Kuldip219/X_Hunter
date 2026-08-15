# Sprite sources & licenses

## Power-up sprites — Kenney.nl (CC0 1.0)

The power-up icons come from two **Kenney.nl** packs by
**Kenney Vleugels**, both licensed **Creative Commons Zero (CC0 1.0)** —
public domain. They may be used in personal and commercial projects;
crediting Kenney (www.kenney.nl) is appreciated but not required.

- License: https://creativecommons.org/publicdomain/zero/1.0/
- Pack license texts: `LICENSE-kenney-CC0.txt` in this folder (identical
  CC0 terms shipped with every pack).

### Shield & rapid fire — "Space Shooter Redux"

| Game file | Original file (in the pack) | Used for | Pack page |
|---|---|---|---|
| `powerup_shield.png` | `PNG/Power-ups/shield_gold.png` | SHIELD power-up icon | https://kenney.nl/assets/space-shooter-redux |
| `powerup_rapid.png` | `PNG/Power-ups/bolt_gold.png` | RAPID FIRE power-up icon | https://kenney.nl/assets/space-shooter-redux |

### Health — "Emotes Pack"

The Redux/Remastered shooter packs contain no heart icon, so the HEALTH
power-up icon comes from Kenney's **Emotes Pack** instead.

| Game file | Original file (in the pack) | Used for | Pack page |
|---|---|---|---|
| `powerup_health.png` | `PNG/Pixel/Style 8/emote_heart.png` | HEALTH power-up icon (the standalone pixel heart, no speech bubble) | https://kenney.nl/assets/emotes-pack |

These are loaded in `assets.py` (via `settings.POWERUP_IMG_FILES`) and
scaled to the `settings.POWERUP_IMG_SIZE` footprint. The same attribution
convention used for the audio assets (`Assets/audio/SOURCES.md` +
`Assets/audio/LICENSE-kenney-CC0.txt`) is mirrored here.
