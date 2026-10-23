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


def test_version():
    """__version__ is derived from installed package metadata, not hard-coded."""
    assert isinstance(gitoxide.__version__, str)
    assert gitoxide.__version__ != "0.0.0+unknown"


def test_blame(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    hunks = repo.blame("file.txt")

    # file.txt is "one\ntwo\n": line 1 came from "add file", line 2 from the
    # commit that appended it.
    assert len(hunks) == 2
    assert [h.start_line for h in hunks] == [1, 2]
    assert all(h.line_count == 1 for h in hunks)
    assert all(isinstance(h, gitoxide.BlameHunk) for h in hunks)

    summaries = [repo.commit(h.commit_id).summary for h in hunks]
    assert summaries == ["add file", "second line"]


def test_blame_hunk_fields(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    hunk = repo.blame("README.md")[0]

    assert len(hunk.commit_id) == 40
    assert hunk.short_id == hunk.commit_id[:7]
    assert hunk.end_line == hunk.start_line + hunk.line_count - 1
    assert hunk.orig_start_line >= 1
    assert "BlameHunk(lines=" in repr(hunk)


def test_blame_at_rev(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    # Before the second line existed, file.txt was a single line.
    hunks = repo.blame("file.txt", "HEAD~1")
    assert len(hunks) == 1
    assert hunks[0].start_line == 1
    assert repo.commit(hunks[0].commit_id).summary == "add file"


def test_blame_missing_path_raises(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    with pytest.raises(gitoxide.GitoxideError):
        repo.blame("does-not-exist.txt")


def test_repr_and_str(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    head = repo.head_commit()

    git_dir = str(repo.git_dir).replace("\\", "\\\\")  # Rust's Debug escaping
    assert repr(repo) == 'Repository(git_dir="{}", bare=false)'.format(git_dir)
    assert repr(head) == 'Commit(id={}, summary="second line")'.format(head.short_id)
    assert repr(head.author) == (
        'Signature(name="Ada Lovelace", email="ada@example.com", time=1577836800)'
    )
    assert str(head.author) == "Ada Lovelace <ada@example.com>"

    ref = next(r for r in repo.references() if r.name == "refs/heads/main")
    assert repr(ref) == 'Reference(name="refs/heads/main", target=Some("{}"))'.format(
        head.id
    )


def test_commit_inequality(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    assert repo.commit("HEAD") != repo.commit("HEAD~1")
    assert hash(repo.commit("HEAD")) != hash(repo.commit("HEAD~1"))


def test_signature_offset(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    assert repo.head_commit().author.offset == 0
    assert repo.head_commit().committer.offset == 0


@pytest.mark.parametrize(
    "call",
    [
        lambda repo: repo.rev_parse("no-such-rev"),
        lambda repo: repo.commit("no-such-rev"),
        lambda repo: repo.commits("no-such-rev"),
        lambda repo: repo.read_blob("no-such-rev:README.md"),
        lambda repo: repo.blame("README.md", "no-such-rev"),
    ],
)
def test_bad_revspec_raises(sample_repo, call):
    repo = gitoxide.open(str(sample_repo))
    with pytest.raises(gitoxide.GitoxideError, match="couldn't parse revision"):
        call(repo)


def test_commit_rejects_non_commit_objects(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    with pytest.raises(gitoxide.GitoxideError, match="kind tree"):
        repo.commit("HEAD^{tree}")
    with pytest.raises(gitoxide.GitoxideError, match="kind blob"):
        repo.commit("HEAD:README.md")


def test_read_blob_rejects_non_blob_objects(sample_repo):
    repo = gitoxide.open(str(sample_repo))
    with pytest.raises(gitoxide.GitoxideError, match="kind commit"):
        repo.read_blob("HEAD")


def test_discover_outside_any_repo_raises(tmp_path):
    with pytest.raises(gitoxide.GitoxideError, match="Could not find a git repository"):
        gitoxide.discover(str(tmp_path))
    with pytest.raises(gitoxide.GitoxideError):
        gitoxide.discover(str(tmp_path / "does-not-exist"))


def test_init_refuses_existing_repo_and_files(sample_repo, tmp_path):
    with pytest.raises(gitoxide.GitoxideError, match="Refusing to initialize"):
        gitoxide.init(str(sample_repo))
    with pytest.raises(gitoxide.GitoxideError, match="Refusing to initialize"):
        gitoxide.init(str(sample_repo), bare=True)

    not_a_dir = tmp_path / "file"
    not_a_dir.write_text("")
    with pytest.raises(gitoxide.GitoxideError):
        gitoxide.init(str(not_a_dir))
    with pytest.raises(gitoxide.GitoxideError):
        gitoxide.init(str(not_a_dir), bare=True)


def test_static_constructors_match_module_functions(sample_repo, tmp_path):
    assert gitoxide.Repository.open(str(sample_repo)).git_dir.samefile(
        sample_repo / ".git"
    )
    assert gitoxide.Repository.discover(str(sample_repo)).git_dir.samefile(
        sample_repo / ".git"
    )
    assert gitoxide.Repository.init(str(tmp_path / "new")).is_bare is False
    assert gitoxide.Repository.init(str(tmp_path / "new.git"), bare=True).is_bare
