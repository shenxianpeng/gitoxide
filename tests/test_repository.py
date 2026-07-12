import gitoxide
import pytest


def test_open_and_properties(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    assert repo.git_dir.name == ".git"
    assert repo.workdir is not None
    assert repo.workdir.samefile(sample_repo)
    assert repo.is_bare is False
    assert repo.is_shallow is False


def test_discover_from_subdir(sample_repo):
    sub = sample_repo / "sub" / "deep"
    sub.mkdir(parents=True)
    repo = gitoxide.discover(str(sub))
    assert repo.git_dir.samefile(sample_repo / ".git")


def test_open_missing_raises(tmp_path):
    with pytest.raises(gitoxide.GitoxideError):
        gitoxide.open(str(tmp_path))


def test_head(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    assert repo.head_name == "main"
    assert repo.head_is_detached is False
    assert repo.head_id is not None
    assert len(repo.head_id) == 40


def test_head_commit(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    head = repo.head_commit()
    assert isinstance(head, gitoxide.Commit)
    assert head.summary == "second line"
    assert head.message.startswith("second line")
    assert "with a body" in head.message
    assert head.author.name == "Ada Lovelace"
    assert head.author.email == "ada@example.com"
    assert head.author.time == 1577836800  # 2020-01-01T00:00:00 UTC
    assert head.short_id == head.id[:7]
    assert len(head.parents) == 1


def test_history_walk(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    commits = repo.commits()
    assert len(commits) == 3
    assert [c.summary for c in commits] == [
        "second line",
        "add file",
        "initial commit",
    ]
    # The last commit is the root and has no parents.
    assert commits[-1].parents == []


def test_history_max_count(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    commits = repo.commits(max_count=2)
    assert len(commits) == 2
    assert commits[0].summary == "second line"


def test_history_from_rev(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    commits = repo.commits("main")
    assert len(commits) == 3


def test_rev_parse(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    head = repo.rev_parse("HEAD")
    assert len(head) == 40
    assert repo.rev_parse("main") == head
    parent = repo.rev_parse("HEAD~1")
    assert parent != head
    assert repo.commit("HEAD~1").id == parent


def test_branches_and_tags(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    assert set(repo.branches()) == {"main", "dev"}
    assert repo.tags() == ["v1.0.0"]


def test_references(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    refs = {r.name: r for r in repo.references()}
    assert "refs/heads/main" in refs
    assert "refs/tags/v1.0.0" in refs
    assert refs["refs/heads/main"].shorthand == "main"
    assert len(refs["refs/heads/main"].target) == 40


def test_read_blob(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    content = repo.read_blob("HEAD:README.md")
    assert content == b"# hello\n"


def test_commit_equality_and_hash(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    a = repo.head_commit()
    b = repo.commit("HEAD")
    assert a == b
    assert hash(a) == hash(b)
    assert len({a, b}) == 1


def test_init_and_bare(tmp_path):
    repo = gitoxide.init(str(tmp_path / "plain"))
    assert repo.is_bare is False
    bare = gitoxide.init(str(tmp_path / "bare.git"), bare=True)
    assert bare.is_bare is True
    assert bare.workdir is None


def test_gix_version():
    assert isinstance(gitoxide.gix_version(), str)
