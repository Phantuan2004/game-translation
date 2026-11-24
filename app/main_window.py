import os
import sys
import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QIcon, QPixmap, QImage, QColor
from PyQt6.QtWidgets import (
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
        self.screen_capture = ScreenCapture()
        self.region_selector = RegionSelector()
        self.overlay = TranslationOverlay(settings_manager=self.settings)
        self.hotkey_manager = HotkeyManager(self)
        self.txt_writer = TxtWriter(self.settings.get("txt_output_path", "game_translation.txt"))

        self.capture_worker: Optional[CaptureWorker] = None
        self.ocr_worker: Optional[OCRWorker] = None
        self.translation_worker: Optional[TranslationWorker] = None
        self._manual_seq_counter: int = 9000
        self._dialogue_cache_by_seq: dict[int, str] = {}

        self._setup_window()
        self._init_ui()
        self._load_saved_settings()
        self._connect_signals()

        # Show overlay if configured
        if self.settings.get("overlay_enabled", True):
            self.overlay.show()

    def _setup_window(self):
        self.setWindowTitle("Game Translator — Real-time Dialogue Translation")
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
        self.status_label = QLabel("Ready")
        self.perf_label = QLabel("Capture: Idle | Cap: -- ms | OCR: -- ms | Trans: -- ms | FPS: 0.0")
        self.status_bar.addWidget(self.status_label, stretch=1)
        self.status_bar.addPermanentWidget(self.perf_label)

    def _create_header_bar(self) -> QWidget:
        header = QFrame()
        header.setStyleSheet("background-color: #1C1C1E; border-radius: 6px; padding: 6px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 4, 10, 4)

        title = QLabel("GAME TRANSLATOR")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #00E5FF; letter-spacing: 1px;")
        subtitle = QLabel("Real-Time Low-Latency Game Dialogue Translation")
        subtitle.setObjectName("secText")

        h_layout.addWidget(title)
        h_layout.addWidget(subtitle)
        h_layout.addStretch()

        self.state_badge = QLabel("STOPPED")
        self.state_badge.setStyleSheet(
            "background-color: #3A3F4B; color: #FFFFFF; font-weight: bold; "
            "padding: 4px 10px; border-radius: 4px; font-size: 11px;"
        )
        h_layout.addWidget(self.state_badge)
        return header

    def _create_capture_settings_box(self) -> QGroupBox:
        box = QGroupBox("Capture Settings (Milestone 1)")
        layout = QGridLayout(box)
        layout.setSpacing(8)

        # Monitor selection
        layout.addWidget(QLabel("Monitor:"), 0, 0)
        self.monitor_combo = QComboBox()
        self._populate_monitors()
        layout.addWidget(self.monitor_combo, 0, 1, 1, 2)

        # Selected Region Info & Button
        layout.addWidget(QLabel("Capture Region:"), 1, 0)
        self.region_label = QLabel("No region selected")
        self.region_label.setStyleSheet("color: #E2E8F0; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.region_label, 1, 1)

        self.select_region_btn = QPushButton("Select Screen Region")
        self.select_region_btn.setStyleSheet("font-weight: bold; color: #00E5FF;")
        layout.addWidget(self.select_region_btn, 1, 2)

        # Capture Interval
        layout.addWidget(QLabel("Interval (ms):"), 2, 0)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(30, 2000)
        self.interval_spin.setSingleStep(25)
        self.interval_spin.setValue(self.settings.get("capture_interval_ms", 150))
        layout.addWidget(self.interval_spin, 2, 1)

        interval_hint = QLabel("Recommended: 100-200 ms")
        interval_hint.setObjectName("secText")
        layout.addWidget(interval_hint, 2, 2)

        return box

    def _create_ocr_settings_box(self) -> QGroupBox:
        box = QGroupBox("OCR & Detection Settings (Milestone 2)")
        layout = QGridLayout(box)
        layout.setSpacing(8)

        self.ocr_enable_cb = QCheckBox("Enable Local OCR")
        self.ocr_enable_cb.setChecked(self.settings.get("ocr_enabled", True))
        layout.addWidget(self.ocr_enable_cb, 0, 0)

        layout.addWidget(QLabel("Engine:"), 0, 1)
        self.ocr_engine_combo = QComboBox()
        self.ocr_engine_combo.addItems([
            "Auto (Fastest available)",
            "Windows Media OCR (~6ms)",
            "RapidOCR (ONNX Neural)",
        ])
        layout.addWidget(self.ocr_engine_combo, 0, 2)

        layout.addWidget(QLabel("Confidence Min:"), 1, 0)
        self.ocr_conf_spin = QDoubleSpinBox()
        self.ocr_conf_spin.setRange(0.0, 1.0)
        self.ocr_conf_spin.setSingleStep(0.05)
        self.ocr_conf_spin.setValue(self.settings.get("ocr_confidence_threshold", 0.4))
        layout.addWidget(self.ocr_conf_spin, 1, 1)

        self.ocr_status_label = QLabel("Change detection: Active")
        self.ocr_status_label.setObjectName("secText")
        layout.addWidget(self.ocr_status_label, 1, 2)

        return box

    def _create_translation_settings_box(self) -> QGroupBox:
        box = QGroupBox("Translation Settings (Milestone 3)")
        layout = QGridLayout(box)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Language:"), 0, 0)
        lang_layout = QHBoxLayout()
        self.src_lang_combo = QComboBox()
        self.src_lang_combo.addItems(["Auto Detect", "English (en)", "Japanese (ja)", "Chinese (zh)"])
        self.tgt_lang_combo = QComboBox()
        self.tgt_lang_combo.addItems(["Vietnamese (vi)"])
        lang_layout.addWidget(self.src_lang_combo)
        lang_layout.addWidget(QLabel("→"))
        lang_layout.addWidget(self.tgt_lang_combo)
        layout.addLayout(lang_layout, 0, 1, 1, 2)

        layout.addWidget(QLabel("Provider:"), 1, 0)
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Google Translate (Free / Fast)", "DeepL API"])
        layout.addWidget(self.provider_combo, 1, 1)

        layout.addWidget(QLabel("Timeout:"), 1, 2)
        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(1.0, 10.0)
        self.timeout_spin.setSingleStep(0.5)
        self.timeout_spin.setValue(self.settings.get("translation_timeout_sec", 3.0))
        self.timeout_spin.setSuffix(" s")
        layout.addWidget(self.timeout_spin, 1, 3)

        layout.addWidget(QLabel("API Key:"), 2, 0)
        self.api_key_edit = QLineEdit(self.settings.get("translation_api_key", ""))
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("Optional for Google, required for DeepL")
        layout.addWidget(self.api_key_edit, 2, 1, 1, 3)

        return box

    def _create_preview_box(self) -> QGroupBox:
        box = QGroupBox("Live Capture Preview")
        layout = QVBoxLayout(box)

        self.preview_label = QLabel("Select a region and start capture to preview dialogue area.")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet(
            "background-color: #0E0E10; border: 1px dashed #3A3F4B; border-radius: 6px; color: #70757F;"
        )
        self.preview_label.setMinimumHeight(190)
        layout.addWidget(self.preview_label)

        # Preview HUD details
        hud_layout = QHBoxLayout()
        self.hud_size_label = QLabel("Region: -- x --")
        self.hud_size_label.setObjectName("secText")
        self.hud_cap_lat_label = QLabel("Cap: -- ms")
        self.hud_cap_lat_label.setObjectName("secText")
        self.hud_ocr_lat_label = QLabel("OCR: -- ms")
        self.hud_ocr_lat_label.setObjectName("secText")
        self.hud_trans_lat_label = QLabel("Trans: -- ms")
        self.hud_trans_lat_label.setObjectName("secText")
        self.hud_fps_label = QLabel("FPS: --")
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
        return box

    def _create_dialogue_view_box(self) -> QGroupBox:
        box = QGroupBox("Detected Dialogue & Translation")
        layout = QVBoxLayout(box)

        # Latest original text header
        orig_header = QHBoxLayout()
        orig_header.addWidget(QLabel("Latest Recognized Original:"))
        self.seq_badge = QLabel("Seq: #0")
        self.seq_badge.setStyleSheet("color: #00E5FF; font-family: monospace; font-size: 11px;")
        orig_header.addStretch()
        orig_header.addWidget(self.seq_badge)
        layout.addLayout(orig_header)

        self.detected_text_edit = QPlainTextEdit()
        self.detected_text_edit.setPlaceholderText("OCR recognized text will appear here (editable for manual translation)...")
        self.detected_text_edit.setMaximumHeight(65)
        layout.addWidget(self.detected_text_edit)

        # Translation header
        trans_header = QHBoxLayout()
        trans_header.addWidget(QLabel("Vietnamese Translation:"))
        self.cache_badge = QLabel("")
        self.cache_badge.setStyleSheet("color: #10B981; font-weight: bold; font-size: 11px;")
        trans_header.addStretch()
        trans_header.addWidget(self.cache_badge)
        layout.addLayout(trans_header)

        self.translated_text_edit = QPlainTextEdit()
        self.translated_text_edit.setPlaceholderText("Vietnamese translation will appear here in real time...")
        self.translated_text_edit.setMaximumHeight(65)
        layout.addWidget(self.translated_text_edit)

        return box

    def _create_output_settings_box(self) -> QGroupBox:
        box = QGroupBox("Output Settings (Milestones 4 & 5)")
        layout = QGridLayout(box)
        layout.setSpacing(8)

        # Overlay Controls
        self.overlay_cb = QCheckBox("Enable Game Overlay")
        self.overlay_cb.setChecked(self.settings.get("overlay_enabled", True))
        layout.addWidget(self.overlay_cb, 0, 0)

        self.reposition_overlay_btn = QPushButton("🔓 Unlock / Move Overlay")
        self.reposition_overlay_btn.setStyleSheet("font-weight: bold; color: #00E5FF;")
        layout.addWidget(self.reposition_overlay_btn, 0, 1)

        self.show_orig_cb = QCheckBox("Show Original (EN)")
        self.show_orig_cb.setChecked(self.settings.get("overlay_show_original", True))
        layout.addWidget(self.show_orig_cb, 0, 2)

        # Overlay Styling: Font & Opacity
        layout.addWidget(QLabel("Overlay Font:"), 1, 0)
        self.overlay_font_spin = QSpinBox()
        self.overlay_font_spin.setRange(12, 36)
        self.overlay_font_spin.setValue(self.settings.get("overlay_font_size", 18))
        layout.addWidget(self.overlay_font_spin, 1, 1)

        layout.addWidget(QLabel("Overlay Opacity:"), 1, 2)
        self.overlay_opacity_spin = QDoubleSpinBox()
        self.overlay_opacity_spin.setRange(0.2, 1.0)
        self.overlay_opacity_spin.setSingleStep(0.05)
        self.overlay_opacity_spin.setValue(self.settings.get("overlay_bg_opacity", 0.8))
        layout.addWidget(self.overlay_opacity_spin, 1, 3)

        # TXT Output Controls
        self.txt_cb = QCheckBox("Enable TXT Output")
        self.txt_cb.setChecked(self.settings.get("txt_output_enabled", True))
        layout.addWidget(self.txt_cb, 2, 0)

        self.txt_path_edit = QLineEdit(self.settings.get("txt_output_path", "game_translation.txt"))
        layout.addWidget(self.txt_path_edit, 2, 1)

        txt_btns_layout = QHBoxLayout()
        txt_btns_layout.setSpacing(6)
        self.browse_txt_btn = QPushButton("Browse")
        self.open_txt_btn = QPushButton("Open File")
        self.clear_history_btn = QPushButton("Reset Log")

        txt_btns_layout.addWidget(self.browse_txt_btn)
        txt_btns_layout.addWidget(self.open_txt_btn)
        txt_btns_layout.addWidget(self.clear_history_btn)
        layout.addLayout(txt_btns_layout, 2, 2, 1, 2)

        return box

    def _create_control_action_bar(self) -> QWidget:
        bar = QFrame()
        bar.setStyleSheet("background-color: #1C1C1E; border-radius: 6px; padding: 4px;")
        layout = QHBoxLayout(bar)
        layout.setSpacing(10)

        self.start_btn = QPushButton("▶  Start Capture")
        self.start_btn.setObjectName("primaryBtn")
        self.start_btn.setFixedHeight(34)

        self.pause_btn = QPushButton("⏸  Pause (F9)")
        self.pause_btn.setEnabled(False)
        self.pause_btn.setFixedHeight(34)

        self.stop_btn = QPushButton("⏹  Stop")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setFixedHeight(34)

        self.manual_translate_btn = QPushButton("Manual Translate (F10)")
        self.manual_translate_btn.setFixedHeight(34)

        self.clear_btn = QPushButton("Clear (F11)")
        self.clear_btn.setFixedHeight(34)

        self.toggle_overlay_btn = QPushButton("Toggle Overlay (F8)")
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
        else:
            self.region_label.setText("No region selected")

        # Global Hotkeys
        self.hotkey_manager.register_defaults(self.settings.get("hotkeys"))

    def _connect_signals(self):
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

    @pyqtSlot(dict)
    def _on_region_selected(self, region: dict):
        self._update_region_ui(region)
        self.settings.set("capture_region", region)
        if self.capture_worker and self.capture_worker.isRunning():
            self.capture_worker.set_region(region)
        if self.ocr_worker:
            self.ocr_worker.reset_detectors()
        self.status_label.setText("Region selected.")

    @pyqtSlot()
    def _on_region_selection_cancelled(self):
        self.status_label.setText("Region selection cancelled.")

    def _update_region_ui(self, region: dict):
        self.region_label.setText(
            f"X: {region['left']}, Y: {region['top']} | {region['width']}x{region['height']}"
        )
        self.hud_size_label.setText(f"Region: {region['width']}x{region['height']}")

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
            self.status_label.setText("Overlay hidden (F8 to show)")
        else:
            self.overlay.show()
            self.status_label.setText("Overlay displayed (F8 to hide)")

    def _on_reposition_overlay_clicked(self):
        self.overlay.show()
        self.overlay.raise_()
        self.overlay.set_click_through(False)  # Unlock for mouse drag
        self.status_label.setText("Overlay unlocked. Drag and resize to position above game.")

    def _browse_txt_path(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Select Dialogue History File", self.txt_path_edit.text(), "Text Files (*.txt);;All Files (*)"
        )
        if path:
            self.txt_path_edit.setText(path)
            self.settings.set("txt_output_path", path)
            self.txt_writer.set_file_path(path)

    def _on_reset_txt_history(self):
        ok = self.txt_writer.clear_session()
        if ok:
            self.status_label.setText("TXT dialogue history session reset.")

    def _clear_views(self):
        self.detected_text_edit.clear()
        self.translated_text_edit.clear()
        self.seq_badge.setText("Seq: #0")
        self.cache_badge.setText("")
        self.overlay.clear_dialogue()
        self._dialogue_cache_by_seq.clear()
        if self.ocr_worker:
            self.ocr_worker.reset_detectors()
        if self.translation_worker:
            self.translation_worker.reset_state()
        self.status_label.setText("Cleared dialogue views, overlay, and scheduler.")

    def _get_lang_codes(self):
        src_raw = self.src_lang_combo.currentText().lower()
        if "en" in src_raw:
            sl = "en"
        elif "ja" in src_raw:
            sl = "ja"
        elif "zh" in src_raw:
            sl = "zh"
        else:
            sl = "auto"
        return sl, "vi"

    def _on_manual_translate(self):
        text = self.detected_text_edit.toPlainText().strip()
        if not text:
            return

        self._manual_seq_counter += 1
        seq_id = self._manual_seq_counter
        self.seq_badge.setText(f"Seq: #{seq_id} (Manual)")
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
                "Region Required",
                "Please click 'Select Screen Region' to choose the dialogue box area before starting capture.",
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
        elif self.pause_btn.text().startswith("▶"):
            self.capture_worker.resume_capture()

    def _pause_capture(self):
        if self.capture_worker and self.capture_worker.isRunning():
            if self.pause_btn.text().startswith("⏸"):
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

    @pyqtSlot(QImage, object, float)
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

        self.hud_cap_lat_label.setText(f"Cap: {latency_ms:.1f} ms")

        # Pass frame to OCR worker without blocking capture
        if self.ocr_worker and self.ocr_enable_cb.isChecked():
            self.ocr_worker.enqueue_frame(frame_array)

    @pyqtSlot(int, str, float, float)
    def _on_dialogue_detected(self, seq_id: int, text: str, confidence: float, latency_ms: float):
        self.seq_badge.setText(f"Seq: #{seq_id}")
        self.detected_text_edit.setPlainText(text)
        self.status_label.setText(f"Dialogue #{seq_id} recognized. Submitting for translation...")
        self._dialogue_cache_by_seq[seq_id] = text

        # Update overlay original text if enabled
        if self.overlay.isVisible() and self.show_orig_cb.isChecked():
            self.overlay.orig_label.setText(text)

        # Submit to Translation Worker
        if self.translation_worker:
            sl, tl = self._get_lang_codes()
            self.translation_worker.request_translation(seq_id, text, src_lang=sl, tgt_lang=tl)

    @pyqtSlot(int, str, str, float, bool)
    def _on_translation_ready(self, seq_id: int, orig: str, trans: str, latency_ms: float, is_cached: bool):
        self.translated_text_edit.setPlainText(trans)
        cache_str = "[CACHED]" if is_cached else "[LIVE]"
        self.cache_badge.setText(cache_str)
        self.hud_trans_lat_label.setText(f"Trans: {latency_ms:.0f} ms {'(Cache)' if is_cached else ''}")
        self.status_label.setText(f"Translated dialogue #{seq_id} ({cache_str.lower()} in {latency_ms:.1f} ms)")

        # 1. Update Game Overlay (if enabled)
        if self.overlay_cb.isChecked() and self.overlay.isVisible():
            self.overlay.update_dialogue(seq_id, orig, trans)

        # 2. Append to TXT Dialogue History (if enabled)
        if self.txt_cb.isChecked():
            self.txt_writer.append_dialogue(seq_id, orig, trans, status="success")

        logger.info("Translation displayed [Seq %d]: '%s' (%s in %.1f ms)", seq_id, trans, cache_str, latency_ms)

    @pyqtSlot(int)
    def _on_translation_stale(self, seq_id: int):
        logger.info("Discarded stale translation result [Seq %d] to protect newer live dialogue.", seq_id)
        # Record skipped in TXT history if dialogue text was registered
        if self.txt_cb.isChecked() and seq_id in self._dialogue_cache_by_seq:
            orig = self._dialogue_cache_by_seq[seq_id]
            self.txt_writer.append_dialogue(seq_id, orig, "", status="skipped")

    @pyqtSlot(int, str, str)
    def _on_translation_failed(self, seq_id: int, orig: str, err_msg: str):
        self.status_label.setText(f"Translation #{seq_id} failed: {err_msg}")
        self.cache_badge.setText("[FAILED]")
        # Record failed in TXT history if enabled
        if self.txt_cb.isChecked():
            self.txt_writer.append_dialogue(seq_id, orig, err_msg, status="failed")

    @pyqtSlot(str, float, float)
    def _on_ocr_completed(self, text: str, confidence: float, latency_ms: float):
        self.hud_ocr_lat_label.setText(f"OCR: {latency_ms:.1f} ms")
        self.ocr_status_label.setText(f"Last OCR: {latency_ms:.1f} ms")

    @pyqtSlot(float)
    def _on_ocr_skipped(self, diff_score: float):
        self.ocr_status_label.setText(f"Static (diff: {diff_score:.1f})")

    @pyqtSlot(float, float)
    def _on_fps_updated(self, fps: float, avg_latency: float):
        self.hud_fps_label.setText(f"FPS: {fps:.1f}")
        self.perf_label.setText(f"Capture: Active | Cap: {avg_latency:.1f} ms | FPS: {fps:.1f}")

    @pyqtSlot(bool, bool)
    def _on_capture_status_changed(self, is_running: bool, is_paused: bool):
        if is_running and not is_paused:
            self.state_badge.setText("CAPTURING")
            self.state_badge.setStyleSheet(
                "background-color: #007ACC; color: #FFFFFF; font-weight: bold; "
                "padding: 4px 10px; border-radius: 4px; font-size: 11px;"
            )
            self.start_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.pause_btn.setText("⏸  Pause (F9)")
            self.stop_btn.setEnabled(True)
            self.status_label.setText("Pipeline active: Capture + OCR + Translation + Overlay + TXT.")
        elif is_running and is_paused:
            self.state_badge.setText("PAUSED")
            self.state_badge.setStyleSheet(
                "background-color: #D97706; color: #FFFFFF; font-weight: bold; "
                "padding: 4px 10px; border-radius: 4px; font-size: 11px;"
            )
            self.start_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.pause_btn.setText("▶  Resume (F9)")
            self.stop_btn.setEnabled(True)
            self.status_label.setText("Screen capture paused.")
        else:
            self.state_badge.setText("STOPPED")
            self.state_badge.setStyleSheet(
                "background-color: #3A3F4B; color: #FFFFFF; font-weight: bold; "
                "padding: 4px 10px; border-radius: 4px; font-size: 11px;"
            )
            self.start_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.pause_btn.setText("⏸  Pause (F9)")
            self.stop_btn.setEnabled(False)
            self.status_label.setText("Screen capture stopped.")
            self.hud_fps_label.setText("FPS: --")
            self.hud_ocr_lat_label.setText("OCR: -- ms")
            self.hud_trans_lat_label.setText("Trans: -- ms")
            self.perf_label.setText("Capture: Idle | Cap: -- ms | OCR: -- ms | Trans: -- ms | FPS: 0.0")

    @pyqtSlot(str)
    def _on_capture_error(self, err_msg: str):
        self.status_label.setText(f"Capture Error: {err_msg}")
        logger.error("Capture worker error: %s", err_msg)

    @pyqtSlot(str)
    def _on_ocr_error(self, err_msg: str):
        self.status_label.setText(f"OCR Error: {err_msg}")
        logger.error("OCR worker error: %s", err_msg)

    def closeEvent(self, event):
        self._stop_capture()
        self.overlay.close()
        self.hotkey_manager.cleanup()
        self.screen_capture.close()
        event.accept()
