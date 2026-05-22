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


MIN_TEXT_LENGTH = 5   # ignore OCR reads shorter than this (garbage / partial frames)
STABLE_READS    = 2   # text must appear this many times in a row before firing


def auto_detect_region() -> dict | None:
    """
    Capture the full screen and use Tesseract bounding-box data to find where
    dialogue text appears in the bottom 40% of the screen.
    Returns a region dict or None if nothing is found.
    """
    from pytesseract import Output as TessOutput

    with mss.mss() as sct:
        mon = sct.monitors[1]          # primary monitor
        shot = sct.grab(mon)
        full = Image.frombytes("RGB", shot.size, shot.rgb)

    scr_w, scr_h = full.size
    top_offset = int(scr_h * 0.60)    # only scan bottom 40%
    crop = full.crop((0, top_offset, scr_w, scr_h))
    crop = _preprocess(crop)

    data = pytesseract.image_to_data(crop, output_type=TessOutput.DICT)
    boxes = [
        (data["left"][i],
         data["top"][i] + top_offset,
         data["width"][i],
         data["height"][i])
        for i in range(len(data["text"]))
        if data["text"][i].strip() and int(data["conf"][i]) > 40
    ]

    if not boxes:
        return None

    pad = 30
    min_x = max(0,      min(b[0]        for b in boxes) - pad)
    min_y = max(0,      min(b[1]        for b in boxes) - pad)
    max_x = min(scr_w,  max(b[0] + b[2] for b in boxes) + pad)
    max_y = min(scr_h,  max(b[1] + b[3] for b in boxes) + pad)
    return {"left": min_x, "top": min_y, "width": max_x - min_x, "height": max_y - min_y}


def start_capture_loop(region: dict, state: CaptureState, on_new_line, interval: float = 0.5):
    """
    Background daemon thread. Calls on_new_line(name, text) when new stable text appears.
    - Skips reads shorter than MIN_TEXT_LENGTH (garbage / partial typewriter frames).
    - Detects typewriter effect: growing text updates candidate without resetting stability.
    - Requires STABLE_READS consecutive identical reads before firing.
    """

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

                # Skip garbage / partial typewriter frames
                if len(raw.strip()) < MIN_TEXT_LENGTH:
                    time.sleep(interval)
                    continue

                h = hashlib.md5(_normalize(raw).encode()).hexdigest()

                if h == state._last_hash:
                    pending_hash = ""
                    pending_count = 0
                    time.sleep(interval)
                    continue

                name, text = parse_dialogue(raw)
                if not text:
                    time.sleep(interval)
                    continue

                if h == pending_hash:
                    # Same candidate again — increment stability
                    pending_count += 1
                elif pending_text and text.startswith(pending_text):
                    # Typewriter: text is still growing — update candidate but keep count
                    pending_hash = h
                    pending_name = name
                    pending_text = text
                else:
                    # Genuinely new text — reset
                    pending_hash  = h
                    pending_name  = name
                    pending_text  = text
                    pending_count = 1

                if pending_count >= STABLE_READS:
                    state._last_hash = pending_hash
                    confirmed_name, confirmed_text = pending_name, pending_text
                    pending_hash = ""
                    pending_count = 0
                    if _WIN32 and state.game_hwnd == 0:
                        state.game_hwnd = win32gui.GetForegroundWindow()
                    on_new_line(confirmed_name, confirmed_text)

            except Exception:
                pass
            time.sleep(interval)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
