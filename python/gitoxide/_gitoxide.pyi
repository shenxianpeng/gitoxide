"""Type stubs for the native ``gitoxide._gitoxide`` extension module."""

from pathlib import Path
from typing import List, Optional, Union

StrPath = Union[str, Path]

class GitoxideError(Exception):
    """Base error raised for failed gitoxide operations."""

class Signature:
    """Authorship information (name, email, timestamp) attached to a commit."""

    name: str
    email: str
    time: int
    """Seconds since the Unix epoch."""
    offset: int
    """UTC offset in seconds (east of UTC is positive)."""

class Commit:
    """A fully-decoded, owned view of a git commit."""

    id: str
    tree_id: str
    message: str
    author: Signature
    committer: Signature
    parents: List[str]
    summary: str
    """The first line of the commit message."""
    short_id: str
    """Abbreviated (7-char) commit id."""

class Reference:
    """A git reference (branch, tag, ...) and the object it points at."""

    name: str
    shorthand: str
    target: Optional[str]

class BlameHunk:
    """A run of consecutive lines attributed to a single commit.

    Line numbers are 1-based and inclusive, matching ``git blame`` output.
    """

    start_line: int
    """First line of the run in the file being blamed."""
    line_count: int
    orig_start_line: int
    """First line of the run in the file as it looked in ``commit_id``."""
    commit_id: str
    """Hex id of the commit that last touched these lines."""
    end_line: int
    """Last line of the run (inclusive)."""
    short_id: str
    """Abbreviated (7-char) commit id."""

class Repository:
    """A handle to a git repository."""

    @staticmethod
    def open(path: StrPath) -> "Repository": ...
    @staticmethod
    def discover(path: StrPath) -> "Repository": ...
    @staticmethod
    def init(path: StrPath, bare: bool = False) -> "Repository": ...
    git_dir: Path
    workdir: Optional[Path]
    is_bare: bool
    is_shallow: bool
    head_id: Optional[str]
    head_name: Optional[str]
    head_is_detached: bool
    def head_commit(self) -> Commit: ...
    def rev_parse(self, spec: str) -> str: ...
    def commit(self, rev: str) -> Commit: ...
    def commits(
        self, rev: Optional[str] = None, max_count: Optional[int] = None
    ) -> List[Commit]: ...
    def references(self) -> List[Reference]: ...
    def branches(self) -> List[str]: ...
    def tags(self) -> List[str]: ...
    def read_blob(self, rev: str) -> bytes: ...
    def blame(self, path: str, rev: Optional[str] = None) -> List[BlameHunk]: ...

def open(path: StrPath) -> Repository: ...
def discover(path: StrPath) -> Repository: ...
def init(path: StrPath, bare: bool = False) -> Repository: ...
def gix_version() -> str: ...
