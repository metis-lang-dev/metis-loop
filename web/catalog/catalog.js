/* The CATALOG panel's list (catalog-sdk s-bc1718e3): one component for both
   consoles, the metis-loop console and the metis-agent console (py and Go
   backends). It lives in metis-loop web/catalog/ (the shared web widgets);
   the loop SDK carries the same bytes (metis_loop_sdk/widget, a link here, its
   wheel the files), served from the installed SDK at /sdk/catalog/catalog.js
   — the user's one exception to
   copies-only, kept to the catalog panel. Its rows are the SDK's catalog
   index() (the loop console) or listing() (the agent console): the domains
   first, with their display line and what each has; a row with `shared`
   is METIS_HOME's (a package the catalog root lacks): a shared tag.

   MetisCatalog.render(box, rows, opts) fills box with the list:
     opts.tags      the `has` keys shown as tags, in order (default host notch readme)
     opts.tagTitle  (d, key, on) -> the tag's title
     opts.key       (d) -> the row's data-dom (default d.path || d.name)
     opts.current   (d) -> true for the open row (class cur)
     opts.title     (d) -> the row's title
     opts.display   show the display name beside the name when it differs
     opts.decorate  (d, parts) -> called per domain row before it is put
                    together: parts.lead (before the tags), parts.head
                    (after them), parts.acts (the right-hand actions),
                    parts.after (below the line) are arrays to push nodes into
     opts.onOpen    (d) -> a click or Enter/Space on a row (never on its
                    README or its actions)
     opts.head      a text line above the domains ("" = none)
     opts.others    list the non-domain catalogs, folded (the loop console)
     opts.othersHead (n) -> the fold's summary
     opts.foot      a text line under the list ("" = none)
     opts.empty     the text when there are no rows
   Shell styles (.dlist .dm/.tag/.cat …) are the console's shell.css; this
   component's own are catalog.css beside it. */
(function () {
  'use strict';
  function el(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      e.setAttribute(k, v === true ? '' : String(v));
    }
    for (const k of kids.flat()) if (k !== null && k !== undefined && k !== '') e.append(k instanceof Node ? k : String(k));
    return e;
  }
  const TAGS = ['host', 'notch', 'readme'];
  function tagTitle(d, k, on) {
    if (k === 'host') return d.host || (on ? 'it has a host' : 'no host');
    if (k === 'notch') return d.notch || (on ? 'it has a notch' : 'no notch');
    if (k === 'readme') return d.readme || (on ? 'it has a README' : 'no README');
    return on ? `it has ${k}` : `no ${k}`;
  }
  function render(box, rows, opts) {
    const o = opts || {};
    rows = rows || [];
    box.replaceChildren();
    if (!rows.length) {
      box.append(el('div', { class: 'empty' }, o.empty ?? 'No catalog list from the backend yet.'));
      return;
    }
    const key = o.key || (d => d.path || d.name);
    const open = (e, d) => {
      if (!o.onOpen || e.target.closest('summary,.rd,.acts,button,a,input')) return;
      if (e.type === 'keydown') {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        if (e.target !== e.currentTarget) return;
        e.preventDefault();
      }
      o.onOpen(d);
    };
    const doms = rows.filter(d => d.kind !== 'catalog');
    const cats = rows.filter(d => d.kind === 'catalog');
    if (o.head) box.append(el('div', { class: 'ph' }, typeof o.head === 'function' ? o.head(doms) : o.head));
    const list = el('div', { class: 'dlist' });
    for (const d of doms) {
      const parts = { lead: [], head: [], acts: [], after: [] };
      if (o.decorate) o.decorate(d, parts);
      const tags = (o.tags || TAGS).filter(k => d.has && k in d.has).map(k => {
        const on = !!d.has[k];
        return el('span', { class: on ? 'tag' : 'tag off', title: (o.tagTitle || tagTitle)(d, k, on) }, k);
      });
      const hd = el('div', { class: 'hd' }, el('span', { class: 'nm' }, d.name),
        o.display && d.display && d.display !== d.name ? el('span', { class: 'empty' }, d.display) : null,
        d.shared ? el('span', { class: 'tag shared', title: "a shared package: METIS_HOME's (the catalog has none of this name)" }, 'shared') : null,
        ...parts.lead, ...tags, ...parts.head,
        parts.acts.length ? el('span', { class: 'acts' }, ...parts.acts) : null);
      const row = el('div', {
        class: 'dm' + (o.current && o.current(d) ? ' cur' : ''), 'data-dom': key(d), tabindex: 0, role: 'button',
        title: o.title ? o.title(d) : null,
      }, hd, d.line ? el('div', { class: 'ln' }, d.line) : null, ...parts.after,
        d.readme_text ? el('details', {}, el('summary', {}, 'README'), el('div', { class: 'rd' }, d.readme_text)) : null);
      row.addEventListener('click', e => open(e, d));
      row.addEventListener('keydown', e => open(e, d));
      list.append(row);
    }
    if (o.others && cats.length) {
      const fold = el('details', { style: 'margin-top:6px' },
        el('summary', {}, o.othersHead ? o.othersHead(cats.length) : `other catalogs (${cats.length}) — the program alone`));
      for (const d of cats) {
        const c = el('div', { class: 'cat', 'data-dom': key(d), tabindex: 0, role: 'button', title: `open ${d.path}.llp` },
          el('span', { class: 'nm' }, d.path), el('span', { class: 'ln' }, d.line || ''));
        c.addEventListener('click', e => open(e, d));
        c.addEventListener('keydown', e => open(e, d));
        fold.append(c);
      }
      list.append(fold);
    }
    if (o.foot) list.append(el('div', { class: 'foot empty' }, o.foot));
    box.append(list);
  }
  window.MetisCatalog = { render, el, version: '0.1.0' };
})();
