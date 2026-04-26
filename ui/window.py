"""
ui/window.py — Floating pill input + dark frosted answer card below
"""

from __future__ import annotations
import threading
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QFrame,
    QScrollArea, QSystemTrayIcon, QMenu, QApplication,
    QGraphicsOpacityEffect, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QPoint, QObject,
    QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QLinearGradient,
    QBrush, QPen, QFont, QIcon, QPixmap, QFontDatabase,
    QAction, QKeySequence, QShortcut
)
from core.assistant import (
    call_gemini, classify_command, load_settings, save_settings,
    fetch_calendar_events, fetch_reminders, fetch_imessages,
    search_contacts, take_screenshot_interactive, place_facetime_call,
    DEFAULT_MODEL
)
from ui.settings_dialog import SettingsDialog
from core.wake_word import SmartListener

FONT_UI = "Helvetica Neue"

def _resolve_fonts():
    global FONT_UI
    fams = QFontDatabase.families()
    FONT_UI = "SF Pro Display" if "SF Pro Display" in fams else "Helvetica Neue"


# ── Gemini worker ──────────────────────────────────────────────────────────────
class GeminiWorker(QObject):
    finished = pyqtSignal(str)
    def __init__(self, prompt, api_key, model, image_data=None, system_context=""):
        super().__init__()
        self.prompt, self.api_key, self.model = prompt, api_key, model
        self.image_data, self.system_context = image_data, system_context
    def run(self):
        self.finished.emit(call_gemini(
            self.prompt, self.api_key, self.model,
            self.image_data, self.system_context))


# ── Frosted pill input bar ─────────────────────────────────────────────────────
class PillBar(QWidget):
    """Floating frosted pill — the only thing visible when idle."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # NO WA_TranslucentBackground here — we paint our own background
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 7, 8, 7)
        layout.setSpacing(6)

        # ✦ icon
        icon = QLabel("✦")
        icon.setFont(QFont(FONT_UI, 14))
        icon.setFixedWidth(26)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("color: rgba(138,180,248,230); background: transparent;")
        layout.addWidget(icon)

        # Input — no border, blends into pill
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask anything…")
        self.input.setFont(QFont(FONT_UI, 14))
        self.input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                color: white;
                border: none;
                padding: 0;
                selection-background-color: rgba(66,133,244,180);
            }
            QLineEdit::placeholder { color: rgba(255,255,255,80); }
        """)
        layout.addWidget(self.input, 1)

        # Mic button
        self.mic = QPushButton("🎤")
        self.mic.setFixedSize(36, 36)
        self.mic.setFont(QFont(FONT_UI, 14))
        self.mic.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic.setStyleSheet(self._mic_style(False))
        layout.addWidget(self.mic)

        # Send button
        self.send = QPushButton("↑")
        self.send.setFixedSize(36, 36)
        self.send.setFont(QFont(FONT_UI, 16, QFont.Weight.Bold))
        self.send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send.setStyleSheet(self._send_style(False))
        layout.addWidget(self.send)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 26, 26)
        # Frosted dark glass
        p.fillPath(path, QBrush(QColor(30, 30, 40, 200)))
        # Subtle border
        p.setPen(QPen(QColor(255, 255, 255, 35), 1))
        p.drawPath(path)

    def _mic_style(self, active):
        if active:
            return ("QPushButton{background:rgba(220,53,69,220);"
                    "border:none;border-radius:18px;color:white;}")
        return ("QPushButton{background:transparent;border:none;"
                "border-radius:18px;color:rgba(255,255,255,140);}"
                "QPushButton:hover{color:white;background:rgba(255,255,255,12);}")

    def _send_style(self, active):
        if active:
            return ("QPushButton{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                    "stop:0 #4285F4,stop:1 #1a73e8);"
                    "color:white;border:none;border-radius:18px;}")
        return ("QPushButton{background:transparent;color:rgba(255,255,255,50);"
                "border:none;border-radius:18px;}")

    def set_mic_active(self, on: bool):
        self.mic.setStyleSheet(self._mic_style(on))

    def set_send_active(self, on: bool):
        self.send.setStyleSheet(self._send_style(on))


# ── Chips row ──────────────────────────────────────────────────────────────────
class ChipsRow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(30)          # strictly single-line height
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(5)
        self.buttons = {}
        style = """
            QPushButton {
                background: rgba(30,30,42,180);
                color: rgba(255,255,255,150);
                border: 1px solid rgba(255,255,255,16);
                border-radius: 10px;
                padding: 0px 10px;
                font-size: 11px;
                max-height: 22px;
                min-height: 22px;
            }
            QPushButton:hover { background:rgba(50,50,68,220); color:white; }
        """
        for label in ["📅 Calendar","☑️ Reminders","💬 Messages","📷 Screen","⚙️"]:
            b = QPushButton(label)
            b.setFont(QFont(FONT_UI, 11))
            b.setFixedHeight(22)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(style)
            layout.addWidget(b)
            self.buttons[label] = b


# ── Answer card — dark charcoal, capped at 1/8 screen height ─────────────────
class AnswerCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._max_h = QApplication.primaryScreen().availableGeometry().height() // 4

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 3px; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,60); border-radius:1px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        il = QVBoxLayout(inner)
        il.setContentsMargins(18, 14, 18, 14)

        self.label = QLabel("")
        self.label.setWordWrap(True)
        self.label.setFont(QFont(FONT_UI, 13))
        self.label.setStyleSheet("color: rgba(255,255,255,225); background: transparent;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        il.addWidget(self.label)
        il.addStretch()

        self._scroll.setWidget(inner)
        layout.addWidget(self._scroll)

        self._fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fx)
        self._fx.setOpacity(1.0)

    def update_height(self, card_inner_width: int):
        """Resize card to content, capped at 1/8 screen."""
        self.label.setFixedWidth(card_inner_width)
        hint = self.label.heightForWidth(card_inner_width)
        if hint < 0:
            hint = self.label.sizeHint().height()
        content_h = hint + 28          # + top/bottom padding
        final_h = min(content_h, self._max_h)
        self._scroll.setFixedHeight(final_h)
        self.setFixedHeight(final_h)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 18, 18)
        # Dark charcoal — same tone as Siri answer card
        p.fillPath(path, QBrush(QColor(28, 28, 38, 240)))
        # Thin top border highlight
        p.setPen(QPen(QColor(255, 255, 255, 20), 1))
        p.drawPath(path)

    def fade_in(self):
        a = QPropertyAnimation(self._fx, b"opacity")
        a.setDuration(300); a.setStartValue(0.0); a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.start(); self._ani_in = a

    def fade_out(self, cb):
        a = QPropertyAnimation(self._fx, b"opacity")
        a.setDuration(500); a.setStartValue(1.0); a.setEndValue(0.0)
        a.setEasingCurve(QEasingCurve.Type.InCubic)
        a.finished.connect(cb); a.start(); self._ani_out = a


# ── Main window ────────────────────────────────────────────────────────────────
class AssistantWindow(QMainWindow):
    _sig = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        _resolve_fonts()
        self.settings  = load_settings()
        self._drag_pos = None
        self._fade_tmr = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(440)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - 460, screen.top() + 20)

        self._build_ui()
        self._setup_tray()
        self._setup_shortcuts()
        self._setup_listener()
        self._sig.connect(self._on_response)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QWidget()
        root.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCentralWidget(root)

        self._vbox = QVBoxLayout(root)
        self._vbox.setContentsMargins(0, 0, 0, 0)
        self._vbox.setSpacing(6)

        # Pill input bar
        self._bar = PillBar()
        self._bar.input.returnPressed.connect(self._send)
        self._bar.input.textChanged.connect(
            lambda t: self._bar.set_send_active(bool(t)))
        self._bar.input.textChanged.connect(self._filter_chips)
        self._bar.send.clicked.connect(self._send)
        self._bar.mic.clicked.connect(self._toggle_mic)
        self._vbox.addWidget(self._bar)

        # Chips row — hidden by default, appears when typing
        self._chips = ChipsRow()
        self._chips.buttons["📅 Calendar"].clicked.connect(self._do_calendar)
        self._chips.buttons["☑️ Reminders"].clicked.connect(self._do_reminders)
        self._chips.buttons["💬 Messages"].clicked.connect(self._do_messages)
        self._chips.buttons["📷 Screen"].clicked.connect(self._do_screenshot)
        self._chips.buttons["⚙️"].clicked.connect(self._open_settings)
        self._chips.setVisible(False)
        self._vbox.addWidget(self._chips)

        # Answer card (hidden until response arrives)
        self._card = AnswerCard()
        self._card.setVisible(False)
        self._vbox.addWidget(self._card)

        self.adjustSize()

    # ── Tray ──────────────────────────────────────────────────────────────────
    def _setup_tray(self):
        pix = QPixmap(22, 22)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = QLinearGradient(0, 0, 22, 22)
        g.setColorAt(0, QColor(66, 133, 244))
        g.setColorAt(1, QColor(138, 180, 248))
        p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(1, 1, 20, 20)
        p.setPen(QPen(QColor(255, 255, 255)))
        p.setFont(QFont(FONT_UI, 9))
        p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "✦")
        p.end()

        self._tray = QSystemTrayIcon(QIcon(pix), self)
        m = QMenu()
        m.setStyleSheet("""
            QMenu { background:#1c1c24; color:white;
                    border:1px solid rgba(255,255,255,20);
                    border-radius:8px; padding:4px; }
            QMenu::item { padding:6px 16px; border-radius:4px; }
            QMenu::item:selected { background:rgba(66,133,244,100); }
        """)
        for lbl, fn in [
            ("Show", self.toggle_visibility), (None, None),
            ("Settings", self._open_settings), (None, None),
            ("Quit", QApplication.quit)
        ]:
            if lbl is None: m.addSeparator()
            else:
                a = QAction(lbl, self); a.triggered.connect(fn); m.addAction(a)
        self._tray.setContextMenu(m)
        self._tray.activated.connect(
            lambda r: self.toggle_visibility()
            if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        self._tray.show()

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+,"), self).activated.connect(self._open_settings)
        QShortcut(QKeySequence("Escape"),  self).activated.connect(self.hide)

    # ── Mic listener ──────────────────────────────────────────────────────────
    def _setup_listener(self):
        self._listener = SmartListener(self)
        self._listener.wake_activated.connect(self._on_wake)
        self._listener.wake_command.connect(self._on_wake_cmd)
        self._listener.partial_text.connect(self._bar.input.setText)
        self._listener.final_text.connect(self._on_dictation_final)
        self._listener.error.connect(lambda e: print(f"[Mic] {e}"))
        self._listener.start()

    def _on_wake(self):
        self.show(); self.raise_(); self.activateWindow()
        self._bar.set_mic_active(True)
        self._bar.input.setPlaceholderText("Listening…")

    def _on_wake_cmd(self, text: str):
        self._bar.set_mic_active(False)
        self._bar.input.setPlaceholderText("Ask anything…")
        if text:
            self._bar.input.setText(text)
            self._send()

    def _on_dictation_final(self, text: str):
        self._bar.input.setText(text)
        self._bar.input.setCursorPosition(len(text))
        self._bar.set_mic_active(False)

    def _toggle_mic(self):
        self._bar.input.setFocus()

    def showEvent(self, e):
        super().showEvent(e)
        if hasattr(self, "_listener"):
            self._listener.set_window_visible(True)

    def hideEvent(self, e):
        super().hideEvent(e)
        if hasattr(self, "_listener"):
            self._listener.set_window_visible(False)

    # ── Response ──────────────────────────────────────────────────────────────
    def _show_thinking(self, msg="Thinking…"):
        if self._fade_tmr:
            self._fade_tmr.stop()
        self._card.label.setText(msg)
        self._card._fx.setOpacity(0.45)
        self._card.setVisible(True)
        QTimer.singleShot(0, self._resize_to_content)

    def _on_response(self, text: str):
        if self._fade_tmr:
            self._fade_tmr.stop()
        self._card.label.setText(text)
        self._card._fx.setOpacity(0.0)
        self._card.setVisible(True)
        self._card.fade_in()
        # Defer resize so Qt has processed the new text first
        QTimer.singleShot(0, self._resize_to_content)

        # Auto-fade after 20s
        self._fade_tmr = QTimer(self)
        self._fade_tmr.setSingleShot(True)
        self._fade_tmr.timeout.connect(
            lambda: self._card.fade_out(self._hide_card))
        self._fade_tmr.start(20000)

    def _resize_to_content(self):
        inner_w = self.width() - 36   # 18px padding each side
        self._card.update_height(inner_w)
        self.adjustSize()

    def _hide_card(self):
        self._card.setVisible(False)
        self._card.label.setText("")
        self.adjustSize()

    # ── Send ──────────────────────────────────────────────────────────────────
    def _send(self):
        text = self._bar.input.text().strip()
        if not text: return
        self._bar.input.clear()
        cmd = classify_command(text)
        if   cmd == "calendar":   self._do_calendar()
        elif cmd == "reminders":  self._do_reminders()
        elif cmd == "messages":   self._do_messages()
        elif cmd == "contacts":   self._do_contacts()
        elif cmd == "screenshot": self._do_screenshot()
        elif cmd == "facetime":   self._do_facetime(text)
        else:                     self._ask_gemini(text)

    def _ask_gemini(self, prompt, image_data=None, system_context=""):
        self._show_thinking()
        key   = self.settings.get("api_key", "")
        model = self.settings.get("model", DEFAULT_MODEL)
        self._worker = GeminiWorker(prompt, key, model, image_data, system_context)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._sig)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    # ── Features ──────────────────────────────────────────────────────────────
    def _do_calendar(self):
        self._show_thinking("Fetching calendar…")
        def _go():
            raw = fetch_calendar_events()
            ctx = f"Calendar:\n{raw}" if raw.strip() else "No events found."
            self._sig.emit(call_gemini("Summarize my upcoming schedule",
                self.settings.get("api_key",""), self.settings.get("model", DEFAULT_MODEL),
                system_context=ctx))
        threading.Thread(target=_go, daemon=True).start()

    def _do_reminders(self):
        self._show_thinking("Fetching reminders…")
        def _go():
            raw = fetch_reminders()
            if not raw.strip() or "No pending" in raw:
                self._sig.emit("✅ No pending reminders!"); return
            self._sig.emit(call_gemini("Summarize my reminders",
                self.settings.get("api_key",""), self.settings.get("model", DEFAULT_MODEL),
                system_context=f"Reminders:\n{raw}"))
        threading.Thread(target=_go, daemon=True).start()

    def _do_messages(self):
        self._show_thinking("Reading messages…")
        def _go():
            raw = fetch_imessages()
            self._sig.emit(call_gemini("Summarize my recent iMessages",
                self.settings.get("api_key",""), self.settings.get("model", DEFAULT_MODEL),
                system_context=f"Messages:\n{raw}"))
        threading.Thread(target=_go, daemon=True).start()

    def _do_contacts(self):
        self._show_thinking("Searching contacts…")
        def _go():
            self._sig.emit(f"👥 Found {len(search_contacts())} contacts.")
        threading.Thread(target=_go, daemon=True).start()

    def _do_screenshot(self):
        self.hide()
        self._show_thinking("Select area…")
        def _go():
            import time; time.sleep(0.3)
            img = take_screenshot_interactive()
            if not img:
                self._sig.emit("Screenshot cancelled."); return
            QTimer.singleShot(0, self.show)
            self._sig.emit(call_gemini(
                "Describe and analyze this screenshot in detail.",
                self.settings.get("api_key",""), self.settings.get("model", DEFAULT_MODEL),
                image_data=img))
        threading.Thread(target=_go, daemon=True).start()
        QTimer.singleShot(500, self.show)

    def _do_facetime(self, text):
        self._show_thinking("Finding contact…")
        def _go():
            name = call_gemini(
                f"Extract only the person's name from: '{text}'. Reply ONLY the name.",
                self.settings.get("api_key",""),
                self.settings.get("model", DEFAULT_MODEL)).strip()
            contacts = search_contacts(name)
            if not contacts:
                self._sig.emit(f"Couldn't find '{name}'."); return
            c = contacts[0]
            addr = c.get("email") or c.get("phone")
            if not addr:
                self._sig.emit(f"No address for {c['name']}."); return
            self._sig.emit(
                f"📹 Calling {c['name']}…" if place_facetime_call(addr) else "Failed.")
        threading.Thread(target=_go, daemon=True).start()

    def _filter_chips(self, text: str):
        """Show chips row only when typing, filter by keyword."""
        t = text.lower().strip()
        if not t:
            self._chips.setVisible(False)
            self.adjustSize()
            return

        mapping = {
            "📅 Calendar":  ["calendar", "schedule", "event", "meeting", "cal"],
            "☑️ Reminders": ["reminder", "remind", "todo", "rem"],
            "💬 Messages":  ["message", "imessage", "text", "chat", "mes"],
            "📷 Screen":    ["screenshot", "screen", "capture", "scr"],
            "⚙️":           ["setting", "config", "key", "set"],
        }
        any_visible = False
        for label, keywords in mapping.items():
            btn = self._chips.buttons[label]
            show = any(k.startswith(t) or t in k for k in keywords)
            btn.setVisible(show)
            if show:
                any_visible = True

        # Show row only if at least one chip matches
        self._chips.setVisible(any_visible)
        self.adjustSize()

    def _open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            self.settings = dlg.get_settings()
            save_settings(self.settings)

    def toggle_visibility(self):
        if self.isVisible(): self.hide()
        else: self.show(); self.raise_(); self.activateWindow()

    # ── Drag ──────────────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (e.globalPosition().toPoint()
                              - self.frameGeometry().topLeft())

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    # ── Window background = fully transparent (widgets paint themselves) ───────
    def paintEvent(self, e):
        pass