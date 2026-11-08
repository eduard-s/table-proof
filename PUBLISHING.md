# Publish TableProof

The distribution name is `table-proof`. The Python import is `table_proof`. The command is `table-proof`.

Version `0.1.0` is an alpha release. The current benchmark does not establish broad accuracy.

PyPI publication is not complete. The first release needs a pending trusted publisher for this repository.

## Local distribution

```sh
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*
.venv/bin/python scripts/examine_distribution.py
python3 -m venv .venv-wheel
.venv-wheel/bin/python -m pip install dist/*.whl
.venv-wheel/bin/python -m table_proof --version
.venv-wheel/bin/python scripts/wheel_smoke.py
```

The wheel smoke test uses the recorded regression pair. It needs only the runtime dependencies.

The archive examination rejects cache files, model weights, symbolic links, and unexpected paths. The source archive contains only selected project files.

## Configure the first publication

1. Sign in to the PyPI account that will own `table-proof`.
2. Open [PyPI Publishing](https://pypi.org/manage/account/publishing/).
3. Add a pending GitHub publisher with these values:

| Field | Value |
| --- | --- |
| PyPI project name | `table-proof` |
| GitHub owner | `eduard-s` |
| GitHub repository | `table-proof` |
| Workflow filename | `publish-python.yml` |
| Environment | `pypi` |

4. Create the `pypi` environment in this repository's GitHub settings.
5. Examine the environment rules for the release account.

The ToolBoundary publisher does not authorize this repository. This workflow uses GitHub OIDC and needs no stored PyPI token.

A pending publisher does not reserve the package name. Read the [PyPI guide](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

## Rehearse the release

1. Open the repository's **Actions** page.
2. Select **Publish Python**.
3. Select **Run workflow** on `main`.
4. Examine the distribution job and its artifacts.

A manual run makes and examines the distributions. It does not publish them. Publication starts only from a pushed version tag.

## Publish version 0.1.0

After the publisher configuration and release examination, run these commands:

```sh
git switch main
git pull --ff-only
git tag v0.1.0
git push origin v0.1.0
```

The tag must match the version in `pyproject.toml`. The workflow runs tests before publication.

The publish job uses the exact distribution artifacts from the successful preparation job. It runs separately from the package tests.

Read the [PyPI publication guide](https://docs.pypi.org/trusted-publishers/using-a-publisher/) for the authentication process.

## Examine the public package

After publication, run these commands from the repository root:

```sh
python3 -m venv .venv-published
.venv-published/bin/python -m pip install --index-url https://pypi.org/simple 'table-proof==0.1.0'
.venv-published/bin/python -m table_proof --version
.venv-published/bin/python scripts/wheel_smoke.py
```

After publication, examine the PyPI page. Add its link to the README, profile, and website. Keep benchmark limitations visible.
