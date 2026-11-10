"""Safe disposable Tk window for live keyboard tests. No files or network."""
from __future__ import annotations
import tkinter as tk

TITLE = "Playloom Disposable Test Window"


def main() -> None:
    root = tk.Tk()
    root.title(TITLE)
    root.geometry("460x310")
    root.configure(bg="#111827")

    heading = tk.Label(root, text="Playloom · Input Test", font=("Segoe UI", 17, "bold"),
                       fg="#f9fafb", bg="#111827")
    heading.pack(pady=(15, 4))
    help_text = tk.Label(root, text="Select this window after the Playloom prompt.\n"
                         "Each Right arrow press moves the square. F12 stops Playloom.",
                         justify="center", bg="#111827", fg="#d1d5db")
    help_text.pack(pady=(0, 8))
    canvas = tk.Canvas(root, bg="#1f2937", highlightthickness=0, width=400, height=120)
    canvas.pack()
    x = 30
    marker = canvas.create_rectangle(x, 46, x+28, 74, fill="#86efac", outline="")
    count = 0
    status = tk.Label(root, text="Right presses received: 0", fg="#86efac",
                      bg="#111827", font=("Segoe UI", 12))
    status.pack(pady=13)

    def on_right(_event) -> None:
        nonlocal x, count
        count += 1
        x = (x + 20) % 370
        canvas.coords(marker, x, 46, x+28, 74)
        status.config(text=f"Right presses received: {count}")

    root.bind("<Right>", on_right)
    root.mainloop()


if __name__ == "__main__":
    main()
