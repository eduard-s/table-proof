# TableProof development benchmark

This small corpus tests a specific failure: table text survives, but its row association changes.
It does not prove broad accuracy, model quality, or user demand.

## Corpus and source records

The corpus has three separate groups:

- **Real library reproducer:** one affected result and one controlled fixed result from installed `docling-core` code.
- **Real source PDF:** two actual Docling extractions of one table from a public CC BY 2.0 paper.
- **Synthetic controls:** fourteen cases from one generated table layout. These include correct tables, wrong associations, missing text, and unsupported inputs.

The real-library pair is not a real-source-PDF dataset. Its PDF and coordinates come from our fixture generator.
The original private invoice is not included. Both cases share one source PDF.

[Docling issue 5198](https://github.com/docling-project/docling/issues/5198) reports the real invoice failure.
[Docling-core PR 986](https://github.com/docling-project/docling-core/pull/986) supplies its mechanism and a small reproducer.
The benchmark adapts that reproducer. It adds known PDF coordinates and dose values.

The affected package is `docling-core` 2.106.0 from commit
`3e3be95e9de7472e78da2068ae2b281e4dd34611`.
Its `concatenate` call changes the referenced first-column values from `BBB, CCC` to `CCC, BBB`.
Cached `cell.text` values remain correct. An auditor must resolve the references to examine the rendered result.

The fixed control uses the same installed commit and dependencies.
`patch_docling.py` applies only the reference-remapping change from PR commit
`bef3c28565c623537d0723b0d3d04f5af8d56c41`.
It changes only the isolated benchmark environment. It records source hashes before and after the patch.
The PR branch itself reports a different package version. This controlled patch avoids that confound.

Each `*.manifest.json` records source and extraction hashes, gold errors, licenses, and source links.
The real-library records also include package versions, archive hashes, and resolved cells.
Generated fixtures use the project MIT license. The upstream reproducer and patch use the Docling-core MIT license.
See [THIRD_PARTY.md](THIRD_PARTY.md).

## Real public PDF

[Mukabana and colleagues (2012)](https://doi.org/10.1007/s10886-012-0088-8) supply the real source table.
The publisher permits reuse under [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/).
The original PDF, source attribution, and hashes are in `fixtures/docling_5136/`.
Its printed Table 2 is on PDF page 6. Upstream issue 5136 calls the same table Table 1.

`page6.pdf` is an unchanged page copy. `table2.pdf` keeps the table text, fonts, geometry, and rules.
The preparation script removes text and graphics outside the table region.
This declared source excerpt prevents a table-only baseline from treating surrounding prose as missing content.
No table value is generated or repaired.

Docling 2.145.0 runs its actual layout and TableFormer models on that excerpt.
Both cases use identical model revisions, CPU settings, and package versions except `docling-parse`:

- Version 7.24.2 loses six species headings.
- Version 7.20.0 keeps the headings but loses the superscript `a` after `0.38` in the `SB (LDPE)` / `Other spp.` cell.

Both outputs contain a real error. The older version is not a clean negative control.
The real-source false-positive rate therefore has a zero denominator and remains null.
TableProof flags the missing headings. It returns uncertainty for the older output and does not diagnose that lost superscript.
This miss remains in the recall denominator.

`gold.json` is an AI-assisted visual transcription of all 64 cells, with significance letters preserved.
A second AI visual pass examines the header and first data row. This is not independent human annotation.
`*.runtime.json` records actual package versions, model revisions, weight hashes, and pipeline settings.
The stored JSON and Markdown are actual Docling outputs without cell repairs.

To repeat this extraction, create a separate environment:

```sh
python3.12 -m venv benchmarks/.venv-extraction
benchmarks/.venv-extraction/bin/python -m pip install -r benchmarks/requirements-extraction-lock.txt
benchmarks/.venv/bin/python -m benchmarks.prepare_public_pdf
benchmarks/.venv-extraction/bin/python -m benchmarks.reproduce_public_pdf --parser-version 7.24.2
benchmarks/.venv-extraction/bin/python -m pip install --no-deps 'docling-parse==7.20.0'
benchmarks/.venv-extraction/bin/python -m benchmarks.reproduce_public_pdf --parser-version 7.20.0
```

The first run downloads public model weights at pinned revisions.
The `--full-page` option stores the complete original page output as separate diagnostic evidence.
It does not add the page as another independent benchmark sample.

## Run the stored corpus

Run these commands from the repository root with Python 3.12:

```sh
python3.12 -m venv benchmarks/.venv
benchmarks/.venv/bin/python -m pip install -r benchmarks/requirements-lock.txt
PYTHONPATH=src benchmarks/.venv/bin/python -m benchmarks.run
PYTHONPATH=src benchmarks/.venv/bin/python -m pytest tests/test_benchmark.py -q
```

The lock file records the measured environment. Some binary wheels depend on the operating system.
The recorded run uses macOS arm64. This benchmark does not claim a second-platform run.
No model download or network request occurs during the stored-corpus evaluation.

`results.json` contains all case outcomes. `results.md` gives the same counts in a table.
The command returns a nonzero exit status if a method raises an error.
Missing methods remain in the report as execution errors. The runner never replaces a missing competitor with a local imitation.

## Reproduce the real library bug

Installation from the lock file starts with the affected, unpatched upstream commit.
To restore that state after a fixed-control run:

```sh
benchmarks/.venv/bin/python -m pip install --no-deps --force-reinstall 'docling-core @ https://github.com/docling-project/docling-core/archive/3e3be95e9de7472e78da2068ae2b281e4dd34611.zip'
benchmarks/.venv/bin/python -m benchmarks.reproduce_docling --variant affected
benchmarks/.venv/bin/python -m benchmarks.patch_docling
benchmarks/.venv/bin/python -m benchmarks.reproduce_docling --variant fixed
benchmarks/.venv/bin/python -m benchmarks.make_synthetic
PYTHONPATH=src benchmarks/.venv/bin/python -m benchmarks.run
```

The scripts stop if the installed commit or actual behavior differs from the expected case.
The fixed-control script also compares the installed module hash with the patch record.
The PDF generator fixes its metadata timestamp. Fixture text and geometry remain explicit in the generator.

## Baselines and scoring

`tableproof` runs the local geometry auditor with vision disabled.
`token_multiset_control` and `structural_validity_control` are our simple controls.
They are not implementations of a competing package.

`pdfmux_numeric_literals` calls the installed [pdfmux public API](https://github.com/NameetP/pdfmux/blob/5662a29c634b24bf02f162e0d18ced9ecf8f0fd4/src/pdfmux/verifier.py)
at commit `5662a29c634b24bf02f162e0d18ced9ecf8f0fd4` (version 1.8.7).
It uses its own PDF extraction, default thresholds, and the optional numeric-literal signal.
The adapter resolves Docling rich-cell references and supplies page Markdown to that API.
It does not supply ground-truth text to the competitor.
TableProof receives Docling JSON with geometry. The competitor receives its supported Markdown format.
These inputs and method statuses differ. Flag precision is not a score for correct error diagnosis.

For pdfmux, a page verdict of `review` or `fail` counts as a document flag.
If its pages contain only `pass` and `unverifiable`, with at least one `unverifiable` page, the result counts as an abstention.
The stored manifest preserves the original page and document verdicts.

The paired reproducer has very short pages. pdfmux flags both variants for low confidence.
Thus its positive flag is not evidence that it found the row swap.
These short pages are a limitation of this comparison. Do not claim a broad win from this pair.

Metrics use one case/document as the unit:

- Precision = flagged erroneous cases / all flagged cases.
- Recall = flagged erroneous cases / all erroneous cases.
- False-positive rate = flagged correct cases / all correct cases.
- Abstention rate = uncertain cases / all cases.
- Review burden = review or uncertain cases / all cases.

Abstentions and execution errors stay in the recall and false-positive-rate denominators.
Execution errors also have their own count and exception details.
A zero denominator produces `null`, not zero.
These rates do not measure whether every wrong cell was found.
The report also gives handoff burden, which adds execution errors to review burden.

The cases are correlated and small. No confidence interval or general accuracy claim is justified.
The corpus is a development set. It is not an untouched test set.

## Next dataset work

Add independent public PDFs before a broad comparison or release claim.

1. Extend the source-paper group beyond the one table from [issue 5136](https://github.com/docling-project/docling/issues/5136).
   Keep actual PDF hashes, license statements, parser versions, and real model outputs.
   Do not label reconstructed cells as extractor output.
2. Select a fixed public-paper sample before model or threshold changes.
   Include correct output, blank cells, repeated values, spanning headers, and multiple-page tables.
3. Get two independent human labels for row and column associations. Record disagreements and resolve them before scoring.
4. Keep that group separate from synthetic mutations and library reproducers.
5. Report cell-localization metrics, source crop evidence, review time, latency, and abstention rates.
6. Evaluate the optional vision path in its own group with exact model revisions and cached weights.
   Its scores must not be described as calibrated error probabilities without a calibration study.

The [PubTables-1M repository](https://github.com/microsoft/table-transformer) supplies another possible evaluation source.
Examine the dataset license and document-level splits before use. The repository is archived.
