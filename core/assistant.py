"""
core/assistant.py — All backend logic: Gemini API, macOS integrations
"""

import subprocess
import base64
import json
import tempfile
import os
import re
import threading
from pathlib import Path

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ── Model list (valid as of April 2026) ────────────────────────────────────────
GEMINI_MODELS = [
    ("gemini-2.5-flash",              "Gemini 2.5 Flash ⚡ (recommended)"),
    ("gemini-2.5-pro",                "Gemini 2.5 Pro 🧠 (smartest)"),
    ("gemini-3.1-flash-preview",      "Gemini 3.1 Flash Preview 🔥 (latest)"),
    ("gemini-3-pro-preview",          "Gemini 3 Pro Preview (powerful)"),
    ("gemini-2.0-flash",              "Gemini 2.0 Flash (fallback)"),
    ("gemini-2.0-flash-lite",         "Gemini 2.0 Flash-Lite (ultra fast)"),
]
DEFAULT_MODEL = "gemini-2.5-flash"

# Settings file
SETTINGS_PATH = Path.home() / ".config" / "gemini-assistant" / "settings.json"


# .env file next to main.py — add one line: GEMINI_API_KEY=AIza...
ENV_PATH = Path(__file__).parent.parent / ".env"

def _key_from_env() -> str:
    """Read GEMINI_API_KEY from a .env file if present."""
    for path in [ENV_PATH, Path.home() / ".env"]:
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if line.startswith("GEMINI_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"\'\' ')
    return ""

def load_settings() -> dict:
    defaults = {"api_key": "", "model": DEFAULT_MODEL}
    if SETTINGS_PATH.exists():
        try:
            data = json.loads(SETTINGS_PATH.read_text())
            if "api_key" in data:
                data["api_key"] = data["api_key"].strip()
            return {**defaults, **data}
        except Exception:
            pass
    # Fall back to .env file
    env_key = _key_from_env()
    if env_key:
        defaults["api_key"] = env_key
    return defaults


def save_settings(settings: dict):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean = dict(settings)
    if "api_key" in clean:
        clean["api_key"] = clean["api_key"].strip()
    SETTINGS_PATH.write_text(json.dumps(clean, indent=2))


# ── Gemini API ─────────────────────────────────────────────────────────────────
def call_gemini(prompt: str, api_key: str, model: str = DEFAULT_MODEL,
                image_data: bytes = None, system_context: str = "") -> str:
    """Synchronous Gemini call. Run in a thread to avoid blocking UI."""
    if not HAS_REQUESTS:
        return "❌ 'requests' package not installed. Run: pip install requests"

    if not api_key:
        return "⚠️ No API key set. Open Settings and paste your Gemini key."

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    )

    parts = []

    if image_data:
        parts.append({
            "inline_data": {
                "mime_type": "image/png",
                "data": base64.b64encode(image_data).decode()
            }
        })

    full_prompt = f"{system_context}\n\nUser: {prompt}" if system_context else prompt
    parts.append({"text": full_prompt})

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1024
        }
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        # Debug: print status to terminal so you can see what's happening
        print(f"[Gemini] HTTP {resp.status_code} | model={model} | key={api_key[:8]}...")
        data = resp.json()

        if "candidates" in data:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        if "error" in data:
            msg = data["error"].get("message", "Unknown error")
            print(f"[Gemini] Error response: {data['error']}")
            return f"❌ Gemini error: {msg}"
        print(f"[Gemini] Unexpected response keys: {list(data.keys())}")
        return "❌ Unexpected response from Gemini."
    except requests.exceptions.Timeout:
        return "❌ Request timed out. Check your internet connection."
    except Exception as e:
        import traceback; traceback.print_exc()
        return f"❌ Error: {e}"


def test_connection(api_key: str, model: str) -> str:
    result = call_gemini("Reply with just: OK", api_key, model)
    if result.strip().upper().startswith("OK") or "OK" in result:
        return "✅ Connected!"
    return f"❌ {result}"


# ── Screenshot ────────────────────────────────────────────────────────────────
def take_screenshot_interactive() -> bytes | None:
    """Uses macOS screencapture with interactive selection. Returns PNG bytes."""
    tmp = tempfile.mktemp(suffix=".png")
    try:
        result = subprocess.run(
            ["screencapture", "-i", "-s", tmp],
            timeout=60
        )
        if result.returncode == 0 and os.path.exists(tmp):
            data = Path(tmp).read_bytes()
            os.unlink(tmp)
            return data
    except Exception:
        pass
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except Exception:
                pass
    return None


# ── AppleScript runner ────────────────────────────────────────────────────────
def run_applescript(script: str) -> str:
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=15
        )
        return result.stdout.strip() or result.stderr.strip() or "No result"
    except subprocess.TimeoutExpired:
        return "AppleScript timed out"
    except FileNotFoundError:
        return "osascript not available (not running on macOS)"
    except Exception as e:
        return f"AppleScript error: {e}"


# ── Calendar ──────────────────────────────────────────────────────────────────
def fetch_calendar_events() -> str:
    script = """
    tell application "Calendar"
        set output to ""
        set theDate to current date
        set endDate to theDate + (7 * days)
        repeat with aCal in calendars
            try
                set theEvents to (every event of aCal whose start date >= theDate and start date <= endDate)
                repeat with e in theEvents
                    set output to output & (summary of e) & " | " & ((start date of e) as string) & "\n"
                end repeat
            end try
        end repeat
        return output
    end tell
    """
    return run_applescript(script)


# ── Reminders ────────────────────────────────────────────────────────────────
def fetch_reminders() -> str:
    script = """
    tell application "Reminders"
        set output to ""
        repeat with aList in lists
            set theReminders to (reminders of aList whose completed is false)
            repeat with r in theReminders
                set output to output & (name of r) & "\n"
            end repeat
        end repeat
        if output is "" then return "No pending reminders"
        return output
    end tell
    """
    return run_applescript(script)


# ── iMessages ────────────────────────────────────────────────────────────────
def fetch_imessages() -> str:
    script = """
    tell application "Messages"
        set output to ""
        set theChats to chats
        repeat with i from 1 to (count of theChats)
            if i > 5 then exit repeat
            set theChat to item i of theChats
            try
                set lastMsg to last message of theChat
                set output to output & (name of theChat) & ": " & (content of lastMsg) & "\n"
            end try
        end repeat
        return output
    end tell
    """
    return run_applescript(script)


# ── Contacts ─────────────────────────────────────────────────────────────────
def search_contacts(name_query: str = "") -> list[dict]:
    script = f"""
    tell application "Contacts"
        set output to ""
        set theContacts to every person whose name contains "{name_query}"
        repeat with c in theContacts
            set cName to name of c
            set cPhone to ""
            set cEmail to ""
            try
                set cPhone to value of phone 1 of c
            end try
            try
                set cEmail to value of email 1 of c
            end try
            set output to output & cName & "|" & cPhone & "|" & cEmail & "\n"
        end repeat
        return output
    end tell
    """
    raw = run_applescript(script)
    contacts = []
    for line in raw.strip().splitlines():
        parts = line.split("|")
        if len(parts) >= 1 and parts[0].strip():
            contacts.append({
                "name": parts[0].strip(),
                "phone": parts[1].strip() if len(parts) > 1 else "",
                "email": parts[2].strip() if len(parts) > 2 else "",
            })
    return contacts


# ── FaceTime ──────────────────────────────────────────────────────────────────
def place_facetime_call(address: str) -> bool:
    try:
        import urllib.parse
        encoded = urllib.parse.quote(address, safe="")
        result = subprocess.run(
            ["open", f"facetime://{encoded}"],
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


# ── Voice (macOS built-in dictation via say/osascript) ────────────────────────
def speak_text(text: str):
    """Use macOS TTS to read a response."""
    # Strip markdown-ish characters for cleaner speech
    clean = re.sub(r"[*_`#]", "", text)
    clean = re.sub(r"\n+", " ", clean).strip()
    subprocess.Popen(["say", clean[:500]])  # cap at 500 chars


# ── Smart command router ──────────────────────────────────────────────────────
CALENDAR_KEYWORDS  = ["calendar", "schedule", "event", "meeting", "appointment"]
REMINDER_KEYWORDS  = ["reminder", "remind", "todo", "to-do", "to do"]
MESSAGE_KEYWORDS   = ["message", "imessage", "text", "chat"]
CONTACT_KEYWORDS   = ["contact", "contacts", "people"]
FACETIME_KEYWORDS  = ["facetime", "video call", "call "]
SCREENSHOT_KEYWORDS = ["screenshot", "screen", "what's on", "what is on"]


def classify_command(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in FACETIME_KEYWORDS):
        return "facetime"
    if any(k in lower for k in CALENDAR_KEYWORDS):
        return "calendar"
    if any(k in lower for k in REMINDER_KEYWORDS):
        return "reminders"
    if any(k in lower for k in MESSAGE_KEYWORDS):
        return "messages"
    if any(k in lower for k in CONTACT_KEYWORDS):
        return "contacts"
    if any(k in lower for k in SCREENSHOT_KEYWORDS):
        return "screenshot"
    return "gemini"
