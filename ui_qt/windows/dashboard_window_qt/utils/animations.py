# ui_qt/windows/dashboard_window_qt/utils/animations.py
"""
Animations and Effects Module - Hiệu ứng và hoạt ảnh cho Dashboard
Bao gồm: Fade, Slide, Bounce, Scale, Rotate, Blur, Glow, và các hiệu ứng đặc biệt
"""

from typing import Optional, Union, Callable, List, Tuple, Any
from enum import Enum
import math
import logging

from PySide6.QtCore import (
    QObject, QTimer, QRect, QPoint, QSize, QPointF, QRectF,
    Signal, Property, QPropertyAnimation, QEasingCurve,
    QParallelAnimationGroup, QSequentialAnimationGroup,
    QAbstractAnimation, QPauseAnimation, QVariantAnimation
)
from PySide6.QtWidgets import (
    QWidget, QGraphicsOpacityEffect, QGraphicsDropShadowEffect,
    QGraphicsBlurEffect, QGraphicsColorizeEffect, QGraphicsEffect
)
from PySide6.QtGui import (
    QColor, QPainter, QBrush, QPen, QLinearGradient,
    QRadialGradient, QConicalGradient, QTransform, QPixmap
)

# Import constants
try:
    from .constants import (
        ANIMATION_DURATION_FAST, ANIMATION_DURATION_NORMAL,
        ANIMATION_DURATION_SLOW, FADE_DURATION, SLIDE_DURATION,
        BOUNCE_DURATION
    )
except ImportError:
    # Fallback values
    ANIMATION_DURATION_FAST = 150
    ANIMATION_DURATION_NORMAL = 300
    ANIMATION_DURATION_SLOW = 500
    FADE_DURATION = 200
    SLIDE_DURATION = 250
    BOUNCE_DURATION = 400

# Logger
logger = logging.getLogger(__name__)


# ========== ENUMS ==========

class AnimationType(Enum):
    """Animation types"""
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    SLIDE_IN = "slide_in"
    SLIDE_OUT = "slide_out"
    BOUNCE = "bounce"
    SCALE = "scale"
    ROTATE = "rotate"
    SHAKE = "shake"
    PULSE = "pulse"
    FLIP = "flip"


class Direction(Enum):
    """Animation directions"""
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"
    CENTER = "center"


class EffectType(Enum):
    """Visual effects"""
    SHADOW = "shadow"
    BLUR = "blur"
    GLOW = "glow"
    COLORIZE = "colorize"
    GLASS = "glass"


# ========== BASE ANIMATION CLASS ==========

class BaseAnimation(QObject):
    """Base class for custom animations"""

    # Signals
    started = Signal()
    finished = Signal()
    valueChanged = Signal(object)

    def __init__(self, widget: QWidget = None, duration: int = ANIMATION_DURATION_NORMAL, parent=None):
        super().__init__(parent)

        self.widget = widget
        self.duration = duration
        self.animation = None
        self.is_running = False

    def start(self):
        """Start animation"""
        if self.animation and not self.is_running:
            self.animation.start()
            self.is_running = True
            self.started.emit()

    def stop(self):
        """Stop animation"""
        if self.animation and self.is_running:
            self.animation.stop()
            self.is_running = False

    def pause(self):
        """Pause animation"""
        if self.animation and self.is_running:
            self.animation.pause()

    def resume(self):
        """Resume animation"""
        if self.animation:
            self.animation.resume()

    def set_duration(self, duration: int):
        """Set animation duration"""
        self.duration = duration
        if self.animation:
            self.animation.setDuration(duration)

    def set_easing_curve(self, curve: QEasingCurve):
        """Set easing curve"""
        if self.animation:
            self.animation.setEasingCurve(curve)

    def _on_finished(self):
        """Handle animation finished"""
        self.is_running = False
        self.finished.emit()


# ========== FADE ANIMATIONS ==========

class FadeAnimation(BaseAnimation):
    """Fade in/out animation"""

    def __init__(self, widget: QWidget, fade_in: bool = True,
                 start_opacity: float = 0.0, end_opacity: float = 1.0,
                 duration: int = FADE_DURATION, parent=None):
        super().__init__(widget, duration, parent)

        self.fade_in = fade_in
        self.start_opacity = start_opacity if not fade_in else end_opacity
        self.end_opacity = end_opacity if not fade_in else start_opacity

        # Create opacity effect if not exists
        if not widget.graphicsEffect():
            self.opacity_effect = QGraphicsOpacityEffect()
            widget.setGraphicsEffect(self.opacity_effect)
        else:
            self.opacity_effect = widget.graphicsEffect()

        # Create animation
        self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.animation.setDuration(self.duration)
        self.animation.setStartValue(self.start_opacity)
        self.animation.setEndValue(self.end_opacity)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)

        # Connect signals
        self.animation.finished.connect(self._on_finished)
        self.animation.valueChanged.connect(lambda v: self.valueChanged.emit(v))


def fade_in(widget: QWidget, duration: int = FADE_DURATION,
            callback: Optional[Callable] = None) -> FadeAnimation:
    """
    Fade in a widget

    Args:
        widget: Widget to animate
        duration: Animation duration in ms
        callback: Function to call when finished

    Returns:
        FadeAnimation instance
    """
    anim = FadeAnimation(widget, fade_in=True, duration=duration)
    if callback:
        anim.finished.connect(callback)
    anim.start()
    return anim


def fade_out(widget: QWidget, duration: int = FADE_DURATION,
             callback: Optional[Callable] = None, hide_after: bool = True) -> FadeAnimation:
    """
    Fade out a widget

    Args:
        widget: Widget to animate
        duration: Animation duration in ms
        callback: Function to call when finished
        hide_after: Hide widget after fade out

    Returns:
        FadeAnimation instance
    """
    anim = FadeAnimation(widget, fade_in=False, duration=duration)
    if hide_after:
        anim.finished.connect(widget.hide)
    if callback:
        anim.finished.connect(callback)
    anim.start()
    return anim


def fade_in_animation(widget: QWidget, duration: int = FADE_DURATION) -> QPropertyAnimation:
    """Create fade in animation (legacy compatibility)"""
    effect = QGraphicsOpacityEffect()
    widget.setGraphicsEffect(effect)

    animation = QPropertyAnimation(effect, b"opacity")
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.InOutQuad)

    return animation


# ========== SLIDE ANIMATIONS ==========

class SlideAnimation(BaseAnimation):
    """Slide animation"""

    def __init__(self, widget: QWidget, direction: Direction = Direction.LEFT,
                 distance: int = 100, duration: int = SLIDE_DURATION, parent=None):
        super().__init__(widget, duration, parent)

        self.direction = direction
        self.distance = distance
        self.start_pos = widget.pos()
        self.end_pos = self._calculate_end_position()

        # Create animation
        self.animation = QPropertyAnimation(widget, b"pos")
        self.animation.setDuration(self.duration)
        self.animation.setStartValue(self.start_pos)
        self.animation.setEndValue(self.end_pos)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

        # Connect signals
        self.animation.finished.connect(self._on_finished)
        self.animation.valueChanged.connect(lambda v: self.valueChanged.emit(v))

    def _calculate_end_position(self) -> QPoint:
        """Calculate end position based on direction"""
        pos = self.start_pos

        if self.direction == Direction.LEFT:
            return QPoint(pos.x() - self.distance, pos.y())
        elif self.direction == Direction.RIGHT:
            return QPoint(pos.x() + self.distance, pos.y())
        elif self.direction == Direction.UP:
            return QPoint(pos.x(), pos.y() - self.distance)
        elif self.direction == Direction.DOWN:
            return QPoint(pos.x(), pos.y() + self.distance)
        else:
            return pos


def slide_in(widget: QWidget, direction: Direction = Direction.LEFT,
             distance: int = 100, duration: int = SLIDE_DURATION) -> SlideAnimation:
    """
    Slide in a widget from direction

    Args:
        widget: Widget to animate
        direction: Slide direction
        distance: Slide distance in pixels
        duration: Animation duration in ms

    Returns:
        SlideAnimation instance
    """
    # Set initial position
    start_pos = widget.pos()
    if direction == Direction.LEFT:
        widget.move(start_pos.x() + distance, start_pos.y())
    elif direction == Direction.RIGHT:
        widget.move(start_pos.x() - distance, start_pos.y())
    elif direction == Direction.UP:
        widget.move(start_pos.x(), start_pos.y() + distance)
    elif direction == Direction.DOWN:
        widget.move(start_pos.x(), start_pos.y() - distance)

    # Reverse direction for slide in
    reverse_dir = {
        Direction.LEFT: Direction.RIGHT,
        Direction.RIGHT: Direction.LEFT,
        Direction.UP: Direction.DOWN,
        Direction.DOWN: Direction.UP
    }.get(direction, direction)

    anim = SlideAnimation(widget, reverse_dir, distance, duration)
    widget.show()
    anim.start()
    return anim


def slide_out(widget: QWidget, direction: Direction = Direction.LEFT,
              distance: int = 100, duration: int = SLIDE_DURATION,
              hide_after: bool = True) -> SlideAnimation:
    """
    Slide out a widget to direction

    Args:
        widget: Widget to animate
        direction: Slide direction
        distance: Slide distance in pixels
        duration: Animation duration in ms
        hide_after: Hide widget after slide out

    Returns:
        SlideAnimation instance
    """
    anim = SlideAnimation(widget, direction, distance, duration)
    if hide_after:
        anim.finished.connect(widget.hide)
    anim.start()
    return anim


def slide_in_animation(widget: QWidget, start_pos: QPoint, end_pos: QPoint,
                       duration: int = SLIDE_DURATION) -> QPropertyAnimation:
    """Create slide animation (legacy compatibility)"""
    animation = QPropertyAnimation(widget, b"pos")
    animation.setDuration(duration)
    animation.setStartValue(start_pos)
    animation.setEndValue(end_pos)
    animation.setEasingCurve(QEasingCurve.OutCubic)

    return animation


# ========== BOUNCE ANIMATION ==========

class BounceAnimation(BaseAnimation):
    """Bounce animation"""

    def __init__(self, widget: QWidget, height: int = 20,
                 duration: int = BOUNCE_DURATION, parent=None):
        super().__init__(widget, duration, parent)

        self.height = height
        self.original_pos = widget.pos()

        # Create animation sequence
        self.animation = QSequentialAnimationGroup()

        # Bounce up
        up_anim = QPropertyAnimation(widget, b"pos")
        up_anim.setDuration(duration // 3)
        up_anim.setStartValue(self.original_pos)
        up_anim.setEndValue(QPoint(self.original_pos.x(), self.original_pos.y() - height))
        up_anim.setEasingCurve(QEasingCurve.OutQuad)

        # Bounce down
        down_anim = QPropertyAnimation(widget, b"pos")
        down_anim.setDuration(duration // 3)
        down_anim.setStartValue(QPoint(self.original_pos.x(), self.original_pos.y() - height))
        down_anim.setEndValue(self.original_pos)
        down_anim.setEasingCurve(QEasingCurve.InQuad)

        # Small bounce
        small_up = QPropertyAnimation(widget, b"pos")
        small_up.setDuration(duration // 6)
        small_up.setStartValue(self.original_pos)
        small_up.setEndValue(QPoint(self.original_pos.x(), self.original_pos.y() - height // 3))
        small_up.setEasingCurve(QEasingCurve.OutQuad)

        small_down = QPropertyAnimation(widget, b"pos")
        small_down.setDuration(duration // 6)
        small_down.setStartValue(QPoint(self.original_pos.x(), self.original_pos.y() - height // 3))
        small_down.setEndValue(self.original_pos)
        small_down.setEasingCurve(QEasingCurve.InQuad)

        # Add to sequence
        self.animation.addAnimation(up_anim)
        self.animation.addAnimation(down_anim)
        self.animation.addAnimation(small_up)
        self.animation.addAnimation(small_down)

        # Connect signals
        self.animation.finished.connect(self._on_finished)


def bounce(widget: QWidget, height: int = 20, duration: int = BOUNCE_DURATION) -> BounceAnimation:
    """
    Bounce a widget

    Args:
        widget: Widget to animate
        height: Bounce height in pixels
        duration: Animation duration in ms

    Returns:
        BounceAnimation instance
    """
    anim = BounceAnimation(widget, height, duration)
    anim.start()
    return anim


# ========== SCALE ANIMATION ==========

class ScaleAnimation(BaseAnimation):
    """Scale animation using size property"""

    def __init__(self, widget: QWidget, scale_factor: float = 1.2,
                 duration: int = ANIMATION_DURATION_NORMAL, parent=None):
        super().__init__(widget, duration, parent)

        self.scale_factor = scale_factor
        self.original_size = widget.size()
        self.scaled_size = QSize(
            int(self.original_size.width() * scale_factor),
            int(self.original_size.height() * scale_factor)
        )

        # Create animation
        self.animation = QPropertyAnimation(widget, b"size")
        self.animation.setDuration(self.duration)
        self.animation.setStartValue(self.original_size)
        self.animation.setEndValue(self.scaled_size)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)

        # Connect signals
        self.animation.finished.connect(self._on_finished)


def scale(widget: QWidget, scale_factor: float = 1.2,
          duration: int = ANIMATION_DURATION_NORMAL,
          restore: bool = True) -> ScaleAnimation:
    """
    Scale a widget

    Args:
        widget: Widget to animate
        scale_factor: Scale factor (1.2 = 120%)
        duration: Animation duration in ms
        restore: Restore original size after animation

    Returns:
        ScaleAnimation instance
    """
    anim = ScaleAnimation(widget, scale_factor, duration)

    if restore:
        # Create reverse animation
        restore_anim = ScaleAnimation(widget, 1.0, duration)
        anim.finished.connect(lambda: QTimer.singleShot(100, restore_anim.start))

    anim.start()
    return anim


# ========== SHAKE ANIMATION ==========

class ShakeAnimation(BaseAnimation):
    """Shake animation for error feedback"""

    def __init__(self, widget: QWidget, amplitude: int = 10,
                 duration: int = 500, parent=None):
        super().__init__(widget, duration, parent)

        self.amplitude = amplitude
        self.original_pos = widget.pos()

        # Create animation sequence
        self.animation = QSequentialAnimationGroup()

        # Number of shakes
        shake_count = 4
        shake_duration = duration // (shake_count * 2)

        for i in range(shake_count):
            # Shake right
            right_anim = QPropertyAnimation(widget, b"pos")
            right_anim.setDuration(shake_duration)
            right_anim.setStartValue(self.original_pos)
            right_anim.setEndValue(QPoint(self.original_pos.x() + amplitude, self.original_pos.y()))
            right_anim.setEasingCurve(QEasingCurve.InOutQuad)

            # Shake left
            left_anim = QPropertyAnimation(widget, b"pos")
            left_anim.setDuration(shake_duration)
            left_anim.setStartValue(QPoint(self.original_pos.x() + amplitude, self.original_pos.y()))
            left_anim.setEndValue(QPoint(self.original_pos.x() - amplitude, self.original_pos.y()))
            left_anim.setEasingCurve(QEasingCurve.InOutQuad)

            self.animation.addAnimation(right_anim)
            self.animation.addAnimation(left_anim)

            # Decrease amplitude
            amplitude = int(amplitude * 0.7)

        # Return to center
        center_anim = QPropertyAnimation(widget, b"pos")
        center_anim.setDuration(shake_duration)
        center_anim.setEndValue(self.original_pos)
        center_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.addAnimation(center_anim)

        # Connect signals
        self.animation.finished.connect(self._on_finished)


def shake(widget: QWidget, amplitude: int = 10, duration: int = 500) -> ShakeAnimation:
    """
    Shake a widget (useful for error feedback)

    Args:
        widget: Widget to animate
        amplitude: Shake amplitude in pixels
        duration: Animation duration in ms

    Returns:
        ShakeAnimation instance
    """
    anim = ShakeAnimation(widget, amplitude, duration)
    anim.start()
    return anim


# ========== PULSE ANIMATION ==========

class PulseAnimation(BaseAnimation):
    """Pulse animation (scale + fade)"""

    def __init__(self, widget: QWidget, scale_factor: float = 1.1,
                 duration: int = 1000, parent=None):
        super().__init__(widget, duration, parent)

        self.scale_factor = scale_factor

        # Create parallel animation group
        self.animation = QParallelAnimationGroup()

        # Scale animation
        original_size = widget.size()
        scaled_size = QSize(
            int(original_size.width() * scale_factor),
            int(original_size.height() * scale_factor)
        )

        scale_anim = QSequentialAnimationGroup()

        # Scale up
        scale_up = QPropertyAnimation(widget, b"size")
        scale_up.setDuration(duration // 2)
        scale_up.setStartValue(original_size)
        scale_up.setEndValue(scaled_size)
        scale_up.setEasingCurve(QEasingCurve.InOutQuad)

        # Scale down
        scale_down = QPropertyAnimation(widget, b"size")
        scale_down.setDuration(duration // 2)
        scale_down.setStartValue(scaled_size)
        scale_down.setEndValue(original_size)
        scale_down.setEasingCurve(QEasingCurve.InOutQuad)

        scale_anim.addAnimation(scale_up)
        scale_anim.addAnimation(scale_down)

        # Opacity animation
        if not widget.graphicsEffect():
            opacity_effect = QGraphicsOpacityEffect()
            widget.setGraphicsEffect(opacity_effect)
        else:
            opacity_effect = widget.graphicsEffect()

        opacity_anim = QSequentialAnimationGroup()

        # Fade slightly
        fade_out = QPropertyAnimation(opacity_effect, b"opacity")
        fade_out.setDuration(duration // 2)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.7)
        fade_out.setEasingCurve(QEasingCurve.InOutQuad)

        fade_in = QPropertyAnimation(opacity_effect, b"opacity")
        fade_in.setDuration(duration // 2)
        fade_in.setStartValue(0.7)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.InOutQuad)

        opacity_anim.addAnimation(fade_out)
        opacity_anim.addAnimation(fade_in)

        # Add to parallel group
        self.animation.addAnimation(scale_anim)
        self.animation.addAnimation(opacity_anim)

        # Set loop count for continuous pulse
        self.animation.setLoopCount(-1)  # Infinite loop

        # Connect signals
        self.animation.finished.connect(self._on_finished)


def pulse(widget: QWidget, scale_factor: float = 1.1,
          duration: int = 1000, loops: int = -1) -> PulseAnimation:
    """
    Create pulse animation

    Args:
        widget: Widget to animate
        scale_factor: Scale factor for pulse
        duration: Animation duration in ms
        loops: Number of loops (-1 for infinite)

    Returns:
        PulseAnimation instance
    """
    anim = PulseAnimation(widget, scale_factor, duration)
    anim.animation.setLoopCount(loops)
    anim.start()
    return anim


# ========== ROTATE ANIMATION ==========

class RotateAnimation(QVariantAnimation):
    """Rotate animation using transform"""

    def __init__(self, widget: QWidget, angle: int = 360,
                 duration: int = ANIMATION_DURATION_NORMAL, parent=None):
        super().__init__(parent)

        self.widget = widget
        self.angle = angle
        self.center = widget.rect().center()

        self.setDuration(duration)
        self.setStartValue(0)
        self.setEndValue(angle)
        self.setEasingCurve(QEasingCurve.InOutQuad)

        # Connect value changed
        self.valueChanged.connect(self._apply_rotation)

    def _apply_rotation(self, value):
        """Apply rotation transform"""
        transform = QTransform()
        transform.translate(self.center.x(), self.center.y())
        transform.rotate(value)
        transform.translate(-self.center.x(), -self.center.y())
        # Note: QWidget doesn't have setTransform, this would need custom painting


def rotate(widget: QWidget, angle: int = 360,
           duration: int = ANIMATION_DURATION_NORMAL) -> RotateAnimation:
    """
    Rotate a widget

    Args:
        widget: Widget to animate
        angle: Rotation angle in degrees
        duration: Animation duration in ms

    Returns:
        RotateAnimation instance
    """
    anim = RotateAnimation(widget, angle, duration)
    anim.start()
    return anim


# ========== VISUAL EFFECTS ==========

def add_shadow(widget: QWidget, blur_radius: int = 20,
               offset: Tuple[int, int] = (0, 5),
               color: QColor = QColor(0, 0, 0, 100)) -> QGraphicsDropShadowEffect:
    """
    Add drop shadow effect to widget

    Args:
        widget: Widget to add shadow
        blur_radius: Shadow blur radius
        offset: Shadow offset (x, y)
        color: Shadow color

    Returns:
        QGraphicsDropShadowEffect instance
    """
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(blur_radius)
    shadow.setOffset(offset[0], offset[1])
    shadow.setColor(color)
    widget.setGraphicsEffect(shadow)
    return shadow


def add_blur(widget: QWidget, radius: int = 10) -> QGraphicsBlurEffect:
    """
    Add blur effect to widget

    Args:
        widget: Widget to blur
        radius: Blur radius

    Returns:
        QGraphicsBlurEffect instance
    """
    blur = QGraphicsBlurEffect()
    blur.setBlurRadius(radius)
    widget.setGraphicsEffect(blur)
    return blur


def add_glow(widget: QWidget, color: QColor = QColor(100, 200, 255, 180),
             blur_radius: int = 30) -> QGraphicsDropShadowEffect:
    """
    Add glow effect to widget

    Args:
        widget: Widget to add glow
        color: Glow color
        blur_radius: Glow radius

    Returns:
        QGraphicsDropShadowEffect instance (used as glow)
    """
    glow = QGraphicsDropShadowEffect()
    glow.setBlurRadius(blur_radius)
    glow.setOffset(0, 0)
    glow.setColor(color)
    widget.setGraphicsEffect(glow)
    return glow


def add_colorize(widget: QWidget, color: QColor = QColor(100, 100, 200),
                 strength: float = 0.5) -> QGraphicsColorizeEffect:
    """
    Add colorize effect to widget

    Args:
        widget: Widget to colorize
        color: Colorize color
        strength: Effect strength (0.0 - 1.0)

    Returns:
        QGraphicsColorizeEffect instance
    """
    colorize = QGraphicsColorizeEffect()
    colorize.setColor(color)
    colorize.setStrength(strength)
    widget.setGraphicsEffect(colorize)
    return colorize


def glass_blur(widget: QWidget, blur_radius: int = 10,
               opacity: float = 0.8) -> None:
    """
    Apply glass blur effect (blur + transparency)

    Args:
        widget: Widget to apply effect
        blur_radius: Blur radius
        opacity: Widget opacity
    """
    blur = QGraphicsBlurEffect()
    blur.setBlurRadius(blur_radius)
    widget.setGraphicsEffect(blur)
    widget.setWindowOpacity(opacity)


# ========== ANIMATION GROUPS ==========

def create_sequence(*animations: QAbstractAnimation) -> QSequentialAnimationGroup:
    """
    Create sequential animation group

    Args:
        *animations: Animations to add to sequence

    Returns:
        QSequentialAnimationGroup instance
    """
    group = QSequentialAnimationGroup()
    for anim in animations:
        group.addAnimation(anim)
    return group


def create_parallel(*animations: QAbstractAnimation) -> QParallelAnimationGroup:
    """
    Create parallel animation group

    Args:
        *animations: Animations to run in parallel

    Returns:
        QParallelAnimationGroup instance
    """
    group = QParallelAnimationGroup()
    for anim in animations:
        group.addAnimation(anim)
    return group


def chain_animations(animations: List[QAbstractAnimation],
                     delay: int = 0) -> QSequentialAnimationGroup:
    """
    Chain animations with optional delay between them

    Args:
        animations: List of animations
        delay: Delay between animations in ms

    Returns:
        QSequentialAnimationGroup instance
    """
    group = QSequentialAnimationGroup()

    for i, anim in enumerate(animations):
        group.addAnimation(anim)
        if delay > 0 and i < len(animations) - 1:
            pause = QPauseAnimation(delay)
            group.addAnimation(pause)

    return group


# ========== COMPOSITE ANIMATIONS ==========

def fade_and_slide(widget: QWidget, direction: Direction = Direction.UP,
                   distance: int = 50, duration: int = ANIMATION_DURATION_NORMAL) -> QParallelAnimationGroup:
    """
    Combine fade and slide animations

    Args:
        widget: Widget to animate
        direction: Slide direction
        distance: Slide distance
        duration: Animation duration

    Returns:
        QParallelAnimationGroup instance
    """
    # Create opacity effect
    opacity_effect = QGraphicsOpacityEffect()
    widget.setGraphicsEffect(opacity_effect)

    # Fade animation
    fade = QPropertyAnimation(opacity_effect, b"opacity")
    fade.setDuration(duration)
    fade.setStartValue(0.0)
    fade.setEndValue(1.0)
    fade.setEasingCurve(QEasingCurve.InOutQuad)

    # Slide animation
    start_pos = widget.pos()
    end_pos = start_pos

    if direction == Direction.UP:
        widget.move(start_pos.x(), start_pos.y() + distance)
        end_pos = start_pos
    elif direction == Direction.DOWN:
        widget.move(start_pos.x(), start_pos.y() - distance)
        end_pos = start_pos
    elif direction == Direction.LEFT:
        widget.move(start_pos.x() + distance, start_pos.y())
        end_pos = start_pos
    elif direction == Direction.RIGHT:
        widget.move(start_pos.x() - distance, start_pos.y())
        end_pos = start_pos

    slide = QPropertyAnimation(widget, b"pos")
    slide.setDuration(duration)
    slide.setStartValue(widget.pos())
    slide.setEndValue(end_pos)
    slide.setEasingCurve(QEasingCurve.OutCubic)

    # Combine
    group = QParallelAnimationGroup()
    group.addAnimation(fade)
    group.addAnimation(slide)

    widget.show()
    group.start()

    return group


def zoom_fade(widget: QWidget, zoom_in: bool = True,
              duration: int = ANIMATION_DURATION_NORMAL) -> QParallelAnimationGroup:
    """
    Zoom and fade animation

    Args:
        widget: Widget to animate
        zoom_in: True for zoom in, False for zoom out
        duration: Animation duration

    Returns:
        QParallelAnimationGroup instance
    """
    # Create opacity effect
    opacity_effect = QGraphicsOpacityEffect()
    widget.setGraphicsEffect(opacity_effect)

    # Size animation
    original_size = widget.size()
    if zoom_in:
        start_size = QSize(int(original_size.width() * 0.8),
                           int(original_size.height() * 0.8))
        end_size = original_size
        start_opacity = 0.0
        end_opacity = 1.0
    else:
        start_size = original_size
        end_size = QSize(int(original_size.width() * 1.2),
                         int(original_size.height() * 1.2))
        start_opacity = 1.0
        end_opacity = 0.0

    widget.resize(start_size)

    size_anim = QPropertyAnimation(widget, b"size")
    size_anim.setDuration(duration)
    size_anim.setStartValue(start_size)
    size_anim.setEndValue(end_size)
    size_anim.setEasingCurve(QEasingCurve.InOutQuad)

    # Opacity animation
    opacity_anim = QPropertyAnimation(opacity_effect, b"opacity")
    opacity_anim.setDuration(duration)
    opacity_anim.setStartValue(start_opacity)
    opacity_anim.setEndValue(end_opacity)
    opacity_anim.setEasingCurve(QEasingCurve.InOutQuad)

    # Combine
    group = QParallelAnimationGroup()
    group.addAnimation(size_anim)
    group.addAnimation(opacity_anim)

    if zoom_in:
        widget.show()
    else:
        group.finished.connect(widget.hide)

    group.start()

    return group


# ========== EASING CURVES ==========

def get_easing_curve(name: str) -> QEasingCurve:
    """
    Get easing curve by name

    Args:
        name: Easing curve name

    Returns:
        QEasingCurve instance
    """
    curves = {
        "linear": QEasingCurve.Linear,
        "in_quad": QEasingCurve.InQuad,
        "out_quad": QEasingCurve.OutQuad,
        "in_out_quad": QEasingCurve.InOutQuad,
        "in_cubic": QEasingCurve.InCubic,
        "out_cubic": QEasingCurve.OutCubic,
        "in_out_cubic": QEasingCurve.InOutCubic,
        "in_elastic": QEasingCurve.InElastic,
        "out_elastic": QEasingCurve.OutElastic,
        "in_out_elastic": QEasingCurve.InOutElastic,
        "in_bounce": QEasingCurve.InBounce,
        "out_bounce": QEasingCurve.OutBounce,
        "in_out_bounce": QEasingCurve.InOutBounce,
        "in_back": QEasingCurve.InBack,
        "out_back": QEasingCurve.OutBack,
        "in_out_back": QEasingCurve.InOutBack
    }

    return curves.get(name.lower(), QEasingCurve.InOutQuad)


# ========== UTILITY FUNCTIONS ==========

def animate_property(widget: QWidget, property_name: str,
                     start_value: Any, end_value: Any,
                     duration: int = ANIMATION_DURATION_NORMAL,
                     easing: QEasingCurve = QEasingCurve.InOutQuad) -> QPropertyAnimation:
    """
    Animate any property of a widget

    Args:
        widget: Widget to animate
        property_name: Property name (e.g., "geometry", "pos", "size")
        start_value: Start value
        end_value: End value
        duration: Animation duration
        easing: Easing curve

    Returns:
        QPropertyAnimation instance
    """
    animation = QPropertyAnimation(widget, property_name.encode())
    animation.setDuration(duration)
    animation.setStartValue(start_value)
    animation.setEndValue(end_value)
    animation.setEasingCurve(easing)
    animation.start()

    return animation


def flash(widget: QWidget, count: int = 3, duration: int = 200) -> QSequentialAnimationGroup:
    """
    Flash a widget (blink effect)

    Args:
        widget: Widget to flash
        count: Number of flashes
        duration: Duration per flash

    Returns:
        QSequentialAnimationGroup instance
    """
    # Create opacity effect
    if not widget.graphicsEffect():
        opacity_effect = QGraphicsOpacityEffect()
        widget.setGraphicsEffect(opacity_effect)
    else:
        opacity_effect = widget.graphicsEffect()

    group = QSequentialAnimationGroup()

    for _ in range(count):
        # Fade out
        fade_out = QPropertyAnimation(opacity_effect, b"opacity")
        fade_out.setDuration(duration // 2)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.3)

        # Fade in
        fade_in = QPropertyAnimation(opacity_effect, b"opacity")
        fade_in.setDuration(duration // 2)
        fade_in.setStartValue(0.3)
        fade_in.setEndValue(1.0)

        group.addAnimation(fade_out)
        group.addAnimation(fade_in)

    group.start()
    return group


def highlight(widget: QWidget, color: QColor = QColor(255, 255, 0, 100),
              duration: int = 1000) -> QPropertyAnimation:
    """
    Highlight a widget with color

    Args:
        widget: Widget to highlight
        color: Highlight color
        duration: Animation duration

    Returns:
        QPropertyAnimation instance
    """
    colorize = QGraphicsColorizeEffect()
    widget.setGraphicsEffect(colorize)

    animation = QPropertyAnimation(colorize, b"strength")
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setKeyValueAt(0.5, 0.8)
    animation.setEndValue(0.0)
    animation.setEasingCurve(QEasingCurve.InOutQuad)

    colorize.setColor(color)
    animation.start()

    return animation


# ========== ANIMATION MANAGER ==========

class AnimationManager(QObject):
    """Manager for handling multiple animations"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.animations = []
        self.running_animations = []

    def add_animation(self, animation: QAbstractAnimation):
        """Add animation to manager"""
        self.animations.append(animation)
        animation.finished.connect(lambda: self._on_animation_finished(animation))

    def start_all(self):
        """Start all animations"""
        for anim in self.animations:
            if anim not in self.running_animations:
                anim.start()
                self.running_animations.append(anim)

    def stop_all(self):
        """Stop all animations"""
        for anim in self.running_animations:
            anim.stop()
        self.running_animations.clear()

    def pause_all(self):
        """Pause all animations"""
        for anim in self.running_animations:
            anim.pause()

    def resume_all(self):
        """Resume all animations"""
        for anim in self.running_animations:
            anim.resume()

    def clear(self):
        """Clear all animations"""
        self.stop_all()
        self.animations.clear()

    def _on_animation_finished(self, animation: QAbstractAnimation):
        """Handle animation finished"""
        if animation in self.running_animations:
            self.running_animations.remove(animation)


# ========== EXAMPLE USAGE ==========

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QPushButton

    app = QApplication(sys.argv)

    # Create test widget
    button = QPushButton("Test Animation")
    button.resize(200, 50)
    button.show()


    # Test different animations
    def test_animations():
        # Fade in
        fade_in(button, duration=500)

        # Wait and slide
        QTimer.singleShot(1000, lambda: slide_in(button, Direction.LEFT))

        # Wait and bounce
        QTimer.singleShot(2000, lambda: bounce(button))

        # Wait and shake
        QTimer.singleShot(3000, lambda: shake(button))

        # Wait and pulse
        QTimer.singleShot(4000, lambda: pulse(button, loops=3))

        # Add shadow
        QTimer.singleShot(5000, lambda: add_shadow(button))

        # Add glow
        QTimer.singleShot(6000, lambda: add_glow(button))


    test_animations()

    sys.exit(app.exec())