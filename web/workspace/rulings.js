/* The RULINGS widget (loop-workspace step 4; WORKSPACE.md §6), over the backend's `surprise` channel: a ruling as the
   person reads it before an apply. Beside the verdict: WHEN the candidate is first enabled and HOW OFTEN it fires
   on the trace (the brake_late lesson: accepted mechanically, refused by a person who sees it fire from tick 2 in
   most of the run), then the goldens moved by name, the lint rows, the readings the trace never carries, the spend,
   the pack, and the judge's document. The verdict is the gate's; nothing here moves it.

     const r = MetisRulings.mount(box, io, {})
     r.show(id)        the ruling of surprise ID
     r.refresh()       the list of ruled surprises
     MetisRulings.card(g)   the ruling as the CHAT's card (g: the surprise channel's `get` reply; loop-chat step 1)

   The shared frontend's (WORKSPACE.md §6.1): served to this console from the loop SDK, never copied into another page. */
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
  function firingsLine(r) {
    const f = r.firings;
    if (!f) return el('span', { class: 'empty' }, 'not in this ruling (judged before the count was kept)');
    if (!f.count) return el('span', { class: 'warn' }, 'never fires differently from the record on this trace: the ruling says nothing of its effect');
    const span = f.first === f.last ? `at k ${f.first}` : `from k ${f.first} to k ${f.last}`;
    return el('span', { class: f.rows > 1 ? 'warn' : '' },
      `${f.count} firing${f.count === 1 ? '' : 's'} in ${f.rows} of the ${f.of_rows} rows where the fired rules differ, ${span}`);
  }
  function enabledLine(r) {
    const e = r.first_enabled;
    if (!e) return el('span', { class: 'warn' }, r.inert ? 'never enabled: inert' : 'not in this ruling');
    return el('span', {}, `k ${e.k}: ${e.rule}` + (e.beside && e.beside.length ? ` (beside ${e.beside.join(', ')})` : ''));
  }
  function list(xs, empty) {
    return xs && xs.length ? el('span', {}, xs.map(x => el('div', {}, typeof x === 'string' ? x : JSON.stringify(x)))) : el('span', { class: 'empty' }, empty);
  }
  // The ruling as a CHAT card (loop-chat step 1, CHAT.md §1): the fields the person reads before an apply, the pack and
  // the judge's document folded under "show pack" / "show document". g: the `surprise get` reply.
  function card(g) {
    const s = g.surprise || {}, r = s.ruling || {};
    const ok = r.verdict === 'accepted';
    const fold = (label, text, cls) => text ? el('details', { class: 'mw-fold' }, el('summary', {}, label), el('pre', { class: cls }, text)) : null;
    return el('div', { class: 'mw-card mw-ruling-card' + (ok ? ' ok' : ' bad') },
      el('div', { class: 'mw-row' },
        el('span', { class: 'mw-badge ' + (ok ? 'ok' : 'bad') }, r.verdict || '?'),
        el('b', {}, s.member || ''), el('span', { class: 'mono empty' }, s.id || '')),
      ok && r.firings && r.firings.rows > 1 ? el('div', { class: 'warn mw-lesson' },
        'Accepted by the gate, mechanically: read when it fires and how often before you apply it.') : null,
      el('div', { class: 'mw-kv' },
        el('span', {}, 'first enabled'), enabledLine(r),
        el('span', {}, 'fires'), firingsLine(r),
        el('span', {}, 'goldens moved'), list(r.moved, 'none: the goldens held'),
        el('span', {}, 'lint'), list(r.lint, 'no rows'),
        el('span', {}, 'spent'), el('span', {}, r.spent ? Number(r.spent).toFixed(4) + ' USD' : '0 USD')),
      el('div', { class: 'mw-acts' },
        fold('show pack', g.pack, 'mw-out'),
        fold('show document', g.md, 'mw-doc')));
  }
  function mount(box, io, opts) {
    const o = opts || {};
    let ruled = [], cur = null, note = '';
    box.classList.add('mw', 'mw-rulings');
    function view() {
      if (!cur) return el('div', { class: 'empty' }, ruled.length ? 'pick a ruling' : 'No rulings yet: the pi loop writes them to .metis/rulings/.');
      const s = cur.surprise, r = s.ruling || {};
      const ok = r.verdict === 'accepted';
      return el('div', { class: 'mw-ruling' },
        el('div', { class: 'mw-row' },
          el('span', { class: 'mw-badge ' + (ok ? 'ok' : 'bad') }, r.verdict || '?'),
          el('b', {}, s.member), el('span', { class: 'mono' }, s.id), el('span', { class: 'empty' }, r.ts || '')),
        ok && r.firings && r.firings.rows > 1 ? el('div', { class: 'warn mw-lesson' },
          'Accepted by the gate, mechanically. Read when it fires and how often before you apply it: a rule that fires through most of the run is rarely the one asked for.') : null,
        el('div', { class: 'mw-kv' },
          el('span', {}, 'first enabled'), enabledLine(r),
          el('span', {}, 'fires'), firingsLine(r),
          el('span', {}, 'open loop after'), el('span', {}, r.open_loop_after !== undefined && r.open_loop_after !== null ? `k ${r.open_loop_after} (later rows are the candidate on recorded inputs, never the world's answer)` : '—'),
          el('span', {}, 'goldens moved'), list(r.moved, 'none'),
          el('span', {}, 'lint'), list(r.lint, 'no rows'),
          el('span', {}, 'reads absent'), list(r.reads_absent, 'none'),
          el('span', {}, 'spent'), el('span', {}, r.spent ? Number(r.spent).toFixed(4) + ' USD' : '0 USD'),
          el('span', {}, 'surprise'), el('span', {}, s.words || el('span', { class: 'empty' }, 'no words'))),
        cur.pack ? el('details', {}, el('summary', {}, 'the pack (packs/' + s.id + '.llp)'), el('pre', { class: 'mw-out' }, cur.pack)) : null,
        cur.md ? el('details', { open: true }, el('summary', {}, 'the ruling (rulings/' + s.id + '.md)'), el('pre', { class: 'mw-doc' }, cur.md)) : null);
    }
    function render() {
      box.replaceChildren(
        el('div', { class: 'mw-row' },
          el('select', { 'aria-label': 'ruling', onchange: e => e.target.value && show(e.target.value) },
            el('option', { value: '' }, ruled.length ? 'a ruling…' : 'none'),
            ruled.slice().reverse().map(x => el('option', { value: x.id, selected: cur && cur.surprise.id === x.id }, `${x.id} ${x.member} ${(x.ruling || {}).verdict || ''}`))),
          el('span', { class: 'mw-grow' }),
          el('button', { class: 'btn', onclick: refresh }, '↻')),
        view(),
        note ? el('div', { class: 'empty' }, note) : '');
    }
    async function refresh() {
      try {
        const all = (await io.ask('surprise', 'list', { status: 'ruled' })).surprises || [];
        ruled = all;
        note = '';
      } catch (e) { note = e.message; }
      render();
    }
    async function show(id) {
      try {
        const g = await io.ask('surprise', 'get', { id });
        cur = { surprise: g.surprise, md: g.md, pack: g.pack || null };
        note = '';
      } catch (e) { note = e.message; }
      render();
    }
    io.on('loop', 'event', f => { if (f.row && f.row.kind === 'ruling') refresh(); });
    render();
    refresh();
    return { refresh, show };
  }
  window.MetisRulings = { mount, card };
})();
