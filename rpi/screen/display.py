"""
screen/display.py — Fullscreen cv2 face display.

Six shapes on a BG_COLOR background:
    eye_left, eye_right            — rounded rectangles of EYE_COLOR
    lid_top_left, lid_top_right    — top eyelids (BG_COLOR rectangles)
    lid_bottom_left, lid_bottom_right — bottom eyelids (BG_COLOR rectangles)

Configure initial positions via shape.snap_to() or direct attribute
assignment, then call Screen.run() to enter the render loop.

Animations use cubic ease-in-out (smoothstep). Trigger them with:
  screen.move_eye_left(x, y, rotation, duration)
  screen.move_eye_right(...)
    screen.move_lid_top_left(...)
    screen.move_lid_top_right(...)
    screen.move_lid_bottom_left(...)
    screen.move_lid_bottom_right(...)
    screen.move_all(
            eye_l_pos, eye_r_pos,
            lid_tl_pos, lid_tr_pos,
            lid_bl_pos, lid_br_pos,
            duration,
    )
    screen.move_group(dx, dy, duration)

Each shape also exposes:
  shape.animate_to(x, y, rotation, duration)   — eased movement
  shape.snap_to(x, y, rotation)                — instant, no animation
"""

import time

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Configurable constants — edit these to style the display
# ---------------------------------------------------------------------------

BG_COLOR: tuple  = (138,  158,  81)   # BGR background + eyelid fill
EYE_COLOR: tuple = (56, 40, 39)  # BGR eye fill

EYE_WIDTH:     int = 140   # width of each eye rounded rectangle (px)
EYE_HEIGHT:    int = 500   # height of each eye rounded rectangle (px)
LID_WIDTH:     int = 150   # width of each eyelid rectangle (px)
LID_HEIGHT:    int = 600   # height of each eyelid rectangle (px)
CORNER_RADIUS: int = 60    # corner radius of the rounded eye rectangles

# Backward-compatible aliases (prefer *_WIDTH/*_HEIGHT)
EYE_SIZE: int = EYE_HEIGHT
LID_SIZE: int = LID_HEIGHT

FPS: int = 60

# ---------------------------------------------------------------------------
# Easing
# ---------------------------------------------------------------------------

def ease_in_out(t: float) -> float:
    """Cubic ease-in-out (smoothstep)."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)

# ---------------------------------------------------------------------------
# Canvas helpers
# ---------------------------------------------------------------------------

def _make_rounded_rect(
    width: int,
    height: int,
    corner_radius: int,
    color: tuple,
) -> np.ndarray:
    """Return a BGRA ndarray with a filled, anti-aliased rounded rectangle."""
    canvas = np.zeros((height, width, 4), dtype=np.uint8)
    r = min(corner_radius, width // 2, height // 2)
    bgra = (int(color[0]), int(color[1]), int(color[2]), 255)
    cv2.rectangle(canvas, (r, 0), (width - r, height), bgra, -1)
    cv2.rectangle(canvas, (0, r), (width, height - r), bgra, -1)
    for cx, cy in [(r, r), (width - r, r), (r, height - r), (width - r, height - r)]:
        cv2.circle(canvas, (cx, cy), r, bgra, -1)
    return canvas


def _make_rect(width: int, height: int, color: tuple) -> np.ndarray:
    """Return a BGRA ndarray with a plain filled rectangle."""
    canvas = np.zeros((height, width, 4), dtype=np.uint8)
    canvas[:, :] = (int(color[0]), int(color[1]), int(color[2]), 255)
    return canvas


def _composite(
    frame: np.ndarray,
    overlay: np.ndarray,
    cx: int,
    cy: int,
    angle: float,
) -> None:
    """Alpha-composite a BGRA overlay (rotated by `angle` degrees) onto a
    BGR frame, centred at pixel (cx, cy)."""
    oh, ow = overlay.shape[:2]
    M = cv2.getRotationMatrix2D((ow / 2.0, oh / 2.0), -angle, 1.0)
    rotated = cv2.warpAffine(
        overlay, M, (ow, oh),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )

    x1, y1 = cx - ow // 2, cy - oh // 2
    x2, y2 = x1 + ow,      y1 + oh

    fx1 = max(0, x1);  fy1 = max(0, y1)
    fx2 = min(frame.shape[1], x2);  fy2 = min(frame.shape[0], y2)
    if fx2 <= fx1 or fy2 <= fy1:
        return

    rx1, ry1 = fx1 - x1, fy1 - y1
    rx2, ry2 = rx1 + (fx2 - fx1), ry1 + (fy2 - fy1)

    src   = rotated[ry1:ry2, rx1:rx2]
    alpha = src[:, :, 3:4].astype(np.float32) / 255.0
    dst   = frame[fy1:fy2, fx1:fx2].astype(np.float32)
    frame[fy1:fy2, fx1:fx2] = (
        alpha * src[:, :, :3] + (1.0 - alpha) * dst
    ).astype(np.uint8)

# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------

class Shape:
    """A display shape with an animatable position and rotation."""

    def __init__(self, x: float = 0.0, y: float = 0.0, rotation: float = 0.0):
        self.x        = x
        self.y        = y
        self.rotation = rotation          # degrees
        self._anim    = None              # type: tuple | None

    # -- public API ----------------------------------------------------------

    def animate_to(
        self,
        end_x:        float,
        end_y:        float,
        end_rotation: float = 0.0,
        duration:     float = 0.5,
    ) -> None:
        """Smoothly move to (end_x, end_y, end_rotation) over `duration` seconds
        using cubic ease-in-out, starting from the current position."""
        self._anim = (
            self.x, self.y, self.rotation,
            end_x,  end_y,  end_rotation,
            time.monotonic(), duration,
        )

    def snap_to(
        self,
        x:        float,
        y:        float,
        rotation: float = 0.0,
    ) -> None:
        """Instantly place the shape at (x, y, rotation), cancelling any
        ongoing animation."""
        self.x, self.y, self.rotation = x, y, rotation
        self._anim = None

    # -- internal ------------------------------------------------------------

    def update(self) -> None:
        if self._anim is None:
            return
        sx, sy, sr, ex, ey, er, t0, dur = self._anim
        progress = (time.monotonic() - t0) / dur if dur > 0.0 else 1.0
        if progress >= 1.0:
            self.x, self.y, self.rotation = ex, ey, er
            self._anim = None
            return
        f = ease_in_out(progress)
        self.x        = sx + (ex - sx) * f
        self.y        = sy + (ey - sy) * f
        self.rotation = sr + (er - sr) * f

# ---------------------------------------------------------------------------
# Screen
# ---------------------------------------------------------------------------

class Screen:
    """
    Fullscreen OpenCV display.

    Shapes (set starting positions before calling run()):
        eye_left, eye_right  — rounded rectangles of EYE_COLOR
        lid_top_left, lid_top_right       — top eyelids of BG_COLOR
        lid_bottom_left, lid_bottom_right — bottom eyelids of BG_COLOR

    Example setup:
        screen = Screen()
        # positions are in pixels; origin is top-left
        screen.eye_left.snap_to(760, 540)
        screen.eye_right.snap_to(1160, 540)
        screen.lid_top_left.snap_to(760, 390)   # above the left eye = open
        screen.lid_top_right.snap_to(1160, 390)
        screen.lid_bottom_left.snap_to(760, 790)
        screen.lid_bottom_right.snap_to(1160, 790)
        screen.run()
    """

    def __init__(self, width: int = 0, height: int = 0, fps: int = FPS):
        self.fps    = fps
        self.width  = width
        self.height = height

        # Shapes — set positions with snap_to() before calling run()
        self.eye_left  = Shape()
        self.eye_right = Shape()
        self.lid_top_left = Shape()
        self.lid_top_right = Shape()
        self.lid_bottom_left = Shape()
        self.lid_bottom_right = Shape()

        # Backward-compatible aliases for older top-lid names.
        self.lid_left = self.lid_top_left
        self.lid_right = self.lid_top_right

        # Foreground translation layer (applied to eyes/lids only)
        self._group_offset = Shape()

        # Pre-rendered canvases (rebuilt if size/color constants change)
        self._eye_canvas = _make_rounded_rect(
            EYE_WIDTH, EYE_HEIGHT, CORNER_RADIUS, EYE_COLOR
        )
        self._lid_canvas = _make_rect(LID_WIDTH, LID_HEIGHT, BG_COLOR)

    def rebuild_canvases(self) -> None:
        """Call this if you change any eye/lid size constants, CORNER_RADIUS,
        or colors at runtime before run()."""
        self._eye_canvas = _make_rounded_rect(
            EYE_WIDTH, EYE_HEIGHT, CORNER_RADIUS, EYE_COLOR
        )
        self._lid_canvas = _make_rect(LID_WIDTH, LID_HEIGHT, BG_COLOR)

    # -----------------------------------------------------------------------
    # Animation helpers
    # -----------------------------------------------------------------------

    def move_eye_left(
        self, x: float, y: float, rotation: float = 0.0, duration: float = 0.5
    ) -> None:
        self.eye_left.animate_to(x, y, rotation, duration)

    def move_eye_right(
        self, x: float, y: float, rotation: float = 0.0, duration: float = 0.5
    ) -> None:
        self.eye_right.animate_to(x, y, rotation, duration)

    def move_lid_top_left(
        self, x: float, y: float, rotation: float = 0.0, duration: float = 0.5
    ) -> None:
        self.lid_top_left.animate_to(x, y, rotation, duration)

    def move_lid_top_right(
        self, x: float, y: float, rotation: float = 0.0, duration: float = 0.5
    ) -> None:
        self.lid_top_right.animate_to(x, y, rotation, duration)

    def move_lid_bottom_left(
        self, x: float, y: float, rotation: float = 0.0, duration: float = 0.5
    ) -> None:
        self.lid_bottom_left.animate_to(x, y, rotation, duration)

    def move_lid_bottom_right(
        self, x: float, y: float, rotation: float = 0.0, duration: float = 0.5
    ) -> None:
        self.lid_bottom_right.animate_to(x, y, rotation, duration)

    def move_lid_left(
        self, x: float, y: float, rotation: float = 0.0, duration: float = 0.5
    ) -> None:
        """Backward-compatible alias for move_lid_top_left."""
        self.move_lid_top_left(x, y, rotation, duration)

    def move_lid_right(
        self, x: float, y: float, rotation: float = 0.0, duration: float = 0.5
    ) -> None:
        """Backward-compatible alias for move_lid_top_right."""
        self.move_lid_top_right(x, y, rotation, duration)

    def move_all(
        self,
        eye_l_pos = None,
        eye_r_pos = None,
        lid_tl_pos = None,
        lid_tr_pos = None,
        lid_bl_pos = None,
        lid_br_pos = None,
        duration:  float = 0.5,
        **legacy_kwargs,
    ) -> None:
        """Animate any combination of shapes simultaneously.

        Each *_pos argument is (x, y) or (x, y, rotation).
        Passing None for a shape leaves it untouched.
        """
        # Backward-compatible mapping from legacy top-lid names.
        if lid_tl_pos is None and "lid_l_pos" in legacy_kwargs:
            lid_tl_pos = legacy_kwargs["lid_l_pos"]
        if lid_tr_pos is None and "lid_r_pos" in legacy_kwargs:
            lid_tr_pos = legacy_kwargs["lid_r_pos"]

        def _apply(shape: Shape, pos):
            if pos is None:
                return
            x, y = pos[0], pos[1]
            r = pos[2] if len(pos) > 2 else 0.0
            shape.animate_to(x, y, r, duration)

        _apply(self.eye_left,  eye_l_pos)
        _apply(self.eye_right, eye_r_pos)
        _apply(self.lid_top_left, lid_tl_pos)
        _apply(self.lid_top_right, lid_tr_pos)
        _apply(self.lid_bottom_left, lid_bl_pos)
        _apply(self.lid_bottom_right, lid_br_pos)

    def move_group(self, dx: float = 0.0, dy: float = 0.0, duration: float = 0.5) -> None:
        """Translate all foreground shapes together by (dx, dy).

        This keeps eye/lid spacing unchanged while moving the whole face.
        """
        self._group_offset.update()
        self._group_offset.animate_to(
            self._group_offset.x + dx,
            self._group_offset.y + dy,
            self._group_offset.rotation,
            duration,
        )

    def get_group_offset(self) -> tuple[float, float]:
        """Return the current foreground translation offset."""
        self._group_offset.update()
        return self._group_offset.x, self._group_offset.y

    # -----------------------------------------------------------------------
    # Render internals
    # -----------------------------------------------------------------------

    def _update(self) -> None:
        self._group_offset.update()
        for shape in (
            self.eye_left,
            self.eye_right,
            self.lid_top_left,
            self.lid_top_right,
            self.lid_bottom_left,
            self.lid_bottom_right,
        ):
            shape.update()

    def _render(self, frame: np.ndarray) -> None:
        frame[:] = BG_COLOR
        gx, gy = int(self._group_offset.x), int(self._group_offset.y)
        # Eyes drawn first so lids can cover them
        _composite(frame, self._eye_canvas,
                   int(self.eye_left.x) + gx,  int(self.eye_left.y) + gy,  self.eye_left.rotation)
        _composite(frame, self._eye_canvas,
                   int(self.eye_right.x) + gx, int(self.eye_right.y) + gy, self.eye_right.rotation)
        _composite(frame, self._lid_canvas,
                   int(self.lid_top_left.x) + gx,  int(self.lid_top_left.y) + gy,  self.lid_top_left.rotation)
        _composite(frame, self._lid_canvas,
                   int(self.lid_top_right.x) + gx, int(self.lid_top_right.y) + gy, self.lid_top_right.rotation)
        _composite(frame, self._lid_canvas,
                   int(self.lid_bottom_left.x) + gx,  int(self.lid_bottom_left.y) + gy,  self.lid_bottom_left.rotation)
        _composite(frame, self._lid_canvas,
                   int(self.lid_bottom_right.x) + gx, int(self.lid_bottom_right.y) + gy, self.lid_bottom_right.rotation)

    def _detect_screen_size(self, win: str) -> None:
        """Use a dummy imshow to ask cv2 the actual fullscreen resolution."""
        tmp = np.zeros((1, 1, 3), dtype=np.uint8)
        cv2.imshow(win, tmp)
        cv2.waitKey(1)
        rect = cv2.getWindowImageRect(win)
        if rect[2] > 0 and rect[3] > 0:
            self.width, self.height = rect[2], rect[3]
        else:
            # Fallback if getWindowImageRect is not supported
            self.width, self.height = 1920, 1080

    # -----------------------------------------------------------------------
    # Run loop
    # -----------------------------------------------------------------------

    def run(self) -> None:
        """Open the fullscreen window and enter the render loop.
        Press ESC to quit."""
        win = "mecha-docent"
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(win, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

        if self.width == 0 or self.height == 0:
            self._detect_screen_size(win)

        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        delay = max(1, 1000 // self.fps)

        while True:
            self._update()
            self._render(frame)
            cv2.imshow(win, frame)
            key = cv2.waitKey(delay) & 0xFF
            if key in (27, ord('q')):   # ESC or q
                break

        cv2.destroyAllWindows()
