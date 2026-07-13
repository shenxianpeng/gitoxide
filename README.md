# gitoxide-python

[![PyPI Version](https://img.shields.io/pypi/v/gitoxide)](https://pypi.org/project/gitoxide/)
[![CI](https://github.com/shenxianpeng/gitoxide/actions/workflows/CI.yml/badge.svg)](https://github.com/shenxianpeng/gitoxide/actions/workflows/CI.yml)

**Fast, safe, pure-Rust Git for Python — bindings to the [gitoxide](https://github.com/GitoxideLabs/gitoxide) engine, and a modern alternative to GitPython.**

`gitoxide` (the `gix` crate) is a next-generation, pure-Rust implementation of
Git. This project exposes that engine to Python through [PyO3](https://pyo3.rs)
and ships as pre-built wheels via [maturin](https://www.maturin.rs), so you get:

| | GitPython | pygit2 | **gitoxide-python** |
|---|---|---|---|
| Backend | shells out to the `git` CLI | C `libgit2` | pure-Rust `gix` |
| Speed | slow (spawns a subprocess per call) | fast | fast (in-process, no subprocess) |
| Install | needs `git` on `PATH` | needs a C toolchain / system `libgit2` | `pip install`, self-contained wheels |
| Memory safety | n/a (subprocess) | C | Rust |

> **Status: alpha.** The binding surface is small but real. It currently covers
> read-oriented workflows (open/discover, HEAD, history walk, refs, branches,
> tags, blob reads) — the operations DevOps tooling reaches for most. See
> [Scope](#scope) for what is and isn't wrapped yet.

## Installation

```bash
pip install gitoxide
```

Pre-built wheels are published for Linux (manylinux, x86_64 + aarch64), macOS
(x86_64 + Apple Silicon), and Windows — no Rust toolchain or system `libgit2`
required.

## Quick start

```python
import gitoxide

repo = gitoxide.open(".")            # or gitoxide.discover(".")

print(repo.git_dir)                  # .../my-project/.git
print(repo.workdir)                  # .../my-project  (None if bare)
print(repo.is_bare)                  # False
print(repo.head_name)                # 'main'  (None if detached)

# The commit at HEAD
head = repo.head_commit()
print(head.short_id, head.summary)
print(head.author.name, head.author.email, head.author.time)

# Walk history (reverse-chronological), like `git log`
for commit in repo.commits(max_count=10):
    print(commit.short_id, commit.author.name, commit.summary)

# Resolve a revspec to an object id
print(repo.rev_parse("HEAD~2"))
print(repo.rev_parse("main"))

# Branches, tags, and all references
print(repo.branches())               # ['main', 'dev', ...]
print(repo.tags())                   # ['v1.0.0', ...]
for ref in repo.references():
    print(ref.name, "->", ref.target)

# Read a file's content at a revision
readme = repo.read_blob("HEAD:README.md")
print(readme.decode())
```

## Migrating from GitPython

Common operations, side by side:

| GitPython | gitoxide-python |
|---|---|
| `from git import Repo` | `import gitoxide` |
| `repo = Repo(path)` | `repo = gitoxide.open(path)` |
| `Repo(path, search_parent_directories=True)` | `gitoxide.discover(path)` |
| `repo.head.commit` | `repo.head_commit()` |
| `repo.active_branch.name` | `repo.head_name` |
| `repo.iter_commits("main", max_count=10)` | `repo.commits("main", max_count=10)` |
| `repo.commit("HEAD~2")` | `repo.commit("HEAD~2")` |
| `repo.rev_parse("main").hexsha` | `repo.rev_parse("main")` |
| `[b.name for b in repo.branches]` | `repo.branches()` |
| `[t.name for t in repo.tags]` | `repo.tags()` |
| `c.hexsha`, `c.summary`, `c.author.name` | `c.id`, `c.summary`, `c.author.name` |

The key difference is what happens underneath: GitPython's `iter_commits` spawns
a `git rev-list` subprocess; gitoxide-python walks the object database
in-process in Rust.

## API

### Module functions

- `gitoxide.open(path) -> Repository`
- `gitoxide.discover(path) -> Repository` — search `path` and its parents
- `gitoxide.init(path, bare=False) -> Repository`
- `gitoxide.gix_version() -> str`

### `Repository`

Properties: `git_dir`, `workdir`, `is_bare`, `is_shallow`, `head_id`,
`head_name`, `head_is_detached`.

> **Note:** `head_name` and `head_is_detached` access the `HEAD` reference
> and may raise `GitoxideError` if it is inaccessible (e.g., corrupted
> repository). Other properties never raise.

Methods: `head_commit()`, `rev_parse(spec)`, `commit(rev)`,
`commits(rev=None, max_count=None)`, `references()`, `branches()`, `tags()`,
`read_blob(rev)`.

### `Commit`

`id`, `short_id`, `tree_id`, `message`, `summary`, `author`, `committer`,
`parents`.

### `Signature`

`name`, `email`, `time` (Unix seconds), `offset` (UTC offset seconds).

### `Reference`

`name`, `shorthand`, `target`.

All errors (from any function or method) are raised as
`gitoxide.GitoxideError`.

## Scope

This is a binding, not a reimplementation: it exposes a slice of what the `gix`
engine already does. Today that slice is:

- **Wrapped:** open / discover / init, HEAD, history walk, rev-parse,
  references, branches, tags, and blob reads.
- **Not wrapped yet:** diff & status, tree listing, writing commits and the
  index, blame, and clone / remote operations.

The engine supports much more; these are simply the parts this binding hasn't
surfaced yet. Issues and pull requests that expose more of `gix` are welcome —
see [Contributing](#contributing).

## Contributing

The binding layer lives in a single [`src/lib.rs`](src/lib.rs) and maps closely
onto the `gix` API, so adding a method is usually a small, self-contained change.

Building from source requires a [Rust toolchain](https://rustup.rs) (this is
also the path used when installing the sdist on a platform without a pre-built
wheel):

```bash
python -m venv .venv && source .venv/bin/activate
pip install maturin pytest

maturin develop          # build the extension into the venv
pytest -q                # run the test suite

cargo fmt --all          # format Rust
cargo clippy --all-targets -- -D warnings
```

The tests generate a throwaway git repository on the fly (see
[`tests/conftest.py`](tests/conftest.py)), so they need `git` on `PATH` but
touch nothing outside a temp directory.

## License

Licensed under either of Apache License 2.0 or MIT license at your option, to
match the upstream gitoxide project.
