import hashlib
import re
import threading
import time

import pytesseract
import mss
from PIL import Image, ImageEnhance, ImageFilter

try:
    import win32gui
    _WIN32 = True
except ImportError:
    _WIN32 = False

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


class CaptureState:
    def __init__(self):
        self._last_hash: str = ""
        self.game_hwnd: int = 0  # set on first dialogue detection


def _normalize(text: str) -> str:
    """Strip punctuation/whitespace so 'Hello...' and 'Hello' compare equal."""
    return re.sub(r'[^\w\s]', '', text.lower().strip())


def _preprocess(img: Image.Image) -> Image.Image:
    """Improve OCR accuracy: greyscale → contrast boost → sharpen → 2× upscale."""
    img = img.convert("L")
    img = ImageEnhance.Contrast(img).enhance(2.5)
    img = img.filter(ImageFilter.SHARPEN)
    img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    return img


def _looks_like_name(s: str) -> bool:
    """
    A character name is short, starts with a capital, contains no sentence-ending
    punctuation, and has no lowercase letters that suggest a sentence beginning.
    """
    if not s or len(s) > 32:
        return False
    if s.endswith(('.', '!', '?', ',', '…', '...')):
        return False
    if '"' in s or '“' in s or '”' in s:
        return False
    # Must start with a capital letter
    if not s[0].isupper():
        return False
    # If more than half the alphabetic chars are lowercase and it's long, it's dialogue
    letters = [c for c in s if c.isalpha()]
    if len(letters) > 12 and sum(1 for c in letters if c.islower()) / len(letters) > 0.4:
        return False
    return True


def parse_dialogue(raw: str) -> tuple[str, str]:
    if not raw.strip():
        return "", ""
    lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
    if len(lines) == 1:
        return "Narrator", lines[0]
    if _looks_like_name(lines[0]):
        return lines[0], " ".join(lines[1:])
    return "Narrator", " ".join(lines)


def has_changed(text: str, state: CaptureState) -> bool:
    h = hashlib.md5(_normalize(text).encode()).hexdigest()
    if h == state._last_hash:
        return False
    state._last_hash = h
    return True


def ocr_region(region: dict) -> str:
    with mss.mss() as sct:
        shot = sct.grab(region)
        img = Image.frombytes("RGB", shot.size, shot.rgb)
    img = _preprocess(img)
    return pytesseract.image_to_string(img).strip()


def _game_is_visible(state: CaptureState) -> bool:
    """Return False only when we know the game window is minimized."""
    if not _WIN32 or state.game_hwnd == 0:
        return True
    try:
        return not win32gui.IsIconic(state.game_hwnd)
    except Exception:
        return True


def start_capture_loop(region: dict, state: CaptureState, on_new_line, interval: float = 0.5):
    """
    Runs in a background daemon thread. Calls on_new_line(name, text) on change.
    Requires the same text to appear STABLE_READS consecutive times before firing,
    so OCR jitter during TTS playback cannot interrupt mid-sentence.
    """
    STABLE_READS = 2  # ~1 second at 500ms interval before speech triggers

    def loop():
        pending_hash  = ""
        pending_name  = ""
        pending_text  = ""
        pending_count = 0

        while True:
            try:
                if not _game_is_visible(state):
                    time.sleep(interval)
                    continue

                raw = ocr_region(region)
                h = hashlib.md5(_normalize(raw).encode()).hexdigest()

                if h == state._last_hash:
                    # Still showing confirmed text — reset any pending candidate
                    pending_hash = ""
                    pending_count = 0
                    time.sleep(interval)
                    continue

                # New/different text seen — track stability
                if h == pending_hash:
                    pending_count += 1
                else:
                    # Fresh candidate — start counting from 1
                    name, text = parse_dialogue(raw)
                    pending_hash  = h
                    pending_name  = name
                    pending_text  = text
                    pending_count = 1

                if pending_count >= STABLE_READS and pending_text:
                    # Text has been stable long enough — confirm and fire
                    state._last_hash = pending_hash
                    confirmed_name   = pending_name
                    confirmed_text   = pending_text
                    pending_hash     = ""
                    pending_count    = 0
                    if _WIN32 and state.game_hwnd == 0:
                        state.game_hwnd = win32gui.GetForegroundWindow()
                    on_new_line(confirmed_name, confirmed_text)

            except Exception:
                pass
            time.sleep(interval)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
