"""Reject scratch files and archive links before a package upload."""

from __future__ import annotations

import io
import stat
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts.examine_distribution import examine_distribution

SOURCE_FILES = {
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "src/table_proof/__init__.py",
}
WHEEL_FILES = {
    "table_proof/__init__.py",
    "table_proof/py.typed",
    "table_proof-0.1.0.dist-info/METADATA",
    "table_proof-0.1.0.dist-info/WHEEL",
    "table_proof-0.1.0.dist-info/RECORD",
    "table_proof-0.1.0.dist-info/licenses/LICENSE",
}


def source_archive(tmp_path: Path, extra: tarfile.TarInfo | None = None) -> Path:
    path = tmp_path / "table_proof-0.1.0.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        for name in SOURCE_FILES:
            member = tarfile.TarInfo(f"table_proof-0.1.0/{name}")
            archive.addfile(member, io.BytesIO())
        if extra is not None:
            archive.addfile(extra, io.BytesIO())
    return path


def test_accepts_small_source_archive(tmp_path: Path) -> None:
    assert examine_distribution(source_archive(tmp_path), "table-proof", "0.1.0") == 4


@pytest.mark.parametrize(
    "name",
    [
        "table_proof-0.1.0/benchmarks/downloads/repeat.json",
        "table_proof-0.1.0/docs/model.safetensors",
        "table_proof-0.1.0/.venv/lib/secret.py",
        "table_proof-0.1.0/src/table_proof/__pycache__/cached.py",
        "table_proof-0.1.0/unrelated.py",
        "table_proof-0.1.0/../outside.py",
        "/table_proof-0.1.0/README.md",
        "C:/table_proof-0.1.0/README.md",
        "table_proof-0.1.0/src\\table_proof\\extra.py",
    ],
)
def test_rejects_unwanted_source_paths(tmp_path: Path, name: str) -> None:
    path = source_archive(tmp_path, tarfile.TarInfo(name))
    with pytest.raises(ValueError):
        examine_distribution(path, "table-proof", "0.1.0")


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE])
def test_rejects_source_links_and_special_files(tmp_path: Path, kind: bytes) -> None:
    member = tarfile.TarInfo("table_proof-0.1.0/src/table_proof/extra.py")
    member.type = kind
    member.linkname = "../../outside.py"
    path = source_archive(tmp_path, member)
    with pytest.raises(ValueError, match="Link or special file"):
        examine_distribution(path, "table-proof", "0.1.0")


def test_rejects_unexpected_source_directory(tmp_path: Path) -> None:
    member = tarfile.TarInfo("table_proof-0.1.0/unrelated")
    member.type = tarfile.DIRTYPE
    with pytest.raises(ValueError, match="Unexpected distribution directory"):
        examine_distribution(source_archive(tmp_path, member), "table-proof", "0.1.0")


@pytest.mark.parametrize("extra", ["symlink", "scratch", "duplicate", "none"])
def test_wheel_contents_and_links(tmp_path: Path, extra: str) -> None:
    path = tmp_path / "table_proof-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        for name in WHEEL_FILES:
            archive.writestr(name, "")
        if extra == "symlink":
            member = zipfile.ZipInfo("table_proof/extra.py")
            member.create_system = 3
            member.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(member, "../../outside.py")
        elif extra == "scratch":
            archive.writestr("benchmarks/downloads/extra.json", "{}")
        elif extra == "duplicate":
            with pytest.warns(UserWarning, match="Duplicate name"):
                archive.writestr("table_proof/__init__.py", "")
    if extra == "none":
        assert examine_distribution(path, "table-proof", "0.1.0") == len(WHEEL_FILES)
    else:
        with pytest.raises(ValueError):
            examine_distribution(path, "table-proof", "0.1.0")
