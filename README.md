# Ren'Py TTS Companion

A desktop companion app that reads Ren'Py visual novel game dialogue aloud in real time. It watches the game window using screen capture + OCR, detects new dialogue, and speaks it with natural-sounding neural voices — with a different voice automatically assigned to each character.

## Features

- Reads dialogue and narration aloud as you play any Ren'Py game
- Per-character voice assignment (auto-assigned, persisted across sessions)
- High-quality Microsoft Edge neural voices (online) with Windows SAPI fallback (offline)
- **Ren'Py script reader** — optionally load the game's `.rpy` files for 100% accurate character names (no OCR guessing)
- Always-on-top companion window — doesn't interfere with the game
- **System tray** — minimize to tray, right-click to show/hide or quit
- **Global hotkeys** — control playback even when the game window is focused
- **Dialogue history** — scrollable log of the last 20 lines
- **Per-character volume** — set each character louder or quieter
- **Mute toggle** — silence TTS instantly without closing the app
- **Auto-pause** — pauses OCR when the game window is minimized
- Repeat, Stop, and Speed controls
- Draggable overlay — position it anywhere on screen

## Requirements

- Windows 10/11
- Python 3.10+ (only needed if running from source)
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) — install to the default path: `C:\Program Files\Tesseract-OCR\`

## Quick Start (exe)

1. **Install Tesseract OCR** — download and run the installer from https://github.com/UB-Mannheim/tesseract/wiki. Use the default install path.
2. **Download `RenpyTTS.exe`** from the `dist/` folder or the Releases page.
3. **Double-click `RenpyTTS.exe`** to launch.
4. On first run, a black fullscreen overlay appears — draw a rectangle over your game's dialogue box area (include the character name row at the top).
5. Play your game. The companion window reads each line aloud as it appears.

## Running from Source

```bash
git clone https://github.com/mdsamiulhaq03/Text-to-speech-Visaul-Novel.git
cd "Text-to-speech-Visaul-Novel"
pip install -r requirements.txt
python -m src.main
```

## Buttons

| Button | Action |
|--------|--------|
| **🔊 / 🔇** | Toggle mute (turns red when muted) |
| **📜 History** | View the last 20 spoken lines |
| **🎤 Voices** | Change voices and volume per character |
| **📍 Region** | Re-draw the capture region (no restart needed) |
| **⚙ Settings** | Load game scripts for accurate character names |
| **—** | Minimize to system tray |
| **⏮ Repeat** | Re-read the current line |
| **■ Stop** | Stop playback immediately |
| **Speed slider** | Adjust speech rate (0.5× – 2.0×) |

## Global Hotkeys

These work even when the game window is focused:

| Hotkey | Action |
|--------|--------|
| `Ctrl+Alt+R` | Repeat last line |
| `Ctrl+Alt+S` | Stop playback |
| `Ctrl+Alt+M` | Toggle mute |

## Script-Based Character Names (Recommended)

For accurate character names without relying on OCR:

1. Click **⚙ Settings** in the overlay
2. Click **Browse…** and select your game's `game/` folder (e.g. `C:\Games\MyVN\game\`)
3. Click **Save & Load Scripts**
4. Status shows `✓ X lines loaded` when complete

The app scans all `.rpy` script files, builds a dialogue → character name database, and uses it automatically. OCR still detects *when* text changes — scripts resolve *who* is speaking. Requires `.rpy` source files (not compiled `.rpyc` only).

## Selecting the Capture Region

For best results, draw the region to include **both** the character name and the dialogue text:

```
┌──────────────────────────────┐  ← start here (above character name)
│          CHARACTER           │
│   Dialogue text goes here…   │
└──────────────────────────────┘  ← end here
```

Click **📍 Region** at any time to re-draw it without restarting.

## Voice Assignment

On first encounter of a character name, a voice is automatically picked from a pool of 8 Microsoft Edge neural voices. Click **🎤 Voices** to change any character's voice or volume.

**Available Edge TTS voices:**

| Voice ID | Description |
|----------|-------------|
| `en-US-JennyNeural` | Female, American |
| `en-US-GuyNeural` | Male, American |
| `en-GB-SoniaNeural` | Female, British |
| `en-GB-RyanNeural` | Male, British |
| `en-AU-NatashaNeural` | Female, Australian |
| `en-AU-WilliamNeural` | Male, Australian |
| `en-IN-NeerjaNeural` | Female, Indian |
| `en-US-AriaNeural` | Female, American (expressive) |
| `en-US-ChristopherNeural` | Male, American (narrator default) |

Run `edge-tts --list-voices` to see all available voices.

## Offline Mode

If you have no internet connection, the app automatically falls back to Windows SAPI voices. Quality is lower but it always works offline.

## Config File

Settings are saved to `config.json` next to the exe:

```json
{
  "region": { "left": 100, "top": 800, "width": 1200, "height": 200 },
  "voices": { "Alice": "en-US-JennyNeural", "Bob": "en-GB-RyanNeural" },
  "volumes": { "Alice": 1.0, "Bob": 0.8 },
  "speed": 1.2,
  "game_folder": "C:/Games/MyVN/game"
}
```

Delete `config.json` to reset everything (region, voices, settings).

## Troubleshooting

**"TesseractNotFoundError"**
Tesseract is not installed at the expected path. Install from https://github.com/UB-Mannheim/tesseract/wiki to `C:\Program Files\Tesseract-OCR\`.

**Character name shows "Narrator" instead of the real name**
Your capture region doesn't include the character name row. Click **📍 Region** and re-draw the box higher up to include both the name and dialogue. Or use **⚙ Settings** to load the game's script files.

**OCR reads garbled text**
Re-draw the region more tightly around just the dialogue box. Avoid including the character sprite or background image.

**No audio / silent playback**
Check your system audio. If Edge TTS fails, check your internet connection — the app will fall back to SAPI.

**Companion window goes behind the game**
The window is always-on-top. If it still hides, click the TTS Companion taskbar entry or the tray icon to bring it back.

**Hotkeys not working**
Global hotkeys may require running the app as administrator on some Windows configurations.

## Running Tests

```bash
python -m pytest -v
```
