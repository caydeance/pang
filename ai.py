"""Opponent AI, described as a set of independent abilities.

Rather than 15 hand-written opponents, the AI is one brain whose abilities fade in
progressively across the levels:

* how fast its paddle may move,
* how much it trusts a predicted landing spot versus just chasing the ball,
* how accurately it predicts, and
* whether it tries to aim the return away from the human.

Each `ai_*` function maps a level to a value in its range, which keeps the difficulty
curve easy to reason about and to tune.
"""

# --- Difficulty range ---------------------------------------------------------
AI_LEVELS = 15
AI_SPEED_MIN = 140.0  # slowest AI paddle speed (pixels/second)
AI_SPEED_MAX = 360.0  # fastest AI paddle speed (pixels/second)
AI_PREDICT_ERROR_MAX = 70.0  # largest random prediction error (pixels)
AI_PREDICT_ERROR_MIN = 4.0  # smallest random prediction error (pixels)
AI_AIM_STRENGTH = 0.85  # 0 = return flat, 1 = maximum aiming away from the human


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
