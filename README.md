# Ren'Py TTS Companion

A desktop companion app that reads Ren'Py visual novel game dialogue aloud in real time. It watches the game window, detects new dialogue via OCR, and speaks it using natural-sounding neural voices — with a different voice automatically assigned to each character.

## Features

- Reads dialogue and narration aloud as you play any Ren'Py game
- Per-character voice assignment (auto-assigned, persisted across sessions)
- High-quality Microsoft Edge neural voices (online) with Windows SAPI fallback (offline)
- Always-on-top companion window — doesn't interfere with the game
- Repeat, Stop, and Speed controls
- Draggable overlay — position it anywhere on screen

## Requirements

- Windows 10/11
- Python 3.10+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) — install to the default path: `C:\Program Files\Tesseract-OCR\`

## Installation

1. **Install Tesseract OCR**

   Download the installer from https://github.com/UB-Mannheim/tesseract/wiki and run it. Use the default install path.

2. **Clone or download this repository**

   ```
   git clone <repo-url>
   cd "Text to speech vn"
   ```

3. **Install Python dependencies**

   ```
   pip install -r requirements.txt
   ```

## Usage

1. **Launch your Ren'Py game** and get to a screen with dialogue.

2. **Run the companion app**

   ```
   python src/main.py
   ```

3. **First run — draw the capture region**

   A black fullscreen overlay will appear. Click and drag a rectangle over the dialogue box area of your game (the area that shows the character name and dialogue text), then release the mouse.

   The region is saved to `config.json` — you won't need to do this again.

4. **Play the game**

   The companion window appears in the top-left corner. As you advance dialogue, the app detects the new text and reads it aloud. The overlay shows the current character name and line.

## Controls

| Control | Action |
|---------|--------|
| **⏮ Repeat** | Re-read the current line |
| **■ Stop** | Stop playback immediately |
| **Speed slider** | Adjust speech rate (0.5× to 2.0×) |
| **Drag window** | Click and drag anywhere on the companion window to reposition it |

## Voice Assignment

On first encounter of a character name, the app automatically picks a voice from a pool of 8 Microsoft Edge neural voices. Voice assignments are saved to `config.json` and reused in future sessions.

To change a character's voice, edit `config.json`:

```json
{
  "voices": {
    "Alice": "en-US-JennyNeural",
    "Bob": "en-GB-RyanNeural",
    "Narrator": "en-US-ChristopherNeural"
  }
}
```

**Available Edge TTS voices** (requires internet):

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

Full list: run `edge-tts --list-voices` in your terminal.

## Offline Mode

If you have no internet connection, the app automatically falls back to Windows SAPI voices (the same voices used by Windows Narrator). Quality is lower but it always works offline.

## Re-selecting the Capture Region

Delete `config.json` and restart the app to re-draw the capture region.

## Troubleshooting

**"TesseractNotFoundError" on startup**
Tesseract is not installed or not found at the expected path. Install it from https://github.com/UB-Mannheim/tesseract/wiki to `C:\Program Files\Tesseract-OCR\`.

**OCR reads wrong text / garbled output**
Re-draw the capture region more precisely over just the dialogue box area. Avoid including the character sprite or background.

**No audio / silent playback**
Check that your system audio is working. If Edge TTS fails silently, check your internet connection — the app will fall back to SAPI.

**Companion window is behind the game**
The window is set to always-on-top. If it still goes behind, try clicking the companion window once.

## Running Tests

```
python -m pytest -v
```
