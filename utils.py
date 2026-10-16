"""Small helpers shared by the other modules."""


def lerp_color(c1, c2, t):
    """Linear blend between two RGB colors.

    `t` runs from 0 (all c1) to 1 (all c2). Used to fade things toward the background
    color instead of dealing with per-pixel alpha.
    """
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))
