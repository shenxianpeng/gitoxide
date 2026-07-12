# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial PyO3 bindings to the gitoxide (`gix`) engine.
- `Repository` with `open`, `discover`, `init`, `git_dir`, `workdir`,
  `is_bare`, `is_shallow`, `head_id`, `head_name`, `head_is_detached`,
  `head_commit`, `rev_parse`, `commit`, `commits`, `references`, `branches`,
  `tags`, and `read_blob`.
- `Commit`, `Signature`, and `Reference` value types.
- `GitoxideError` exception type.
- Type stubs (`_gitoxide.pyi`) and a `py.typed` marker.
- CI: test matrix (Linux/macOS/Windows × CPython 3.9/3.12), `rustfmt`/`clippy`
  lint, wheel builds, and a maturin-based PyPI publish workflow.
