"""Shared fixtures: build small throwaway git repositories to test against."""

import os
import subprocess
from pathlib import Path

import pytest

SIGNATURE = "Ada Lovelace <ada@example.com> 1577836800 +0000"


def _env(home):
    """A hermetic git environment with a fixed identity and timestamp."""
    return {
        "GIT_AUTHOR_NAME": "Ada Lovelace",
        "GIT_AUTHOR_EMAIL": "ada@example.com",
        "GIT_COMMITTER_NAME": "Ada Lovelace",
        "GIT_COMMITTER_EMAIL": "ada@example.com",
        "GIT_AUTHOR_DATE": "2020-01-01T00:00:00 +0000",
        "GIT_COMMITTER_DATE": "2020-01-01T00:00:00 +0000",
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(home),
    }


def _run(args, cwd, env, **kwargs):
    return subprocess.run(
        args, cwd=cwd, env=env, check=True, capture_output=True, **kwargs
    )


def git(path, *args):
    """Run a git command inside `path` and return its stripped stdout."""
    return _run(["git", *args], path, _env(path), text=True).stdout.strip()


def write_commit_object(path, content):
    """Store `content` verbatim as a commit object (no validation) and return its id.

    `git hash-object --literally` lets the tests plant malformed commits that
    git itself would never create, to exercise the decoding error paths.
    """
    if isinstance(content, str):
        content = content.encode()
    out = _run(
        ["git", "hash-object", "-t", "commit", "-w", "--literally", "--stdin"],
        path,
        _env(path),
        input=content,
    ).stdout
    return out.decode().strip()


def _commit_file(path, name, text, message):
    (path / name).write_text(text)
    git(path, "add", name)
    git(path, "commit", "-q", "-m", message)


@pytest.fixture(scope="session")
def sample_repo(tmp_path_factory):
    """Create a git repo with three commits, a branch, and a tag."""
    path = tmp_path_factory.mktemp("sample_repo")
    git(path, "init", "-q", "-b", "main", ".")

    _commit_file(path, "README.md", "# hello\n", "initial commit")
    _commit_file(path, "file.txt", "one\n", "add file")
    _commit_file(path, "file.txt", "one\ntwo\n", "second line\n\nwith a body")

    git(path, "tag", "v1.0.0")
    git(path, "branch", "dev")

    return path


@pytest.fixture
def scratch_repo(tmp_path):
    """A fresh single-commit repo that a test may freely corrupt."""
    path = tmp_path / "scratch"
    path.mkdir()
    git(path, "init", "-q", "-b", "main", ".")
    _commit_file(path, "a.txt", "one\n", "first")
    return path


@pytest.fixture(scope="session")
def bare_repo(tmp_path_factory, sample_repo):
    """A bare clone of `sample_repo`."""
    path = tmp_path_factory.mktemp("bare") / "sample.git"
    git(path.parent, "clone", "-q", "--bare", sample_repo.as_uri(), str(path))
    return path


@pytest.fixture(scope="session")
def shallow_repo(tmp_path_factory, sample_repo):
    """A depth-1 clone of `sample_repo`."""
    path = tmp_path_factory.mktemp("shallow") / "sample"
    git(path.parent, "clone", "-q", "--depth", "1", sample_repo.as_uri(), str(path))
    return path


@pytest.fixture(scope="session")
def detached_repo(tmp_path_factory, sample_repo):
    """A clone of `sample_repo` with HEAD detached at the first commit."""
    path = tmp_path_factory.mktemp("detached") / "sample"
    git(path.parent, "clone", "-q", sample_repo.as_uri(), str(path))
    git(path, "checkout", "-q", "--detach", "HEAD~2")
    return path


@pytest.fixture
def unborn_repo(tmp_path):
    """A freshly initialised repo whose HEAD points at a branch with no commits."""
    path = tmp_path / "unborn"
    git(tmp_path, "init", "-q", "-b", "main", str(path))
    return path
