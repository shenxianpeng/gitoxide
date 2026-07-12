//! PyO3 bindings to the gitoxide (`gix`) engine.
//!
//! This crate exposes a small, ergonomic, GitPython-flavored surface over the
//! pure-Rust gitoxide implementation. The heavy lifting is done by `gix`; this
//! layer is only about translating types and errors to and from Python.

use std::path::PathBuf;

use gix::bstr::ByteSlice;
use pyo3::create_exception;
use pyo3::exceptions::PyException;
use pyo3::prelude::*;

create_exception!(
    _gitoxide,
    GitoxideError,
    PyException,
    "Base error for gitoxide operations."
);

/// Convert any error that implements `Display` into a `GitoxideError`.
fn err<E: std::fmt::Display>(e: E) -> PyErr {
    GitoxideError::new_err(e.to_string())
}

/// Lossily decode a git byte string (which is *usually* UTF-8) into a `String`.
fn bstr_to_string(b: &gix::bstr::BStr) -> String {
    b.to_str_lossy().into_owned()
}

// ---------------------------------------------------------------------------
// Signature
// ---------------------------------------------------------------------------

/// The authorship information attached to a commit (name, email, timestamp).
#[pyclass(module = "gitoxide._gitoxide", frozen)]
#[derive(Clone)]
struct Signature {
    #[pyo3(get)]
    name: String,
    #[pyo3(get)]
    email: String,
    /// Seconds since the Unix epoch.
    #[pyo3(get)]
    time: i64,
    /// UTC offset in seconds (east of UTC is positive).
    #[pyo3(get)]
    offset: i32,
}

#[pymethods]
impl Signature {
    fn __repr__(&self) -> String {
        format!(
            "Signature(name={:?}, email={:?}, time={})",
            self.name, self.email, self.time
        )
    }

    fn __str__(&self) -> String {
        format!("{} <{}>", self.name, self.email)
    }
}

impl Signature {
    fn from_ref(sig: &gix::actor::SignatureRef<'_>) -> Self {
        let time = sig.time().unwrap_or_default();
        Signature {
            name: bstr_to_string(sig.name),
            email: bstr_to_string(sig.email),
            time: time.seconds,
            offset: time.offset,
        }
    }
}

// ---------------------------------------------------------------------------
// Commit
// ---------------------------------------------------------------------------

/// A fully-decoded, owned view of a git commit.
#[pyclass(module = "gitoxide._gitoxide", frozen)]
#[derive(Clone)]
struct Commit {
    #[pyo3(get)]
    id: String,
    #[pyo3(get)]
    tree_id: String,
    #[pyo3(get)]
    message: String,
    #[pyo3(get)]
    author: Signature,
    #[pyo3(get)]
    committer: Signature,
    #[pyo3(get)]
    parents: Vec<String>,
}

#[pymethods]
impl Commit {
    /// The first line of the commit message.
    #[getter]
    fn summary(&self) -> String {
        self.message.lines().next().unwrap_or("").to_string()
    }

    /// Abbreviated (7-char) commit id, like `git log --oneline`.
    #[getter]
    fn short_id(&self) -> String {
        self.id.chars().take(7).collect()
    }

    fn __repr__(&self) -> String {
        format!(
            "Commit(id={}, summary={:?})",
            self.short_id(),
            self.summary()
        )
    }

    fn __eq__(&self, other: &Commit) -> bool {
        self.id == other.id
    }

    fn __hash__(&self) -> u64 {
        // Derive a stable hash from the hex id.
        let mut h: u64 = 1469598103934665603;
        for b in self.id.as_bytes() {
            h ^= *b as u64;
            h = h.wrapping_mul(1099511628211);
        }
        h
    }
}

impl Commit {
    fn from_gix(commit: &gix::Commit<'_>) -> PyResult<Self> {
        let commit_ref = commit.decode().map_err(err)?;
        Ok(Commit {
            id: commit.id().to_hex().to_string(),
            tree_id: commit_ref.tree().to_hex().to_string(),
            message: bstr_to_string(commit_ref.message.as_bstr()),
            author: Signature::from_ref(&commit_ref.author),
            committer: Signature::from_ref(&commit_ref.committer),
            parents: commit_ref
                .parents()
                .map(|id| id.to_hex().to_string())
                .collect(),
        })
    }
}

// ---------------------------------------------------------------------------
// Reference
// ---------------------------------------------------------------------------

/// A git reference (branch, tag, or other ref) and the object it points at.
#[pyclass(module = "gitoxide._gitoxide", frozen)]
#[derive(Clone)]
struct Reference {
    /// The full ref name, e.g. `refs/heads/main`.
    #[pyo3(get)]
    name: String,
    /// The short name, e.g. `main`.
    #[pyo3(get)]
    shorthand: String,
    /// The peeled target object id (hex), if the ref resolves to an object.
    #[pyo3(get)]
    target: Option<String>,
}

#[pymethods]
impl Reference {
    fn __repr__(&self) -> String {
        format!("Reference(name={:?}, target={:?})", self.name, self.target)
    }
}

// ---------------------------------------------------------------------------
// Repository
// ---------------------------------------------------------------------------

/// A handle to a git repository.
///
/// `gix::Repository` is `Send` but not `Sync` (its in-memory pack cache uses
/// interior mutability), so the handle is marked `unsendable`: it must be used
/// from the thread that created it. This matches how the object is accessed
/// under Python's GIL.
#[pyclass(module = "gitoxide._gitoxide", unsendable)]
struct Repository {
    inner: gix::Repository,
}

#[pymethods]
impl Repository {
    /// Open an existing repository at `path` (discovery is *not* performed;
    /// use :meth:`discover` to search parent directories).
    #[staticmethod]
    fn open(path: PathBuf) -> PyResult<Self> {
        let inner = gix::open(path).map_err(err)?;
        Ok(Repository { inner })
    }

    /// Discover a repository by searching `path` and its parents.
    #[staticmethod]
    fn discover(path: PathBuf) -> PyResult<Self> {
        let inner = gix::discover(path).map_err(err)?;
        Ok(Repository { inner })
    }

    /// Initialize a new repository at `path`.
    #[staticmethod]
    #[pyo3(signature = (path, bare = false))]
    fn init(path: PathBuf, bare: bool) -> PyResult<Self> {
        let inner = if bare {
            gix::init_bare(path).map_err(err)?
        } else {
            gix::init(path).map_err(err)?
        };
        Ok(Repository { inner })
    }

    /// The path to the `.git` directory.
    #[getter]
    fn git_dir(&self) -> PathBuf {
        self.inner.git_dir().to_path_buf()
    }

    /// The path to the working tree, or ``None`` for a bare repository.
    #[getter]
    fn workdir(&self) -> Option<PathBuf> {
        self.inner.workdir().map(|p| p.to_path_buf())
    }

    /// Whether this is a bare repository.
    #[getter]
    fn is_bare(&self) -> bool {
        self.inner.is_bare()
    }

    /// Whether this is a shallow clone.
    #[getter]
    fn is_shallow(&self) -> bool {
        self.inner.is_shallow()
    }

    /// The object id (hex) that ``HEAD`` currently points at, or ``None`` on an
    /// unborn branch.
    #[getter]
    fn head_id(&self) -> Option<String> {
        self.inner.head_id().ok().map(|id| id.to_hex().to_string())
    }

    /// The short name of the branch ``HEAD`` points at (e.g. ``main``), or
    /// ``None`` when ``HEAD`` is detached.
    #[getter]
    fn head_name(&self) -> PyResult<Option<String>> {
        let head = self.inner.head().map_err(err)?;
        Ok(head.referent_name().map(|n| n.shorten().to_string()))
    }

    /// Whether ``HEAD`` is detached (not pointing at a branch).
    #[getter]
    fn head_is_detached(&self) -> PyResult<bool> {
        let head = self.inner.head().map_err(err)?;
        Ok(head.is_detached())
    }

    /// The commit currently at ``HEAD``.
    fn head_commit(&self) -> PyResult<Commit> {
        let commit = self.inner.head_commit().map_err(err)?;
        Commit::from_gix(&commit)
    }

    /// Resolve a revspec (e.g. ``HEAD``, ``main``, ``@~2``, a hex id) to a
    /// single object id (hex).
    fn rev_parse(&self, spec: &str) -> PyResult<String> {
        let id = self.inner.rev_parse_single(spec).map_err(err)?;
        Ok(id.to_hex().to_string())
    }

    /// Look up a commit by id or revspec.
    fn commit(&self, rev: &str) -> PyResult<Commit> {
        let id = self.inner.rev_parse_single(rev).map_err(err)?;
        let commit = id.object().map_err(err)?.try_into_commit().map_err(err)?;
        Commit::from_gix(&commit)
    }

    /// Walk history starting at `rev` (default ``HEAD``), yielding commits in
    /// reverse-chronological order. Pass `max_count` to limit the number of
    /// commits returned.
    #[pyo3(signature = (rev = None, max_count = None))]
    fn commits(&self, rev: Option<&str>, max_count: Option<usize>) -> PyResult<Vec<Commit>> {
        let tip = match rev {
            Some(spec) => self.inner.rev_parse_single(spec).map_err(err)?.detach(),
            None => self.inner.head_id().map_err(err)?.detach(),
        };
        let platform = self.inner.rev_walk([tip]);
        let iter = platform.all().map_err(err)?;
        let mut out = Vec::new();
        for info in iter {
            let info = info.map_err(err)?;
            let commit = info.object().map_err(err)?;
            out.push(Commit::from_gix(&commit)?);
            if let Some(limit) = max_count {
                if out.len() >= limit {
                    break;
                }
            }
        }
        Ok(out)
    }

    /// All references in the repository.
    fn references(&self) -> PyResult<Vec<Reference>> {
        let platform = self.inner.references().map_err(err)?;
        let mut out = Vec::new();
        for r in platform.all().map_err(err)? {
            let mut r = r.map_err(err)?;
            out.push(reference_from_gix(&mut r));
        }
        Ok(out)
    }

    /// Local branch names (short form, e.g. ``main``).
    fn branches(&self) -> PyResult<Vec<String>> {
        let platform = self.inner.references().map_err(err)?;
        let mut out = Vec::new();
        for r in platform.local_branches().map_err(err)? {
            let r = r.map_err(err)?;
            out.push(r.name().shorten().to_string());
        }
        Ok(out)
    }

    /// Tag names (short form, e.g. ``v1.0.0``).
    fn tags(&self) -> PyResult<Vec<String>> {
        let platform = self.inner.references().map_err(err)?;
        let mut out = Vec::new();
        for r in platform.tags().map_err(err)? {
            let r = r.map_err(err)?;
            out.push(r.name().shorten().to_string());
        }
        Ok(out)
    }

    /// Read the raw bytes of a blob given its id or a revspec (e.g.
    /// ``HEAD:README.md``).
    fn read_blob(&self, rev: &str) -> PyResult<Vec<u8>> {
        let id = self.inner.rev_parse_single(rev).map_err(err)?;
        let object = id.object().map_err(err)?;
        let blob = object.try_into_blob().map_err(err)?;
        Ok(blob.data.clone())
    }

    fn __repr__(&self) -> String {
        format!(
            "Repository(git_dir={:?}, bare={})",
            self.inner.git_dir(),
            self.inner.is_bare()
        )
    }
}

/// Build a [`Reference`] from a `gix` reference, peeling it to an object id.
fn reference_from_gix(r: &mut gix::Reference<'_>) -> Reference {
    let name = r.name().as_bstr().to_str_lossy().into_owned();
    let shorthand = r.name().shorten().to_string();
    let target = r.peel_to_id().ok().map(|id| id.to_hex().to_string());
    Reference {
        name,
        shorthand,
        target,
    }
}

// ---------------------------------------------------------------------------
// Module-level conveniences
// ---------------------------------------------------------------------------

/// Open an existing repository at `path`.
#[pyfunction]
fn open(path: PathBuf) -> PyResult<Repository> {
    Repository::open(path)
}

/// Discover a repository by searching `path` and its parents.
#[pyfunction]
fn discover(path: PathBuf) -> PyResult<Repository> {
    Repository::discover(path)
}

/// Initialize a new repository at `path`.
#[pyfunction]
#[pyo3(signature = (path, bare = false))]
fn init(path: PathBuf, bare: bool) -> PyResult<Repository> {
    Repository::init(path, bare)
}

/// The version of the underlying `gix` engine, for diagnostics.
#[pyfunction]
fn gix_version() -> &'static str {
    "0.75"
}

#[pymodule]
fn _gitoxide(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Repository>()?;
    m.add_class::<Commit>()?;
    m.add_class::<Signature>()?;
    m.add_class::<Reference>()?;
    m.add_function(wrap_pyfunction!(open, m)?)?;
    m.add_function(wrap_pyfunction!(discover, m)?)?;
    m.add_function(wrap_pyfunction!(init, m)?)?;
    m.add_function(wrap_pyfunction!(gix_version, m)?)?;
    m.add("GitoxideError", m.py().get_type::<GitoxideError>())?;
    Ok(())
}
