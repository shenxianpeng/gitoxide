#!/usr/bin/env python3
"""Fail unless every line of the Rust sources in an lcov report was executed.

Usage::

    cargo llvm-cov report --lcov --output-path lcov.info
    python .github/scripts/check_rust_coverage.py lcov.info

The report is produced by running the pytest suite against an extension built
inside ``cargo llvm-cov show-env`` (see the ``coverage`` job in CI).

There is exactly one kind of line that is allowed to stay unexecuted: a
``#[pymethods]`` attribute line. For every ``&self`` method PyO3 generates a
wrapper that extracts the receiver with ``?``. That wrapper has no source of
its own, so rustc attributes its single coverage region, the ``?`` error edge,
to the attribute. The edge is dead from Python: CPython has already checked
the receiver's type, and the borrow cannot fail because every class is either
``frozen`` or has no ``&mut self`` methods.
"""

import sys
from pathlib import Path

ALLOWED_UNEXECUTED = "#[pymethods]"


def parse_lcov(text):
    """Return ``{source path: {line: execution count}}``."""
    files = {}
    current = None
    for record in text.splitlines():
        if record.startswith("SF:"):
            current = files.setdefault(record[3:], {})
        elif record.startswith("DA:") and current is not None:
            line, count = record[3:].split(",")[:2]
            current[int(line)] = int(count)
    return files


def main(lcov_path):
    files = parse_lcov(Path(lcov_path).read_text())
    rust = {path: lines for path, lines in files.items() if path.endswith(".rs")}
    if not rust:
        print(f"{lcov_path}: no Rust sources in the report", file=sys.stderr)
        return 1

    failed = False
    for path, lines in sorted(rust.items()):
        source = Path(path).read_text().splitlines()
        unexecuted = sorted(line for line, count in lines.items() if count == 0)
        allowed = [n for n in unexecuted if source[n - 1].strip() == ALLOWED_UNEXECUTED]
        missing = [n for n in unexecuted if n not in allowed]
        name = Path(path).name
        print(
            f"{name}: {len(lines) - len(unexecuted)}/{len(lines)} lines executed, "
            f"{len(allowed)} {ALLOWED_UNEXECUTED} attribute line(s) excluded"
        )
        for n in missing:
            print(f"  {name}:{n}: {source[n - 1].strip()}")
        failed |= bool(missing)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
