import logging
from typing import Dict, Optional
from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QGuiApplication
from PySide6.QtWidgets import QWidget

from app.i18n import tr, DEFAULT_UI_LANGUAGE

logger = logging.getLogger(__name__)


class RegionSelector(QWidget):
    """Fullscreen semi-transparent overlay widget for selecting a screen capture region."""

    region_selected = Signal(dict)
    selection_cancelled = Signal()

    def __init__(self, parent=None, ui_language: str = DEFAULT_UI_LANGUAGE):
        super().__init__(parent)
        self._ui_language = ui_language
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._start_pos: Optional[QPoint] = None
        self._current_pos: Optional[QPoint] = None
        self._is_selecting = False

    def set_ui_language(self, lang: str) -> None:
        self._ui_language = lang
        self.update()

    def start_selection(self, target_screen=None):
        """Covers all screens or the specified screen and activates selection mode."""
        self._start_pos = None
        self._current_pos = None
        self._is_selecting = False

        # Cover entire virtual desktop across all connected monitors
        all_screens = QGuiApplication.screens()
        if not all_screens:
            self.setGeometry(0, 0, 1920, 1080)
        else:
            combined_rect = all_screens[0].geometry()
            for scr in all_screens[1:]:
                combined_rect = combined_rect.united(scr.geometry())
            self.setGeometry(combined_rect)

        self.show()
        self.raise_()
        self.activateWindow()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos = event.globalPosition().toPoint()
            self._current_pos = self._start_pos
            self._is_selecting = True
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self._cancel()

    def mouseMoveEvent(self, event):
        if self._is_selecting:
            self._current_pos = event.globalPosition().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_selecting:
            self._is_selecting = False
            self._current_pos = event.globalPosition().toPoint()
            self._confirm_selection()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._start_pos and self._current_pos:
                self._confirm_selection()
            else:
                self._cancel()
        else:
            super().keyPressEvent(event)

    def _get_selection_rect(self) -> QRect:
        if not self._start_pos or not self._current_pos:
            return QRect()
        x1 = min(self._start_pos.x(), self._current_pos.x())
        y1 = min(self._start_pos.y(), self._current_pos.y())
        x2 = max(self._start_pos.x(), self._current_pos.x())
        y2 = max(self._start_pos.y(), self._current_pos.y())
        return QRect(x1, y1, x2 - x1, y2 - y1)

    def _confirm_selection(self):
        rect = self._get_selection_rect()
        self.hide()
        # Require a minimum size of 10x10 to prevent accidental clicks
        if rect.width() >= 10 and rect.height() >= 10:
            region_dict = {
                "left": rect.left(),
                "top": rect.top(),
                "width": rect.width(),
                "height": rect.height(),
            }
            logger.info("Region selected: %s", region_dict)
            self.region_selected.emit(region_dict)
        else:
            logger.info("Selection too small, cancelled.")
            self.selection_cancelled.emit()

    def _cancel(self):
        self.hide()
        logger.info("Region selection cancelled by user.")
        self.selection_cancelled.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background overlay: dimmed darkening (dark transparent)
        painter.fillRect(self.rect(), QColor(10, 10, 15, 140))

        if self._start_pos and self._current_pos:
            # Global coordinates to local widget coordinates
            top_left_global = self.geometry().topLeft()
            sel_global = self._get_selection_rect()
            local_rect = QRect(
                sel_global.left() - top_left_global.x(),
                sel_global.top() - top_left_global.y(),
                sel_global.width(),
                sel_global.height(),
            )

            # Clear the selected area so the desktop shines through
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(local_rect, Qt.GlobalColor.transparent)

            # Reset composition mode to draw bounding border
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

            # Draw glowing accent border
            pen = QPen(QColor(0, 229, 255, 230), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(local_rect)

            # Dimension badge
            text = f" {sel_global.width()} x {sel_global.height()} (X: {sel_global.left()}, Y: {sel_global.top()}) "
            font = QFont("Segoe UI", 9, QFont.Weight.Bold)
            painter.setFont(font)

            badge_y = local_rect.top() - 25 if local_rect.top() >= 30 else local_rect.bottom() + 5
            badge_x = local_rect.left()

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(20, 24, 30, 220)))
            text_rect = painter.fontMetrics().boundingRect(text)
            text_rect.adjust(-6, -3, 6, 3)
            text_rect.moveTo(badge_x, badge_y)
            painter.drawRoundedRect(text_rect, 4, 4)

            painter.setPen(QColor(0, 229, 255))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)
        else:
            # Help text when not actively dragging
            painter.setFont(QFont("Segoe UI", 12))
            painter.setPen(QColor(240, 240, 245, 220))
            help_text = tr(self._ui_language, "selector_help")
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, help_text)
