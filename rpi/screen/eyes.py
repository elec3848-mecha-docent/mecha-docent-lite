"""
screen/eyes.py — High-level eye animation helpers.

Wraps a Screen instance with named, blocking animation calls.
All durations are in seconds.

Usage:
    from screen.display import Screen
    from screen.eyes import Eyes

    screen = Screen()
    eyes = Eyes(screen)
    eyes.init()        # snap to default open position
    eyes.blink()
    eyes.look("left")
    eyes.squint()
    eyes.open()
"""

import time

from screen.display import Screen, EYE_SIZE, LID_SIZE

# ---------------------------------------------------------------------------
# Layout (1080p baseline — change to suit your resolution)
# ---------------------------------------------------------------------------

W, H = 1920, 1080

EYE_Y        = H // 2
EYE_L_X      = W // 2 - 220
EYE_R_X      = W // 2 + 220

LID_OPEN_Y   = EYE_Y - EYE_SIZE - LID_SIZE // 2 - 10   # fully open (hidden above)
LID_SHUT_Y   = EYE_Y                                     # fully closed (over eye)
LID_SQUINT_Y = EYE_Y - EYE_SIZE // 4                    # halfway down

LOOK_OFFSET  = 160   # px shift when looking left/right


class Eyes:
    def __init__(self, screen: Screen) -> None:
        self.screen = screen

    def init(self) -> None:
        """Snap all shapes to the default open position (no animation)."""
        s = self.screen
        s.eye_left.snap_to(EYE_L_X,  EYE_Y)
        s.eye_right.snap_to(EYE_R_X, EYE_Y)
        s.lid_left.snap_to(EYE_L_X,  LID_OPEN_Y)
        s.lid_right.snap_to(EYE_R_X, LID_OPEN_Y)

    def open(self, duration: float = 0.2) -> None:
        """Animate eyes to the fully open, centred position."""
        self.screen.move_all(
            eye_l_pos=(EYE_L_X, EYE_Y),
            eye_r_pos=(EYE_R_X, EYE_Y),
            lid_l_pos=(EYE_L_X, LID_OPEN_Y),
            lid_r_pos=(EYE_R_X, LID_OPEN_Y),
            duration=duration,
        )

    def blink(self, duration: float = 0.08) -> None:
        """Close lids, pause, then re-open. Blocks for the full blink duration."""
        s = self.screen
        s.move_all(
            lid_l_pos=(EYE_L_X, LID_SHUT_Y),
            lid_r_pos=(EYE_R_X, LID_SHUT_Y),
            duration=duration,
        )
        time.sleep(duration + 0.05)
        s.move_all(
            lid_l_pos=(EYE_L_X, LID_OPEN_Y),
            lid_r_pos=(EYE_R_X, LID_OPEN_Y),
            duration=duration,
        )

    def look(self, direction: str, duration: float = 0.2) -> None:
        """Slide eyes (and lids) left, right, or back to centre."""
        offset = {"left": -LOOK_OFFSET, "right": LOOK_OFFSET, "centre": 0}[direction]
        self.screen.move_all(
            eye_l_pos=(EYE_L_X + offset, EYE_Y),
            eye_r_pos=(EYE_R_X + offset, EYE_Y),
            lid_l_pos=(EYE_L_X + offset, LID_OPEN_Y),
            lid_r_pos=(EYE_R_X + offset, LID_OPEN_Y),
            duration=duration,
        )

    def squint(self, duration: float = 0.15) -> None:
        """Drop lids to the halfway position."""
        self.screen.move_all(
            lid_l_pos=(EYE_L_X, LID_SQUINT_Y),
            lid_r_pos=(EYE_R_X, LID_SQUINT_Y),
            duration=duration,
        )
