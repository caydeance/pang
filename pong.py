import array
import math
import random
import sys
from enum import Enum, auto

import pygame

SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480

PADDLE_W = 12
PADDLE_H = 80
PADDLE_X = 24

PADDLE_SPEED = 540.0

BALL_SIZE = 12
BALL_SPEED = 300.0
MAX_BALL_SPEED = 640.0
BALL_SPEED_UP = 1.06
MAX_BOUNCE_ANGLE = math.pi / 3

WIN_SCORE = 7

FIXED_DT = 1.0 / 120.0
MAX_FRAME_TIME = 0.25

AI_LEVELS = 15
AI_SPEED_MIN = 140.0
AI_SPEED_MAX = 360.0

AI_PREDICT_ERROR_MAX = 70.0
AI_PREDICT_ERROR_MIN = 4.0

AI_AIM_STRENGTH = 0.85

SAMPLE_RATE = 48000

WHITE = (255, 255, 255)
BG = (16, 16, 24)
DASH = (96, 96, 112)
DIMMED = (128, 128, 144)
HIGHLIGHT = (120, 200, 255)


class State(Enum):
    MENU = auto()
    LEVELS = auto()
    PLAYING = auto()
    PAUSED = auto()
    GAMEOVER = auto()


MENU_OPTIONS = [
    ("Player vs AI", True),
    ("Two Players", False),
]


def _ramp(level, lo, hi):
    if hi <= lo:
        return 1.0 if level >= hi else 0.0
    return max(0.0, min(1.0, (level - lo) / (hi - lo)))


def ai_speed(level):
    return AI_SPEED_MIN + (AI_SPEED_MAX - AI_SPEED_MIN) * _ramp(level, 3, 7)


def ai_predict_blend(level):
    return _ramp(level, 6, 10)


def ai_predict_error(level):
    t = _ramp(level, 6, 15)
    return AI_PREDICT_ERROR_MAX + (AI_PREDICT_ERROR_MIN - AI_PREDICT_ERROR_MAX) * t


def ai_aim_skill(level):
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
        "win": make_tone(880, 0.35, 0.5),
    }


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

        self.reset_ball(1)

    def menu_move(self, delta):
        opts = [vs_ai for _, vs_ai in MENU_OPTIONS]
        idx = opts.index(self.vs_ai)
        idx = max(0, min(len(MENU_OPTIONS) - 1, idx + delta))
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

    def start(self):
        self.left_score = 0
        self.right_score = 0
        self.winner = None
        self.left_y = SCREEN_HEIGHT / 2 - PADDLE_H / 2
        self.right_y = SCREEN_HEIGHT / 2 - PADDLE_H / 2
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
                self.ai_error = (random.random() * 2 - 1) * ai_predict_error(
                    self.ai_level
                )
                self.ai_predicted = True
            center = self.predict_intercept(self.right.left) + BALL_SIZE / 2
            self.ai_target_y = self.clamp_y(center + self.ai_error - PADDLE_H / 2)
            target = track_target + (self.ai_target_y - track_target) * blend

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
            self.ai_predicted = False
            self.play("wall")
        if self.by + BALL_SIZE >= SCREEN_HEIGHT:
            self.by = SCREEN_HEIGHT - BALL_SIZE
            self.ball_vy = -self.ball_vy
            self.ai_predicted = False
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
            self.check_game_over()
            if self.state == State.PLAYING:
                self.reset_ball(1)
        if self.bx > SCREEN_WIDTH:
            self.left_score += 1
            self.play("score")
            self.check_game_over()
            if self.state == State.PLAYING:
                self.reset_ball(-1)

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
            self.draw_menu(screen, fonts)
            return

        if self.state == State.LEVELS:
            self.draw_levels(screen, fonts)
            return

        for y in range(0, SCREEN_HEIGHT, 20):
            pygame.draw.rect(screen, DASH, (SCREEN_WIDTH // 2 - 2, y, 4, 12))

        pygame.draw.rect(screen, WHITE, self.left)
        pygame.draw.rect(screen, WHITE, self.right)
        pygame.draw.rect(screen, WHITE, self.ball)

        score_font = fonts["score"]
        hint_font = fonts["hint"]

        left_label = score_font.render(str(self.left_score), True, WHITE)
        right_label = score_font.render(str(self.right_score), True, WHITE)
        screen.blit(
            left_label, left_label.get_rect(center=(SCREEN_WIDTH // 2 - 30, 40))
        )
        screen.blit(
            right_label, right_label.get_rect(center=(SCREEN_WIDTH // 2 + 30, 40))
        )

        screen.blit(hint_font.render("W/S", True, WHITE), (24, SCREEN_HEIGHT - 24))
        if self.vs_ai:
            screen.blit(
                hint_font.render(f"AI Lv{self.ai_level}", True, WHITE),
                (SCREEN_WIDTH - 84, SCREEN_HEIGHT - 24),
            )
        else:
            screen.blit(
                hint_font.render("UP/DOWN", True, WHITE),
                (SCREEN_WIDTH - 84, SCREEN_HEIGHT - 24),
            )

        if self.state == State.PAUSED:
            self.draw_center_banner(screen, fonts, "PAUSED", "SPACE to resume")
        elif self.state == State.GAMEOVER:
            self.draw_game_over(screen, fonts)

    def draw_center_banner(self, screen, fonts, title, subtitle):
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

        num_font = pygame.font.Font(None, 150)
        number = num_font.render(str(self.ai_level), True, HIGHLIGHT)
        screen.blit(number, number.get_rect(center=(SCREEN_WIDTH // 2, 195)))

        tag = menu_font.render(level_tag(self.ai_level), True, WHITE)
        screen.blit(tag, tag.get_rect(center=(SCREEN_WIDTH // 2, 285)))

        desc = hint_font.render(level_description(self.ai_level), True, DIMMED)
        screen.blit(desc, desc.get_rect(center=(SCREEN_WIDTH // 2, 320)))

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

        again = hint_font.render("R  Play again", True, WHITE)
        screen.blit(
            again, again.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 60))
        )
        back = hint_font.render("ESC  Menu", True, DIMMED)
        screen.blit(
            back, back.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 84))
        )


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
