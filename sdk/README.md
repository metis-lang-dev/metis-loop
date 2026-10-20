# metis-loop-sdk

The metis loop SDK: the code that has to stay the same in every consumer of
the catalog. Its consumers are metis-loop's human loop, metis-agent's domain
agent and metis-agentic-loop's tools. It holds:

- `metis_loop_sdk.catalog`: catalog access, the one validated write
  (`apply`, `edit`, `take`), the catalog widget;
- `metis_loop_sdk.models`: the model adapters.

Each has a JSON CLI (`python -m metis_loop_sdk.<module>`). A TypeScript face,
`metis_loop_sdk/ts/catalog.ts`, ships in the wheel.

```sh
pip install metis-loop-sdk            # Python 3.10+; metispy and metis-catalog come with it
pip install -e ../metis-loop/sdk      # development, beside the sibling checkouts (install them -e first)
```

Installed alone, the catalog it reads is the metis-catalog wheel's (read-only);
set `METIS_CATALOG` to a checkout or a scratch copy for the writes (`apply`,
`edit`, `take`). `python -m metis_loop_sdk.catalog ts --json` prints where the
TypeScript face is (`dir`): a node consumer imports it from there.

## Releasing

The SDK goes to PyPI from GitHub by trusted publishing (metis-loop's
`.github/workflows/publish.yml`, metispy's flow; no token anywhere): bump
`version` in `pyproject.toml` and `metis_loop_sdk.__version__`, commit,
`gh release create sdk-vX.Y.Z` (the tag must be `sdk-v` + that version: the
workflow refuses any other); the tag's push publishes straight through (the
`pypi` environment has no required reviewer). The run builds the sdist and
the wheel from `sdk/`, smoke-installs the wheel in a fresh venv outside the
checkout with metispy and metis-catalog from PyPI (`tools/smoke_wheel.sh`;
ci.yml's sdk-alone job runs it on every push, with the metis-catalog
checkout) and uploads. `workflow_dispatch` is the dry run: everything but
the upload.

Apache License 2.0 (see `LICENSE`, `NOTICE`).
