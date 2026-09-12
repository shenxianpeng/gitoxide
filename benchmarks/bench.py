"""Benchmark gitoxide-python against GitPython and pygit2 on a real repository.

Run it (no checkout of this project needed — the libraries come from PyPI):

    uv run --no-project --python 3.14 \\
        --with gitoxide --with GitPython --with pygit2 \\
        benchmarks/bench.py --repo /path/to/cpython

Design notes, because a benchmark is only worth as much as its fairness:

* **Every library does the same work.** Each operation forces the values it
  claims to produce — commit ids, author names, summaries — into Python.
  Handing back a lazy object that decodes later would time the wrong thing.
* **One process per library.** GitPython keeps a long-lived ``git cat-file``
  child process; pygit2 and gix keep their own caches. Sharing one interpreter
  would let them interfere with each other.
* **Steady state, not cold start.** The repository handle is opened once and
  reused, and ``timeit`` warms each operation before measuring. That is the
  *friendliest* choice for GitPython, whose ``cat-file`` helper is already
  running by the time the clock starts.
* **Median of several runs**, with min and max kept in the JSON so anyone can
  see the spread.

The exact call made for each library is written next to it below; that code is
the benchmark's real documentation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import sys
import timeit
from pathlib import Path
from typing import Callable, Dict, List, Tuple

LIBRARIES = ("gitpython", "pygit2", "gitoxide")

# Operation ids, in the order they are reported.
OPS = (
    "open",
    "head_commit",
    "rev_parse",
    "walk",
    "references",
    "read_blob",
    "blame",
)

Suite = Dict[str, Callable[[], object]]


def _digest(parts) -> str:
    """A short, order-independent fingerprint used to cross-check libraries."""
    h = hashlib.sha256()
    for item in sorted(str(p) for p in parts):
        h.update(item.encode())
        h.update(b"\0")
    return h.hexdigest()[:12]


# --------------------------------------------------------------------------
# Per-library suites
# --------------------------------------------------------------------------


def suite_gitpython(args) -> Tuple[Suite, Callable[[], None], str]:
    import git

    repo = git.Repo(args.repo)

    def op_open():
        r = git.Repo(args.repo)
        r.close()

    def op_head_commit():
        c = repo.head.commit
        return c.hexsha, c.summary, c.author.name

    def op_rev_parse():
        return repo.rev_parse(args.rev_spec).hexsha

    def op_walk():
        return [
            (c.hexsha, c.author.name, c.summary)
            for c in repo.iter_commits("HEAD", max_count=args.walk_count)
        ]

    def op_references():
        return [(r.path, r.object.hexsha) for r in repo.references]

    def op_read_blob():
        tree = repo.head.commit.tree
        return (tree / args.blob_path).data_stream.read()

    def op_blame():
        return [
            (commit.hexsha, len(lines))
            for commit, lines in repo.blame("HEAD", args.blame_path)
        ]

    ops: Suite = {
        "open": op_open,
        "head_commit": op_head_commit,
        "rev_parse": op_rev_parse,
        "walk": op_walk,
        "references": op_references,
        "read_blob": op_read_blob,
        "blame": op_blame,
    }
    return ops, repo.close, git.__version__


def suite_pygit2(args) -> Tuple[Suite, Callable[[], None], str]:
    import pygit2

    repo = pygit2.Repository(str(args.repo))

    def op_open():
        pygit2.Repository(str(args.repo))

    def op_head_commit():
        c = repo[repo.head.target]
        return str(c.id), c.message.split("\n", 1)[0], c.author.name

    def op_rev_parse():
        return str(repo.revparse_single(args.rev_spec).id)

    def op_walk():
        out = []
        for i, c in enumerate(repo.walk(repo.head.target, pygit2.enums.SortMode.TIME)):
            if i >= args.walk_count:
                break
            out.append((str(c.id), c.author.name, c.message.split("\n", 1)[0]))
        return out

    def op_references():
        return [(r.name, str(r.target)) for r in repo.references.iterator()]

    def op_read_blob():
        return repo.revparse_single(f"HEAD:{args.blob_path}").data

    def op_blame():
        return [
            (str(h.final_commit_id), h.lines_in_hunk) for h in repo.blame(args.blame_path)
        ]

    ops: Suite = {
        "open": op_open,
        "head_commit": op_head_commit,
        "rev_parse": op_rev_parse,
        "walk": op_walk,
        "references": op_references,
        "read_blob": op_read_blob,
        "blame": op_blame,
    }
    return ops, lambda: None, pygit2.__version__


def suite_gitoxide(args) -> Tuple[Suite, Callable[[], None], str]:
    import gitoxide

    repo = gitoxide.open(args.repo)

    def op_open():
        gitoxide.open(args.repo)

    def op_head_commit():
        c = repo.head_commit()
        return c.id, c.summary, c.author.name

    def op_rev_parse():
        return repo.rev_parse(args.rev_spec)

    def op_walk():
        return [
            (c.id, c.author.name, c.summary)
            for c in repo.commits(max_count=args.walk_count)
        ]

    def op_references():
        return [(r.name, r.target) for r in repo.references()]

    def op_read_blob():
        return repo.read_blob(f"HEAD:{args.blob_path}")

    def op_blame():
        return [(h.commit_id, h.line_count) for h in repo.blame(args.blame_path)]

    ops: Suite = {
        "open": op_open,
        "head_commit": op_head_commit,
        "rev_parse": op_rev_parse,
        "walk": op_walk,
        "references": op_references,
        "read_blob": op_read_blob,
        "blame": op_blame,
    }
    return ops, lambda: None, gitoxide.__version__


SUITES = {
    "gitpython": suite_gitpython,
    "pygit2": suite_pygit2,
    "gitoxide": suite_gitoxide,
}


# --------------------------------------------------------------------------
# Result fingerprints — so a fast wrong answer cannot win
# --------------------------------------------------------------------------


def fingerprint(op: str, value) -> str:
    """Reduce an operation's result to something comparable across libraries."""
    if op == "open":
        return "-"
    if op == "head_commit":
        commit_id, summary, author = value
        return f"{commit_id[:12]} {author} {summary[:40]}"
    if op == "rev_parse":
        return str(value)[:12]
    if op == "walk":
        return f"n={len(value)} {_digest(c[0] for c in value)}"
    if op == "references":
        return f"n={len(value)} {_digest(name for name, _ in value)}"
    if op == "read_blob":
        return f"{len(value)}B sha={hashlib.sha256(value).hexdigest()[:12]}"
    if op == "blame":
        # Only the number of attributed lines is comparable: the three
        # implementations group consecutive lines from one commit into hunks
        # differently, so hunk counts legitimately differ.
        return f"lines={sum(n for _, n in value)}"
    return "?"


# --------------------------------------------------------------------------
# Timing
# --------------------------------------------------------------------------


def measure(fn: Callable[[], object], repeats: int, probe_seconds: float) -> Dict[str, float]:
    # Slow operations are also the most stable ones, and pygit2's blame takes
    # half a minute per call — no need to sit through seven of those.
    if probe_seconds > 1:
        repeats = min(repeats, 3)
    elif probe_seconds > 0.1:
        repeats = min(repeats, 5)

    timer = timeit.Timer(fn)
    inner, _ = timer.autorange()  # warms the cache and picks a loop count
    samples = timer.repeat(repeat=repeats, number=inner)
    per_call = [s / inner for s in samples]
    return {
        "seconds": statistics.median(per_call),
        "min_seconds": min(per_call),
        "max_seconds": max(per_call),
        "runs": repeats,
        "inner_loops": inner,
    }


def run_worker(args) -> Dict[str, object]:
    ops, close, version = SUITES[args.library](args)
    results = []
    for op in OPS:
        if op in args.skip:
            continue
        fn = ops[op]
        probe_start = timeit.default_timer()
        value = fn()  # once, outside the clock, for the fingerprint
        probe_seconds = timeit.default_timer() - probe_start
        timing = measure(fn, args.repeats, probe_seconds)
        timing["op"] = op
        timing["result"] = fingerprint(op, value)
        results.append(timing)
        print(
            f"  {op:<12} {timing['seconds'] * 1000:9.3f} ms   {timing['result']}",
            file=sys.stderr,
        )
    close()
    return {"library": args.library, "version": version, "ops": results}


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def git_out(repo: Path, *cmd: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *cmd], capture_output=True, text=True, check=True
    ).stdout.strip()


def repo_metadata(repo: Path) -> Dict[str, object]:
    # Prefer the canonical upstream URL: benchmarking a fork of a well-known
    # project should still name the project, not whoever cloned it.
    remotes = git_out(repo, "remote").split()
    remote = next((r for r in ("upstream", "origin") if r in remotes), "")
    return {
        "path": str(repo),
        "name": git_out(repo, "remote", "get-url", remote) if remote else repo.name,
        "head": git_out(repo, "rev-parse", "HEAD"),
        "head_date": git_out(repo, "log", "-1", "--format=%cs"),
        "commits": int(git_out(repo, "rev-list", "--count", "HEAD")),
        "refs": len(git_out(repo, "for-each-ref", "--format=%(refname)").splitlines()),
    }


def machine_metadata() -> Dict[str, object]:
    cpu = platform.processor()
    if sys.platform == "darwin":
        try:
            cpu = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):  # pragma: no cover
            pass
    return {
        "cpu": cpu,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "git": subprocess.run(
            ["git", "--version"], capture_output=True, text=True, check=True
        ).stdout.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--repo", type=Path, required=True, help="repository to measure")
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "results.json")
    parser.add_argument("--walk-count", type=int, default=10_000)
    parser.add_argument("--rev-spec", default="HEAD~100")
    parser.add_argument("--blob-path", default="README.rst")
    parser.add_argument("--blame-path", default="Lib/textwrap.py")
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--skip", default="", help="comma-separated operations to skip")
    parser.add_argument("--library", choices=LIBRARIES, help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.repo = args.repo.resolve()
    args.skip = {s for s in args.skip.split(",") if s}

    # Worker mode: measure one library and print its JSON. The driver re-invokes
    # this script once per library so the three never share an interpreter.
    if args.library:
        json.dump(run_worker(args), sys.stdout)
        return 0

    libraries = []
    for library in LIBRARIES:
        print(f"{library}:", file=sys.stderr)
        proc = subprocess.run(
            [
                sys.executable,
                __file__,
                "--library",
                library,
                "--repo",
                str(args.repo),
                "--walk-count",
                str(args.walk_count),
                "--rev-spec",
                args.rev_spec,
                "--blob-path",
                args.blob_path,
                "--blame-path",
                args.blame_path,
                "--repeats",
                str(args.repeats),
                "--skip",
                ",".join(sorted(args.skip)),
            ],
            capture_output=True,
            text=True,
        )
        sys.stderr.write(proc.stderr)
        if proc.returncode != 0:
            print(f"{library} failed", file=sys.stderr)
            return proc.returncode
        libraries.append(json.loads(proc.stdout))

    # Cross-check: every library must have produced the same answer.
    mismatches = []
    for op in OPS:
        if op in args.skip:
            continue
        answers = {
            lib["library"]: next(o["result"] for o in lib["ops"] if o["op"] == op)
            for lib in libraries
        }
        if len({*answers.values()}) > 1:
            mismatches.append({"op": op, "answers": answers})

    payload = {
        "repo": repo_metadata(args.repo),
        "machine": machine_metadata(),
        "parameters": {
            "walk_count": args.walk_count,
            "rev_spec": args.rev_spec,
            "blob_path": args.blob_path,
            "blame_path": args.blame_path,
            "repeats": args.repeats,
        },
        "libraries": libraries,
        "mismatches": mismatches,
    }
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\nwrote {args.out}", file=sys.stderr)

    if mismatches:
        print("\nresults differ between libraries:", file=sys.stderr)
        for m in mismatches:
            print(f"  {m['op']}: {m['answers']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
