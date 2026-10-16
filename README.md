# Pong

A small Pong built with [pygame](https://www.pygame.org/) and Python. Single-player
against a 15-level AI opponent, or two-player on one keyboard. All sound effects are
generated in code, so there are no asset files to manage.

## Controls

**Menu**
- `W` / `S` — move the selection
- `Enter` / `Space` — confirm

**Level select** (Player vs AI)
- `W` / `S` or `A` / `D` — change the AI level (1–15)
- `Enter` / `Space` — start
- `Esc` — back to the menu

**In play**
- `W` / `S` — move the left paddle
- `Up` / `Down` — move the right paddle (two-player mode only)
- `Space` — pause / resume
- `R` — restart the match
- `Esc` — return to the menu

First player to **7** points wins.

## Difficulty

The opponent is one AI whose abilities fade in as the level rises, so difficulty climbs
smoothly instead of jumping:

| Levels | What the AI does                                  |
| ------ | ------------------------------------------------- |
| 1–3    | Slowly follows the ball                           |
| 4–6    | Follows the ball faster                           |
| 7–9    | Predicts where the ball will land                 |
| 10–15  | Predicts and aims its returns away from you      |

## Running

Requires Python 3 and pygame (pygame-ce works too).

```sh
pip install pygame-ce
python main.py
```

With Nix, the included `flake.nix` provides a ready-made shell:

```sh
nix develop
python main.py
```

## Project layout

| File | Responsibility |
| --- | --- |
| `main.py` | Entry point: pygame setup, input, the fixed-timestep loop |
| `game.py` | Simulation (physics, scoring, AI driving) and playfield rendering |
| `ai.py` | Difficulty curve and the AI's abilities |
| `menu.py` | Menu, level-select, pause, and game-over screens |
| `audio.py` | Procedurally generated sound effects |
| `config.py` | All tunable constants, colors, and the `State` enum |
| `utils.py` | Small shared helpers |

## Building a standalone executable

Package a desktop binary with [PyInstaller](https://pyinstaller.org/):

```sh
pip install pyinstaller
pyinstaller --onefile --windowed --name pong main.py
# result: dist/pong
```

Run it in the browser with [pygbag](https://pypi.org/project/pygbag/) (Compiles to
WebAssembly):

```sh
pip install pygbag
pygbag main.py
# then open the local URL it prints
```
