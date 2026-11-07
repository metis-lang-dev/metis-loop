/* The console's EMBED FACE (loop-road-ui s-0314a8ee step 1, CHAT.md §1): a host page frames the served console as an
   iframe with ?panels=chat&embed=ORIGIN; ORIGIN is the only origin the face listens to and posts to. Without embed= (or
   with a value that is not an origin) nothing listens and nothing is posted. The wire is window.postMessage, both ways:

     host -> console  {metis: "chat", text, via?}          a line as typed into the CHAT's input, sent ("/" rows at 0 USD,
                                                            anything else to pi); via "heard": shown as heard (the host's mic)
                      {metis: "gate", answer, id}           the open gate ID answered: confirm | refuse
     console -> host  {metis: "ready"}                      the face is up, always the first post (the host's "the loop is not
                                                            running" ends)
                      {metis: "row", who, text, kind, ...}  every row as the CHAT shows it (a mark's carries mark: N)
                      {metis: "gate", open: true, id, title} | {metis: "gate", answered, id}

   The workspace files stay the data path (marks, traces, records): the wire carries chat lines only.

     const face = MetisEmbed.face(window, location.search)     null without a valid embed=
     face.attach(chat)        chat: MetisLoop.mount's {say, answerGate}; posts {metis: "ready"}
     face.row(row)            opts.onRow of the CHAT
     face.gate(g)             opts.onGate of the CHAT
*/
(function (root) {
  function origin(q) {
    const e = new URLSearchParams(q || '').get('embed');
    if (!e) return null;
    try {
      const u = new URL(e);
      return (u.protocol === 'http:' || u.protocol === 'https:') && u.origin === e.replace(/\/$/, '') ? u.origin : null;
    } catch (err) { return null; }
  }

  function face(win, search) {
    const at = origin(search);
    if (!at || !win || !win.parent || win.parent === win) return null;
    let chat = null, ready = false;
    const send = m => { try { win.parent.postMessage(m, at); } catch (e) { /* the host went */ } };
    const post = m => { if (!ready) { ready = true; send({ metis: 'ready' }); } send(m); };   // "ready" always first
    win.addEventListener('message', ev => {
      if (ev.origin !== at || ev.source !== win.parent) return;        // the named origin, the framing page only
      const d = ev.data;
      if (!d || typeof d !== 'object' || !chat) return;
      if (d.metis === 'chat' && typeof d.text === 'string' && d.text.trim())
        chat.say(d.text.trim(), d.via === 'heard' ? 'heard' : undefined);
      else if (d.metis === 'gate' && (d.answer === 'confirm' || d.answer === 'refuse') && d.id)
        chat.answerGate(d.id, d.answer);
    });
    return {
      origin: at,
      attach(c) { chat = c; if (!ready) { ready = true; send({ metis: 'ready' }); } },
      row(r) { if (r) post(Object.assign({ metis: 'row' }, r)); },
      gate(g) {
        if (!g) return;
        if (g.open) post({ metis: 'gate', open: true, id: g.token, title: g.title || '' });
        else if (g.answered) post({ metis: 'gate', answered: g.answered, id: g.token });
      },
    };
  }

  root.MetisEmbed = { origin, face };
})(typeof window !== 'undefined' ? window : globalThis);
