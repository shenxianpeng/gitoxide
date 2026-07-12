# gitoxide-python

**Fast, safe, pure-Rust Git for Python — bindings to the [gitoxide](https://github.com/GitoxideLabs/gitoxide) engine, and a modern alternative to GitPython.**

`gitoxide` (the `gix` crate) is a next-generation, pure-Rust implementation of
Git, used by projects such as [`onefetch`](https://github.com/o2sh/onefetch).
It was created by **Byron**, who is also the original author of **GitPython**.

This project exposes that engine to Python through [PyO3](https://pyo3.rs) and
ships as pre-built wheels via [maturin](https://www.maturin.rs), so you get:

| | GitPython | pygit2 | **gitoxide-python** |
|---|---|---|---|
| Backend | shells out to the `git` CLI | C `libgit2` | pure-Rust `gix` |
| Speed | slow (spawns a subprocess per call) | fast | fast (in-process, no subprocess) |
| Install | needs `git` on `PATH` | needs a C toolchain / system `libgit2` | `pip install`, self-contained wheels |
| Memory safety | n/a (subprocess) | C | Rust |

> **Status: alpha.** The binding surface is small but real and growing. It
> currently covers read-oriented workflows (open/discover, HEAD, history walk,
> refs, branches, tags, blob reads) — the operations DevOps tooling reaches for
> most. See [Roadmap](#roadmap).

## Installation

```bash
pip install gitoxide
```

Pre-built wheels are published for Linux (manylinux, x86_64 + aarch64), macOS
(x86_64 + Apple Silicon), and Windows — no Rust toolchain or system `libgit2`
required.

### From source

Building from a checkout (or from the sdist on an unsupported platform) requires
a [Rust toolchain](https://rustup.rs):

```bash
pip install maturin
maturin develop            # build + install into the active virtualenv
# or build a wheel:
maturin build --release
```

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

Errors are raised as `gitoxide.GitoxideError`.

## Roadmap

- Diffing and status
- Tree traversal / listing entries
- Writing commits, staging (index), tag/branch creation
- Blame
- Cloning and remote operations (fetch/push)
- Lazy commit iterators instead of eager lists for very large histories

Contributions welcome — the binding layer lives in a single [`src/lib.rs`](src/lib.rs)
and maps cleanly onto the `gix` API.

## Development

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

Licensed under either of Apache License 2.0 or MIT license at your option, to
match the upstream gitoxide project.
