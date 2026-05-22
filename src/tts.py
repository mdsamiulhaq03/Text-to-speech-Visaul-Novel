import asyncio
import io
import logging
import threading

import edge_tts
import pyttsx3
import pygame

VOICE_POOL = [
    "en-US-JennyNeural",
    "en-US-GuyNeural",
    "en-GB-SoniaNeural",
    "en-GB-RyanNeural",
    "en-AU-NatashaNeural",
    "en-AU-WilliamNeural",
    "en-IN-NeerjaNeural",
    "en-US-AriaNeural",
]
NARRATOR_VOICE = "en-US-ChristopherNeural"


class VoicePool:
    def __init__(
        self,
        voices: list[str] = VOICE_POOL,
        narrator_voice: str = NARRATOR_VOICE,
        existing: dict[str, str] | None = None,
    ):
        self._voices = voices
        self._narrator_voice = narrator_voice
        self._map: dict[str, str] = dict(existing or {})
        self._index = 0
        self._lock = threading.Lock()

    def get_voice(self, character: str) -> str:
        with self._lock:
            if character == "Narrator":
                return self._narrator_voice
            if character not in self._map:
                self._map[character] = self._voices[self._index % len(self._voices)]
                self._index += 1
            return self._map[character]

    def assignments(self) -> dict[str, str]:
        return dict(self._map)


class TTSEngine:
    def __init__(self, voice_pool: VoicePool, speed: float = 1.0,
                 volumes: dict[str, float] | None = None):
        self._pool = voice_pool
        self._speed = speed
        self._volumes: dict[str, float] = dict(volumes or {})
        self._lock = threading.Lock()
        self._current_channel: pygame.mixer.Channel | None = None
        self._abort_event: threading.Event = threading.Event()
        self._pygame_available = False
        try:
            pygame.mixer.init()
            self._pygame_available = True
        except Exception as e:
            logging.warning("pygame audio unavailable (%s), will use SAPI only", e)

    def speak(self, character: str, text: str):
        self._abort_event.set()
        self._abort_event = threading.Event()
        abort = self._abort_event

        voice = self._pool.get_voice(character)
        rate = self._speed_to_edge_rate(self._speed)
        volume = self._volumes.get(character, 1.0)
        thread = threading.Thread(
            target=self._speak_thread,
            args=(text, voice, rate, volume, abort),
            daemon=True,
        )
        thread.start()

    def stop(self):
        self._abort_event.set()
        with self._lock:
            if self._current_channel:
                self._current_channel.stop()

    def set_speed(self, speed: float):
        self._speed = speed

    def set_volume(self, character: str, volume: float):
        self._volumes[character] = max(0.0, min(2.0, volume))

    def get_volumes(self) -> dict[str, float]:
        return dict(self._volumes)

    def _speak_thread(self, text: str, voice: str, rate: str,
                      volume: float, abort: threading.Event):
        if abort.is_set():
            return
        try:
            audio = asyncio.run(self._fetch_edge_audio(text, voice, rate))
            if abort.is_set():
                return
            if self._pygame_available:
                self._play_audio(audio, volume)
            else:
                self._speak_sapi(text, self._speed, volume)
        except Exception as e:
            logging.warning("Edge TTS failed (%s), falling back to SAPI", e)
            if not abort.is_set():
                self._speak_sapi(text, self._speed, volume)

    @staticmethod
    async def _fetch_edge_audio(text: str, voice: str, rate: str) -> bytes:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)

    def _play_audio(self, audio: bytes, volume: float = 1.0):
        with self._lock:
            sound = pygame.mixer.Sound(io.BytesIO(audio))
            sound.set_volume(min(1.0, max(0.0, volume)))
            self._current_channel = sound.play()

    @staticmethod
    def _speak_sapi(text: str, speed: float = 1.0, volume: float = 1.0):
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", int(200 * speed))
            engine.setProperty("volume", min(1.0, max(0.0, volume)))
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            logging.warning("SAPI fallback also failed: %s", e)

    @staticmethod
    def _speed_to_edge_rate(speed: float) -> str:
        pct = int((speed - 1.0) * 100)
        return f"{pct:+d}%"
