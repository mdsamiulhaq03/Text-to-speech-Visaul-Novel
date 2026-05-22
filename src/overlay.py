import logging
import threading
import tkinter as tk
from tkinter import font as tkfont
from collections import deque

from PIL import Image, ImageDraw
import pystray

from src.tts import VOICE_POOL, NARRATOR_VOICE

ALL_VOICES = VOICE_POOL + [NARRATOR_VOICE]
HISTORY_MAX = 20

BG      = "#0f0f1a"
BG2     = "#1a1a2e"
ACCENT  = "#7c3aed"
ACCENT2 = "#6d28d9"
ACCENT_LIGHT = "#a78bfa"
TEXT    = "#e2e8f0"
MUTED   = "#64748b"
BORDER  = "#2d2d44"
GREEN   = "#22c55e"
RED     = "#ef4444"


def _make_tray_image() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, 62, 62], fill="#7c3aed")
    bar_heights = [14, 22, 30, 22, 14]
    for i, h in enumerate(bar_heights):
        x = 12 + i * 10
        d.rectangle([x, 32 - h // 2, x + 6, 32 + h // 2], fill="white")
    return img


class OverlayWindow:
    """
    Always-on-top companion window.
    Call update_line(character, text) from any thread.
    Call start() to enter the tkinter main loop (blocks).
    """

    def __init__(self, on_repeat, on_stop, on_speed_change,
                 on_region_change, on_voice_save,
                 speed: float = 1.0,
                 voices: dict | None = None,
                 volumes: dict | None = None):
        self._on_repeat       = on_repeat
        self._on_stop         = on_stop
        self._on_speed_change = on_speed_change
        self._on_region_change = on_region_change
        self._on_voice_save   = on_voice_save
        self._initial_speed   = speed
        self._voices          = dict(voices or {})
        self._volumes         = dict(volumes or {})
        self._history: deque[tuple[str, str]] = deque(maxlen=HISTORY_MAX)
        self._muted           = False
        self._root            = None
        self._tray_icon       = None

    # ── public thread-safe updates ────────────────────────────────────

    def update_line(self, character: str, text: str):
        if self._root:
            self._history.append((character, text))
            self._root.after(0, self._char_var.set, character)
            self._root.after(0, self._text_var.set, text)

    def update_voices(self, voices: dict):
        self._voices = dict(voices)

    def update_volumes(self, volumes: dict):
        self._volumes = dict(volumes)

    def is_muted(self) -> bool:
        return self._muted

    def toggle_mute(self):
        if self._root:
            self._root.after(0, self._do_toggle_mute)

    # ── build UI ──────────────────────────────────────────────────────

    def build(self):
        root = tk.Tk()
        root.title("TTS Companion")
        root.geometry("560x178")
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.95)
        root.wm_attributes("-toolwindow", True)
        root.configure(bg=BG)
        root.resizable(False, False)

        # drag
        root._drag_x = root._drag_y = 0
        root.bind("<ButtonPress-1>",
                  lambda e: setattr(root, "_drag_x", e.x) or setattr(root, "_drag_y", e.y))
        root.bind("<B1-Motion>", lambda e: root.geometry(
            f"+{root.winfo_x()+e.x-root._drag_x}+{root.winfo_y()+e.y-root._drag_y}"
        ))

        # ── top bar ───────────────────────────────────────────────────
        top = tk.Frame(root, bg=BG)
        top.pack(fill=tk.X, padx=10, pady=(8, 2))

        self._char_var = tk.StringVar(value="—")
        tk.Label(top, textvariable=self._char_var,
                 fg=ACCENT_LIGHT, bg=BG,
                 font=tkfont.Font(family="Arial", size=11, weight="bold"),
                 anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

        icon_btn = dict(bg=BORDER, fg=TEXT, relief="flat",
                        font=tkfont.Font(family="Arial", size=8),
                        padx=7, pady=2, cursor="hand2", bd=0,
                        activebackground=ACCENT, activeforeground="white")

        # right-side icon buttons (right-to-left pack order)
        tk.Button(top, text="—",
                  command=self._minimize_to_tray, **icon_btn
                  ).pack(side=tk.RIGHT, padx=(3, 0))
        tk.Button(top, text="📍 Region",
                  command=self._on_region_change, **icon_btn
                  ).pack(side=tk.RIGHT, padx=(3, 0))
        tk.Button(top, text="🎤 Voices",
                  command=self._open_voice_dialog, **icon_btn
                  ).pack(side=tk.RIGHT, padx=(3, 0))
        tk.Button(top, text="📜 History",
                  command=self._open_history_dialog, **icon_btn
                  ).pack(side=tk.RIGHT, padx=(3, 0))
        self._mute_btn = tk.Button(top, text="🔊",
                                   command=self._do_toggle_mute, **icon_btn)
        self._mute_btn.pack(side=tk.RIGHT, padx=(3, 0))

        # ── separator ─────────────────────────────────────────────────
        tk.Frame(root, bg=BORDER, height=1).pack(fill=tk.X, padx=10)

        # ── dialogue text ─────────────────────────────────────────────
        self._text_var = tk.StringVar(value="Waiting for dialogue…")
        tk.Label(root, textvariable=self._text_var,
                 fg=TEXT, bg=BG,
                 font=tkfont.Font(family="Arial", size=10),
                 wraplength=530, justify="left", anchor="nw"
                 ).pack(padx=12, pady=(6, 4), fill=tk.X)

        # ── separator ─────────────────────────────────────────────────
        tk.Frame(root, bg=BORDER, height=1).pack(fill=tk.X, padx=10)

        # ── controls ──────────────────────────────────────────────────
        ctrl = tk.Frame(root, bg=BG)
        ctrl.pack(padx=10, pady=6, fill=tk.X)

        btn = dict(bg=ACCENT, fg="white", relief="flat",
                   font=tkfont.Font(family="Arial", size=9),
                   padx=10, pady=3, cursor="hand2", bd=0,
                   activebackground=ACCENT2, activeforeground="white")

        tk.Button(ctrl, text="⏮ Repeat", command=self._on_repeat, **btn
                  ).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(ctrl, text="■ Stop", command=self._on_stop, **btn
                  ).pack(side=tk.LEFT, padx=(0, 12))

        tk.Label(ctrl, text="Speed", fg=MUTED, bg=BG,
                 font=tkfont.Font(family="Arial", size=8)).pack(side=tk.LEFT)

        self._speed_var = tk.DoubleVar(value=self._initial_speed)
        tk.Scale(ctrl, from_=0.5, to=2.0, resolution=0.1,
                 orient=tk.HORIZONTAL, variable=self._speed_var,
                 command=lambda v: self._on_speed_change(float(v)),
                 bg=BG, fg=TEXT, troughcolor=BORDER,
                 highlightthickness=0, length=110, showvalue=True,
                 activebackground=ACCENT,
                 ).pack(side=tk.LEFT, padx=(4, 0))

        # hotkey hint
        tk.Label(ctrl,
                 text="Ctrl+Alt: R=Repeat  S=Stop  M=Mute",
                 fg=MUTED, bg=BG,
                 font=tkfont.Font(family="Arial", size=7)
                 ).pack(side=tk.RIGHT)

        self._root = root

    # ── mute ──────────────────────────────────────────────────────────

    def _do_toggle_mute(self):
        self._muted = not self._muted
        if self._muted:
            self._mute_btn.config(text="🔇", bg=RED)
            self._on_stop()
        else:
            self._mute_btn.config(text="🔊", bg=BORDER)

    # ── system tray ───────────────────────────────────────────────────

    def _start_tray(self):
        img = _make_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem("Show / Hide", self._tray_toggle, default=True),
            pystray.MenuItem("Quit", self._tray_quit),
        )
        self._tray_icon = pystray.Icon("RenpyTTS", img, "TTS Companion", menu)
        thread = threading.Thread(target=self._tray_icon.run, daemon=True)
        thread.start()

    def _minimize_to_tray(self):
        if self._root:
            self._root.withdraw()

    def _tray_toggle(self, icon=None, item=None):
        if self._root:
            self._root.after(0, self._do_tray_toggle)

    def _do_tray_toggle(self):
        if self._root.winfo_viewable():
            self._root.withdraw()
        else:
            self._root.deiconify()
            self._root.lift()

    def _tray_quit(self, icon=None, item=None):
        if self._tray_icon:
            self._tray_icon.stop()
        if self._root:
            self._root.after(0, self._root.destroy)

    # ── history dialog ────────────────────────────────────────────────

    def _open_history_dialog(self):
        if not self._root:
            return
        dlg = tk.Toplevel(self._root)
        dlg.title("Dialogue History")
        dlg.configure(bg=BG2)
        dlg.geometry("500x380")
        dlg.attributes("-topmost", True)
        dlg.resizable(True, True)

        tk.Label(dlg, text="Recent Dialogue",
                 fg=ACCENT_LIGHT, bg=BG2,
                 font=tkfont.Font(family="Arial", size=10, weight="bold")
                 ).pack(padx=14, pady=(10, 4), anchor="w")
        tk.Frame(dlg, bg=BORDER, height=1).pack(fill=tk.X, padx=14, pady=(0, 6))

        frame = tk.Frame(dlg, bg=BG2)
        frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))

        sb = tk.Scrollbar(frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        txt = tk.Text(frame, bg=BG, fg=TEXT, relief="flat",
                      font=tkfont.Font(family="Arial", size=9),
                      wrap=tk.WORD, yscrollcommand=sb.set,
                      padx=8, pady=6, spacing1=2)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=txt.yview)

        txt.tag_config("char", fg=ACCENT_LIGHT,
                       font=tkfont.Font(family="Arial", size=9, weight="bold"))
        txt.tag_config("line", fg=TEXT)

        if not self._history:
            txt.insert(tk.END, "No dialogue recorded yet.", "line")
        else:
            for char, line in self._history:
                txt.insert(tk.END, f"{char}\n", "char")
                txt.insert(tk.END, f"  {line}\n\n", "line")
            txt.see(tk.END)

        txt.config(state=tk.DISABLED)

    # ── voice / volume dialog ─────────────────────────────────────────

    def _open_voice_dialog(self):
        if not self._root:
            return
        dlg = tk.Toplevel(self._root)
        dlg.title("Voice & Volume Settings")
        dlg.configure(bg=BG2)
        dlg.attributes("-topmost", True)
        dlg.resizable(False, False)
        dlg.grab_set()

        tk.Label(dlg, text="Character Voice & Volume",
                 fg=ACCENT_LIGHT, bg=BG2,
                 font=tkfont.Font(family="Arial", size=10, weight="bold")
                 ).pack(padx=16, pady=(12, 2), anchor="w")
        tk.Label(dlg, text="Volume: 0.5 = quiet  1.0 = normal  2.0 = loud",
                 fg=MUTED, bg=BG2,
                 font=tkfont.Font(family="Arial", size=8)
                 ).pack(padx=16, pady=(0, 6), anchor="w")
        tk.Frame(dlg, bg=BORDER, height=1).pack(fill=tk.X, padx=16, pady=(0, 8))

        scroll_frame = tk.Frame(dlg, bg=BG2)
        scroll_frame.pack(padx=16, fill=tk.BOTH)

        all_chars = list(self._voices.keys())
        if "Narrator" not in all_chars:
            all_chars = ["Narrator"] + all_chars

        voice_vars: dict[str, tk.StringVar] = {}
        vol_vars:   dict[str, tk.DoubleVar] = {}
        small = tkfont.Font(family="Arial", size=8)
        norm  = tkfont.Font(family="Arial", size=9)

        for char in all_chars:
            cur_voice = self._voices.get(
                char, NARRATOR_VOICE if char == "Narrator" else VOICE_POOL[0])
            cur_vol = self._volumes.get(char, 1.0)

            row = tk.Frame(scroll_frame, bg=BG2)
            row.pack(fill=tk.X, pady=3)

            tk.Label(row, text=char, fg=TEXT, bg=BG2,
                     font=norm, width=14, anchor="w").pack(side=tk.LEFT)

            vv = tk.StringVar(value=cur_voice)
            voice_vars[char] = vv
            menu = tk.OptionMenu(row, vv, *ALL_VOICES)
            menu.config(bg=BORDER, fg=TEXT, relief="flat",
                        activebackground=ACCENT, activeforeground="white",
                        font=small, highlightthickness=0, bd=0, padx=6, pady=2)
            menu["menu"].config(bg=BG2, fg=TEXT,
                                activebackground=ACCENT, activeforeground="white")
            menu.pack(side=tk.LEFT, padx=(6, 12))

            tk.Label(row, text="Vol:", fg=MUTED, bg=BG2,
                     font=small).pack(side=tk.LEFT)
            dv = tk.DoubleVar(value=cur_vol)
            vol_vars[char] = dv
            tk.Scale(row, from_=0.0, to=2.0, resolution=0.05,
                     orient=tk.HORIZONTAL, variable=dv,
                     bg=BG2, fg=TEXT, troughcolor=BORDER,
                     highlightthickness=0, length=90, showvalue=True,
                     activebackground=ACCENT, font=small,
                     ).pack(side=tk.LEFT)

        tk.Frame(dlg, bg=BORDER, height=1).pack(fill=tk.X, padx=16, pady=(10, 6))

        def save():
            updated_voices  = {c: v.get() for c, v in voice_vars.items()}
            updated_volumes = {c: round(v.get(), 2) for c, v in vol_vars.items()}
            self._voices  = updated_voices
            self._volumes = updated_volumes
            self._on_voice_save(updated_voices, updated_volumes)
            dlg.destroy()

        tk.Button(dlg, text="Save", command=save,
                  bg=ACCENT, fg="white", relief="flat",
                  padx=20, pady=4, cursor="hand2",
                  activebackground=ACCENT2,
                  font=tkfont.Font(family="Arial", size=9)
                  ).pack(pady=(0, 12))

        dlg.update_idletasks()
        dlg.geometry(f"{dlg.winfo_reqwidth()+32}x{dlg.winfo_reqheight()}")

    # ── entry point ───────────────────────────────────────────────────

    def start(self):
        self.build()
        self._start_tray()
        self._root.mainloop()
        if self._tray_icon:
            self._tray_icon.stop()
