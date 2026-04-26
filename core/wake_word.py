"""
core/wake_word.py — Smart mic listener
- Window hidden  → listens for "Hey Google", then shows window + sends command
- Window visible → continuously transcribes speech into the text bar (live dictation)
"""

from __future__ import annotations
import threading
import time
from PyQt6.QtCore import QObject, pyqtSignal

WAKE_PHRASES = ["hey google", "okay google", "ok google", "hi google"]


class SmartListener(QObject):
    # Emitted when wake word detected while window is hidden
    wake_command    = pyqtSignal(str)   # full command (may be empty if just wake phrase)
    wake_activated  = pyqtSignal()      # just the trigger moment

    # Emitted during live dictation (window visible)
    partial_text    = pyqtSignal(str)   # intermediate — update text bar
    final_text      = pyqtSignal(str)   # finished phrase — send it

    error           = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running   = False
        self._visible   = False          # set by window
        self._available = False
        self._sr        = None
        self._mic       = None
        self._lock      = threading.Lock()
        self._check_deps()

    def _check_deps(self):
        try:
            import speech_recognition as sr
            self._sr  = sr
            self._mic = sr.Microphone()
            self._available = True
        except Exception as e:
            print(f"[Mic] Not available: {e}")

    @property
    def available(self) -> bool:
        return self._available

    def set_window_visible(self, visible: bool):
        """Call this whenever the window shows or hides."""
        self._visible = visible

    def start(self):
        if not self._available:
            self.error.emit(
                "Microphone unavailable.\n"
                "Run: brew install portaudio && pip install pyaudio"
            )
            return
        if self._running:
            return
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()
        print("[Mic] Smart listener started")

    def stop(self):
        self._running = False

    # ── Main loop ─────────────────────────────────────────────────────────────
    def _loop(self):
        sr = self._sr
        r  = sr.Recognizer()
        r.energy_threshold        = 300
        r.dynamic_energy_threshold = True
        r.pause_threshold         = 0.5
        r.non_speaking_duration   = 0.3

        while self._running:
            try:
                with self._mic as source:
                    r.adjust_for_ambient_noise(source, duration=0.15)
                    # Short phrase limit so we get quick updates
                    audio = r.listen(source, timeout=2, phrase_time_limit=6)

                text = self._transcribe(r, audio)
                if not text:
                    continue

                lower = text.lower().strip()

                if self._visible:
                    # ── Live dictation mode ───────────────────────────────────
                    # Emit as partial first for instant feedback, then final
                    self.partial_text.emit(text)
                    # Small pause then emit final (so user sees it settle)
                    time.sleep(0.05)
                    self.final_text.emit(text)

                else:
                    # ── Wake word mode ────────────────────────────────────────
                    if any(p in lower for p in WAKE_PHRASES):
                        print(f"[Mic] Wake word! full text: {lower!r}")
                        self.wake_activated.emit()

                        # Strip wake phrase — use the rest as command
                        cmd = lower
                        for p in WAKE_PHRASES:
                            cmd = cmd.replace(p, "").strip(" ,.")

                        if cmd:
                            self.wake_command.emit(cmd)
                        else:
                            # Listen for the follow-up
                            follow = self._listen_followup(r)
                            if follow:
                                self.wake_command.emit(follow)
                            else:
                                self.wake_command.emit("")   # just open, no command

            except self._sr.WaitTimeoutError:
                continue
            except Exception as e:
                if self._running:
                    print(f"[Mic] error: {e}")
                    time.sleep(0.5)

    def _listen_followup(self, r) -> str:
        """Listen up to 6s for the command after wake word."""
        try:
            with self._mic as source:
                audio = r.listen(source, timeout=2, phrase_time_limit=8)
            return self._transcribe(r, audio)
        except Exception:
            return ""

    def _transcribe(self, r, audio) -> str:
        sr = self._sr
        try:
            return r.recognize_google(audio)
        except sr.UnknownValueError:
            return ""
        except sr.RequestError:
            pass
        try:
            return r.recognize_sphinx(audio)
        except Exception:
            return ""