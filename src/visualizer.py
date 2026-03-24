#!/usr/bin/env python3

from __future__ import annotations

import random
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tkinter import (
    BOTH,
    END,
    LEFT,
    DISABLED,
    NORMAL,
    RIDGE,
    RIGHT,
    TOP,
    BooleanVar,
    Button,
    Checkbutton,
    Canvas,
    Entry,
    Frame,
    Label,
    OptionMenu,
    Radiobutton,
    Scale,
    StringVar,
    Text,
    Tk,
    X,
)
from tkinter import messagebox


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PUSH_SWAP = (SCRIPT_DIR.parent.parent / "push_swap").resolve()
DEFAULT_CHECKER = (SCRIPT_DIR / "checker_linux").resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.parent.resolve()
VALID_OPS = {"sa", "sb", "ss", "pa", "pb", "ra", "rb", "rr", "rra", "rrb", "rrr"}
NO_STRATEGY = "__none__"
STRATEGIES = [
    ("None", NO_STRATEGY, "Run without a strategy flag"),
    ("Adaptive", "--adaptive", "Default disorder-based selection"),
    ("Simple", "--simple", "Force O(n2)"),
    ("Medium", "--medium", "Force O(nsqrt(n))"),
    ("Complex", "--complex", "Force O(n log n)"),
]
STRATEGY_LABELS = [label for label, _flag, _hint in STRATEGIES if label != "None"]
STRATEGY_FLAGS = {label: flag for label, flag, _hint in STRATEGIES}
STRATEGY_HINTS = {label: hint for label, _flag, hint in STRATEGIES}
BG_APP = "#f2f4f8"
BG_PANEL = "#ffffff"
BG_DARK = "#101820"
BG_ACCENT = "#1f7a8c"
BG_ACCENT_ALT = "#2a9d8f"
FG_TEXT = "#14213d"
FG_MUTED = "#526071"
FG_LIGHT = "#f8f9fb"
MIN_TILE_CHAR_WIDTH = 10
APPROX_CHAR_WIDTH_PX = 9
DEFAULT_GRADIENT_START = "#2ec4b6"
DEFAULT_GRADIENT_END = "#ff6b6b"
GRADIENT_PRESETS: dict[str, tuple[str, str]] = {
    "Turquoise -> Coral": ("#2ec4b6", "#ff6b6b"),
    "Ocean": ("#00b4d8", "#03045e"),
    "Sunset": ("#ffd166", "#ef476f"),
    "Fire": ("#ffe066", "#d00000"),
    "Forest": ("#b7e4c7", "#1b4332"),
    "Ice": ("#caf0f8", "#0077b6"),
    "Lavender": ("#cdb4db", "#6d597a"),
    "Mono": ("#e9ecef", "#212529"),
}


@dataclass
class Snapshot:
    a: list[int]
    b: list[int]
    op: str


def parse_values(raw: str) -> list[int]:
    raw = raw.strip()
    if not raw:
        raise ValueError("Enter at least one integer.")
    values = [int(part) for part in raw.split()]
    if len(values) != len(set(values)):
        raise ValueError("Values must be unique.")
    return values


def op_swap(stack: list[int]) -> None:
    if len(stack) >= 2:
        stack[0], stack[1] = stack[1], stack[0]


def op_push(src: list[int], dst: list[int]) -> None:
    if src:
        dst.insert(0, src.pop(0))


def op_rotate(stack: list[int]) -> None:
    if len(stack) >= 2:
        stack.append(stack.pop(0))


def op_reverse_rotate(stack: list[int]) -> None:
    if len(stack) >= 2:
        stack.insert(0, stack.pop())


def apply_op(a: list[int], b: list[int], op: str) -> None:
    if op == "sa":
        op_swap(a)
    elif op == "sb":
        op_swap(b)
    elif op == "ss":
        op_swap(a)
        op_swap(b)
    elif op == "pa":
        op_push(b, a)
    elif op == "pb":
        op_push(a, b)
    elif op == "ra":
        op_rotate(a)
    elif op == "rb":
        op_rotate(b)
    elif op == "rr":
        op_rotate(a)
        op_rotate(b)
    elif op == "rra":
        op_reverse_rotate(a)
    elif op == "rrb":
        op_reverse_rotate(b)
    elif op == "rrr":
        op_reverse_rotate(a)
        op_reverse_rotate(b)
    else:
        raise ValueError(f"Unknown operation: {op}")


def normalize_hex_color(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise ValueError("Gradient colors cannot be empty.")
    if not value.startswith("#"):
        value = f"#{value}"
    if len(value) != 7 or any(ch not in "0123456789abcdefABCDEF" for ch in value[1:]):
        raise ValueError(f"Invalid hex color: {raw}")
    return value.lower()


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = normalize_hex_color(value)
    return tuple(int(value[idx:idx + 2], 16) for idx in (1, 3, 5))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    red, green, blue = rgb
    return f"#{red:02x}{green:02x}{blue:02x}"


def interpolate_color(start: str, end: str, ratio: float) -> str:
    clamped_ratio = max(0.0, min(1.0, ratio))
    start_rgb = hex_to_rgb(start)
    end_rgb = hex_to_rgb(end)
    mixed = tuple(
        round(start_channel + ((end_channel - start_channel) * clamped_ratio))
        for start_channel, end_channel in zip(start_rgb, end_rgb)
    )
    return rgb_to_hex(mixed)


class PushSwapVisualizer:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Push Swap Visualizer")
        self.root.minsize(1520, 860)
        self.root.configure(bg=BG_APP)
        self._set_initial_geometry()

        self.push_swap_var = StringVar(value=str(DEFAULT_PUSH_SWAP))
        self.checker_var = StringVar(value=str(DEFAULT_CHECKER))
        self.values_var = StringVar(value="2 1 3")
        self.positive_only_var = BooleanVar(value=True)
        self.strategy_var = StringVar(value=NO_STRATEGY)
        self.strategy_enabled_var = BooleanVar(value=False)
        self.strategy_label_var = StringVar(value="Adaptive")
        self.bench_var = BooleanVar(value=False)
        self.status_var = StringVar(value="Ready.")
        self.info_var = StringVar(value="No run loaded.")
        self.speed_var = StringVar(value="20.0")
        self.gradient_preset_var = StringVar(value="Turquoise -> Coral")
        self.gradient_start = DEFAULT_GRADIENT_START
        self.gradient_end = DEFAULT_GRADIENT_END

        self.snapshots: list[Snapshot] = []
        self.ops: list[str] = []
        self.current_index = 0
        self.play_job: str | None = None
        self.value_ranks: dict[int, int] = {}
        self.sorted_values: list[int] = []
        self.settings_visible = True
        self.toggle_settings_var = StringVar(value="Hide Settings")

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._render_current_state()

    def _set_initial_geometry(self) -> None:
        screen_h = self.root.winfo_screenheight()
        width = 1520
        height = max(860, screen_h - 80)
        self.root.geometry(f"{width}x{height}+20+20")

    def _build_ui(self) -> None:
        self.header = Frame(self.root, bg=BG_APP, padx=14, pady=14)
        self.header.pack(side=TOP, fill=X)
        self.header.pack_propagate(False)
        self.header.configure(height=250)
        self.header.grid_columnconfigure(0, weight=1, minsize=920)
        self.header.grid_columnconfigure(1, weight=0, minsize=430)
        self.header.grid_rowconfigure(0, weight=1)

        paths = Frame(self.header, bg=BG_PANEL, padx=14, pady=14, highlightbackground="#d8dee8", highlightthickness=1)
        paths.grid(row=0, column=0, sticky="nsew")
        paths.pack_propagate(False)
        paths.configure(width=920)

        actions = Frame(
            self.header,
            bg=BG_PANEL,
            padx=14,
            pady=14,
            highlightbackground="#d8dee8",
            highlightthickness=1,
            width=430,
        )
        actions.grid(row=0, column=1, sticky="ns", padx=(14, 0))
        actions.pack_propagate(False)

        Label(paths, text="Binary Paths", bg=BG_PANEL, fg=FG_TEXT, font=("Helvetica", 14, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )
        Label(paths, text="push_swap", bg=BG_PANEL, fg=FG_TEXT, font=("Helvetica", 11, "bold")).grid(
            row=1, column=0, sticky="w", pady=4
        )
        Entry(paths, textvariable=self.push_swap_var, width=72, relief="flat", bg="#f8fafc", fg=FG_TEXT).grid(
            row=1, column=1, sticky="we", padx=(10, 0), pady=4, ipady=6
        )

        Label(paths, text="checker", bg=BG_PANEL, fg=FG_TEXT, font=("Helvetica", 11, "bold")).grid(
            row=2, column=0, sticky="w", pady=4
        )
        Entry(paths, textvariable=self.checker_var, width=72, relief="flat", bg="#f8fafc", fg=FG_TEXT).grid(
            row=2, column=1, sticky="we", padx=(10, 0), pady=4, ipady=6
        )

        Label(paths, text="Values", bg=BG_PANEL, fg=FG_TEXT, font=("Helvetica", 14, "bold")).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(14, 10)
        )
        Entry(paths, textvariable=self.values_var, width=72, relief="flat", bg="#f8fafc", fg=FG_TEXT).grid(
            row=4, column=0, columnspan=2, sticky="we", pady=4, ipady=8
        )
        Checkbutton(
            paths,
            text="Positive values only",
            variable=self.positive_only_var,
            onvalue=True,
            offvalue=False,
            bg=BG_PANEL,
            fg=FG_TEXT,
            activebackground=BG_PANEL,
            activeforeground=FG_TEXT,
            selectcolor="#e1f0f4",
            highlightthickness=0,
            font=("Helvetica", 10, "bold"),
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))

        Label(paths, text="Strategy Selector", bg=BG_PANEL, fg=FG_TEXT, font=("Helvetica", 14, "bold")).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(14, 10)
        )
        strategy_frame = Frame(paths, bg=BG_PANEL)
        strategy_frame.grid(row=7, column=0, columnspan=2, sticky="we")
        Checkbutton(
            strategy_frame,
            text="Define strategy",
            variable=self.strategy_enabled_var,
            onvalue=True,
            offvalue=False,
            command=self._on_strategy_toggle,
            bg=BG_PANEL,
            fg=FG_TEXT,
            activebackground=BG_PANEL,
            activeforeground=FG_TEXT,
            selectcolor="#e1f0f4",
            highlightthickness=0,
            font=("Helvetica", 11, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self.strategy_menu = OptionMenu(
            strategy_frame,
            self.strategy_label_var,
            *STRATEGY_LABELS,
            command=self._on_strategy_change,
        )
        self.strategy_menu.configure(
            width=18,
            relief="flat",
            bg="#f8fafc",
            fg=FG_TEXT,
            activebackground="#e1f0f4",
            activeforeground=FG_TEXT,
            highlightthickness=0,
        )
        self.strategy_menu["menu"].configure(bg="#f8fafc", fg=FG_TEXT, activebackground="#e1f0f4")
        self.strategy_menu.grid(row=0, column=1, sticky="w", padx=(16, 0))
        self.strategy_hint_label = Label(
            strategy_frame,
            text="Enable this to pass a strategy flag to push_swap.",
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=("Helvetica", 9),
        )
        self.strategy_hint_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.strategy_detail_label = Label(
            strategy_frame,
            text="",
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=("Helvetica", 9),
        )
        self.strategy_detail_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))
        self._on_strategy_toggle()
        Checkbutton(
            paths,
            text="Enable --bench",
            variable=self.bench_var,
            onvalue=True,
            offvalue=False,
            bg=BG_PANEL,
            fg=FG_TEXT,
            activebackground=BG_PANEL,
            activeforeground=FG_TEXT,
            selectcolor="#e1f0f4",
            highlightthickness=0,
            font=("Helvetica", 11, "bold"),
        ).grid(row=8, column=0, columnspan=2, sticky="w", pady=(12, 0))
        Label(paths, text="Color-Theme", bg=BG_PANEL, fg=FG_TEXT, font=("Helvetica", 14, "bold")).grid(
            row=9, column=0, columnspan=2, sticky="w", pady=(14, 10)
        )
        gradient_frame = Frame(paths, bg=BG_PANEL)
        gradient_frame.grid(row=10, column=0, columnspan=2, sticky="we")
        Label(gradient_frame, text="Preset", bg=BG_PANEL, fg=FG_MUTED, font=("Helvetica", 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        preset_menu = OptionMenu(gradient_frame, self.gradient_preset_var, *GRADIENT_PRESETS.keys())
        preset_menu.configure(
            width=18,
            relief="flat",
            bg="#f8fafc",
            fg=FG_TEXT,
            activebackground="#e1f0f4",
            activeforeground=FG_TEXT,
            highlightthickness=0,
        )
        preset_menu["menu"].configure(bg="#f8fafc", fg=FG_TEXT, activebackground="#e1f0f4")
        preset_menu.grid(row=0, column=1, sticky="w")
        Button(
            gradient_frame,
            text="Apply Theme",
            command=self.use_gradient_preset,
            bg=BG_ACCENT,
            fg=FG_LIGHT,
            activebackground="#16697a",
            activeforeground=FG_LIGHT,
            relief="flat",
            padx=12,
            pady=5,
        ).grid(row=0, column=2, sticky="w", padx=(12, 0))
        Label(
            gradient_frame,
            text="Choose a preset color theme for the stack bars.",
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=("Helvetica", 9),
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))
        paths.grid_columnconfigure(1, weight=1)

        Label(actions, text="Quick Actions", bg=BG_PANEL, fg=FG_TEXT, font=("Helvetica", 14, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10)
        )

        Button(
            actions,
            text="Random 20",
            command=lambda: self.generate_values(20),
            bg=BG_ACCENT,
            fg=FG_LIGHT,
            activebackground="#16697a",
            activeforeground=FG_LIGHT,
            relief="flat",
            padx=14,
            pady=8,
        ).grid(row=1, column=0, padx=4, pady=4, sticky="we")
        Button(
            actions,
            text="Random 100",
            command=lambda: self.generate_values(100),
            bg=BG_ACCENT,
            fg=FG_LIGHT,
            activebackground="#16697a",
            activeforeground=FG_LIGHT,
            relief="flat",
            padx=14,
            pady=8,
        ).grid(row=1, column=1, padx=4, pady=4, sticky="we")
        Button(
            actions,
            text="Random 500",
            command=lambda: self.generate_values(500),
            bg=BG_ACCENT,
            fg=FG_LIGHT,
            activebackground="#16697a",
            activeforeground=FG_LIGHT,
            relief="flat",
            padx=14,
            pady=8,
        ).grid(row=1, column=2, padx=4, pady=4, sticky="we")
        Button(
            actions,
            text="Shuffle",
            command=self.shuffle_values,
            bg=BG_ACCENT_ALT,
            fg=FG_LIGHT,
            activebackground="#20897e",
            activeforeground=FG_LIGHT,
            relief="flat",
            padx=14,
            pady=8,
        ).grid(
            row=2, column=0, padx=4, pady=8, sticky="we"
        )
        Button(
            actions,
            text="make re",
            command=self.rebuild_push_swap,
            bg="#e76f51",
            fg=FG_LIGHT,
            activebackground="#d65f43",
            activeforeground=FG_LIGHT,
            relief="flat",
            padx=14,
            pady=8,
        ).grid(row=2, column=1, padx=4, pady=8, sticky="we")
        Button(
            actions,
            text="Run push_swap",
            command=self.run_push_swap,
            bg="#ffb703",
            fg="#1a1a1a",
            activebackground="#f4a000",
            activeforeground="#1a1a1a",
            relief="flat",
            padx=14,
            pady=8,
        ).grid(row=2, column=2, padx=4, pady=8, sticky="we")
        for col in range(3):
            actions.grid_columnconfigure(col, weight=1, minsize=128)

        status_row = Frame(self.root, padx=14, pady=2, bg=BG_APP)
        status_row.pack(side=TOP, fill=X)
        Label(
            status_row,
            textvariable=self.status_var,
            anchor="w",
            bg=BG_APP,
            fg=FG_MUTED,
            font=("Helvetica", 11),
        ).pack(side=LEFT, fill=X, expand=True)
        Button(
            status_row,
            textvariable=self.toggle_settings_var,
            command=self.toggle_settings,
            relief="flat",
            bg="#e9eef5",
            fg=FG_TEXT,
            activebackground="#d8e2f0",
            activeforeground=FG_TEXT,
            padx=12,
            pady=4,
        ).pack(side=RIGHT, padx=(10, 0))
        Label(
            status_row,
            textvariable=self.info_var,
            anchor="e",
            bg=BG_APP,
            fg=FG_TEXT,
            font=("Helvetica", 11, "bold"),
        ).pack(side=RIGHT)

        self.playback_bar = Frame(self.root, padx=14, pady=8, bg=BG_APP)
        self.playback_bar.pack(side=TOP, fill=X)

        playback_panel = Frame(
            self.playback_bar,
            bg=BG_PANEL,
            padx=14,
            pady=12,
            highlightbackground="#d8dee8",
            highlightthickness=1,
        )
        playback_panel.pack(fill=X)
        playback_panel.grid_columnconfigure(0, weight=0)
        playback_panel.grid_columnconfigure(1, weight=0)
        playback_panel.grid_columnconfigure(2, weight=0)
        playback_panel.grid_columnconfigure(3, weight=1)

        Label(playback_panel, text="Playback", bg=BG_PANEL, fg=FG_TEXT, font=("Helvetica", 14, "bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 18)
        )
        Button(
            playback_panel,
            text="Step -",
            command=self.step_back,
            relief="flat",
            bg="#e9eef5",
            fg=FG_TEXT,
            padx=14,
            pady=8,
        ).grid(row=0, column=1, padx=(0, 8), sticky="w")
        Button(
            playback_panel,
            text="Step +",
            command=self.step_forward,
            relief="flat",
            bg="#e9eef5",
            fg=FG_TEXT,
            padx=14,
            pady=8,
        ).grid(row=0, column=2, padx=(0, 8), sticky="w")
        Button(
            playback_panel,
            text="Play / Pause",
            command=self.toggle_play,
            relief="flat",
            bg="#14213d",
            fg=FG_LIGHT,
            activebackground="#0b162e",
            activeforeground=FG_LIGHT,
            padx=14,
            pady=8,
        ).grid(row=0, column=3, sticky="w")
        Label(playback_panel, text="Delay (ms)", bg=BG_PANEL, fg=FG_MUTED, font=("Helvetica", 11, "bold")).grid(
            row=1, column=0, sticky="w", pady=(12, 0)
        )
        delay_scale = Scale(
            playback_panel,
            from_=1,
            to=1000,
            resolution=1,
            orient="horizontal",
            showvalue=True,
            command=self._on_speed_change,
            bg=BG_PANEL,
            fg=FG_TEXT,
            highlightthickness=0,
            troughcolor="#d6deeb",
            activebackground=BG_ACCENT,
        )
        delay_scale.set(20.0)
        delay_scale.grid(row=1, column=1, columnspan=3, sticky="we", pady=(8, 0))

        main = Frame(self.root, padx=14, pady=14, bg=BG_APP)
        main.pack(fill=BOTH, expand=True)
        main.pack_propagate(False)
        main.grid_columnconfigure(0, weight=1, minsize=980)
        main.grid_columnconfigure(1, weight=0, minsize=380)
        main.grid_rowconfigure(0, weight=1)

        canvas_wrap = Frame(main, bg=BG_APP, width=760)
        canvas_wrap.grid(row=0, column=0, sticky="nsew")
        canvas_wrap.pack_propagate(False)

        self.canvas = Canvas(canvas_wrap, bg=BG_DARK, highlightthickness=0)
        self.canvas.pack(fill=BOTH, expand=True)

        side = Frame(main, width=380, bg=BG_PANEL, highlightbackground="#d8dee8", highlightthickness=1)
        side.grid(row=0, column=1, sticky="nsew")
        side.pack_propagate(False)

        Label(side, text="Operations", bg=BG_PANEL, fg=FG_TEXT, font=("Helvetica", 14, "bold")).pack(
            anchor="w", padx=12, pady=(12, 8)
        )
        self.ops_text = Text(
            side,
            width=34,
            wrap="none",
            relief="flat",
            bg="#fbfcfe",
            fg=FG_TEXT,
            font=("Courier", 16),
            padx=10,
            pady=10,
        )
        self.ops_text.pack(fill=BOTH, expand=True)

    def _on_strategy_change(self, selected_label: str) -> None:
        self.strategy_var.set(STRATEGY_FLAGS.get(selected_label, NO_STRATEGY))
        self.strategy_detail_label.configure(
            text=STRATEGY_HINTS.get(selected_label, ""),
            fg=FG_MUTED,
        )
        if self.strategy_enabled_var.get():
            self.strategy_hint_label.configure(
                text=f"Current flag: {self.strategy_var.get()}",
                fg=BG_ACCENT,
            )

    def _on_strategy_toggle(self) -> None:
        if self.strategy_enabled_var.get():
            self.strategy_menu.configure(state=NORMAL)
            self._on_strategy_change(self.strategy_label_var.get())
        else:
            self.strategy_menu.configure(state=DISABLED)
            self.strategy_var.set(NO_STRATEGY)
            self.strategy_hint_label.configure(
                text="Enable this to pass a strategy flag to push_swap.",
                fg=FG_MUTED,
            )
            self.strategy_detail_label.configure(
                text="Run without a strategy flag.",
                fg=FG_MUTED,
            )

    def toggle_settings(self) -> None:
        self.set_settings_visible(not self.settings_visible)

    def set_settings_visible(self, visible: bool) -> None:
        if self.settings_visible == visible:
            return
        self.settings_visible = visible
        if visible:
            self.header.pack(side=TOP, fill=X, before=self.playback_bar)
            self.toggle_settings_var.set("Hide Settings")
        else:
            self.header.pack_forget()
            self.toggle_settings_var.set("Show Settings")

    def _on_speed_change(self, value: str) -> None:
        self.speed_var.set(f"{float(value):.1f}")

    def generate_values(self, size: int) -> None:
        if self.positive_only_var.get():
            values = random.sample(range(1, (size * 40) + 1), size)
        else:
            values = random.sample(range(-size * 20, size * 20), size)
        self.values_var.set(" ".join(str(v) for v in values))
        value_mode = "positive-only" if self.positive_only_var.get() else "signed"
        self.status_var.set(f"Generated {size} unique {value_mode} values.")

    def shuffle_values(self) -> None:
        try:
            values = parse_values(self.values_var.get())
        except ValueError as exc:
            messagebox.showerror("Invalid values", str(exc))
            return
        random.shuffle(values)
        self.values_var.set(" ".join(str(v) for v in values))
        self.status_var.set("Shuffled current values.")

    def use_gradient_preset(self) -> None:
        preset_name = self.gradient_preset_var.get()
        gradient_start, gradient_end = GRADIENT_PRESETS[preset_name]
        self.gradient_start = gradient_start
        self.gradient_end = gradient_end
        if self.snapshots:
            self._render_current_state()
            self.status_var.set("Updated color theme.")
        else:
            self.status_var.set("Color theme saved for the next run.")

    def apply_gradient(self) -> bool:
        self.use_gradient_preset()
        return True

    def rebuild_push_swap(self) -> None:
        self.stop_playback()
        self.status_var.set("Running make re...")
        self.root.update_idletasks()
        result = subprocess.run(
            ["make", "re"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            self.status_var.set("make re completed successfully.")
            return

        error_text = (result.stderr or result.stdout).strip()
        if not error_text:
            error_text = "make re failed with no output."
        self.status_var.set("make re failed.")
        messagebox.showerror("Build failed", error_text)

    def run_push_swap(self) -> None:
        self.stop_playback()
        push_swap = Path(self.push_swap_var.get()).expanduser()
        checker = Path(self.checker_var.get()).expanduser()

        if not push_swap.exists():
            messagebox.showerror("Missing binary", f"push_swap not found:\n{push_swap}")
            return

        try:
            values = parse_values(self.values_var.get())
        except ValueError as exc:
            messagebox.showerror("Invalid values", str(exc))
            return
        if not self.apply_gradient():
            return

        selected_strategy = self.strategy_var.get().strip()
        strategy_flag = ""
        if selected_strategy and selected_strategy != NO_STRATEGY:
            strategy_flag = selected_strategy
        args = [str(push_swap)]
        if strategy_flag:
            args.append(strategy_flag)
        if self.bench_var.get():
            args.append("--bench")
        args.extend(str(v) for v in values)
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        if result.returncode != 0 and result.stderr:
            self.status_var.set(result.stderr.strip())
        else:
            strategy_label = strategy_flag or "no strategy flag"
            bench_label = " with --bench" if self.bench_var.get() else ""
            self.status_var.set(f"push_swap executed with {strategy_label}{bench_label}.")

        ops = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        invalid = [op for op in ops if op not in VALID_OPS]
        if invalid:
            messagebox.showerror("Invalid output", f"Unknown operations:\n{', '.join(invalid[:10])}")
            return

        try:
            snapshots = self._build_snapshots(values, ops)
        except ValueError as exc:
            messagebox.showerror("Simulation error", str(exc))
            return

        check_text = "checker unavailable"
        if checker.exists():
            checker_run = subprocess.run(
                [str(checker), *[str(v) for v in values]],
                input=result.stdout,
                capture_output=True,
                text=True,
                check=False,
            )
            check_text = (checker_run.stdout or checker_run.stderr).strip() or "no checker output"

        self.ops = ops
        self.snapshots = snapshots
        self.sorted_values = sorted(values)
        self.value_ranks = {value: idx for idx, value in enumerate(self.sorted_values)}
        self.current_index = 0
        self._refresh_ops_text()
        self._render_current_state()
        self.set_settings_visible(False)
        strategy_label = strategy_flag or "none"
        bench_text = "on" if self.bench_var.get() else "off"
        self.info_var.set(
            f"strategy: {strategy_label} | bench: {bench_text} | ops: {len(ops)} | checker: {check_text}"
        )

    def _build_snapshots(self, values: list[int], ops: list[str]) -> list[Snapshot]:
        a = list(values)
        b: list[int] = []
        snapshots = [Snapshot(a.copy(), b.copy(), "start")]
        for op in ops:
            apply_op(a, b, op)
            snapshots.append(Snapshot(a.copy(), b.copy(), op))
        return snapshots

    def _refresh_ops_text(self) -> None:
        self.ops_text.delete("1.0", END)
        self.ops_text.insert(END, "0: start\n")
        for idx, op in enumerate(self.ops, start=1):
            prefix = "-> " if idx == self.current_index else "   "
            self.ops_text.insert(END, f"{prefix}{idx:4d}: {op}\n")

    def _render_current_state(self) -> None:
        self.canvas.delete("all")
        if not self.snapshots:
            self.canvas.create_text(
                500,
                120,
                text="Run push_swap to visualize operations.",
                fill=FG_LIGHT,
                font=("Helvetica", 18, "bold"),
            )
            return

        snap = self.snapshots[self.current_index]
        width = max(self.canvas.winfo_width(), 1000)
        height = max(self.canvas.winfo_height(), 700)
        col_width = width // 2
        top_pad = 115
        stack_height = height - 170
        max_size = max(1, len(self.snapshots[0].a))
        row_height = max(6, stack_height / max_size)
        max_rank = max(1, len(self.value_ranks) - 1)

        self.canvas.create_text(col_width // 2, 34, text="Stack A", fill=FG_LIGHT, font=("Helvetica", 22, "bold"))
        self.canvas.create_text(col_width + col_width // 2, 34, text="Stack B", fill=FG_LIGHT, font=("Helvetica", 22, "bold"))
        self.canvas.create_line(36, 72, width - 36, 72, fill="#223040", width=2)
        self.canvas.create_text(
            width // 2,
            90,
            text=f"step {self.current_index}/{len(self.ops)}   op: {snap.op}",
            fill="#ffd166",
            font=("Helvetica", 16, "bold"),
        )

        self._draw_stack(snap.a, 0, col_width, top_pad, row_height, max_rank)
        self._draw_stack(snap.b, col_width, col_width, top_pad, row_height, max_rank)

    def _draw_stack(
        self,
        stack: list[int],
        x_offset: int,
        col_width: int,
        top_pad: int,
        row_height: float,
        max_rank: int,
    ) -> None:
        center_x = x_offset + col_width / 2
        stack_left = x_offset + 20
        stack_right = x_offset + col_width - 20
        self.canvas.create_rectangle(
            stack_left,
            top_pad - 10,
            stack_right,
            top_pad + row_height * max(1, len(self.snapshots[0].a)),
            outline="#2a3440",
            width=2,
        )
        max_bar_half = max(8.0, (stack_right - stack_left) / 2)
        min_bar_half = min(max_bar_half, (MIN_TILE_CHAR_WIDTH * APPROX_CHAR_WIDTH_PX) / 2)
        for idx, value in enumerate(stack):
            y0 = top_pad + idx * row_height
            y1 = y0 + row_height - 2
            rank = self.value_ranks.get(value, 0)
            width_span = max_bar_half - min_bar_half
            rank_ratio = rank / max_rank if max_rank else 0.0
            bar_half = min_bar_half + (rank_ratio * width_span)
            bar_color = interpolate_color(
                self.gradient_start,
                self.gradient_end,
                rank_ratio,
            )
            self.canvas.create_rectangle(
                center_x - bar_half,
                y0,
                center_x + bar_half,
                y1,
                fill=bar_color,
                outline="",
            )
            self.canvas.create_text(
                center_x,
                (y0 + y1) / 2,
                text=str(value),
                fill="#081018",
                font=("Helvetica", max(8, int(min(14, row_height * 0.45))), "bold"),
            )

    def step_forward(self) -> None:
        if not self.snapshots:
            return
        if self.current_index < len(self.snapshots) - 1:
            self.current_index += 1
            self._refresh_ops_text()
            self._render_current_state()
        else:
            self.stop_playback()

    def step_back(self) -> None:
        self.stop_playback()
        if not self.snapshots:
            return
        if self.current_index > 0:
            self.current_index -= 1
            self._refresh_ops_text()
            self._render_current_state()

    def toggle_play(self) -> None:
        if self.play_job is None:
            self._play_loop()
        else:
            self.stop_playback()

    def _play_loop(self) -> None:
        self.step_forward()
        if self.current_index < len(self.snapshots) - 1:
            # Tkinter timers use integer milliseconds, so sub-1ms values map to the
            # fastest available refresh instead of raising errors.
            delay = max(1, round(float(self.speed_var.get())))
            self.play_job = self.root.after(delay, self._play_loop)
        else:
            self.play_job = None

    def stop_playback(self) -> None:
        if self.play_job is not None:
            self.root.after_cancel(self.play_job)
            self.play_job = None

    def close(self) -> None:
        self.stop_playback()
        if self.root.winfo_exists():
            self.root.quit()
            self.root.destroy()


def main() -> int:
    root = Tk()
    app = PushSwapVisualizer(root)
    def handle_sigint(_signum, _frame) -> None:
        root.after(0, app.close)

    signal.signal(signal.SIGINT, handle_sigint)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.close()
    finally:
        app.stop_playback()
    return 0


if __name__ == "__main__":
    sys.exit(main())
