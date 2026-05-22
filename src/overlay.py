import tkinter as tk
from tkinter import font as tkfont

from src.tts import VOICE_POOL, NARRATOR_VOICE

ALL_VOICES = VOICE_POOL + [NARRATOR_VOICE]

BG = "#0f0f1a"
BG2 = "#1a1a2e"
ACCENT = "#7c3aed"
ACCENT_LIGHT = "#a78bfa"
TEXT = "#e2e8f0"
MUTED = "#64748b"
BORDER = "#2d2d44"


class OverlayWindow:
    """
    Always-on-top companion window.
    Call update_line(character, text) from any thread.
    Call start() to enter the tkinter main loop (blocks).
    """

    def __init__(self, on_repeat, on_stop, on_speed_change,
                 on_region_change, on_voice_save,
                 speed: float = 1.0, voices: dict = None):
        self._on_repeat = on_repeat
        self._on_stop = on_stop
        self._on_speed_change = on_speed_change
        self._on_region_change = on_region_change
        self._on_voice_save = on_voice_save
        self._initial_speed = speed
        self._voices = dict(voices or {})
        self._root = None

    def build(self):
        root = tk.Tk()
        root.title("TTS Companion")
        root.geometry("540x175")
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.95)
        root.wm_attributes("-toolwindow", True)
        root.configure(bg=BG)
        root.resizable(False, False)

        # ── drag support ──────────────────────────────────────────────
        root._drag_x = 0
        root._drag_y = 0
        root.bind("<ButtonPress-1>",
                  lambda e: setattr(root, "_drag_x", e.x) or setattr(root, "_drag_y", e.y))
        root.bind("<B1-Motion>", lambda e: root.geometry(
            f"+{root.winfo_x() + e.x - root._drag_x}"
            f"+{root.winfo_y() + e.y - root._drag_y}"
        ))

        # ── top bar: character name + settings buttons ────────────────
        top_bar = tk.Frame(root, bg=BG, pady=0)
        top_bar.pack(fill=tk.X, padx=10, pady=(8, 2))

        self._char_var = tk.StringVar(value="—")
        tk.Label(
            top_bar, textvariable=self._char_var,
            fg=ACCENT_LIGHT, bg=BG,
            font=tkfont.Font(family="Arial", size=11, weight="bold"),
            anchor="w"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        icon_style = {
            "bg": BORDER, "fg": TEXT, "relief": "flat",
            "font": tkfont.Font(family="Arial", size=8),
            "padx": 7, "pady": 2, "cursor": "hand2", "bd": 0,
        }
        tk.Button(top_bar, text="—",
                  command=lambda: root.iconify(), **icon_style
                  ).pack(side=tk.RIGHT, padx=(4, 0))
        tk.Button(top_bar, text="📍 Region",
                  command=self._on_region_change, **icon_style
                  ).pack(side=tk.RIGHT, padx=(4, 0))
        tk.Button(top_bar, text="🎤 Voices",
                  command=self._open_voice_dialog, **icon_style
                  ).pack(side=tk.RIGHT, padx=(4, 0))

        # ── separator ─────────────────────────────────────────────────
        tk.Frame(root, bg=BORDER, height=1).pack(fill=tk.X, padx=10)

        # ── dialogue text ─────────────────────────────────────────────
        self._text_var = tk.StringVar(value="Waiting for dialogue…")
        tk.Label(
            root, textvariable=self._text_var,
            fg=TEXT, bg=BG,
            font=tkfont.Font(family="Arial", size=10),
            wraplength=510, justify="left", anchor="nw",
        ).pack(padx=12, pady=(6, 4), fill=tk.X)

        # ── separator ─────────────────────────────────────────────────
        tk.Frame(root, bg=BORDER, height=1).pack(fill=tk.X, padx=10)

        # ── controls bar ──────────────────────────────────────────────
        controls = tk.Frame(root, bg=BG)
        controls.pack(padx=10, pady=6, fill=tk.X)

        btn = {"bg": ACCENT, "fg": "white", "relief": "flat",
               "font": tkfont.Font(family="Arial", size=9),
               "padx": 10, "pady": 3, "cursor": "hand2", "bd": 0,
               "activebackground": "#6d28d9", "activeforeground": "white"}

        tk.Button(controls, text="⏮ Repeat",
                  command=self._on_repeat, **btn).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(controls, text="■ Stop",
                  command=self._on_stop, **btn).pack(side=tk.LEFT, padx=(0, 12))

        tk.Label(controls, text="Speed", fg=MUTED, bg=BG,
                 font=tkfont.Font(family="Arial", size=8)).pack(side=tk.LEFT)

        self._speed_var = tk.DoubleVar(value=self._initial_speed)
        tk.Scale(
            controls, from_=0.5, to=2.0, resolution=0.1,
            orient=tk.HORIZONTAL, variable=self._speed_var,
            command=lambda v: self._on_speed_change(float(v)),
            bg=BG, fg=TEXT, troughcolor=BORDER,
            highlightthickness=0, length=110, showvalue=True,
            activebackground=ACCENT,
        ).pack(side=tk.LEFT, padx=(4, 0))

        self._root = root

    # ── public thread-safe update ─────────────────────────────────────
    def update_line(self, character: str, text: str):
        if self._root:
            self._root.after(0, self._char_var.set, character)
            self._root.after(0, self._text_var.set, text)

    def update_voices(self, voices: dict):
        """Called from main thread after voices change."""
        self._voices = dict(voices)

    # ── voice settings dialog ─────────────────────────────────────────
    def _open_voice_dialog(self):
        if not self._root:
            return
        dlg = tk.Toplevel(self._root)
        dlg.title("Voice Settings")
        dlg.configure(bg=BG2)
        dlg.attributes("-topmost", True)
        dlg.resizable(False, False)
        dlg.grab_set()

        tk.Label(dlg, text="Character Voice Assignments",
                 fg=ACCENT_LIGHT, bg=BG2,
                 font=tkfont.Font(family="Arial", size=10, weight="bold")
                 ).pack(padx=16, pady=(12, 4), anchor="w")
        tk.Frame(dlg, bg=BORDER, height=1).pack(fill=tk.X, padx=16, pady=(0, 8))

        scroll_frame = tk.Frame(dlg, bg=BG2)
        scroll_frame.pack(padx=16, fill=tk.BOTH)

        # Build rows: one per character + Narrator always shown
        all_chars = list(self._voices.keys())
        if "Narrator" not in all_chars:
            all_chars = ["Narrator"] + all_chars

        row_vars: dict[str, tk.StringVar] = {}
        label_w = tkfont.Font(family="Arial", size=9)

        for i, char in enumerate(all_chars):
            current_voice = self._voices.get(char, NARRATOR_VOICE if char == "Narrator" else VOICE_POOL[0])
            row = tk.Frame(scroll_frame, bg=BG2)
            row.pack(fill=tk.X, pady=2)

            tk.Label(row, text=char, fg=TEXT, bg=BG2,
                     font=label_w, width=14, anchor="w"
                     ).pack(side=tk.LEFT)

            var = tk.StringVar(value=current_voice)
            row_vars[char] = var

            menu = tk.OptionMenu(row, var, *ALL_VOICES)
            menu.config(bg=BORDER, fg=TEXT, relief="flat",
                        activebackground=ACCENT, activeforeground="white",
                        font=tkfont.Font(family="Arial", size=8),
                        highlightthickness=0, bd=0, padx=6, pady=2)
            menu["menu"].config(bg=BG2, fg=TEXT,
                                activebackground=ACCENT,
                                activeforeground="white")
            menu.pack(side=tk.LEFT, padx=(8, 0))

        tk.Frame(dlg, bg=BORDER, height=1).pack(fill=tk.X, padx=16, pady=(10, 6))

        def save():
            updated = {char: var.get() for char, var in row_vars.items()}
            self._voices = updated
            self._on_voice_save(updated)
            dlg.destroy()

        tk.Button(dlg, text="Save", command=save,
                  bg=ACCENT, fg="white", relief="flat", padx=20, pady=4,
                  cursor="hand2", activebackground="#6d28d9",
                  font=tkfont.Font(family="Arial", size=9)
                  ).pack(pady=(0, 12))

        # Size dialog to fit content
        dlg.update_idletasks()
        dlg.geometry(f"{dlg.winfo_reqwidth() + 32}x{dlg.winfo_reqheight()}")

    # ── entry point ───────────────────────────────────────────────────
    def start(self):
        self.build()
        self._root.mainloop()
