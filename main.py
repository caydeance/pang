"""Entry point: pygame setup, input handling, and the fixed-timestep loop."""

import sys

import pygame

from audio import init_sounds
from config import (
    FIXED_DT,
    MAX_FRAME_TIME,
    SAMPLE_RATE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    State,
)
from game import Game


def main():
    pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, 512)
    pygame.init()
    sounds = init_sounds()

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Pong")
    clock = pygame.time.Clock()

    fonts = {
        "title": pygame.font.Font(None, 110),
        "gameover": pygame.font.Font(None, 72),
        "menu": pygame.font.Font(None, 40),
        "score": pygame.font.Font(None, 56),
        "hint": pygame.font.Font(None, 22),
    }

    game = Game(sounds)
    accumulator = 0.0

    running = True
    while running:
        frame_dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if game.state == State.MENU:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key in (pygame.K_w, pygame.K_UP):
                        game.menu_move(-1)
                    elif event.key in (pygame.K_s, pygame.K_DOWN):
                        game.menu_move(1)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        game.select_menu()
                elif game.state == State.LEVELS:
                    if event.key == pygame.K_ESCAPE:
                        game.state = State.MENU
                    elif event.key in (
                        pygame.K_w,
                        pygame.K_UP,
                        pygame.K_a,
                        pygame.K_LEFT,
                    ):
                        game.adjust_level(-1)
                    elif event.key in (
                        pygame.K_s,
                        pygame.K_DOWN,
                        pygame.K_d,
                        pygame.K_RIGHT,
                    ):
                        game.adjust_level(1)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        game.start()
                elif game.state == State.PLAYING:
                    if event.key == pygame.K_ESCAPE:
                        game.state = State.MENU
                    elif event.key == pygame.K_SPACE:
                        game.state = State.PAUSED
                    elif event.key == pygame.K_r:
                        game.start()
                elif game.state == State.PAUSED:
                    if event.key == pygame.K_SPACE:
                        game.state = State.PLAYING
                    elif event.key == pygame.K_ESCAPE:
                        game.state = State.MENU
                    elif event.key == pygame.K_r:
                        game.start()
                elif game.state == State.GAMEOVER:
                    if event.key == pygame.K_r:
                        game.start()
                    elif event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                        game.state = State.MENU

        if game.state == State.PLAYING:
            accumulator = min(accumulator + frame_dt, MAX_FRAME_TIME)
            while accumulator >= FIXED_DT:
                game.update(FIXED_DT)
                accumulator -= FIXED_DT
                if game.state != State.PLAYING:
                    accumulator = 0.0
                    break
        else:
            accumulator = 0.0

        game.draw(screen, fonts)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
