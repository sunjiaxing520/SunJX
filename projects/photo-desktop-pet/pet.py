from __future__ import annotations

import math
import random
import time
import tkinter as tk
from pathlib import Path
from tkinter import Menu

from PIL import Image, ImageOps, ImageTk


APP_DIR = Path(__file__).resolve().parent
ASSET_PATH = APP_DIR / "assets" / "girl-pet.png"
TRANSPARENT_COLOR = "#ff00ff"
TICK_MS = 50
TOPMOST_REFRESH_MS = 1200


class DesktopPet:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("照片桌宠")
        self.root.overrideredirect(True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        self.root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)

        self.original = Image.open(ASSET_PATH).convert("RGBA")
        self.scale_index = 0
        self.scales = [0.22, 0.32, 0.44]
        self.pose_cache: dict[tuple[int, int, int, int, bool], ImageTk.PhotoImage] = {}
        self.photo: ImageTk.PhotoImage | None = None
        self.base_image = self.original
        self.frame_width = 0
        self.frame_height = 0

        self.base_x = 0
        self.base_y = 0
        self.dragging = False
        self.drag_pointer_x = 0
        self.drag_pointer_y = 0
        self.drag_window_x = 0
        self.drag_window_y = 0

        self.action = "idle"
        self.action_tick = 0
        self.action_duration = 0
        self.action_data: dict[str, float] = {}
        self.idle_tick = 0
        self.next_action_at = time.monotonic() + 2.5

        self.topmost_var = tk.BooleanVar(value=True)
        self.autoplay_var = tk.BooleanVar(value=True)
        self.bubble_hide_job: str | None = None

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
        self.menu.add_command(label="打招呼", command=self.start_greeting)
        self.menu.add_command(label="跳一下", command=self.start_jump)
        self.menu.add_command(label="散步一下", command=self.start_walk)
        self.menu.add_command(label="摇摆一下", command=self.start_sway)
        self.menu.add_separator()
        self.menu.add_command(label="切换大小", command=self.toggle_size)
        self.menu.add_checkbutton(
            label="始终置顶",
            variable=self.topmost_var,
            command=self.apply_topmost,
        )
        self.menu.add_checkbutton(
            label="自动动作",
            variable=self.autoplay_var,
            command=self.on_autoplay_changed,
        )
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self.root.destroy)

        self.bind_pointer_events(self.pet_label)
        self.bind_pointer_events(self.bubble)

        self.render_scale()
        self.place_initially()
        self.apply_topmost()
        self.root.after(TICK_MS, self.animation_loop)
        self.root.after(TOPMOST_REFRESH_MS, self.refresh_topmost)
        self.root.after(7000, self.random_chat)

    def bind_pointer_events(self, widget: tk.Widget) -> None:
        widget.bind("<ButtonPress-1>", self.start_drag)
        widget.bind("<B1-Motion>", self.drag)
        widget.bind("<ButtonRelease-1>", self.end_drag)
        widget.bind("<Double-Button-1>", lambda _event: self.start_jump())
        widget.bind("<Button-3>", self.show_menu)

    def render_scale(self) -> None:
        scale = self.scales[self.scale_index]
        width = max(120, int(self.original.width * scale))
        height = max(120, int(self.original.height * scale))
        self.base_image = self.original.resize((width, height), Image.Resampling.LANCZOS)
        self.frame_width = width + max(16, int(width * 0.08))
        self.frame_height = height + max(16, int(height * 0.06))
        self.pose_cache.clear()
        self.show_pose()
        self.root.update_idletasks()

    def show_pose(
        self,
        width_factor: float = 1.0,
        height_factor: float = 1.0,
        angle: float = 0.0,
        mirrored: bool = False,
    ) -> None:
        width_step = round(width_factor * 200)
        height_step = round(height_factor * 200)
        angle_step = round(angle)
        key = (self.scale_index, width_step, height_step, angle_step, mirrored)
        photo = self.pose_cache.get(key)

        if photo is None:
            pose = self.base_image
            if mirrored:
                pose = ImageOps.mirror(pose)

            pose_width = max(1, round(pose.width * width_step / 200))
            pose_height = max(1, round(pose.height * height_step / 200))
            pose = pose.resize((pose_width, pose_height), Image.Resampling.LANCZOS)

            canvas = Image.new("RGBA", (self.frame_width, self.frame_height), (0, 0, 0, 0))
            paste_x = (self.frame_width - pose_width) // 2
            paste_y = self.frame_height - pose_height
            canvas.alpha_composite(pose, (paste_x, paste_y))

            if angle_step:
                canvas = canvas.rotate(
                    angle_step,
                    resample=Image.Resampling.BICUBIC,
                    center=(self.frame_width // 2, self.frame_height - 1),
                    fillcolor=(0, 0, 0, 0),
                )

            photo = ImageTk.PhotoImage(canvas)
            self.pose_cache[key] = photo

        self.photo = photo
        self.pet_label.configure(image=photo)

    def place_initially(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.base_x = max(20, screen_w - self.root.winfo_reqwidth() - 70)
        self.base_y = max(20, screen_h - self.root.winfo_reqheight() - 80)
        self.move_window(self.base_x, self.base_y)

    def move_window(self, x: float, y: float) -> None:
        self.root.geometry(f"+{round(x)}+{round(y)}")

    def start_drag(self, event: tk.Event) -> None:
        self.dragging = True
        self.cancel_action(keep_current_position=True)
        self.drag_pointer_x = event.x_root
        self.drag_pointer_y = event.y_root
        self.drag_window_x = self.root.winfo_x()
        self.drag_window_y = self.root.winfo_y()
        self.root.configure(cursor="fleur")

    def drag(self, event: tk.Event) -> None:
        x = self.drag_window_x + event.x_root - self.drag_pointer_x
        y = self.drag_window_y + event.y_root - self.drag_pointer_y
        self.base_x = x
        self.base_y = y
        self.move_window(x, y)

    def end_drag(self, _event: tk.Event) -> None:
        self.dragging = False
        self.base_x = self.root.winfo_x()
        self.base_y = self.root.winfo_y()
        self.next_action_at = time.monotonic() + 3.0
        self.root.configure(cursor="")

    def show_menu(self, event: tk.Event) -> None:
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def apply_topmost(self) -> None:
        enabled = bool(self.topmost_var.get())
        self.root.wm_attributes("-topmost", enabled)
        if enabled:
            self.root.lift()
            self.root.after_idle(lambda: self.root.wm_attributes("-topmost", True))

    def refresh_topmost(self) -> None:
        if self.topmost_var.get():
            self.root.wm_attributes("-topmost", True)
            self.root.lift()
        self.root.after(TOPMOST_REFRESH_MS, self.refresh_topmost)

    def on_autoplay_changed(self) -> None:
        if self.autoplay_var.get():
            self.next_action_at = time.monotonic() + 1.5

    def toggle_size(self) -> None:
        old_width = self.root.winfo_width()
        old_height = self.root.winfo_height()
        anchor_x = self.base_x + old_width / 2
        anchor_y = self.base_y + old_height

        self.scale_index = (self.scale_index + 1) % len(self.scales)
        self.render_scale()

        new_width = self.root.winfo_reqwidth()
        new_height = self.root.winfo_reqheight()
        self.base_x = anchor_x - new_width / 2
        self.base_y = anchor_y - new_height
        self.move_window(self.base_x, self.base_y)

    def begin_action(self, name: str, duration: int, **data: float) -> None:
        if self.dragging:
            return
        self.action = name
        self.action_tick = 0
        self.action_duration = max(1, duration)
        self.action_data = data

    def cancel_action(self, keep_current_position: bool = False) -> None:
        if keep_current_position:
            self.base_x = self.root.winfo_x()
            self.base_y = self.root.winfo_y()
        self.action = "idle"
        self.action_tick = 0
        self.action_duration = 0
        self.action_data = {}
        self.show_pose()

    def finish_action(self) -> None:
        self.action = "idle"
        self.action_tick = 0
        self.action_duration = 0
        self.action_data = {}
        self.show_pose()
        self.move_window(self.base_x, self.base_y)
        self.next_action_at = time.monotonic() + random.uniform(5.0, 10.0)

    def start_jump(self) -> None:
        self.begin_action("jump", 18)

    def start_walk(self) -> None:
        if self.dragging:
            return

        screen_w = self.root.winfo_screenwidth()
        pet_w = max(self.root.winfo_width(), self.root.winfo_reqwidth())
        min_x = 10
        max_x = max(min_x, screen_w - pet_w - 10)
        distance = random.randint(130, 280)
        direction = random.choice((-1, 1))

        if direction < 0 and self.base_x - distance < min_x:
            direction = 1
        elif direction > 0 and self.base_x + distance > max_x:
            direction = -1

        target_x = min(max_x, max(min_x, self.base_x + direction * distance))
        actual_distance = target_x - self.base_x
        if abs(actual_distance) < 40:
            target_x = min(max_x, max(min_x, self.base_x - direction * distance))
            actual_distance = target_x - self.base_x

        duration = max(28, round(abs(actual_distance) / 4.5))
        self.begin_action(
            "walk",
            duration,
            start_x=self.base_x,
            target_x=target_x,
            direction=1.0 if actual_distance >= 0 else -1.0,
        )

    def start_greeting(self) -> None:
        self.show_bubble(random.choice(["嗨，我在这里", "今天也要开心呀", "记得喝水哦"]))
        self.begin_action("greet", 28)

    def start_sway(self) -> None:
        self.begin_action("sway", 36)

    def start_random_action(self) -> None:
        random.choices(
            [self.start_walk, self.start_jump, self.start_greeting, self.start_sway],
            weights=[4, 3, 2, 2],
            k=1,
        )[0]()

    def animation_loop(self) -> None:
        if not self.dragging:
            if (
                self.action == "idle"
                and self.autoplay_var.get()
                and time.monotonic() >= self.next_action_at
            ):
                self.start_random_action()

            if self.action == "idle":
                self.animate_idle()
            elif self.action == "jump":
                self.animate_jump()
            elif self.action == "walk":
                self.animate_walk()
            elif self.action == "greet":
                self.animate_greeting()
            elif self.action == "sway":
                self.animate_sway()

        self.root.after(TICK_MS, self.animation_loop)

    def action_progress(self) -> float:
        return min(1.0, self.action_tick / max(1, self.action_duration - 1))

    def advance_action(self) -> None:
        self.action_tick += 1
        if self.action_tick >= self.action_duration:
            self.finish_action()

    def animate_idle(self) -> None:
        self.idle_tick += 1
        phase = self.idle_tick / 10
        offset_x = math.sin(phase / 3.5) * 1.5
        offset_y = math.sin(phase) * 2.5
        breathing = 1.0 + math.sin(phase) * 0.006
        self.show_pose(width_factor=2.0 - breathing, height_factor=breathing)
        self.move_window(self.base_x + offset_x, self.base_y + offset_y)

    def animate_jump(self) -> None:
        progress = self.action_progress()
        jump_height = 72 * 4 * progress * (1 - progress)
        if progress < 0.14 or progress > 0.86:
            self.show_pose(width_factor=1.045, height_factor=0.965)
        else:
            self.show_pose(width_factor=0.975, height_factor=1.035)
        self.move_window(self.base_x, self.base_y - jump_height)
        self.advance_action()

    def animate_walk(self) -> None:
        progress = self.action_progress()
        eased = progress * progress * (3 - 2 * progress)
        start_x = self.action_data["start_x"]
        target_x = self.action_data["target_x"]
        direction = self.action_data["direction"]
        x = start_x + (target_x - start_x) * eased
        steps = max(3, round(abs(target_x - start_x) / 45))
        step_phase = progress * steps * math.tau
        y = self.base_y - abs(math.sin(step_phase)) * 7
        angle = -direction * (2.0 + math.sin(step_phase) * 1.5)
        stride = 1.0 + abs(math.sin(step_phase)) * 0.012
        self.show_pose(
            width_factor=2.0 - stride,
            height_factor=stride,
            angle=angle,
            mirrored=direction < 0,
        )
        self.move_window(x, y)

        if self.action_tick + 1 >= self.action_duration:
            self.base_x = target_x
        self.advance_action()

    def animate_greeting(self) -> None:
        progress = self.action_progress()
        wave = math.sin(progress * math.tau * 3)
        self.show_pose(angle=wave * 3)
        self.move_window(self.base_x + wave * 5, self.base_y - abs(wave) * 3)
        self.advance_action()

    def animate_sway(self) -> None:
        progress = self.action_progress()
        sway = math.sin(progress * math.tau * 2)
        bounce = abs(math.sin(progress * math.tau * 4))
        self.show_pose(angle=sway * 4, height_factor=1.0 + bounce * 0.008)
        self.move_window(self.base_x + sway * 8, self.base_y - bounce * 4)
        self.advance_action()

    def show_bubble(self, text: str, duration: int = 2600) -> None:
        if self.bubble_hide_job is not None:
            self.root.after_cancel(self.bubble_hide_job)
        self.bubble.configure(text=text)
        self.bubble.place(relx=0.5, y=8, anchor="n")
        self.bubble.lift()
        self.bubble_hide_job = self.root.after(duration, self.hide_bubble)

    def hide_bubble(self) -> None:
        self.bubble.place_forget()
        self.bubble_hide_job = None

    def random_chat(self) -> None:
        if random.random() < 0.45:
            self.show_bubble(
                random.choice(["我在这里陪你", "休息一下吧", "今天也辛苦啦", "记得喝水哦"])
            )
        self.root.after(random.randint(10000, 18000), self.random_chat)

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    DesktopPet().run()
