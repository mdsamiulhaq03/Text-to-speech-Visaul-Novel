import json
import os
import threading

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")

class Config:
    def __init__(self, path: str = DEFAULT_CONFIG_PATH):
        self._path = path
        self.region: dict | None = None
        self.voices: dict[str, str] = {}
        self.speed: float = 1.0
        self._save_lock = threading.Lock()
        self._load()

    def _load(self):
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.region = data.get("region")
            self.voices = data.get("voices", {})
            self.speed = data.get("speed", 1.0)
        except json.JSONDecodeError:
            # Silently fall back to defaults if JSON is corrupted
            pass

    def save(self):
        data = {"region": self.region, "voices": self.voices, "speed": self.speed}
        dir_path = os.path.dirname(self._path)
        if dir_path:  # Handle edge case where dirname returns empty string
            os.makedirs(dir_path, exist_ok=True)
        with self._save_lock:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    def set_voice(self, character: str, voice: str):
        self.voices[character] = voice
