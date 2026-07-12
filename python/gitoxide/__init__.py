"""gitoxide — fast, safe, pure-Rust Git for Python.

This package provides Python bindings to the `gitoxide <https://github.com/GitoxideLabs/gitoxide>`_
engine (the ``gix`` crate), the pure-Rust Git implementation created by Byron,
the original author of GitPython.

It aims to be a modern alternative to GitPython:

* **Fast** — no subprocess spawning like GitPython; work happens in-process in Rust.
* **Portable** — no dependency on a system ``libgit2`` like pygit2; ships as
  self-contained wheels.
* **Safe** — memory-safe Rust under the hood.

Quick start
-----------

>>> import gitoxide
>>> repo = gitoxide.open(".")
>>> head = repo.head_commit()
>>> print(head.short_id, head.summary)
>>> for commit in repo.commits(max_count=10):
...     print(commit.short_id, commit.author.name, commit.summary)
"""

from ._gitoxide import (
    Commit,
    GitoxideError,
    Reference,
    Repository,
    Signature,
    discover,
    gix_version,
    init,
    open,
)

__all__ = [
    "Commit",
    "GitoxideError",
    "Reference",
    "Repository",
    "Signature",
    "discover",
    "gix_version",
    "init",
    "open",
    "__version__",
]

__version__ = "0.1.0"
