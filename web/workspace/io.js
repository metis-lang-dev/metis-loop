/* The workspace widgets' wire (loop-workspace s-5b4be5fa step 4; docs/WORKSPACE.md §6, §6.1): one small object the console
   makes over its own socket and hands to each widget. The widgets never open a socket: the console owns the transport
   (its gateway socket), the widgets speak the backend's frames
   (loop/workspace_ch.py: the trace, surprise, bundle and loop channels).

     const io = MetisIO.make(frame => socket.send(JSON.stringify(frame)));
     socket.onmessage = e => io.feed(JSON.parse(e.data))   // true when a widget took it
     io.ask(ch, type, fields)  -> Promise of the reply frame (its req matched); an error frame rejects
     io.on(ch, type, fn)       a push (no req, or not ours): fn(frame); type null = every type of ch

   The shared frontend's (WORKSPACE.md §6.1): served to this console from the loop SDK, never copied into another page. */
(function () {
  'use strict';
  function make(send, opts) {
    const o = opts || {};
    const waits = new Map();
    const subs = [];
    let n = 0;
    return {
      ask(ch, type, fields, timeoutMs) {
        const req = 'w' + (++n) + '.' + Date.now().toString(36);
        return new Promise((resolve, reject) => {
          const t = setTimeout(() => {
            if (waits.delete(req)) reject(new Error(`${ch} ${type}: no answer in ${Math.round((timeoutMs || o.timeoutMs || 330000) / 1000)} s`));
          }, timeoutMs || o.timeoutMs || 330000);
          waits.set(req, { resolve, reject, t });
          send(Object.assign({ ch, type, req }, fields || {}));
        });
      },
      on(ch, type, fn) {
        subs.push({ ch, type: type || null, fn });
      },
      feed(f) {
        if (!f || typeof f !== 'object') return false;
        const w = f.req && waits.get(f.req);
        if (w) {
          waits.delete(f.req);
          clearTimeout(w.t);
          if (f.type === 'error') w.reject(new Error(f.error || 'error'));
          else w.resolve(f);
          return true;
        }
        let hit = false;
        for (const s of subs) {
          if (s.ch === f.ch && (s.type === null || s.type === f.type)) {
            try { s.fn(f); } catch (e) { console.error('workspace widget', s.ch, e); }
            hit = true;
          }
        }
        return hit;
      },
    };
  }
  window.MetisIO = { make };
})();
