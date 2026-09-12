"""Render benchmarks/results.json as a chart — one SVG per colour mode.

    python benchmarks/plot.py            # reads results.json, writes docs/benchmark-*.svg

The chart is small multiples: one panel per operation, each with its own scale,
because the operations span four orders of magnitude and a shared axis would
flatten everything next to `blame`. Within a panel the three libraries keep a
fixed row order, gitoxide-python in the accent colour and the other two in a
de-emphasis grey — the row labels carry identity, so colour never has to.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

HERE = Path(__file__).parent
ROOT = HERE.parent

# --- palette ---------------------------------------------------------------
# Values from the data-viz reference palette; the accent is categorical slot 1,
# the de-emphasis grey is the muted ink. Both clear 3:1 against their surface
# (light 4.30:1 / 3.50:1, dark 4.79:1 / 4.85:1).
THEMES = {
    "light": {
        "surface": "#fcfcfb",
        "primary": "#0b0b0b",
        "secondary": "#52514e",
        "muted": "#898781",
        "accent": "#2a78d6",
        "context": "#898781",
        "baseline": "#c3c2b7",
        "good": "#006300",
    },
    "dark": {
        "surface": "#1a1a19",
        "primary": "#ffffff",
        "secondary": "#c3c2b7",
        "muted": "#898781",
        "accent": "#3987e5",
        "context": "#898781",
        "baseline": "#383835",
        "good": "#0ca30c",
    },
}

FONT = (
    "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
)

# Row order is fixed across every panel: the subject first, then the two
# libraries it is being compared against.
ROWS = [
    ("gitoxide", "gitoxide-python"),
    ("gitpython", "GitPython"),
    ("pygit2", "pygit2"),
]

# Panels read in this order — the operations a history tool spends its time in
# first. `open` (a tie) and `blame` (a loss) come last; they are still on the
# chart, they just don't get to be the first impression.
DISPLAY_ORDER = [
    "walk",
    "references",
    "read_blob",
    "rev_parse",
    "head_commit",
    "open",
    "blame",
]

# --- layout ----------------------------------------------------------------
WIDTH = 1200
MARGIN = 48
COL_GAP = 44
PANEL_W = (WIDTH - 2 * MARGIN - COL_GAP) // 2
PANEL_H = 172
HEADER_H = 126
FOOTER_H = 52
LABEL_W = 122          # right-aligned library names
BAR_X = LABEL_W + 14
VALUE_W = 104          # reserved for the value label after the bar tip
BAR_H = 16
ROW_PITCH = 30


def esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def text_width(text: str, size: float, weight: int = 400) -> float:
    """Rough advance width — enough to keep labels from colliding."""
    factor = 0.58 if weight >= 600 else 0.545
    return len(str(text)) * size * factor


def unit_for(seconds: float) -> Tuple[float, str]:
    """The unit a reader would say out loud for a duration of this size."""
    if seconds >= 1:
        return 1.0, "s"
    if seconds >= 1e-3:
        return 1e3, "ms"
    return 1e6, "µs"


def format_duration(seconds: float, scale: float, unit: str) -> str:
    """Three significant figures. The unit is passed in, not chosen per value:
    every row in a panel shares the unit of the panel's largest value, so no
    one reads `602 µs` as the bigger number next to `3.02 ms`."""
    value = seconds * scale
    if value >= 100:
        return f"{value:.0f} {unit}"
    if value >= 10:
        return f"{value:.1f} {unit}"
    if value >= 1:
        return f"{value:.2f} {unit}"
    return f"{value:.3f} {unit}"


def format_ratio(ratio: float) -> str:
    return f"{ratio:.0f}" if ratio >= 10 else f"{ratio:.1f}"


# --- panel copy ------------------------------------------------------------


def panel_copy(data: dict) -> Dict[str, Dict[str, str]]:
    """Titles and the one-line context under each title."""
    params = data["parameters"]
    repo = data["repo"]

    # The fingerprints carry the sizes, so the labels can't drift from the run.
    results = {
        op["op"]: op["result"]
        for op in data["libraries"][0]["ops"]
    }
    blob_bytes = re.match(r"(\d+)B", results.get("read_blob", ""))
    blame_lines = re.search(r"lines=(\d+)", results.get("blame", ""))
    ref_count = re.search(r"n=(\d+)", results.get("references", ""))

    blob_kb = f"{int(blob_bytes.group(1)) / 1024:.1f} KB" if blob_bytes else ""

    return {
        "open": {
            "title": "Open the repository",
            "context": "a handle, nothing read yet",
        },
        "head_commit": {
            "title": "Read the HEAD commit",
            "context": "id, author and summary",
        },
        "rev_parse": {
            "title": f"Resolve {params['rev_spec']}",
            "context": "walk back to an older commit id",
        },
        "walk": {
            "title": f"Walk {params['walk_count']:,} commits",
            "context": "id, author and summary for each one",
        },
        "references": {
            "title": f"List {ref_count.group(1) if ref_count else ''} references",
            "context": "every branch and tag, with its target",
        },
        "read_blob": {
            "title": "Read a file at HEAD",
            "context": f"{params['blob_path']}, {blob_kb}".strip().rstrip(","),
        },
        "blame": {
            "title": f"Blame {Path(params['blame_path']).name}",
            "context": f"{blame_lines.group(1) if blame_lines else ''} lines"
            f" of {params['blame_path']}",
        },
    }


def repo_label(data: dict) -> str:
    url = data["repo"]["name"]
    match = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", url)
    return match.group(1) if match else url


# --- svg -------------------------------------------------------------------


def render(data: dict, theme: Dict[str, str]) -> str:
    copy = panel_copy(data)
    timings = {
        lib["library"]: {op["op"]: op["seconds"] for op in lib["ops"]}
        for lib in data["libraries"]
    }
    measured = [op["op"] for op in data["libraries"][0]["ops"]]
    ops = [op for op in DISPLAY_ORDER if op in measured]
    ops += [op for op in measured if op not in DISPLAY_ORDER]

    rows_of_panels = (len(ops) + 2) // 2  # the last cell holds the method note
    height = HEADER_H + rows_of_panels * PANEL_H + FOOTER_H
    out: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" '
        f'width="{WIDTH}" height="{height}" font-family="{FONT}">',
        f'<rect width="{WIDTH}" height="{height}" fill="{theme["surface"]}"/>',
    ]

    def text(x, y, content, size=13, fill=None, weight=400, anchor="start", extra=""):
        out.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" '
            f'fill="{fill or theme["primary"]}" font-weight="{weight}" '
            f'text-anchor="{anchor}"{extra}>{esc(content)}</text>'
        )

    # Header ---------------------------------------------------------------
    text(MARGIN, 52, "gitoxide-python vs GitPython vs pygit2", size=30, weight=600)
    subtitle = (
        f"Median time per operation on {repo_label(data)} "
        f"({data['repo']['commits']:,} commits) — lower is better"
    )
    text(MARGIN, 78, subtitle, size=15, fill=theme["secondary"])

    # Key: a swatch beside each name, so identity never rides on colour alone.
    key_y = 100
    key_x = MARGIN
    for colour, name in ((theme["accent"], "gitoxide-python"), (theme["context"], "GitPython / pygit2")):
        out.append(
            f'<rect x="{key_x}" y="{key_y - 9}" width="10" height="10" rx="2" fill="{colour}"/>'
        )
        text(key_x + 16, key_y, name, size=13, fill=theme["secondary"])
        key_x += 16 + text_width(name, 13) + 28

    # Panels ---------------------------------------------------------------
    for index, op in enumerate(ops):
        col, row = index % 2, index // 2
        x0 = MARGIN + col * (PANEL_W + COL_GAP)
        y0 = HEADER_H + row * PANEL_H

        text(x0, y0 + 16, copy[op]["title"], size=17, weight=600)
        text(x0, y0 + 36, copy[op]["context"], size=12.5, fill=theme["muted"])

        subject = timings["gitoxide"][op]
        reference = timings["gitpython"][op]
        if subject < reference:
            note, note_fill = f"{format_ratio(reference / subject)}× faster than GitPython", theme["good"]
        else:
            note, note_fill = f"{format_ratio(subject / reference)}× slower than GitPython", theme["secondary"]
        text(x0 + PANEL_W, y0 + 16, note, size=13, fill=note_fill, anchor="end")

        longest = max(timings[lib][op] for lib, _ in ROWS)
        scale, unit = unit_for(longest)
        bar_max = PANEL_W - BAR_X - VALUE_W

        for row_index, (lib, label) in enumerate(ROWS):
            seconds = timings[lib][op]
            y = y0 + 56 + row_index * ROW_PITCH
            text(
                x0 + LABEL_W,
                y + BAR_H - 4,
                label,
                size=13,
                fill=theme["secondary"] if lib != "gitoxide" else theme["primary"],
                weight=600 if lib == "gitoxide" else 400,
                anchor="end",
            )

            width = max(3.0, bar_max * (seconds / longest))
            colour = theme["accent"] if lib == "gitoxide" else theme["context"]
            radius = min(4.0, width / 2)
            bx = x0 + BAR_X
            # Square at the baseline, 4px rounded at the data end.
            out.append(
                f'<path d="M{bx:.1f},{y:.1f} H{bx + width - radius:.1f} '
                f'A{radius:.1f},{radius:.1f} 0 0 1 {bx + width:.1f},{y + radius:.1f} '
                f'V{y + BAR_H - radius:.1f} '
                f'A{radius:.1f},{radius:.1f} 0 0 1 {bx + width - radius:.1f},{y + BAR_H:.1f} '
                f'H{bx:.1f} Z" fill="{colour}"/>'
            )
            text(
                bx + width + 9,
                y + BAR_H - 4,
                format_duration(seconds, scale, unit),
                size=13,
                weight=600 if lib == "gitoxide" else 400,
                fill=theme["primary"] if lib == "gitoxide" else theme["secondary"],
                extra=' font-variant-numeric="tabular-nums"',
            )

        # A hairline baseline under the bars, one step off the surface.
        base_y = y0 + 56 + len(ROWS) * ROW_PITCH - (ROW_PITCH - BAR_H) + 6
        out.append(
            f'<line x1="{x0 + BAR_X}" y1="{base_y:.1f}" x2="{x0 + PANEL_W}" '
            f'y2="{base_y:.1f}" stroke="{theme["baseline"]}" stroke-width="1"/>'
        )

    # Method note, in the cell the panels left empty ------------------------
    if len(ops) % 2:
        col, row = len(ops) % 2, len(ops) // 2
        x0 = MARGIN + col * (PANEL_W + COL_GAP)
        y0 = HEADER_H + row * PANEL_H
        text(x0, y0 + 16, "How it was measured", size=17, weight=600)
        lines = [
            "Each library runs in its own process and resolves the same",
            "values, so none can win by handing back a lazy object. All",
            "three agree on every result — the script checks.",
            "GitPython shells out to git; pygit2 wraps libgit2; this",
            "binding calls gix in-process.",
        ]
        for line_index, line in enumerate(lines):
            text(
                x0,
                y0 + 42 + line_index * 19,
                line,
                size=13,
                fill=theme["secondary"],
            )

    # Footer ---------------------------------------------------------------
    machine, repo = data["machine"], data["repo"]
    names = dict(ROWS)
    versions = ", ".join(
        f"{names.get(lib['library'], lib['library'])} {lib['version']}"
        for lib in data["libraries"]
    )
    footer_y = height - FOOTER_H + 22
    text(
        MARGIN,
        footer_y,
        f"{versions} · Python {machine['python']} · {machine['git']} · {machine['cpu']}",
        size=12.5,
        fill=theme["muted"],
    )
    text(
        MARGIN,
        footer_y + 18,
        f"{repo_label(data)} @ {repo['head'][:7]} ({repo['head_date']}) · "
        f"median of up to {data['parameters']['repeats']} runs · "
        f"reproduce with benchmarks/bench.py",
        size=12.5,
        fill=theme["muted"],
    )

    out.append("</svg>")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--results", type=Path, default=HERE / "results.json")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "docs")
    args = parser.parse_args()

    data = json.loads(args.results.read_text())
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for mode, theme in THEMES.items():
        path = args.out_dir / f"benchmark-{mode}.svg"
        path.write_text(render(data, theme) + "\n")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
