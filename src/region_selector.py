import tkinter as tk


def select_region() -> dict:
    """Standalone first-run region selector (creates its own Tk root)."""
    root = tk.Tk()
    result = _run_selector(root, is_toplevel=False)
    return result


def select_region_toplevel(parent: tk.Tk) -> dict:
    """
    Region selector that runs inside an existing Tk mainloop.
    Hides the parent window, shows a fullscreen Toplevel, then restores.
    Blocks until selection is complete.
    """
    result = {}
    parent.withdraw()

    top = tk.Toplevel(parent)
    top.attributes("-fullscreen", True)
    top.attributes("-alpha", 0.35)
    top.attributes("-topmost", True)
    top.config(bg="black")
    top.title("Draw dialogue box region")

    canvas = tk.Canvas(top, bg="black", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    tk.Label(
        top,
        text="Click and drag over the dialogue box, then release.",
        fg="white", bg="black", font=("Arial", 18),
    ).place(relx=0.5, rely=0.05, anchor="center")

    start = {}
    rect_id = [None]

    def on_press(event):
        start["x"] = event.x
        start["y"] = event.y

    def on_drag(event):
        if "x" not in start:
            return
        if rect_id[0]:
            canvas.delete(rect_id[0])
        try:
            rect_id[0] = canvas.create_rectangle(
                start["x"], start["y"], event.x, event.y,
                outline="#a78bfa", width=3, fill="#7c3aed33"
            )
        except tk.TclError:
            rect_id[0] = canvas.create_rectangle(
                start["x"], start["y"], event.x, event.y,
                outline="#a78bfa", width=3, fill=""
            )

    def on_release(event):
        x1 = min(start["x"], event.x)
        y1 = min(start["y"], event.y)
        x2 = max(start["x"], event.x)
        y2 = max(start["y"], event.y)
        result["left"] = x1
        result["top"] = y1
        result["width"] = x2 - x1
        result["height"] = y2 - y1
        top.destroy()
        parent.deiconify()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    parent.wait_window(top)
    return result


def _run_selector(root: tk.Tk, is_toplevel: bool) -> dict:
    result = {}
    start = {}

    root.attributes("-fullscreen", True)
    root.attributes("-alpha", 0.35)
    root.attributes("-topmost", True)
    root.config(bg="black")
    root.title("Draw dialogue box region")

    canvas = tk.Canvas(root, bg="black", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    tk.Label(
        root,
        text="Click and drag over the dialogue box, then release.",
        fg="white", bg="black", font=("Arial", 18),
    ).place(relx=0.5, rely=0.05, anchor="center")

    rect_id = [None]

    def on_press(event):
        start["x"] = event.x
        start["y"] = event.y

    def on_drag(event):
        if "x" not in start:
            return
        if rect_id[0]:
            canvas.delete(rect_id[0])
        try:
            rect_id[0] = canvas.create_rectangle(
                start["x"], start["y"], event.x, event.y,
                outline="#a78bfa", width=3, fill="#7c3aed33"
            )
        except tk.TclError:
            rect_id[0] = canvas.create_rectangle(
                start["x"], start["y"], event.x, event.y,
                outline="#a78bfa", width=3, fill=""
            )

    def on_release(event):
        x1 = min(start["x"], event.x)
        y1 = min(start["y"], event.y)
        x2 = max(start["x"], event.x)
        y2 = max(start["y"], event.y)
        result["left"] = x1
        result["top"] = y1
        result["width"] = x2 - x1
        result["height"] = y2 - y1
        root.destroy()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    root.mainloop()
    return result
