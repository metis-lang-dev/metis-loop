// nav.js — the loop console's voice navigation (console-nav s-b923ebfe step 2): the page as
// the host of two domains of metis-agent (domains/ui: the widgets and the focus; domains/repl:
// the REPL, whose host is a client of this page's gateway), fsttm-web's dialog panel as the one
// input, and the input's two channels: NAV (the navigation agent, Gemma E2B on metis-agent's
// /ws) and CHAT (the formalization agent: the CLAUDE dock's chat/say on the gateway).
//
//   import { startNav } from './lib/nav.js';
//   startNav(window.consolePage);          // the page's own API (loop_console.html, the end of its script)
//
// The wires. The page's gateway socket stays the page's (loop_console.html). This module opens
// the second, metis-agent's /ws (its URL is the gateway's meta/agent frame's, `[console]
// metis_agent`), through fsttm-web's ws adapter: a dropped socket is opened again and the
// hello claims ui and repl again, and the claim's `page` frame makes the port report the
// page's whole state (the takeover report, ui-port.js sync()).
//
// The effects (the agent's dlg-trace records, sent to the owning page only):
//   ui    focus, show, hide, numbers, pick, jump, mode, …  → the port (ui-port.js)
//         activate / deactivate {domain: repl}            → the agent's activate / deactivate;
//                                                           an activate binds the repl host to
//                                                           this page: {session, token, ws}
//   repl  open {llp, host}  → the page opens it; its session is the binding {session}, a
//                             failure {open_failed}
//         apply             → the page asks the gateway for its plan; the plan opens the APPLY
//                             dialog through the port (+opened); the click stays the person's
//         tell {text}       → the page posts the words to the chat (chat/say), and the input
//                             stays in CHAT (sticky) until the person flips back
//
// The input's channels: the flip key (`[console] flip_key`, ctrl+space by default) both ways;
// the wake word in CHAT ("metis, go to the catalog": that one utterance is the navigation's);
// a held Space (push-to-talk, the panel's quasimode) is CHAT while held, and the ui domain
// hears it as the typed intents HOLD / RELEASE (no model pass). A brain with no chat seat
// (openrouter, ollama: brain-choice) refuses CHAT with "agent seat: needs claude".
import { Panel } from './panel.js';
import { connect } from './ws.js';
import { UiPort } from './ui-port.js';

const DOCK_OF = { claude: 'chat', catalog: 'catalog', candidates: 'candidates', records: 'records', talk: 'talk' };
const WIDGET_DOCK = Object.fromEntries(Object.entries(DOCK_OF).map(([d, w]) => [w, d]));
const WAKE = /^\s*metis\b[\s,:.!-]*/i;
const NO_SEAT = 'agent seat: needs claude';

// the console's lists: their entries (the base's pick resolves names against them) and what a
// pick does on this page
const ENTRIES = {
  catin: () => [...document.querySelectorAll('#catlist option')],
  copy: () => [...document.querySelectorAll('#catrows [data-dom]')],
  extensions: () => [...document.querySelectorAll('#catdock .plist .pk')],
  records: () => [...document.querySelectorAll('#records .rec, #records .cand')],
  candidates: () => [...document.querySelectorAll('#cands .cand')],
};

// the widgets the console has only sometimes (base v6.5's present/absent): the editor needs an
// open catalog (a working copy to edit)
const CONDITIONAL = { editor: page => page.hasCatalog() };

class ConsolePort extends UiPort {
  constructor(opts) { super(opts); this.page = opts.page; }
  // sync: the takeover report says which conditional widgets the page has now, too
  sync() {
    super.sync();
    for (const [w, has] of Object.entries(CONDITIONAL)) this.line(has(this.page) ? `+present(${w})` : `+absent(${w})`);
  }
  // a conditional widget's element exists only once the page makes it (the editor's window):
  // a show or a focus makes it first, through the page's own opener
  effect(e) {
    if ((e.ui === 'show' || e.ui === 'focus') && e.widget in CONDITIONAL && !this.el(e.widget)) this.onDock?.(e.widget, true);
    super.effect(e);
  }
  entries(w) { return ENTRIES[w] ? ENTRIES[w]() : super.entries(w); }
  badges(items) { this.unbadge(); items.forEach((e, i) => { if (i < 9) e.dataset.n = String(i + 1); }); }
  unbadge() { for (const e of document.querySelectorAll('[data-n]')) delete e.dataset.n; }
}

// tag: the widgets the page renders later (the CATALOG dock's rows, the editor's windows)
// get their data-w and role as they appear
function tag(sel, w, role) {
  for (const e of document.querySelectorAll(sel)) {
    if (e.dataset.w !== w) Object.assign(e.dataset, { w, role });
    if (!e.hasAttribute('tabindex')) e.tabIndex = -1;
  }
}
function tagRendered() {
  tag('#catdock details.rootrd', 'readme', 'container');
  tag('#catrows', 'copy', 'list');
  tag('#catdock .plist', 'extensions', 'list');
}

export async function startNav(page) {
  const gw = page.gw;
  if (!gw) return null;                              // published as an artifact: no agent
  const agent = await page.agent();                  // the gateway's meta/agent frame (its url)
  if (!agent?.url) return null;
  const gwWs = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${gw.ws}`;
  const flipKey = gw.flip_key || 'ctrl+space';
  const log = window.nav = [];                       // the test hook: every port line, effect and frame
  const rec = (dir, f) => log.push({ t: Math.round(performance.now()), dir, ...f });

  let replOn = false, n = 0;
  const hello = b => b.send({ ev: 'hello', since: 1e15, claim: ['ui', 'repl'] });
  const backend = await connect(agent.url, { timeoutMs: 5000, reconnect: 2000, onReopen: hello });
  if (!backend) { page.banner(`no navigation agent at ${agent.url}: the console works as before`, 6000); return null; }
  const send = m => { if (backend.isOpen) backend.send(m); };     // a line during a drop is lost: the takeover report restates the page
  const bindings = extra => ({ ws: gwWs, token: gw.token || '', ...(page.sid() ? { session: page.sid() } : {}), ...extra });
  const activateRepl = extra => send({ ev: 'activate', domain: 'repl', bindings: bindings(extra) });

  // the TALK dock and the band's INPUT field show while the navigation runs
  for (const e of document.querySelectorAll('[data-strip="talk"],#b-navw')) e.hidden = false;
  if (!page.docks.state.talk) page.docks.set('talk', { shown: true, open: true });

  // ── the port: the page as the ui domain's host ──
  let byEffect = null;                               // a dock the port shows or hides for an effect: not the person's
  const port = window.port = new ConsolePort({
    page,
    root: document.getElementById('root'),
    syncDocks: true,
    send: lines => { rec('port', { lines }); send({ ev: 'world', domain: 'ui', atoms: lines }); },
    log: (dir, e) => { if (dir !== 'effect') rec(dir, { effect: e }); },     // an effect is logged once, with its domain (frame())
    onDock: (w, shown) => {
      byEffect = w;
      try {
        if (w === 'editor') shown ? page.openEditor() : page.closeEditors();
        else if (WIDGET_DOCK[w]) page.docks.set(WIDGET_DOCK[w], shown ? { shown: true, open: true } : { shown: false });
      } finally { byEffect = null; }
    },
  });
  port.onPick = (w, text, el) => {
    if (w === 'catin' || w === 'copy') page.select(el?.dataset?.dom ?? el?.value ?? text);    // selected: loading is the REPL's
    else if (w === 'records') el?.click();                                                  // the record sinks into the session
  };
  // the person's own shows and hides of a dock (the strip, a dock's ✕) and the editor's windows
  let shown = Object.fromEntries(Object.keys(DOCK_OF).map(d => [d, !!page.docks.state[d]?.shown]));
  page.onDocks = state => {
    for (const [d, w] of Object.entries(DOCK_OF)) {
      const s = !!state[d]?.shown;
      if (s !== shown[d]) { shown[d] = s; if (byEffect !== w) port.docked(w, s); }
    }
  };
  page.onEditor = on => { if (byEffect !== 'editor') port.docked('editor', on); };
  page.onDialog = dlg => port.openDialog(dlg);       // the APPLY dialog rises through the port (+opened)
  page.onCatalog = () => port.line('+present(editor)');   // a catalog opened: the editor is on the page
  new MutationObserver(tagRendered).observe(document.getElementById('catdock'), { childList: true, subtree: true });
  tagRendered();

  // ── the panel: the one input in the TALK dock ──
  const seat = () => !!page.manifest()?.seats?.chat;
  const panel = window.panel = new Panel(document.getElementById('talkpanel'), {
    backend, table: await (await fetch('lib/fsttm.json')).json(), title: 'navigation',
    flipKey,
    side: { label: 'formalization agent', send: async text => {
      if (!seat()) throw new Error(NO_SEAT);
      page.say(text);                                // the CLAUDE dock shows the agent's answer
      return '';
    } },
    onFrame: frame,
    onChannel: () => band(),
  });
  const core = panel.core;
  // push-to-talk: the rules hear the held key as the typed intents HOLD and RELEASE
  const typed = intent => send({ ev: 'intent', domain: 'ui', id: `ptt-${++n}`, j: { intent } });
  const hold = core.hold.bind(core), release = core.release.bind(core);
  core.hold = () => {
    if (!seat()) { panel.note(NO_SEAT); return false; }
    const ok = hold();
    if (ok) { typed('HOLD'); band(); }
    return ok;
  };
  core.release = () => {
    const ok = release();
    if (ok) { typed('RELEASE'); band(); }
    return ok;
  };
  const setChannel = core.setChannel.bind(core);
  core.setChannel = ch => {                          // no chat seat: CHAT refuses with the brain's words
    if (ch === 'side' && !seat()) { panel.note(NO_SEAT); return false; }
    return setChannel(ch);
  };
  const turn = core.turn.bind(core);
  core.turn = (text, o) => {                         // the wake word in CHAT: this one utterance is the navigation's
    if (core.channel !== 'side' || core.held || !WAKE.test(text)) return turn(text, o);
    core.channel = 'main';
    try { return turn(text.replace(WAKE, ''), o); } finally { core.channel = 'side'; }
  };
  window.say = text => panel.say(text);

  // the band: the input's channel and the flip key
  function band() {
    const el = document.getElementById('b-nav');
    if (!el) return;
    const chat = core.channel === 'side';
    el.textContent = chat ? `→ formalization agent${core.held ? ' (held)' : ''}` : 'navigation';
    el.className = 'v ' + (chat ? 'nav-chat' : 'nav-nav');
    document.getElementById('b-navw').title = `${flipKey} flips the input${seat() ? '' : ` (CHAT: ${NO_SEAT})`}; hold Space to talk to the formalization agent`;
  }
  port.onMode = m => { panel.setMode(m === 'dictation' ? 'dictation' : ''); };
  band();

  // ── the agent's frames ──
  function frame(f) {
    rec('frame', { ev: f.ev });
    if (f.ev === 'page') {
      if (f.owns?.includes('ui')) port.sync();       // the takeover report: the program learns the page as it is
      if (f.owns?.includes('repl') && replOn) activateRepl();
      return;
    }
    if (f.ev !== 'journal' || !f.rec || f.rec.kind !== 'dlg-trace') return;
    for (const x of f.rec.fired ?? []) {
      if (f.rec.domain === 'ui' && /^p_(go|show)_absent\b/.test(x.event ?? '') && !page.hasCatalog())
        page.banner('the editor needs an open catalog: say "load <package>" first', 6000);
    }
    if (!f.rec.effects) return;
    for (const e of f.rec.effects) {
      rec('effect', { domain: f.rec.domain, effect: e });
      if (f.rec.domain === 'ui') uiEffect(e); else if (f.rec.domain === 'repl') replEffect(e);
    }
  }
  function uiEffect(e) {
    if ((e.ui === 'activate' || e.ui === 'deactivate') && e.domain === 'repl') {
      replOn = e.ui === 'activate';
      if (replOn) activateRepl(); else send({ ev: 'deactivate', domain: 'repl' });
      return;
    }
    port.effect(e);
  }
  function replEffect(e) {
    if (e.repl === 'open') {
      page.open(e.llp, !!e.host).then(() => activateRepl(), why => activateRepl({ open_failed: String(why?.message ?? why) }));
    } else if (e.repl === 'apply') {
      page.apply();                                  // the plan comes to this socket; it opens the dialog
    } else if (e.repl === 'tell') {
      page.say(String(e.text ?? ''));
      setChannel(seat() ? 'side' : core.channel);    // CHAT now, until the person flips back
    }
  }
  // the page's session changed by hand (the person opened a catalog): the repl host follows it
  page.onSession = () => { if (replOn) activateRepl(); };

  hello(backend);
  return { backend, port, panel };
}
