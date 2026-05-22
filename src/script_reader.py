"""
Parses Ren'Py .rpy script files to build a dialogue → character lookup table.
Used as the primary source for character names instead of relying on OCR parsing.
"""

import re
import threading
from pathlib import Path


def _strip_tags(text: str) -> str:
    """Remove Ren'Py text markup: {b}, {color=#fff}, {image=...}, etc."""
    return re.sub(r'\{[^}]*\}', '', text)


def _normalize(text: str) -> str:
    """Normalize text for comparison: strip tags, punctuation, lowercase, collapse spaces."""
    text = _strip_tags(text)
    text = re.sub(r'[^\w\s]', '', text.lower())
    return ' '.join(text.split())


# Ren'Py keywords that can appear before a quoted string but are NOT character vars
_KEYWORDS = {
    'label', 'menu', 'if', 'elif', 'else', 'jump', 'call', 'return', 'pass',
    'scene', 'show', 'hide', 'play', 'stop', 'voice', 'with', 'window', 'nvl',
    'pause', 'python', 'init', 'transform', 'image', 'style', 'define', 'default',
    'screen', 'translate', 'extend', 'queue', 'movie', 'subtitles', 'music',
}


def _collect_characters(text: str, char_map: dict):
    """Extract variable→display-name mappings from Character() definitions."""
    # define e = Character("Eileen") or define e = Character(_("Eileen"), ...)
    pattern = re.compile(
        r'(?:define|default)\s+(\w+)\s*=\s*Character\s*\(\s*(?:_\s*\()?\s*["\']([^"\']{1,50})["\']',
        re.MULTILINE,
    )
    for m in pattern.finditer(text):
        char_map[m.group(1)] = m.group(2)


def _collect_dialogues(text: str, char_map: dict, db: dict):
    """Parse dialogue lines and add normalized_text → character_name to db."""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue

        # ── "CharName" "dialogue" ─────────────────────────────────────
        m = re.match(r'^"([^"]{1,50})"\s+"(.+)"$', line)
        if m and '{' not in m.group(1):
            name, dialogue = m.group(1), m.group(2)
            key = _normalize(dialogue)
            if key:
                db[key] = name
            continue

        # ── var "dialogue"  or  var attr1 attr2 "dialogue" ───────────
        m = re.match(r'^([a-zA-Z_]\w*)(?:\s+[a-zA-Z_]\w*)*\s+"(.+)"$', line)
        if m:
            var, dialogue = m.group(1), m.group(2)
            if var in char_map:
                key = _normalize(dialogue)
                if key:
                    db[key] = char_map[var]
            # don't add narrator lines here — handled next
            continue

        # ── "narrator dialogue" ───────────────────────────────────────
        m = re.match(r'^"(.+)"$', line)
        if m:
            key = _normalize(m.group(1))
            if key and key not in db:
                db[key] = "Narrator"


def _parse_directory(game_dir: str) -> tuple[dict, dict]:
    rpy_files = list(Path(game_dir).rglob("*.rpy"))
    if not rpy_files:
        raise FileNotFoundError(f"No .rpy files found in: {game_dir}")

    char_map: dict[str, str] = {}
    dialogue_db: dict[str, str] = {}

    # First pass: character definitions (needed before dialogue pass)
    for f in rpy_files:
        try:
            _collect_characters(f.read_text(encoding="utf-8", errors="ignore"), char_map)
        except Exception:
            pass

    # Second pass: dialogue lines
    for f in rpy_files:
        try:
            _collect_dialogues(
                f.read_text(encoding="utf-8", errors="ignore"), char_map, dialogue_db
            )
        except Exception:
            pass

    return char_map, dialogue_db


class ScriptDatabase:
    """
    Loads Ren'Py .rpy scripts and provides fast dialogue → character name lookup.
    Use lookup(ocr_text) to get the character name for an OCR'd line.
    Falls back to None if not found (caller should use OCR heuristic instead).
    """

    def __init__(self):
        self._db: dict[str, str] = {}
        self._lock = threading.Lock()
        self.line_count = 0
        self.is_loaded = False
        self.load_error: str = ""

    def load(self, game_dir: str, on_done=None):
        """Load scripts in a background thread. Calls on_done() when complete."""
        self.is_loaded = False
        self.load_error = ""
        t = threading.Thread(target=self._worker, args=(game_dir, on_done), daemon=True)
        t.start()

    def _worker(self, game_dir: str, on_done):
        try:
            _, db = _parse_directory(game_dir)
            with self._lock:
                self._db = db
                self.line_count = len(db)
                self.is_loaded = True
        except Exception as e:
            self.load_error = str(e)
        if on_done:
            on_done()

    def lookup(self, ocr_text: str) -> str | None:
        """
        Return character name for ocr_text, or None if not in database.
        Tries exact normalized match first, then partial containment.
        """
        if not self._db or not ocr_text.strip():
            return None

        key = _normalize(ocr_text)
        if not key or len(key) < 4:
            return None

        with self._lock:
            # 1. Exact match
            if key in self._db:
                return self._db[key]

            # 2. OCR may have cut off trailing words — check if DB has a line
            #    that starts with at least the first 60% of the OCR key
            prefix_len = max(10, int(len(key) * 0.6))
            prefix = key[:prefix_len]
            for db_key, name in self._db.items():
                if db_key.startswith(prefix):
                    return name

        return None
