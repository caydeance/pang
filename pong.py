"""
Pong built on pygame.

If you are a software developer but new to games, these are the ideas to keep in mind
while reading this file:

* Coordinates start at the TOP-LEFT. x grows to the right, y grows DOWNWARD. So "up"
  means decreasing y, and the bottom edge of this 480px-tall screen is y == 480.
* Speeds are in PIXELS PER SECOND and everything is integrated every frame with
  `position += velocity * dt`. Working in per-second units is what lets the game behave
  the same whether the machine renders 30 or 300 frames per second.
* The game is split into two halves that never mix: `update(dt)` advances the simulation
  and `draw(...)` only paints the current state. Physics never reads input directly, and
  drawing never mutates game state.
* pygame paints onto a `Surface`. The window's display is itself a surface, and
  `pygame.display.flip()` at the end of the loop presents whatever you drew. Text is
  rendered to its own small surface before being blitted (drawn) somewhere.
* Collisions here are simple axis-aligned bounding boxes (`pygame.Rect`), which is more
  than enough for axis-aligned rectangles (paddles) and a square (the ball).
"""

import array
import math
import random
import sys
from enum import Enum, auto

import pygame

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

# --- AI difficulty (15 levels, see the ai_* helpers below) --------------------
AI_LEVELS = 15
AI_SPEED_MIN = 140.0  # slowest AI paddle speed (pixels/second)
AI_SPEED_MAX = 360.0  # fastest AI paddle speed (pixels/second)

# --- AI prediction error ------------------------------------------------------
# The AI predicts where the ball will cross its paddle, then adds a random offset so it
# isn't perfect. Higher levels use a smaller error (more accurate).
AI_PREDICT_ERROR_MAX = 70.0
AI_PREDICT_ERROR_MIN = 4.0

# How far off-center the AI tries to hit the ball (0 = dead center). Hitting off-center
# sends the ball back at an angle, which the AI uses to aim away from the human.
AI_AIM_STRENGTH = 0.85

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


def lerp_color(c1, c2, t):
    # Linear blend between two RGB colors. t goes 0 (all c1) to 1 (all c2). Used to fade
    # things toward the background color instead of dealing with per-pixel alpha.
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


class State(Enum):
    # A tiny finite state machine drives what the game shows and what input does.
    MENU = auto()
    LEVELS = auto()
    PLAYING = auto()
    PAUSED = auto()
    GAMEOVER = auto()


# Each entry is (label shown on the menu, does this mode use the AI?).
MENU_OPTIONS = [
    ("Player vs AI", True),
    ("Two Players", False),
]


def _ramp(level, lo, hi):
    """Map a level to a 0..1 progress value.

    Returns 0 for levels at or below `lo` and 1 at or above `hi`, interpolating linearly
    in between. This is how each AI ability is faded in over a range of levels, so
    difficulty rises smoothly instead of jumping at a single threshold.
    """
    if hi <= lo:
        return 1.0 if level >= hi else 0.0
    return max(0.0, min(1.0, (level - lo) / (hi - lo)))


def ai_speed(level):
    # Paddle speed ramps up across levels 3..7 (levels 1-2 stay at the minimum).
    return AI_SPEED_MIN + (AI_SPEED_MAX - AI_SPEED_MIN) * _ramp(level, 3, 7)


def ai_predict_blend(level):
    # 0 = react only to the ball's current position, 1 = trust the predicted landing spot.
    return _ramp(level, 6, 10)


def ai_predict_error(level):
    # Random inaccuracy (pixels) added to the prediction; shrinks across levels 6..15.
    t = _ramp(level, 6, 15)
    return AI_PREDICT_ERROR_MAX + (AI_PREDICT_ERROR_MIN - AI_PREDICT_ERROR_MAX) * t


def ai_aim_skill(level):
    # 0 = just return the ball, 1 = fully aim the return away from the human.
    return _ramp(level, 10, 15)


def level_description(level):
    if level <= 3:
        return "Slowly follows the ball"
    if level <= 6:
        return "Follows the ball faster"
    if level <= 9:
        return "Predicts where the ball lands"
    return "Predicts and aims away from you"


def level_tag(level):
    if level <= 3:
        return "BEGINNER"
    if level <= 6:
        return "EASY"
    if level <= 9:
        return "MEDIUM"
    if level <= 12:
        return "HARD"
    return "EXPERT"


def make_tone(freq, secs, vol=0.5):
    """Synthesize a short beep as raw PCM audio.

    A digital sound is just a stream of samples: here a sine wave whose volume fades out
    exponentially over its duration (that decay is what makes it sound like a "blip" and
    not a harsh cut-off). Samples are 16-bit signed integers, and we write the same sample
    to both channels so it plays centered in stereo.
    """
    n = int(secs * SAMPLE_RATE)
    buf = array.array("h")  # "h" = signed 16-bit integers
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-4 * t / secs)  # exponential fade-out envelope
        s = int(math.sin(2 * math.pi * freq * t) * env * vol * 32767)
        buf.append(s)
        buf.append(s)
    return pygame.mixer.Sound(buffer=buf.tobytes())


def init_sounds():
    # Generate the effects in code instead of shipping audio files. If there is no audio
    # device (headless CI, for example), degrade gracefully to "no sounds".
    try:
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2)
    except pygame.error:
        return {}
    return {
        "paddle": make_tone(440, 0.06, 0.5),
        "wall": make_tone(220, 0.05, 0.4),
        "score": make_tone(660, 0.18, 0.5),
        "win": make_tone(880, 0.35, 0.5),
    }


class Game:
    def __init__(self, sounds):
        # Paddle/ball positions are kept both as pixel Rects (for drawing and collision)
        # and as floats (bx/by, left_y/right_y). Integers lose sub-pixel movement, which
        # makes smooth motion impossible, so the authoritative values are the floats.
        self.left = pygame.Rect(
            PADDLE_X, SCREEN_HEIGHT // 2 - PADDLE_H // 2, PADDLE_W, PADDLE_H
        )
        self.right = pygame.Rect(
            SCREEN_WIDTH - PADDLE_X - PADDLE_W,
            SCREEN_HEIGHT // 2 - PADDLE_H // 2,
            PADDLE_W,
            PADDLE_H,
        )
        self.ball = pygame.Rect(0, 0, BALL_SIZE, BALL_SIZE)

        self.left_y = float(self.left.y)
        self.right_y = float(self.right.y)
        self.bx = 0.0
        self.by = 0.0

        # Velocity in pixels/second. vx is horizontal, vy is vertical (positive = down).
        self.ball_vx = 0.0
        self.ball_vy = 0.0
        self.speed = BALL_SPEED

        self.left_score = 0
        self.right_score = 0

        self.vs_ai = True
        self.ai_level = 8
        self.sounds = sounds
        self.state = State.MENU
        self.winner = None

        self.ai_target_y = self.right_y
        self.ai_predicted = False
        self.ai_error = 0.0

        # Human paddle velocities (pixels/second), integrated for smooth acceleration.
        self.left_vy = 0.0
        self.right_vy = 0.0

        # Juice: camera shake intensity, recent ball positions, and active particles.
        self.trauma = 0.0
        self.trail = []
        self.particles = []  # each: [x, y, vx, vy, life_left, life_total]

        # A scratch Surface we render the playfield onto so we can shake it as a whole.
        self.field = None

        self.reset_ball(1)

    def menu_move(self, delta):
        # Move the highlighted menu entry up/down, clamped to the list bounds.
        opts = [vs_ai for _, vs_ai in MENU_OPTIONS]
        idx = opts.index(self.vs_ai)
        idx = max(0, min(len(MENU_OPTIONS) - 1, idx + delta))
        self.vs_ai = opts[idx]

    def select_menu(self):
        # Confirming "Player vs AI" goes to the level picker; "Two Players" starts at once.
        if self.vs_ai:
            self.state = State.LEVELS
        else:
            self.start()

    def adjust_level(self, delta):
        self.ai_level = max(1, min(AI_LEVELS, self.ai_level + delta))

    def play(self, name):
        # Sound playback is fire-and-forget, so overlapping effects are fine.
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    def add_trauma(self, amount):
        # Pile on shake intensity, saturating at 1 (see MAX_SHAKE / TRAUMA_DECAY).
        self.trauma = min(1.0, self.trauma + amount)

    def shake_offset(self):
        # Camera offset for this frame. Squaring trauma makes the falloff feel punchy:
        # small hits barely move, big hits ramp up fast. Returns a random point so the
        # shake looks like noise rather than a smooth drift.
        if self.trauma <= 0:
            return 0, 0
        mag = MAX_SHAKE * self.trauma * self.trauma
        return (random.uniform(-mag, mag), random.uniform(-mag, mag))

    def spawn_particles(self, x, y):
        # Emit a radial burst: pick a random direction and speed for each particle. This
        # replaces any previous burst (particles is a flat list; one burst at a time).
        self.particles = []
        for _ in range(PARTICLE_COUNT):
            ang = random.uniform(0, 2 * math.pi)
            spd = random.uniform(0.3, 1.0) * PARTICLE_SPEED
            self.particles.append(
                [x, y, math.cos(ang) * spd, math.sin(ang) * spd, PARTICLE_LIFE, PARTICLE_LIFE]
            )

    def get_field(self):
        # Create the offscreen playfield surface on first use. It must be built after the
        # display exists, so we can't do it in __init__.
        if self.field is None:
            self.field = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        return self.field

    def start(self):
        # Begin a fresh match: reset scores, paddles, and all transient effects.
        self.left_score = 0
        self.right_score = 0
        self.winner = None
        self.left_y = SCREEN_HEIGHT / 2 - PADDLE_H / 2
        self.right_y = SCREEN_HEIGHT / 2 - PADDLE_H / 2
        self.left_vy = 0.0
        self.right_vy = 0.0
        self.trauma = 0.0
        self.trail = []
        self.particles = []
        self.reset_ball(random.choice((-1.0, 1.0)))
        self.state = State.PLAYING

    def reset_ball(self, direction):
        # Serve from the center. We choose a random vertical share (up to 0.7 of the total
        # speed) and derive vx so the total speed stays exactly BALL_SPEED:
        # vx^2 + vy^2 == speed^2. `direction` (+1/-1) picks which player receives it.
        self.bx = SCREEN_WIDTH / 2 - BALL_SIZE / 2
        self.by = SCREEN_HEIGHT / 2 - BALL_SIZE / 2
        self.ball.x = int(self.bx)
        self.ball.y = int(self.by)
        self.speed = BALL_SPEED
        max_vy = BALL_SPEED * 0.7
        self.ball_vy = (random.random() * 2 - 1) * max_vy
        self.ball_vx = (
            math.sqrt(BALL_SPEED * BALL_SPEED - self.ball_vy * self.ball_vy) * direction
        )
        self.ai_predicted = False
        self.trail = []

    @staticmethod
    def clamp_y(y):
        # Keep a paddle's top edge within [0, screen_height - paddle_height].
        return max(0.0, min(y, SCREEN_HEIGHT - PADDLE_H))

    def predict_intercept(self, paddle_x):
        # Where will the ball cross the given x if it keeps going in a straight line?
        # First find the time to travel the remaining horizontal distance (t = dist/speed),
        # then move that far vertically. Deliberately ignores future wall bounces, so the
        # AI can be fooled by one and has to re-read the ball afterwards -- just like a
        # person eyeballing the ball would be.
        if self.ball_vx <= 0:
            return self.by
        t = (paddle_x - self.bx) / self.ball_vx
        return self.by + self.ball_vy * t

    def aim_target(self):
        # Compute the paddle position that returns the ball toward the side the human is
        # NOT on. The trick: the ball bounces according to where it strikes the paddle
        # (see bounce_off_paddle), so we shift the paddle off the intercept point by up to
        # AI_AIM_STRENGTH of a half-paddle. That skews the exit angle away from the player.
        intercept = self.predict_intercept(self.right.left) + BALL_SIZE / 2  # ball center
        player_center = self.left_y + PADDLE_H / 2
        sign = 1.0 if player_center < SCREEN_HEIGHT / 2 else -1.0  # +1 down, -1 up
        rel = sign * AI_AIM_STRENGTH
        paddle_center = intercept - rel * (PADDLE_H / 2)
        return self.clamp_y(paddle_center - PADDLE_H / 2)

    def update_ai(self, dt):
        # The AI only needs to move while the ball is approaching it (moving right).
        if self.ball_vx <= 0:
            self.ai_predicted = False
            return

        track_target = self.by + BALL_SIZE / 2 - PADDLE_H / 2  # follow the ball's y
        blend = ai_predict_blend(self.ai_level)
        if blend <= 0:
            # Low levels: naive tracking, reacting to where the ball is right now.
            target = track_target
        else:
            # Higher levels: blend that naive tracking with a predicted landing spot.
            if not self.ai_predicted:
                # Roll one random aiming error for this straight segment of the rally so
                # the target doesn't jitter frame to frame.
                err_mag = ai_predict_error(self.ai_level)
                self.ai_error = (random.random() * 2 - 1) * err_mag
                self.ai_predicted = True
            center = self.predict_intercept(self.right.left) + BALL_SIZE / 2
            pred_y = self.clamp_y(center + self.ai_error - PADDLE_H / 2)
            target = track_target + (pred_y - track_target) * blend

        # Top levels also bias the paddle off-center to aim the return away from the human.
        aim = ai_aim_skill(self.ai_level)
        if aim > 0:
            target = target + (self.aim_target() - target) * aim

        self.move_ai_toward(target, dt, ai_speed(self.ai_level))

    def move_ai_toward(self, target, dt, speed):
        # Move at a fixed speed but never overshoot the target (that would cause wobble).
        diff = target - self.right_y
        step = speed * dt
        if abs(diff) <= step:
            self.right_y = target
        else:
            self.right_y += math.copysign(step, diff)

    @staticmethod
    def approach(current, target, rate, dt):
        # Nudge `current` toward `target` by at most `rate * dt`, stopping exactly on it.
        # Used to ramp a paddle's velocity up/down for acceleration instead of snapping.
        step = rate * dt
        if abs(target - current) <= step:
            return target
        return current + math.copysign(step, target - current)

    def bounce_off_paddle(self, paddle, direction):
        # Classic Pong bounce: where the ball hits the paddle decides the exit angle.
        # `rel` is the hit offset from the paddle center, normalized to -1..1 (edges).
        # rel=0 -> straight back out; rel=+/-1 -> MAX_BOUNCE_ANGLE. `direction` (-1/+1)
        # then sends the ball toward the other side. Speed ticks up a little each hit.
        rel = (self.ball.y + BALL_SIZE / 2) - (paddle.y + PADDLE_H / 2)
        rel /= PADDLE_H / 2
        rel = max(-1.0, min(1.0, rel))
        self.speed = min(self.speed * BALL_SPEED_UP, MAX_BALL_SPEED)
        angle = rel * MAX_BOUNCE_ANGLE
        self.ball_vx = math.cos(angle) * self.speed * direction
        self.ball_vy = math.sin(angle) * self.speed

    def update(self, dt):
        # Advance the whole simulation by a fixed `dt`. No drawing happens here.
        keys = pygame.key.get_pressed()

        # Human paddles: read input into a desired velocity, accelerate toward it, then
        # integrate velocity into position (position += velocity * dt).
        want_left = 0.0
        if keys[pygame.K_w]:
            want_left -= PADDLE_SPEED
        if keys[pygame.K_s]:
            want_left += PADDLE_SPEED
        self.left_vy = self.approach(self.left_vy, want_left, PADDLE_ACCEL, dt)
        self.left_y += self.left_vy * dt

        if self.vs_ai:
            self.update_ai(dt)
        else:
            want_right = 0.0
            if keys[pygame.K_UP]:
                want_right -= PADDLE_SPEED
            if keys[pygame.K_DOWN]:
                want_right += PADDLE_SPEED
            self.right_vy = self.approach(self.right_vy, want_right, PADDLE_ACCEL, dt)
            self.right_y += self.right_vy * dt

        self.left_y = self.clamp_y(self.left_y)
        self.right_y = self.clamp_y(self.right_y)
        self.left.y = int(self.left_y)
        self.right.y = int(self.right_y)

        # Integrate the ball, then resolve collisions. We reflect (negate) vy at the
        # top/bottom walls and push the ball back inside so it can't tunnel through.
        self.bx += self.ball_vx * dt
        self.by += self.ball_vy * dt

        if self.by <= 0:
            self.by = 0
            self.ball_vy = -self.ball_vy
            self.ai_predicted = False  # trajectory changed; let the AI re-read it
            self.add_trauma(0.12)
            self.play("wall")
        if self.by + BALL_SIZE >= SCREEN_HEIGHT:
            self.by = SCREEN_HEIGHT - BALL_SIZE
            self.ball_vy = -self.ball_vy
            self.ai_predicted = False
            self.add_trauma(0.12)
            self.play("wall")

        self.ball.x = int(self.bx)
        self.ball.y = int(self.by)

        # Append to the trail history, dropping the oldest so it stays a fixed length.
        self.trail.append((self.bx, self.by))
        if len(self.trail) > TRAIL_LEN:
            self.trail.pop(0)

        # Paddle hits. We check direction as well as overlap so the ball can't get stuck
        # "hitting" the paddle it's moving away from.
        if self.ball_vx < 0 and self.ball.colliderect(self.left):
            self.bx = self.left.right
            self.bounce_off_paddle(self.left, 1)
            self.add_trauma(0.18)
            self.play("paddle")
        if self.ball_vx > 0 and self.ball.colliderect(self.right):
            self.bx = self.right.left - BALL_SIZE
            self.bounce_off_paddle(self.right, -1)
            self.add_trauma(0.18)
            self.play("paddle")

        # A ball leaving the left edge scores for the right player (and vice versa).
        if self.bx + BALL_SIZE < 0:
            self.right_score += 1
            self.add_trauma(0.5)
            self.spawn_particles(0, self.by + BALL_SIZE / 2)
            self.play("score")
            self.check_game_over()
            if self.state == State.PLAYING:
                self.reset_ball(1)
        if self.bx > SCREEN_WIDTH:
            self.left_score += 1
            self.add_trauma(0.5)
            self.spawn_particles(SCREEN_WIDTH, self.by + BALL_SIZE / 2)
            self.play("score")
            self.check_game_over()
            if self.state == State.PLAYING:
                self.reset_ball(-1)

        # Age transient effects every tick so they we can be dt-independent.
        self.trauma = max(0.0, self.trauma - TRAUMA_DECAY * dt)
        self._update_particles(dt)

    def _update_particles(self, dt):
        # Integrate particle positions, apply drag so they slow down, drop expired ones.
        # Rebuilding the list each tick is a simple way to remove dead particles.
        alive = []
        for p in self.particles:
            p[4] -= dt
            if p[4] <= 0:
                continue
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            drag = 1.0 - 3.0 * dt  # velocity damping per frame
            p[2] *= drag
            p[3] *= drag
            alive.append(p)
        self.particles = alive

    def check_game_over(self):
        if self.left_score >= WIN_SCORE:
            self.winner = "LEFT"
            self.state = State.GAMEOVER
            self.play("win")
        elif self.right_score >= WIN_SCORE:
            self.winner = "RIGHT"
            self.state = State.GAMEOVER
            self.play("win")

    def draw(self, screen, fonts):
        # Rendering only. The menu screens draw straight to the display surface.
        screen.fill(BG)

        if self.state == State.MENU:
            self.draw_menu(screen, fonts)
            return

        if self.state == State.LEVELS:
            self.draw_levels(screen, fonts)
            return

        # The playfield is painted onto an offscreen surface first, then blitted onto the
        # screen at an offset. Shifting the whole surface in one go is how the screen
        # shake is implemented -- much simpler than offsetting every individual object.
        field = self.get_field()
        field.fill(BG)

        # Dashed center line.
        for y in range(0, SCREEN_HEIGHT, 20):
            pygame.draw.rect(field, DASH, (SCREEN_WIDTH // 2 - 2, y, 4, 12))

        self.draw_trail(field)

        pygame.draw.rect(field, WHITE, self.left)
        pygame.draw.rect(field, WHITE, self.right)
        pygame.draw.rect(field, WHITE, self.ball)

        self.draw_particles(field)

        # Scores and control hints. render() produces a surface; get_rect(center=...)
        # gives us a rect of the right size positioned around that point for centering.
        score_font = fonts["score"]
        hint_font = fonts["hint"]

        left_label = score_font.render(str(self.left_score), True, WHITE)
        right_label = score_font.render(str(self.right_score), True, WHITE)
        field.blit(left_label, left_label.get_rect(center=(SCREEN_WIDTH // 2 - 30, 40)))
        field.blit(right_label, right_label.get_rect(center=(SCREEN_WIDTH // 2 + 30, 40)))

        field.blit(hint_font.render("W/S", True, WHITE), (24, SCREEN_HEIGHT - 24))
        if self.vs_ai:
            field.blit(
                hint_font.render(f"AI Lv{self.ai_level}", True, WHITE),
                (SCREEN_WIDTH - 84, SCREEN_HEIGHT - 24),
            )
        else:
            field.blit(
                hint_font.render("UP/DOWN", True, WHITE),
                (SCREEN_WIDTH - 84, SCREEN_HEIGHT - 24),
            )

        # Apply the shake by blitting the finished playfield at an offset.
        ox, oy = self.shake_offset()
        screen.blit(field, (ox, oy))

        # Overlays (pause / game over) go on top and deliberately do not shake.
        if self.state == State.PAUSED:
            self.draw_center_banner(screen, fonts, "PAUSED", "SPACE to resume")
        elif self.state == State.GAMEOVER:
            self.draw_game_over(screen, fonts)

    def draw_trail(self, surface):
        # Draw the remembered ball positions oldest-first so newer ones paint on top.
        # Each is faded and shrunk by how old it is, giving a motion-blur-like streak.
        n = len(self.trail)
        for i, (tx, ty) in enumerate(self.trail):
            frac = (i + 1) / n
            color = lerp_color(BG, WHITE, frac * 0.6)
            radius = max(1, int(BALL_SIZE / 2 * (0.25 + 0.75 * frac)))
            center = (int(tx + BALL_SIZE / 2), int(ty + BALL_SIZE / 2))
            pygame.draw.circle(surface, color, center, radius)

    def draw_particles(self, surface):
        # Fade and shrink each particle as its remaining life runs out.
        for px, py, _vx, _vy, life, max_life in self.particles:
            frac = max(0.0, life / max_life)
            color = lerp_color(BG, HIGHLIGHT, frac)
            pygame.draw.circle(surface, color, (int(px), int(py)), 1 + int(3 * frac))

    def draw_center_banner(self, screen, fonts, title, subtitle):
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

    def draw_menu(self, screen, fonts):
        title_font = fonts["title"]
        menu_font = fonts["menu"]
        hint_font = fonts["hint"]

        title = title_font.render("PONG", True, WHITE)
        screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 120)))

        # Highlight whichever option matches the current selection.
        for i, (text, vs_ai) in enumerate(MENU_OPTIONS):
            clr = HIGHLIGHT if vs_ai == self.vs_ai else DIMMED
            label = menu_font.render(text, True, clr)
            screen.blit(label, label.get_rect(center=(SCREEN_WIDTH // 2, 220 + i * 48)))

        start = menu_font.render("ENTER / SPACE  Select", True, WHITE)
        screen.blit(start, start.get_rect(center=(SCREEN_WIDTH // 2, 350)))

        info = hint_font.render(
            f"W/S  Move          First to {WIN_SCORE}", True, DIMMED
        )
        screen.blit(info, info.get_rect(center=(SCREEN_WIDTH // 2, 400)))

    def draw_levels(self, screen, fonts):
        title_font = fonts["title"]
        menu_font = fonts["menu"]
        hint_font = fonts["hint"]

        title = title_font.render("AI LEVEL", True, WHITE)
        screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 78)))

        # Big level number.
        num_font = pygame.font.Font(None, 150)
        number = num_font.render(str(self.ai_level), True, HIGHLIGHT)
        screen.blit(number, number.get_rect(center=(SCREEN_WIDTH // 2, 195)))

        tag = menu_font.render(level_tag(self.ai_level), True, WHITE)
        screen.blit(tag, tag.get_rect(center=(SCREEN_WIDTH // 2, 285)))

        desc = hint_font.render(level_description(self.ai_level), True, DIMMED)
        screen.blit(desc, desc.get_rect(center=(SCREEN_WIDTH // 2, 320)))

        # A simple progress bar: grey track, colored fill, and a round marker. Geometry is
        # computed from the current level so it scales with AI_LEVELS.
        bar_x, bar_w = SCREEN_WIDTH // 2 - 150, 300
        bar_y = 350
        pygame.draw.rect(screen, DASH, (bar_x, bar_y, bar_w, 8))
        seg = bar_w / AI_LEVELS
        fill = int(seg * self.ai_level)
        pygame.draw.rect(screen, HIGHLIGHT, (bar_x, bar_y, fill, 8))
        marker = bar_x + int(seg * (self.ai_level - 0.5))
        pygame.draw.circle(screen, WHITE, (marker, bar_y + 4), 7)

        if self.ai_level < AI_LEVELS:
            screen.blit(
                hint_font.render(f"Lv {self.ai_level + 1}", True, DIMMED),
                (bar_x + bar_w - 30, bar_y + 14),
            )

        start = menu_font.render("ENTER / SPACE  Play", True, WHITE)
        screen.blit(start, start.get_rect(center=(SCREEN_WIDTH // 2, 405)))

        info = hint_font.render("W/S or A/D  Change Level", True, DIMMED)
        screen.blit(info, info.get_rect(center=(SCREEN_WIDTH // 2, 445)))

    def draw_game_over(self, screen, fonts):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        screen.blit(overlay, (0, 0))

        gameover_font = fonts["gameover"]
        menu_font = fonts["menu"]
        hint_font = fonts["hint"]

        # The banner text depends on who won, and whether it was a single-player match.
        if self.winner == "LEFT":
            banner = "YOU WIN" if self.vs_ai else "LEFT WINS"
        else:
            banner = "AI WINS" if self.vs_ai else "RIGHT WINS"

        label = gameover_font.render(banner, True, WHITE)
        screen.blit(
            label, label.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50))
        )

        score = menu_font.render(
            f"{self.left_score}   -   {self.right_score}", True, DIMMED
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


def main():
    # The main loop. Each iteration: read events, advance the simulation, draw, present.
    pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, 512)
    pygame.init()
    sounds = init_sounds()

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Pong")
    clock = pygame.time.Clock()  # used to measure real elapsed time between frames

    # Pre-build the fonts once; creating them every frame would be slow. The dict keys
    # are used by the draw_* methods above.
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

        # 2) Draw the current state and present the finished frame to the window.
        game.draw(screen, fonts)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
