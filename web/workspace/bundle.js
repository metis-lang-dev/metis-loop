/* The BUNDLE widget (loop-workspace step 4; WORKSPACE.md §6), over the backend's `bundle` channel: the workspace's
   composition, its members, the image of the last `metisc build`, STALE with why, and the session's reload (the
   two-users ruling: STALE → reload, nothing pushed into a running session).

     const b = MetisBundle.mount(box, io, {session: () => sid})   session: the REPL session a reload re-opens
     b.refresh()

   Copy with io.js and workspace.css (copies, not dependencies). */
(function () {
  'use strict';
  function el(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? '' : String(v));
    }
    for (const k of kids.flat()) if (k !== null && k !== undefined && k !== '') e.append(k instanceof Node ? k : String(k));
    return e;
  }
  function mount(box, io, opts) {
    const o = opts || {};
    let b, note = '';
    box.classList.add('mw', 'mw-bundle');
    function render() {
      box.replaceChildren();
      if (b === undefined) { box.append(el('div', { class: 'empty' }, 'reading the bundle…')); return; }
      if (b === null) {
        box.append(el('div', { class: 'empty' }, 'No bundle here: the workspace has no domains/composition.yaml (the REPL still serves one package at a time).'));
        return;
      }
      const sid = o.session ? o.session() : null;
      const golden = b.golden ? (b.image && b.golden.startsWith(b.image.slice(0, 12)) ? 'the image is image.golden' : 'image.golden is ' + b.golden.slice(0, 12)) : 'no image.golden';
      box.append(
        el('div', { class: 'mw-row' }, el('b', {}, b.name), ' ', el('span', { class: 'empty' }, b.composition),
          el('span', { class: 'mw-grow' }),
          el('span', { class: 'mw-badge ' + (b.stale ? 'warn' : 'ok'), title: b.why || 'every member is older than the build record' }, b.stale ? 'STALE' : 'built')),
        el('div', { class: 'mw-kv' },
          el('span', {}, 'members'), el('span', {}, (b.members || []).join(' · ') || '—'),
          el('span', {}, 'image'), el('span', { class: 'mono' }, b.image ? b.image.slice(0, 16) : '(not built)'),
          el('span', {}, 'golden'), el('span', {}, golden),
          el('span', {}, 'build'), el('span', { class: 'mono' }, b.build || '—'),
          el('span', {}, 'config'), el('span', { class: 'mono' }, b.config ? b.config.split('/').slice(-2).join('/') : '—'),
          b.stale ? el('span', {}, 'why') : null, b.stale ? el('span', { class: 'warn' }, b.why || '') : null),
        el('div', { class: 'mw-acts' },
          el('button', { class: 'btn', onclick: refresh }, 'refresh'),
          el('button', {
            class: 'btn', disabled: !sid,
            title: sid ? 'the session re-opened on what is built now (epoch + 1)' : 'open a session first',
            onclick: () => reload(sid),
          }, 'reload the session')),
        note ? el('div', { class: 'empty' }, note) : null);
    }
    async function refresh() {
      try { b = (await io.ask('bundle', 'state')).bundle; note = ''; } catch (e) { note = e.message; b = b === undefined ? null : b; }
      render();
    }
    async function reload(sid) {
      note = 'reloading…'; render();
      try { await io.ask('bundle', 'reload', { session: sid }); note = 'reloaded: the session is on the files as they are now'; } catch (e) { note = e.message; }
      refresh();
    }
    io.on('bundle', 'stale', f => { b = f.bundle; note = f.bundle && f.bundle.stale ? 'a member changed after the build' : 'built again'; render(); });
    render();
    refresh();
    return { refresh, render };
  }
  window.MetisBundle = { mount };
})();
