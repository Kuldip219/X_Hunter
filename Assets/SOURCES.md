# Sprite sources & licenses

## Power-up sprites — Kenney.nl "Space Shooter Redux" (CC0 1.0)

The three power-up icons come from **Kenney.nl**'s **Space Shooter Redux**
pack by **Kenney Vleugels**, licensed **Creative Commons Zero (CC0 1.0)** —
public domain. They may be used in personal and commercial projects;
crediting Kenney (www.kenney.nl) is appreciated but not required.

- Pack page: https://kenney.nl/assets/space-shooter-redux
- License: https://creativecommons.org/publicdomain/zero/1.0/
- Pack license text: `LICENSE-kenney-CC0.txt` in this folder (the license
  shipped with the pack).

| Game file | Original file (in the pack) | Used for |
|---|---|---|
| `powerup_shield.png` | `PNG/Power-ups/shield_gold.png` | SHIELD power-up icon |
| `powerup_rapid.png` | `PNG/Power-ups/bolt_gold.png` | RAPID FIRE power-up icon |
| `powerup_life.png` | `PNG/UI/playerLife1_blue.png` | EXTRA LIFE power-up icon |

These are loaded in `assets.py` (via `settings.POWERUP_IMG_FILES`) and
scaled to the `settings.POWERUP_IMG_SIZE` footprint. The same attribution
convention used for the audio assets (`Assets/audio/SOURCES.md` +
`Assets/audio/LICENSE-kenney-CC0.txt`) is mirrored here.
