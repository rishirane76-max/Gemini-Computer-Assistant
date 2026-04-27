# Gemini Assistant 🤖

# WINDOWS AND LINUX WILL COME LATER.

A native floating AI assistant for macOS — powered by Google Gemini. Works like "Hey Google" on Android but lives on your desktop as a minimal floating bar.

![macOS](https://img.shields.io/badge/macOS-26%2B-blue?logo=apple&logoColor=white)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

| Feature | How to trigger |
|---------|----------------|
| 💬 Ask anything | Type in the bar + Enter |
| 🎤 Voice dictation | Speak while window is open — text fills automatically |
| 👋 Wake word | Say **"Hey Google"** while window is hidden |
| 📅 Calendar | Type `calendar` or click chip |
| ☑️ Reminders | Type `reminder` or click chip |
| 💬 Messages | Type `message` or click chip |
| 📷 Screenshot | Type `screen` or click chip — select area, Gemini analyzes it |
| 👥 Contacts | Type `contacts` |
| 📹 FaceTime | Type `facetime [name]` |
| ⚙️ Settings | Click ⚙️ chip or type `settings` |

---

## Requirements

- Python 3.10+
- A free or paid Google Gemini API key → [Get one here](https://aistudio.google.com/app/apikey)

---

## Installation

### 1. Clone the repo

    git clone https://github.com/rishirane76-max/GeminiAssistant.git
    cd GeminiAssistant

### 2. Install dependencies

**macOS**

    brew install portaudio
    pip install -r requirements.txt
    pip install pyaudio

**Linux**

    sudo apt install portaudio19-dev python3-pyqt6
    pip install -r requirements.txt
    pip install pyaudio

**Windows**

    pip install -r requirements.txt
    pip install pyaudio

### 3. Add your API key

> ⚠️ **Never share your real `.env` file.** It's already ignored by Git.

Create a `.env` file in the project root with your Gemini API key:

**macOS / Linux**

    echo 'GEMINI_API_KEY=your_api_key_here' > .env

**Windows (Command Prompt)**

    echo GEMINI_API_KEY=your_api_key_here > .env

**Windows (PowerShell)**

    "GEMINI_API_KEY=your_api_key_here" | Out-File -FilePath .env -Encoding utf8

> Get your free API key at https://aistudio.google.com/app/apikey

#### Alternative: Using `.env.example`

    cp .env.example .env
    # Then edit .env with your real key

#### Verify your key is set

    # macOS / Linux
    cat .env

    # Windows (PowerShell)
    Get-Content .env

The file should contain exactly: `GEMINI_API_KEY=AIzaSy...`

### 4. Run

    python main.py

---

## Build a standalone app

    pip install pyinstaller

    # macOS / Linux
    pyinstaller --onefile --windowed --name "GeminiAssistant" \
      --add-data "ui:ui" \
      --add-data "core:core" \
      --hidden-import PyQt6 \
      --hidden-import speech_recognition \
      main.py

    # Windows
    pyinstaller --onefile --windowed --name "GeminiAssistant" ^
      --add-data "ui;ui" ^
      --add-data "core;core" ^
      --hidden-import PyQt6 ^
      --hidden-import speech_recognition ^
      main.py

Output is at `dist/GeminiAssistant` (mac/linux) or `dist/GeminiAssistant.exe` (windows).

> After building, create a `.env` file next to the executable with your API key.

---

## Changing your API key

    # macOS / Linux
    echo 'GEMINI_API_KEY=your_new_key_here' > .env

    # Windows (Command Prompt)
    echo GEMINI_API_KEY=your_new_key_here > .env

Or open Settings inside the app (⚙️) and paste the key there.

---

## Changing the model

Open `~/.config/gemini-assistant/settings.json` and change the model field, or run:

    # macOS / Linux
    echo '{"api_key": "your_key", "model": "gemini-2.5-pro"}' > ~/.config/gemini-assistant/settings.json

    # Windows (PowerShell)
    '{"api_key": "your_key", "model": "gemini-2.5-pro"}' | Out-File "$env:USERPROFILE\.config\gemini-assistant\settings.json"

**Available models:**

| Model | Description |
|-------|-------------|
| `gemini-2.5-flash` | Fast, recommended for most use |
| `gemini-2.5-pro` | Smartest, best for complex tasks |
| `gemini-3.1-flash-preview` | Latest preview |
| `gemini-2.0-flash` | Stable fallback |

---

## macOS permissions

On first run macOS will ask for permissions. Allow all of these in **System Settings → Privacy & Security**:

- **Microphone** — voice dictation + wake word
- **Speech Recognition** — converting speech to text
- **Calendar** — reading upcoming events
- **Reminders** — reading your to-do list
- **Contacts** — searching contacts for FaceTime
- **Screen Recording** — screenshot analysis
- **Automation → Messages** — reading iMessages

---

## Project structure

    GeminiAssistant/
    ├── main.py                  # Entry point
    ├── requirements.txt         # Python dependencies
    ├── .env                     # Your API key (never committed)
    ├── .env.example             # Example API key file (commit this)
    ├── .gitignore
    ├── core/
    │   ├── assistant.py         # Gemini API + macOS integrations
    │   └── wake_word.py         # Hey Google wake word + live dictation
    └── ui/
        ├── window.py            # Main floating window (PyQt6)
        └── settings_dialog.py   # Settings dialog

---

## How it works

    You speak / type
          ↓
    SmartListener (wake_word.py)
      ├── Window hidden → detect "Hey Google" → pop up + send command
      └── Window visible → live dictation → fills text bar

    Text input
          ↓
    classify_command() → routes to right handler
      ├── Gemini API (assistant.py) → answer card fades in below bar
      ├── Calendar / Reminders → AppleScript → summarized by Gemini
      ├── iMessages → AppleScript
      ├── Contacts → AppleScript
      └── FaceTime → facetime:// URL scheme

---

## Contributing

PRs welcome. Open an issue first for major changes.

## HELP

If you need help with installation please ask me in the discord server : https://discord.gg/3HfV5cErYX

---

## License

MIT
