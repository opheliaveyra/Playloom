"""Tiny save-free visual puzzle for testing mouse input before real games.

No game account, files, networking, or third-party assets are involved.
"""
from __future__ import annotations


TITLE = "Playloom Puzzle Test Window"


def main() -> None:
    import tkinter as tk

    root = tk.Tk()
    root.title(TITLE)
    root.geometry("760x530")
    root.resizable(False, False)
    root.configure(bg="#101624")

    tk.Label(root, text="✦ PLAYLOOM / THE LITTLE LOCKED ROOM",
             font=("Segoe UI", 19, "bold"), fg="#f7e6c0",
             bg="#101624").pack(pady=(18, 3))
    tk.Label(root, text="A tiny point-and-click adventure  ·  no saves  ·  no network",
             font=("Segoe UI", 10), fg="#a3afc2", bg="#101624").pack(pady=(0, 9))

    canvas = tk.Canvas(root, width=712, height=352, bg="#23283c",
                       highlightthickness=1, highlightbackground="#53617a")
    canvas.pack()

    # The room: warm lamp, shelf, rug and the locked doorway.
    canvas.create_rectangle(14, 12, 698, 340, outline="#3e4962", width=2)
    canvas.create_oval(70, 12, 345, 200, fill="#31374a", outline="")
    canvas.create_oval(145, 25, 240, 120, fill="#e2b86c", outline="")
    canvas.create_oval(165, 45, 220, 100, fill="#f6d9a5", outline="")
    canvas.create_rectangle(48, 270, 365, 294, fill="#765b62", outline="")
    canvas.create_rectangle(52, 294, 74, 338, fill="#644550", outline="")
    canvas.create_rectangle(340, 294, 358, 338, fill="#644550", outline="")
    canvas.create_oval(85, 298, 500, 345, fill="#56485e", outline="")

    canvas.create_rectangle(474, 74, 638, 333, fill="#111b30",
                            outline="#bea778", width=5, tags="door")
    canvas.create_rectangle(493, 89, 622, 323, fill="#5b586d",
                            outline="#c7b081", width=3, tags="door")
    canvas.create_oval(589, 205, 604, 220, fill="#efd58a", outline="", tags="door")
    lock = canvas.create_text(558, 153, text="🔒", font=("Segoe UI Emoji", 26),
                              fill="#fff0ce", tags="door")
    canvas.create_text(558, 283, text="THE DOOR", font=("Segoe UI", 14, "bold"),
                       fill="#fff3d3", tags="door")

    canvas.create_text(198, 185, text="An old brass key", font=("Segoe UI", 11),
                       fill="#f9dea6", tags="key")
    canvas.create_oval(159, 205, 184, 230, outline="#edc56f", width=7, tags="key")
    canvas.create_line(183, 218, 271, 218, fill="#edc56f", width=9, tags="key")
    canvas.create_line(251, 218, 251, 233, fill="#edc56f", width=7, tags="key")
    canvas.create_line(268, 218, 268, 234, fill="#edc56f", width=7, tags="key")

    has_key = False
    opened = False
    status = tk.StringVar(value="The door is locked. Something glitters on the table…")
    tk.Label(root, textvariable=status, font=("Segoe UI", 11), fg="#e2e8f0",
             bg="#101624", wraplength=720).pack(pady=(15, 5))
    tk.Label(root, text="Click what you want to inspect. F12 stops Playloom instantly.",
             font=("Segoe UI", 10), fg="#8191ad", bg="#101624").pack()

    def click(event):
        nonlocal has_key, opened
        x, y = event.x, event.y
        if opened:
            return
        if 148 <= x <= 279 and 175 <= y <= 245:
            if not has_key:
                has_key = True
                canvas.delete("key")
                status.set("You picked up the brass key. Perhaps it fits the door.")
            return
        if 472 <= x <= 642 and 70 <= y <= 336:
            if has_key:
                opened = True
                canvas.itemconfigure(lock, text="✦")
                canvas.create_rectangle(492, 89, 622, 323, fill="#647f67",
                                        outline="#d6c092", width=2)
                canvas.create_text(556, 185, text="DOOR OPEN!",
                                   font=("Segoe UI", 16, "bold"), fill="#faffdd")
                status.set("Puzzle solved! The key opened the door. ✨")
            else:
                status.set("The door is locked. You need a key first.")
            return
        status.set("Nothing interesting here. Look around the room.")

    canvas.bind("<Button-1>", click)
    root.mainloop()


if __name__ == "__main__":
    main()
