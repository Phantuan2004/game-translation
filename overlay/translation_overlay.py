import ctypes
import logging
from typing import Optional, Dict, Any

from PySide6.QtCore import Qt, QPoint, QRect, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QBrush, QPen
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGraphicsDropShadowEffect,
    QFrame,
    QSizeGrip,
)

from app.settings_manager import SettingsManager
from app.i18n import tr, DEFAULT_UI_LANGUAGE

logger = logging.getLogger(__name__)

# Windows API constants for click-through
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000


class TranslationOverlay(QWidget):
    """Transparent floating overlay for displaying real-time game dialogue translations."""

    position_changed = Signal(dict)  # {"x": int, "y": int, "width": int, "height": int}
    lock_toggled = Signal(bool)  # is_locked (click-through)

    def __init__(self, settings_manager: Optional[SettingsManager] = None, parent=None):
        super().__init__(parent)
        self.settings = settings_manager or SettingsManager()
        self._ui_language: str = self.settings.get("ui_language", DEFAULT_UI_LANGUAGE)
        self._latest_seq_id: int = 0
        self._is_locked: bool = self.settings.get("overlay_click_through", True)
        self._drag_start_pos: Optional[QPoint] = None

        self._setup_window_flags()
        self._init_ui()
        self._apply_settings()

    def _setup_window_flags(self):
        # Frameless, Always on Top, Tool window (does not steal focus or show on taskbar)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(320, 100)

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 8, 12, 10)
        self.main_layout.setSpacing(6)

        # 1. Top Control Bar (reposition handle & lock toggle)
        self.top_bar = QWidget()
        self.top_bar_layout = QHBoxLayout(self.top_bar)
        self.top_bar_layout.setContentsMargins(4, 2, 4, 2)
        self.top_bar_layout.setSpacing(6)

        self.title_label = QLabel(tr(self._ui_language, "overlay_title"))
        self.title_label.setStyleSheet("color: #70757F; font-size: 11px; font-weight: bold;")

        self.lock_btn = QPushButton(tr(self._ui_language, "overlay_lock_locked"))
        self.lock_btn.setStyleSheet(
            "background-color: #23272F; color: #00E5FF; border: 1px solid #3A3F4B; "
            "border-radius: 3px; padding: 2px 8px; font-size: 11px;"
        )
        self.lock_btn.clicked.connect(self.toggle_click_through)

        self.close_btn = QPushButton("✕")
        self.close_btn.setStyleSheet(
            "background-color: #23272F; color: #A5A7AD; border: none; "
            "border-radius: 3px; padding: 2px 6px; font-size: 11px;"
        )
        self.close_btn.clicked.connect(self.hide)

        self.top_bar_layout.addWidget(self.title_label)
        self.top_bar_layout.addStretch()
        self.top_bar_layout.addWidget(self.lock_btn)
        self.top_bar_layout.addWidget(self.close_btn)
        self.main_layout.addWidget(self.top_bar)

        # 2. Original dialogue text label (Optional)
        self.orig_label = QLabel()
        self.orig_label.setWordWrap(True)
        self.orig_label.setStyleSheet("color: #C0C4CC; font-size: 13px; font-style: italic;")
        self.main_layout.addWidget(self.orig_label)

        # 3. Vietnamese translation text label (Primary)
        self.trans_label = QLabel(tr(self._ui_language, "overlay_waiting"))
        self.trans_label.setWordWrap(True)
        self.trans_label.setStyleSheet(
            "color: #FFFFFF; font-size: 18px; font-weight: bold; line-height: 1.3;"
        )
        self.main_layout.addWidget(self.trans_label)

        # 4. Bottom size grip for resizing when unlocked
        grip_layout = QHBoxLayout()
        grip_layout.addStretch()
        self.size_grip = QSizeGrip(self)
        self.size_grip.setStyleSheet("width: 14px; height: 14px;")
        grip_layout.addWidget(self.size_grip)
        self.main_layout.addLayout(grip_layout)

    def _apply_settings(self):
        # Restore position and size
        pos = self.settings.get("overlay_position", {"x": 100, "y": 700})
        dim = self.settings.get("overlay_size", {"width": 800, "height": 180})
        self.setGeometry(pos.get("x", 100), pos.get("y", 700), dim.get("width", 800), dim.get("height", 180))

        # Show / hide original text
        show_orig = self.settings.get("overlay_show_original", True)
        self.orig_label.setVisible(show_orig)

        # Typography
        font_size = self.settings.get("overlay_font_size", 18)
        text_color = self.settings.get("overlay_text_color", "#FFFFFF")
        self.trans_label.setStyleSheet(
            f"color: {text_color}; font-size: {font_size}px; font-weight: bold; line-height: 1.3;"
        )

        self._update_lock_ui()

    def set_font_size(self, size: int):
        self.settings.set("overlay_font_size", size)
        text_color = self.settings.get("overlay_text_color", "#FFFFFF")
        self.trans_label.setStyleSheet(
            f"color: {text_color}; font-size: {size}px; font-weight: bold; line-height: 1.3;"
        )

    def set_bg_opacity(self, opacity: float):
        self.settings.set("overlay_bg_opacity", max(0.1, min(1.0, opacity)))
        self.update()

    def set_show_original(self, show: bool):
        self.settings.set("overlay_show_original", show)
        self.orig_label.setVisible(show)

    def update_dialogue(self, seq_id: int, original_text: str, translated_text: str):
        """Updates the visible overlay dialogue with strict sequence ID validation."""
        if seq_id < self._latest_seq_id:
            logger.warning(
                "Overlay rejected stale dialogue #%d (currently showing #%d)",
                seq_id,
                self._latest_seq_id,
            )
            return

        self._latest_seq_id = seq_id
        if not self.orig_label.isHidden():
            self.orig_label.setText(original_text)
        self.trans_label.setText(translated_text)
        self.update()

    def clear_dialogue(self):
        self.orig_label.clear()
        self.trans_label.setText(tr(self._ui_language, "overlay_waiting"))
        self._latest_seq_id = 0
        self.update()

    def set_ui_language(self, lang: str):
        self._ui_language = lang
        self.title_label.setText(tr(lang, "overlay_title"))
        self._update_lock_ui()
        if self._latest_seq_id == 0:
            self.trans_label.setText(tr(lang, "overlay_waiting"))

    def toggle_click_through(self):
        self.set_click_through(not self._is_locked)

    def set_click_through(self, enabled: bool):
        """Enables or disables click-through on Windows using WS_EX_TRANSPARENT."""
        self._is_locked = enabled
        self.settings.set("overlay_click_through", enabled)
        self._update_lock_ui()

        # Apply Windows API extended window style
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            current = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if enabled:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, current | WS_EX_TRANSPARENT | WS_EX_LAYERED)
            else:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, current & ~WS_EX_TRANSPARENT)
            logger.info("Overlay click-through set to: %s", enabled)
        except Exception as e:
            logger.warning("Could not set Windows click-through style: %s", e)

        self.lock_toggled.emit(enabled)

    def _update_lock_ui(self):
        if self._is_locked:
            self.top_bar.setVisible(False)
            self.size_grip.setVisible(False)
            self.lock_btn.setText(tr(self._ui_language, "overlay_lock_locked"))
        else:
            self.top_bar.setVisible(True)
            self.size_grip.setVisible(True)
            self.lock_btn.setText(tr(self._ui_language, "overlay_lock_unlocked"))

    # Mouse drag repositioning when unlocked
    def mousePressEvent(self, event):
        if not self._is_locked and event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if not self._is_locked and self._drag_start_pos and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_start_pos
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if not self._is_locked and event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = None
            self._save_geometry()
            event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._save_geometry()

    def _save_geometry(self):
        geo = self.geometry()
        self.settings.set("overlay_position", {"x": geo.x(), "y": geo.y()}, auto_save=False)
        self.settings.set("overlay_size", {"width": geo.width(), "height": geo.height()}, auto_save=True)
        self.position_changed.emit({"x": geo.x(), "y": geo.y(), "width": geo.width(), "height": geo.height()})

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background color with user-configured opacity
        opacity = float(self.settings.get("overlay_bg_opacity", 0.8))
        alpha = int(opacity * 255)
        bg_color = QColor(18, 18, 20, alpha)

        # Draw rounded translucent card background
        painter.setPen(QPen(QColor(44, 44, 46, alpha), 1))
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)
