"""Dev harness for the Loop Console — LOCAL TESTING ONLY, never
published. Serves `loop_console.html` wrapped in a shim that implements
the page's capabilities over this server:

  - claude.use("db")   -> an in-memory doc store (get/set/update/delete,
                          where/orderBy/limit, onSnapshot by polling);
  - claude.use("user") -> a fixed dev viewer (owner, can edit);
  - anything else      -> null (the page must degrade).

A drain thread plays the serving Claude session (skills/metis-loop
"Serving the console"): sessions with status "opening" are bound via
console_serve.open_session, queued intents run via serve_one, and the
postings are written back into the same docs — the real kernel, the
real whitelist, the real catalogs.

    python console/dev_serve.py [--port 8765] [--demo]

--demo seeds one candidate + one surprise record so the right panel
has rows (the published page never seeds). Open the page with ?nodb
or ?guest to see it with that capability absent (use() -> null);
?mocksample (=deny|=rate) gives `sample` a CANNED stand-in (no model)
that runs the REPL lines found in a message through the page's tool."""
import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from loop.console_serve import ConsoleServer  # noqa: E402

SHIM = r"""
(()=>{
const call=b=>fetch("/db",{method:"POST",headers:{"content-type":"application/json"},
  body:JSON.stringify(b)}).then(r=>r.json()).then(r=>{if(r.error)throw {code:"invalid_argument",message:r.error};return r});
const meta={fromCache:false,hasPendingWrites:false};
const dsnap=(id,r)=>({id,exists:!!r.exists,data:()=>r.exists?r.data:undefined,metadata:meta});
function poll(fetcher,deliver,err,keyOf){let last=null,stop=false;
  const tick=async()=>{if(stop)return;
    try{const r=await fetcher();const k=(keyOf||JSON.stringify)(r);if(k!==last){last=k;deliver(r)}}
    catch(e){err&&err({code:"unavailable",message:String(e&&e.message||e)})}
    if(!stop)setTimeout(tick,250)};
  tick();return()=>{stop=true}}
function docRef(path){const id=path.split("/").pop();return Object.freeze({id,path,
  get:async()=>dsnap(id,await call({op:"get",path})),
  set:async data=>{await call({op:"set",path,data})},
  update:async data=>{await call({op:"update",path,data})},
  delete:async()=>{await call({op:"delete",path})},
  onSnapshot:(next,err)=>poll(()=>call({op:"get",path}),r=>next(dsnap(id,r)),err),
  collection:p=>query(path+"/"+p,{})})}
function query(path,q){
  const qs=r=>{const docs=r.docs.map(d=>dsnap(d.id,{exists:true,data:d.data}));
    return {docs,size:docs.length,empty:!docs.length,docChanges:()=>[],metadata:meta}};
  return Object.freeze({path,
    where:(f,o,v)=>query(path,{...q,where:[...(q.where||[]),[f,o,v]]}),
    orderBy:(f,d)=>query(path,{...q,orderBy:[f,d||"asc"]}),
    limit:n=>query(path,{...q,limit:n}),
    get:async()=>qs(await call({op:"query",path,q})),
    /* ?missmod: like the live db seen in step 4 — a query snapshot
       fires on ADDS/REMOVES only, never on modifications */
    onSnapshot:(next,err)=>poll(()=>call({op:"query",path,q}),r=>next(qs(r)),err,
      new URLSearchParams(location.search).has("missmod")?r=>r.docs.map(d=>d.id).join(","):undefined),
    doc:id=>docRef(path+"/"+(id||Math.random().toString(36).slice(2,10))),
    add:async data=>{const d=docRef(path+"/"+Math.random().toString(36).slice(2,10));await d.set(data);return d}})}
const DB=Object.freeze({doc:docRef,collection:p=>query(p,{})});
const USER=Object.freeze({id:async()=>"dev-viewer",me:async()=>({id:"dev-viewer",name:"dev"}),
  isOwner:async()=>true,canEdit:async()=>true,can:async()=>true,
  profiles:async ids=>Object.fromEntries(ids.map(i=>[i,{id:i,name:""}]))});
const Q=new URLSearchParams(location.search);   // ?nodb / ?guest: absence
/* ?mocksample[=deny|rate]: a CANNED stand-in for Claude (never a model):
   pulls REPL lines out of the last user message, runs each through the
   page's repl tool, then streams a summary — drives the tool loop, the
   claude> marks, streaming, stop, refusals and the error codes. */
const sleep=(ms,sig)=>new Promise((r,j)=>{const t=setTimeout(r,ms);
  sig&&sig.addEventListener("abort",()=>{clearTimeout(t);j({code:"cancelled",message:"cancelled"})},{once:true})});
async function mockSample(input,opts){opts=opts||{};const sig=opts.signal;
  const mode=Q.get("mocksample");
  if(mode==="deny")throw {code:"not_granted",message:"not granted (mock)"};
  if(mode==="rate")throw {code:"rate_limited",message:"rate limited (mock)"};
  const turns=typeof input==="string"?[{role:"user",content:input}]:input;
  const last=String(turns[turns.length-1].content).split("\n\n[console now")[0]
    .split("== The viewer ==\n").pop();              // never the preamble
  const lines=(last.match(/:?\b(run \d+|step|why(?: [\w()]+)?|ctx(?: \w+)?|events|graph|accept|causes \S+ \S+|reset)\b/g)||[])
    .map(l=>":"+l.replace(/^:/,""));
  const tool=(opts.tools||[]).find(t=>t.name==="repl");const notes=[];
  await sleep(700,sig);
  for(const line of lines){
    if(!tool)break;
    try{const r=await tool.execute({line},{signal:sig});
      notes.push(`${line} -> ${r.status}: ${String(r.result).split("\n")[0].slice(0,90)}`)}
    catch(e){if(e&&e.code==="cancelled")throw e;notes.push(`${line} -> ${e.message.slice(0,90)}`)}}
  const text=(lines.length?"[mock] I ran "+lines.length+" line(s):\n"+notes.join("\n")
    :"[mock] No REPL line in your message — this mock only echoes. ")+
    "\n(the real model answers on the published artifact; this canned reply exercises the tool loop and streaming.)";
  let shown="";
  for(const w of text.split(/(\s+)/)){await sleep(25,sig);shown+=w;
    opts.onText&&opts.onText({text:shown,delta:w})}
  return {text,truncated:false,modelTierApplied:"default"}}
const SAMPLE=Object.freeze(Object.assign(mockSample,{json:async()=>{throw {code:"invalid_argument",message:"mock: no json"}},
  limits:async()=>({maxPromptBytes:200000})}));
window.claude=Object.freeze({use:name=>new Promise(res=>setTimeout(()=>
  res(name==="db"&&!Q.has("nodb")?DB:name==="user"&&!Q.has("guest")?USER:
      name==="sample"&&Q.has("mocksample")?SAMPLE:null),60))});
})();
"""


class Store:
    """The in-memory db: path -> doc dict; even segments are docs."""

    def __init__(self):
        self.docs = {}
        self.lock = threading.RLock()

    def op(self, req):
        op, path = req.get("op"), req.get("path", "")
        with self.lock:
            if op == "get":
                d = self.docs.get(path)
                return {"exists": d is not None, "data": d}
            if op == "set":
                self.docs[path] = dict(req.get("data") or {})
                return {"ok": True}
            if op == "update":
                if path not in self.docs:
                    return {"error": f"no document {path}"}
                self.docs[path].update(req.get("data") or {})
                return {"ok": True}
            if op == "delete":
                self.docs.pop(path, None)
                return {"ok": True}
            if op == "query":
                return {"docs": self.query(path, req.get("q") or {})}
        return {"error": f"bad op {op}"}

    def query(self, coll, q):
        depth = coll.count("/") + 1
        rows = [(p.rsplit("/", 1)[1], d) for p, d in self.docs.items()
                if p.startswith(coll + "/") and p.count("/") == depth]
        ops = {"==": lambda a, b: a == b, "!=": lambda a, b: a != b,
               "<": lambda a, b: a is not None and a < b,
               "<=": lambda a, b: a is not None and a <= b,
               ">": lambda a, b: a is not None and a > b,
               ">=": lambda a, b: a is not None and a >= b,
               "in": lambda a, b: a in b}
        for f, o, v in q.get("where") or []:
            rows = [(i, d) for i, d in rows if ops[o](d.get(f), v)]
        if q.get("orderBy"):
            f, direction = q["orderBy"]
            rows.sort(key=lambda r: (r[1].get(f) is None, str(r[1].get(f))),
                      reverse=direction == "desc")
        else:
            rows.sort(key=lambda r: r[0])
        if q.get("limit"):
            rows = rows[:q["limit"]]
        return [{"id": i, "data": d} for i, d in rows]


def drain(store, srv, stop):
    """The serving session's loop, in-process."""
    while not stop.is_set():
        drain_once(store, srv)
        stop.wait(0.15)


def drain_once(store, srv):
    """One pass of the serving session — exactly what the real one does
    with ArtifactData: list sessions + intents, `srv.drain(...)`, apply
    the writes as updates."""
    with store.lock:
        sessions = [(p.split("/")[1], dict(d)) for p, d in store.docs.items()
                    if p.startswith("sessions/") and p.count("/") == 1]
        intents = [(p.split("/")[1], dict(d)) for p, d in store.docs.items()
                   if p.startswith("intents/") and p.count("/") == 1
                   and d.get("status") == "queued"]
    for w in srv.drain(sessions, intents):
        with store.lock:
            store.docs.setdefault(w["path"], {}).update(w["data"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--demo", action="store_true")
    ns = ap.parse_args(argv)
    store, srv = Store(), ConsoleServer()
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    store.docs["meta/catalogs"] = srv.catalogs_doc()["data"]
    if ns.demo:
        store.docs["candidates/c-demo"] = {
            "record_id": "r-demo", "status": "pending", "ok": True,
            "findings": [], "ts": now,
            "llp": "%% demo candidate (dev harness only)\n"}
        store.docs["surprise/r-demo"] = {"kind": "rare", "ts": now,
                                         "observed": {"wolf": 1}}
    page = (HERE / "loop_console.html").read_text()
    html = ("<!doctype html><html><head><meta charset=utf-8><meta "
            "name=viewport content=\"width=device-width,initial-scale=1\">"
            f"<script>{SHIM}</script></head><body>{page}</body></html>")

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype):
            b = body.encode()
            self.send_response(code)
            self.send_header("content-type", ctype)
            self.send_header("content-length", str(len(b)))
            self.send_header("cache-control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path.split("?")[0] in ("/", "/index.html"):
                self._send(200, html, "text/html; charset=utf-8")
            elif self.path == "/_store":          # debugging aid
                with store.lock:
                    self._send(200, json.dumps(store.docs, indent=1,
                                               default=str),
                               "application/json")
            else:
                self._send(404, "not found", "text/plain")

        def do_POST(self):
            if self.path != "/db":
                return self._send(404, "not found", "text/plain")
            n = int(self.headers.get("content-length") or 0)
            try:
                req = json.loads(self.rfile.read(n) or b"{}")
                res = store.op(req)
            except Exception as e:                  # noqa: BLE001
                res = {"error": f"{type(e).__name__}: {e}"}
            self._send(200, json.dumps(res, default=str),
                       "application/json")

    stop = threading.Event()
    threading.Thread(target=drain, args=(store, srv, stop),
                     daemon=True).start()
    httpd = ThreadingHTTPServer(("127.0.0.1", ns.port), H)
    print(f"loop console dev harness: http://127.0.0.1:{ns.port}/",
          flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
    return 0


if __name__ == "__main__":
    sys.exit(main())
