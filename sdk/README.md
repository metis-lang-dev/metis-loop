# metis-loop-sdk

The metis loop SDK: the code metis-agent and pi (`pi/`) share that is not the
catalog itself — the catalog API's TypeScript face, the catalog widget and the
model adapters. The catalog (`metis.catalog`) and the loop's policy over its
writes (`metis.gate`) are metispy's. It holds:

- `metis_loop_sdk.web`: the catalog widget the consoles serve (`WIDGET_DIR`,
  `WIDGET_URL`, `widget_file`) and where the TypeScript face is (`TS_DIR`):
  `metis_loop_sdk/ts/catalog.ts` and `ts/gate.ts`, metis.catalog's and
  metis.gate's faces for node (each call is one `python -m metis.catalog|gate … --json`);
- `metis_loop_sdk.models`: the model adapters.

Each has a JSON CLI (`python -m metis_loop_sdk.<module>`); `python -m
metis_loop_sdk.web ts` prints where the TypeScript face is (`dir`): a node
consumer imports it from there.

**Not a PyPI package.** The SDK is installed into a local python and used from
there: editable from a metis-loop checkout, or by its git tag. Nothing reaches
it by a python path (no `sys.path` / `PYTHONPATH` into `sdk/`).

```sh
# Python 3.10+; metispy (PyPI) first
pip install "metis-loop-sdk @ git+https://github.com/metis-lang-dev/metis-loop@sdk-vX.Y.Z#subdirectory=sdk"
pip install -e sdk/                   # development, in a metis-loop checkout
```

## Releasing

A release is a git tag, not an upload: bump `version` in `pyproject.toml` and
`metis_loop_sdk.__version__`, commit, `gh release create sdk-vX.Y.Z` (the tag
must be `sdk-v` + that version: publish.yml refuses any other). The tag's run
(metis-loop's `.github/workflows/publish.yml`) builds the sdist and the wheel
from `sdk/` and smoke-installs the wheel in a fresh venv outside the checkout
(`tools/smoke_wheel.sh`); ci.yml's sdk-alone job runs the same smoke on every
push. Consumers pin the tag's git URL.

Apache License 2.0 (see `LICENSE`, `NOTICE`).
