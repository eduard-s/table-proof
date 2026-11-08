# Contribute

## Install

Use Python 3.12 for development. From the repository root, run:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

## Before a commit

```sh
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src/table_proof
.venv/bin/pytest --cov=table_proof --cov-report=term-missing
.venv/bin/python -m benchmarks.run \
  --methods tableproof token_multiset_control structural_validity_control \
  --output artifacts/local-benchmark.json
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*
```

The default tests do not download model weights. Read the [vision guide](docs/VISION.md) for a real-model run.

## Add a defect case

1. Reduce the source to the smallest useful public example.
2. Record its license and attribution.
3. Record the extractor version and exact command.
4. Preserve the actual extracted output.
5. Label the wrong cells against the original source.
6. Add a correct control from the same layout.
7. Record unsupported evidence explicitly.

Do not submit confidential documents. Use an authorized public source or an independent synthetic reproduction.

## Change a detector

Add a regression test that fails before the change. Include a correct table that exercises the same rule.

Keep uncertain evidence separate from an error finding. A broader detector must not silently convert uncertainty to success.

Update the architecture and report documents when behavior changes. Write short sentences with one meaning per term.

## Dependencies

Keep heavy model packages in the vision extra. Keep model downloads explicit.

For the measured competitor comparison, use the isolated benchmark lock file. Do not replace a competitor with a local approximation.
