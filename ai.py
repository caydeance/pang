"""AI difficulty curve."""

AI_LEVELS = 15
AI_SPEED_MIN = 140.0
AI_SPEED_MAX = 360.0
AI_PREDICT_ERROR_MAX = 70.0
AI_PREDICT_ERROR_MIN = 4.0
AI_AIM_STRENGTH = 0.85


def _ramp(level, lo, hi):
    """Map a level to a 0..1 progress value, interpolating between lo and hi."""
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
