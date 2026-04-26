#!/usr/bin/env python3
"""
Gemini Assistant for macOS — Python/PyQt6 port
Run: python main.py
"""

import sys
import os

# ── must set before QApplication ──────────────────────────────────────────────
os.environ["QT_MAC_WANTS_LAYER"] = "1"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ui.window import AssistantWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Gemini Assistant")
    app.setOrganizationName("GeminiAssistant")

    # Keep app alive even when window is hidden (menu-bar style)
    app.setQuitOnLastWindowClosed(False)

    window = AssistantWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
