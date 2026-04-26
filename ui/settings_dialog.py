"""
ui/settings_dialog.py — Settings window, clean redesign
"""

from __future__ import annotations
import threading

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFrame, QWidget, QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QFont, QDesktopServices, QColor, QPainter, QPainterPath, QBrush, QPen

from core.assistant import GEMINI_MODELS, DEFAULT_MODEL, test_connection


STYLE = """
QDialog { background: #0f0f17; color: white; }
QScrollArea, QWidget#scroll_contents { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 4px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,50); border-radius: 2px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QLabel { background: transparent; }
QLineEdit {
    background: rgba(255,255,255,8);
    color: rgba(255,255,255,220);
    border: 1px solid rgba(255,255,255,22);
    border-radius: 9px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: #4285F4;
}
QLineEdit:focus { border: 1px solid rgba(66,133,244,180); background: rgba(255,255,255,11); }
QLineEdit:hover { border: 1px solid rgba(255,255,255,35); }
QComboBox {
    background: rgba(255,255,255,8);
    color: rgba(255,255,255,220);
    border: 1px solid rgba(255,255,255,22);
    border-radius: 9px;
    padding: 8px 12px;
    font-size: 12px;
}
QComboBox:hover { border: 1px solid rgba(255,255,255,35); }
QComboBox:focus { border: 1px solid rgba(66,133,244,180); }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: #1a1a26;
    color: rgba(255,255,255,210);
    border: 1px solid rgba(255,255,255,18);
    border-radius: 8px;
    selection-background-color: rgba(66,133,244,160);
    padding: 4px;
    outline: none;
}
QPushButton {
    background: rgba(255,255,255,10);
    color: rgba(255,255,255,190);
    border: 1px solid rgba(255,255,255,18);
    border-radius: 8px;
    padding: 7px 16px;
    font-size: 12px;
}
QPushButton:hover { background: rgba(255,255,255,17); color: white; }
QPushButton:pressed { background: rgba(255,255,255,8); }
QPushButton#btn_save {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #4285F4, stop:1 #1a73e8);
    color: white; border: none; font-weight: 600;
}
QPushButton#btn_save:hover {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #5a9cf5, stop:1 #2b84f9);
}
QPushButton#btn_link {
    background: transparent; border: none;
    color: #4285F4; font-size: 11px; padding: 0;
}
QPushButton#btn_link:hover { color: #8AB4F8; }
QPushButton#btn_eye {
    background: transparent; border: none;
    font-size: 15px; padding: 0 4px; border-radius: 6px;
}
QPushButton#btn_eye:hover { background: rgba(255,255,255,10); }
"""


class Card(QWidget):
    """Rounded frosted card."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._vbox = QVBoxLayout(self)
        self._vbox.setContentsMargins(16, 14, 16, 14)
        self._vbox.setSpacing(10)

    def add(self, w):
        self._vbox.addWidget(w)
        return w

    def add_layout(self, l):
        self._vbox.addLayout(l)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 12, 12)
        p.fillPath(path, QBrush(QColor(255, 255, 255, 10)))
        p.setPen(QPen(QColor(255, 255, 255, 20), 1))
        p.drawPath(path)


def _hdivider():
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet("background: rgba(255,255,255,12); border:none;")
    return f


def _cap(text: str) -> QLabel:
    l = QLabel(text.upper())
    l.setFont(QFont("Helvetica Neue", 10, QFont.Weight.DemiBold))
    l.setStyleSheet("color: rgba(255,255,255,45); letter-spacing: 1px;")
    return l


def _row_label(text: str, size=13) -> QLabel:
    l = QLabel(text)
    l.setFont(QFont("Helvetica Neue", size, QFont.Weight.Medium))
    l.setStyleSheet("color: rgba(255,255,255,210);")
    return l


def _sub_label(text: str) -> QLabel:
    l = QLabel(text)
    l.setFont(QFont("Menlo", 10))
    l.setStyleSheet("color: rgba(255,255,255,70);")
    return l


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = dict(settings)
        self.setWindowTitle("Settings")
        self.setFixedSize(460, 620)
        self.setStyleSheet(STYLE)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet(
            "background: rgba(255,255,255,5);"
            "border-bottom: 1px solid rgba(255,255,255,10);"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)
        title_lbl = QLabel("Settings")
        title_lbl.setFont(QFont("Helvetica Neue", 15, QFont.Weight.DemiBold))
        title_lbl.setStyleSheet("color: white;")
        hl.addWidget(title_lbl)
        root.addWidget(header)

        # ── Scroll body ───────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QWidget()
        body.setObjectName("scroll_contents")
        vbox = QVBoxLayout(body)
        vbox.setContentsMargins(20, 18, 20, 18)
        vbox.setSpacing(18)

        # ─ API Key card ───────────────────────────────────────────────────────
        vbox.addWidget(_cap("AI Configuration"))
        key_card = Card()

        kh = QHBoxLayout()
        kh.setContentsMargins(0, 0, 0, 0)
        kh.addWidget(_row_label("Gemini API Key"))
        kh.addStretch()
        link_btn = QPushButton("Get free key →")
        link_btn.setObjectName("btn_link")
        link_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://aistudio.google.com/app/apikey")))
        kh.addWidget(link_btn)
        key_card.add_layout(kh)

        ki = QHBoxLayout()
        ki.setSpacing(6)
        self._key_input = QLineEdit()
        self._key_input.setText(self.settings.get("api_key", ""))
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setFixedHeight(38)
        eye = QPushButton("👁")
        eye.setObjectName("btn_eye")
        eye.setFixedSize(36, 38)
        eye.setToolTip("Show / hide key")
        eye.clicked.connect(self._toggle_eye)
        ki.addWidget(self._key_input, 1)
        ki.addWidget(eye)
        key_card.add_layout(ki)

        hint = QLabel("Stored locally at ~/.config/gemini-assistant/settings.json")
        hint.setWordWrap(True)
        hint.setFont(QFont("Helvetica Neue", 10))
        hint.setStyleSheet("color: rgba(255,255,255,45);")
        key_card.add(hint)

        self._test_btn = QPushButton("Test Connection")
        self._test_btn.setFixedHeight(34)
        self._test_btn.clicked.connect(self._test_api)
        key_card.add(self._test_btn)

        # Result label — hidden until test runs, wraps freely
        self._test_result = QLabel("")
        self._test_result.setWordWrap(True)
        self._test_result.setFont(QFont("Helvetica Neue", 11))
        self._test_result.setVisible(False)
        key_card.add(self._test_result)

        vbox.addWidget(key_card)

        # ─ Model card ─────────────────────────────────────────────────────────
        vbox.addWidget(_cap("Model"))
        model_card = Card()
        model_card.add(_row_label("Gemini Model"))

        self._model_combo = QComboBox()
        self._model_combo.setFixedHeight(38)
        current = self.settings.get("model", DEFAULT_MODEL)
        for mid, mlabel in GEMINI_MODELS:
            self._model_combo.addItem(mlabel, userData=mid)
            if mid == current:
                self._model_combo.setCurrentIndex(self._model_combo.count() - 1)

        self._model_id_lbl = _sub_label(f"Model ID: {current}")
        self._model_combo.currentIndexChanged.connect(self._on_model_change)
        model_card.add(self._model_combo)
        model_card.add(self._model_id_lbl)
        vbox.addWidget(model_card)

        # ─ Permissions card ───────────────────────────────────────────────────
        vbox.addWidget(_cap("Permissions — Grant in System Settings → Privacy"))
        perm_card = Card()
        perms = [
            ("📅", "Calendar",           "Read upcoming events"),
            ("☑️",  "Reminders",          "Read pending reminders"),
            ("👥", "Contacts",           "Search & FaceTime contacts"),
            ("🎤", "Microphone",         "Voice commands"),
            ("🌐", "Speech Recognition", "Convert speech to text"),
            ("📷", "Screen Recording",   "Screenshot analysis"),
        ]
        for i, (icon, name, desc) in enumerate(perms):
            if i > 0:
                perm_card.add(_hdivider())
            row = QHBoxLayout()
            row.setContentsMargins(0, 3, 0, 3)
            row.setSpacing(10)

            icon_lbl = QLabel(icon)
            icon_lbl.setFixedWidth(22)
            icon_lbl.setFont(QFont("Helvetica Neue", 14))

            text_col = QVBoxLayout()
            text_col.setSpacing(1)
            name_lbl = QLabel(name)
            name_lbl.setFont(QFont("Helvetica Neue", 12, QFont.Weight.Medium))
            name_lbl.setStyleSheet("color: rgba(255,255,255,210);")
            desc_lbl = QLabel(desc)
            desc_lbl.setFont(QFont("Helvetica Neue", 10))
            desc_lbl.setStyleSheet("color: rgba(255,255,255,75);")
            text_col.addWidget(name_lbl)
            text_col.addWidget(desc_lbl)

            open_btn = QPushButton("Open →")
            open_btn.setObjectName("btn_link")
            open_btn.setFont(QFont("Helvetica Neue", 11))
            open_btn.clicked.connect(lambda: QDesktopServices.openUrl(
                QUrl("x-apple.systempreferences:com.apple.preference.security?Privacy")))

            row.addWidget(icon_lbl)
            row.addLayout(text_col, 1)
            row.addWidget(open_btn)
            perm_card.add_layout(row)

        vbox.addWidget(perm_card)

        # ─ About ──────────────────────────────────────────────────────────────
        about = QLabel("Gemini Assistant v1.0  ·  Powered by Google Gemini  ·  macOS 13+")
        about.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about.setFont(QFont("Helvetica Neue", 10))
        about.setStyleSheet("color: rgba(255,255,255,35);")
        vbox.addWidget(about)
        vbox.addStretch()

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(60)
        footer.setStyleSheet(
            "background: rgba(255,255,255,4);"
            "border-top: 1px solid rgba(255,255,255,10);"
        )
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 0, 20, 0)
        fl.setSpacing(10)
        fl.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(90, 34)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("btn_save")
        save_btn.setFixedSize(90, 34)
        save_btn.clicked.connect(self.accept)

        fl.addWidget(cancel_btn)
        fl.addWidget(save_btn)
        root.addWidget(footer)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _toggle_eye(self):
        if self._key_input.echoMode() == QLineEdit.EchoMode.Password:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Password)

    def _on_model_change(self, idx: int):
        mid = self._model_combo.itemData(idx)
        self._model_id_lbl.setText(f"Model ID: {mid}")

    def _test_api(self):
        self._test_btn.setEnabled(False)
        self._test_result.setVisible(True)
        self._test_result.setText("Testing…")
        self._test_result.setStyleSheet("color: rgba(255,255,255,130);")

        key   = self._key_input.text().strip()
        model = self._model_combo.currentData()

        def _do():
            result = test_connection(key, model)
            self._pending_test = result
            QTimer.singleShot(0, self._show_test_result)

        threading.Thread(target=_do, daemon=True).start()

    def _show_test_result(self):
        r = getattr(self, "_pending_test", "")
        ok = r.startswith("✅")
        self._test_result.setVisible(True)
        self._test_result.setText(r)
        self._test_result.setStyleSheet(
            f"color: {'#4ade80' if ok else '#f87171'};"
        )
        self._test_btn.setEnabled(True)

    def get_settings(self) -> dict:
        return {
            "api_key": self._key_input.text().strip(),
            "model":   self._model_combo.currentData(),
        }
