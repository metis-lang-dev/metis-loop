/* The LOOP widget (loop-workspace step 4; WORKSPACE.md §5.2, §6), over the backend's `loop` channel: the pi loop's
   state (who holds the workspace, its mode and model, the spend), start and stop of the backend's own child in rpc
   mode, the chat (the person's say, pi's words, its tool calls and results), the pending gate's plan with confirm
   and refuse, the budget line pi's extension adds to every tool reply past half the session's budget (spend, tool
   calls, model requests), and the journal as it is written. The TUI is the local seat, this the remote: one at a
   time (the lock).

     const l = MetisLoop.mount(box, io, {})
     l.refresh()

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
  const BUDGET = /\[budget: ([0-9.]+) of ([0-9.]+) USD spent; (\d+) tool calls, (\d+) model requests[^\]]*\]/;
  const MAX = 300;
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
    const s = { state: null, chat: [], journal: [], seen: 0, gate: null, budget: null, over: null, note: '', tab: 'chat' };
    box.classList.add('mw', 'mw-loop');
    function lockLine(k, l) {
      if (!l) return el('span', { class: 'empty' }, `${k}: none`);
      const more = ['mode', 'model', 'port'].filter(x => l[x] !== undefined && l[x] !== null).map(x => `${x} ${l[x]}`).join(', ');
      return el('span', { class: l.alive ? '' : 'warn' }, `${k}: pid ${l.pid}${more ? ' (' + more + ')' : ''}${l.alive ? '' : ' — gone (stale)'}`);
    }
    function stateBox() {
      const st = s.state;
      if (!st) return el('div', { class: 'empty' }, 'reading the loop…');
      const c = st.child, cost = st.cost || {};
      return el('div', { class: 'mw-kv' },
        el('span', {}, 'locks'), el('span', {}, lockLine('pi', st.loops.pi), ' · ', lockLine('backend', st.loops.backend)),
        el('span', {}, 'child'), el('span', {}, c ? `${c.state}, pid ${c.pid}${c.model ? ', ' + c.model : ''}${c.budget ? ', budget ' + c.budget + ' USD' : ''}` : el('span', { class: 'empty' }, 'none from this backend')),
        el('span', {}, 'spend'), el('span', {}, `${Number(cost.total || 0).toFixed(4)} USD in ${cost.calls || 0} paid calls (.metis/cost.jsonl)`),
        s.budget ? el('span', {}, 'budget') : null,
        s.budget ? el('span', { class: 'warn mw-budget' }, `${s.budget.spent} of ${s.budget.budget} USD spent · ${s.budget.calls} tool calls · ${s.budget.requests} model requests`) : null,
        s.over ? el('span', {}, 'over') : null,
        s.over ? el('span', { class: 'bad' }, `the session's budget is spent: ${Number(s.over.spent).toFixed(4)} of ${s.over.budget} USD; no further model turns`) : null);
    }
    function controls() {
      const c = s.state && s.state.child, running = c && c.state === 'running';
      const held = s.state && s.state.loops.pi && s.state.loops.pi.alive && !running;
      return el('form', { class: 'mw-row', onsubmit: e => { e.preventDefault(); start(e.target); } },
        el('input', { name: 'model', placeholder: "model (loop.sh's default)", 'aria-label': 'model', disabled: running }),
        el('input', { name: 'budget', class: 'mw-num', placeholder: 'USD', 'aria-label': 'budget in USD', title: 'the session budget (USD, above 0); none: loop.sh\'s default', disabled: running }),
        el('button', { class: 'btn', type: 'submit', disabled: running || held, title: held ? 'a pi loop (the TUI?) holds this workspace' : 'pi --mode rpc as this backend\'s child' }, 'start'),
        el('button', { class: 'btn', type: 'button', disabled: !running, onclick: stop }, 'stop'),
        el('span', { class: 'mw-grow' }),
        ['chat', 'journal'].map(t => el('button', { type: 'button', class: 'chip', 'aria-pressed': s.tab === t ? 'true' : 'false', onclick: () => { s.tab = t; render(); } }, t)));
    }
    function gateBox() {
      const g = s.gate;
      if (!g) return null;
      const p = g.plan || {};
      return el('div', { class: 'mw-gate' },
        el('div', { class: 'mw-sub' }, 'THE GATE — ' + (p.title || 'pi asks to write')),
        el('pre', { class: 'mw-out' }, p.message || JSON.stringify(p, null, 1)),
        el('div', { class: 'mw-acts' },
          el('button', { class: 'btn', onclick: () => answer('confirm') }, 'confirm'),
          el('button', { class: 'btn', onclick: () => answer('refuse') }, 'refuse')));
    }
    function chatBox() {
      const c = s.state && s.state.child, running = c && c.state === 'running';
      return el('div', { class: 'mw-chat' },
        el('div', { class: 'mw-log' }, s.chat.length ? s.chat.map(m => el('div', { class: 'mw-msg ' + m.cls }, m.who ? el('span', { class: 'mw-who' }, m.who) : null, m.text))
          : el('div', { class: 'empty' }, running ? 'say what to do: "take the next surprise"' : 'start the pi loop, or run pi/loop.sh in a terminal (the TUI); its words show here only from this backend\'s child, its journal in both')),
        el('form', { class: 'mw-row', onsubmit: e => { e.preventDefault(); say(e.target); } },
          el('input', { name: 'text', class: 'mw-grow', placeholder: running ? 'to the pi loop' : 'no pi loop runs from this backend', disabled: !running, 'aria-label': 'to the pi loop' }),
          el('button', { class: 'btn', type: 'submit', disabled: !running }, 'say')));
    }
    function journalBox() {
      return el('div', { class: 'mw-log mw-journal' }, s.journal.length ? s.journal.slice(-MAX).map(r => {
        const rest = Object.entries(r).filter(([k]) => !['ts', 'who', 'kind'].includes(k)).map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`).join(' ');
        return el('div', { class: 'mw-jrow who-' + r.who }, el('span', { class: 'empty' }, String(r.ts || '').slice(11, 19)), ' ', el('b', {}, r.who), ' ', r.kind, ' ', el('span', { class: 'empty' }, rest));
      }) : el('div', { class: 'empty' }, 'the journal is empty (.metis/loop/journal.jsonl)'));
    }
    function render() {
      const log = box.querySelector('.mw-log');
      const atEnd = !log || log.scrollTop + log.clientHeight >= log.scrollHeight - 24;
      const kept = snap(box);
      box.replaceChildren(stateBox(), controls(), gateBox() || '', s.tab === 'chat' ? chatBox() : journalBox(), s.note ? el('div', { class: 'empty' }, s.note) : '');
      unsnap(box, kept);
      const l2 = box.querySelector('.mw-log');
      if (l2 && atEnd) l2.scrollTop = l2.scrollHeight;
    }
    function push(cls, who, text) {
      s.chat.push({ cls, who, text });
      if (s.chat.length > MAX) s.chat.splice(0, s.chat.length - MAX);
    }
    function onPi(ev) {
      const k = ev.kind;
      if (k === 'text') push('pi', 'pi', ev.text || '');
      else if (k === 'tool_call') push('tool', '⚙', `${ev.name} ${ev.args && Object.keys(ev.args).length ? JSON.stringify(ev.args) : ''}`);
      else if (k === 'tool_result') {
        const t = String(ev.text || '');
        const m = BUDGET.exec(t);
        if (m) s.budget = { spent: m[1], budget: m[2], calls: m[3], requests: m[4] };
        const short = t.replace(BUDGET, '').trim();
        push('tool' + (ev.ok === false ? ' err' : ''), ev.ok === false ? '✗' : '✓', `${ev.name}: ${short.length > 400 ? short.slice(0, 400) + '…' : short}`);
      } else if (k === 'notify') push('note', ev.level || 'note', ev.text || '');
      else if (k === 'error') push('err', 'error', `${ev.where || ''} ${ev.error || ''}`);
      else if (k === 'turn_end') push('note', '', ev.aborted ? '— the turn was aborted —' : '— pi waits for you —');
      else if (k === 'exit') push('err', 'exit', `pi exited (${ev.code})${ev.stderr_tail && ev.stderr_tail.length ? ': ' + [].concat(ev.stderr_tail).slice(-3).join(' | ') : ''}`);
      else if (k === 'usage') return;
      render();
    }
    async function refresh() {
      try { s.state = await io.ask('loop', 'state'); s.note = ''; } catch (e) { s.note = e.message; }
      render();
    }
    async function tail() {
      try {
        const r = await io.ask('loop', 'events', { since: 0 });
        s.journal = r.rows || [];
        s.seen = s.journal.length;
        for (const row of s.journal) if (row.kind === 'budget' && row.who === 'pi') s.over = row;
      } catch (e) { s.note = e.message; }
      render();
    }
    async function start(form) {
      const f = new FormData(form);
      const msg = { mode: 'rpc' };
      const m = String(f.get('model') || '').trim(), b = String(f.get('budget') || '').trim();
      if (m) msg.model = m;
      if (b) msg.budget = Number(b);
      s.note = 'starting pi…';
      render();
      try { await io.ask('loop', 'start', msg, 120000); s.chat = []; s.budget = s.over = null; s.note = ''; } catch (e) { s.note = e.message; }
      refresh();
    }
    async function stop() {
      try { await io.ask('loop', 'stop'); } catch (e) { s.note = e.message; }
      refresh();
    }
    async function say(form) {
      const text = String(new FormData(form).get('text') || '').trim();
      if (!text) return;
      form.querySelector('[name=text]').value = '';
      push('me', 'you', text);
      render();
      try { await io.ask('loop', 'say', { text }); } catch (e) { s.note = e.message; render(); }
    }
    async function answer(how) {
      const g = s.gate;
      if (!g) return;
      s.gate = null;
      push('note', 'gate', `${how}ed: ${(g.plan && g.plan.title) || g.token}`);
      render();
      try { await io.ask('loop', how, { token: g.token }); } catch (e) { s.note = e.message; render(); }
    }
    io.on('loop', 'pi', f => onPi(f.event || {}));
    io.on('loop', 'gate', f => { s.gate = { token: f.token, plan: f.plan }; render(); });
    io.on('loop', 'child', () => { s.gate = null; refresh(); });
    io.on('loop', 'event', f => {
      if (!f.row) return;
      s.journal.push(f.row);
      if (s.journal.length > MAX * 2) s.journal.splice(0, s.journal.length - MAX);
      if (f.row.kind === 'budget' && f.row.who === 'pi') s.over = f.row;
      if (['lock', 'unlock', 'pi_start', 'pi_start_failed', 'budget'].includes(f.row.kind)) refresh();
      else if (s.tab === 'journal') render();
    });
    render();
    refresh();
    tail();
    return { refresh, tail };
  }
  window.MetisLoop = { mount };
})();
