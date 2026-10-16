"""The simulation: paddle/ball physics, scoring, AI, and playfield rendering."""

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

        self.left_vy = 0.0
        self.right_vy = 0.0

        self.trauma = 0.0
        self.trail = []
        self.particles = []

        self.field = None

        self.reset_ball(1)

    def menu_move(self, delta):
        opts = [vs_ai for _, vs_ai in menu.MENU_OPTIONS]
        idx = opts.index(self.vs_ai)
        idx = max(0, min(len(menu.MENU_OPTIONS) - 1, idx + delta))
        self.vs_ai = opts[idx]

    def select_menu(self):
        if self.vs_ai:
            self.state = State.LEVELS
        else:
            self.start()

    def adjust_level(self, delta):
        self.ai_level = max(1, min(AI_LEVELS, self.ai_level + delta))

    def play(self, name):
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    def add_trauma(self, amount):
        self.trauma = min(1.0, self.trauma + amount)

    def shake_offset(self):
        if self.trauma <= 0:
            return 0, 0
        mag = MAX_SHAKE * self.trauma * self.trauma
        return (random.uniform(-mag, mag), random.uniform(-mag, mag))

    def spawn_particles(self, x, y):
        self.particles = []
        for _ in range(PARTICLE_COUNT):
            ang = random.uniform(0, 2 * math.pi)
            spd = random.uniform(0.3, 1.0) * PARTICLE_SPEED
            self.particles.append(
                [x, y, math.cos(ang) * spd, math.sin(ang) * spd, PARTICLE_LIFE, PARTICLE_LIFE]
            )

    def get_field(self):
        if self.field is None:
            self.field = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        return self.field

    def start(self):
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
        return max(0.0, min(y, SCREEN_HEIGHT - PADDLE_H))

    def predict_intercept(self, paddle_x):
        if self.ball_vx <= 0:
            return self.by
        t = (paddle_x - self.bx) / self.ball_vx
        return self.by + self.ball_vy * t

    def aim_target(self):
        intercept = self.predict_intercept(self.right.left) + BALL_SIZE / 2
        player_center = self.left_y + PADDLE_H / 2
        sign = 1.0 if player_center < SCREEN_HEIGHT / 2 else -1.0
        rel = sign * AI_AIM_STRENGTH
        paddle_center = intercept - rel * (PADDLE_H / 2)
        return self.clamp_y(paddle_center - PADDLE_H / 2)

    def update_ai(self, dt):
        if self.ball_vx <= 0:
            self.ai_predicted = False
            return

        track_target = self.by + BALL_SIZE / 2 - PADDLE_H / 2
        blend = ai_predict_blend(self.ai_level)
        if blend <= 0:
            target = track_target
        else:
            if not self.ai_predicted:
                err_mag = ai_predict_error(self.ai_level)
                self.ai_error = (random.random() * 2 - 1) * err_mag
                self.ai_predicted = True
            center = self.predict_intercept(self.right.left) + BALL_SIZE / 2
            pred_y = self.clamp_y(center + self.ai_error - PADDLE_H / 2)
            target = track_target + (pred_y - track_target) * blend

        aim = ai_aim_skill(self.ai_level)
        if aim > 0:
            target = target + (self.aim_target() - target) * aim

        self.move_ai_toward(target, dt, ai_speed(self.ai_level))

    def move_ai_toward(self, target, dt, speed):
        diff = target - self.right_y
        step = speed * dt
        if abs(diff) <= step:
            self.right_y = target
        else:
            self.right_y += math.copysign(step, diff)

    @staticmethod
    def approach(current, target, rate, dt):
        step = rate * dt
        if abs(target - current) <= step:
            return target
        return current + math.copysign(step, target - current)

    def bounce_off_paddle(self, paddle, direction):
        rel = (self.ball.y + BALL_SIZE / 2) - (paddle.y + PADDLE_H / 2)
        rel /= PADDLE_H / 2
        rel = max(-1.0, min(1.0, rel))
        self.speed = min(self.speed * BALL_SPEED_UP, MAX_BALL_SPEED)
        angle = rel * MAX_BOUNCE_ANGLE
        self.ball_vx = math.cos(angle) * self.speed * direction
        self.ball_vy = math.sin(angle) * self.speed

    def update(self, dt):
        keys = pygame.key.get_pressed()

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

        self.bx += self.ball_vx * dt
        self.by += self.ball_vy * dt

        if self.by <= 0:
            self.by = 0
            self.ball_vy = -self.ball_vy
            self.ai_predicted = False
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

        self.trail.append((self.bx, self.by))
        if len(self.trail) > TRAIL_LEN:
            self.trail.pop(0)

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

        self.trauma = max(0.0, self.trauma - TRAUMA_DECAY * dt)
        self._update_particles(dt)

    def _update_particles(self, dt):
        alive = []
        for p in self.particles:
            p[4] -= dt
            if p[4] <= 0:
                continue
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            drag = 1.0 - 3.0 * dt
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
        screen.fill(BG)

        if self.state == State.MENU:
            menu.draw_menu(screen, self, fonts)
            return

        if self.state == State.LEVELS:
            menu.draw_levels(screen, self, fonts)
            return

        field = self.get_field()
        field.fill(BG)

        for y in range(0, SCREEN_HEIGHT, 20):
            pygame.draw.rect(field, DASH, (SCREEN_WIDTH // 2 - 2, y, 4, 12))

        self.draw_trail(field)

        pygame.draw.rect(field, WHITE, self.left)
        pygame.draw.rect(field, WHITE, self.right)
        pygame.draw.rect(field, WHITE, self.ball)

        self.draw_particles(field)

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

        ox, oy = self.shake_offset()
        screen.blit(field, (ox, oy))

        if self.state == State.PAUSED:
            menu.draw_center_banner(screen, fonts, "PAUSED", "SPACE to resume")
        elif self.state == State.GAMEOVER:
            menu.draw_game_over(screen, self, fonts)

    def draw_trail(self, surface):
        n = len(self.trail)
        for i, (tx, ty) in enumerate(self.trail):
            frac = (i + 1) / n
            color = lerp_color(BG, WHITE, frac * 0.6)
            radius = max(1, int(BALL_SIZE / 2 * (0.25 + 0.75 * frac)))
            center = (int(tx + BALL_SIZE / 2), int(ty + BALL_SIZE / 2))
            pygame.draw.circle(surface, color, center, radius)

    def draw_particles(self, surface):
        for px, py, _vx, _vy, life, max_life in self.particles:
            frac = max(0.0, life / max_life)
            color = lerp_color(BG, HIGHLIGHT, frac)
            pygame.draw.circle(surface, color, (int(px), int(py)), 1 + int(3 * frac))
