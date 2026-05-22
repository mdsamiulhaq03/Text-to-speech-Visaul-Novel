import tkinter as tk
from tkinter import font as tkfont

class OverlayWindow:
    """
    Always-on-top companion window.
    Call update_line(character, text) from any thread.
    Call start() to enter the tkinter main loop (blocks).
    """

    def __init__(self, on_repeat, on_stop, on_speed_change, speed: float = 1.0):
        self._on_repeat = on_repeat
        self._on_stop = on_stop
        self._on_speed_change = on_speed_change
        self._initial_speed = speed
        self._root = None

    def build(self):
        root = tk.Tk()
        root.title("TTS Companion")
        root.geometry("520x140")
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.92)
        root.wm_attributes("-toolwindow", True)
        root.configure(bg="#1a1a2e")
        root.resizable(False, False)

        # Drag support
        root._drag_x = 0
        root._drag_y = 0
        root.bind("<ButtonPress-1>", lambda e: setattr(root, "_drag_x", e.x) or setattr(root, "_drag_y", e.y))
        root.bind("<B1-Motion>", lambda e: root.geometry(
            f"+{root.winfo_x() + e.x - root._drag_x}+{root.winfo_y() + e.y - root._drag_y}"
        ))

        self._char_var = tk.StringVar(value="—")
        self._text_var = tk.StringVar(value="Waiting for dialogue...")

        char_label = tk.Label(
            root, textvariable=self._char_var,
            fg="#a78bfa", bg="#1a1a2e",
            font=tkfont.Font(family="Arial", size=11, weight="bold"),
            anchor="w"
        )
        char_label.pack(padx=12, pady=(8, 0), fill=tk.X)

        text_label = tk.Label(
            root, textvariable=self._text_var,
            fg="#e2e8f0", bg="#1a1a2e",
            font=tkfont.Font(family="Arial", size=10),
            wraplength=490, justify="left", anchor="w"
        )
        text_label.pack(padx=12, pady=(2, 6), fill=tk.X)

        controls = tk.Frame(root, bg="#1a1a2e")
        controls.pack(padx=12, pady=(0, 8), fill=tk.X)

        btn_style = {"bg": "#7c3aed", "fg": "white", "relief": "flat",
                     "font": tkfont.Font(family="Arial", size=9),
                     "padx": 10, "pady": 3, "cursor": "hand2"}

        tk.Button(controls, text="⏮ Repeat", command=self._on_repeat, **btn_style).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(controls, text="■ Stop", command=self._on_stop, **btn_style).pack(side=tk.LEFT, padx=(0, 12))

        tk.Label(controls, text="Speed:", fg="#94a3b8", bg="#1a1a2e",
                 font=tkfont.Font(family="Arial", size=9)).pack(side=tk.LEFT)

        self._speed_var = tk.DoubleVar(value=self._initial_speed)
        slider = tk.Scale(
            controls, from_=0.5, to=2.0, resolution=0.1,
            orient=tk.HORIZONTAL, variable=self._speed_var,
            command=lambda v: self._on_speed_change(float(v)),
            bg="#1a1a2e", fg="#e2e8f0", troughcolor="#334155",
            highlightthickness=0, length=120, showvalue=True
        )
        slider.pack(side=tk.LEFT, padx=4)

        self._root = root

    def update_line(self, character: str, text: str):
        if self._root:
            self._root.after(0, self._char_var.set, character)
            self._root.after(0, self._text_var.set, text)

    def start(self):
        self.build()
        self._root.mainloop()
