"""Entry point: set up pygame, then run the input -> simulate -> draw loop.

Two ideas worth knowing if you are new to games:

* The main loop runs forever until the player quits. Each pass it reads input, advances
  the simulation, and paints one frame.
* Simulation uses a FIXED TIMESTEP: real elapsed time is banked in `accumulator` and spent
  in equal `FIXED_DT` slices. Physics therefore advances by the same amount every step no
  matter how fast or slow the machine is. `MAX_FRAME_TIME` caps how much time can pile up,
  so one long freeze can't trigger a burst of hundreds of catch-up steps ("death spiral").

Input handling (here), simulation (game.py), and drawing (game.py + menu.py) are kept
separate so each one stays easy to reason about.
"""

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
    # The main loop. Each iteration: read events, advance the simulation, draw, present.
    pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, 512)
    pygame.init()
    sounds = init_sounds()

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Pong")
    clock = pygame.time.Clock()  # used to measure real elapsed time between frames

    # Pre-build the fonts once; creating them every frame would be slow. The dict keys
    # are used by the drawing code in game.py and menu.py.
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
        # Seconds since the previous frame. clock.tick(60) also caps us near 60 FPS.
        frame_dt = clock.tick(60) / 1000.0

        # 1) Input: turn OS events into state changes. This is decoupled from physics so
        #    input handling stays responsive even if we step physics at a different rate.
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

        # 2) Fixed-timestep simulation. We bank the real elapsed time and consume it in
        #    fixed FIXED_DT chunks, so physics always advances by the same amount per step.
        #    If a frame was slow, we may run several steps to catch up. We cap the debt
        #    (MAX_FRAME_TIME) so a long stall can't spawn an unbounded burst of steps.
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

        # 3) Draw the current state and present the finished frame to the window.
        game.draw(screen, fonts)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
