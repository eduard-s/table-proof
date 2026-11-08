# Deferred publication

PyPI publication is deferred to a separate release round. The current work prepares and tests local distributions.

The proposed distribution name is `table-proof`. The Python import is `table_proof`. The command is `table-proof`.

A repository name does not reserve a registry name. Examine registry ownership before the first publication.

## Local distribution

```sh
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*
python3 -m venv .venv-wheel
.venv-wheel/bin/python -m pip install dist/*.whl
.venv-wheel/bin/python -m table_proof --version
.venv-wheel/bin/python scripts/wheel_smoke.py
```

The wheel smoke test uses the recorded regression pair. It needs only the runtime dependencies.

## Next release round

1. Examine the final package name and version.
2. Complete the remaining dataset review.
3. Examine the CI results and distribution contents.
4. Configure a PyPI trusted publisher for this repository.
5. Add a publication workflow after that configuration.
6. Publish a release with a matching version and tag.
7. Install the public distribution in a new environment.

The current CI workflow creates test artifacts. It does not publish packages.
