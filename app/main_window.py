import os
import sys
import logging
from typing import Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QIcon, QPixmap, QImage, QColor
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QSlider,
    QCheckBox,
    QLineEdit,
    QPlainTextEdit,
    QFileDialog,
    QMessageBox,
    QStatusBar,
    QFrame,
    QSplitter,
)

from app.settings_manager import SettingsManager
from app.hotkey_manager import HotkeyManager
from app.i18n import tr, DEFAULT_UI_LANGUAGE
from capture.screen_capture import ScreenCapture
from capture.region_selector import RegionSelector
from overlay.translation_overlay import TranslationOverlay
from output.txt_writer import TxtWriter
from workers.capture_worker import CaptureWorker
from workers.ocr_worker import OCRWorker
from workers.translation_worker import TranslationWorker

logger = logging.getLogger(__name__)

DARK_STYLESHEET = """
QMainWindow {
    background-color: #121212;
}

QWidget {
    color: #F7F7F8;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}

QGroupBox {
    background-color: #1C1C1E;
    border: 1px solid #2C2C2E;
    border-radius: 8px;
    margin-top: 18px;
    padding: 14px 10px 10px 10px;
    font-weight: bold;
    color: #00E5FF;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
    color: #00E5FF;
}

QLabel {
    color: #F7F7F8;
}

QLabel#secText {
    color: #A5A7AD;
    font-size: 12px;
}

QPushButton {
    background-color: #23272F;
    color: #F7F7F8;
    border: 1px solid #3A3F4B;
    border-radius: 5px;
    padding: 6px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #2D333F;
    border-color: #00E5FF;
}

QPushButton:pressed {
    background-color: #1A1D24;
}

QPushButton#primaryBtn {
    background-color: #007ACC;
    border: 1px solid #0098FF;
    color: #FFFFFF;
    font-weight: bold;
}

QPushButton#primaryBtn:hover {
    background-color: #0098FF;
}

QPushButton#stopBtn {
    background-color: #8B1A1A;
    border: 1px solid #B22222;
    color: #FFFFFF;
    font-weight: bold;
}

QPushButton#stopBtn:hover {
    background-color: #A52A2A;
}

QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
    background-color: #23272F;
    color: #F7F7F8;
    border: 1px solid #3A3F4B;
    border-radius: 4px;
    padding: 4px 8px;
}

QComboBox:focus, QSpinBox:focus, QLineEdit:focus {
    border: 1px solid #00E5FF;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QPlainTextEdit {
    background-color: #181A20;
    color: #E2E8F0;
    border: 1px solid #2C2C2E;
    border-radius: 4px;
    font-family: "Consolas", monospace;
    font-size: 12px;
    padding: 6px;
}

QCheckBox {
    spacing: 6px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #4A5060;
    background-color: #23272F;
}

QCheckBox::indicator:checked {
    background-color: #007ACC;
    border-color: #00E5FF;
}

QStatusBar {
    background-color: #1C1C1E;
    color: #A5A7AD;
    border-top: 1px solid #2C2C2E;
}
"""


class MainWindow(QMainWindow):
    """Main Application Window for Game Translator."""

    def __init__(self, settings_manager: Optional[SettingsManager] = None):
        super().__init__()
        self.settings = settings_manager or SettingsManager()
        self._ui_language: str = self.settings.get("ui_language", DEFAULT_UI_LANGUAGE)
        self.screen_capture = ScreenCapture()
        self.region_selector = RegionSelector(ui_language=self._ui_language)
        self.overlay = TranslationOverlay(settings_manager=self.settings)
        self.hotkey_manager = HotkeyManager(self)
        self.txt_writer = TxtWriter(self.settings.get("txt_output_path", "game_translation.txt"))

        self.capture_worker: Optional[CaptureWorker] = None
        self.ocr_worker: Optional[OCRWorker] = None
        self.translation_worker: Optional[TranslationWorker] = None
        self._manual_seq_counter: int = 9000
        self._current_seq_id: int = 0
        self._is_manual_seq: bool = False
        self._is_capturing: bool = False
        self._is_paused: bool = False
        self._cache_state: str = ""
        self._dialogue_cache_by_seq: dict[int, str] = {}

        self._setup_window()
        self._init_ui()
        self._load_saved_settings()
        self._apply_language()
        self._connect_signals()

        # Show overlay if configured
        if self.settings.get("overlay_enabled", True):
            self.overlay.show()

    def _t(self, key: str, **kwargs) -> str:
        return tr(self._ui_language, key, **kwargs)

    def _setup_window(self):
        self.setWindowTitle(self._t("window_title"))
        self.resize(1160, 800)
        self.setMinimumSize(980, 700)
        self.setStyleSheet(DARK_STYLESHEET)

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(14, 12, 14, 10)
        main_layout.setSpacing(10)

        # 1. Header Bar
        header = self._create_header_bar()
        main_layout.addWidget(header)

        # 2. Split view: Left Panel (Controls & Settings), Right Panel (Preview & Dialogue)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 6, 0)
        left_layout.setSpacing(10)

        left_layout.addWidget(self._create_capture_settings_box())
        left_layout.addWidget(self._create_ocr_settings_box())
        left_layout.addWidget(self._create_translation_settings_box())
        left_layout.addWidget(self._create_output_settings_box())
        left_layout.addStretch()

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.setSpacing(10)

        right_layout.addWidget(self._create_preview_box(), stretch=3)
        right_layout.addWidget(self._create_dialogue_view_box(), stretch=2)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([520, 640])
        main_layout.addWidget(splitter, stretch=1)

        # 3. Bottom Control Action Bar
        control_bar = self._create_control_action_bar()
        main_layout.addWidget(control_bar)

        # 4. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel()
        self.perf_label = QLabel()
        self.status_bar.addWidget(self.status_label, stretch=1)
        self.status_bar.addPermanentWidget(self.perf_label)

    def _create_header_bar(self) -> QWidget:
        header = QFrame()
        header.setStyleSheet("background-color: #1C1C1E; border-radius: 6px; padding: 6px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 4, 10, 4)

        title = QLabel("GAME TRANSLATOR")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #00E5FF; letter-spacing: 1px;")
        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("secText")

        h_layout.addWidget(title)
        h_layout.addWidget(self.subtitle_label)
        h_layout.addStretch()

        self.ui_lang_label = QLabel()
        self.ui_lang_label.setObjectName("secText")
        self.ui_lang_combo = QComboBox()
        self.ui_lang_combo.addItem("Tiếng Việt", "vi")
        self.ui_lang_combo.addItem("English", "en")
        self.ui_lang_combo.setMinimumWidth(105)
        lang_idx = self.ui_lang_combo.findData(self._ui_language)
        if lang_idx >= 0:
            self.ui_lang_combo.setCurrentIndex(lang_idx)

        h_layout.addWidget(self.ui_lang_label)
        h_layout.addWidget(self.ui_lang_combo)
        h_layout.addSpacing(8)

        self.state_badge = QLabel()
        self.state_badge.setStyleSheet(
            "background-color: #3A3F4B; color: #FFFFFF; font-weight: bold; "
            "padding: 4px 10px; border-radius: 4px; font-size: 11px;"
        )
        h_layout.addWidget(self.state_badge)
        return header

    def _create_capture_settings_box(self) -> QGroupBox:
        self.capture_box = QGroupBox()
        layout = QGridLayout(self.capture_box)
        layout.setSpacing(8)

        # Monitor selection
        self.monitor_lbl = QLabel()
        layout.addWidget(self.monitor_lbl, 0, 0)
        self.monitor_combo = QComboBox()
        self._populate_monitors()
        layout.addWidget(self.monitor_combo, 0, 1, 1, 2)

        # Selected Region Info & Button
        self.capture_region_lbl = QLabel()
        layout.addWidget(self.capture_region_lbl, 1, 0)
        self.region_label = QLabel()
        self.region_label.setStyleSheet("color: #E2E8F0; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.region_label, 1, 1)

        self.select_region_btn = QPushButton()
        self.select_region_btn.setStyleSheet("font-weight: bold; color: #00E5FF;")
        layout.addWidget(self.select_region_btn, 1, 2)

        # Capture Interval
        self.interval_lbl = QLabel()
        layout.addWidget(self.interval_lbl, 2, 0)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(30, 2000)
        self.interval_spin.setSingleStep(25)
        self.interval_spin.setValue(self.settings.get("capture_interval_ms", 150))
        layout.addWidget(self.interval_spin, 2, 1)

        self.interval_hint = QLabel()
        self.interval_hint.setObjectName("secText")
        layout.addWidget(self.interval_hint, 2, 2)

        return self.capture_box

    def _create_ocr_settings_box(self) -> QGroupBox:
        self.ocr_box = QGroupBox()
        layout = QGridLayout(self.ocr_box)
        layout.setSpacing(8)

        self.ocr_enable_cb = QCheckBox()
        self.ocr_enable_cb.setChecked(self.settings.get("ocr_enabled", True))
        layout.addWidget(self.ocr_enable_cb, 0, 0)

        self.ocr_engine_lbl = QLabel()
        layout.addWidget(self.ocr_engine_lbl, 0, 1)
        self.ocr_engine_combo = QComboBox()
        self.ocr_engine_combo.addItems(["", "", ""])
        layout.addWidget(self.ocr_engine_combo, 0, 2)

        self.ocr_conf_lbl = QLabel()
        layout.addWidget(self.ocr_conf_lbl, 1, 0)
        self.ocr_conf_spin = QDoubleSpinBox()
        self.ocr_conf_spin.setRange(0.0, 1.0)
        self.ocr_conf_spin.setSingleStep(0.05)
        self.ocr_conf_spin.setValue(self.settings.get("ocr_confidence_threshold", 0.4))
        layout.addWidget(self.ocr_conf_spin, 1, 1)

        self.ocr_status_label = QLabel()
        self.ocr_status_label.setObjectName("secText")
        layout.addWidget(self.ocr_status_label, 1, 2)

        return self.ocr_box

    def _create_translation_settings_box(self) -> QGroupBox:
        self.translation_box = QGroupBox()
        layout = QGridLayout(self.translation_box)
        layout.setSpacing(8)

        self.trans_lang_lbl = QLabel()
        layout.addWidget(self.trans_lang_lbl, 0, 0)
        lang_layout = QHBoxLayout()
        self.src_lang_combo = QComboBox()
        self.src_lang_combo.addItem("", "auto")
        self.src_lang_combo.addItem("", "en")
        self.src_lang_combo.addItem("", "ja")
        self.src_lang_combo.addItem("", "zh")
        self.tgt_lang_combo = QComboBox()
        self.tgt_lang_combo.addItem("", "vi")
        lang_layout.addWidget(self.src_lang_combo)
        lang_layout.addWidget(QLabel("→"))
        lang_layout.addWidget(self.tgt_lang_combo)
        layout.addLayout(lang_layout, 0, 1, 1, 2)

        self.provider_lbl = QLabel()
        layout.addWidget(self.provider_lbl, 1, 0)
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["", ""])
        layout.addWidget(self.provider_combo, 1, 1)

        self.timeout_lbl = QLabel()
        layout.addWidget(self.timeout_lbl, 1, 2)
        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(1.0, 10.0)
        self.timeout_spin.setSingleStep(0.5)
        self.timeout_spin.setValue(self.settings.get("translation_timeout_sec", 3.0))
        self.timeout_spin.setSuffix(" s")
        layout.addWidget(self.timeout_spin, 1, 3)

        self.api_key_lbl = QLabel()
        layout.addWidget(self.api_key_lbl, 2, 0)
        self.api_key_edit = QLineEdit(self.settings.get("translation_api_key", ""))
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.api_key_edit, 2, 1, 1, 3)

        return self.translation_box

    def _create_preview_box(self) -> QGroupBox:
        self.preview_box = QGroupBox()
        layout = QVBoxLayout(self.preview_box)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet(
            "background-color: #0E0E10; border: 1px dashed #3A3F4B; border-radius: 6px; color: #70757F;"
        )
        self.preview_label.setMinimumHeight(190)
        layout.addWidget(self.preview_label)

        # Preview HUD details
        hud_layout = QHBoxLayout()
        self.hud_size_label = QLabel()
        self.hud_size_label.setObjectName("secText")
        self.hud_cap_lat_label = QLabel()
        self.hud_cap_lat_label.setObjectName("secText")
        self.hud_ocr_lat_label = QLabel()
        self.hud_ocr_lat_label.setObjectName("secText")
        self.hud_trans_lat_label = QLabel()
        self.hud_trans_lat_label.setObjectName("secText")
        self.hud_fps_label = QLabel()
        self.hud_fps_label.setObjectName("secText")

        hud_layout.addWidget(self.hud_size_label)
        hud_layout.addStretch()
        hud_layout.addWidget(self.hud_cap_lat_label)
        hud_layout.addSpacing(10)
        hud_layout.addWidget(self.hud_ocr_lat_label)
        hud_layout.addSpacing(10)
        hud_layout.addWidget(self.hud_trans_lat_label)
        hud_layout.addSpacing(10)
        hud_layout.addWidget(self.hud_fps_label)

        layout.addLayout(hud_layout)
        return self.preview_box

    def _create_dialogue_view_box(self) -> QGroupBox:
        self.dialogue_box = QGroupBox()
        layout = QVBoxLayout(self.dialogue_box)

        # Latest original text header
        orig_header = QHBoxLayout()
        self.orig_header_lbl = QLabel()
        orig_header.addWidget(self.orig_header_lbl)
        self.seq_badge = QLabel()
        self.seq_badge.setStyleSheet("color: #00E5FF; font-family: monospace; font-size: 11px;")
        orig_header.addStretch()
        orig_header.addWidget(self.seq_badge)
        layout.addLayout(orig_header)

        self.detected_text_edit = QPlainTextEdit()
        self.detected_text_edit.setMaximumHeight(65)
        layout.addWidget(self.detected_text_edit)

        # Translation header
        trans_header = QHBoxLayout()
        self.trans_header_lbl = QLabel()
        trans_header.addWidget(self.trans_header_lbl)
        self.cache_badge = QLabel("")
        self.cache_badge.setStyleSheet("color: #10B981; font-weight: bold; font-size: 11px;")
        trans_header.addStretch()
        trans_header.addWidget(self.cache_badge)
        layout.addLayout(trans_header)

        self.translated_text_edit = QPlainTextEdit()
        self.translated_text_edit.setMaximumHeight(65)
        layout.addWidget(self.translated_text_edit)

        return self.dialogue_box

    def _create_output_settings_box(self) -> QGroupBox:
        self.output_box = QGroupBox()
        layout = QGridLayout(self.output_box)
        layout.setSpacing(8)

        # Overlay Controls
        self.overlay_cb = QCheckBox()
        self.overlay_cb.setChecked(self.settings.get("overlay_enabled", True))
        layout.addWidget(self.overlay_cb, 0, 0)

        self.reposition_overlay_btn = QPushButton()
        self.reposition_overlay_btn.setStyleSheet("font-weight: bold; color: #00E5FF;")
        layout.addWidget(self.reposition_overlay_btn, 0, 1)

        self.show_orig_cb = QCheckBox()
        self.show_orig_cb.setChecked(self.settings.get("overlay_show_original", True))
        layout.addWidget(self.show_orig_cb, 0, 2)

        # Overlay Styling: Font & Opacity
        self.overlay_font_lbl = QLabel()
        layout.addWidget(self.overlay_font_lbl, 1, 0)
        self.overlay_font_spin = QSpinBox()
        self.overlay_font_spin.setRange(12, 36)
        self.overlay_font_spin.setValue(self.settings.get("overlay_font_size", 18))
        layout.addWidget(self.overlay_font_spin, 1, 1)

        self.overlay_opacity_lbl = QLabel()
        layout.addWidget(self.overlay_opacity_lbl, 1, 2)
        self.overlay_opacity_spin = QDoubleSpinBox()
        self.overlay_opacity_spin.setRange(0.2, 1.0)
        self.overlay_opacity_spin.setSingleStep(0.05)
        self.overlay_opacity_spin.setValue(self.settings.get("overlay_bg_opacity", 0.8))
        layout.addWidget(self.overlay_opacity_spin, 1, 3)

        # TXT Output Controls
        self.txt_cb = QCheckBox()
        self.txt_cb.setChecked(self.settings.get("txt_output_enabled", True))
        layout.addWidget(self.txt_cb, 2, 0)

        self.txt_path_edit = QLineEdit(self.settings.get("txt_output_path", "game_translation.txt"))
        layout.addWidget(self.txt_path_edit, 2, 1)

        txt_btns_layout = QHBoxLayout()
        txt_btns_layout.setSpacing(6)
        self.browse_txt_btn = QPushButton()
        self.open_txt_btn = QPushButton()
        self.clear_history_btn = QPushButton()

        txt_btns_layout.addWidget(self.browse_txt_btn)
        txt_btns_layout.addWidget(self.open_txt_btn)
        txt_btns_layout.addWidget(self.clear_history_btn)
        layout.addLayout(txt_btns_layout, 2, 2, 1, 2)

        return self.output_box

    def _create_control_action_bar(self) -> QWidget:
        bar = QFrame()
        bar.setStyleSheet("background-color: #1C1C1E; border-radius: 6px; padding: 4px;")
        layout = QHBoxLayout(bar)
        layout.setSpacing(10)

        self.start_btn = QPushButton()
        self.start_btn.setObjectName("primaryBtn")
        self.start_btn.setFixedHeight(34)

        self.pause_btn = QPushButton()
        self.pause_btn.setEnabled(False)
        self.pause_btn.setFixedHeight(34)

        self.stop_btn = QPushButton()
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setFixedHeight(34)

        self.manual_translate_btn = QPushButton()
        self.manual_translate_btn.setFixedHeight(34)

        self.clear_btn = QPushButton()
        self.clear_btn.setFixedHeight(34)

        self.toggle_overlay_btn = QPushButton()
        self.toggle_overlay_btn.setFixedHeight(34)

        layout.addWidget(self.start_btn)
        layout.addWidget(self.pause_btn)
        layout.addWidget(self.stop_btn)
        layout.addSpacing(10)
        layout.addWidget(self.manual_translate_btn)
        layout.addWidget(self.clear_btn)
        layout.addStretch()
        layout.addWidget(self.toggle_overlay_btn)

        return bar

    def _populate_monitors(self):
        self.monitor_combo.clear()
        monitors = self.screen_capture.get_monitors()
        for mon in monitors:
            self.monitor_combo.addItem(mon["name"], mon["id"])

        saved_mon = self.settings.get("monitor_index", 1)
        for i in range(self.monitor_combo.count()):
            if self.monitor_combo.itemData(i) == saved_mon:
                self.monitor_combo.setCurrentIndex(i)
                break

    def _load_saved_settings(self):
        region = self.settings.get("capture_region")
        if region:
            self._update_region_ui(region)

        # Global Hotkeys
        self.hotkey_manager.register_defaults(self.settings.get("hotkeys"))

    def _on_ui_language_changed(self, index: int):
        lang = self.ui_lang_combo.itemData(index)
        if lang:
            self.set_ui_language(lang)

    def set_ui_language(self, lang: str):
        if lang not in ("en", "vi"):
            lang = DEFAULT_UI_LANGUAGE
        self._ui_language = lang
        self.settings.set("ui_language", lang)

        # Sync combo box without re-triggering signal
        idx = self.ui_lang_combo.findData(lang)
        if idx >= 0 and self.ui_lang_combo.currentIndex() != idx:
            self.ui_lang_combo.blockSignals(True)
            self.ui_lang_combo.setCurrentIndex(idx)
            self.ui_lang_combo.blockSignals(False)

        self.region_selector.set_ui_language(lang)
        self.overlay.set_ui_language(lang)
        self._apply_language()

    def _apply_language(self):
        self.setWindowTitle(self._t("window_title"))
        self.subtitle_label.setText(self._t("header_subtitle"))
        self.ui_lang_label.setText(self._t("ui_lang_label"))

        # Capture box
        self.capture_box.setTitle(self._t("group_capture"))
        self.monitor_lbl.setText(self._t("lbl_monitor"))
        self.capture_region_lbl.setText(self._t("lbl_capture_region"))
        self.select_region_btn.setText(self._t("btn_select_region"))
        self.interval_lbl.setText(self._t("lbl_interval"))
        self.interval_hint.setText(self._t("interval_hint"))

        region = self.settings.get("capture_region")
        if region:
            self._update_region_ui(region)
        else:
            self.region_label.setText(self._t("no_region_selected"))
            self.hud_size_label.setText(self._t("hud_region_empty"))

        # OCR box
        self.ocr_box.setTitle(self._t("group_ocr"))
        self.ocr_enable_cb.setText(self._t("cb_enable_ocr"))
        self.ocr_engine_lbl.setText(self._t("lbl_ocr_engine"))
        ocr_idx = max(0, self.ocr_engine_combo.currentIndex())
        self.ocr_engine_combo.blockSignals(True)
        self.ocr_engine_combo.setItemText(0, self._t("ocr_engine_auto"))
        self.ocr_engine_combo.setItemText(1, self._t("ocr_engine_windows"))
        self.ocr_engine_combo.setItemText(2, self._t("ocr_engine_rapid"))
        self.ocr_engine_combo.setCurrentIndex(ocr_idx)
        self.ocr_engine_combo.blockSignals(False)
        self.ocr_conf_lbl.setText(self._t("lbl_conf_min"))
        if not self._is_capturing:
            self.ocr_status_label.setText(self._t("ocr_status_active"))

        # Translation box
        self.translation_box.setTitle(self._t("group_translation"))
        self.trans_lang_lbl.setText(self._t("lbl_trans_lang"))
        src_idx = max(0, self.src_lang_combo.currentIndex())
        self.src_lang_combo.blockSignals(True)
        self.src_lang_combo.setItemText(0, self._t("src_lang_auto"))
        self.src_lang_combo.setItemText(1, self._t("src_lang_en"))
        self.src_lang_combo.setItemText(2, self._t("src_lang_ja"))
        self.src_lang_combo.setItemText(3, self._t("src_lang_zh"))
        self.src_lang_combo.setCurrentIndex(src_idx)
        self.src_lang_combo.blockSignals(False)

        self.tgt_lang_combo.blockSignals(True)
        self.tgt_lang_combo.setItemText(0, self._t("tgt_lang_vi"))
        self.tgt_lang_combo.blockSignals(False)

        self.provider_lbl.setText(self._t("lbl_provider"))
        prov_idx = max(0, self.provider_combo.currentIndex())
        self.provider_combo.blockSignals(True)
        self.provider_combo.setItemText(0, self._t("provider_google"))
        self.provider_combo.setItemText(1, self._t("provider_deepl"))
        self.provider_combo.setCurrentIndex(prov_idx)
        self.provider_combo.blockSignals(False)

        self.timeout_lbl.setText(self._t("lbl_timeout"))
        self.api_key_lbl.setText(self._t("lbl_api_key"))
        self.api_key_edit.setPlaceholderText(self._t("api_key_placeholder"))

        # Output box
        self.output_box.setTitle(self._t("group_output"))
        self.overlay_cb.setText(self._t("cb_enable_overlay"))
        self.reposition_overlay_btn.setText(self._t("btn_reposition_overlay"))
        self.show_orig_cb.setText(self._t("cb_show_original"))
        self.overlay_font_lbl.setText(self._t("lbl_overlay_font"))
        self.overlay_opacity_lbl.setText(self._t("lbl_overlay_opacity"))
        self.txt_cb.setText(self._t("cb_enable_txt"))
        self.browse_txt_btn.setText(self._t("btn_browse_txt"))
        self.open_txt_btn.setText(self._t("btn_open_txt"))
        self.clear_history_btn.setText(self._t("btn_reset_txt"))

        # Preview box
        self.preview_box.setTitle(self._t("group_preview"))
        if self.preview_label.pixmap() is None or self.preview_label.pixmap().isNull():
            self.preview_label.setText(self._t("preview_placeholder"))
        if not self._is_capturing:
            self.hud_cap_lat_label.setText(self._t("hud_cap_empty"))
            self.hud_ocr_lat_label.setText(self._t("hud_ocr_empty"))
            self.hud_trans_lat_label.setText(self._t("hud_trans_empty"))
            self.hud_fps_label.setText(self._t("hud_fps_empty"))

        # Dialogue view box
        self.dialogue_box.setTitle(self._t("group_dialogue"))
        self.orig_header_lbl.setText(self._t("lbl_orig_header"))
        seq_key = "seq_badge_manual" if self._is_manual_seq else "seq_badge"
        self.seq_badge.setText(self._t(seq_key, seq_id=self._current_seq_id))
        self.detected_text_edit.setPlaceholderText(self._t("detected_placeholder"))
        self.trans_header_lbl.setText(self._t("lbl_trans_header"))
        self.translated_text_edit.setPlaceholderText(self._t("translated_placeholder"))
        if self._cache_state == "cached":
            self.cache_badge.setText(self._t("badge_cached"))
        elif self._cache_state == "live":
            self.cache_badge.setText(self._t("badge_live"))
        elif self._cache_state == "failed":
            self.cache_badge.setText(self._t("badge_failed"))
        else:
            self.cache_badge.setText("")

        # Action bar
        self.start_btn.setText(self._t("btn_start"))
        self.stop_btn.setText(self._t("btn_stop"))
        self.manual_translate_btn.setText(self._t("btn_manual_translate"))
        self.clear_btn.setText(self._t("btn_clear"))
        self.toggle_overlay_btn.setText(self._t("btn_toggle_overlay"))

        # State badge & pause button & status bar
        self._refresh_capture_state_labels()

    def _refresh_capture_state_labels(self):
        if self._is_capturing and not self._is_paused:
            self.state_badge.setText(self._t("state_capturing"))
            self.pause_btn.setText(self._t("btn_pause"))
        elif self._is_capturing and self._is_paused:
            self.state_badge.setText(self._t("state_paused"))
            self.pause_btn.setText(self._t("btn_resume"))
        else:
            self.state_badge.setText(self._t("state_stopped"))
            self.pause_btn.setText(self._t("btn_pause"))
            self.status_label.setText(self._t("status_ready"))
            self.perf_label.setText(self._t("perf_idle"))

    def _connect_signals(self):
        self.ui_lang_combo.currentIndexChanged.connect(self._on_ui_language_changed)
        self.select_region_btn.clicked.connect(self._on_click_select_region)
        self.region_selector.region_selected.connect(self._on_region_selected)
        self.region_selector.selection_cancelled.connect(self._on_region_selection_cancelled)

        self.start_btn.clicked.connect(self._start_capture)
        self.pause_btn.clicked.connect(self._pause_capture)
        self.stop_btn.clicked.connect(self._stop_capture)

        self.interval_spin.valueChanged.connect(self._on_interval_changed)
        self.monitor_combo.currentIndexChanged.connect(self._on_monitor_changed)

        self.ocr_enable_cb.toggled.connect(self._on_ocr_enable_toggled)
        self.ocr_conf_spin.valueChanged.connect(self._on_ocr_conf_changed)
        self.ocr_engine_combo.currentIndexChanged.connect(self._on_ocr_engine_changed)

        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self.api_key_edit.textChanged.connect(self._on_api_key_changed)
        self.timeout_spin.valueChanged.connect(self._on_timeout_changed)

        # Overlay controls
        self.overlay_cb.toggled.connect(self._on_overlay_enabled_toggled)
        self.toggle_overlay_btn.clicked.connect(self._toggle_overlay)
        self.reposition_overlay_btn.clicked.connect(self._on_reposition_overlay_clicked)
        self.overlay_font_spin.valueChanged.connect(self.overlay.set_font_size)
        self.overlay_opacity_spin.valueChanged.connect(self.overlay.set_bg_opacity)
        self.show_orig_cb.toggled.connect(self.overlay.set_show_original)

        # TXT output controls
        self.txt_cb.toggled.connect(self._on_txt_enabled_toggled)
        self.browse_txt_btn.clicked.connect(self._browse_txt_path)
        self.open_txt_btn.clicked.connect(self.txt_writer.open_in_editor)
        self.clear_history_btn.clicked.connect(self._on_reset_txt_history)

        # Global hotkey signals
        self.hotkey_manager.toggle_overlay.connect(self._toggle_overlay)
        self.hotkey_manager.pause_resume.connect(self._pause_capture)
        self.hotkey_manager.manual_translate.connect(self._on_manual_translate)
        self.hotkey_manager.clear_translation.connect(self._clear_views)

        self.clear_btn.clicked.connect(self._clear_views)
        self.manual_translate_btn.clicked.connect(self._on_manual_translate)

    def _on_click_select_region(self):
        self.region_selector.start_selection()

    @Slot(dict)
    def _on_region_selected(self, region: dict):
        self._update_region_ui(region)
        self.settings.set("capture_region", region)
        if self.capture_worker and self.capture_worker.isRunning():
            self.capture_worker.set_region(region)
        if self.ocr_worker:
            self.ocr_worker.reset_detectors()
        self.status_label.setText(self._t("status_region_selected"))

    @Slot()
    def _on_region_selection_cancelled(self):
        self.status_label.setText(self._t("status_region_cancelled"))

    def _update_region_ui(self, region: dict):
        self.region_label.setText(
            f"X: {region['left']}, Y: {region['top']} | {region['width']}x{region['height']}"
        )
        self.hud_size_label.setText(
            self._t("hud_region_size", width=region["width"], height=region["height"])
        )

    def _on_interval_changed(self, value: int):
        self.settings.set("capture_interval_ms", value)
        if self.capture_worker:
            self.capture_worker.set_interval(value)

    def _on_monitor_changed(self, index: int):
        mon_id = self.monitor_combo.itemData(index)
        if mon_id is not None:
            self.settings.set("monitor_index", mon_id)

    def _on_ocr_enable_toggled(self, checked: bool):
        self.settings.set("ocr_enabled", checked)
        if self.ocr_worker:
            self.ocr_worker.set_enabled(checked)

    def _on_ocr_conf_changed(self, value: float):
        self.settings.set("ocr_confidence_threshold", value)
        if self.ocr_worker:
            self.ocr_worker.set_min_confidence(value)

    def _on_ocr_engine_changed(self, index: int):
        mapping = {0: "auto", 1: "windows", 2: "rapid"}
        engine_str = mapping.get(index, "auto")
        if self.ocr_worker:
            self.ocr_worker.set_engine(engine_str)

    def _on_provider_changed(self, index: int):
        provider_name = "deepl" if index == 1 else "google"
        self.settings.set("translation_provider", provider_name)
        if self.translation_worker:
            self.translation_worker.set_provider(provider_name, self.api_key_edit.text())

    def _on_api_key_changed(self, key: str):
        self.settings.set("translation_api_key", key)
        if self.translation_worker:
            self.translation_worker.set_provider(
                self.settings.get("translation_provider", "google"), key
            )

    def _on_timeout_changed(self, value: float):
        self.settings.set("translation_timeout_sec", value)
        if self.translation_worker:
            self.translation_worker.set_timeout(value)

    def _on_overlay_enabled_toggled(self, checked: bool):
        self.settings.set("overlay_enabled", checked)
        if checked:
            self.overlay.show()
        else:
            self.overlay.hide()

    def _on_txt_enabled_toggled(self, checked: bool):
        self.settings.set("txt_output_enabled", checked)

    def _toggle_overlay(self):
        if self.overlay.isVisible():
            self.overlay.hide()
            self.status_label.setText(self._t("status_overlay_hidden"))
        else:
            self.overlay.show()
            self.status_label.setText(self._t("status_overlay_shown"))

    def _on_reposition_overlay_clicked(self):
        self.overlay.show()
        self.overlay.raise_()
        self.overlay.set_click_through(False)  # Unlock for mouse drag
        self.status_label.setText(self._t("status_overlay_unlocked"))

    def _browse_txt_path(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._t("dlg_save_txt_title"),
            self.txt_path_edit.text(),
            self._t("dlg_save_txt_filter"),
        )
        if path:
            self.txt_path_edit.setText(path)
            self.settings.set("txt_output_path", path)
            self.txt_writer.set_file_path(path)

    def _on_reset_txt_history(self):
        ok = self.txt_writer.clear_session()
        if ok:
            self.status_label.setText(self._t("status_txt_reset"))

    def _clear_views(self):
        self.detected_text_edit.clear()
        self.translated_text_edit.clear()
        self._current_seq_id = 0
        self._is_manual_seq = False
        self._cache_state = ""
        self.seq_badge.setText(self._t("seq_badge", seq_id=0))
        self.cache_badge.setText("")
        self.overlay.clear_dialogue()
        self._dialogue_cache_by_seq.clear()
        if self.ocr_worker:
            self.ocr_worker.reset_detectors()
        if self.translation_worker:
            self.translation_worker.reset_state()
        self.status_label.setText(self._t("status_cleared"))

    def _get_lang_codes(self):
        sl = self.src_lang_combo.currentData() or "auto"
        return sl, "vi"

    def _on_manual_translate(self):
        text = self.detected_text_edit.toPlainText().strip()
        if not text:
            return

        self._manual_seq_counter += 1
        seq_id = self._manual_seq_counter
        self._current_seq_id = seq_id
        self._is_manual_seq = True
        self.seq_badge.setText(self._t("seq_badge_manual", seq_id=seq_id))
        self._dialogue_cache_by_seq[seq_id] = text

        sl, tl = self._get_lang_codes()
        if self.translation_worker is None:
            self._init_translation_worker()

        self.translation_worker.request_translation(seq_id, text, src_lang=sl, tgt_lang=tl)

    def _init_translation_worker(self):
        if self.translation_worker is None:
            provider_name = "deepl" if self.provider_combo.currentIndex() == 1 else "google"
            self.translation_worker = TranslationWorker(
                provider_name=provider_name,
                api_key=self.api_key_edit.text(),
                timeout_sec=self.timeout_spin.value(),
            )
            self.translation_worker.translation_ready.connect(self._on_translation_ready)
            self.translation_worker.translation_stale_discarded.connect(self._on_translation_stale)
            self.translation_worker.translation_failed.connect(self._on_translation_failed)
            self.translation_worker.status_updated.connect(lambda msg: self.status_label.setText(msg))
            self.translation_worker.start()

    def _start_capture(self):
        region = self.settings.get("capture_region")
        if not region:
            QMessageBox.warning(
                self,
                self._t("dlg_region_req_title"),
                self._t("dlg_region_req_msg"),
            )
            return

        # Ensure Overlay is visible if enabled
        if self.overlay_cb.isChecked() and not self.overlay.isVisible():
            self.overlay.show()

        # Initialize Translation Worker
        self._init_translation_worker()

        # Initialize OCR Worker
        if self.ocr_worker is None:
            engine_idx = self.ocr_engine_combo.currentIndex()
            engine_str = {0: "auto", 1: "windows", 2: "rapid"}.get(engine_idx, "auto")
            self.ocr_worker = OCRWorker(
                engine_name=engine_str,
                min_confidence=self.ocr_conf_spin.value(),
            )
            self.ocr_worker.set_enabled(self.ocr_enable_cb.isChecked())
            self.ocr_worker.dialogue_detected.connect(self._on_dialogue_detected)
            self.ocr_worker.ocr_completed.connect(self._on_ocr_completed)
            self.ocr_worker.ocr_skipped.connect(self._on_ocr_skipped)
            self.ocr_worker.error_occurred.connect(self._on_ocr_error)
            self.ocr_worker.start()

        # Initialize Capture Worker
        if self.capture_worker is None:
            self.capture_worker = CaptureWorker(
                region=region,
                interval_ms=self.interval_spin.value(),
            )
            self.capture_worker.frame_ready.connect(self._on_frame_ready)
            self.capture_worker.fps_updated.connect(self._on_fps_updated)
            self.capture_worker.status_changed.connect(self._on_capture_status_changed)
            self.capture_worker.error_occurred.connect(self._on_capture_error)

        if not self.capture_worker.isRunning():
            self.capture_worker.start()
        elif self._is_paused:
            self.capture_worker.resume_capture()

    def _pause_capture(self):
        if self.capture_worker and self.capture_worker.isRunning():
            if not self._is_paused:
                self.capture_worker.pause_capture()
            else:
                self.capture_worker.resume_capture()

    def _stop_capture(self):
        if self.capture_worker and self.capture_worker.isRunning():
            self.capture_worker.stop()
            self.capture_worker = None

        if self.ocr_worker and self.ocr_worker.isRunning():
            self.ocr_worker.stop()
            self.ocr_worker = None

        if self.translation_worker and self.translation_worker.isRunning():
            self.translation_worker.stop()
            self.translation_worker = None

    @Slot(QImage, object, float)
    def _on_frame_ready(self, qimage: QImage, frame_array, latency_ms: float):
        if not qimage.isNull():
            target_size = self.preview_label.size()
            pixmap = QPixmap.fromImage(qimage)
            scaled = pixmap.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_label.setPixmap(scaled)

        self.hud_cap_lat_label.setText(self._t("hud_cap_val", lat=latency_ms))

        # Pass frame to OCR worker without blocking capture
        if self.ocr_worker and self.ocr_enable_cb.isChecked():
            self.ocr_worker.enqueue_frame(frame_array)

    @Slot(int, str, float, float)
    def _on_dialogue_detected(self, seq_id: int, text: str, confidence: float, latency_ms: float):
        self._current_seq_id = seq_id
        self._is_manual_seq = False
        self.seq_badge.setText(self._t("seq_badge", seq_id=seq_id))
        self.detected_text_edit.setPlainText(text)
        self.status_label.setText(self._t("status_dialogue_recognized", seq_id=seq_id))
        self._dialogue_cache_by_seq[seq_id] = text

        # Update overlay original text if enabled
        if self.overlay.isVisible() and self.show_orig_cb.isChecked():
            self.overlay.orig_label.setText(text)

        # Submit to Translation Worker
        if self.translation_worker:
            sl, tl = self._get_lang_codes()
            self.translation_worker.request_translation(seq_id, text, src_lang=sl, tgt_lang=tl)

    @Slot(int, str, str, float, bool)
    def _on_translation_ready(self, seq_id: int, orig: str, trans: str, latency_ms: float, is_cached: bool):
        self.translated_text_edit.setPlainText(trans)
        self._cache_state = "cached" if is_cached else "live"
        cache_str = self._t("badge_cached") if is_cached else self._t("badge_live")
        self.cache_badge.setText(cache_str)
        suffix = self._t("hud_trans_cache_suffix") if is_cached else ""
        self.hud_trans_lat_label.setText(self._t("hud_trans_val", lat=latency_ms, suffix=suffix))
        mode = self._t("mode_cached") if is_cached else self._t("mode_live")
        self.status_label.setText(
            self._t("status_translated", seq_id=seq_id, mode=mode, lat=latency_ms)
        )

        # 1. Update Game Overlay (if enabled)
        if self.overlay_cb.isChecked() and self.overlay.isVisible():
            self.overlay.update_dialogue(seq_id, orig, trans)

        # 2. Append to TXT Dialogue History (if enabled)
        if self.txt_cb.isChecked():
            self.txt_writer.append_dialogue(seq_id, orig, trans, status="success")

        logger.info("Translation displayed [Seq %d]: '%s' (%s in %.1f ms)", seq_id, trans, cache_str, latency_ms)

    @Slot(int)
    def _on_translation_stale(self, seq_id: int):
        logger.info("Discarded stale translation result [Seq %d] to protect newer live dialogue.", seq_id)
        # Record skipped in TXT history if dialogue text was registered
        if self.txt_cb.isChecked() and seq_id in self._dialogue_cache_by_seq:
            orig = self._dialogue_cache_by_seq[seq_id]
            self.txt_writer.append_dialogue(seq_id, orig, "", status="skipped")

    @Slot(int, str, str)
    def _on_translation_failed(self, seq_id: int, orig: str, err_msg: str):
        self.status_label.setText(self._t("status_trans_failed", seq_id=seq_id, err=err_msg))
        self._cache_state = "failed"
        self.cache_badge.setText(self._t("badge_failed"))
        # Record failed in TXT history if enabled
        if self.txt_cb.isChecked():
            self.txt_writer.append_dialogue(seq_id, orig, err_msg, status="failed")

    @Slot(str, float, float)
    def _on_ocr_completed(self, text: str, confidence: float, latency_ms: float):
        self.hud_ocr_lat_label.setText(self._t("hud_ocr_val", lat=latency_ms))
        self.ocr_status_label.setText(self._t("ocr_status_last", lat=latency_ms))

    @Slot(float)
    def _on_ocr_skipped(self, diff_score: float):
        self.ocr_status_label.setText(self._t("ocr_status_static", diff=diff_score))

    @Slot(float, float)
    def _on_fps_updated(self, fps: float, avg_latency: float):
        self.hud_fps_label.setText(self._t("hud_fps_val", fps=fps))
        self.perf_label.setText(self._t("perf_active", lat=avg_latency, fps=fps))

    @Slot(bool, bool)
    def _on_capture_status_changed(self, is_running: bool, is_paused: bool):
        self._is_capturing = is_running
        self._is_paused = is_paused
        if is_running and not is_paused:
            self.state_badge.setText(self._t("state_capturing"))
            self.state_badge.setStyleSheet(
                "background-color: #007ACC; color: #FFFFFF; font-weight: bold; "
                "padding: 4px 10px; border-radius: 4px; font-size: 11px;"
            )
            self.start_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.pause_btn.setText(self._t("btn_pause"))
            self.stop_btn.setEnabled(True)
            self.status_label.setText(self._t("status_pipeline_active"))
        elif is_running and is_paused:
            self.state_badge.setText(self._t("state_paused"))
            self.state_badge.setStyleSheet(
                "background-color: #D97706; color: #FFFFFF; font-weight: bold; "
                "padding: 4px 10px; border-radius: 4px; font-size: 11px;"
            )
            self.start_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.pause_btn.setText(self._t("btn_resume"))
            self.stop_btn.setEnabled(True)
            self.status_label.setText(self._t("status_paused"))
        else:
            self.state_badge.setText(self._t("state_stopped"))
            self.state_badge.setStyleSheet(
                "background-color: #3A3F4B; color: #FFFFFF; font-weight: bold; "
                "padding: 4px 10px; border-radius: 4px; font-size: 11px;"
            )
            self.start_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.pause_btn.setText(self._t("btn_pause"))
            self.stop_btn.setEnabled(False)
            self.status_label.setText(self._t("status_stopped"))
            self.hud_fps_label.setText(self._t("hud_fps_empty"))
            self.hud_ocr_lat_label.setText(self._t("hud_ocr_empty"))
            self.hud_trans_lat_label.setText(self._t("hud_trans_empty"))
            self.perf_label.setText(self._t("perf_idle"))

    @Slot(str)
    def _on_capture_error(self, err_msg: str):
        self.status_label.setText(self._t("status_capture_error", err=err_msg))
        logger.error("Capture worker error: %s", err_msg)

    @Slot(str)
    def _on_ocr_error(self, err_msg: str):
        self.status_label.setText(self._t("status_ocr_error", err=err_msg))
        logger.error("OCR worker error: %s", err_msg)

    def closeEvent(self, event):
        self._stop_capture()
        self.overlay.close()
        self.hotkey_manager.cleanup()
        self.screen_capture.close()
        event.accept()
