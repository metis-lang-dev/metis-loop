# web/ — the shared web widgets

Front-end components that more than one console shows, kept in one place
instead of copied (the user's exception to copies-only, 2026-10-17; each
console's shell, shell.css/shell.js, stays its own copy).

| widget | what | served at |
|---|---|---|
| `catalog/` | the CATALOG panel's list: `catalog.js` (`MetisCatalog.render`) and `catalog.css` (catalog-sdk s-bc1718e3) | `/sdk/catalog/` — by the metis-loop console and the metis-agent console (py and Go) |
| `workspace/` | the workspace panels (loop-workspace s-5b4be5fa step 4, docs/WORKSPACE.md §6): `bundle.js`, `trace.js`, `surprises.js`, `rulings.js`, `loop.js` (`MetisBundle`/`MetisTrace`/`MetisSurprises`/`MetisRulings`/`MetisLoop`.mount(box, io, opts)), the wire they share `io.js` (`MetisIO.make(send)`: `ask`, `on`, `feed` over the host's own socket) and `workspace.css`. Each speaks one of the backend's channels (loop/workspace_ch.py). A consumer page COPIES them (the road page next); they are not imported across repos | `/sdk/workspace/` — by the metis-loop console |

The loop SDK (`sdk/`, `metis_loop_sdk`) carries these bytes to its pip
consumers: `sdk/metis_loop_sdk/widget` is a link to `web/catalog/` and
`sdk/metis_loop_sdk/workspace` one to `web/workspace/`, and the wheel built from the
checkout holds the files (`metis_loop_sdk.web.WIDGET_DIR`, `WS_WIDGET_DIR`;
`python -m metis_loop_sdk.web workspace` lists them).
