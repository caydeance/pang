"""Procedurally generated sound effects."""

import array
import math

import pygame

from config import SAMPLE_RATE


def make_tone(freq, duration, vol=0.5):
    n = int(SAMPLE_RATE * duration)
    buf = array.array("h")
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-4.0 * t / duration)
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
