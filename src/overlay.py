import logging
import threading
import tkinter as tk
from tkinter import font as tkfont, filedialog
from collections import deque

from PIL import Image, ImageDraw
import pystray

from src.tts import VOICE_POOL, NARRATOR_VOICE, check_online, fetch_available_voices, load_cached_voices

ALL_VOICES   = load_cached_voices()   # populated from cache or built-in pool
HISTORY_MAX  = 20
FONT         = "Segoe UI"   # Modern Windows font, falls back gracefully

# ── colour palette ────────────────────────────────────────────────────────────
BG_HEADER  = "#080810"
BG_MAIN    = "#0d0d18"
BG_CTRL    = "#080810"
BG_DIALOG  = "#10101e"
BORDER     = "#1c1c2e"
ACCENT     = "#7c3aed"
ACCENT_H   = "#9333ea"
ACCENT_L   = "#c084fc"
TEXT       = "#f1f5f9"
SUBTEXT    = "#475569"
MUTED      = "#334155"
DOT_IDLE   = "#2d3748"
DOT_PLAY   = "#22c55e"
DOT_MUTE   = "#ef4444"
RED        = "#ef4444"
GREEN      = "#22c55e"


def _make_tray_image() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    d.ellipse([2, 2, 62, 62], fill="#7c3aed")
    for i, h in enumerate([14, 22, 30, 22, 14]):
        x = 12 + i * 10
        d.rectangle([x, 32 - h // 2, x + 6, 32 + h // 2], fill="white")
    return img


class OverlayWindow:
    """
    Borderless always-on-top companion window.
    Call update_line(character, text) from any thread.
    Call start() to enter the tkinter main loop (blocks).
    """

    def __init__(self, on_repeat, on_stop, on_speed_change,
                 on_region_change, on_voice_save, on_game_folder_change,
                 on_reset,
                 speed: float = 1.0,
                 voices: dict | None = None,
                 volumes: dict | None = None,
                 game_folder: str = "",
                 script_db=None,
                 window_x: int = -1,
                 window_y: int = -1):
        self._on_repeat             = on_repeat
        self._on_stop               = on_stop
        self._on_speed_change       = on_speed_change
        self._on_region_change      = on_region_change
        self._on_voice_save         = on_voice_save
        self._on_game_folder_change = on_game_folder_change
        self._on_reset              = on_reset
        self._speed                 = speed
        self._voices                = dict(voices or {})
        self._volumes               = dict(volumes or {})
        self._game_folder           = game_folder
        self._script_db             = script_db
        self._window_x              = window_x
        self._window_y              = window_y
        self._on_pos_save           = None
        self._history: deque[tuple[str, str]] = deque(maxlen=HISTORY_MAX)
        self._muted                 = False
        self._root                  = None
        self._tray_icon             = None
        self._dot_canvas            = None
        self._dot_id                = None

    # ── thread-safe public API ────────────────────────────────────────────────

    def update_line(self, character: str, text: str):
        if self._root:
            self._history.append((character, text))
            self._root.after(0, self._char_var.set, character)
            self._root.after(0, self._text_var.set, text)
            self._root.after(0, self._set_dot, DOT_PLAY)

    def update_voices(self, voices: dict):
        self._voices = dict(voices)

    def update_volumes(self, volumes: dict):
        self._volumes = dict(volumes)

    def is_muted(self) -> bool:
        return self._muted

    def toggle_mute(self):
        if self._root:
            self._root.after(0, self._do_toggle_mute)

    def set_region_apply_callback(self, cb):
        self._on_region_apply = cb

    # ── build ─────────────────────────────────────────────────────────────────

    def build(self):
        root = tk.Tk()
        root.overrideredirect(True)                   # borderless
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.96)
        root.configure(bg=BORDER)                     # 1-px border colour

        pos = f"+{self._window_x}+{self._window_y}" if self._window_x >= 0 else "+200+200"
        root.geometry(f"580x152{pos}")

        # ── drag on entire window ─────────────────────────────────────────────
        root._dx = root._dy = 0

        def _press(e):
            root._dx, root._dy = e.x, e.y

        def _drag(e):
            root.geometry(f"+{root.winfo_x()+e.x-root._dx}+{root.winfo_y()+e.y-root._dy}")

        def _release(e):
            if self._on_pos_save:
                self._on_pos_save(root.winfo_x(), root.winfo_y())

        root.bind("<ButtonPress-1>",   _press)
        root.bind("<B1-Motion>",       _drag)
        root.bind("<ButtonRelease-1>", _release)

        # ── outer container (provides 1-px border) ────────────────────────────
        outer = tk.Frame(root, bg=BORDER)
        outer.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # ════════════════════════════════════════════════════════════════════════
        # HEADER  ◉  Character Name          [🔊][📜][🎤][📍][⚙] [─]
        # ════════════════════════════════════════════════════════════════════════
        hdr = tk.Frame(outer, bg=BG_HEADER, height=40)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        # Status dot
        self._dot_canvas = tk.Canvas(hdr, width=10, height=10,
                                     bg=BG_HEADER, highlightthickness=0)
        self._dot_id = self._dot_canvas.create_oval(0, 0, 9, 9,
                                                     fill=DOT_IDLE, outline="")
        self._dot_canvas.pack(side=tk.LEFT, padx=(14, 6), pady=15)

        # Character name
        self._char_var = tk.StringVar(value="—")
        tk.Label(hdr, textvariable=self._char_var,
                 fg=ACCENT_L, bg=BG_HEADER,
                 font=(FONT, 11, "bold"), anchor="w"
                 ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Online status badge
        self._net_var = tk.StringVar(value="…")
        self._net_lbl = tk.Label(hdr, textvariable=self._net_var,
                                  fg=SUBTEXT, bg=BG_HEADER,
                                  font=(FONT, 7), padx=6)
        self._net_lbl.pack(side=tk.LEFT, padx=(0, 4))

        # Right-side icon buttons
        def _hbtn(parent, label, cmd, danger=False):
            b = tk.Button(parent, text=label, command=cmd,
                          bg=BG_HEADER, fg=TEXT if not danger else RED,
                          relief="flat", bd=0, padx=8, pady=0,
                          font=(FONT, 9), cursor="hand2",
                          activebackground=BORDER, activeforeground=TEXT)
            b.pack(side=tk.RIGHT)
            return b

        _hbtn(hdr, "─",   self._minimize_to_tray)
        _hbtn(hdr, "⚙",   self._open_settings_dialog)
        _hbtn(hdr, "📍",  self._on_region_change)
        _hbtn(hdr, "🎤",  self._open_voice_dialog)
        _hbtn(hdr, "📜",  self._open_history_dialog)
        self._mute_btn = _hbtn(hdr, "🔊", self._do_toggle_mute)

        # ════════════════════════════════════════════════════════════════════════
        # DIALOGUE TEXT
        # ════════════════════════════════════════════════════════════════════════
        tk.Frame(outer, bg=BORDER, height=1).pack(fill=tk.X)

        content = tk.Frame(outer, bg=BG_MAIN)
        content.pack(fill=tk.X)

        self._text_var = tk.StringVar(value="Waiting for dialogue…")
        tk.Label(content, textvariable=self._text_var,
                 fg=TEXT, bg=BG_MAIN,
                 font=(FONT, 10),
                 wraplength=548, justify="left", anchor="nw",
                 padx=14, pady=10
                 ).pack(fill=tk.X)

        # ════════════════════════════════════════════════════════════════════════
        # CONTROLS  [▶ Repeat] [■ Stop]   Speed  − 1.0× +    ⌨ R/S/M
        # ════════════════════════════════════════════════════════════════════════
        tk.Frame(outer, bg=BORDER, height=1).pack(fill=tk.X)

        ctrl = tk.Frame(outer, bg=BG_CTRL, height=38)
        ctrl.pack(fill=tk.X)
        ctrl.pack_propagate(False)

        def _cbtn(parent, label, cmd, primary=True):
            bg  = ACCENT   if primary else BORDER
            abg = ACCENT_H if primary else "#252535"
            b = tk.Button(parent, text=label, command=cmd,
                          bg=bg, fg=TEXT, relief="flat", bd=0,
                          font=(FONT, 9), cursor="hand2",
                          padx=12, pady=0,
                          activebackground=abg, activeforeground=TEXT)
            b.pack(side=tk.LEFT, padx=(0, 4), pady=6)
            return b

        _cbtn(ctrl, "▶  Repeat", self._on_repeat)
        _cbtn(ctrl, "■  Stop",   self._stop_and_idle, primary=False)

        # divider
        tk.Frame(ctrl, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=8, padx=8)

        # Speed label + − / + buttons
        tk.Label(ctrl, text="Speed", fg=SUBTEXT, bg=BG_CTRL,
                 font=(FONT, 8)).pack(side=tk.LEFT, padx=(0, 6))

        def _spd_btn(txt, delta):
            def cmd():
                self._speed = round(max(0.5, min(2.0, self._speed + delta)), 1)
                self._speed_lbl.config(text=f"{self._speed:.1f}×")
                self._on_speed_change(self._speed)
            b = tk.Button(ctrl, text=txt, command=cmd,
                          bg=MUTED, fg=TEXT, relief="flat", bd=0,
                          font=(FONT, 10, "bold"), cursor="hand2",
                          padx=6, pady=0,
                          activebackground=ACCENT, activeforeground=TEXT)
            b.pack(side=tk.LEFT)

        _spd_btn("−", -0.1)
        self._speed_lbl = tk.Label(ctrl, text=f"{self._speed:.1f}×",
                                   fg=TEXT, bg=BG_CTRL,
                                   font=(FONT, 9, "bold"),
                                   width=5, anchor="center")
        self._speed_lbl.pack(side=tk.LEFT)
        _spd_btn("+", +0.1)

        # hotkey hint
        tk.Label(ctrl, text="Ctrl+Alt:  R  S  M",
                 fg=MUTED, bg=BG_CTRL,
                 font=(FONT, 7)).pack(side=tk.RIGHT, padx=12)

        self._root = root

    # ── internal helpers ──────────────────────────────────────────────────────

    def _set_dot(self, colour: str):
        if self._dot_canvas and self._dot_id:
            self._dot_canvas.itemconfig(self._dot_id, fill=colour)

    def _stop_and_idle(self):
        self._on_stop()
        if self._root:
            self._root.after(0, self._set_dot, DOT_IDLE)

    def _do_toggle_mute(self):
        self._muted = not self._muted
        if self._muted:
            self._mute_btn.config(text="🔇", fg=RED)
            self._set_dot(DOT_MUTE)
            self._on_stop()
        else:
            self._mute_btn.config(text="🔊", fg=TEXT)
            self._set_dot(DOT_IDLE)

    # ── system tray ───────────────────────────────────────────────────────────

    def _start_tray(self):
        img  = _make_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem("Show / Hide", self._tray_toggle, default=True),
            pystray.MenuItem("Quit",        self._tray_quit),
        )
        self._tray_icon = pystray.Icon("RenpyTTS", img, "TTS Companion", menu)
        threading.Thread(target=self._tray_icon.run, daemon=True).start()

    def _minimize_to_tray(self):
        if self._root:
            self._root.withdraw()

    def _tray_toggle(self, *_):
        if self._root:
            self._root.after(0, self._do_tray_toggle)

    def _do_tray_toggle(self):
        if self._root.winfo_viewable():
            self._root.withdraw()
        else:
            self._root.deiconify()
            self._root.lift()

    def _tray_quit(self, *_):
        if self._tray_icon:
            self._tray_icon.stop()
        if self._root:
            self._root.after(0, self._root.destroy)

    # ── history dialog ────────────────────────────────────────────────────────

    def _open_history_dialog(self):
        if not self._root:
            return
        dlg = tk.Toplevel(self._root)
        dlg.title("Dialogue History")
        dlg.configure(bg=BG_DIALOG)
        dlg.geometry("500x380")
        dlg.attributes("-topmost", True)
        dlg.resizable(True, True)

        _dlg_title(dlg, "Recent Dialogue")

        frame = tk.Frame(dlg, bg=BG_DIALOG)
        frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))

        sb  = tk.Scrollbar(frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        txt = tk.Text(frame, bg=BG_MAIN, fg=TEXT, relief="flat",
                      font=(FONT, 9), wrap=tk.WORD,
                      yscrollcommand=sb.set, padx=8, pady=6)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=txt.yview)

        txt.tag_config("char", fg=ACCENT_L, font=(FONT, 9, "bold"))
        txt.tag_config("line", fg=TEXT)

        if not self._history:
            txt.insert(tk.END, "No dialogue recorded yet.", "line")
        else:
            for char, line in self._history:
                txt.insert(tk.END, f"{char}\n", "char")
                txt.insert(tk.END, f"  {line}\n\n", "line")
            txt.see(tk.END)
        txt.config(state=tk.DISABLED)

    # ── voice / volume dialog ─────────────────────────────────────────────────

    def _open_voice_dialog(self):
        if not self._root:
            return
        dlg = tk.Toplevel(self._root)
        dlg.title("Voices & Volume")
        dlg.configure(bg=BG_DIALOG)
        dlg.attributes("-topmost", True)
        dlg.resizable(False, False)
        dlg.grab_set()

        _dlg_title(dlg, "Character Voices & Volume")

        # ── online status + refresh row ───────────────────────────────
        net_row = tk.Frame(dlg, bg=BG_DIALOG)
        net_row.pack(padx=16, pady=(0, 8), fill=tk.X)

        refresh_status = tk.StringVar(value=f"{len(ALL_VOICES)} voices available")
        tk.Label(net_row, textvariable=refresh_status,
                 fg=SUBTEXT, bg=BG_DIALOG,
                 font=(FONT, 8)).pack(side=tk.LEFT)

        # dropdown update helper — rebuilds menus after refresh
        menu_refs: list = []   # filled after dropdown creation

        def on_voices_refreshed(new_voices):
            if not new_voices:
                return
            refresh_status.set(f"✓ {len(new_voices)} voices refreshed")
            for menu_widget, var in menu_refs:
                menu_widget["menu"].delete(0, "end")
                for v in new_voices:
                    menu_widget["menu"].add_command(
                        label=v,
                        command=lambda val=v, sv=var: sv.set(val)
                    )

        def do_refresh():
            self.refresh_voice_list(refresh_status, on_done_ui=on_voices_refreshed)

        tk.Button(net_row, text="🔄 Refresh",
                  command=do_refresh,
                  bg=BORDER, fg=TEXT, relief="flat",
                  font=(FONT, 8), padx=8, cursor="hand2",
                  activebackground=ACCENT, activeforeground=TEXT,
                  ).pack(side=tk.RIGHT)

        tk.Label(dlg, text="Volume  0.5 = quiet · 1.0 = normal · 2.0 = loud",
                 fg=SUBTEXT, bg=BG_DIALOG,
                 font=(FONT, 8)).pack(padx=16, pady=(0, 8), anchor="w")

        scroll_frame = tk.Frame(dlg, bg=BG_DIALOG)
        scroll_frame.pack(padx=16, fill=tk.BOTH)

        all_chars = list(self._voices.keys())
        if "Narrator" not in all_chars:
            all_chars = ["Narrator"] + all_chars

        voice_vars: dict[str, tk.StringVar]  = {}
        vol_vars:   dict[str, tk.DoubleVar]  = {}

        for char in all_chars:
            cur_voice = self._voices.get(char, NARRATOR_VOICE if char == "Narrator" else VOICE_POOL[0])
            cur_vol   = self._volumes.get(char, 1.0)

            row = tk.Frame(scroll_frame, bg=BG_DIALOG)
            row.pack(fill=tk.X, pady=3)

            tk.Label(row, text=char, fg=TEXT, bg=BG_DIALOG,
                     font=(FONT, 9), width=14, anchor="w").pack(side=tk.LEFT)

            vv = tk.StringVar(value=cur_voice)
            voice_vars[char] = vv
            menu = tk.OptionMenu(row, vv, *ALL_VOICES)
            menu.config(bg=BORDER, fg=TEXT, relief="flat",
                        activebackground=ACCENT, activeforeground=TEXT,
                        font=(FONT, 8), highlightthickness=0, bd=0, padx=6)
            menu["menu"].config(bg=BG_MAIN, fg=TEXT,
                                activebackground=ACCENT, activeforeground=TEXT)
            menu.pack(side=tk.LEFT, padx=(6, 14))
            menu_refs.append((menu, vv))

            tk.Label(row, text="Vol:", fg=SUBTEXT, bg=BG_DIALOG,
                     font=(FONT, 8)).pack(side=tk.LEFT)

            dv = tk.DoubleVar(value=cur_vol)
            vol_vars[char] = dv
            tk.Scale(row, from_=0.0, to=2.0, resolution=0.05,
                     orient=tk.HORIZONTAL, variable=dv,
                     bg=BG_DIALOG, fg=TEXT, troughcolor=BORDER,
                     highlightthickness=0, length=90, showvalue=True,
                     activebackground=ACCENT, font=(FONT, 7),
                     ).pack(side=tk.LEFT)

        _dlg_sep(dlg)

        def save():
            self._voices  = {c: v.get() for c, v in voice_vars.items()}
            self._volumes = {c: round(v.get(), 2) for c, v in vol_vars.items()}
            self._on_voice_save(self._voices, self._volumes)
            dlg.destroy()

        _dlg_btn(dlg, "Save", save)
        dlg.update_idletasks()
        dlg.geometry(f"{dlg.winfo_reqwidth()+32}x{dlg.winfo_reqheight()}")

    # ── settings dialog ───────────────────────────────────────────────────────

    def set_script_db(self, db):
        self._script_db = db

    def _open_settings_dialog(self):
        if not self._root:
            return
        dlg = tk.Toplevel(self._root)
        dlg.title("Settings")
        dlg.configure(bg=BG_DIALOG)
        dlg.attributes("-topmost", True)
        dlg.resizable(False, False)
        dlg.grab_set()

        _dlg_title(dlg, "Game Scripts", sub="Point to the game's 'game/' folder for accurate\n"
                                             "character names from .rpy files.")

        folder_row = tk.Frame(dlg, bg=BG_DIALOG)
        folder_row.pack(padx=16, fill=tk.X)

        folder_var = tk.StringVar(value=self._game_folder or "No folder selected")
        tk.Label(folder_row, textvariable=folder_var,
                 fg=TEXT, bg=BG_DIALOG,
                 font=(FONT, 8), width=36, anchor="w"
                 ).pack(side=tk.LEFT)

        def pick_folder():
            p = filedialog.askdirectory(title="Select game/ folder", parent=dlg)
            if p:
                folder_var.set(p)

        tk.Button(folder_row, text="Browse…", command=pick_folder,
                  bg=BORDER, fg=TEXT, relief="flat", font=(FONT, 8),
                  padx=8, cursor="hand2",
                  activebackground=ACCENT, activeforeground=TEXT,
                  ).pack(side=tk.LEFT, padx=(8, 0))

        self._script_status_var = tk.StringVar(value=self._script_status_text())
        tk.Label(dlg, textvariable=self._script_status_var,
                 fg=GREEN if (self._script_db and self._script_db.is_loaded) else SUBTEXT,
                 bg=BG_DIALOG, font=(FONT, 8)
                 ).pack(padx=16, pady=(6, 0), anchor="w")

        _dlg_sep(dlg)

        status_var = tk.StringVar(value="")
        tk.Label(dlg, textvariable=status_var, fg=SUBTEXT,
                 bg=BG_DIALOG, font=(FONT, 8)
                 ).pack(padx=16, anchor="w")

        def auto_detect():
            status_var.set("Switching to game in 3 s, then detecting…")
            dlg.update_idletasks()
            dlg.after(3000, _do_detect)

        def _do_detect():
            from src.capture import auto_detect_region
            region = auto_detect_region()
            if region:
                status_var.set(f"✓ Detected {region['width']}×{region['height']} "
                               f"at ({region['left']},{region['top']})")
                self._on_region_change_with_value(region)
            else:
                status_var.set("Could not detect — try drawing manually.")

        def save_scripts():
            nf = folder_var.get()
            if nf == "No folder selected":
                nf = ""
            dlg.destroy()
            self._game_folder = nf
            self._on_game_folder_change(nf)

        btn_row = tk.Frame(dlg, bg=BG_DIALOG)
        btn_row.pack(pady=(6, 0))
        tk.Button(btn_row, text="🔍 Auto-detect Region",
                  command=auto_detect,
                  bg=BORDER, fg=TEXT, relief="flat",
                  padx=12, pady=4, cursor="hand2",
                  activebackground=ACCENT, activeforeground=TEXT,
                  font=(FONT, 9)).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(btn_row, text="Save & Load Scripts",
                  command=save_scripts,
                  bg=ACCENT, fg=TEXT, relief="flat",
                  padx=12, pady=4, cursor="hand2",
                  activebackground=ACCENT_H,
                  font=(FONT, 9)).pack(side=tk.LEFT)

        # Danger zone
        _dlg_sep(dlg)
        tk.Label(dlg, text="Danger Zone", fg=RED, bg=BG_DIALOG,
                 font=(FONT, 9, "bold")).pack(padx=16, anchor="w")
        tk.Label(dlg, text="Clears all voices, volumes, region, position and settings.",
                 fg=SUBTEXT, bg=BG_DIALOG,
                 font=(FONT, 8)).pack(padx=16, pady=(0, 6), anchor="w")

        def do_reset():
            dlg.destroy()
            self._on_reset()

        tk.Button(dlg, text="🔄 Reset Everything", command=do_reset,
                  bg=RED, fg=TEXT, relief="flat",
                  padx=12, pady=4, cursor="hand2",
                  activebackground="#dc2626",
                  font=(FONT, 9)).pack(pady=(0, 14))

        dlg.update_idletasks()
        dlg.geometry(f"{max(dlg.winfo_reqwidth()+32, 380)}x{dlg.winfo_reqheight()}")

    def _on_region_change_with_value(self, region: dict):
        cb = getattr(self, "_on_region_apply", None)
        if cb and self._root:
            self._root.after(0, lambda: cb(region))

    def _script_status_text(self) -> str:
        db = self._script_db
        if db is None:           return "Scripts: not loaded"
        if db.load_error:        return f"Scripts: error — {db.load_error}"
        if db.is_loaded:         return f"Scripts: ✓ {db.line_count:,} lines loaded"
        return "Scripts: loading…"

    def update_script_status(self):
        if self._root and hasattr(self, "_script_status_var"):
            self._root.after(0, self._script_status_var.set, self._script_status_text())

    # ── connectivity check ────────────────────────────────────────────────────

    def _check_connectivity(self):
        """Run online check in background, update badge, reschedule every 30s."""
        def worker():
            online = check_online()
            if self._root:
                self._root.after(0, self._apply_net_status, online)
        threading.Thread(target=worker, daemon=True).start()

    def _apply_net_status(self, online: bool):
        if not self._root:
            return
        if online:
            self._net_var.set("● EDGE")
            self._net_lbl.config(fg=GREEN)
        else:
            self._net_var.set("● SAPI")
            self._net_lbl.config(fg=RED)
        # Re-check in 30 seconds
        self._root.after(30_000, self._check_connectivity)

    def refresh_voice_list(self, status_var: tk.StringVar = None,
                           on_done_ui=None):
        """Fetch fresh voice list from Edge TTS; update ALL_VOICES global."""
        global ALL_VOICES
        if status_var and self._root:
            self._root.after(0, status_var.set, "Fetching voices…")

        def on_done(voices, error):
            global ALL_VOICES
            if voices:
                ALL_VOICES = voices
                msg = f"✓ {len(voices)} voices loaded"
            else:
                msg = f"Error: {error}"
            if self._root:
                self._root.after(0, status_var.set, msg) if status_var else None
                if on_done_ui:
                    self._root.after(0, on_done_ui, voices or [])

        fetch_available_voices(on_done=on_done)

    # ── entry point ───────────────────────────────────────────────────────────

    def start(self):
        self.build()
        self._start_tray()
        self._check_connectivity()   # initial check + starts 30s loop
        self._root.mainloop()
        if self._tray_icon:
            self._tray_icon.stop()


# ── dialog helpers (DRY) ──────────────────────────────────────────────────────

def _dlg_title(dlg: tk.Toplevel, title: str, sub: str = ""):
    tk.Label(dlg, text=title, fg=ACCENT_L, bg=BG_DIALOG,
             font=(FONT, 10, "bold")).pack(padx=16, pady=(14, 2), anchor="w")
    if sub:
        tk.Label(dlg, text=sub, fg=SUBTEXT, bg=BG_DIALOG,
                 font=(FONT, 8), justify="left"
                 ).pack(padx=16, pady=(0, 8), anchor="w")
    _dlg_sep(dlg)


def _dlg_sep(dlg: tk.Toplevel):
    tk.Frame(dlg, bg=BORDER, height=1).pack(fill=tk.X, padx=16, pady=(6, 8))


def _dlg_btn(dlg: tk.Toplevel, label: str, cmd):
    tk.Button(dlg, text=label, command=cmd,
              bg=ACCENT, fg=TEXT, relief="flat",
              padx=20, pady=4, cursor="hand2",
              activebackground=ACCENT_H,
              font=(FONT, 9)).pack(pady=(0, 14))
