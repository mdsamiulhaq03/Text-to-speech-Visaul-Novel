import hashlib
import threading
import pytesseract
import mss
from PIL import Image

# Adjust if Tesseract is installed elsewhere
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

class CaptureState:
    def __init__(self):
        self._last_hash: str = ""

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
    h = hashlib.md5(text.encode()).hexdigest()
    if h == state._last_hash:
        return False
    state._last_hash = h
    return True

def ocr_region(region: dict) -> str:
    with mss.mss() as sct:
        shot = sct.grab(region)
        img = Image.frombytes("RGB", shot.size, shot.rgb)
    return pytesseract.image_to_string(img).strip()

def start_capture_loop(region: dict, state: CaptureState, on_new_line, interval: float = 0.5):
    """
    Runs in a background daemon thread.
    Calls on_new_line(name, text) when text changes.
    """
    import time

    def loop():
        while True:
            try:
                raw = ocr_region(region)
                if has_changed(raw, state):
                    name, text = parse_dialogue(raw)
                    if text:
                        on_new_line(name, text)
            except Exception:
                pass
            time.sleep(interval)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
