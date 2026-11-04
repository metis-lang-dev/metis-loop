/* The CHAT widget (loop-chat s-f6c32d0c step 1, docs/CHAT.md §1; before it the LOOP widget of loop-workspace step 4),
   over the backend's `loop` channel, with the `bundle` and `surprise` channels for its header and cards. The tester's
   interface to the pi loop: say what to do, read what the loop did.

   - the header line: the bundle (name, image, BUILT/STALE), the pi child (none, running, or the lock of a loop
     elsewhere, the TUI's), the spend of the session's budget;
   - the chat: the person's lines, pi's words, its tool calls and results, the turn's end;
   - the gate's plan as a card with confirm / refuse; a ruling as a card (MetisRulings.card: verdict, first enabled,
     firings, goldens moved, lint, spend, show pack / show document); STALE as a notice with [rebuild] [reload];
   - a line said with no pi child starts one first (the options' model and budget, else loop.sh's) and says so.

     const c = MetisLoop.mount(box, io, {session: () => sid})   session: the REPL session [reload] re-opens
     c.refresh()        the child, the locks, the bundle
     c.tail()           the journal (the "journal" chip)
     c.ruling(id)       the ruling of surprise ID as a card in the chat

   A line starting with "/" is the backend's command (loop-chat step 2, CHAT.md §2: loop/chat_tools.json, 0 USD): it never
   starts pi; its answer shows as a block, a ruling as its card, a /mark draft in SURPRISES (opts.onMark). The input
   completes the commands on "/" (the table, `loop commands`). opts.onMark(draft): the host's SURPRISES dialog.
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
  const BUDGET = /\[budget: ([0-9.]+) of ([0-9.]+) USD spent; (\d+) tool calls, (\d+) model requests[^\]]*\]/;
  const DEFAULT_BUDGET = 1;     // loop.sh's METIS_LOOP_BUDGET default for a paid model
  const MAX = 300;
  function snap(box) {          // what the person is typing survives a re-render (a push redraws the widget)
    const out = new Map();
    for (const i of box.querySelectorAll('input[name],textarea[name]')) out.set(i.name, i.value);
    const a = document.activeElement;
    return { out, focus: a && box.contains(a) ? a.name : null };
  }
  function unsnap(box, s) {
    for (const i of box.querySelectorAll('input[name],textarea[name]')) {
      if (!s.out.has(i.name)) continue;
      i.value = s.out.get(i.name);
      if (i.name === s.focus) i.focus();
    }
  }
  function mount(box, io, opts) {
    const o = opts || {};
    const s = { state: null, bundle: undefined, chat: [], journal: [], budget: null, over: null, spent: 0, note: '',
      tab: 'chat', options: false, model: '', budgetIn: '', noThinking: false, ruled: new Set(), commands: [] };
    box.classList.add('mw', 'mw-loop', 'mw-chatw');
    const listId = 'mw-cmds-' + Math.random().toString(36).slice(2, 8);     // one chat per mount: its own completion list
    const child = () => s.state && s.state.child;
    const running = () => { const c = child(); return !!(c && c.state === 'running'); };
    const elsewhere = () => { const l = s.state && s.state.loops && s.state.loops.pi; return l && l.alive && !running() ? l : null; };

    // ---- the header line ----
    function bundlePart() {
      const b = s.bundle;
      if (b === undefined) return el('span', { class: 'empty' }, 'reading the bundle…');
      if (b === null) return el('span', { class: 'empty', title: 'no domains/composition.yaml in this workspace' }, 'no bundle');
      return el('span', {}, el('b', {}, b.name), ' · ',
        el('span', { class: 'mono' }, b.image ? 'v-' + b.image.slice(0, 12) : 'not built'), ' ',
        el('span', { class: 'mw-badge ' + (b.stale ? 'warn' : 'ok'), title: b.stale ? (b.why || 'stale') : 'every member is older than the build record' }, b.stale ? 'STALE' : 'BUILT'));
    }
    function piPart() {
      const c = child(), l = elsewhere();
      if (c && c.state !== 'exited') return el('span', {}, `pi: ${c.state}${c.model ? ' · ' + c.model : ''}`);
      if (l) return el('span', { class: 'warn', title: 'one pi loop per workspace (the lock)' }, `pi: pid ${l.pid} holds the workspace (${l.mode || '?'})`);
      return el('span', { class: 'empty' }, 'pi: none');
    }
    function spendPart() {
      const c = child();
      const of = s.budget ? Number(s.budget.budget) : c && c.budget ? Number(c.budget) : DEFAULT_BUDGET;
      const spent = Math.max(s.spent, s.budget ? Number(s.budget.spent) : 0);
      const total = s.state && s.state.cost ? s.state.cost : {};
      const tip = `the session: ${spent.toFixed(4)} USD by pi's estimate (the key's real bill ran ~3x higher on deepseek v4 pro: loop-chat step 3's round, 0.4477 USD billed vs 0.149 counted)` +
        (s.budget ? `, ${s.budget.calls} tool calls, ${s.budget.requests} model requests` : '') +
        `\nthe workspace: ${Number(total.total || 0).toFixed(4)} USD in ${total.calls || 0} paid calls (.metis/cost.jsonl)`;
      return el('span', { class: s.over ? 'bad' : s.budget ? 'warn' : '', title: tip }, `${spent.toFixed(2)} of ${of} USD (pi's estimate)`);
    }
    function header() {
      const run = running(), held = !!elsewhere();
      return el('div', { class: 'mw-row mw-head' },
        bundlePart(), el('span', { class: 'empty' }, '·'), piPart(), el('span', { class: 'empty' }, '·'), spendPart(),
        el('span', { class: 'mw-grow' }),
        run ? el('button', { class: 'btn', type: 'button', onclick: stop, title: 'stop the pi child' }, 'stop')
          : el('button', { class: 'btn', type: 'button', disabled: held, onclick: () => start(), title: held ? 'a pi loop (the TUI?) holds this workspace' : 'pi --mode rpc as this backend\'s child' }, 'start'),
        el('button', { type: 'button', class: 'chip', 'aria-pressed': s.options ? 'true' : 'false', title: 'the model and budget of the next start', onclick: () => { s.options = !s.options; render(); } }, 'options'),
        el('button', { type: 'button', class: 'chip', 'aria-pressed': s.tab === 'journal' ? 'true' : 'false', title: '.metis/loop/journal.jsonl', onclick: () => { s.tab = s.tab === 'journal' ? 'chat' : 'journal'; render(); } }, 'journal'));
    }
    function options() {
      if (!s.options) return null;
      const run = running();
      return el('div', { class: 'mw-row mw-opts' },
        el('input', { name: 'model', placeholder: "model (loop.sh's default)", 'aria-label': 'model', disabled: run, oninput: e => { s.model = e.target.value; } }),
        el('input', { name: 'budget', class: 'mw-num', placeholder: 'USD', 'aria-label': 'budget in USD', disabled: run, title: 'the session budget (USD, above 0); empty: loop.sh\'s default', oninput: e => { s.budgetIn = e.target.value; } }),
        el('label', { class: 'empty', title: "the model thinks before it acts by default (pi's level for the model); this turns it off for the next start" },
          el('input', { type: 'checkbox', disabled: run, checked: s.noThinking, onchange: e => { s.noThinking = e.target.checked; } }), ' no thinking'),
        el('span', { class: 'empty' }, run ? 'for the next start' : 'used by the next start (or the first line said)'));
    }

    // ---- the chat: lines and cards ----
    function push(cls, who, text) {
      s.chat.push({ cls, who, text });
      if (s.chat.length > MAX) s.chat.splice(0, s.chat.length - MAX);
    }
    function pushCard(m) {       // m.node() builds the card; the node is kept, so a fold opened stays open across pushes
      s.chat.push(m);
      if (s.chat.length > MAX) s.chat.splice(0, s.chat.length - MAX);
    }
    function gateCard(m) {
      const p = m.plan || {};
      return el('div', { class: 'mw-card mw-gate' },
        el('div', { class: 'mw-sub' }, 'THE GATE — ' + (p.title || 'pi asks to write')),
        el('pre', { class: 'mw-out' }, p.message || JSON.stringify(p, null, 1)),
        m.answered ? el('div', { class: 'empty' }, m.answered)
          : el('div', { class: 'mw-acts' },
            el('button', { class: 'btn', onclick: () => answer(m, 'confirm') }, 'confirm'),
            el('button', { class: 'btn', onclick: () => answer(m, 'refuse') }, 'refuse')));
    }
    function staleCard(b) {
      const sid = o.session ? o.session() : null;
      return el('div', { class: 'mw-card mw-notice' },
        el('div', {}, el('span', { class: 'mw-badge warn' }, 'STALE'), ' ', el('b', {}, b.name), ' ', el('span', { class: 'empty' }, b.why || 'a member changed after the build')),
        el('div', { class: 'mw-acts' },
          el('button', { class: 'btn', title: 'says /rebuild: the bundle built again (make / metisc build)', onclick: () => sendLine('/rebuild') }, 'rebuild'),
          reloadBtn(sid)));
    }
    function builtCard(b) {
      const sid = o.session ? o.session() : null;
      return el('div', { class: 'mw-card mw-notice' },
        el('div', {}, el('span', { class: 'mw-badge ok' }, 'BUILT'), ' ', el('b', {}, b.name), ' ', el('span', { class: 'mono' }, b.image ? 'v-' + b.image.slice(0, 12) : ''),
          el('span', { class: 'empty' }, ': a session plays the old image until it is reloaded')),
        el('div', { class: 'mw-acts' }, reloadBtn(sid)));
    }
    function reloadBtn(sid) {
      return el('button', {
        class: 'btn', disabled: !sid,
        title: sid ? 'the session re-opened on what is built now (epoch + 1)' : 'no session on this page: a host page (the road) reloads its own',
        onclick: () => reload(sid),
      }, 'reload');
    }
    function line(m) {
      if (m.node) return m.node;
      if (m.card) return (m.node = m.card());
      return el('div', { class: 'mw-msg ' + m.cls }, m.who ? el('span', { class: 'mw-who' }, m.who) : null, m.text);
    }
    function chatBox() {
      const held = elsewhere();
      return el('div', { class: 'mw-chat' },
        el('div', { class: 'mw-log', 'aria-live': 'polite' }, s.chat.length ? s.chat.map(line)
          : el('div', { class: 'empty' }, held ? `the pi loop of pid ${held.pid} (${held.mode || '?'}) holds this workspace: its journal shows here, its words in its terminal`
            : running() ? 'say what to do: "take the next surprise"' : 'say what to do — "take the next surprise" starts the pi loop first')),
        el('form', { class: 'mw-row', onsubmit: e => { e.preventDefault(); say(e.target); } },
          el('input', { name: 'text', class: 'mw-grow', placeholder: held ? 'another pi loop holds this workspace: /commands still answer (/help)' : 'to the pi loop, or /help', 'aria-label': 'to the pi loop', autocomplete: 'off', list: listId }),
          el('datalist', { id: listId }, s.commands.map(c => el('option', { value: '/' + c.name }, c.description))),
          el('button', { class: 'btn', type: 'submit' }, 'say')));
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
      box.replaceChildren(header(), options() || '',
        s.over ? el('div', { class: 'bad' }, `budget spent: ${Number(s.over.spent).toFixed(4)} of ${s.over.budget} USD; no further model turns this session (stop, then start with a larger budget in options)`) : '',
        s.tab === 'chat' ? chatBox() : journalBox(), s.note ? el('div', { class: 'empty' }, s.note) : '');
      unsnap(box, kept);
      const l2 = box.querySelector('.mw-log');
      if (l2 && atEnd) l2.scrollTop = l2.scrollHeight;
    }

    // ---- pi's events ----
    function onPi(ev) {
      const k = ev.kind;
      if (k === 'text') push('pi', 'pi', ev.text || '');
      else if (k === 'tool_call') push('tool', '⚙', `${ev.name} ${ev.args && Object.keys(ev.args).length ? JSON.stringify(ev.args) : ''}`);
      else if (k === 'tool_result') {
        const t = String(ev.text || '');
        const m = BUDGET.exec(t);
        if (m) s.budget = { spent: m[1], budget: m[2], calls: m[3], requests: m[4] };
        const short = t.replace(BUDGET, '').trim();
        push('tool' + (ev.ok === false ? ' err' : ''), ev.ok === false ? '✗' : '✓', `${ev.name}: ${short.length > 300 ? short.slice(0, 300) + '…' : short}`);
      } else if (k === 'notify') push('note', ev.level || 'note', ev.text || '');
      else if (k === 'error') push('err', 'error', `${ev.where || ''} ${ev.error || ''}`);
      else if (k === 'turn_end') {
        if (ev.empty) push('err', 'pi', ev.note || 'pi ended its turn without words');   // the backend's line (loop-chat step 3)
        push('note', '', ev.aborted ? '— the turn was aborted —' : '— pi waits for you —');
      }
      else if (k === 'exit') push('err', 'exit', `pi exited (${ev.code})${ev.stderr_tail && ev.stderr_tail.length ? ': ' + [].concat(ev.stderr_tail).slice(-3).join(' | ') : ''}`);
      else if (k === 'usage') { s.spent += Number(ev.cost) || 0; }
      render();
    }

    // ---- the backend ----
    async function refresh() {
      try { s.state = await io.ask('loop', 'state'); s.note = ''; } catch (e) { s.note = e.message; }
      try {
        const b = (await io.ask('bundle', 'state')).bundle;
        if (s.bundle === undefined && b && b.stale) pushCard({ card: () => staleCard(b) });
        s.bundle = b;
      } catch (e) { if (s.bundle === undefined) s.bundle = null; }
      render();
    }
    async function tail() {
      try {
        const r = await io.ask('loop', 'events', { since: 0 });
        s.journal = r.rows || [];
        for (const row of s.journal) if (row.kind === 'budget' && row.who === 'pi') s.over = row;
      } catch (e) { s.note = e.message; }
      render();
    }
    function startMsg() {
      const msg = { mode: 'rpc' };
      const m = String(s.model || '').trim(), b = String(s.budgetIn || '').trim();
      if (m) msg.model = m;
      if (s.noThinking) msg.no_thinking = true;
      if (b) {
        const n = Number(b);
        if (!Number.isFinite(n) || n <= 0)      // never a silent default: NaN would go as null, and loop.sh's 1.00 apply
          throw new Error(`budget ${JSON.stringify(b)}: a number of USD above 0, or empty for loop.sh's default`);
        msg.budget = n;
      }
      return msg;
    }
    async function start() {
      let msg;
      try { msg = startMsg(); } catch (e) { s.note = e.message; s.options = true; render(); return false; }
      push('note', 'loop', 'starting the pi loop…');
      render();
      try {
        const r = await io.ask('loop', 'start', msg, 120000);
        const c = r.child || {};                       // what started: the backend's budget (/budget's too), not the form's (L4)
        push('note', 'loop', `started the pi loop: ${c.model || msg.model || "loop.sh's model"}, thinking ${msg.no_thinking ? 'off' : "on (pi's default level)"}, ` +
          `budget ${c.budget ? c.budget + ' USD' : DEFAULT_BUDGET + " USD (loop.sh's default)"}`);
        s.budget = s.over = null; s.spent = 0; s.note = '';
        await refresh();
        return true;
      } catch (e) { push('err', 'error', e.message); await refresh(); return false; }
    }
    async function stop() {
      try { await io.ask('loop', 'stop'); } catch (e) { s.note = e.message; }
      refresh();
    }
    async function command(text) {
      try {
        const sid = o.session ? o.session() : null;
        const r = await io.ask('loop', 'say', sid ? { text, session: sid } : { text }, 120000);
        if (r.text) push('cmd', '/' + (r.command || ''), r.text);
        if (r.ruling) await ruling(r.ruling);
        if (r.draft && o.onMark) o.onMark(r.draft);
        if (r.child !== undefined || ['take', 'stop', 'budget', 'rebuild', 'reload'].includes(r.command)) await refresh();
      } catch (e) { push('err', 'error', e.message); }
      render();
    }
    async function sendLine(text) {
      if (!text) return;
      push('me', 'you', text);
      render();
      if (text.startsWith('/')) return command(text);       // the backend's, never a model turn
      if (!running()) {
        if (elsewhere()) { push('err', 'error', 'another pi loop holds this workspace (its words are in its terminal): only /commands answer here'); render(); return; }
        if (!(await start())) return;
      }
      try { await io.ask('loop', 'say', { text }); } catch (e) { push('err', 'error', e.message); render(); }
    }
    function say(form) {
      const i = form.querySelector('[name=text]');
      const text = String(i.value || '').trim();
      i.value = '';
      return sendLine(text);
    }
    async function answer(m, how) {
      if (m.answered) return;
      m.answered = how === 'confirm' ? 'confirmed' : 'refused: nothing written';
      m.node = null;
      render();
      try { await io.ask('loop', how, { token: m.token }); } catch (e) { m.answered = `${how}: ${e.message}`; m.node = null; render(); }
    }
    async function reload(sid) {
      try { await io.ask('bundle', 'reload', { session: sid }); push('note', 'loop', `reloaded ${sid}: the session is on the files as they are now`); }
      catch (e) { push('err', 'error', e.message); }
      refresh();
    }
    async function ruling(id) {
      try {
        const g = await io.ask('surprise', 'get', { id });
        const card = window.MetisRulings && window.MetisRulings.card;
        if (card) pushCard({ card: () => card(g) });
        else push('note', 'ruling', `${id}: ${((g.surprise || {}).ruling || {}).verdict || '?'}`);
      } catch (e) { push('err', 'error', e.message); }
      render();
    }
    io.on('loop', 'pi', f => onPi(f.event || {}));
    io.on('loop', 'gate', f => { pushCard({ gate: true, token: f.token, plan: f.plan, card() { return gateCard(this); } }); render(); });
    io.on('loop', 'child', () => {
      for (const m of s.chat) if (m.gate && !m.answered) { m.answered = 'the child is gone: nothing written'; m.node = null; }
      refresh();
    });
    io.on('loop', 'event', f => {
      const row = f.row;
      if (!row) return;
      s.journal.push(row);
      if (s.journal.length > MAX * 2) s.journal.splice(0, s.journal.length - MAX);
      if (row.kind === 'budget' && row.who === 'pi') s.over = row;
      if (row.kind === 'ruling' && row.id && !s.ruled.has(row.id)) { s.ruled.add(row.id); ruling(row.id); }
      if (['lock', 'unlock', 'pi_start', 'pi_start_failed', 'budget'].includes(row.kind)) refresh();
      else render();
    });
    io.on('bundle', 'stale', f => {
      const b = f.bundle, was = s.bundle;
      s.bundle = b;
      if (b && b.stale && !(was && was.stale)) pushCard({ card: () => staleCard(b) });
      else if (b && !b.stale && was && was.stale) pushCard({ card: () => builtCard(b) });
      render();
    });
    async function commands() {
      try { s.commands = (await io.ask('loop', 'commands')).commands || []; render(); } catch (e) { /* an older backend: no completion */ }
    }
    render();
    refresh();
    tail();
    commands();
    return { refresh, tail, ruling, say: sendLine };
  }
  window.MetisLoop = { mount };
})();
