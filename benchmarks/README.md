# Benchmarks

What this measures: the cost of the read-oriented operations DevOps tooling
actually reaches for — open a repository, resolve a revision, walk history,
list refs, read a file, blame a file — across the three ways Python talks to
Git today.

| | backend |
|---|---|
| **GitPython** | spawns the `git` CLI and parses its output |
| **pygit2** | wraps the C library `libgit2` |
| **gitoxide-python** | calls the pure-Rust `gix` engine in-process |

The numbers live in [`results.json`](results.json); the chart in
[`../docs/`](../docs) is generated from that file.

## Results

Median time per operation on a full clone of [python/cpython][cpython]
(130,654 commits, 531 references), Apple M2 / macOS 26, Python 3.14.7,
git 2.52.0, gitoxide-python 0.4.0 (gix 0.87.1), GitPython 3.1.62,
pygit2 1.20.0 (libgit2 1.9.6).

| Operation | GitPython | pygit2 | gitoxide-python | vs GitPython |
|---|---:|---:|---:|---:|
| Open the repository | 0.129 ms | 0.111 ms | 0.146 ms | 1.1× slower |
| Read the HEAD commit | 0.087 ms | 0.023 ms | **0.034 ms** | 2.6× faster |
| Resolve `HEAD~100` | 3.02 ms | 0.028 ms | **0.602 ms** | 5.0× faster |
| Walk 10,000 commits | 323 ms | 389 ms | **129 ms** | 2.5× faster |
| List 531 references | 74.4 ms | 1.31 ms | **3.45 ms** | 22× faster |
| Read a 8.7 KB blob | 0.179 ms | 0.188 ms | **0.049 ms** | 3.7× faster |
| Blame 475 lines | 1.07 s | 28.4 s | 1.85 s | 1.7× slower |

Read honestly, that is: **faster than GitPython on five of seven operations**,
a tie on `open`, and a loss on `blame` — where GitPython is not really the
opponent, since it shells out to git's own C implementation. Against pygit2 the
split is different: this binding walks history 3× faster and blames 15× faster,
while pygit2 wins the single-object lookups (`rev-parse`, one reference, one
commit) it has spent fifteen years tuning.

[cpython]: https://github.com/python/cpython

## Reproduce it

```bash
git clone https://github.com/python/cpython /tmp/cpython

uv run --no-project --python 3.14 \
    --with gitoxide --with GitPython --with pygit2 \
    benchmarks/bench.py --repo /tmp/cpython
```

Without `uv`: `pip install gitoxide GitPython pygit2`, then
`python benchmarks/bench.py --repo /tmp/cpython`.

Numbers will not match this file — they are one machine's — but the shape
should. Regenerate the chart with `python benchmarks/plot.py`.

## The rules

A benchmark is worth what its fairness is worth, so:

* **Every library does the same work.** Each operation forces the values it
  claims to produce — commit ids, author names, summaries — into Python.
  Returning a lazy object that decodes later would time the wrong thing.
* **The results are cross-checked.** Each operation is fingerprinted (the set
  of commit ids walked, the SHA-256 of the blob read, the number of lines
  blamed) and the three libraries must agree. A disagreement is printed and
  recorded in `results.json` under `mismatches`, so a fast wrong answer cannot
  quietly win.
* **One process per library.** GitPython keeps a long-lived `git cat-file`
  child process alive; pygit2 and gix keep their own caches. Sharing one
  interpreter would let them interfere.
* **Steady state, not cold start.** The repository handle is opened once and
  reused, and `timeit` warms each operation before the clock starts. This is
  the *friendliest* setup for GitPython, whose `cat-file` helper is already
  running by then.
* **Median of up to 7 runs**, min and max kept in the JSON. Operations slower
  than a second repeat fewer times — they are also the most stable.

## The exact call, per operation

This is the part worth arguing with. If an operation below is not how you would
write it, open an issue — a benchmark that uses a library badly is just a
strawman.

| Operation | GitPython | pygit2 | gitoxide-python |
|---|---|---|---|
| Open | `git.Repo(path)` | `pygit2.Repository(path)` | `gitoxide.open(path)` |
| HEAD commit | `repo.head.commit` → `.hexsha`, `.summary`, `.author.name` | `repo[repo.head.target]` → `.id`, `.message`, `.author.name` | `repo.head_commit()` → `.id`, `.summary`, `.author.name` |
| Resolve `HEAD~100` | `repo.rev_parse("HEAD~100").hexsha` | `repo.revparse_single("HEAD~100").id` | `repo.rev_parse("HEAD~100")` |
| Walk 10,000 commits | `repo.iter_commits("HEAD", max_count=10000)` | `repo.walk(repo.head.target, SortMode.TIME)`, stopped at 10,000 | `repo.commits(max_count=10000)` |
| List references | `[(r.path, r.object.hexsha) for r in repo.references]` | `[(r.name, r.target) for r in repo.references.iterator()]` | `[(r.name, r.target) for r in repo.references()]` |
| Read a blob | `(repo.head.commit.tree / path).data_stream.read()` | `repo.revparse_single(f"HEAD:{path}").data` | `repo.read_blob(f"HEAD:{path}")` |
| Blame | `repo.blame("HEAD", path)` | `repo.blame(path)` | `repo.blame(path)` |

Three of those deserve a note:

* **`references` on GitPython.** `r.object` costs one `cat-file` round trip per
  reference, which is most of that panel's time. It is the documented way to
  get a reference's target; `git for-each-ref` through `repo.git` would be
  faster, but that is shelling out by hand, not using the library.
* **`walk` on pygit2.** `SortMode.TIME` is used because it matches what
  `git log`, `iter_commits` and `commits()` return. pygit2's default
  (`SortMode.NONE`) is faster and returns a different order — and it was
  measured too, so the choice can't be the reason for the result: on this
  repository 10,000 commits take 363 ms sorted by time, 363 ms topologically
  and 175 ms unsorted, against 129 ms here. Time-sorting also carries a fixed
  setup cost — 198 ms of it is already spent by commit 200.
* **`blame` everywhere.** GitPython shells out to `git blame`, so that row is
  really *git's own C implementation* — which is why it is the row to beat, and
  currently isn't beaten.

## Caveats

* One machine, one repository, warm OS page cache. Cold-cache and
  small-repository numbers look different.
* `open` is close to a no-op for all three; it is in the chart so the chart
  isn't only showing the operations that flatter this binding.
* gix's blame is younger than git's and pays for it. That row is reported for
  the same reason.
