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

    def get_voice(self, character: str) -> str:
        if character == "Narrator":
            return self._narrator_voice
        if character not in self._map:
            self._map[character] = self._voices[self._index % len(self._voices)]
            self._index += 1
        return self._map[character]

    def assignments(self) -> dict[str, str]:
        return dict(self._map)


class TTSEngine:
    def __init__(self, voice_pool: VoicePool, speed: float = 1.0):
        self._pool = voice_pool
        self._speed = speed
        self._lock = threading.Lock()
        self._current_channel: pygame.mixer.Channel | None = None
        pygame.mixer.init()

    def speak(self, character: str, text: str):
        voice = self._pool.get_voice(character)
        rate = self._speed_to_edge_rate(self._speed)
        thread = threading.Thread(
            target=self._speak_thread, args=(text, voice, rate), daemon=True
        )
        thread.start()

    def stop(self):
        with self._lock:
            if self._current_channel:
                self._current_channel.stop()

    def set_speed(self, speed: float):
        self._speed = speed

    def _speak_thread(self, text: str, voice: str, rate: str):
        try:
            audio = asyncio.run(self._fetch_edge_audio(text, voice, rate))
            self._play_audio(audio)
        except Exception as e:
            logging.warning("Edge TTS failed (%s), falling back to SAPI", e)
            self._speak_sapi(text)

    @staticmethod
    async def _fetch_edge_audio(text: str, voice: str, rate: str) -> bytes:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)

    def _play_audio(self, audio: bytes):
        with self._lock:
            sound = pygame.mixer.Sound(io.BytesIO(audio))
            self._current_channel = sound.play()

    @staticmethod
    def _speak_sapi(text: str):
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()

    @staticmethod
    def _speed_to_edge_rate(speed: float) -> str:
        pct = int((speed - 1.0) * 100)
        return f"{pct:+d}%"
