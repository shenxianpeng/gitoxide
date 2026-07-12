"""Shared fixtures: build a small throwaway git repository to test against."""

import subprocess
from pathlib import Path

import pytest


def _run(args, cwd, env):
    subprocess.run(args, cwd=cwd, env=env, check=True, capture_output=True)


@pytest.fixture(scope="session")
def sample_repo(tmp_path_factory):
    """Create a git repo with three commits, a branch, and a tag."""
    path = tmp_path_factory.mktemp("sample_repo")
    env = {
        "GIT_AUTHOR_NAME": "Ada Lovelace",
        "GIT_AUTHOR_EMAIL": "ada@example.com",
        "GIT_COMMITTER_NAME": "Ada Lovelace",
        "GIT_COMMITTER_EMAIL": "ada@example.com",
        "GIT_AUTHOR_DATE": "2020-01-01T00:00:00 +0000",
        "GIT_COMMITTER_DATE": "2020-01-01T00:00:00 +0000",
        "PATH": __import__("os").environ.get("PATH", ""),
        "HOME": str(path),
    }

    _run(["git", "init", "-q", "-b", "main", "."], path, env)

    (path / "README.md").write_text("# hello\n")
    _run(["git", "add", "README.md"], path, env)
    _run(["git", "commit", "-q", "-m", "initial commit"], path, env)

    (path / "file.txt").write_text("one\n")
    _run(["git", "add", "file.txt"], path, env)
    _run(["git", "commit", "-q", "-m", "add file"], path, env)

    (path / "file.txt").write_text("one\ntwo\n")
    _run(["git", "commit", "-q", "-am", "second line\n\nwith a body"], path, env)

    _run(["git", "tag", "v1.0.0"], path, env)
    _run(["git", "branch", "dev"], path, env)

    return path
