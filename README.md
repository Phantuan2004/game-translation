# Game Translator — Real-time Game Dialogue Translation Tool

A lightweight, low-latency Windows desktop utility that captures dialogue text displayed inside games, recognizes it locally using OCR, translates it into Vietnamese, and displays the translation in real-time via an overlay and live text log.

## Features & Milestones

- **Milestone 1 (Completed):**
  - High-performance screen capture with sub-millisecond latency
  - Dynamic monitor detection & selection with DPI scaling support
  - Interactive click-and-drag screen region selector with dimension badge
  - Real-time capture preview with aspect-ratio scaling
  - Non-blocking background capture worker (`QThread`) with live latency and FPS metrics
  - Safe JSON configuration persistence with validation and corrupt file recovery
  - Modern dark-themed Windows UI (PyQt6)

- **Milestone 2 (Completed):**
  - Pluggable local OCR engine architecture:
    - **Windows Media OCR**: Built-in, ultra-fast (~5-15 ms latency), zero cloud dependencies.
    - **RapidOCR**: Local ONNX neural text detection & recognition.
    - **Auto Engine**: Chooses the fastest available local engine with automatic fallback.
  - Sub-millisecond Image Change Detection (`ImageChangeDetector`) to skip OCR on static screens.
  - Multi-line dialogue text normalization (`TextNormalizer`) with hyphenation handling and quote cleaning.
  - Dialogue duplicate suppression & sequence tracking (`DialogueDetector`).
  - Dedicated background `OCRWorker` with bounded latest-frame priority (zero backlog accumulation).
  - Live detected dialogue and sequence badge updates in the UI.

- **Milestone 3 (Completed):**
  - Pluggable translation provider interface:
    - **Google Translate (Free)**: Real-time, natural Vietnamese dialogue translation without requiring paid API keys.
    - **DeepL API**: Configurable Free and Pro endpoint with masked API key storage.
  - **Bounded Latest-Priority Translation Scheduler (`TranslationScheduler`)**:
    - Discards outdated pending work when games advance dialogue rapidly.
    - Sequence ID enforcement (`validate_for_display`): guarantees that older completed translations can never overwrite newer dialogue.
  - **SQLite Translation Cache (`TranslationCache`)**:
    - Persistent across application restarts in `config/translation_cache.db`.
    - Fuzzy normalized comparison keys (`TextNormalizer.comparison_key`).
    - Sub-millisecond lookup latency.
  - Background `TranslationWorker` with live/cached status badges.
  - Manual translation mode allowing user editing before translating.

- **Milestone 4 (Completed):**
  - **Frameless Transparent Game Overlay (`TranslationOverlay`)**:
    - Always on Top floating HUD for Windowed & Borderless Windowed games.
    - Displays high-contrast Vietnamese translation with optional English original text.
    - Adjustable font size (12 - 36 pt), typography, background color, and opacity (20% - 100%).
    - Word wrapping with drop-shadow effects for legibility over bright and dark backgrounds.
  - **Native Windows Click-Through (`WS_EX_TRANSPARENT`)**:
    - Mouse clicks pass through directly into the game without gameplay interference.
    - "Unlock / Reposition Mode" allowing easy mouse dragging and corner resizing.
    - Automatic geometry and settings persistence.
  - **Global Hotkeys (`HotkeyManager`)**:
    - Official Windows API `RegisterHotKey` (safe from anti-cheat hook detection).
    - **F8**: Toggle overlay visibility
    - **F9**: Pause / resume capture
    - **F10**: Manual translate current text
    - **F11**: Clear current dialogue

- **Milestone 5 (Completed):**
  - **Live TXT Dialogue History Output (`TxtWriter`)**:
    - Thread-safe, chronological dialogue appending with UTF-8 encoding.
    - Format: `[HH:MM:SS] \n EN: ... \n VI: ... \n ---`.
    - Handles skipped dialogue (latency discard) and translation failure indicators.
    - Consecutive duplicate suppression.
    - "Open File" action launching default text editor (Notepad).
    - Session reset marker (`=== SESSION RESET ===`).
  - **Simultaneous Dual Output**:
    - Game Overlay and Live TXT output run concurrently or independently.
    - Clean pipeline startup, pause, resume, and teardown across all worker threads.

- **Milestone 6 (Upcoming):**
  - In-game testing, packaging, and validation

## Quick Start

### Prerequisites
- Windows 10 / 11
- Python 3.10+ (tested with Python 3.14)

### Installation
```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Running the Application
```powershell
.\.venv\Scripts\python.exe main.py
```

### Running Tests
```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```
