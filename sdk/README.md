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
pip install -e ../metis-loop/sdk      # development, beside the sibling checkouts
pip install "metis-loop-sdk @ git+https://github.com/metis-lang-dev/metis-loop@sdk-vX.Y.Z#subdirectory=sdk"
```

It needs metispy and metis-catalog installed first.

Apache License 2.0 (see `LICENSE`, `NOTICE`).
