"""Unusual repository states: bare, shallow, detached, unborn and corrupt."""

import gitoxide
import pytest

from conftest import SIGNATURE, git, write_commit_object


# -- bare / shallow / detached / unborn ---------------------------------------


def test_bare_clone(bare_repo):
    repo = gitoxide.open(str(bare_repo))
    assert repo.is_bare is True
    assert repo.workdir is None
    assert repo.git_dir.samefile(bare_repo)
    assert repr(repo).endswith("bare=true)")
    assert repo.head_name == "main"
    assert len(repo.commits()) == 3
    assert repo.read_blob("HEAD:README.md") == b"# hello\n"


def test_shallow_clone(shallow_repo, sample_repo):
    repo = gitoxide.open(str(shallow_repo))
    assert repo.is_shallow is True
    assert gitoxide.open(str(sample_repo)).is_shallow is False
    # Only the tip is present; history stops at the shallow boundary.
    assert [c.summary for c in repo.commits()] == ["second line"]


def test_detached_head(detached_repo, sample_repo):
    repo = gitoxide.open(str(detached_repo))
    assert repo.head_is_detached is True
    assert repo.head_name is None
    assert repo.head_id == gitoxide.open(str(sample_repo)).rev_parse("HEAD~2")
    assert repo.head_commit().summary == "initial commit"
    # A walk from a detached HEAD still works and stops at the root.
    assert len(repo.commits()) == 1


def test_unborn_head(unborn_repo):
    repo = gitoxide.open(str(unborn_repo))
    assert repo.head_id is None
    assert repo.head_name == "main"
    assert repo.head_is_detached is False
    assert repo.references() == []
    assert repo.branches() == []
    assert repo.tags() == []

    with pytest.raises(gitoxide.GitoxideError, match="does not have any commits"):
        repo.head_commit()
    with pytest.raises(gitoxide.GitoxideError, match="does not have any commits"):
        repo.commits()
    with pytest.raises(gitoxide.GitoxideError, match="does not have any commits"):
        repo.blame("a.txt")


# -- corrupt references -------------------------------------------------------


def test_corrupt_head(scratch_repo):
    repo = gitoxide.open(str(scratch_repo))
    (scratch_repo / ".git" / "HEAD").write_text("this is not a ref\n")

    assert repo.head_id is None
    with pytest.raises(gitoxide.GitoxideError, match="could not be decoded"):
        repo.head_name
    with pytest.raises(gitoxide.GitoxideError, match="could not be decoded"):
        repo.head_is_detached
    with pytest.raises(gitoxide.GitoxideError, match="could not be decoded"):
        repo.head_commit()
    with pytest.raises(gitoxide.GitoxideError, match="could not be decoded"):
        repo.commits()
    with pytest.raises(gitoxide.GitoxideError, match="could not be decoded"):
        repo.blame("a.txt")


def test_dangling_ref(scratch_repo):
    """A ref pointing at an object that does not exist."""
    missing = "0123456789abcdef0123456789abcdef01234567"
    (scratch_repo / ".git" / "refs" / "heads" / "dangling").write_text(missing + "\n")
    repo = gitoxide.open(str(scratch_repo))

    # Resolving the name works, dereferencing the object does not.
    assert repo.rev_parse("dangling") == missing
    for call in (repo.commit, repo.read_blob, repo.commits):
        with pytest.raises(gitoxide.GitoxideError, match="could not be found"):
            call("dangling")
    with pytest.raises(gitoxide.GitoxideError):
        repo.blame("a.txt", "dangling")

    # references() still lists it, with no peeled target.
    refs = {r.name: r for r in repo.references()}
    assert refs["refs/heads/dangling"].target is None
    assert refs["refs/heads/dangling"].shorthand == "dangling"
    assert refs["refs/heads/main"].target == repo.head_id
    assert repr(refs["refs/heads/dangling"]) == (
        'Reference(name="refs/heads/dangling", target=None)'
    )


def test_undecodable_ref(scratch_repo):
    repo = gitoxide.open(str(scratch_repo))
    (scratch_repo / ".git" / "refs" / "heads" / "broken").write_text("not a hash\n")
    (scratch_repo / ".git" / "refs" / "tags" / "broken").write_text("not a hash\n")

    with pytest.raises(gitoxide.GitoxideError, match="refs/heads/broken"):
        repo.references()
    with pytest.raises(gitoxide.GitoxideError, match="refs/heads/broken"):
        repo.branches()
    with pytest.raises(gitoxide.GitoxideError, match="refs/tags/broken"):
        repo.tags()


def test_corrupt_packed_refs(scratch_repo):
    git(scratch_repo, "pack-refs", "--all")
    repo = gitoxide.open(str(scratch_repo))
    assert repo.branches() == ["main"]

    (scratch_repo / ".git" / "packed-refs").write_bytes(b"\xff garbage\n")
    for call in (repo.references, repo.branches, repo.tags):
        with pytest.raises(gitoxide.GitoxideError):
            call()


# -- malformed commit objects ---------------------------------------------------


def test_undecodable_commit(scratch_repo):
    repo = gitoxide.open(str(scratch_repo))
    bad = write_commit_object(scratch_repo, "this is not a commit\n")
    with pytest.raises(gitoxide.GitoxideError, match="object parsing failed"):
        repo.commit(bad)


def test_invalid_author_and_committer(scratch_repo):
    repo = gitoxide.open(str(scratch_repo))
    tree = repo.head_commit().tree_id

    bad_author = write_commit_object(
        scratch_repo,
        f"tree {tree}\nauthor nobody\ncommitter {SIGNATURE}\n\nmsg\n",
    )
    bad_committer = write_commit_object(
        scratch_repo,
        f"tree {tree}\nauthor {SIGNATURE}\ncommitter nobody\n\nmsg\n",
    )
    for oid in (bad_author, bad_committer):
        with pytest.raises(gitoxide.GitoxideError, match="Invalid actor signature"):
            repo.commit(oid)
    with pytest.raises(gitoxide.GitoxideError, match="Invalid actor signature"):
        repo.blame("a.txt", bad_author)


def test_history_walk_over_malformed_commits(scratch_repo):
    repo = gitoxide.open(str(scratch_repo))
    tree = repo.head_commit().tree_id

    def child_of(parent, message):
        return write_commit_object(
            scratch_repo,
            f"tree {tree}\nparent {parent}\nauthor {SIGNATURE}\n"
            f"committer {SIGNATURE}\n\n{message}\n",
        )

    # The traversal itself chokes on a parent it cannot decode at all.
    unparsable = write_commit_object(scratch_repo, "garbage\n")
    with pytest.raises(gitoxide.GitoxideError, match="during traversal"):
        repo.commits(child_of(unparsable, "child"))

    # The traversal gets past a commit whose header is well-formed enough for
    # it, but decoding it fully for Python fails.
    bad_header = write_commit_object(
        scratch_repo,
        f"tree {tree}\nauthor {SIGNATURE}\ncommitter {SIGNATURE}\nnot-a-header\n\nmsg\n",
    )
    with pytest.raises(gitoxide.GitoxideError, match="object parsing failed"):
        repo.commits(child_of(bad_header, "child"))


def test_signature_without_timestamp(scratch_repo):
    repo = gitoxide.open(str(scratch_repo))
    tree = repo.head_commit().tree_id
    oid = write_commit_object(
        scratch_repo,
        f"tree {tree}\nauthor Ada <ada@example.com>\n"
        "committer Ada <ada@example.com>\n\nno time\n",
    )
    author = repo.commit(oid).author
    assert (author.name, author.email) == ("Ada", "ada@example.com")
    assert (author.time, author.offset) == (0, 0)


def test_non_utf8_bytes_are_decoded_lossily(scratch_repo):
    repo = gitoxide.open(str(scratch_repo))
    tree = repo.head_commit().tree_id
    oid = write_commit_object(
        scratch_repo,
        f"tree {tree}\nauthor ".encode()
        + b"J\xf6rg <joerg@example.com> 1577836800 +0100\n"
        + f"committer {SIGNATURE}\n\n".encode()
        + b"caf\xe9\n",
    )
    commit = repo.commit(oid)
    assert commit.author.name == "J�rg"
    assert commit.author.offset == 3600
    assert commit.message == "caf�\n"
    assert commit.summary == "caf�"
    assert commit.parents == []
