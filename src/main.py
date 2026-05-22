import logging
import os

from src.config import Config
from src.capture import CaptureState, start_capture_loop
from src.region_selector import select_region, select_region_toplevel
from src.tts import VoicePool, TTSEngine, VOICE_POOL, NARRATOR_VOICE
from src.overlay import OverlayWindow
from src.script_reader import ScriptDatabase

CONFIG_PATH = "config.json"


def _register_hotkeys(on_repeat, on_stop, on_mute):
    try:
        import keyboard
        keyboard.add_hotkey("ctrl+alt+r", on_repeat)
        keyboard.add_hotkey("ctrl+alt+s", on_stop)
        keyboard.add_hotkey("ctrl+alt+m", on_mute)
    except Exception as e:
        logging.warning("Global hotkeys unavailable (%s)", e)


def main():
    cfg = Config(path=CONFIG_PATH)

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
    tts = TTSEngine(voice_pool=voice_pool, speed=cfg.speed, volumes=cfg.volumes)
    capture_state = CaptureState()
    script_db = ScriptDatabase()

    last_line = {"character": "", "text": ""}

    def apply_new_region(region: dict):
        if not region or region.get("width", 0) < 10:
            return
        cfg.region = region
        capture_state._last_hash = ""
        cfg.save()
        start_capture_loop(cfg.region, capture_state, on_new_line, interval=0.5)

    def on_region_change():
        new_region = select_region_toplevel(overlay._root)
        apply_new_region(new_region)

    def on_voice_save(updated_voices: dict, updated_volumes: dict):
        voice_pool._map.update(updated_voices)
        cfg.voices.update(updated_voices)
        cfg.volumes.update(updated_volumes)
        for char, vol in updated_volumes.items():
            tts.set_volume(char, vol)
        cfg.save()

    def on_game_folder_change(folder: str):
        cfg.game_folder = folder
        cfg.save()
        if not folder:
            return
        overlay.update_script_status()
        script_db.load(folder, on_done=lambda: overlay.update_script_status())

    def on_pos_save(x: int, y: int):
        cfg.window_x = x
        cfg.window_y = y
        cfg.save()

    def on_reset():
        # Wipe config and restart cleanly
        try:
            os.remove(CONFIG_PATH)
        except FileNotFoundError:
            pass
        tts.stop()
        if overlay._tray_icon:
            overlay._tray_icon.stop()
        if overlay._root:
            overlay._root.destroy()
        # Re-run main from scratch
        main()

    overlay = OverlayWindow(
        on_repeat=lambda: tts.speak(last_line["character"], last_line["text"]),
        on_stop=tts.stop,
        on_speed_change=lambda v: (tts.set_speed(v), setattr(cfg, "speed", v), cfg.save()),
        on_region_change=on_region_change,
        on_voice_save=on_voice_save,
        on_game_folder_change=on_game_folder_change,
        on_reset=on_reset,
        speed=cfg.speed,
        voices=cfg.voices,
        volumes=cfg.volumes,
        game_folder=cfg.game_folder,
        script_db=script_db,
        window_x=cfg.window_x,
        window_y=cfg.window_y,
    )
    overlay._on_pos_save = on_pos_save
    overlay.set_region_apply_callback(apply_new_region)

    # Auto-load scripts from saved folder on startup
    if cfg.game_folder:
        script_db.load(cfg.game_folder, on_done=lambda: overlay.update_script_status())

    def on_new_line(character: str, text: str):
        if text == last_line["text"]:
            return

        # Use script database for character name if available
        if script_db.is_loaded:
            resolved = script_db.lookup(text)
            if resolved:
                character = resolved

        last_line["character"] = character
        last_line["text"] = text
        overlay.update_line(character, text)
        # Queue: finish current sentence then speak next
        if not overlay.is_muted():
            tts.speak_queued(character, text)
        cfg.voices.update(voice_pool.assignments())
        overlay.update_voices(cfg.voices)
        cfg.save()

    _register_hotkeys(
        on_repeat=lambda: tts.speak(last_line["character"], last_line["text"]),
        on_stop=tts.stop,
        on_mute=overlay.toggle_mute,
    )

    start_capture_loop(cfg.region, capture_state, on_new_line, interval=0.5)
    overlay.start()


if __name__ == "__main__":
    main()
