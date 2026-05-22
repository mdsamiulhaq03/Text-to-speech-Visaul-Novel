import json
import os
import threading

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")

class Config:
    def __init__(self, path: str = DEFAULT_CONFIG_PATH):
        self._path = path
        self.region: dict | None = None
        self.voices: dict[str, str] = {}
        self.volumes: dict[str, float] = {}
        self.speed: float = 1.0
        self.game_folder: str = ""
        self.window_x: int = -1
        self.window_y: int = -1
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
            self.volumes = data.get("volumes", {})
            self.speed = data.get("speed", 1.0)
            self.game_folder = data.get("game_folder", "")
            self.window_x = data.get("window_x", -1)
            self.window_y = data.get("window_y", -1)
        except json.JSONDecodeError:
            pass

    def save(self):
        data = {
            "region": self.region,
            "voices": self.voices,
            "volumes": self.volumes,
            "speed": self.speed,
            "game_folder": self.game_folder,
            "window_x": self.window_x,
            "window_y": self.window_y,
        }
        dir_path = os.path.dirname(self._path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        with self._save_lock:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    def set_voice(self, character: str, voice: str):
        self.voices[character] = voice
