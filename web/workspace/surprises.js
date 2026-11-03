/* The SURPRISES widget (loop-workspace step 4; WORKSPACE.md §4, §6), over the backend's `surprise` channel: the
   workspace's surprises with their status (open · taken · ruled), and the drop dialog. A drop comes from a REPL
   session (its member and trace, k its last tick) or from a trace (a tick or a window the TRACE widget marked); the
   person says what was seen (a reading) or what should have held (atoms: `+a`, `-b`), and in words why. The pi
   loop takes it from .metis/surprises/; nothing here judges.

     const s = MetisSurprises.mount(box, io, {onRuling: id => …, session: () => sid})
     s.draft({run, member, k, window}) | s.draft({session})   opens the dialog filled in
     s.refresh()

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
  const WATCH = new Set(['surprise', 'take', 'retake', 'ruling', 'not_judged', 'release', 'judging']);
  function snap(box) {          // what the person is typing survives a re-render (a push redraws the widget)
    const out = new Map();
    for (const i of box.querySelectorAll('input[name],textarea[name],input[data-v],input[data-f]')) {
      out.set(i.name || ('v:' + (i.dataset.v || i.dataset.f)), i.type === 'checkbox' ? i.checked : i.value);
    }
    const a = document.activeElement;
    return { out, focus: a && box.contains(a) ? (a.name || ('v:' + (a.dataset.v || a.dataset.f))) : null };
  }
  function unsnap(box, s) {
    for (const i of box.querySelectorAll('input[name],textarea[name],input[data-v],input[data-f]')) {
      const k = i.name || ('v:' + (i.dataset.v || i.dataset.f));
      if (!s.out.has(k)) continue;
      if (i.type === 'checkbox') i.checked = s.out.get(k); else i.value = s.out.get(k);
      if (k === s.focus) i.focus();
    }
  }
  function mount(box, io, opts) {
    const o = opts || {};
    let rows = [], draft = null, note = '';
    box.classList.add('mw', 'mw-surprises');
    function where(r) {
      const t = r.trace ? r.trace.replace(/^traces\//, '') : null;
      const at = r.window ? `k ${r.window[0]}..${r.window[1]}` : r.k !== undefined && r.k !== null ? `k ${r.k}` : '';
      return [t, at].filter(Boolean).join(' · ') || 'no trace';
    }
    function row(r) {
      const ruled = r.status === 'ruled';
      return el('div', { class: 'mw-srow' },
        el('span', { class: 'mw-badge ' + (ruled ? 'ok' : r.status === 'taken' ? 'info' : 'warn') }, r.status),
        el('span', { class: 'mono' }, r.id), el('b', {}, r.member), el('span', { class: 'empty' }, where(r)),
        r.words ? el('div', { class: 'mw-words' }, r.words) : null,
        r.trace_note ? el('div', { class: 'warn' }, r.trace_note) : null,
        r.taken ? el('div', { class: 'empty' }, `taken by pid ${r.taken.pid} at ${r.taken.ts}`) : null,
        ruled && o.onRuling ? el('button', { class: 'btn', onclick: () => o.onRuling(r.id) }, 'the ruling') : null);
    }
    function dialog() {
      if (!draft) return null;
      const d = draft;
      const from = d.session ? `the session ${d.session}` : `the trace ${d.run}, member ${d.member}`;
      return el('form', { class: 'mw-form mw-drop', onsubmit: e => { e.preventDefault(); drop(e.target); } },
        el('div', { class: 'mw-sub' }, 'DROP A SURPRISE — from ' + from),
        d.session ? null : el('label', {}, 'member', el('input', { name: 'member', value: d.member || '' })),
        el('label', { title: 'the tick it is about; a window instead when two ticks are given' }, 'k',
          el('input', { name: 'k', class: 'mw-num', value: d.k ?? '' })),
        el('label', {}, 'window', el('input', { name: 'w0', class: 'mw-num', value: d.window ? d.window[0] : '' }), '..',
          el('input', { name: 'w1', class: 'mw-num', value: d.window ? d.window[1] : '' })),
        el('label', { title: 'what should have held at the tick, as metis.trace case writes it: +atom / -atom, comma-separated' },
          'atoms', el('input', { name: 'atoms', placeholder: '+brake_late, -accel', value: '' })),
        el('label', { title: 'what was seen, in a line (the reading the record carries)' }, 'reading',
          el('input', { name: 'reading', placeholder: 'what happened', value: d.reading || (d.fired && d.fired.length ? 'fired: ' + d.fired.join(' ') : '') })),
        el('label', { class: 'mw-wide' }, 'words', el('textarea', { name: 'words', rows: 3, placeholder: 'what should have happened, and why: the pi loop reads this first' })),
        el('div', { class: 'mw-acts' },
          el('button', { class: 'btn', type: 'submit' }, 'drop to the loop'),
          el('button', { class: 'btn', type: 'button', onclick: () => { draft = null; render(); } }, 'cancel')));
    }
    function render(fresh) {
      const sid = o.session ? o.session() : null;
      const kept = fresh ? null : snap(box);
      box.replaceChildren(
        el('div', { class: 'mw-row' },
          el('span', { class: 'empty' }, rows.length ? `${rows.filter(r => r.status === 'open').length} open · ${rows.filter(r => r.status === 'taken').length} taken · ${rows.filter(r => r.status === 'ruled').length} ruled` : ''),
          el('span', { class: 'mw-grow' }),
          el('button', { class: 'btn', disabled: !sid, title: sid ? 'a surprise from the open session (its trace, its last tick)' : 'open a session first', onclick: () => api.draft({ session: sid }) }, 'drop from the session'),
          el('button', { class: 'btn', onclick: refresh }, '↻')),
        dialog() || '',
        rows.length ? el('div', { class: 'mw-list' }, rows.slice().reverse().map(row))
          : el('div', { class: 'empty' }, 'No surprises in .metis/surprises/. Drop one from a session, or mark a tick in TRACE.'),
        note ? el('div', { class: 'empty' }, note) : '');
      if (kept) unsnap(box, kept);
    }
    async function refresh() {
      try { rows = (await io.ask('surprise', 'list')).surprises || []; note = ''; } catch (e) { note = e.message; }
      render();
    }
    async function drop(form) {
      const f = new FormData(form);
      const num = k => { const v = String(f.get(k) || '').trim(); return v === '' ? null : parseInt(v, 10); };
      const msg = {};
      if (draft.session) msg.session = draft.session;
      else { msg.run = draft.run; msg.member = String(f.get('member') || draft.member || ''); }
      const k = num('k'), w0 = num('w0'), w1 = num('w1');
      if (k !== null) msg.k = k;
      if (w0 !== null && w1 !== null) msg.window = [w0, w1];
      const atoms = String(f.get('atoms') || '').split(',').map(x => x.trim()).filter(Boolean);
      if (atoms.length) msg.atoms = atoms;
      const reading = String(f.get('reading') || '').trim();
      if (reading) msg.reading = reading;
      const words = String(f.get('words') || '').trim();
      if (words) msg.words = words;
      try {
        const r = await io.ask('surprise', 'drop', msg);
        note = 'dropped ' + r.id + ': the pi loop takes it from .metis/surprises/';
        draft = null;
        render(true);
      } catch (e) { note = e.message; }
      refresh();
    }
    const api = {
      refresh,
      render: () => render(),
      draft(d) { draft = Object.assign({}, d); note = ''; render(true); const f = box.querySelector('textarea[name=words]'); if (f) f.focus(); },
    };
    io.on('surprise', 'dropped', () => refresh());
    io.on('loop', 'event', f => { if (f.row && WATCH.has(f.row.kind)) refresh(); });
    render();
    refresh();
    return api;
  }
  window.MetisSurprises = { mount };
})();
