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
    RIGHT,
    TOP,
    Button,
    Canvas,
    Entry,
    Frame,
    Label,
    Scale,
    StringVar,
    Text,
    Tk,
    X,
)
from tkinter import messagebox


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PUSH_SWAP = (SCRIPT_DIR.parent / "push_swap").resolve()
DEFAULT_CHECKER = (SCRIPT_DIR.parent / "checker_linux").resolve()
VALID_OPS = {"sa", "sb", "ss", "pa", "pb", "ra", "rb", "rr", "rra", "rrb", "rrr"}
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
        self.status_var = StringVar(value="Ready.")
        self.info_var = StringVar(value="No run loaded.")
        self.speed_var = StringVar(value="20.0")

        self.snapshots: list[Snapshot] = []
        self.ops: list[str] = []
        self.current_index = 0
        self.play_job: str | None = None
        self.value_ranks: dict[int, int] = {}

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._render_current_state()

    def _set_initial_geometry(self) -> None:
        screen_h = self.root.winfo_screenheight()
        width = 1520
        height = max(860, screen_h - 80)
        self.root.geometry(f"{width}x{height}+20+20")

    def _build_ui(self) -> None:
        header = Frame(self.root, bg=BG_APP, padx=14, pady=14)
        header.pack(side=TOP, fill=X)
        header.pack_propagate(False)
        header.configure(height=250)
        header.grid_columnconfigure(0, weight=1, minsize=920)
        header.grid_columnconfigure(1, weight=0, minsize=430)
        header.grid_rowconfigure(0, weight=1)

        paths = Frame(header, bg=BG_PANEL, padx=14, pady=14, highlightbackground="#d8dee8", highlightthickness=1)
        paths.grid(row=0, column=0, sticky="nsew")
        paths.pack_propagate(False)
        paths.configure(width=920)

        actions = Frame(
            header,
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
            text="Run push_swap",
            command=self.run_push_swap,
            bg="#ffb703",
            fg="#1a1a1a",
            activebackground="#f4a000",
            activeforeground="#1a1a1a",
            relief="flat",
            padx=14,
            pady=8,
        ).grid(row=2, column=1, columnspan=2, padx=4, pady=8, sticky="we")

        Label(actions, text="Playback", bg=BG_PANEL, fg=FG_TEXT, font=("Helvetica", 14, "bold")).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(10, 10)
        )

        Button(
            actions,
            text="Step -",
            command=self.step_back,
            relief="flat",
            bg="#e9eef5",
            fg=FG_TEXT,
            padx=14,
            pady=8,
        ).grid(row=4, column=0, padx=4, pady=4, sticky="we")
        Button(
            actions,
            text="Step +",
            command=self.step_forward,
            relief="flat",
            bg="#e9eef5",
            fg=FG_TEXT,
            padx=14,
            pady=8,
        ).grid(row=4, column=1, padx=4, pady=4, sticky="we")
        Button(
            actions,
            text="Play / Pause",
            command=self.toggle_play,
            relief="flat",
            bg="#14213d",
            fg=FG_LIGHT,
            activebackground="#0b162e",
            activeforeground=FG_LIGHT,
            padx=14,
            pady=8,
        ).grid(row=4, column=2, padx=4, pady=4, sticky="we")

        Label(actions, text="Delay (ms)", bg=BG_PANEL, fg=FG_MUTED, font=("Helvetica", 11, "bold")).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(10, 0)
        )

        delay_scale = Scale(
            actions,
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
        delay_scale.grid(row=6, column=0, columnspan=3, sticky="we", padx=4)
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
        Label(
            status_row,
            textvariable=self.info_var,
            anchor="e",
            bg=BG_APP,
            fg=FG_TEXT,
            font=("Helvetica", 11, "bold"),
        ).pack(side=RIGHT)

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

    def _on_speed_change(self, value: str) -> None:
        self.speed_var.set(f"{float(value):.1f}")

    def generate_values(self, size: int) -> None:
        values = random.sample(range(-size * 20, size * 20), size)
        self.values_var.set(" ".join(str(v) for v in values))
        self.status_var.set(f"Generated {size} unique values.")

    def shuffle_values(self) -> None:
        try:
            values = parse_values(self.values_var.get())
        except ValueError as exc:
            messagebox.showerror("Invalid values", str(exc))
            return
        random.shuffle(values)
        self.values_var.set(" ".join(str(v) for v in values))
        self.status_var.set("Shuffled current values.")

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

        args = [str(push_swap), *[str(v) for v in values]]
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        if result.stderr:
            self.status_var.set(result.stderr.strip())
        else:
            self.status_var.set("push_swap executed.")

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
        self.value_ranks = {value: idx for idx, value in enumerate(sorted(values))}
        self.current_index = 0
        self._refresh_ops_text()
        self._render_current_state()
        self.info_var.set(f"ops: {len(ops)} | checker: {check_text}")

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

        self._draw_stack(snap.a, 0, col_width, top_pad, row_height, max_rank, "#2ec4b6")
        self._draw_stack(snap.b, col_width, col_width, top_pad, row_height, max_rank, "#ff6b6b")

    def _draw_stack(
        self,
        stack: list[int],
        x_offset: int,
        col_width: int,
        top_pad: int,
        row_height: float,
        max_rank: int,
        color: str,
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
            self.canvas.create_rectangle(
                center_x - bar_half,
                y0,
                center_x + bar_half,
                y1,
                fill=color,
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
