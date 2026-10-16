"""The menu, level-select, and end-of-game screens.

Drawing lives apart from the simulation in game.py. Every function here takes the display
surface, the current `game` (for the highlighted option, chosen level, and scores), and a
`fonts` dict built once at startup.
"""

import pygame

from ai import AI_LEVELS, level_description, level_tag
from config import (
    DASH,
    DIMMED,
    HIGHLIGHT,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    WHITE,
    WIN_SCORE,
)

# Each entry is (label shown on the menu, does this mode use the AI?).
MENU_OPTIONS = [
    ("Player vs AI", True),
    ("Two Players", False),
]


def draw_center_banner(screen, fonts, title, subtitle):
    # A translucent full-screen overlay dims the field behind the banner text. The
    # SRCALPHA flag is what makes the overlay's alpha channel actually blend.
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    screen.blit(overlay, (0, 0))

    title_font = fonts["gameover"]
    hint_font = fonts["hint"]
    label = title_font.render(title, True, WHITE)
    screen.blit(
        label, label.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20))
    )
    sub = hint_font.render(subtitle, True, DIMMED)
    screen.blit(
        sub, sub.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30))
    )


def draw_menu(screen, game, fonts):
    title_font = fonts["title"]
    menu_font = fonts["menu"]
    hint_font = fonts["hint"]

    title = title_font.render("PONG", True, WHITE)
    screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 120)))

    # Highlight whichever option matches the current selection.
    for i, (text, vs_ai) in enumerate(MENU_OPTIONS):
        clr = HIGHLIGHT if vs_ai == game.vs_ai else DIMMED
        label = menu_font.render(text, True, clr)
        screen.blit(label, label.get_rect(center=(SCREEN_WIDTH // 2, 220 + i * 48)))

    start = menu_font.render("ENTER / SPACE  Select", True, WHITE)
    screen.blit(start, start.get_rect(center=(SCREEN_WIDTH // 2, 350)))

    info = hint_font.render(
        f"W/S  Move          First to {WIN_SCORE}", True, DIMMED
    )
    screen.blit(info, info.get_rect(center=(SCREEN_WIDTH // 2, 400)))


def draw_levels(screen, game, fonts):
    title_font = fonts["title"]
    menu_font = fonts["menu"]
    hint_font = fonts["hint"]

    title = title_font.render("AI LEVEL", True, WHITE)
    screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 78)))

    # Big level number.
    num_font = pygame.font.Font(None, 150)
    number = num_font.render(str(game.ai_level), True, HIGHLIGHT)
    screen.blit(number, number.get_rect(center=(SCREEN_WIDTH // 2, 195)))

    tag = menu_font.render(level_tag(game.ai_level), True, WHITE)
    screen.blit(tag, tag.get_rect(center=(SCREEN_WIDTH // 2, 285)))

    desc = hint_font.render(level_description(game.ai_level), True, DIMMED)
    screen.blit(desc, desc.get_rect(center=(SCREEN_WIDTH // 2, 320)))

    # A simple progress bar: grey track, colored fill, and a round marker. Geometry is
    # computed from the current level so it scales with AI_LEVELS.
    bar_x, bar_w = SCREEN_WIDTH // 2 - 150, 300
    bar_y = 350
    pygame.draw.rect(screen, DASH, (bar_x, bar_y, bar_w, 8))
    seg = bar_w / AI_LEVELS
    fill = int(seg * game.ai_level)
    pygame.draw.rect(screen, HIGHLIGHT, (bar_x, bar_y, fill, 8))
    marker = bar_x + int(seg * (game.ai_level - 0.5))
    pygame.draw.circle(screen, WHITE, (marker, bar_y + 4), 7)

    if game.ai_level < AI_LEVELS:
        screen.blit(
            hint_font.render(f"Lv {game.ai_level + 1}", True, DIMMED),
            (bar_x + bar_w - 30, bar_y + 14),
        )

    start = menu_font.render("ENTER / SPACE  Play", True, WHITE)
    screen.blit(start, start.get_rect(center=(SCREEN_WIDTH // 2, 405)))

    info = hint_font.render("W/S or A/D  Change Level", True, DIMMED)
    screen.blit(info, info.get_rect(center=(SCREEN_WIDTH // 2, 445)))


def draw_game_over(screen, game, fonts):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    screen.blit(overlay, (0, 0))

    gameover_font = fonts["gameover"]
    menu_font = fonts["menu"]
    hint_font = fonts["hint"]

    # The banner text depends on who won, and whether it was a single-player match.
    if game.winner == "LEFT":
        banner = "YOU WIN" if game.vs_ai else "LEFT WINS"
    else:
        banner = "AI WINS" if game.vs_ai else "RIGHT WINS"

    label = gameover_font.render(banner, True, WHITE)
    screen.blit(
        label, label.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50))
    )

    score = menu_font.render(
        f"{game.left_score}   -   {game.right_score}", True, DIMMED
    )
    screen.blit(
        score, score.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 5))
    )

    # The two controls shown under the result: restart, or go back to the menu.
    again = hint_font.render("R  Play again", True, WHITE)
    screen.blit(
        again, again.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 60))
    )
    back = hint_font.render("ESC  Menu", True, DIMMED)
    screen.blit(
        back, back.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 84))
    )
