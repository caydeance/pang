"""The simulation: paddle/ball physics, scoring, AI, and playfield rendering.

If you are a software developer but new to games, these are the ideas to keep in mind
while reading this class:

* Coordinates start at the TOP-LEFT. x grows to the right, y grows DOWNWARD. So "up"
  means decreasing y, and the bottom edge of this 480px-tall screen is y == 480.
* Speeds are in PIXELS PER SECOND and everything is integrated every step with
  `position += velocity * dt`. Working in per-second units is what lets the game behave
  the same whether the machine runs 30 or 300 simulation steps per second.
* `update(dt)` advances the simulation and `draw(...)` only paints the current state.
  Physics never reads input directly and drawing never mutates game state. main.py owns
  the loop that calls them.
* pygame paints onto a `Surface`. The window's display is itself a surface. Text is
  rendered to its own small surface before being blitted (drawn) somewhere.
* Collisions here are simple axis-aligned bounding boxes (`pygame.Rect`), which is more
  than enough for axis-aligned rectangles (paddles) and a square (the ball).
"""

import math
import random

import pygame

import menu
from ai import (
    AI_AIM_STRENGTH,
    AI_LEVELS,
    ai_aim_skill,
    ai_predict_blend,
    ai_predict_error,
    ai_speed,
)
from config import (
    BALL_SIZE,
    BALL_SPEED,
    BALL_SPEED_UP,
    BG,
    DASH,
    HIGHLIGHT,
    MAX_BALL_SPEED,
    MAX_BOUNCE_ANGLE,
    MAX_SHAKE,
    PADDLE_ACCEL,
    PADDLE_H,
    PADDLE_SPEED,
    PADDLE_W,
    PADDLE_X,
    PARTICLE_COUNT,
    PARTICLE_LIFE,
    PARTICLE_SPEED,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    State,
    TRAIL_LEN,
    TRAUMA_DECAY,
    WHITE,
    WIN_SCORE,
)
from utils import lerp_color


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
        opts = [vs_ai for _, vs_ai in menu.MENU_OPTIONS]
        idx = opts.index(self.vs_ai)
        idx = max(0, min(len(menu.MENU_OPTIONS) - 1, idx + delta))
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
            menu.draw_menu(screen, self, fonts)
            return

        if self.state == State.LEVELS:
            menu.draw_levels(screen, self, fonts)
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
            menu.draw_center_banner(screen, fonts, "PAUSED", "SPACE to resume")
        elif self.state == State.GAMEOVER:
            menu.draw_game_over(screen, self, fonts)

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
