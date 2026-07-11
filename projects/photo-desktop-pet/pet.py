from __future__ import annotations

import math
import random
import tkinter as tk
from pathlib import Path
from tkinter import Menu

from PIL import Image, ImageTk


APP_DIR = Path(__file__).resolve().parent
ASSET_PATH = APP_DIR / "assets" / "girl-pet.png"
TRANSPARENT_COLOR = "#ff00ff"


class DesktopPet:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("桌宠")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        self.root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)

        self.original = Image.open(ASSET_PATH).convert("RGBA")
        self.scale_index = 0
        self.scales = [0.22, 0.32, 0.44]
        self.photo: ImageTk.PhotoImage | None = None

        self.drag_start_x = 0
        self.drag_start_y = 0
        self.dragging = False
        self.idle_tick = 0
        self.base_x = 0
        self.base_y = 0
        self.topmost = True

        self.pet_label = tk.Label(
            self.root,
            bd=0,
            highlightthickness=0,
            bg=TRANSPARENT_COLOR,
            cursor="hand2",
        )
        self.pet_label.pack()

        self.bubble = tk.Label(
            self.root,
            text="",
            font=("Microsoft YaHei UI", 10),
            fg="#333333",
            bg="#fff7fb",
            padx=10,
            pady=5,
            bd=0,
        )

        self.menu = Menu(self.root, tearoff=False)
        self.menu.add_command(label="打招呼", command=lambda: self.say_random(force=True))
        self.menu.add_command(label="切换大小", command=self.toggle_size)
        self.menu.add_checkbutton(label="置顶", command=self.toggle_topmost)
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self.root.destroy)
        self.menu.invoke(2)

        self.pet_label.bind("<ButtonPress-1>", self.start_drag)
        self.pet_label.bind("<B1-Motion>", self.drag)
        self.pet_label.bind("<ButtonRelease-1>", self.end_drag)
        self.pet_label.bind("<Double-Button-1>", lambda _event: self.toggle_size())
        self.pet_label.bind("<Button-3>", self.show_menu)

        self.render_pet()
        self.place_initially()
        self.root.after(80, self.idle_animation)
        self.root.after(1000, self.say_random)

    def render_pet(self) -> None:
        scale = self.scales[self.scale_index]
        width = max(120, int(self.original.width * scale))
        height = max(120, int(self.original.height * scale))
        image = self.original.resize((width, height), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(image)
        self.pet_label.configure(image=self.photo)
        self.root.update_idletasks()

    def place_initially(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.base_x = max(20, screen_w - self.root.winfo_reqwidth() - 90)
        self.base_y = max(20, screen_h - self.root.winfo_reqheight() - 120)
        self.root.geometry(f"+{self.base_x}+{self.base_y}")

    def start_drag(self, event: tk.Event) -> None:
        self.dragging = True
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def drag(self, event: tk.Event) -> None:
        x = self.root.winfo_x() + event.x - self.drag_start_x
        y = self.root.winfo_y() + event.y - self.drag_start_y
        self.base_x = x
        self.base_y = y
        self.root.geometry(f"+{x}+{y}")

    def end_drag(self, _event: tk.Event) -> None:
        self.dragging = False

    def show_menu(self, event: tk.Event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def toggle_size(self) -> None:
        self.scale_index = (self.scale_index + 1) % len(self.scales)
        current_x = self.root.winfo_x()
        current_y = self.root.winfo_y()
        self.render_pet()
        self.base_x = current_x
        self.base_y = current_y
        self.root.geometry(f"+{current_x}+{current_y}")

    def toggle_topmost(self) -> None:
        self.topmost = not self.topmost
        self.root.attributes("-topmost", self.topmost)

    def idle_animation(self) -> None:
        if not self.dragging:
            self.idle_tick += 1
            offset_y = int(math.sin(self.idle_tick / 7) * 3)
            offset_x = int(math.sin(self.idle_tick / 31) * 2)
            self.root.geometry(f"+{self.base_x + offset_x}+{self.base_y + offset_y}")
        self.root.after(80, self.idle_animation)

    def say_random(self, force: bool = False) -> None:
        if force or random.random() < 0.45:
            text = random.choice(["今天也要开心呀", "我在这里陪你", "要喝水吗？", "工作辛苦啦"])
            self.bubble.configure(text=text)
            self.bubble.place(relx=0.5, y=8, anchor="n")
            self.root.after(2600, self.bubble.place_forget)
        self.root.after(random.randint(9000, 18000), self.say_random)

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    DesktopPet().run()
