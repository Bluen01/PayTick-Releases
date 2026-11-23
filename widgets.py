import math
import os
import threading
import calendar
from datetime import date, datetime, timedelta, time as dt_time
from typing import List, Set
from PySide6.QtCore import Qt, QObject, QEvent, QTimer, QRectF, QPointF, QPoint, QDate, QTime, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, Signal, Property
from PySide6.QtGui import (
    QPainter,
    QPainterPath,
    QPixmap,
    QColor,
    QPen,
    QBrush,
    QLinearGradient,
    QFont,
    QFontMetrics,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QFrame,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QCheckBox,
    QDoubleSpinBox,
    QDateEdit,
    QTimeEdit,
    QLineEdit,
    QScrollArea,
    QCalendarWidget,
    QTextEdit,
    QProgressBar,
    QFileDialog,
)

from core import CompTimeManager, OvertimeRecord, TimeCalculator, LunarCalendar, FastDownloader

MAIN_WIDTH = 360


def _source_han_font(size_pt: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont("Source Han Sans CN", size_pt, weight)
    font.setFamilies(["Source Han Sans CN", "思源黑体 CN", "Source Han Sans SC", "思源黑体", "Noto Sans SC", "SimHei"])
    return font


class SmoothProgressBar(QWidget):
    """
    8-10px 圆角平滑工作进度条，支持暗黑/白色简约双主题轨道与点缀色渐变
    """
    def __init__(self, parent=None, accent_color: str = "#FF6B00"):
        super().__init__(parent)
        self._value = 0.0
        self._accent_color = QColor(accent_color)
        self._track_color = QColor("#232329")
        self.setFixedHeight(9)

    def set_value(self, val: float) -> None:
        clamped = max(0.0, min(100.0, val))
        if abs(clamped - self._value) > 0.001:
            self._value = clamped
            self.update()

    def set_accent_color(self, color_hex: str) -> None:
        self._accent_color = QColor(color_hex)
        self.update()

    def set_track_color(self, color_hex: str) -> None:
        self._track_color = QColor(color_hex)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        radius = h / 2.0

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._track_color))
        painter.drawRoundedRect(QRectF(0, 0, w, h), radius, radius)

        if self._value > 0.0:
            fill_w = max(h, (self._value / 100.0) * w)
            grad = QLinearGradient(0, 0, fill_w, 0)
            lighter = QColor(self._accent_color).lighter(115)
            grad.setColorAt(0.0, self._accent_color)
            grad.setColorAt(1.0, lighter)

            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(QRectF(0, 0, fill_w, h), radius, radius)


class CapsuleToggleSwitch(QWidget):
    """圆角胶囊拨动开关（Toggle Switch）：自绘平滑胶囊轨道与圆形滑块，严格跟随主题配色。"""

    toggled = Signal(bool)

    def __init__(self, parent=None, accent_color: str = "#FF6B00", is_light: bool = False):
        super().__init__(parent)
        self._checked = False
        self._knob_pos = 0.0
        self._hovered = False
        self._accent_color = QColor(accent_color)
        self._is_light = is_light
        self.setFixedSize(44, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 16ms 帧定时器驱动 10 帧 ease_out_cubic 缓动动画（约 160ms）
        self._anim_total_frames = 10
        self._anim_frame = 0
        self._anim_start = 0.0
        self._anim_end = 0.0
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._on_anim_tick)

    @staticmethod
    def _ease_out_cubic(t: float) -> float:
        u = max(0.0, min(1.0, float(t)))
        return 1.0 - (1.0 - u) ** 3

    def _on_anim_tick(self) -> None:
        self._anim_frame += 1
        p = min(1.0, self._anim_frame / float(self._anim_total_frames))
        eased = self._ease_out_cubic(p)
        self._knob_pos = max(0.0, min(1.0, self._anim_start + (self._anim_end - self._anim_start) * eased))
        self.update()
        if self._anim_frame >= self._anim_total_frames:
            self._knob_pos = self._anim_end
            self._anim_timer.stop()
            self.update()

    def _get_knob_pos(self) -> float:
        return self._knob_pos

    def _set_knob_pos(self, pos: float) -> None:
        self._knob_pos = max(0.0, min(1.0, float(pos)))
        self.update()

    knob_pos = Property(float, _get_knob_pos, _set_knob_pos)

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, checked: bool, animate: bool = True) -> None:
        target = bool(checked)
        end_val = 1.0 if target else 0.0
        changed = target != self._checked
        self._checked = target
        if not changed:
            # 若已经在向目标值执行缓动动画，绝不打断或瞬移滑块
            if self._anim_timer.isActive() and abs(self._anim_end - end_val) < 1e-6:
                return
            if abs(self._knob_pos - end_val) > 1e-4:
                self._anim_timer.stop()
                self._knob_pos = end_val
                self.update()
            return

        self._anim_timer.stop()
        if animate and self.isVisible():
            self._anim_start = self._knob_pos
            self._anim_end = end_val
            self._anim_frame = 0
            self._anim_timer.start()
        else:
            self._knob_pos = end_val
            self.update()

    def set_accent_color(self, color_hex: str) -> None:
        self._accent_color = QColor(color_hex)
        self.update()

    def set_light_mode(self, is_light: bool) -> None:
        self._is_light = bool(is_light)
        self.update()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            new_state = not self._checked
            self.set_checked(new_state, animate=True)
            self.toggled.emit(new_state)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        radius = h / 2.0

        off_color = QColor("#CFD4DC" if self._is_light else "#3A3A46")
        if self._hovered and not self._checked:
            off_color = QColor("#BFC6D1" if self._is_light else "#484856")
        on_color = QColor(self._accent_color)
        if self._hovered and self._checked:
            on_color = on_color.lighter(108)

        t = self._knob_pos
        r = int(off_color.red() + (on_color.red() - off_color.red()) * t)
        g = int(off_color.green() + (on_color.green() - off_color.green()) * t)
        b = int(off_color.blue() + (on_color.blue() - off_color.blue()) * t)
        track_color = QColor(r, g, b)

        # 胶囊轨道
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(track_color))
        p.drawRoundedRect(QRectF(0.0, 0.0, w, h), radius, radius)

        # 圆形滑块（含轻微柔和阴影）
        margin = 3.0
        knob_d = h - margin * 2.0
        x_min = margin
        x_max = w - margin - knob_d
        knob_x = x_min + (x_max - x_min) * t
        knob_y = margin

        p.setBrush(QColor(0, 0, 0, 26))
        p.drawEllipse(QRectF(knob_x, knob_y + 0.8, knob_d, knob_d))

        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QPen(QColor(0, 0, 0, 14), 0.6))
        p.drawEllipse(QRectF(knob_x, knob_y, knob_d, knob_d))
        p.end()


class VectorIconButton(QPushButton):
    """
    极简矢量微图标按钮（支持 Pin 置顶、Gear 设置、Close 关闭），支持暗色/白色双主题
    """
    def __init__(self, icon_type: str, parent=None, accent_color: str = "#FF6B00"):
        super().__init__(parent)
        self.icon_type = icon_type
        self.is_active = False
        self.accent_color = QColor(accent_color)
        self.is_light_mode = False
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hovered = False

    def set_active(self, active: bool) -> None:
        self.is_active = active
        self.update()

    def set_accent_color(self, color_hex: str) -> None:
        self.accent_color = QColor(color_hex)
        self.update()

    def set_light_mode(self, is_light: bool) -> None:
        self.is_light_mode = is_light
        self.update()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0, 0, self.width(), self.height())
        pressed = self.isDown()

        if pressed:
            if self.icon_type == "close":
                painter.setBrush(QColor("#C50F1F"))
            else:
                press_bg = "#D5D7E0" if self.is_light_mode else "#32323C"
                painter.setBrush(QColor(press_bg))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 7.0, 7.0)
        elif self._hovered:
            if self.icon_type == "close":
                painter.setBrush(QColor("#E81123"))
            else:
                hover_bg = "#E6E6EC" if self.is_light_mode else "#26262C"
                painter.setBrush(QColor(hover_bg))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 7.0, 7.0)
        elif self.is_active and self.icon_type == "pin":
            bg = QColor(self.accent_color)
            bg.setAlpha(35)
            painter.setBrush(bg)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 7.0, 7.0)

        if (self._hovered or pressed) and self.icon_type == "close":
            pen_color = QColor("#FFFFFF")
        elif self.is_active or pressed:
            pen_color = self.accent_color
        elif self._hovered:
            pen_color = QColor("#18181C" if self.is_light_mode else "#F4F4F6")
        else:
            pen_color = QColor("#686872" if self.is_light_mode else "#8E8E98")

        pen = QPen(pen_color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        cx, cy = self.width() / 2.0, self.height() / 2.0
        if pressed:
            painter.translate(cx, cy + 0.6)
            painter.scale(0.92, 0.92)
            painter.translate(-cx, -cy)

        if self.icon_type == "close":
            offset = 4.6
            painter.drawLine(QPointF(cx - offset, cy - offset), QPointF(cx + offset, cy + offset))
            painter.drawLine(QPointF(cx + offset, cy - offset), QPointF(cx - offset, cy + offset))

        elif self.icon_type == "min":
            painter.drawLine(QPointF(cx - 4.8, cy), QPointF(cx + 4.8, cy))

        elif self.icon_type == "mini":
            painter.drawRoundedRect(QRectF(cx - 5.5, cy - 4.5, 11.0, 9.0), 2.0, 2.0)
            painter.setBrush(pen_color)
            painter.drawRoundedRect(QRectF(cx - 0.5, cy + 0.3, 4.2, 2.8), 0.8, 0.8)

        elif self.icon_type == "restore":
            painter.drawRoundedRect(QRectF(cx - 5.0, cy - 4.5, 10.0, 9.0), 2.0, 2.0)
            painter.drawLine(QPointF(cx - 2.2, cy + 2.0), QPointF(cx + 2.4, cy - 2.2))
            painter.drawLine(QPointF(cx - 0.4, cy - 2.2), QPointF(cx + 2.4, cy - 2.2))
            painter.drawLine(QPointF(cx + 2.4, cy - 2.2), QPointF(cx + 2.4, cy + 0.6))

        elif self.icon_type == "gear":
            painter.drawEllipse(QPointF(cx, cy), 2.5, 2.5)
            painter.drawEllipse(QPointF(cx, cy), 5.2, 5.2)
            for i in range(6):
                angle = math.radians(i * 60)
                x1 = cx + 5.0 * math.cos(angle)
                y1 = cy + 5.0 * math.sin(angle)
                x2 = cx + 6.8 * math.cos(angle)
                y2 = cy + 6.8 * math.sin(angle)
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        elif self.icon_type == "pin":
            if self.is_active:
                painter.setBrush(pen_color)
            painter.drawRoundedRect(QRectF(cx - 3.6, cy - 5.5, 7.2, 5.2), 1.5, 1.5)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(QPointF(cx - 5.0, cy - 0.2), QPointF(cx + 5.0, cy - 0.2))
            painter.drawLine(QPointF(cx, cy), QPointF(cx, cy + 5.8))

        elif self.icon_type == "popout":
            painter.drawRoundedRect(QRectF(cx - 4.8, cy - 3.0, 7.4, 7.4), 1.4, 1.4)
            painter.drawLine(QPointF(cx - 0.5, cy + 0.5), QPointF(cx + 4.8, cy - 4.8))
            painter.drawLine(QPointF(cx + 1.4, cy - 4.8), QPointF(cx + 4.8, cy - 4.8))
            painter.drawLine(QPointF(cx + 4.8, cy - 4.8), QPointF(cx + 4.8, cy - 1.4))


class RollingStatusTicker(QWidget):
    """
    无边框透明状态文案滚动条：
    - 去掉半圆形框，纯文字展示
    - 切换时现有文案向上移动消失，新文案从下往上出现（无缝衔接）
    - 支持鼠标点击手动切换
    """
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._cur_label = QLabel("", self)
        self._next_label = QLabel("", self)
        font = _source_han_font(10)
        for lbl in (self._cur_label, self._next_label):
            lbl.setFont(font)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._next_label.hide()
        self._anim_group: QParallelAnimationGroup | None = None
        self._text_color = "#C8C8D2"

    def set_text_color(self, color_hex: str) -> None:
        self._text_color = color_hex
        style = f"color: {color_hex}; background: transparent;"
        self._cur_label.setStyleSheet(style)
        self._next_label.setStyleSheet(style)

    def set_text_immediate(self, text: str) -> None:
        if self._anim_group is not None and self._anim_group.state() == QParallelAnimationGroup.State.Running:
            self._anim_group.stop()
        self._cur_label.setText(text)
        self._cur_label.setGeometry(0, 0, self.width(), self.height())
        self._cur_label.show()
        self._next_label.hide()

    def slide_to(self, new_text: str) -> None:
        if new_text == self._cur_label.text():
            return
        if not self._cur_label.text() or self.width() <= 0:
            self.set_text_immediate(new_text)
            return
        if self._anim_group is not None and self._anim_group.state() == QParallelAnimationGroup.State.Running:
            self._anim_group.stop()
            self._cur_label.setGeometry(0, 0, self.width(), self.height())

        w, h = self.width(), self.height()
        self._next_label.setText(new_text)
        self._next_label.setGeometry(0, h, w, h)
        self._next_label.show()

        anim_out = QPropertyAnimation(self._cur_label, b"pos", self)
        anim_out.setDuration(320)
        anim_out.setStartValue(QPoint(0, 0))
        anim_out.setEndValue(QPoint(0, -h))
        anim_out.setEasingCurve(QEasingCurve.Type.OutCubic)

        anim_in = QPropertyAnimation(self._next_label, b"pos", self)
        anim_in.setDuration(320)
        anim_in.setStartValue(QPoint(0, h))
        anim_in.setEndValue(QPoint(0, 0))
        anim_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(anim_out)
        group.addAnimation(anim_in)
        group.finished.connect(self._on_anim_finished)
        self._anim_group = group
        group.start()

    def _on_anim_finished(self) -> None:
        self._cur_label, self._next_label = self._next_label, self._cur_label
        self._cur_label.setGeometry(0, 0, self.width(), self.height())
        self._next_label.hide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._anim_group is None or self._anim_group.state() != QParallelAnimationGroup.State.Running:
            self._cur_label.setGeometry(0, 0, self.width(), self.height())

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class CardFrame(QFrame):
    """
    圆角卡片容器，支持动态切换暗色/白色简约主题
    """
    def __init__(self, parent=None, bg_color="#17171B", border_color="#24242A", radius=14):
        super().__init__(parent)
        self.radius = radius
        self.setObjectName("CardFrame")
        self.set_colors(bg_color, border_color)

    def set_colors(self, bg_color: str, border_color: str) -> None:
        self.setStyleSheet(
            f"""
            QFrame#CardFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: {self.radius}px;
            }}
            """
        )


class CustomRestCalendarDialog(QDialog):
    """
    自定义休息日历弹窗：
    1. 顶部支持【上月】、【下月】切换与【定位今日】快速回到本月当前日期
    2. 7x6 月历网格：点一下选中休息，再点一下取消；已经过去的日期灰色显示
    3. 固定休息周期设置：
       - 每周固定休（可多选周一至周日）
       - 每月固定休（已选择日期）方框可勾选（勾选后已选日期的号数在每个月均固定休息）
    4. 底部【确认保存】
    """
    WEEKDAY_HEADERS = ["一", "二", "三", "四", "五", "六", "日"]

    def __init__(
        self,
        parent=None,
        rest_dates: List[str] = None,
        fixed_weekdays: List[int] = None,
        monthly_selected_days_enabled: bool = False,
        theme_mode: str = "dark",
        accent_color: str = "#FF6B00",
    ):
        super().__init__(parent)
        self.theme_mode = theme_mode
        self.accent_color = accent_color
        self.is_light = theme_mode == "light"

        self.selected_dates: Set[str] = set(rest_dates or [])
        self.fixed_weekdays: Set[int] = set(fixed_weekdays or [])
        self.monthly_selected_days_enabled = bool(monthly_selected_days_enabled)

        today = date.today()
        self.view_year = today.year
        self.view_month = today.month
        self._drag_pos: QPoint | None = None

        self.setFixedSize(MAIN_WIDTH, 505)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Dialog
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)

        self._build_ui()
        self._apply_dialog_style()
        self._refresh_calendar_grid()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor("#F5F6F8") if self.is_light else QColor("#151519")
        border = QColor("#CFD4E0") if self.is_light else QColor("#2D2D36")
        rect = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
        painter.setBrush(QBrush(bg))
        painter.setPen(QPen(border, 1.4))
        painter.drawRoundedRect(rect, 18.0, 18.0)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 15)
        root.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(2)
        self.lbl_title = QLabel("自定义休息日历", self)
        self.lbl_title.setFont(_source_han_font(11, QFont.Weight.Bold))
        self.btn_min = VectorIconButton("min", self, self.accent_color)
        self.btn_min.set_light_mode(self.is_light)
        self.btn_min.setToolTip("最小化")
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_close = VectorIconButton("close", self, self.accent_color)
        self.btn_close.set_light_mode(self.is_light)
        self.btn_close.clicked.connect(self.reject)
        top_row.addWidget(self.lbl_title)
        top_row.addStretch(1)
        top_row.addWidget(self.btn_min)
        top_row.addWidget(self.btn_close)
        root.addLayout(top_row)

        nav_row = QHBoxLayout()
        nav_row.setSpacing(6)

        self.btn_prev_month = QPushButton("◀ 上月", self)
        self.btn_prev_month.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev_month.setFixedHeight(28)
        self.btn_prev_month.setFont(_source_han_font(9, QFont.Weight.Bold))
        self.btn_prev_month.clicked.connect(self._go_prev_month)

        self.lbl_month_title = QLabel("2026年 11月", self)
        self.lbl_month_title.setFont(_source_han_font(11, QFont.Weight.Bold))
        self.lbl_month_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_next_month = QPushButton("下月 ▶", self)
        self.btn_next_month.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next_month.setFixedHeight(28)
        self.btn_next_month.setFont(_source_han_font(9, QFont.Weight.Bold))
        self.btn_next_month.clicked.connect(self._go_next_month)

        self.btn_today = QPushButton("定位今日", self)
        self.btn_today.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_today.setFixedHeight(28)
        self.btn_today.setFont(_source_han_font(9, QFont.Weight.Bold))
        self.btn_today.setToolTip("快速回到本月并定位当前日期")
        self.btn_today.clicked.connect(self._go_today)

        nav_row.addWidget(self.btn_prev_month)
        nav_row.addWidget(self.lbl_month_title, 1)
        nav_row.addWidget(self.btn_next_month)
        nav_row.addWidget(self.btn_today)
        root.addLayout(nav_row)

        self.cal_card = CardFrame(self, radius=12)
        cal_layout = QVBoxLayout(self.cal_card)
        cal_layout.setContentsMargins(10, 8, 10, 10)
        cal_layout.setSpacing(4)

        header_grid = QGridLayout()
        header_grid.setSpacing(4)
        self.weekday_labels: List[QLabel] = []
        for col, name in enumerate(self.WEEKDAY_HEADERS):
            lbl = QLabel(name, self.cal_card)
            lbl.setFont(_source_han_font(9, QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedHeight(20)
            header_grid.addWidget(lbl, 0, col)
            self.weekday_labels.append(lbl)
        cal_layout.addLayout(header_grid)

        self.days_grid = QGridLayout()
        self.days_grid.setSpacing(4)
        self.day_buttons: List[QPushButton] = []
        for idx in range(42):
            btn = QPushButton("", self.cal_card)
            btn.setFixedSize(40, 30)
            btn.setFont(_source_han_font(9, QFont.Weight.Bold))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, i=idx: self._on_day_clicked(i))
            self.days_grid.addWidget(btn, idx // 7, idx % 7)
            self.day_buttons.append(btn)
        cal_layout.addLayout(self.days_grid)
        root.addWidget(self.cal_card)

        self.rule_card = CardFrame(self, radius=12)
        rule_layout = QVBoxLayout(self.rule_card)
        rule_layout.setContentsMargins(12, 10, 12, 10)
        rule_layout.setSpacing(8)

        self.lbl_rule_header = QLabel("固定休息设置 (与日历点选叠加生效)", self.rule_card)
        self.lbl_rule_header.setFont(_source_han_font(9, QFont.Weight.Bold))
        rule_layout.addWidget(self.lbl_rule_header)

        wd_row = QHBoxLayout()
        wd_row.setSpacing(4)
        self.lbl_wd_tip = QLabel("每周固定休:", self.rule_card)
        self.lbl_wd_tip.setFont(_source_han_font(9))
        wd_row.addWidget(self.lbl_wd_tip)

        self.weekday_toggle_btns: List[QPushButton] = []
        for wd_idx, wd_short in enumerate(["一", "二", "三", "四", "五", "六", "日"]):
            b = QPushButton(wd_short, self.rule_card)
            b.setCheckable(True)
            b.setChecked(wd_idx in self.fixed_weekdays)
            b.setFixedSize(28, 24)
            b.setFont(_source_han_font(9, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(self._on_fixed_rule_changed)
            wd_row.addWidget(b)
            self.weekday_toggle_btns.append(b)
        wd_row.addStretch(1)
        rule_layout.addLayout(wd_row)

        # 每月固定休（已选择日期）方框可勾选
        self.chk_monthly_selected = QCheckBox("每月固定休（已选择日期）", self.rule_card)
        self.chk_monthly_selected.setFont(_source_han_font(9, QFont.Weight.Medium))
        self.chk_monthly_selected.setChecked(self.monthly_selected_days_enabled)
        self.chk_monthly_selected.toggled.connect(self._on_fixed_rule_changed)
        rule_layout.addWidget(self.chk_monthly_selected)

        root.addWidget(self.rule_card)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_clear_month = QPushButton("清空本月点选", self)
        self.btn_clear_month.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_month.setFixedHeight(34)
        self.btn_clear_month.setFont(_source_han_font(9, QFont.Weight.Bold))
        self.btn_clear_month.clicked.connect(self._clear_current_month_manual)

        self.btn_confirm = QPushButton("确认", self)
        self.btn_confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_confirm.setFixedHeight(34)
        self.btn_confirm.setFont(_source_han_font(10, QFont.Weight.Bold))
        self.btn_confirm.clicked.connect(self.accept)

        btn_row.addWidget(self.btn_clear_month, 1)
        btn_row.addWidget(self.btn_confirm, 1)
        root.addLayout(btn_row)

    def _apply_dialog_style(self) -> None:
        acc = self.accent_color
        if self.is_light:
            card_bg = "#FFFFFF"
            card_border = "#E2E5EC"
            primary_text = "#18181C"
            muted_text = "#7A7A86"
            btn_bg = "#ECEEF3"
            btn_border = "#D6D9E2"
        else:
            card_bg = "#1C1C22"
            card_border = "#2A2A34"
            primary_text = "#F4F4F6"
            muted_text = "#8A8A96"
            btn_bg = "#25252E"
            btn_border = "#343440"

        self.lbl_title.setStyleSheet(f"color: {primary_text};")
        self.lbl_month_title.setStyleSheet(f"color: {primary_text};")
        self.cal_card.set_colors(card_bg, card_border)
        self.rule_card.set_colors(card_bg, card_border)

        for lbl in self.weekday_labels:
            lbl.setStyleSheet(f"color: {muted_text};")

        self.lbl_rule_header.setStyleSheet(f"color: {muted_text};")
        self.lbl_wd_tip.setStyleSheet(f"color: {primary_text};")
        self.chk_monthly_selected.setStyleSheet(
            f"""
            QCheckBox {{
                color: {primary_text};
                spacing: 7px;
            }}
            QCheckBox::indicator {{
                width: 15px;
                height: 15px;
                border-radius: 4px;
                border: 1.5px solid {muted_text};
                background-color: {btn_bg};
            }}
            QCheckBox::indicator:checked {{
                border-color: {acc};
                background-color: {acc};
            }}
            """
        )

        nav_btn_qss = f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {primary_text};
                border: 1px solid {btn_border};
                border-radius: 7px;
                padding: 2px 8px;
            }}
            QPushButton:hover {{
                border-color: {acc};
            }}
        """
        for b in (self.btn_prev_month, self.btn_next_month, self.btn_today, self.btn_clear_month):
            b.setStyleSheet(nav_btn_qss)

        self.btn_confirm.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {acc};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: {acc};
                color: #FFFFFF;
            }}
            """
        )
        self._update_weekday_toggle_styles()

    def _update_weekday_toggle_styles(self) -> None:
        acc = self.accent_color
        is_light = self.is_light
        idle_bg = "#ECEEF3" if is_light else "#25252E"
        idle_fg = "#484854" if is_light else "#B0B0BC"

        for b in self.weekday_toggle_btns:
            if b.isChecked():
                b.setStyleSheet(
                    f"""
                    QPushButton {{
                        background-color: {acc};
                        color: #FFFFFF;
                        border: none;
                        border-radius: 6px;
                    }}
                    """
                )
            else:
                b.setStyleSheet(
                    f"""
                    QPushButton {{
                        background-color: {idle_bg};
                        color: {idle_fg};
                        border: 1px solid transparent;
                        border-radius: 6px;
                    }}
                    """
                )

    def _on_fixed_rule_changed(self) -> None:
        self.fixed_weekdays = {
            idx for idx, b in enumerate(self.weekday_toggle_btns) if b.isChecked()
        }
        self.monthly_selected_days_enabled = self.chk_monthly_selected.isChecked()
        self._update_weekday_toggle_styles()
        self._refresh_calendar_grid()

    def _selected_day_numbers(self) -> Set[int]:
        nums = set()
        for item in self.selected_dates:
            try:
                nums.add(int(item.split("-")[2]))
            except Exception:
                pass
        return nums

    def _is_matched_by_fixed_rule(self, d: date, selected_day_nums: Set[int]) -> bool:
        if d.weekday() in self.fixed_weekdays:
            return True
        if self.monthly_selected_days_enabled and d.day in selected_day_nums:
            return True
        return False

    def _refresh_calendar_grid(self) -> None:
        self.lbl_month_title.setText(f"{self.view_year}年 {self.view_month:02d}月")
        today = date.today()
        first_weekday, num_days = calendar.monthrange(self.view_year, self.view_month)
        selected_day_nums = self._selected_day_numbers()

        acc = self.accent_color
        if self.is_light:
            past_fg = "#B8BAC4"
            past_bg = "#F4F5F8"
            normal_fg = "#1E1E24"
            normal_bg = "#F0F2F6"
        else:
            past_fg = "#52525E"
            past_bg = "#18181E"
            normal_fg = "#E6E6EE"
            normal_bg = "#24242D"

        self._cell_dates: List[date | None] = [None] * 42

        for idx, btn in enumerate(self.day_buttons):
            day_num = idx - first_weekday + 1
            if 1 <= day_num <= num_days:
                cur_d = date(self.view_year, self.view_month, day_num)
                self._cell_dates[idx] = cur_d
                d_str = cur_d.strftime("%Y-%m-%d")
                is_past = cur_d < today
                is_today = cur_d == today
                is_manual = d_str in self.selected_dates
                is_rule = self._is_matched_by_fixed_rule(cur_d, selected_day_nums)
                is_rest = is_manual or is_rule

                btn.setVisible(True)
                btn.setText(f"{day_num}\n休" if is_rest else str(day_num))

                if is_rest:
                    if is_past:
                        btn.setStyleSheet(
                            f"""
                            QPushButton {{
                                background-color: {past_bg};
                                color: {past_fg};
                                border: 1px solid {acc};
                                border-radius: 7px;
                                font-size: 10px;
                            }}
                            """
                        )
                    else:
                        btn.setStyleSheet(
                            f"""
                            QPushButton {{
                                background-color: {acc};
                                color: #FFFFFF;
                                border: {'2px solid #FFFFFF' if is_today else 'none'};
                                border-radius: 7px;
                                font-size: 10px;
                            }}
                            """
                        )
                else:
                    fg = past_fg if is_past else normal_fg
                    bg = past_bg if is_past else normal_bg
                    border_css = f"1.5px solid {acc}" if is_today else "1px solid transparent"
                    btn.setStyleSheet(
                        f"""
                        QPushButton {{
                            background-color: {bg};
                            color: {fg};
                            border: {border_css};
                            border-radius: 7px;
                            font-size: 11px;
                        }}
                        QPushButton:hover {{
                            border-color: {acc};
                        }}
                        """
                    )
            else:
                btn.setVisible(False)

    def _on_day_clicked(self, idx: int) -> None:
        cur_d = self._cell_dates[idx]
        if cur_d is None:
            return
        d_str = cur_d.strftime("%Y-%m-%d")
        if d_str in self.selected_dates:
            self.selected_dates.remove(d_str)
        else:
            self.selected_dates.add(d_str)
        self._refresh_calendar_grid()

    def _go_prev_month(self) -> None:
        if self.view_month == 1:
            self.view_year -= 1
            self.view_month = 12
        else:
            self.view_month -= 1
        self._refresh_calendar_grid()

    def _go_next_month(self) -> None:
        if self.view_month == 12:
            self.view_year += 1
            self.view_month = 1
        else:
            self.view_month += 1
        self._refresh_calendar_grid()

    def _go_today(self) -> None:
        today = date.today()
        self.view_year = today.year
        self.view_month = today.month
        self._refresh_calendar_grid()

    def _clear_current_month_manual(self) -> None:
        prefix = f"{self.view_year:04d}-{self.view_month:02d}-"
        self.selected_dates = {d for d in self.selected_dates if not d.startswith(prefix)}
        self._refresh_calendar_grid()

    def get_result(self) -> dict:
        return {
            "custom_rest_dates": sorted(self.selected_dates),
            "custom_fixed_weekdays": sorted(self.fixed_weekdays),
            "custom_monthly_selected_days_enabled": self.monthly_selected_days_enabled,
        }


class _ThemedCalendarWidget(QCalendarWidget):
    """自定义日历弹窗：将超过最大可选日期（明天及以后）的日期显著降色显示，提示不可选。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_light = False

    def set_light_mode(self, is_light: bool) -> None:
        self._is_light = is_light
        self.updateCells()

    def paintCell(self, painter: QPainter, rect, qdate: QDate) -> None:
        if qdate > self.maximumDate():
            painter.save()
            painter.setPen(QColor("#C4C7D2") if self._is_light else QColor("#454554"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(qdate.day()))
            painter.restore()
            return
        super().paintCell(painter, rect, qdate)


class CompTimeDialog(QDialog):
    """
    「管理我的调休」独立非模态窗口：
    1. 查看当前剩余调休余额与上次加班时长
    2. 添加或编辑加班记录（选择日期、实际下班时间、备注；自动按规则计算加班与调休时长，也支持编辑模式手动微调时长）
    3. 手动直接增减/修改调休余额时长
    4. 查看、编辑、删除历史加班记录列表
    """

    data_changed = Signal()

    def __init__(
        self,
        comp_manager: CompTimeManager,
        work_end_str: str = "18:30",
        theme_mode: str = "dark",
        accent_color: str = "#FF6B00",
        lunch_start_str: str = "12:00",
        lunch_end_str: str = "13:00",
        today_is_workday: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.comp_manager = comp_manager
        self.work_end_str = work_end_str
        self.lunch_start_str = lunch_start_str
        self.lunch_end_str = lunch_end_str
        self.today_is_workday = today_is_workday
        self.is_light = theme_mode == "light"
        self.accent_color = accent_color
        self._editing_record_id: str | None = None
        self._drag_pos: QPoint | None = None

        self.setFixedSize(MAIN_WIDTH, 560)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)

        self._build_ui()
        self._apply_style()
        self._refresh_view()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor("#F5F6F8") if self.is_light else QColor("#151519")
        border = QColor("#CFD4E0") if self.is_light else QColor("#2D2D36")
        rect = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
        painter.setBrush(QBrush(bg))
        painter.setPen(QPen(border, 1.4))
        painter.drawRoundedRect(rect, 18.0, 18.0)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # 1. 顶部标题与最小化/关闭
        top_row = QHBoxLayout()
        top_row.setSpacing(2)
        self.lbl_title = QLabel("管理我的调休", self)
        self.lbl_title.setFont(_source_han_font(11, QFont.Weight.Bold))
        self.btn_min = VectorIconButton("min", self, self.accent_color)
        self.btn_min.set_light_mode(self.is_light)
        self.btn_min.setToolTip("最小化")
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_close = VectorIconButton("close", self, self.accent_color)
        self.btn_close.set_light_mode(self.is_light)
        self.btn_close.clicked.connect(self.accept)
        top_row.addWidget(self.lbl_title)
        top_row.addStretch(1)
        top_row.addWidget(self.btn_min)
        top_row.addWidget(self.btn_close)
        root.addLayout(top_row)

        # 2. 顶部统计概览卡片
        self.summary_card = CardFrame(self, radius=12)
        sum_layout = QHBoxLayout(self.summary_card)
        sum_layout.setContentsMargins(14, 10, 14, 10)
        sum_layout.setSpacing(12)

        bal_col = QVBoxLayout()
        bal_col.setSpacing(2)
        self.lbl_bal_cap = QLabel("剩余调休余额", self.summary_card)
        self.lbl_bal_cap.setFont(_source_han_font(8))
        self.lbl_bal_val = QLabel("0.0 小时", self.summary_card)
        self.lbl_bal_val.setFont(_source_han_font(15, QFont.Weight.Bold))
        bal_col.addWidget(self.lbl_bal_cap)
        bal_col.addWidget(self.lbl_bal_val)

        ot_col = QVBoxLayout()
        ot_col.setSpacing(2)
        self.lbl_ot_cap = QLabel("上次加班时长", self.summary_card)
        self.lbl_ot_cap.setFont(_source_han_font(8))
        self.lbl_ot_cap.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_ot_val = QLabel("0.0 小时", self.summary_card)
        self.lbl_ot_val.setFont(_source_han_font(15, QFont.Weight.Bold))
        self.lbl_ot_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        ot_col.addWidget(self.lbl_ot_cap)
        ot_col.addWidget(self.lbl_ot_val)

        sum_layout.addLayout(bal_col, 1)
        sum_layout.addLayout(ot_col, 1)
        root.addWidget(self.summary_card)

        # 3. 添加 / 编辑加班记录卡片
        self.form_card = CardFrame(self, radius=12)
        f_layout = QVBoxLayout(self.form_card)
        f_layout.setContentsMargins(12, 10, 12, 10)
        f_layout.setSpacing(8)

        self.lbl_form_title = QLabel("添加加班记录", self.form_card)
        self.lbl_form_title.setFont(_source_han_font(9, QFont.Weight.Bold))
        f_layout.addWidget(self.lbl_form_title)

        row1 = QHBoxLayout()
        row1.setSpacing(6)
        self.edit_date = QDateEdit(QDate.currentDate(), self.form_card)
        self.edit_date.setDisplayFormat("yyyy-MM-dd")
        self.edit_date.setMaximumDate(QDate.currentDate())
        self.edit_date.setCalendarPopup(True)
        self.edit_date.setCalendarWidget(_ThemedCalendarWidget(self.form_card))
        self.edit_date.setFont(_source_han_font(9, QFont.Weight.Bold))
        self.edit_date.dateChanged.connect(self._on_time_preview_changed)

        wh, wm = 18, 30
        try:
            parts = self.work_end_str.split(":")
            wh, wm = int(parts[0]), int(parts[1])
        except Exception:
            pass

        self.edit_start_time = QTimeEdit(QTime(wh, wm), self.form_card)
        self.edit_start_time.setDisplayFormat("HH:mm")
        self.edit_start_time.setFont(_source_han_font(9, QFont.Weight.Bold))
        self.edit_start_time.timeChanged.connect(self._on_time_preview_changed)

        self.lbl_time_sep = QLabel("-", self.form_card)
        self.lbl_time_sep.setFont(_source_han_font(9, QFont.Weight.Bold))

        self.edit_end_time = QTimeEdit(QTime(20, 30), self.form_card)
        self.edit_end_time.setDisplayFormat("HH:mm")
        self.edit_end_time.setFont(_source_han_font(9, QFont.Weight.Bold))
        self.edit_end_time.timeChanged.connect(self._on_time_preview_changed)

        row1.addWidget(self.edit_date, 1)
        row1.addWidget(self.edit_start_time)
        row1.addWidget(self.lbl_time_sep)
        row1.addWidget(self.edit_end_time)
        f_layout.addLayout(row1)

        # 编辑模式时允许直接微调加班/调休小时数
        self.edit_hours_row_widget = QWidget(self.form_card)
        eh_row = QHBoxLayout(self.edit_hours_row_widget)
        eh_row.setContentsMargins(0, 0, 0, 0)
        eh_row.setSpacing(6)
        self.lbl_eh_ot = QLabel("加班(h):", self.edit_hours_row_widget)
        self.lbl_eh_ot.setFont(_source_han_font(8))
        self.spin_edit_ot = QDoubleSpinBox(self.edit_hours_row_widget)
        self.spin_edit_ot.setRange(0.0, 24.0)
        self.spin_edit_ot.setSingleStep(0.5)
        self.spin_edit_ot.setDecimals(2)
        self.spin_edit_ot.setFont(_source_han_font(9, QFont.Weight.Bold))

        self.lbl_eh_comp = QLabel("调休(h):", self.edit_hours_row_widget)
        self.lbl_eh_comp.setFont(_source_han_font(8))
        self.spin_edit_comp = QDoubleSpinBox(self.edit_hours_row_widget)
        self.spin_edit_comp.setRange(0.0, 24.0)
        self.spin_edit_comp.setSingleStep(0.5)
        self.spin_edit_comp.setDecimals(2)
        self.spin_edit_comp.setFont(_source_han_font(9, QFont.Weight.Bold))

        eh_row.addWidget(self.lbl_eh_ot)
        eh_row.addWidget(self.spin_edit_ot, 1)
        eh_row.addWidget(self.lbl_eh_comp)
        eh_row.addWidget(self.spin_edit_comp, 1)
        self.edit_hours_row_widget.setVisible(False)
        f_layout.addWidget(self.edit_hours_row_widget)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        self.edit_note = QLineEdit(self.form_card)
        self.edit_note.setPlaceholderText("备注 (选填)")
        self.edit_note.setFont(_source_han_font(9))

        self.chk_deduct_lunch = QCheckBox("减去午休", self.form_card)
        self.chk_deduct_lunch.setChecked(True)
        self.chk_deduct_lunch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_deduct_lunch.setFont(_source_han_font(8))
        self.chk_deduct_lunch.setToolTip(f"自动扣除午休时段 ({self.lunch_start_str} - {self.lunch_end_str})")
        self.chk_deduct_lunch.toggled.connect(self._on_time_preview_changed)

        self.btn_cancel_edit = QPushButton("取消", self.form_card)
        self.btn_cancel_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel_edit.setFixedHeight(28)
        self.btn_cancel_edit.setFont(_source_han_font(9, QFont.Weight.Bold))
        self.btn_cancel_edit.clicked.connect(self._cancel_edit)
        self.btn_cancel_edit.setVisible(False)

        self.btn_submit_rec = QPushButton("添加记录", self.form_card)
        self.btn_submit_rec.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_submit_rec.setFixedHeight(28)
        self.btn_submit_rec.setFixedWidth(74)
        self.btn_submit_rec.setFont(_source_han_font(9, QFont.Weight.Bold))
        self.btn_submit_rec.clicked.connect(self._submit_record)

        row2.addWidget(self.edit_note, 1)
        row2.addWidget(self.chk_deduct_lunch)
        row2.addWidget(self.btn_cancel_edit)
        row2.addWidget(self.btn_submit_rec)
        f_layout.addLayout(row2)

        self.lbl_form_error = QLabel("", self.form_card)
        self.lbl_form_error.setFont(_source_han_font(8))
        self.lbl_form_error.setStyleSheet("color: #EF4444;")
        self.lbl_form_error.setVisible(False)
        f_layout.addWidget(self.lbl_form_error)

        root.addWidget(self.form_card)

        # 4. 手动修改/添加调休时长卡片
        self.adjust_card = CardFrame(self, radius=12)
        adj_layout = QHBoxLayout(self.adjust_card)
        adj_layout.setContentsMargins(12, 8, 12, 8)
        adj_layout.setSpacing(8)

        self.lbl_adj_title = QLabel("手动增减调休:", self.adjust_card)
        self.lbl_adj_title.setFont(_source_han_font(9, QFont.Weight.Bold))

        self.spin_adj_hours = QDoubleSpinBox(self.adjust_card)
        self.spin_adj_hours.setRange(-200.0, 200.0)
        self.spin_adj_hours.setSingleStep(0.5)
        self.spin_adj_hours.setDecimals(1)
        self.spin_adj_hours.setSuffix(" 小时")
        self.spin_adj_hours.setValue(1.0)
        self.spin_adj_hours.setFont(_source_han_font(9, QFont.Weight.Bold))

        self.btn_apply_adj = QPushButton("应用调整", self.adjust_card)
        self.btn_apply_adj.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply_adj.setFixedHeight(26)
        self.btn_apply_adj.setFont(_source_han_font(9, QFont.Weight.Bold))
        self.btn_apply_adj.clicked.connect(self._apply_manual_adjustment)

        adj_layout.addWidget(self.lbl_adj_title)
        adj_layout.addWidget(self.spin_adj_hours, 1)
        adj_layout.addWidget(self.btn_apply_adj)
        root.addWidget(self.adjust_card)

        # 5. 加班记录列表卡片（可滚轮滑动）
        self.list_card = CardFrame(self, radius=12)
        l_layout = QVBoxLayout(self.list_card)
        l_layout.setContentsMargins(12, 10, 10, 10)
        l_layout.setSpacing(6)

        self.lbl_list_title = QLabel("加班记录明细", self.list_card)
        self.lbl_list_title.setFont(_source_han_font(9, QFont.Weight.Bold))
        l_layout.addWidget(self.lbl_list_title)

        self.rec_scroll = QScrollArea(self.list_card)
        self.rec_scroll.setWidgetResizable(True)
        self.rec_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.rec_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.rec_container = QWidget()
        self.rec_layout = QVBoxLayout(self.rec_container)
        self.rec_layout.setContentsMargins(0, 2, 4, 2)
        self.rec_layout.setSpacing(6)
        self.rec_scroll.setWidget(self.rec_container)
        l_layout.addWidget(self.rec_scroll, 1)

        root.addWidget(self.list_card, 1)

    def apply_theme(self, theme_mode: str | bool, accent_color: str) -> None:
        self.is_light = theme_mode if isinstance(theme_mode, bool) else (str(theme_mode) == "light")
        self.accent_color = accent_color
        if hasattr(self, "btn_min"):
            self.btn_min.set_light_mode(self.is_light)
            self.btn_min.set_accent_color(accent_color)
        if hasattr(self, "btn_close"):
            self.btn_close.set_light_mode(self.is_light)
            self.btn_close.set_accent_color(accent_color)
        self._apply_style()
        if hasattr(self, "_refresh_view"):
            self._refresh_view()
        self.update()

    def _apply_style(self) -> None:
        acc = self.accent_color
        if self.is_light:
            card_bg = "#FFFFFF"
            card_border = "#E2E5EC"
            primary_text = "#18181C"
            muted_text = "#7A7A86"
            input_bg = "#F4F5F8"
            input_border = "#D6D9E2"
            scroll_handle = "#D0D3DC"
        else:
            card_bg = "#1C1C22"
            card_border = "#2A2A34"
            primary_text = "#F4F4F6"
            muted_text = "#8A8A96"
            input_bg = "#25252E"
            input_border = "#343440"
            scroll_handle = "#343440"

        self.lbl_title.setStyleSheet(f"color: {primary_text};")
        for c in (self.summary_card, self.form_card, self.adjust_card, self.list_card):
            c.set_colors(card_bg, card_border)

        self.lbl_bal_cap.setStyleSheet(f"color: {muted_text};")
        self.lbl_ot_cap.setStyleSheet(f"color: {muted_text};")
        self.lbl_bal_val.setStyleSheet(f"color: {acc};")
        self.lbl_ot_val.setStyleSheet(f"color: {primary_text};")
        self.lbl_form_title.setStyleSheet(f"color: {muted_text};")
        self.lbl_adj_title.setStyleSheet(f"color: {primary_text};")
        self.lbl_list_title.setStyleSheet(f"color: {muted_text};")
        self.lbl_eh_ot.setStyleSheet(f"color: {muted_text};")
        self.lbl_eh_comp.setStyleSheet(f"color: {muted_text};")
        self.lbl_time_sep.setStyleSheet(f"color: {muted_text};")

        input_qss = f"""
            QDateEdit, QTimeEdit, QDoubleSpinBox, QLineEdit {{
                background-color: {input_bg};
                color: {primary_text};
                border: 1px solid {input_border};
                border-radius: 6px;
                padding: 3px 6px;
            }}
            QDateEdit:focus, QTimeEdit:focus, QDoubleSpinBox:focus, QLineEdit:focus {{
                border-color: {acc};
            }}
        """
        for w in (
            self.edit_date,
            self.edit_start_time,
            self.edit_end_time,
            self.edit_note,
            self.spin_adj_hours,
            self.spin_edit_ot,
            self.spin_edit_comp,
        ):
            w.setStyleSheet(input_qss)

        self.chk_deduct_lunch.setStyleSheet(
            f"""
            QCheckBox {{
                color: {primary_text};
                spacing: 4px;
            }}
            QCheckBox::indicator {{
                width: 13px;
                height: 13px;
                border-radius: 4px;
                border: 1.5px solid {muted_text};
                background-color: {input_bg};
            }}
            QCheckBox::indicator:checked {{
                border-color: {acc};
                background-color: {acc};
            }}
            """
        )

        cal = self.edit_date.calendarWidget()
        if cal is not None:
            if isinstance(cal, _ThemedCalendarWidget):
                cal.set_light_mode(self.is_light)
            cal.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
            cal_bg = "#FFFFFF" if self.is_light else "#1C1C22"
            cal_nav_bg = "#F4F5F8" if self.is_light else "#25252E"
            cal_border = "#D6D9E2" if self.is_light else "#343440"
            cal_hover = "#EAECEF" if self.is_light else "#2E2E3A"
            cal.setStyleSheet(
                f"""
                QCalendarWidget QWidget {{
                    background-color: {cal_bg};
                    color: {primary_text};
                    alternate-background-color: {cal_nav_bg};
                }}
                QCalendarWidget QWidget#qt_calendar_navigationbar {{
                    background-color: {cal_nav_bg};
                    border-bottom: 1px solid {cal_border};
                    padding: 2px;
                }}
                QCalendarWidget QToolButton {{
                    color: {primary_text};
                    background-color: transparent;
                    border: none;
                    border-radius: 4px;
                    padding: 3px 6px;
                    font-weight: bold;
                }}
                QCalendarWidget QToolButton:hover {{
                    background-color: {cal_hover};
                    color: {acc};
                }}
                QCalendarWidget QMenu {{
                    background-color: {cal_bg};
                    color: {primary_text};
                    border: 1px solid {cal_border};
                }}
                QCalendarWidget QSpinBox {{
                    background-color: {input_bg};
                    color: {primary_text};
                    border: 1px solid {cal_border};
                    border-radius: 4px;
                    padding: 1px 4px;
                }}
                QCalendarWidget QAbstractItemView:enabled {{
                    background-color: {cal_bg};
                    color: {primary_text};
                    selection-background-color: {acc};
                    selection-color: #FFFFFF;
                    outline: 0;
                }}
                QCalendarWidget QAbstractItemView:disabled {{
                    color: {muted_text};
                }}
                """
            )

        self.btn_submit_rec.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {acc};
                color: #FFFFFF;
                border: none;
                border-radius: 7px;
            }}
            QPushButton:hover {{
                background-color: {acc};
                color: #FFFFFF;
            }}
            """
        )

        sub_btn_qss = f"""
            QPushButton {{
                background-color: {input_bg};
                color: {primary_text};
                border: 1px solid {input_border};
                border-radius: 7px;
                padding: 2px 8px;
            }}
            QPushButton:hover {{
                border-color: {acc};
                color: {acc};
            }}
        """
        self.btn_apply_adj.setStyleSheet(sub_btn_qss)
        self.btn_cancel_edit.setStyleSheet(sub_btn_qss)

        self.rec_container.setStyleSheet("background: transparent;")
        self.rec_scroll.setStyleSheet(
            f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ background: transparent; width: 5px; }}
            QScrollBar::handle:vertical {{ background: {scroll_handle}; border-radius: 2px; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
            """
        )

    def _on_time_preview_changed(self) -> None:
        if hasattr(self, "lbl_form_error"):
            self.lbl_form_error.setVisible(False)
        if self._editing_record_id is not None:
            start_str = self.edit_start_time.time().toString("HH:mm")
            end_str = self.edit_end_time.time().toString("HH:mm")
            ot_h, comp_h = CompTimeManager.calc_overtime_and_comp(
                start_str,
                end_str,
                deduct_lunch=self.chk_deduct_lunch.isChecked(),
                lunch_start_str=self.lunch_start_str,
                lunch_end_str=self.lunch_end_str,
            )
            self.spin_edit_ot.setValue(ot_h)
            self.spin_edit_comp.setValue(comp_h)

    def _validate_overtime_datetime(self, d_str: str, s_str: str, e_str: str) -> str | None:
        try:
            sel_date = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            return "日期格式无效"

        now = datetime.now()
        today = now.date()
        if sel_date > today:
            return "不能添加未来日期的加班记录"

        sh, sm = TimeCalculator.parse_hm(s_str, (18, 30))
        eh, em = TimeCalculator.parse_hm(e_str, (20, 30))
        start_dt = datetime.combine(sel_date, dt_time(sh, sm))
        end_dt = datetime.combine(sel_date, dt_time(eh, em))
        if end_dt < start_dt and eh < 12:
            end_dt += timedelta(days=1)

        if sel_date == today:
            wh, wm = TimeCalculator.parse_hm(self.work_end_str, (18, 30))
            work_end_dt = datetime.combine(today, dt_time(wh, wm))
            if self.today_is_workday and now < work_end_dt:
                return "今日尚未下班，暂不能添加今日加班记录"
            if start_dt > now or end_dt > now:
                return "加班时间不能超过当前时间"
        elif end_dt > now:
            return "加班时间不能超过当前时间"
        return None

    def _submit_record(self) -> None:
        d_str = self.edit_date.date().toString("yyyy-MM-dd")
        s_str = self.edit_start_time.time().toString("HH:mm")
        e_str = self.edit_end_time.time().toString("HH:mm")
        note = self.edit_note.text().strip()

        err = self._validate_overtime_datetime(d_str, s_str, e_str)
        if err is not None:
            self.lbl_form_error.setText(err)
            self.lbl_form_error.setVisible(True)
            return
        self.lbl_form_error.setVisible(False)

        if self._editing_record_id is None:
            self.comp_manager.add_record(
                d_str,
                s_str,
                e_str,
                note,
                deduct_lunch=self.chk_deduct_lunch.isChecked(),
                lunch_start_str=self.lunch_start_str,
                lunch_end_str=self.lunch_end_str,
            )
        else:
            self.comp_manager.update_record(
                self._editing_record_id,
                d_str,
                s_str,
                e_str,
                self.spin_edit_ot.value(),
                self.spin_edit_comp.value(),
                note,
            )
            self._cancel_edit()

        self.edit_note.clear()
        self._refresh_view()
        self.data_changed.emit()

    def _start_edit_record(self, rec: OvertimeRecord) -> None:
        self._editing_record_id = rec.id
        self.lbl_form_title.setText(f"编辑加班记录 ({rec.date_str})")
        self.btn_submit_rec.setText("保存修改")
        self.btn_cancel_edit.setVisible(True)
        self.edit_hours_row_widget.setVisible(True)

        qd = QDate.fromString(rec.date_str, "yyyy-MM-dd")
        if qd.isValid():
            self.edit_date.setDate(qd)
        st = QTime.fromString(rec.start_time_str, "HH:mm")
        if st.isValid():
            self.edit_start_time.setTime(st)
        et = QTime.fromString(rec.end_time_str, "HH:mm")
        if et.isValid():
            self.edit_end_time.setTime(et)

        self.spin_edit_ot.setValue(rec.overtime_hours)
        self.spin_edit_comp.setValue(rec.comp_hours)
        self.edit_note.setText(rec.note)

    def _cancel_edit(self) -> None:
        self._editing_record_id = None
        self.lbl_form_title.setText("添加加班记录")
        self.btn_submit_rec.setText("添加记录")
        self.btn_cancel_edit.setVisible(False)
        self.edit_hours_row_widget.setVisible(False)
        self.edit_note.clear()

    def _delete_record(self, rec_id: str) -> None:
        if self._editing_record_id == rec_id:
            self._cancel_edit()
        self.comp_manager.delete_record(rec_id)
        self._refresh_view()
        self.data_changed.emit()

    def _apply_manual_adjustment(self) -> None:
        delta = float(self.spin_adj_hours.value())
        if abs(delta) > 1e-6:
            self.comp_manager.add_manual_adjustment(delta)
            self._refresh_view()
            self.data_changed.emit()

    def _refresh_view(self) -> None:
        bal = self.comp_manager.get_balance_hours()
        last_ot = self.comp_manager.get_last_overtime_hours()
        self.lbl_bal_val.setText(f"{bal:.1f} 小时")
        self.lbl_ot_val.setText(f"{last_ot:.1f} 小时")
        self._on_time_preview_changed()

        while self.rec_layout.count():
            item = self.rec_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        row_bg = "#F5F6FA" if self.is_light else "#25252E"
        text_main = "#18181C" if self.is_light else "#F4F4F6"
        text_sub = "#6A6A76" if self.is_light else "#9A9AA6"
        acc = self.accent_color

        if not self.comp_manager.records:
            empty_lbl = QLabel("暂无加班记录，可在上方添加", self.rec_container)
            empty_lbl.setFont(_source_han_font(9))
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet(f"color: {text_sub}; padding: 18px 0;")
            self.rec_layout.addWidget(empty_lbl)
        else:
            for rec in self.comp_manager.records:
                row = QFrame(self.rec_container)
                row.setStyleSheet(f"QFrame {{ background-color: {row_bg}; border-radius: 7px; }}")
                rl = QHBoxLayout(row)
                rl.setContentsMargins(8, 6, 8, 6)
                rl.setSpacing(6)

                info_col = QVBoxLayout()
                info_col.setSpacing(1)
                top_txt = f"{rec.date_str}  {rec.start_time_str} - {rec.end_time_str}"
                lbl_top = QLabel(top_txt, row)
                lbl_top.setFont(_source_han_font(9, QFont.Weight.Bold))
                lbl_top.setStyleSheet(f"color: {text_main}; background: transparent;")

                sub_row = QHBoxLayout()
                sub_row.setContentsMargins(0, 0, 0, 0)
                sub_row.setSpacing(6)
                sub_txt = f"加班 {rec.overtime_hours:.1f}h · 调休 +{rec.comp_hours:.1f}h"
                lbl_sub = QLabel(sub_txt, row)
                lbl_sub.setFont(_source_han_font(8))
                lbl_sub.setStyleSheet(
                    f"color: {acc if rec.comp_hours > 0 else text_sub}; background: transparent;"
                )
                sub_row.addWidget(lbl_sub)

                if rec.note:
                    note_font = _source_han_font(8)
                    fm = QFontMetrics(note_font)
                    elided = fm.elidedText(rec.note, Qt.TextElideMode.ElideRight, 86)
                    lbl_note = QLabel(elided, row)
                    lbl_note.setFont(note_font)
                    lbl_note.setStyleSheet(f"color: {text_sub}; background: transparent;")
                    lbl_note.setToolTip(rec.note)
                    sub_row.addWidget(lbl_note, 1)
                else:
                    sub_row.addStretch(1)

                info_col.addWidget(lbl_top)
                info_col.addLayout(sub_row)

                btn_edit = QPushButton("编辑", row)
                btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_edit.setFixedSize(38, 22)
                btn_edit.setFont(_source_han_font(8, QFont.Weight.Bold))
                btn_edit.setStyleSheet(
                    f"QPushButton {{ background: transparent; color: {acc}; border: 1px solid {acc}; border-radius: 5px; }}"
                )
                btn_edit.clicked.connect(lambda checked=False, r=rec: self._start_edit_record(r))

                btn_del = QPushButton("删除", row)
                btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_del.setFixedSize(38, 22)
                btn_del.setFont(_source_han_font(8, QFont.Weight.Bold))
                btn_del.setStyleSheet(
                    "QPushButton { background: transparent; color: #EF4444; border: 1px solid #EF4444; border-radius: 5px; }"
                )
                btn_del.clicked.connect(lambda checked=False, rid=rec.id: self._delete_record(rid))

                rl.addLayout(info_col, 1)
                rl.addWidget(btn_edit)
                rl.addWidget(btn_del)
                self.rec_layout.addWidget(row)

        self.rec_layout.addStretch(1)


class _ThemedToolTipPopup(QWidget):
    """自绘无系统阴影/无黑底的圆角悬停提示框，严格匹配浅色/深色主题。"""

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._is_light = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 5, 9, 5)
        self._label = QLabel(self)
        self._label.setFont(_source_han_font(9))
        layout.addWidget(self._label)
        self._apply_colors()

    def set_light_mode(self, is_light: bool) -> None:
        self._is_light = is_light
        self._apply_colors()

    def _apply_colors(self) -> None:
        text_color = "#18181C" if self._is_light else "#EAEAEF"
        self._label.setStyleSheet(f"color: {text_color}; background: transparent;")
        self.update()

    def show_tip(self, text: str, global_pos: QPoint) -> None:
        self._label.setText(text)
        self.adjustSize()

        x = global_pos.x() + 10
        y = global_pos.y() + 14
        screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            if x + self.width() > geo.right() - 4:
                x = max(geo.left() + 4, global_pos.x() - self.width() - 8)
            if y + self.height() > geo.bottom() - 4:
                y = max(geo.top() + 4, global_pos.y() - self.height() - 8)

        self.move(x, y)
        self.show()
        self.raise_()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor("#FFFFFF") if self._is_light else QColor("#1F1F25")
        border = QColor("#DCDFE6") if self._is_light else QColor("#30303A")

        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, 6, 6)
        painter.fillPath(path, bg)
        painter.setPen(QPen(border, 1.0))
        painter.drawPath(path)


class ThemedToolTipManager(QObject):
    """拦截全局 QEvent.ToolTip，使用自绘弹窗替代 Windows 原生黑底 QTipLabel。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._popup = _ThemedToolTipPopup()
        self._target: QWidget | None = None

    def set_light_mode(self, is_light: bool) -> None:
        self._popup.set_light_mode(is_light)

    def eventFilter(self, obj, event) -> bool:
        try:
            etype = event.type()
            if etype == QEvent.Type.ToolTip:
                if isinstance(obj, QWidget) and obj.toolTip():
                    self._target = obj
                    self._popup.show_tip(obj.toolTip(), event.globalPos())
                else:
                    self._target = None
                    self._popup.hide()
                event.accept()
                return True

            if self._popup.isVisible() and etype in (
                QEvent.Type.Leave,
                QEvent.Type.MouseButtonPress,
                QEvent.Type.Wheel,
                QEvent.Type.WindowDeactivate,
                QEvent.Type.Hide,
            ):
                if obj is self._target or etype in (
                    QEvent.Type.MouseButtonPress,
                    QEvent.Type.WindowDeactivate,
                ):
                    self._popup.hide()
                    self._target = None
        except RuntimeError:
            return False
        return False


class CloseConfirmDialog(QDialog):
    """关闭确认弹窗：询问是否最小化到任务栏（是 / 否），匹配暗黑高级与白色简约主题。"""

    def __init__(self, theme_mode: str = "dark", accent_color: str = "#FF6B00", parent=None):
        super().__init__(parent)
        self.is_light = theme_mode == "light"
        self.accent_color = accent_color
        self.choice = "cancel"  # "yes" | "no" | "cancel"

        self.setFixedSize(268, 134)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        top_row = QHBoxLayout()
        self.lbl_title = QLabel("关闭提示", self)
        self.lbl_title.setFont(_source_han_font(10, QFont.Weight.Bold))
        self.btn_x = VectorIconButton("close", self, accent_color)
        self.btn_x.setLightMode(self.is_light) if hasattr(self.btn_x, "setLightMode") else self.btn_x.set_light_mode(self.is_light)
        self.btn_x.clicked.connect(self.reject)
        top_row.addWidget(self.lbl_title)
        top_row.addStretch(1)
        top_row.addWidget(self.btn_x)
        root.addLayout(top_row)

        self.lbl_msg = QLabel("是否最小化到任务栏？", self)
        self.lbl_msg.setFont(_source_han_font(10))
        self.lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.lbl_msg)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_no = QPushButton("否", self)
        self.btn_no.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_no.setFixedHeight(32)
        self.btn_no.setFont(_source_han_font(10, QFont.Weight.Bold))
        self.btn_no.clicked.connect(self._on_no)

        self.btn_yes = QPushButton("是", self)
        self.btn_yes.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_yes.setFixedHeight(32)
        self.btn_yes.setFont(_source_han_font(10, QFont.Weight.Bold))
        self.btn_yes.clicked.connect(self._on_yes)

        btn_row.addWidget(self.btn_no, 1)
        btn_row.addWidget(self.btn_yes, 1)
        root.addLayout(btn_row)

        self._apply_style()

    def _on_yes(self) -> None:
        self.choice = "yes"
        self.accept()

    def _on_no(self) -> None:
        self.choice = "no"
        self.accept()

    def apply_theme(self, theme_mode: str | bool, accent_color: str) -> None:
        self.is_light = theme_mode if isinstance(theme_mode, bool) else (str(theme_mode) == "light")
        self.accent_color = accent_color
        if hasattr(self, "btn_min"):
            self.btn_min.set_light_mode(self.is_light)
            self.btn_min.set_accent_color(accent_color)
        if hasattr(self, "btn_close"):
            self.btn_close.set_light_mode(self.is_light)
            self.btn_close.set_accent_color(accent_color)
        self._apply_style()
        if hasattr(self, "_refresh_view"):
            self._refresh_view()
        self.update()

    def _apply_style(self) -> None:
        primary_text = "#18181C" if self.is_light else "#F4F4F6"
        muted_text = "#6A6A76" if self.is_light else "#9A9AA6"
        no_bg = "#EFF0F4" if self.is_light else "#25252E"
        no_border = "#DCDFE6" if self.is_light else "#343440"

        self.lbl_title.setStyleSheet(f"color: {muted_text};")
        self.lbl_msg.setStyleSheet(f"color: {primary_text};")
        self.btn_yes.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {self.accent_color};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: {self.accent_color};
            }}
            """
        )
        self.btn_no.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {no_bg};
                color: {primary_text};
                border: 1px solid {no_border};
                border-radius: 8px;
            }}
            QPushButton:hover {{
                border-color: {self.accent_color};
                color: {self.accent_color};
            }}
            """
        )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor("#FFFFFF") if self.is_light else QColor("#17171B")
        border = QColor("#DCDFE6") if self.is_light else QColor("#2E2E38")
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        painter.fillPath(path, bg)
        painter.setPen(QPen(border, 1.0))
        painter.drawPath(path)


class ToastPopup(QWidget):
    """轻提示浮层：居中显示在父窗口下方，定时自动消失。"""

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._is_light = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        self._label = QLabel("", self)
        self._label.setFont(_source_han_font(9, QFont.Weight.Bold))
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, is_light: bool = False, duration_ms: int = 2400) -> None:
        self._is_light = is_light
        text_color = "#18181C" if is_light else "#F4F4F6"
        self._label.setStyleSheet(f"color: {text_color}; background: transparent;")
        self._label.setText(text)
        self.adjustSize()

        parent = self.parentWidget()
        if parent is not None:
            geo = parent.geometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + geo.height() - self.height() - 56
            self.move(x, y)

        self.show()
        self.raise_()
        self._timer.start(duration_ms)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor("#FFFFFF") if self._is_light else QColor("#22222A")
        border = QColor("#DCDFE6") if self._is_light else QColor("#363644")
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        painter.fillPath(path, bg)
        painter.setPen(QPen(border, 1.0))
        painter.drawPath(path)


class UpdateDialog(QDialog):
    """两段式在线更新弹窗：阶段1 立即下载（带进度条），阶段2 确认安装并重启。"""

    download_requested = Signal()
    install_requested = Signal()

    def __init__(
        self,
        current_version: str,
        latest_version: str,
        changelog: str,
        theme_mode: str = "dark",
        accent_color: str = "#FF6B00",
        parent=None,
    ):
        super().__init__(parent)
        self.is_light = theme_mode == "light"
        self.accent_color = accent_color
        self._stage = "ready"  # "ready" | "downloading" | "downloaded"
        self._drag_pos: QPoint | None = None

        self.setFixedSize(MAIN_WIDTH, 300)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(2)
        self.lbl_title = QLabel(f"发现新版本 v{latest_version}", self)
        self.lbl_title.setFont(_source_han_font(11, QFont.Weight.Bold))
        self.btn_min = VectorIconButton("min", self, accent_color)
        self.btn_min.set_light_mode(self.is_light)
        self.btn_min.setToolTip("最小化")
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_close = VectorIconButton("close", self, accent_color)
        self.btn_close.set_light_mode(self.is_light)
        self.btn_close.clicked.connect(self.reject)
        top_row.addWidget(self.lbl_title)
        top_row.addStretch(1)
        top_row.addWidget(self.btn_min)
        top_row.addWidget(self.btn_close)
        root.addLayout(top_row)

        self.lbl_sub = QLabel(f"当前版本 v{current_version}  →  最新版本 v{latest_version}", self)
        self.lbl_sub.setFont(_source_han_font(8))
        root.addWidget(self.lbl_sub)

        self.txt_changelog = QTextEdit(self)
        self.txt_changelog.setReadOnly(True)
        self.txt_changelog.setFont(_source_han_font(9))
        self.txt_changelog.setPlainText(changelog.strip() or "本次更新包含体验优化与问题修复。")
        root.addWidget(self.txt_changelog, 1)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

        self.lbl_status = QLabel("", self)
        self.lbl_status.setFont(_source_han_font(8))
        self.lbl_status.setVisible(False)
        root.addWidget(self.lbl_status)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_later = QPushButton("暂不更新", self)
        self.btn_later.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_later.setFixedHeight(34)
        self.btn_later.setFont(_source_han_font(9, QFont.Weight.Bold))
        self.btn_later.clicked.connect(self.reject)

        self.btn_action = QPushButton("立即下载", self)
        self.btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_action.setFixedHeight(34)
        self.btn_action.setFont(_source_han_font(9, QFont.Weight.Bold))
        self.btn_action.clicked.connect(self._on_action_clicked)

        btn_row.addWidget(self.btn_later, 1)
        btn_row.addWidget(self.btn_action, 2)
        root.addLayout(btn_row)

        self._apply_style()

    def _on_action_clicked(self) -> None:
        if self._stage == "ready":
            self._stage = "downloading"
            self.btn_action.setEnabled(False)
            self.btn_action.setText("正在下载...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.lbl_status.setVisible(True)
            self.lbl_status.setText("正在连接加速节点下载...")
            self.download_requested.emit()
        elif self._stage == "downloaded":
            self.install_requested.emit()

    def set_progress(self, pct: int, status_text: str) -> None:
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(max(0, min(100, pct)))
        self.lbl_status.setVisible(True)
        self.lbl_status.setText(status_text)

    def set_download_finished(self) -> None:
        self._stage = "downloaded"
        self.progress_bar.setValue(100)
        self.lbl_status.setText("下载完成，点击确认后将自动替换并重启")
        self.btn_action.setEnabled(True)
        self.btn_action.setText("确认安装并重启")

    def set_error(self, msg: str) -> None:
        self._stage = "ready"
        self.lbl_status.setVisible(True)
        self.lbl_status.setText(msg)
        self.btn_action.setEnabled(True)
        self.btn_action.setText("重试下载")

    def apply_theme(self, theme_mode: str | bool, accent_color: str) -> None:
        self.is_light = theme_mode if isinstance(theme_mode, bool) else (str(theme_mode) == "light")
        self.accent_color = accent_color
        if hasattr(self, "btn_min"):
            self.btn_min.set_light_mode(self.is_light)
            self.btn_min.set_accent_color(accent_color)
        if hasattr(self, "btn_close"):
            self.btn_close.set_light_mode(self.is_light)
            self.btn_close.set_accent_color(accent_color)
        self._apply_style()
        if hasattr(self, "_refresh_view"):
            self._refresh_view()
        self.update()

    def _apply_style(self) -> None:
        primary_text = "#18181C" if self.is_light else "#F4F4F6"
        muted_text = "#6A6A76" if self.is_light else "#8E8E9A"
        box_bg = "#F4F5F8" if self.is_light else "#22222A"
        box_border = "#DCDFE6" if self.is_light else "#2F2F3B"
        track_bg = "#EAECEF" if self.is_light else "#25252E"

        self.lbl_title.setStyleSheet(f"color: {primary_text};")
        self.lbl_sub.setStyleSheet(f"color: {muted_text};")
        self.lbl_status.setStyleSheet(f"color: {muted_text};")

        self.txt_changelog.setStyleSheet(
            f"""
            QTextEdit {{
                background-color: {box_bg};
                color: {primary_text};
                border: 1px solid {box_border};
                border-radius: 8px;
                padding: 6px 8px;
            }}
            """
        )
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background-color: {track_bg};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {self.accent_color};
                border-radius: 3px;
            }}
            """
        )
        self.btn_later.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {box_bg};
                color: {primary_text};
                border: 1px solid {box_border};
                border-radius: 8px;
            }}
            QPushButton:hover {{
                border-color: {self.accent_color};
                color: {self.accent_color};
            }}
            """
        )
        self.btn_action.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {self.accent_color};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:disabled {{
                opacity: 0.65;
            }}
            """
        )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor("#FFFFFF") if self.is_light else QColor("#17171B")
        border = QColor("#DCDFE6") if self.is_light else QColor("#2E2E38")
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        painter.fillPath(path, bg)
        painter.setPen(QPen(border, 1.0))
        painter.drawPath(path)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class FeedbackDialog(QDialog):
    """极简暗黑风格意见反馈弹窗（支持顶部拖动、1000字限制、防连点）。"""

    submit_requested = Signal(str, str)

    def __init__(
        self,
        theme_mode: str = "dark",
        accent_color: str = "#FF6B00",
        history_items: list[dict] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.is_light = theme_mode == "light"
        self.accent_color = accent_color
        self._drag_pos: QPoint | None = None
        self._submitting = False
        self._history_items = [item for item in (history_items or []) if isinstance(item, dict)]

        self.setFixedSize(MAIN_WIDTH, 444 if self._history_items else 316)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(2)
        self.lbl_title = QLabel("意见反馈", self)
        self.lbl_title.setFont(_source_han_font(11, QFont.Weight.Bold))
        self.btn_min = VectorIconButton("min", self, accent_color)
        self.btn_min.set_light_mode(self.is_light)
        self.btn_min.setToolTip("最小化")
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_close = VectorIconButton("close", self, accent_color)
        self.btn_close.set_light_mode(self.is_light)
        self.btn_close.clicked.connect(self.reject)
        top_row.addWidget(self.lbl_title)
        top_row.addStretch(1)
        top_row.addWidget(self.btn_min)
        top_row.addWidget(self.btn_close)
        root.addLayout(top_row)

        self.txt_content = QTextEdit(self)
        self.txt_content.setFont(_source_han_font(9))
        self.txt_content.setPlaceholderText("请描述您遇到的问题或功能建议...")
        self.txt_content.textChanged.connect(self._on_text_changed)
        root.addWidget(self.txt_content, 1)

        count_row = QHBoxLayout()
        self.lbl_status = QLabel("", self)
        self.lbl_status.setFont(_source_han_font(8))
        self.lbl_count = QLabel("0 / 1000", self)
        self.lbl_count.setFont(_source_han_font(8))
        count_row.addWidget(self.lbl_status, 1)
        count_row.addWidget(self.lbl_count)
        root.addLayout(count_row)

        self.edit_contact = QLineEdit(self)
        self.edit_contact.setFont(_source_han_font(9))
        self.edit_contact.setFixedHeight(32)
        self.edit_contact.setPlaceholderText("选填：微信 / QQ / 邮箱，方便联系您")
        root.addWidget(self.edit_contact)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_cancel = QPushButton("取消", self)
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setFixedHeight(34)
        self.btn_cancel.setFont(_source_han_font(9, QFont.Weight.Bold))
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_submit = QPushButton("提交反馈", self)
        self.btn_submit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_submit.setFixedHeight(34)
        self.btn_submit.setFont(_source_han_font(9, QFont.Weight.Bold))
        self.btn_submit.clicked.connect(self._on_submit_clicked)

        btn_row.addWidget(self.btn_cancel, 1)
        btn_row.addWidget(self.btn_submit, 2)
        root.addLayout(btn_row)

        self.history_container = QWidget(self)
        h_outer = QVBoxLayout(self.history_container)
        h_outer.setContentsMargins(0, 4, 0, 0)
        h_outer.setSpacing(6)
        self.lbl_history_title = QLabel("我的反馈与开发者回复", self.history_container)
        self.lbl_history_title.setFont(_source_han_font(8, QFont.Weight.Bold))
        h_outer.addWidget(self.lbl_history_title)

        self.history_scroll = QScrollArea(self.history_container)
        self.history_scroll.setWidgetResizable(True)
        self.history_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.history_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.history_scroll.setFixedHeight(104)

        self.history_list_widget = QWidget(self.history_scroll)
        self.hl_layout = QVBoxLayout(self.history_list_widget)
        self.hl_layout.setContentsMargins(0, 0, 4, 0)
        self.hl_layout.setSpacing(6)

        self.history_scroll.setWidget(self.history_list_widget)
        h_outer.addWidget(self.history_scroll)
        root.addWidget(self.history_container)

        self.update_history(self._history_items)
        self._apply_style()

    def apply_theme(self, theme_mode: str, accent_color: str) -> None:
        self.is_light = theme_mode == "light"
        self.accent_color = accent_color
        self.btn_min.set_light_mode(self.is_light)
        self.btn_min.set_accent_color(accent_color)
        self.btn_close.set_light_mode(self.is_light)
        self.btn_close.set_accent_color(accent_color)
        self.update_history(self._history_items)
        self._apply_style()
        self.update()

    def update_history(self, history_items: list[dict] | None) -> None:
        self._history_items = [item for item in (history_items or []) if isinstance(item, dict)]
        while self.hl_layout.count():
            child = self.hl_layout.takeAt(0)
            if child.widget() is not None:
                child.widget().deleteLater()

        primary_text = "#18181C" if self.is_light else "#F4F4F6"
        muted_text = "#6A6A76" if self.is_light else "#8E8E9A"
        reply_color = "#2563EB" if self.is_light else "#60A5FA"
        item_bg = "#F4F5F8" if self.is_light else "#22222A"
        item_border = "#DCDFE6" if self.is_light else "#2F2F3B"

        for item in self._history_items:
            card = QFrame(self.history_list_widget)
            card.setStyleSheet(
                f"QFrame {{ background-color: {item_bg}; border: 1px solid {item_border}; border-radius: 7px; }}"
            )
            cl = QVBoxLayout(card)
            cl.setContentsMargins(8, 6, 8, 6)
            cl.setSpacing(3)

            q_time = str(item.get("time") or "").strip()
            q_text = str(item.get("content") or "").strip()
            lbl_q = QLabel(f"我 ({q_time}): {q_text}" if q_time else f"我: {q_text}", card)
            lbl_q.setFont(_source_han_font(8))
            lbl_q.setWordWrap(True)
            lbl_q.setStyleSheet(f"color: {primary_text}; border: none; background: transparent;")
            cl.addWidget(lbl_q)

            reply_text = str(item.get("reply") or "").strip()
            if reply_text:
                r_time = str(item.get("reply_time") or "").strip()
                r_prefix = f"开发者回复 ({r_time}): " if r_time else "开发者回复: "
                lbl_r = QLabel(f"{r_prefix}{reply_text}", card)
                lbl_r.setFont(_source_han_font(8, QFont.Weight.Bold))
                lbl_r.setWordWrap(True)
                lbl_r.setStyleSheet(f"color: {reply_color}; border: none; background: transparent;")
                cl.addWidget(lbl_r)
            else:
                lbl_wait = QLabel("暂未回复", card)
                lbl_wait.setFont(_source_han_font(8))
                lbl_wait.setStyleSheet(f"color: {muted_text}; border: none; background: transparent;")
                cl.addWidget(lbl_wait)

            self.hl_layout.addWidget(card)

        self.hl_layout.addStretch(1)
        has_items = bool(self._history_items)
        self.history_container.setVisible(has_items)
        self.setFixedSize(MAIN_WIDTH, 444 if has_items else 316)

    def _on_text_changed(self) -> None:
        text = self.txt_content.toPlainText()
        if len(text) > 1000:
            cursor = self.txt_content.textCursor()
            pos = min(cursor.position(), 1000)
            self.txt_content.blockSignals(True)
            self.txt_content.setPlainText(text[:1000])
            cursor.setPosition(pos)
            self.txt_content.setTextCursor(cursor)
            self.txt_content.blockSignals(False)
            text = text[:1000]
        self.lbl_count.setText(f"{len(text)} / 1000")
        if self.lbl_status.text():
            self.lbl_status.setText("")

    def _on_submit_clicked(self) -> None:
        if self._submitting:
            return
        content = self.txt_content.toPlainText().strip()
        if not content:
            self.set_error("请填写反馈内容后再提交")
            return
        contact = self.edit_contact.text().strip()
        self.submit_requested.emit(content, contact)

    def set_submitting(self, submitting: bool) -> None:
        self._submitting = submitting
        self.btn_submit.setEnabled(not submitting)
        self.btn_submit.setText("提交中..." if submitting else "提交反馈")

    def set_error(self, msg: str) -> None:
        self.set_submitting(False)
        self.lbl_status.setStyleSheet("color: #EF4444;")
        self.lbl_status.setText(msg)

    def apply_theme(self, theme_mode: str | bool, accent_color: str) -> None:
        self.is_light = theme_mode if isinstance(theme_mode, bool) else (str(theme_mode) == "light")
        self.accent_color = accent_color
        if hasattr(self, "btn_min"):
            self.btn_min.set_light_mode(self.is_light)
            self.btn_min.set_accent_color(accent_color)
        if hasattr(self, "btn_close"):
            self.btn_close.set_light_mode(self.is_light)
            self.btn_close.set_accent_color(accent_color)
        self._apply_style()
        if hasattr(self, "_refresh_view"):
            self._refresh_view()
        self.update()

    def _apply_style(self) -> None:
        primary_text = "#18181C" if self.is_light else "#F4F4F6"
        muted_text = "#6A6A76" if self.is_light else "#8E8E9A"
        box_bg = "#F4F5F8" if self.is_light else "#22222A"
        box_border = "#DCDFE6" if self.is_light else "#2F2F3B"

        self.lbl_title.setStyleSheet(f"color: {primary_text};")
        self.lbl_count.setStyleSheet(f"color: {muted_text};")
        self.lbl_status.setStyleSheet("color: #EF4444;")
        self.lbl_history_title.setStyleSheet(f"color: {muted_text};")
        self.history_list_widget.setStyleSheet("background: transparent;")
        scroll_handle = "#D0D3DC" if self.is_light else "#343440"
        self.history_scroll.setStyleSheet(
            f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ background: transparent; width: 4px; }}
            QScrollBar::handle:vertical {{ background: {scroll_handle}; border-radius: 2px; min-height: 16px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
            """
        )

        input_qss = f"""
            QTextEdit, QLineEdit {{
                background-color: {box_bg};
                color: {primary_text};
                border: 1px solid {box_border};
                border-radius: 8px;
                padding: 6px 8px;
            }}
            QTextEdit:focus, QLineEdit:focus {{
                border-color: {self.accent_color};
            }}
        """
        self.txt_content.setStyleSheet(input_qss)
        self.edit_contact.setStyleSheet(input_qss)

        self.btn_cancel.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {box_bg};
                color: {primary_text};
                border: 1px solid {box_border};
                border-radius: 8px;
            }}
            QPushButton:hover {{
                border-color: {self.accent_color};
                color: {self.accent_color};
            }}
            """
        )
        self.btn_submit.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {self.accent_color};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:disabled {{
                opacity: 0.65;
            }}
            """
        )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor("#FFFFFF") if self.is_light else QColor("#17171B")
        border = QColor("#DCDFE6") if self.is_light else QColor("#2E2E38")
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        painter.fillPath(path, bg)
        painter.setPen(QPen(border, 1.0))
        painter.drawPath(path)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class _HolidayCalendarGrid(QWidget):
    """自绘连续滚动月历网格：60fps 像素级平滑滚动、主显月份日期格加深、小字农历/节日及“休”/“班”角标。"""

    dominant_month_changed = Signal(int, int)

    def __init__(self, parent=None, large_mode: bool = False):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._large_mode = large_mode
        today = date.today()
        first_day = date(today.year, today.month, 1)
        self._top_monday = first_day - timedelta(days=first_day.weekday())
        self._dom_year = today.year
        self._dom_month = today.month

        self._is_light = False
        self._accent = "#FF6B00"
        self._holiday_map: dict[str, dict] = {}  # "YYYY-MM-DD" -> {"is_holiday": bool, "name": str}
        self._cells: list[tuple[QRectF, date, str]] = []

        # 连续滚动状态（像素偏移，向下滚动正值、向上滚动负值）
        self._scroll_px = 0.0
        self._target_scroll_px = 0.0
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._on_anim_tick)

    def _header_h(self) -> float:
        return 22.0 if self._large_mode else 16.0

    def _row_h(self) -> float:
        h = float(self.height()) if self.height() > 0 else (330.0 if self._large_mode else 162.0)
        return max(20.0, (h - self._header_h()) / 6.0)

    def _normalize_scroll(self) -> None:
        row_h = self._row_h()
        while self._scroll_px >= row_h:
            self._scroll_px -= row_h
            self._target_scroll_px -= row_h
            self._top_monday += timedelta(days=7)
        while self._scroll_px < 0.0:
            self._scroll_px += row_h
            self._target_scroll_px += row_h
            self._top_monday -= timedelta(days=7)
        # 边界限制：1900 ~ 2100 年
        if self._top_monday.year < 1900:
            self._top_monday = date(1900, 1, 1)
            self._scroll_px = 0.0
            self._target_scroll_px = 0.0
        elif self._top_monday.year > 2100:
            self._top_monday = date(2100, 11, 29)
            self._scroll_px = 0.0
            self._target_scroll_px = 0.0

    def _compute_dominant_month(self) -> tuple[int, int]:
        row_h = self._row_h()
        body_h = row_h * 6.0
        counts: dict[tuple[int, int], float] = {}
        # 统计可见区域内（共 7 行缓冲）每个月份占据的可见高度权重
        for r in range(7):
            y_top = r * row_h - self._scroll_px
            y_bot = y_top + row_h
            vis_h = max(0.0, min(body_h, y_bot) - max(0.0, y_top))
            if vis_h <= 0.0:
                continue
            row_start = self._top_monday + timedelta(days=r * 7)
            for c in range(7):
                d = row_start + timedelta(days=c)
                key = (d.year, d.month)
                counts[key] = counts.get(key, 0.0) + vis_h
        if not counts:
            return self._dom_year, self._dom_month
        return max(counts.items(), key=lambda kv: kv[1])[0]

    def _on_anim_tick(self) -> None:
        diff = self._target_scroll_px - self._scroll_px
        if abs(diff) < 0.4:
            self._scroll_px = self._target_scroll_px
            self._anim_timer.stop()
        else:
            self._scroll_px += diff * 0.26

        self._normalize_scroll()
        new_dom = self._compute_dominant_month()
        if new_dom != (self._dom_year, self._dom_month):
            self._dom_year, self._dom_month = new_dom
            self.dominant_month_changed.emit(self._dom_year, self._dom_month)
        self.update()

    def scroll_by_pixels(self, delta_px: float) -> None:
        self._target_scroll_px += delta_px
        if not self._anim_timer.isActive():
            self._anim_timer.start()

    def snap_to_month(self, year: int, month: int, animate: bool = True) -> None:
        first_day = date(year, month, 1)
        target_monday = first_day - timedelta(days=first_day.weekday())
        week_diff = (target_monday - self._top_monday).days / 7.0
        row_h = self._row_h()
        if animate and self.isVisible() and abs(week_diff) <= 18:
            self._target_scroll_px = week_diff * row_h
            if not self._anim_timer.isActive():
                self._anim_timer.start()
        else:
            self._anim_timer.stop()
            self._top_monday = target_monday
            self._scroll_px = 0.0
            self._target_scroll_px = 0.0
            self._dom_year, self._dom_month = year, month
            self.dominant_month_changed.emit(self._dom_year, self._dom_month)
            self.update()

    def dominant_year_month(self) -> tuple[int, int]:
        return self._dom_year, self._dom_month

    def set_theme(self, is_light: bool, accent_color: str) -> None:
        self._is_light = is_light
        self._accent = accent_color
        self.update()

    def set_holiday_data(self, holiday_map: dict[str, dict]) -> None:
        self._holiday_map = holiday_map
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        col_w = w / 7.0
        header_h = self._header_h()
        row_h = self._row_h()

        primary = QColor("#18181C") if self._is_light else QColor("#F4F4F6")
        muted = QColor("#888894") if self._is_light else QColor("#7D7D87")
        dimmed = QColor("#C2C5D0") if self._is_light else QColor("#4A4A58")
        weekend_col = QColor("#5A5C6E") if self._is_light else QColor("#B4B6C4")
        dom_cell_bg = QColor("#ECEEF4") if self._is_light else QColor("#23232D")
        accent = QColor(self._accent)
        rest_green = QColor("#10B981")
        work_red = QColor("#EF4444")
        today_fill = QColor(accent.red(), accent.green(), accent.blue(), 42)

        # 星期标题
        painter.setFont(_source_han_font(9 if self._large_mode else 7, QFont.Weight.Bold))
        weekdays = ["一", "二", "三", "四", "五", "六", "日"]
        for c, wd in enumerate(weekdays):
            painter.setPen(accent if c >= 5 else muted)
            painter.drawText(QRectF(c * col_w, 0.0, col_w, header_h), Qt.AlignmentFlag.AlignCenter, wd)

        # 裁剪日期网格区，保证连续滚动时不溢出星期标题
        body_rect = QRectF(0.0, header_h, w, max(0.0, h - header_h))
        painter.setClipRect(body_rect)

        today = date.today()
        self._cells = []

        day_font = _source_han_font(11 if self._large_mode else 8, QFont.Weight.Bold)
        sub_font = _source_han_font(8 if self._large_mode else 6)
        badge_font = _source_han_font(7 if self._large_mode else 6, QFont.Weight.Bold)

        # 渲染 7 行缓冲（支持平滑像素偏移）
        for r in range(7):
            row_start = self._top_monday + timedelta(days=r * 7)
            y0 = header_h + r * row_h - self._scroll_px
            for c in range(7):
                d = row_start + timedelta(days=c)
                cell_rect = QRectF(c * col_w + 1.2, y0 + 1.2, col_w - 2.4, row_h - 2.4)
                in_dom = (d.year == self._dom_year and d.month == self._dom_month)
                d_str = d.strftime("%Y-%m-%d")
                hol = self._holiday_map.get(d_str)

                # 背景色：窗口中占比最多的月份日期格加深显示
                if d == today:
                    painter.setBrush(today_fill)
                    painter.setPen(QPen(accent, 1.1))
                    painter.drawRoundedRect(cell_rect, 5.0, 5.0)
                elif hol and hol.get("is_holiday") and in_dom:
                    painter.setBrush(QColor(16, 185, 129, 38))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(cell_rect, 5.0, 5.0)
                elif in_dom:
                    painter.setBrush(dom_cell_bg)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(cell_rect, 5.0, 5.0)

                sub_text, full_tip, is_fest = LunarCalendar.get_day_info(d)
                tip_parts = [d_str, full_tip]
                if hol:
                    tag = "法定节假日 (休)" if hol.get("is_holiday") else "调休补班 (班)"
                    hname = hol.get("name", "")
                    tip_parts.append(f"{tag} · {hname}" if hname else tag)
                if body_rect.intersects(cell_rect):
                    self._cells.append((cell_rect, d, " · ".join(tip_parts)))

                # 日期数字
                if not in_dom:
                    day_color = dimmed
                elif d == today:
                    day_color = accent
                elif d.weekday() >= 5:
                    day_color = weekend_col
                else:
                    day_color = primary

                painter.setFont(day_font)
                painter.setPen(day_color)
                num_rect = QRectF(cell_rect.left(), cell_rect.top() + 1.0, cell_rect.width(), cell_rect.height() * 0.54)
                painter.drawText(num_rect, Qt.AlignmentFlag.AlignCenter, str(d.day))

                # 小字农历/节日
                if not in_dom:
                    sub_color = dimmed
                elif is_fest:
                    sub_color = accent
                else:
                    sub_color = muted
                painter.setFont(sub_font)
                painter.setPen(sub_color)
                sub_rect = QRectF(cell_rect.left(), cell_rect.top() + cell_rect.height() * 0.50, cell_rect.width(), cell_rect.height() * 0.46)
                max_chars = 4 if self._large_mode else 3
                painter.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, sub_text[:max_chars])

                # 法定节假日“休” / 补班“班”角标
                if hol:
                    is_rest = bool(hol.get("is_holiday"))
                    badge_text = "休" if is_rest else "班"
                    badge_color = rest_green if is_rest else work_red
                    painter.setFont(badge_font)
                    painter.setPen(badge_color if in_dom else dimmed)
                    bw = 14.0 if self._large_mode else 10.0
                    badge_rect = QRectF(cell_rect.right() - bw, cell_rect.top(), bw, bw)
                    painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        for rect, _, tip in self._cells:
            if rect.contains(pos):
                if self.toolTip() != tip:
                    self.setToolTip(tip)
                return
        if self.toolTip():
            self.setToolTip("")


class HolidayCalendarWidget(QWidget):
    """法定节假日模块内的日历模式组件：支持连续丝滑滚轮、主显月份加深、按钮归位及联网节假日同步。"""

    month_changed = Signal(int, int)

    def __init__(self, parent=None, large_mode: bool = False):
        super().__init__(parent)
        today = date.today()
        self._year = today.year
        self._month = today.month
        self._large_mode = large_mode
        self._raw_by_year: dict[int, dict] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6 if large_mode else 4)

        nav = QHBoxLayout()
        nav.setContentsMargins(2, 0, 2, 0)
        nav.setSpacing(6 if large_mode else 4)

        btn_w, btn_h = (28, 24) if large_mode else (22, 18)
        nav_font_pt = 10 if large_mode else 8

        self.btn_prev = QPushButton("<", self)
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setFixedSize(btn_w, btn_h)
        self.btn_prev.setFont(_source_han_font(nav_font_pt, QFont.Weight.Bold))
        self.btn_prev.clicked.connect(lambda: self._shift_month(-1))

        self.lbl_ym = QLabel(f"{self._year}年{self._month:02d}月", self)
        self.lbl_ym.setFont(_source_han_font(nav_font_pt, QFont.Weight.Bold))
        self.lbl_ym.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_next = QPushButton(">", self)
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setFixedSize(btn_w, btn_h)
        self.btn_next.setFont(_source_han_font(nav_font_pt, QFont.Weight.Bold))
        self.btn_next.clicked.connect(lambda: self._shift_month(1))

        self.btn_today = QPushButton("今", self)
        self.btn_today.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_today.setFixedSize(btn_w, btn_h)
        self.btn_today.setFont(_source_han_font(9 if large_mode else 7, QFont.Weight.Bold))
        self.btn_today.setToolTip("回到本月")
        self.btn_today.clicked.connect(self._go_today)

        nav.addWidget(self.btn_prev)
        nav.addWidget(self.lbl_ym, 1)
        nav.addWidget(self.btn_next)
        nav.addWidget(self.btn_today)
        layout.addLayout(nav)

        self.grid = _HolidayCalendarGrid(self, large_mode=large_mode)
        self.grid.dominant_month_changed.connect(self._on_dominant_month_changed)
        if large_mode:
            self.grid.setMinimumHeight(330)
            layout.addWidget(self.grid, 1)
        else:
            self.grid.setFixedHeight(162)
            layout.addWidget(self.grid)

    def _on_dominant_month_changed(self, year: int, month: int) -> None:
        self._year = year
        self._month = month
        self.lbl_ym.setText(f"{year}年{month:02d}月")
        if self._raw_by_year:
            self._rebuild_holiday_map()
        self.month_changed.emit(year, month)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return
        event.accept()
        # 每次滚轮按实际 delta 丝滑滚动约 0.55 行（不强制整月跳转）
        step_px = -delta * (self.grid._row_h() * 0.55) / 120.0
        self.grid.scroll_by_pixels(step_px)

    def current_year_month(self) -> tuple[int, int]:
        return self._year, self._month

    def _shift_month(self, delta: int) -> None:
        m = self._month + delta
        y = self._year
        if m < 1:
            m = 12
            y -= 1
        elif m > 12:
            m = 1
            y += 1
        if 1900 <= y <= 2100:
            self._year, self._month = y, m
            self.lbl_ym.setText(f"{y}年{m:02d}月")
            self.grid.snap_to_month(y, m, animate=True)
            self.month_changed.emit(y, m)

    def _go_today(self) -> None:
        today = date.today()
        self._year, self._month = today.year, today.month
        self.lbl_ym.setText(f"{self._year}年{self._month:02d}月")
        self.grid.snap_to_month(self._year, self._month, animate=True)
        self.month_changed.emit(self._year, self._month)

    def _rebuild_holiday_map(self) -> None:
        holiday_map: dict[str, dict] = {}
        for yr in (self._year - 1, self._year, self._year + 1):
            raw = self._raw_by_year.get(yr) or {}
            for _, item in raw.items():
                if not isinstance(item, dict):
                    continue
                d_str = str(item.get("date") or "")
                if d_str:
                    holiday_map[d_str] = {
                        "is_holiday": bool(item.get("holiday", False)),
                        "name": str(item.get("target") or item.get("name") or ""),
                    }
        self.grid.set_holiday_data(holiday_map)

    def set_holiday_data(self, raw_by_year: dict[int, dict]) -> None:
        self._raw_by_year = raw_by_year
        self._rebuild_holiday_map()

    def apply_theme(self, is_light: bool, accent_color: str) -> None:
        self.grid.set_theme(is_light, accent_color)
        primary = "#18181C" if is_light else "#F4F4F6"
        btn_bg = "#F2F3F7" if is_light else "#1F1F25"
        btn_border = "#E0E2EA" if is_light else "#2C2C34"
        self.lbl_ym.setStyleSheet(f"color: {primary};")
        btn_qss = f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {primary};
                border: 1px solid {btn_border};
                border-radius: 5px;
            }}
            QPushButton:hover {{
                border-color: {accent_color};
                color: {accent_color};
            }}
        """
        for b in (self.btn_prev, self.btn_next, self.btn_today):
            b.setStyleSheet(btn_qss)


class HolidayCalendarDialog(QDialog):
    """独立大尺寸节假日日历窗口：支持鼠标滚轮翻月、农历与节日、法定节假日“休”角标及拖动。"""

    month_changed = Signal(int, int)

    def __init__(
        self,
        theme_mode: str = "dark",
        accent_color: str = "#FF6B00",
        raw_by_year: dict[int, dict] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.is_light = theme_mode == "light"
        self.accent_color = accent_color
        self._drag_pos: QPoint | None = None

        self.setFixedSize(432, 438)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(2)
        self.lbl_title = QLabel("CALENDAR · 法定节假日日历", self)
        self.lbl_title.setFont(_source_han_font(10, QFont.Weight.Bold))
        self.btn_min = VectorIconButton("min", self, accent_color)
        self.btn_min.set_light_mode(self.is_light)
        self.btn_min.setToolTip("最小化")
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_close = VectorIconButton("close", self, accent_color)
        self.btn_close.set_light_mode(self.is_light)
        self.btn_close.clicked.connect(self.close)
        top_row.addWidget(self.lbl_title)
        top_row.addStretch(1)
        top_row.addWidget(self.btn_min)
        top_row.addWidget(self.btn_close)
        root.addLayout(top_row)

        self.calendar = HolidayCalendarWidget(self, large_mode=True)
        self.calendar.month_changed.connect(self.month_changed.emit)
        root.addWidget(self.calendar, 1)

        self.apply_theme(self.is_light, self.accent_color)
        if raw_by_year is not None:
            self.calendar.set_holiday_data(raw_by_year)

    def apply_theme(self, is_light: bool, accent_color: str) -> None:
        self.is_light = is_light
        self.accent_color = accent_color
        primary = "#18181C" if is_light else "#F4F4F6"
        self.lbl_title.setStyleSheet(f"color: {primary};")
        self.btn_min.set_light_mode(is_light)
        self.btn_min.set_accent_color(accent_color)
        self.btn_close.set_light_mode(is_light)
        self.btn_close.set_accent_color(accent_color)
        self.calendar.apply_theme(is_light, accent_color)
        self.update()

    def set_holiday_data(self, raw_by_year: dict[int, dict]) -> None:
        self.calendar.set_holiday_data(raw_by_year)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor("#FFFFFF") if self.is_light else QColor("#17171B")
        border = QColor("#DCDFE6") if self.is_light else QColor("#2E2E38")
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, 16, 16)
        painter.fillPath(path, bg)
        painter.setPen(QPen(border, 1.0))
        painter.drawPath(path)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class DownloadConfirmDialog(QDialog):
    """下载确认弹窗：自动探测文件名与分段加速能力，支持修改文件名与浏览保存目录。"""

    _probe_ready = Signal(str, str, int, bool)

    def __init__(
        self,
        url: str,
        default_dir: str,
        theme_mode: str = "dark",
        accent_color: str = "#FF6B00",
        parent=None,
    ):
        super().__init__(parent)
        self.raw_url = url
        self.final_url = url
        self.total_bytes = 0
        self.supports_range = False
        self.is_light = theme_mode == "light"
        self.accent_color = accent_color
        self._drag_pos: QPoint | None = None
        self._user_edited_name = False

        self.setFixedSize(MAIN_WIDTH, 236)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Dialog
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(9)

        top_row = QHBoxLayout()
        top_row.setSpacing(2)
        self.lbl_title = QLabel("确认下载任务", self)
        self.lbl_title.setFont(_source_han_font(11, QFont.Weight.Bold))
        self.btn_min = VectorIconButton("min", self, accent_color)
        self.btn_min.set_light_mode(self.is_light)
        self.btn_min.setToolTip("最小化")
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_close = VectorIconButton("close", self, accent_color)
        self.btn_close.set_light_mode(self.is_light)
        self.btn_close.clicked.connect(self.reject)
        top_row.addWidget(self.lbl_title)
        top_row.addStretch(1)
        top_row.addWidget(self.btn_min)
        top_row.addWidget(self.btn_close)
        root.addLayout(top_row)

        self.lbl_name_cap = QLabel("保存文件名", self)
        self.lbl_name_cap.setFont(_source_han_font(8))
        root.addWidget(self.lbl_name_cap)

        initial_name = FastDownloader._extract_filename({}, url)
        self.edit_filename = QLineEdit(initial_name, self)
        self.edit_filename.setFixedHeight(30)
        self.edit_filename.setFont(_source_han_font(9, QFont.Weight.Bold))
        self.edit_filename.textEdited.connect(lambda _t: setattr(self, "_user_edited_name", True))
        root.addWidget(self.edit_filename)

        self.lbl_dir_cap = QLabel("保存目录", self)
        self.lbl_dir_cap.setFont(_source_han_font(8))
        root.addWidget(self.lbl_dir_cap)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(6)
        self.edit_dir = QLineEdit(default_dir, self)
        self.edit_dir.setFixedHeight(30)
        self.edit_dir.setFont(_source_han_font(9))
        self.btn_browse = QPushButton("浏览", self)
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.setFixedSize(54, 30)
        self.btn_browse.setFont(_source_han_font(9, QFont.Weight.Bold))
        self.btn_browse.clicked.connect(self._on_browse)
        dir_row.addWidget(self.edit_dir, 1)
        dir_row.addWidget(self.btn_browse)
        root.addLayout(dir_row)

        self.lbl_probe = QLabel("正在探测文件大小与多线程支持...", self)
        self.lbl_probe.setFont(_source_han_font(8))
        root.addWidget(self.lbl_probe)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.btn_cancel = QPushButton("取消", self)
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setFixedHeight(34)
        self.btn_cancel.setFont(_source_han_font(9, QFont.Weight.Bold))
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_confirm = QPushButton("确认下载", self)
        self.btn_confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_confirm.setFixedHeight(34)
        self.btn_confirm.setFont(_source_han_font(9, QFont.Weight.Bold))
        self.btn_confirm.clicked.connect(self._on_confirm)

        btn_row.addWidget(self.btn_cancel, 1)
        btn_row.addWidget(self.btn_confirm, 2)
        root.addLayout(btn_row)

        self._apply_style()
        self._probe_ready.connect(self._on_probe_ready)
        self._start_probe()

    def _start_probe(self) -> None:
        def _worker() -> None:
            final_url, fname, total_b, supports_rng = FastDownloader.probe(self.raw_url)
            self._probe_ready.emit(final_url, fname, total_b, supports_rng)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_probe_ready(self, final_url: str, fname: str, total_b: int, supports_rng: bool) -> None:
        self.final_url = final_url
        self.total_bytes = total_b
        self.supports_range = supports_rng
        if not self._user_edited_name and fname:
            self.edit_filename.setText(fname)
        size_txt = FastDownloader.format_size(total_b) if total_b > 0 else "未知大小"
        if supports_rng and total_b > FastDownloader.RANGE_THRESHOLD_BYTES:
            mode_txt = "支持 16 线程并发加速"
        else:
            mode_txt = "单线程流式高速下载"
        self.lbl_probe.setText(f"文件大小: {size_txt} · {mode_txt}")

    def _on_browse(self) -> None:
        cur = self.edit_dir.text().strip() or FastDownloader.default_download_dir()
        chosen = QFileDialog.getExistingDirectory(self, "选择保存目录", cur)
        if chosen:
            self.edit_dir.setText(os.path.normpath(chosen))

    def _on_confirm(self) -> None:
        fname = FastDownloader.sanitize_filename(self.edit_filename.text())
        sdir = self.edit_dir.text().strip()
        if not sdir:
            sdir = FastDownloader.default_download_dir()
        self.edit_filename.setText(fname)
        self.edit_dir.setText(sdir)
        self.accept()

    def get_result(self) -> tuple[str, str, str, int, bool]:
        return (
            self.final_url,
            FastDownloader.sanitize_filename(self.edit_filename.text()),
            self.edit_dir.text().strip() or FastDownloader.default_download_dir(),
            self.total_bytes,
            self.supports_range,
        )

    def apply_theme(self, theme_mode: str | bool, accent_color: str) -> None:
        self.is_light = theme_mode if isinstance(theme_mode, bool) else (str(theme_mode) == "light")
        self.accent_color = accent_color
        if hasattr(self, "btn_min"):
            self.btn_min.set_light_mode(self.is_light)
            self.btn_min.set_accent_color(accent_color)
        if hasattr(self, "btn_close"):
            self.btn_close.set_light_mode(self.is_light)
            self.btn_close.set_accent_color(accent_color)
        self._apply_style()
        if hasattr(self, "_refresh_view"):
            self._refresh_view()
        self.update()

    def _apply_style(self) -> None:
        primary_text = "#18181C" if self.is_light else "#F4F4F6"
        muted_text = "#6A6A76" if self.is_light else "#8E8E9A"
        box_bg = "#F4F5F8" if self.is_light else "#22222A"
        box_border = "#DCDFE6" if self.is_light else "#2F2F3B"

        self.lbl_title.setStyleSheet(f"color: {primary_text};")
        self.lbl_name_cap.setStyleSheet(f"color: {muted_text};")
        self.lbl_dir_cap.setStyleSheet(f"color: {muted_text};")
        self.lbl_probe.setStyleSheet(f"color: {muted_text};")

        input_qss = f"""
            QLineEdit {{
                background-color: {box_bg};
                color: {primary_text};
                border: 1px solid {box_border};
                border-radius: 7px;
                padding: 4px 8px;
            }}
            QLineEdit:focus {{
                border-color: {self.accent_color};
            }}
        """
        self.edit_filename.setStyleSheet(input_qss)
        self.edit_dir.setStyleSheet(input_qss)

        sub_btn_qss = f"""
            QPushButton {{
                background-color: {box_bg};
                color: {primary_text};
                border: 1px solid {box_border};
                border-radius: 7px;
            }}
            QPushButton:hover {{
                border-color: {self.accent_color};
                color: {self.accent_color};
            }}
        """
        self.btn_browse.setStyleSheet(sub_btn_qss)
        self.btn_cancel.setStyleSheet(sub_btn_qss)
        self.btn_confirm.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {self.accent_color};
                color: #FFFFFF;
                border: none;
                border-radius: 7px;
            }}
            """
        )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor("#FFFFFF") if self.is_light else QColor("#17171B")
        border = QColor("#DCDFE6") if self.is_light else QColor("#2E2E38")
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        painter.fillPath(path, bg)
        painter.setPen(QPen(border, 1.0))
        painter.drawPath(path)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)
