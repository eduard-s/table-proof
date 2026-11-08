"""Apply only PR986's ref-remapping change to the pinned benchmark installation."""
# ruff: noqa: E501 -- Exact upstream lines must remain byte-identical for the patch.

from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path

from benchmarks.common import ROOT, sha256, write_json
from benchmarks.reproduce_docling import AFFECTED, FIXED

OLD = """                            # update rich table cells references:
                            if isinstance(parent_item, TableItem):
                                for table_cell in parent_item.data.table_cells:
                                    if isinstance(table_cell, RichTableCell) and table_cell.ref.cref == item.self_ref:
                                        table_cell.ref.cref = new_cref
                                        break

"""
ANCHOR = "            # rewrite FloatingItem explicit refs starting from start_indices to avoid corrupting items from prior calls\n"
NEW = """            # Remap rich table cell references of tables added in this call.
            # This must run after traversal, using the old->new ref map: rewriting
            # a cell ref in place while iterating would alias a new ref onto a
            # not-yet-remapped old ref whenever the index already holds items.
            # E.g. concatenating a doc whose first rich group is assigned the
            # new ref #/groups/1 while a later group of the same doc still
            # holds the old ref #/groups/1 would swap the two cells' contents.
            for table_item in self.tables[start_indices["tables"] :]:
                for table_cell in table_item.data.table_cells:
                    if isinstance(table_cell, RichTableCell):
                        new_cell_cref = orig_ref_to_new_ref.get(table_cell.ref.cref)
                        if new_cell_cref is not None:
                            table_cell.ref.cref = new_cell_cref
"""


def apply() -> dict:
    import docling_core.types.doc.document as module

    dist = importlib.metadata.distribution("docling-core")
    if AFFECTED not in (dist.read_text("direct_url.json") or ""):
        raise RuntimeError(f"Install affected commit {AFFECTED} first")
    path = Path(module.__file__).resolve()
    if not path.is_relative_to((ROOT / ".venv").resolve()):
        raise RuntimeError(
            "This helper only changes benchmarks/.venv, never your project environment"
        )
    original = path.read_text()
    if original.count(OLD) != 1 or original.count(ANCHOR) != 1:
        raise RuntimeError("Upstream source differs from the pinned patch target")
    record = {
        "source_url": f"https://github.com/docling-project/docling-core/pull/986/files/{FIXED}",
        "patch_commit": FIXED,
        "base_commit": AFFECTED,
        "unpatched_module_sha256": sha256(path),
        "patch_helper_sha256": sha256(Path(__file__)),
        "description": "Only PR986's rich-cell-reference hunk, applied to the same installed base commit.",
    }
    path.write_text(original.replace(OLD, "").replace(ANCHOR, NEW + ANCHOR))
    record["patched_module_sha256"] = sha256(path)
    write_json(ROOT / "fixtures" / "docling_5198" / "applied_fix.json", record)
    return record


if __name__ == "__main__":
    print(json.dumps(apply(), indent=2))
