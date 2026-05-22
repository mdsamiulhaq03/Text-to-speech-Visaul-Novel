import json
import os

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")

class Config:
    def __init__(self, path: str = DEFAULT_CONFIG_PATH):
        self._path = path
        self.region: dict | None = None
        self.voices: dict[str, str] = {}
        self.speed: float = 1.0
        self._load()

    def _load(self):
        if not os.path.exists(self._path):
            return
        with open(self._path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.region = data.get("region")
        self.voices = data.get("voices", {})
        self.speed = data.get("speed", 1.0)

    def save(self):
        data = {"region": self.region, "voices": self.voices, "speed": self.speed}
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def set_voice(self, character: str, voice: str):
        self.voices[character] = voice
