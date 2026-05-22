import tkinter as tk

def select_region() -> dict:
    """
    Shows a fullscreen semi-transparent overlay.
    User clicks and drags to select the dialogue box region.
    Returns {"top": int, "left": int, "width": int, "height": int}.
    Blocks until the user completes selection.
    """
    result = {}
    start = {}

    root = tk.Tk()
    root.attributes("-fullscreen", True)
    root.attributes("-alpha", 0.35)
    root.attributes("-topmost", True)
    root.config(bg="black")
    root.title("Draw dialogue box region")

    canvas = tk.Canvas(root, bg="black", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    label = tk.Label(
        root,
        text="Click and drag over the dialogue box, then release.",
        fg="white",
        bg="black",
        font=("Arial", 18),
    )
    label.place(relx=0.5, rely=0.05, anchor="center")

    rect_id = None

    def on_press(event):
        start["x"] = event.x
        start["y"] = event.y

    def on_drag(event):
        nonlocal rect_id
        if "x" not in start:
            return
        if rect_id:
            canvas.delete(rect_id)
        try:
            rect_id = canvas.create_rectangle(
                start["x"], start["y"], event.x, event.y,
                outline="#a78bfa", width=3, fill="#7c3aed33"
            )
        except tk.TclError:
            # Fallback if hex-alpha color is not supported
            rect_id = canvas.create_rectangle(
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
