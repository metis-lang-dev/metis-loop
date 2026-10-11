// nina-web — the thin browser side of the harness (HARNESS.md §5-§6).
// The browser captures and plays; everything that understands audio stays
// in Go. Ported from nina_splat v1-bridge.js: the /ws connect/reconnect,
// the intent summary, applyVoice, chatAdd. New: the AudioWorklet mic, the
// WebAudio player with tts_done, the dialog-state strip, the events pane.
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const WSP = location.protocol === 'https:' ? 'wss' : 'ws';
  let ws = null, micWS = null, micTok = '', isMaster = false;
  let dialog = '', attnWanted = null;

  // ---------- log ----------
  const logCard = $('logCard');
  function log(text, cls = '') {
    const d = document.createElement('div');
    d.className = cls;
    d.textContent = `${new Date().toLocaleTimeString('en-GB')} ${text}`;
    logCard.appendChild(d);
    while (logCard.children.length > 200) logCard.removeChild(logCard.firstChild);
    logCard.scrollTop = logCard.scrollHeight;
  }
  $('btnClear').onclick = () => { logCard.innerHTML = ''; };

  // ---------- /ws ----------
  function send(m) {
    if (!ws || ws.readyState !== 1) { log(`[LINK] not connected — dropped ${JSON.stringify(m)}`, 'text-red-400'); return; }
    ws.send(JSON.stringify(m));
    log(`→ ${JSON.stringify(m)}`, 'text-slate-500');
  }
  function connect() {
    ws = new WebSocket(`${WSP}://${location.host}/ws`);
    ws.binaryType = 'arraybuffer';
    ws.onopen = () => {
      $('linkDot').className = 'inline-block w-2.5 h-2.5 rounded-full bg-emerald-400 shadow shadow-emerald-400';
      $('linkLbl').textContent = location.host;
      log('[LINK] /ws connected', 'text-emerald-400');
    };
    ws.onclose = () => {
      $('linkDot').className = 'inline-block w-2.5 h-2.5 rounded-full bg-red-500';
      $('linkLbl').textContent = 'reconnecting…';
      isMaster = false; micTok = ''; applyMic();
      log('[LINK] /ws lost — reconnecting in 2 s', 'text-red-400');
      setTimeout(connect, 2000);
    };
    ws.onmessage = (ev) => {
      if (ev.data instanceof ArrayBuffer) { player.chunk(ev.data); return; }
      let m;
      try { m = JSON.parse(ev.data); } catch { return; }
      if (m.ev !== 'tts' && m.ev !== 'tts_end') log(`← ${ev.data}`, 'text-slate-400');
      onEvent(m);
    };
  }

  function onEvent(m) {
    switch (m.ev) {
      case 'state': applyDialog(m.dialog); break;
      case 'transcript': chatAdd(m.text, null, m.t); break;
      case 'reply': chatAdd(null, m.text, m.t); break;   // what was SPOKEN — never intent.voice
      case 'intent': {
        const it = m.intent || {};
        const summ = it.action ? `${it.intent} ${it.action}${it.direction ? ' ' + it.direction : ''}`
          : (it.goal && it.goal.description) ? `${it.intent} → ${it.goal.description}`
          : (it.target && it.target.description) ? `${it.intent} → ${it.target.description}`
          : (it.intent || JSON.stringify(it));
        chatAdd(null, `[${summ}]`, m.t, true);
        break;
      }
      case 'command': eventAdd(m); break;
      case 'role':
        if (m.master === true) { isMaster = true; micTok = m.mic_tok || ''; applyMic(); if (micWanted) openMic(); }
        else if (m.master === false) { isMaster = false; micTok = ''; if (m.reason) log(`[MIC] ${m.reason}`, 'text-amber-400'); closeMic(false); applyMic(); }
        break;
      case 'tts': player.start(m); break;
      case 'tts_end': player.end(m.id); break;
      case 'tts_stop': player.stop(m.id); break;
      case 'denied': log(`[LINK] denied: ${m.what}`, 'text-amber-400'); break;
    }
  }

  // ---------- dialog state strip + attention ----------
  function applyDialog(st) {
    dialog = st;
    for (const el of $('dialogStrip').children) {
      const on = el.dataset.st === st;
      el.className = 'px-2.5 py-1 ' + (el.dataset.st === 'ASLEEP' ? '' : 'border-l border-slate-700 ') +
        (on ? (st === 'ASLEEP' ? 'bg-amber-500/20 text-amber-300' : st === 'SPEAKING' ? 'bg-fuchsia-500/20 text-fuchsia-300' : 'bg-emerald-500/20 text-emerald-300')
            : 'bg-slate-800 text-slate-500');
    }
    if (st === 'ASLEEP' || st === 'AWAKE') {
      $('attnSwitch').checked = st === 'AWAKE';
      $('attnLbl').textContent = st === 'AWAKE' ? 'awake' : 'asleep';
      $('attnLbl').className = st === 'AWAKE' ? 'text-emerald-400' : 'text-amber-400';
    }
  }
  $('attnSwitch').onchange = (e) => send({ ev: 'attention', state: e.target.checked ? 'AWAKE' : 'ASLEEP' });

  // ---------- chat ----------
  function chatAdd(you, nina, t, dim = false) {
    const c = $('chatCard');
    if (c.firstElementChild && c.firstElementChild.classList.contains('italic')) c.innerHTML = '';
    const ts = new Date(t ? t * 1000 : Date.now()).toLocaleTimeString('en-GB');
    if (you) {
      const u = document.createElement('div');
      u.className = 'text-slate-100';
      u.textContent = `${ts} you   ${String(you).trim()}`;
      c.appendChild(u);
    }
    if (nina !== null && nina !== undefined) {
      const s = document.createElement('div');
      s.className = dim ? 'text-slate-500' : 'text-cyan-300';
      s.textContent = `${ts} nina  ${String(nina).trim()}`;
      c.appendChild(s);
    }
    while (c.children.length > 200) c.removeChild(c.firstChild);
    c.scrollTop = c.scrollHeight;
  }
  $('chatForm').onsubmit = (e) => {
    e.preventDefault();
    const inp = $('chatInput'), text = inp.value.trim();
    if (!text) return;
    player.unlock();
    send({ ev: 'say_text', text });
    inp.value = '';
  };
  $('btnAnnounce').onclick = () => send({ ev: 'say', text: 'System check. All services nominal.' });

  // ---------- events pane: commands + task injection ----------
  function eventAdd(m) {
    const card = $('eventsCard');
    if (card.firstElementChild && card.firstElementChild.classList.contains('italic')) card.innerHTML = '';
    const row = document.createElement('div');
    row.className = 'border border-slate-700 rounded-lg p-2 bg-slate-950';
    row.dataset.id = m.id;
    const ts = new Date(m.t ? m.t * 1000 : Date.now()).toLocaleTimeString('en-GB');
    const head = document.createElement('div');
    head.className = 'flex items-baseline gap-2 font-mono text-[11px]';
    head.innerHTML = `<span class="text-slate-500">${ts}</span><span class="text-fuchsia-300 font-bold">${esc(m.name)}</span><span class="text-slate-500 ml-auto">${esc(m.id)}</span>`;
    const args = document.createElement('div');
    args.className = 'font-mono text-[10px] text-slate-300 break-all mt-0.5';
    args.textContent = JSON.stringify(m.args || {});
    const btns = document.createElement('div');
    btns.className = 'flex gap-1.5 mt-1.5';
    for (const r of ['done', 'failed', 'refused', 'expired']) {
      const b = document.createElement('button');
      b.className = 'px-2 py-0.5 rounded text-[10px] font-mono border ' +
        (r === 'done' ? 'border-emerald-500/60 text-emerald-300 hover:bg-emerald-500/10'
          : r === 'refused' ? 'border-amber-500/60 text-amber-300 hover:bg-amber-500/10'
          : 'border-slate-600 text-slate-300 hover:bg-slate-800');
      b.textContent = r;
      b.onclick = () => {
        send({ ev: 'task', id: m.id, result: r, detail: $('taskDetail').value.trim() });
        for (const x of btns.children) x.disabled = true;
        btns.className += ' opacity-50';
        head.insertAdjacentHTML('beforeend', `<span class="text-slate-400">→ ${r}</span>`);
      };
      btns.appendChild(b);
    }
    row.append(head, args, btns);
    card.appendChild(row);
    while (card.children.length > 30) card.removeChild(card.firstChild);
    card.scrollTop = card.scrollHeight;
  }
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  // ---------- player: tts header + binary chunks → WebAudio, gapless; tts_done when playback ends ----------
  const player = (() => {
    let ctx = null;
    let cur = null; // {id, rate, sources:[], startAt, nextAt, ended, samples, got, timer}
    function ensure() {
      if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
      return ctx;
    }
    function unlock() { // Chrome autoplay: resume on a user gesture
      const c = ensure();
      if (c.state === 'suspended') c.resume().then(applyAudio, applyAudio);
      applyAudio();
    }
    function applyAudio() {
      const c = ensure(), b = $('btnAudio');
      const ok = c.state === 'running';
      b.textContent = ok ? 'audio on' : 'enable audio';
      b.className = 'px-2.5 py-1 rounded-md text-[11px] font-mono border ' + (ok
        ? 'border-emerald-500/60 text-emerald-300' : 'border-amber-500/60 text-amber-300 hover:bg-amber-500/10');
    }
    function start(h) {
      if (cur) finish(cur, false); // a new stream supersedes a stale one
      const c = ensure();
      cur = { id: h.id, rate: h.rate || 24000, sources: [], startAt: 0, nextAt: 0, samples: h.samples || 0, got: 0, ended: false, timer: null };
      $('ttsLbl').textContent = `tts ${h.id} ${(cur.samples / cur.rate).toFixed(2)}s`;
      if (c.state !== 'running') log('[TTS] audio context suspended — click “enable audio”; acking anyway', 'text-amber-400');
    }
    function chunk(ab) {
      if (!cur) return;
      const c = ensure();
      const i16 = new Int16Array(ab);
      cur.got += i16.length;
      const buf = c.createBuffer(1, i16.length, cur.rate);
      const f = buf.getChannelData(0);
      for (let i = 0; i < i16.length; i++) f[i] = i16[i] / 32768;
      const src = c.createBufferSource();
      src.buffer = buf;
      src.connect(c.destination);
      const now = c.currentTime;
      if (!cur.startAt) { cur.startAt = now + 0.02; cur.nextAt = cur.startAt; }
      const at = Math.max(now, cur.nextAt);
      src.start(at);
      cur.nextAt = at + buf.duration;
      cur.sources.push(src);
    }
    function end(id) {
      if (!cur || cur.id !== id) return;
      cur.ended = true;
      const c = ensure();
      const s = cur;
      const wait = Math.max(0, (s.nextAt || c.currentTime) - c.currentTime);
      // tts_done when the last scheduled sample has played (or at once when
      // the context cannot play: the floor must not hang on a muted tab)
      s.timer = setTimeout(() => finish(s, true), c.state === 'running' ? wait * 1000 + 30 : 0);
    }
    function stop(id) {
      if (!cur || cur.id !== id) return;
      finish(cur, false);
    }
    function finish(s, completed) {
      if (s.timer) clearTimeout(s.timer);
      const c = ensure();
      let playedMs = 0;
      if (s.startAt) playedMs = Math.round(Math.max(0, Math.min(c.currentTime - s.startAt, (s.nextAt - s.startAt))) * 1000);
      if (completed) playedMs = Math.round(((s.nextAt - s.startAt) || 0) * 1000);
      for (const src of s.sources) { try { src.stop(); } catch {} }
      if (cur === s) cur = null;
      send({ ev: 'tts_done', id: s.id, played_ms: playedMs });
      $('ttsLbl').textContent = `tts — last ${completed ? 'played' : 'cut'} ${(playedMs / 1000).toFixed(2)}s`;
    }
    return { start, chunk, end, stop, unlock, applyAudio };
  })();
  $('btnAudio').onclick = () => player.unlock();
  document.addEventListener('click', () => player.unlock(), { once: true });

  // ---------- mic: grab the token, AudioWorklet → 640-byte frames → /ws_mic ----------
  let micWanted = false, micStream = null, micCtx = null, micNode = null;
  function applyMic() {
    const b = $('btnMic'), dot = $('micDot');
    const live = micWS && micWS.readyState === 1;
    b.textContent = live ? 'mic on' : micWanted ? 'mic…' : 'mic off';
    b.className = 'px-2.5 py-1 rounded-md text-[11px] font-mono border ' + (live
      ? 'border-emerald-500/60 text-emerald-300' : 'border-slate-600 text-slate-300 hover:bg-slate-800');
    dot.className = 'inline-block w-2.5 h-2.5 rounded-full ' + (live ? 'bg-emerald-400 shadow shadow-emerald-400' : 'bg-slate-700');
  }
  $('btnMic').onclick = async () => {
    player.unlock();
    if (micWanted) { micWanted = false; closeMic(true); applyMic(); return; }
    micWanted = true; applyMic();
    if (!isMaster) { send({ ev: 'grab_master' }); return; } // role{mic_tok} opens the mic
    openMic();
  };
  async function openMic() {
    if (micWS || !micTok) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      log('[MIC] unavailable: getUserMedia needs a secure context (https or localhost)', 'text-amber-400');
      micWanted = false; applyMic(); return;
    }
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    } catch (e) { log('[MIC] denied: ' + e.message, 'text-red-400'); micWanted = false; applyMic(); return; }
    micCtx = new (window.AudioContext || window.webkitAudioContext)();
    try {
      await micCtx.audioWorklet.addModule('mic-worklet.js');
    } catch (e) { log('[MIC] worklet failed: ' + e.message, 'text-red-400'); closeMic(true); return; }
    micWS = new WebSocket(`${WSP}://${location.host}/ws_mic?tok=${encodeURIComponent(micTok)}`);
    micWS.binaryType = 'arraybuffer';
    micWS.onopen = () => { log(`[MIC] live — ${micCtx.sampleRate} Hz → 16 kHz, 20 ms frames`, 'text-emerald-400'); applyMic(); };
    micWS.onclose = () => { log('[MIC] stream closed by the server (token rotated?)', 'text-amber-400'); micWS = null; applyMic(); };
    const src = micCtx.createMediaStreamSource(micStream);
    micNode = new AudioWorkletNode(micCtx, 'pcm16k', { processorOptions: { inRate: micCtx.sampleRate } });
    micNode.port.onmessage = (ev) => { if (micWS && micWS.readyState === 1) micWS.send(ev.data); };
    src.connect(micNode); // no connection to destination: nothing is played back locally
  }
  function closeMic(release) {
    if (micNode) { try { micNode.disconnect(); } catch {} micNode = null; }
    if (micCtx) { micCtx.close().catch(() => {}); micCtx = null; }
    if (micStream) { for (const t of micStream.getTracks()) t.stop(); micStream = null; }
    if (micWS) { micWS.onclose = null; micWS.close(); micWS = null; }
    if (release && isMaster) send({ ev: 'release_master' });
    if (release) { isMaster = false; micTok = ''; }
    applyMic();
  }

  applyMic();
  player.applyAudio();
  connect();
})();
