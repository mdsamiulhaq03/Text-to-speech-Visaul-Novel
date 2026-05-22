from src.config import Config
from src.capture import CaptureState, start_capture_loop
from src.region_selector import select_region
from src.tts import VoicePool, TTSEngine, VOICE_POOL, NARRATOR_VOICE
from src.overlay import OverlayWindow

CONFIG_PATH = "config.json"

def main():
    cfg = Config(path=CONFIG_PATH)

    # First-run: ask user to draw the capture region
    if cfg.region is None:
        print("First run: please draw the dialogue box region in the overlay.")
        region = select_region()
        if not region or region.get("width", 0) < 10:
            print("No region selected, exiting.")
            return
        cfg.region = region
        cfg.save()

    voice_pool = VoicePool(
        voices=VOICE_POOL,
        narrator_voice=NARRATOR_VOICE,
        existing=cfg.voices,
    )
    tts = TTSEngine(voice_pool=voice_pool, speed=cfg.speed)
    capture_state = CaptureState()

    last_line = {"character": "", "text": ""}
    overlay = OverlayWindow(
        on_repeat=lambda: tts.speak(last_line["character"], last_line["text"]),
        on_stop=tts.stop,
        on_speed_change=lambda v: (tts.set_speed(v), setattr(cfg, "speed", v), cfg.save()),
    )

    def on_new_line(character: str, text: str):
        last_line["character"] = character
        last_line["text"] = text
        overlay.update_line(character, text)
        tts.stop()
        tts.speak(character, text)
        # Persist any new voice assignments
        cfg.voices.update(voice_pool.assignments())
        cfg.save()

    start_capture_loop(cfg.region, capture_state, on_new_line, interval=0.5)
    overlay.start()

if __name__ == "__main__":
    main()
