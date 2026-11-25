import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.settings_manager import SettingsManager
from app.main_window import MainWindow


def setup_logging():
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "game_translator.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main():
    setup_logging()
    logger = logging.getLogger("main")
    logger.info("Starting Game Translator Application...")

    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Game Translator")
    app.setOrganizationName("GameTranslator")

    settings = SettingsManager()
    window = MainWindow(settings_manager=settings)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
