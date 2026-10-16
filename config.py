"""Shared constants, colors, and the game-state enum.

Keeping every tunable number in one place means gameplay can be adjusted without hunting
through the code. Speeds are in pixels/second; see game.py for how they get integrated
each frame.
"""

import math
from enum import Enum, auto

# --- Screen geometry (pixels) -------------------------------------------------
SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480

# --- Paddle geometry and motion ----------------------------------------------
PADDLE_W = 12
PADDLE_H = 80
PADDLE_X = 24  # distance from the left/right edge where the paddle sits
PADDLE_SPEED = 540.0  # top speed a human paddle can reach (pixels/second)

# --- Ball physics -------------------------------------------------------------
BALL_SIZE = 12
BALL_SPEED = 300.0  # speed at the start of a rally (pixels/second)
MAX_BALL_SPEED = 640.0  # hard ceiling so rallies can't become unplayable
BALL_SPEED_UP = 1.06  # multiply speed by this on every paddle hit (speeds up rallies)
MAX_BOUNCE_ANGLE = math.pi / 3  # steepest exit angle off a paddle (60 degrees)

# --- Match rules --------------------------------------------------------------
WIN_SCORE = 7  # first player to this many points wins

# --- Simulation timing --------------------------------------------------------
# Rather than trusting "however long the last frame took", we advance physics in fixed
# slices of time (a "fixed timestep"). This keeps movement stable and repeatable even if
# the frame rate stutters. MAX_FRAME_TIME caps the catch-up so a long freeze (e.g. the
# window was dragged) can't trigger hundreds of simulation steps at once ("death spiral").
FIXED_DT = 1.0 / 120.0
MAX_FRAME_TIME = 0.25

# --- Human paddle feel --------------------------------------------------------
# Paddles don't jump to full speed instantly; they accelerate toward the desired speed.
PADDLE_ACCEL = 6000.0  # pixels/second^2

# --- Screen shake ("trauma" model) --------------------------------------------
# Impacts add intensity ("trauma"), which decays every frame. The camera offset scales
# with trauma squared so big hits shake hard but settle quickly and smoothly.
MAX_SHAKE = 7.0  # largest possible camera offset in pixels (when trauma == 1)
TRAUMA_DECAY = 1.8  # trauma lost per second

# --- Ball trail ---------------------------------------------------------------
TRAIL_LEN = 12  # how many previous ball positions to keep and draw as a fading trail

# --- Score particle burst -----------------------------------------------------
PARTICLE_COUNT = 24
PARTICLE_LIFE = 0.6  # seconds each particle lives
PARTICLE_SPEED = 260.0  # initial particle speed (pixels/second)

# --- Audio --------------------------------------------------------------------
SAMPLE_RATE = 48000  # samples per second for the generated sound effects

# --- Palette (RGB tuples) -----------------------------------------------------
WHITE = (255, 255, 255)
BG = (16, 16, 24)
DASH = (96, 96, 112)
DIMMED = (128, 128, 144)
HIGHLIGHT = (120, 200, 255)


class State(Enum):
    # A tiny finite state machine drives what the game shows and what input does.
    MENU = auto()
    LEVELS = auto()
    PLAYING = auto()
    PAUSED = auto()
    GAMEOVER = auto()
