import array
import math
import random
import sys

import pygame

SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480

PADDLE_W = 12
PADDLE_H = 80
PADDLE_X = 24

PADDLE_SPEED = 540.0
AI_SPEED = 300.0

BALL_SIZE = 12
BALL_SPEED = 300.0
MAX_BALL_SPEED = 520.0
BALL_SPEED_UP = 1.06
MAX_BOUNCE_ANGLE = math.pi / 4

SAMPLE_RATE = 48000

WHITE = (255, 255, 255)
BG = (16, 16, 24)
DASH = (96, 96, 112)


def make_tone(freq, secs, vol=0.5):
    n = int(secs * SAMPLE_RATE)
    buf = array.array("h")
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-4 * t / secs)
        s = int(math.sin(2 * math.pi * freq * t) * env * vol * 32767)
        buf.append(s)
        buf.append(s)
    return pygame.mixer.Sound(buffer=buf.tobytes())


def init_sounds():
    try:
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2)
    except pygame.error:
        return {}
    return {
        "paddle": make_tone(440, 0.06, 0.5),
        "wall": make_tone(220, 0.05, 0.4),
        "score": make_tone(660, 0.18, 0.5),
    }


class Game:
    def __init__(self, sounds):
        self.left = pygame.Rect(PADDLE_X, SCREEN_HEIGHT // 2 - PADDLE_H // 2, PADDLE_W, PADDLE_H)
        self.right = pygame.Rect(SCREEN_WIDTH - PADDLE_X - PADDLE_W, SCREEN_HEIGHT // 2 - PADDLE_H // 2, PADDLE_W, PADDLE_H)
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
        self.paused = False
        self.sounds = sounds

        self.reset_ball(random.choice((-1.0, 1.0)))

    def play(self, name):
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    def reset_ball(self, direction):
        self.bx = SCREEN_WIDTH / 2 - BALL_SIZE / 2
        self.by = SCREEN_HEIGHT / 2 - BALL_SIZE / 2
        self.ball.x = int(self.bx)
        self.ball.y = int(self.by)
        self.speed = BALL_SPEED
        max_vy = BALL_SPEED * 0.7
        self.ball_vy = (random.random() * 2 - 1) * max_vy
        self.ball_vx = math.sqrt(BALL_SPEED * BALL_SPEED - self.ball_vy * self.ball_vy) * direction

    @staticmethod
    def clamp_y(y):
        return max(0.0, min(y, SCREEN_HEIGHT - PADDLE_H))

    def update_ai(self, dt):
        if self.ball_vx < 0:
            return
        target = self.ball.y + BALL_SIZE / 2 - PADDLE_H / 2
        diff = target - self.right_y
        step = AI_SPEED * dt
        if abs(diff) <= step:
            self.right_y = target
        else:
            self.right_y += math.copysign(step, diff)

    def bounce_off_paddle(self, paddle, direction):
        rel = (self.ball.y + BALL_SIZE / 2) - (paddle.y + PADDLE_H / 2)
        rel /= PADDLE_H / 2
        rel = max(-1.0, min(1.0, rel))
        self.speed = min(self.speed * BALL_SPEED_UP, MAX_BALL_SPEED)
        angle = rel * MAX_BOUNCE_ANGLE
        self.ball_vx = math.cos(angle) * self.speed * direction
        self.ball_vy = math.sin(angle) * self.speed

    def update(self, dt):
        if self.paused:
            return

        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:
            self.left_y -= PADDLE_SPEED * dt
        if keys[pygame.K_s]:
            self.left_y += PADDLE_SPEED * dt

        if self.vs_ai:
            self.update_ai(dt)
        else:
            if keys[pygame.K_UP]:
                self.right_y -= PADDLE_SPEED * dt
            if keys[pygame.K_DOWN]:
                self.right_y += PADDLE_SPEED * dt

        self.left_y = self.clamp_y(self.left_y)
        self.right_y = self.clamp_y(self.right_y)
        self.left.y = int(self.left_y)
        self.right.y = int(self.right_y)

        self.bx += self.ball_vx * dt
        self.by += self.ball_vy * dt

        if self.by <= 0:
            self.by = 0
            self.ball_vy = -self.ball_vy
            self.play("wall")
        if self.by + BALL_SIZE >= SCREEN_HEIGHT:
            self.by = SCREEN_HEIGHT - BALL_SIZE
            self.ball_vy = -self.ball_vy
            self.play("wall")

        self.ball.x = int(self.bx)
        self.ball.y = int(self.by)

        if self.ball_vx < 0 and self.ball.colliderect(self.left):
            self.bx = self.left.right
            self.bounce_off_paddle(self.left, 1)
            self.play("paddle")
        if self.ball_vx > 0 and self.ball.colliderect(self.right):
            self.bx = self.right.left - BALL_SIZE
            self.bounce_off_paddle(self.right, -1)
            self.play("paddle")

        if self.bx + BALL_SIZE < 0:
            self.right_score += 1
            self.play("score")
            self.reset_ball(-1)
        if self.bx > SCREEN_WIDTH:
            self.left_score += 1
            self.play("score")
            self.reset_ball(1)

    def draw(self, screen, score_font, hint_font):
        screen.fill(BG)

        for y in range(0, SCREEN_HEIGHT, 20):
            pygame.draw.rect(screen, DASH, (SCREEN_WIDTH // 2 - 2, y, 4, 12))

        pygame.draw.rect(screen, WHITE, self.left)
        pygame.draw.rect(screen, WHITE, self.right)
        pygame.draw.rect(screen, WHITE, self.ball)

        left_label = score_font.render(str(self.left_score), True, WHITE)
        right_label = score_font.render(str(self.right_score), True, WHITE)
        screen.blit(left_label, left_label.get_rect(center=(SCREEN_WIDTH // 2 - 30, 40)))
        screen.blit(right_label, right_label.get_rect(center=(SCREEN_WIDTH // 2 + 30, 40)))

        screen.blit(hint_font.render("W/S", True, WHITE), (24, SCREEN_HEIGHT - 24))
        if self.vs_ai:
            screen.blit(hint_font.render("AI (1)", True, WHITE), (SCREEN_WIDTH - 64, SCREEN_HEIGHT - 24))
        else:
            screen.blit(hint_font.render("UP/DOWN (2)", True, WHITE), (SCREEN_WIDTH - 110, SCREEN_HEIGHT - 24))

        if self.paused:
            label = hint_font.render("PAUSED - SPACE to resume", True, WHITE)
            screen.blit(label, label.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))


def main():
    pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, 512)
    pygame.init()
    sounds = init_sounds()

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Pong")
    clock = pygame.time.Clock()

    score_font = pygame.font.Font(None, 56)
    hint_font = pygame.font.Font(None, 22)

    game = Game(sounds)
    running = True

    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    game.paused = not game.paused
                elif event.key == pygame.K_r:
                    game.left_score = 0
                    game.right_score = 0
                    game.paused = False
                    game.reset_ball(random.choice((-1.0, 1.0)))
                elif event.key == pygame.K_1:
                    game.vs_ai = True
                elif event.key == pygame.K_2:
                    game.vs_ai = False

        game.update(dt)
        game.draw(screen, score_font, hint_font)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
