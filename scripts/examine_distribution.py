"""Reject unexpected files and unsafe paths before distribution upload."""

from __future__ import annotations

import argparse
import stat
import tarfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT_FILES = {
    ".gitignore",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "PKG-INFO",
    "PUBLISHING.md",
    "README.md",
    "THIRD_PARTY.md",
    "pyproject.toml",
}
BLOCKED_PARTS = {
    ".git",
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "artifacts",
    "build",
    "dist",
    "downloads",
}
WEIGHT_SUFFIXES = {".bin", ".ckpt", ".h5", ".hdf5", ".onnx", ".pt", ".pth", ".safetensors"}


def safe_path(name: str) -> PurePosixPath:
    """Examine paths without extraction or filesystem normalization."""
    parts = name.rstrip("/").split("/")
    if (
        not name
        or name.startswith("/")
        or "\\" in name
        or PureWindowsPath(name).drive
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ValueError(f"Unsafe archive path: {name!r}")
    path = PurePosixPath(*parts)
    if any(
        part in BLOCKED_PARTS or part.startswith(".venv") or part.endswith("-cache")
        for part in path.parts
    ):
        raise ValueError(f"Cache or scratch path: {name!r}")
    if path.suffix.lower() in WEIGHT_SUFFIXES:
        raise ValueError(f"Model weight file: {name!r}")
    return path


def source_allowed(path: PurePosixPath) -> bool:
    """Keep the source archive within the explicit package contents."""
    parts = path.parts
    if len(parts) == 1:
        return path.name in ROOT_FILES
    if parts[:2] == ("src", "table_proof"):
        return path.suffix == ".py" or path.as_posix() == "src/table_proof/py.typed"
    if parts[0] == "tests":
        return path.suffix == ".py"
    if parts[0] == "spec":
        return len(parts) == 2 and path.suffix == ".json"
    if parts[0] == "scripts":
        return len(parts) == 2 and path.suffix == ".py"
    if parts[0] == "docs":
        return path.suffix == ".md" or (
            parts[:2] == ("docs", "assets") and len(parts) == 3 and path.suffix == ".json"
        )
    if parts[:2] == ("benchmarks", "fixtures"):
        return path.suffix in {".json", ".md", ".pdf"}
    if parts[0] == "benchmarks" and len(parts) == 2:
        return path.suffix in {".py", ".md", ".txt"} or path.name in {
            "DOCLING_LICENSE",
            "results.json",
        }
    return False


def wheel_allowed(path: PurePosixPath, metadata_dir: str) -> bool:
    if path.parts[0] == "table_proof":
        return path.suffix == ".py" or path.as_posix() == "table_proof/py.typed"
    if path.parts[0] != metadata_dir:
        return False
    return path.as_posix() in {
        f"{metadata_dir}/{name}"
        for name in ("METADATA", "WHEEL", "RECORD", "entry_points.txt", "licenses/LICENSE")
    }


def directory_allowed(path: PurePosixPath, *, wheel: bool, metadata_dir: str) -> bool:
    parts = path.parts
    if not parts:
        return not wheel
    if wheel:
        return parts[0] == "table_proof" or path.as_posix() in {
            metadata_dir,
            f"{metadata_dir}/licenses",
        }
    return (
        parts[0] in {"tests", "docs"}
        or path.as_posix() in {"src", "spec", "scripts", "benchmarks"}
        or parts[:2] in {("src", "table_proof"), ("benchmarks", "fixtures")}
    )


def examine_distribution(archive: Path, name: str, version: str) -> int:
    """Return the file count, or raise ValueError for a rejected archive."""
    normalized_name = name.replace("-", "_")
    metadata_dir = f"{normalized_name}-{version}.dist-info"
    source_root = f"{normalized_name}-{version}"
    seen: set[str] = set()
    files: set[str] = set()

    def examine_entry(raw_name: str, *, directory: bool, regular: bool, wheel: bool) -> None:
        path = safe_path(raw_name)
        if path.as_posix() in seen:
            raise ValueError(f"Duplicate archive path: {raw_name!r}")
        seen.add(path.as_posix())
        if not regular and not directory:
            raise ValueError(f"Link or special file: {raw_name!r}")
        if not wheel:
            if path.parts[0] != source_root:
                raise ValueError(f"Unexpected source root: {raw_name!r}")
            path = PurePosixPath(*path.parts[1:])
        if directory:
            if not directory_allowed(path, wheel=wheel, metadata_dir=metadata_dir):
                raise ValueError(f"Unexpected distribution directory: {raw_name!r}")
            return
        allowed = wheel_allowed(path, metadata_dir) if wheel else source_allowed(path)
        if not allowed:
            raise ValueError(f"Unexpected distribution file: {raw_name!r}")
        files.add(path.as_posix())

    if archive.name.endswith(".whl"):
        with zipfile.ZipFile(archive) as wheel:
            for member in wheel.infolist():
                mode = member.external_attr >> 16
                examine_entry(
                    member.filename,
                    directory=member.is_dir() and not stat.S_ISLNK(mode),
                    regular=stat.S_IFMT(mode) in {0, stat.S_IFREG},
                    wheel=True,
                )
        required = {
            "table_proof/__init__.py",
            "table_proof/py.typed",
            f"{metadata_dir}/METADATA",
            f"{metadata_dir}/WHEEL",
            f"{metadata_dir}/RECORD",
            f"{metadata_dir}/licenses/LICENSE",
        }
    elif archive.name.endswith(".tar.gz"):
        with tarfile.open(archive, "r:gz") as source:
            for member in source:
                examine_entry(
                    member.name,
                    directory=member.isdir(),
                    regular=member.isfile(),
                    wheel=False,
                )
        required = {"pyproject.toml", "README.md", "LICENSE", "src/table_proof/__init__.py"}
    else:
        raise ValueError(f"Unsupported distribution: {archive}")
    if absent := required - files:
        raise ValueError(f"Missing distribution files: {sorted(absent)}")
    return len(files)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "archives", type=Path, nargs="*", help="Archives to examine. Default: dist/*"
    )
    args = parser.parse_args()
    archives = args.archives or sorted(Path("dist").glob("*"))
    if not archives:
        parser.error("No distribution archives found. Make the distributions first.")
    project_file = Path(__file__).resolve().parents[1] / "pyproject.toml"
    project = tomllib.loads(project_file.read_text())["project"]
    for archive in archives:
        try:
            count = examine_distribution(archive, project["name"], project["version"])
        except (ValueError, OSError, tarfile.TarError, zipfile.BadZipFile) as error:
            parser.exit(1, f"Rejected {archive}: {error}\n")
        print(f"Accepted {archive}: {count} files, no links or unexpected paths.")


if __name__ == "__main__":
    main()
