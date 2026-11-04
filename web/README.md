# web/ — the shared web widgets

Front-end components that more than one console shows, kept in one place
instead of copied (the user's exception to copies-only, 2026-10-17; each
console's shell, shell.css/shell.js, stays its own copy).

| widget | what | served at |
|---|---|---|
| `catalog/` | the CATALOG panel's list: `catalog.js` (`MetisCatalog.render`) and `catalog.css` (catalog-sdk s-bc1718e3) | `/sdk/catalog/` — by the metis-loop console and the metis-agent console (py and Go) |
| `workspace/` | the workspace panels (loop-workspace s-5b4be5fa step 4, docs/WORKSPACE.md §6): `bundle.js`, `trace.js`, `rulings.js`, `loop.js` (`MetisBundle`/`MetisTrace`/`MetisRulings`/`MetisLoop`.mount(box, io, opts); `loop.js` is the CHAT and draws a ruling with `MetisRulings.card(g)`, loop-chat step 1, docs/CHAT.md §1), the wire they share `io.js` (`MetisIO.make(send)`: `ask`, `on`, `feed` over the host's own socket) and `workspace.css`. Each speaks one of the backend's channels (loop/workspace_ch.py). They are the pi loop's ONE frontend (WORKSPACE.md §6.1), served to this console on every workspace: never copied into another page, the road page included (a host page frames the served page, `?panels=chat`) | `/sdk/workspace/` — by the metis-loop console only |

The loop SDK (`sdk/`, `metis_loop_sdk`) carries these bytes to its pip
consumers: `sdk/metis_loop_sdk/widget` is a link to `web/catalog/` and
`sdk/metis_loop_sdk/workspace` one to `web/workspace/`, and the wheel built from the
checkout holds the files (`metis_loop_sdk.web.WIDGET_DIR`, `WS_WIDGET_DIR`;
`python -m metis_loop_sdk.web workspace` lists them).
