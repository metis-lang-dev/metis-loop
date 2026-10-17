# web/ — the shared web widgets

Front-end components that more than one console shows, kept in one place
instead of copied (the user's exception to copies-only, 2026-10-17; each
console's shell, shell.css/shell.js, stays its own copy).

| widget | what | served at |
|---|---|---|
| `catalog/` | the CATALOG panel's list: `catalog.js` (`MetisCatalog.render`) and `catalog.css` (catalog-sdk s-bc1718e3) | `/sdk/catalog/` — by the metis-loop console and the metis-agent console (py and Go) |

The loop SDK (`sdk/`, `metis_loop_sdk`) carries these bytes to its pip
consumers: `sdk/metis_loop_sdk/widget` is a link to `web/catalog/`, and the
wheel built from the checkout holds the files (`metis_loop_sdk.catalog.WIDGET_DIR`).
