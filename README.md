# gitoxide-python

**Fast, safe, pure-Rust Git for Python — bindings to the [gitoxide](https://github.com/GitoxideLabs/gitoxide) engine, and a modern alternative to GitPython.**

`gitoxide` (the `gix` crate) is a next-generation, pure-Rust implementation of
Git, used by projects such as [`uv`](https://github.com/astral-sh/uv) and
[`onefetch`](https://github.com/o2sh/onefetch). It was created by **Byron**, who
is also the original author of **GitPython**.

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

From source (requires a Rust toolchain):

```bash
pip install maturin
maturin develop            # build + install into the active venv
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

```python
# GitPython
from git import Repo
repo = Repo(".")
for c in repo.iter_commits("main", max_count=10):
    print(c.hexsha[:7], c.author.name, c.summary)

# gitoxide-python
import gitoxide
repo = gitoxide.open(".")
for c in repo.commits("main", max_count=10):
    print(c.short_id, c.author.name, c.summary)
```

The key difference: GitPython's `iter_commits` spawns a `git rev-list`
subprocess; `gitoxide-python` walks the object database in-process in Rust.

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

## License

Licensed under either of Apache License 2.0 or MIT license at your option, to
match the upstream gitoxide project.
