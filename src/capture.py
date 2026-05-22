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


def parse_dialogue(raw: str) -> tuple[str, str]:
    if not raw.strip():
        return "", ""
    lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
    if len(lines) == 1:
        return "Narrator", lines[0]
    name = lines[0]
    text = " ".join(lines[1:])
    return name, text


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
    """Runs in a background daemon thread. Calls on_new_line(name, text) on change."""

    def loop():
        while True:
            try:
                if not _game_is_visible(state):
                    time.sleep(interval)
                    continue
                raw = ocr_region(region)
                if has_changed(raw, state):
                    name, text = parse_dialogue(raw)
                    if text:
                        if _WIN32 and state.game_hwnd == 0:
                            state.game_hwnd = win32gui.GetForegroundWindow()
                        on_new_line(name, text)
            except Exception:
                pass
            time.sleep(interval)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
