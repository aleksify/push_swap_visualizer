# Push Swap Visualizer

This is a standalone Python visualizer for `push_swap` that uses only the standard
library Tkinter GUI.

## Features

- Runs your local `push_swap` binary directly
- Generates random unique values for 20, 100, or 500 numbers
- Lets you run with a selected strategy flag or with no strategy flag at all
- Steps forward and backward through the operation list
- Plays the full run with adjustable delay
- Draws stack `a` and stack `b` side by side
- Optionally validates the output with `checker_linux`

## Run

```bash
./push_swap-visualizer
```

You can still run it directly with:

```bash
python3 src/visualizer.py
```

Default paths:

- `push_swap`: `../push_swap`
- `checker_linux`: `src/checker_linux`

You can change both paths in the UI.

## Notes

- If Tkinter is missing on your system, install the Python Tk package first.
- The visualizer simulates the operations itself, so it can still animate even if
  the checker path is missing.

## Reference
- Codex was used for writing this program
