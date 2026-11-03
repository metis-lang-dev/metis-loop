/* The TRACE widget (loop-workspace step 4; WORKSPACE.md §6), over the backend's `trace` channel: the workspace's
   runs, a run's k range and checkpoints, the Tick table at k (counts, the rules fired, the atoms made:
   metis.trace.timeline), step ±1 and jump, the declared trace verbs as buttons with their own arguments (nothing a
   verb does not declare), and "mark here", which hands a surprise draft to the host.

     const t = MetisTrace.mount(box, io, {onMark: ({run, member, k, window}) => …})
     t.refresh(); t.open(run)

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
    const s = { runs: [], run: null, trace: null, member: null, k: null, tick: null, tools: null, tool: null, out: null, note: '', mark0: null };
    box.classList.add('mw', 'mw-trace');
    const val = (id) => box.querySelector(`[data-f="${id}"]`);

    function header() {
      return el('div', { class: 'mw-row' },
        el('select', { 'aria-label': 'run', onchange: e => open(e.target.value) },
          el('option', { value: '' }, s.runs.length ? 'a run…' : 'no traces in .metis/traces/'),
          s.runs.map(r => el('option', { value: r.run, selected: r.run === s.run }, `${r.run} (${r.segments} seg)`))),
        s.trace ? el('select', { 'aria-label': 'member', onchange: e => { s.member = e.target.value; go(s.k); } },
          Object.keys(s.trace.header.members || {}).sort().map(m => el('option', { value: m, selected: m === s.member }, m))) : null,
        el('span', { class: 'mw-grow' }),
        el('button', { class: 'btn', onclick: refresh, title: 'the runs again' }, '↻'));
    }
    function nav() {
      if (!s.trace) return null;
      const t = s.trace;
      return el('div', { class: 'mw-row' },
        el('button', { class: 'btn', onclick: () => go(s.k - 1), disabled: s.k <= t.k0 }, '◀'),
        el('input', {
          'data-f': 'k', type: 'number', min: t.k0, max: t.k1, value: s.k ?? t.k0, 'aria-label': 'tick', class: 'mw-num',
          onkeydown: e => { if (e.key === 'Enter') go(parseInt(e.target.value, 10)); },
        }),
        el('button', { class: 'btn', onclick: () => go(s.k + 1), disabled: s.k >= t.k1 }, '▶'),
        el('button', { class: 'btn', onclick: () => go(parseInt(val('k').value, 10)) }, 'jump'),
        el('span', { class: 'empty' }, `k ${t.k0}..${t.k1} · checkpoints ${t.checkpoints.join(' ')}`),
        el('span', { class: 'mw-grow' }),
        el('button', { class: 'btn', title: 'start a window here; the next mark closes it', onclick: () => { s.mark0 = s.k; render(); } },
          s.mark0 === null ? 'from here' : `from ${s.mark0}`),
        el('button', { class: 'btn mw-mark', title: 'draft a surprise at this tick (or the window from the marked tick)', onclick: mark }, 'mark here'));
    }
    function table() {
      const t = s.tick;
      if (!t) return el('div', { class: 'empty' }, s.trace ? 'pick a tick' : 'open a run');
      const counts = Object.entries(t.counts || {}).sort((a, b) => a[0].localeCompare(b[0]));
      const made = new Set(t.made || []);
      return el('div', { class: 'mw-tick' },
        el('div', { class: 'mw-sub' }, `TICK ${t.k} · ${t.member}`, t.exact ? '' : el('span', { class: 'warn', title: 'no program: the rules\' effects are not applied, the state is exact only at a checkpoint' }, ' (state approximate)')),
        el('div', { class: 'mw-kv' },
          el('span', {}, 'fired'), el('span', {}, t.fired && t.fired.length ? t.fired.map(r => el('span', { class: 'mw-rule' }, r)) : el('span', { class: 'empty' }, 'nothing')),
          el('span', {}, 'made'), el('span', {}, made.size ? [...made].sort().join(' ') : el('span', { class: 'empty' }, 'nothing'))),
        el('table', { class: 'mw-counts' },
          el('tbody', {}, counts.map(([a, n]) => el('tr', { class: made.has(a) ? 'made' : null }, el('td', {}, a), el('td', {}, String(n)))))));
    }
    function verbs() {
      if (!s.tools) return null;
      const t = s.tools.find(x => x.name === s.tool);
      const props = t ? t.parameters.properties : {};
      const need = new Set(t ? t.parameters.required : []);
      const pre = { trace: s.run ? 'traces/' + s.run : '', trace_a: s.run ? 'traces/' + s.run : '', member: s.member || '', k: s.k ?? '', at: s.k ?? '' };
      return el('details', { class: 'mw-verbs', open: !!s.tool },
        el('summary', {}, 'verbs (metis/trace_tools.json)'),
        el('div', { class: 'mw-row' }, s.tools.map(x => el('button', {
          class: 'chip', 'aria-pressed': x.name === s.tool ? 'true' : 'false', title: x.description,
          onclick: () => { s.tool = x.name === s.tool ? null : x.name; s.out = null; render(true); },
        }, x.name.replace(/^trace_/, '')))),
        t ? el('form', { class: 'mw-form', onsubmit: e => { e.preventDefault(); runVerb(t); } },
          Object.entries(props).map(([k, p]) => el('label', { title: p.description || '' }, k + (need.has(k) ? '*' : ''),
            p.type === 'BOOLEAN' ? el('input', { type: 'checkbox', 'data-v': k })
              : el('input', { 'data-v': k, value: pre[k] ?? '', placeholder: p.type === 'ARRAY' ? 'a, b, …' : p.type.toLowerCase() }))),
          el('button', { class: 'btn', type: 'submit' }, 'run ' + t.name)) : null,
        s.out ? el('pre', { class: 'mw-out' + (s.out.code ? ' err' : '') }, `exit ${s.out.code}\n${s.out.out || ''}${s.out.err ? '\n' + s.out.err : ''}`) : null);
    }
    function render(fresh) {
      const kept = fresh ? null : snap(box);
      box.replaceChildren(header(), nav() || '', table(), verbs() || '', s.note ? el('div', { class: 'empty' }, s.note) : '');
      if (kept) unsnap(box, kept);
    }
    async function refresh() {
      try {
        s.runs = (await io.ask('trace', 'list')).traces;
        if (!s.tools) s.tools = (await io.ask('trace', 'tools')).tools;
        s.note = '';
      } catch (e) { s.note = e.message; }
      render();
    }
    async function open(run) {
      s.run = run || null; s.trace = s.tick = null; s.mark0 = null;
      if (!run) return render();
      try {
        s.trace = (await io.ask('trace', 'open', { run })).trace;
        const ms = Object.keys(s.trace.header.members || {}).sort();
        if (!ms.includes(s.member)) s.member = ms[0];
        s.note = '';
        await go(s.trace.k0 + (s.trace.k1 > s.trace.k0 ? 1 : 0));
      } catch (e) { s.note = e.message; render(); }
    }
    async function go(k) {
      if (!s.trace || !Number.isInteger(k)) return;
      k = Math.max(s.trace.k0, Math.min(s.trace.k1, k));
      s.k = k;
      try { s.tick = await io.ask('trace', 'tick', { run: s.run, member: s.member, k }); s.note = ''; }
      catch (e) { s.tick = null; s.note = e.message; }
      render(true);
    }
    function mark() {
      if (!s.trace || s.k === null) return;
      const w = s.mark0 !== null && s.mark0 !== s.k ? [Math.min(s.mark0, s.k), Math.max(s.mark0, s.k)] : null;
      s.mark0 = null;
      render();
      if (o.onMark) o.onMark({ run: s.run, member: s.member, k: s.k, window: w, fired: (s.tick && s.tick.fired) || [] });
    }
    async function runVerb(t) {
      const args = {};
      for (const inp of box.querySelectorAll('[data-v]')) {
        const k = inp.dataset.v, p = t.parameters.properties[k];
        if (p.type === 'BOOLEAN') { if (inp.checked) args[k] = true; continue; }
        const v = inp.value.trim();
        if (!v) continue;
        args[k] = p.type === 'ARRAY' ? v.split(',').map(x => x.trim()).filter(Boolean)
          : p.type === 'INTEGER' ? parseInt(v, 10) : p.type === 'NUMBER' ? Number(v) : v;
      }
      s.out = { code: '…', out: 'running ' + t.name + '…' };
      render();
      try { s.out = await io.ask('trace', 'verb', { name: t.name, args }, 330000); }
      catch (e) { s.out = { code: 'refused', out: '', err: e.message }; }
      render();
    }
    render();
    refresh();
    return { refresh, open, go, state: () => ({ run: s.run, member: s.member, k: s.k }) };
  }
  window.MetisTrace = { mount };
})();
