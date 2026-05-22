from src.config import Config
from src.capture import CaptureState, start_capture_loop
from src.region_selector import select_region, select_region_toplevel
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
    capture_thread_holder = [None]

    last_line = {"character": "", "text": ""}

    def on_region_change():
        # Called on main thread via button — hide overlay, re-select, restart loop
        new_region = select_region_toplevel(overlay._root)
        if not new_region or new_region.get("width", 0) < 10:
            return
        cfg.region = new_region
        cfg.save()
        # Restart the capture loop with the new region
        capture_state._last_hash = ""
        capture_thread_holder[0] = start_capture_loop(
            cfg.region, capture_state, on_new_line, interval=0.5
        )

    def on_voice_save(updated_voices: dict):
        # Update pool map and persist
        voice_pool._map.update(updated_voices)
        cfg.voices.update(updated_voices)
        cfg.save()

    overlay = OverlayWindow(
        on_repeat=lambda: tts.speak(last_line["character"], last_line["text"]),
        on_stop=tts.stop,
        on_speed_change=lambda v: (tts.set_speed(v), setattr(cfg, "speed", v), cfg.save()),
        on_region_change=on_region_change,
        on_voice_save=on_voice_save,
        speed=cfg.speed,
        voices=cfg.voices,
    )

    def on_new_line(character: str, text: str):
        if text == last_line["text"]:
            return
        last_line["character"] = character
        last_line["text"] = text
        overlay.update_line(character, text)
        tts.stop()
        tts.speak(character, text)
        cfg.voices.update(voice_pool.assignments())
        overlay.update_voices(cfg.voices)
        cfg.save()

    capture_thread_holder[0] = start_capture_loop(
        cfg.region, capture_state, on_new_line, interval=0.5
    )
    overlay.start()


if __name__ == "__main__":
    main()
