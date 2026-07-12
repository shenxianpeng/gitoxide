//! Build script: expose the *resolved* `gix` version to the crate as the
//! `GIX_VERSION` compile-time environment variable, so the binding can report
//! it accurately without hard-coding a value that drifts from `Cargo.lock`.

use std::path::Path;

fn main() {
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").unwrap_or_default();
    let lock_path = Path::new(&manifest_dir).join("Cargo.lock");
    println!("cargo:rerun-if-changed={}", lock_path.display());

    let version = std::fs::read_to_string(&lock_path)
        .ok()
        .and_then(|lock| gix_version_from_lock(&lock))
        .unwrap_or_else(|| "unknown".to_string());

    println!("cargo:rustc-env=GIX_VERSION={version}");
}

/// Find the `version` of the `[[package]] name = "gix"` entry in a Cargo.lock.
fn gix_version_from_lock(lock: &str) -> Option<String> {
    let mut lines = lock.lines();
    while let Some(line) = lines.next() {
        if line.trim() == r#"name = "gix""# {
            for next in lines.by_ref() {
                let next = next.trim();
                if let Some(rest) = next.strip_prefix("version = \"") {
                    return rest.strip_suffix('"').map(str::to_string);
                }
                if next.starts_with("[[package]]") {
                    break;
                }
            }
        }
    }
    None
}
