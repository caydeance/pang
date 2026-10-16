"""Procedurally generated sound effects.

The effects are synthesised in code instead of shipping audio files, so there are no
assets to manage. `make_tone` builds one short sine tone; `init_sounds` wires up a small
named set of them.
"""

import array
import math

import pygame

from config import SAMPLE_RATE


def make_tone(freq, duration, vol=0.5):
    """Build a single sine-wave blip as a pygame Sound.

    A raw sample is just a number; a sound is a sequence of them. Each sample is a sine
    wave multiplied by an exponential decay ("envelope") so the tone fades out instead of
    clicking off. We write each value twice, making the mono signal stereo, and use
    signed 16-bit integers ("h") which is what `init_sounds` asks the mixer for.
    """
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
    # Returns a dict of named sounds. If no audio device is available (headless CI, for
    # example), return an empty dict so the game still runs silently.
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
