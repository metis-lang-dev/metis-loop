# metis-loop-sdk

The metis loop SDK: the code that has to stay the same in every consumer of
the catalog. Its consumers are metis-loop's human loop, metis-agent's domain
agent and metis-agentic-loop's tools. It holds:

- `metis_loop_sdk.catalog`: catalog access, the one validated write
  (`apply`, `edit`, `take`), the catalog widget;
- `metis_loop_sdk.models`: the model adapters.

Each has a JSON CLI (`python -m metis_loop_sdk.<module>`). A TypeScript face,
`metis_loop_sdk/ts/catalog.ts`, ships in the wheel.

**The catalog root is the current directory**, as `cd DIR && claude` makes DIR
the project: `catalog.root()` is `$METIS_CATALOG`, else the cwd.

```sh
cd DIR && python -m metis_loop_sdk.catalog list --json      # DIR's domains/<name>/: an empty DIR lists nothing
cd DIR && python -m metis_loop_sdk.catalog apply lamp --program lamp.llp --json   # writes DIR/domains/lamp/
METIS_CATALOG=DIR python -m metis_loop_sdk.catalog list --json                     # the same, from elsewhere
```

Any directory is a catalog; `domains/` appears at the first write. The loops'
own state goes in `catalog.state()`, `DIR/.metis/` (made on demand, added to
DIR's `.gitignore` when DIR is a git checkout), and nothing under a dot
directory is a catalog. The intent generator is the root's `tools/intents.py`,
else the installed metis-catalog's; `metisc` is `$METISC`, else PATH. Nothing
is looked up beside a checkout.

```sh
# Python 3.10+; metispy and metis-catalog first (not on PyPI yet: their checkouts or git URLs)
pip install "metis-loop-sdk @ git+https://github.com/metis-lang-dev/metis-loop@sdk-vX.Y.Z#subdirectory=sdk"
pip install -e sdk/                   # development, in a metis-loop checkout (metispy and metis-catalog installed first)
```

`python -m metis_loop_sdk.catalog ts --json` prints where the TypeScript face
is (`dir`): a node consumer imports it from there.

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
