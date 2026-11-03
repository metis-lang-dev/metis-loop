// The workspace's TypeScript face against metispy's own CLI (loop-workspace s-5b4be5fa step 1, docs/WORKSPACE.md
// §2): the names are py's (layout().face), the layout's paths are py's Workspace.path, each read answers what the
// CLI answers, and the writes (drop, take, rule, journal, lock) land as py reads them. Run by
// tests/test_ts_face.py, or:
//   METIS_LOOP_SDK_PY=<python with metispy> [METIS_LOOP_SDK_WS_TS=<its workspace.ts>] \
//     node --experimental-strip-types --test sdk/tests/ts/workspace.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

type Face = typeof import("../../metis_loop_sdk/ts/workspace.ts");
const ws: Face = await import(
	process.env.METIS_LOOP_SDK_WS_TS ? pathToFileURL(process.env.METIS_LOOP_SDK_WS_TS).href : "../../metis_loop_sdk/ts/workspace.ts");
const PY = process.env.METIS_LOOP_SDK_PY ?? "python3";

const py = (r: string | null, ...args: string[]) =>
	JSON.parse(execFileSync(PY, ["-m", "metis.catalog.workspace", ...(r ? ["--root", r] : []), ...args, "--json"], { encoding: "utf8" }));
// py's own Workspace, called in a child: what the module answers, not only the CLI
const pyws = (r: string, expr: string) =>
	JSON.parse(execFileSync(PY, ["-c", `import json,sys; from metis.catalog import workspace as W; ws = W.workspace(sys.argv[1]); print(json.dumps(${expr}, default=str))`, r], { encoding: "utf8" }));
const scratch = () => mkdtempSync(join(tmpdir(), "workspace-ts-test-"));
const deadPid = () => spawnSync(process.execPath, ["-e", "0"]).pid!;

test("the face has py's names, and the layout is py's one table", () => {
	const lay = ws.layout();
	assert.deepEqual(lay, py(null, "layout"));
	const missing = lay.face.filter((n: string) => typeof (ws as any)[n] !== "function");
	assert.deepEqual(missing, [], "every name of the py face is a function here");
	const r = scratch();
	for (const [name, fill] of [["journal", {}], ["surprise", { id: "20261103T120000-abcdef" }], ["trace", { run: "s1" }],
		["lock", { kind: "pi" }], ["cost", {}]] as [string, Record<string, string>][])
		assert.equal(ws.path(name, fill, r), pyws(r, `str(ws.path(${JSON.stringify(name)}, **${JSON.stringify(fill)}))`), name);
	assert.throws(() => ws.path("surprise", {}, r), /\{id\} not given/);
});

test("an empty dir: the reads answer what the py CLI answers, and make nothing", () => {
	const r = scratch();
	assert.equal(ws.root(r).root, resolve(r));
	assert.equal(ws.bundle(undefined, r), null);
	assert.deepEqual(ws.surprises(undefined, r), []);
	assert.deepEqual(ws.traces(r), py(r, "traces"));
	assert.deepEqual(ws.events(0, r), []);
	assert.deepEqual(ws.cost(r), py(r, "cost"));
	assert.deepEqual(ws.loops(r), { pi: null, backend: null });
	assert.equal(ws.context(undefined, r), py(r, "context").context);
	assert.deepEqual(readdirSync(r), [], "not even .metis/");
});

test("a surprise dropped, taken and ruled from node is what py reads", () => {
	const r = scratch();
	const id = ws.drop_surprise({ member: "responder", trace: "traces/s1", k: 41, window: [30, 41], atoms: ["brake_lon"], words: "it should have braked" }, "backend", r);
	assert.match(id, new RegExp(ws.layout().id));
	assert.deepEqual(ws.surprises("open", r), py(r, "surprises", "--status", "open"));
	assert.equal(pyws(r, `ws.surprise(${JSON.stringify(id)})["status"]`), "open");
	ws.take_surprise(id, process.pid, "pi", r);
	assert.equal(ws.surprise(id, r).taken.pid, process.pid);
	assert.throws(() => ws.take_surprise(id, process.pid, "pi", r), /taken by pid/);
	const j = ws.rule(id, "# the ruling\n\naccepted\n", "accepted", { pack: "% the pack\n", fields: { moved: [], spent: 0 } }, r);
	assert.equal(j, `rulings/${id}.json`);
	const ruled = ws.surprise(id, r);
	assert.equal(ruled.status, "ruled");
	assert.deepEqual(ruled.ruling, pyws(r, `ws.rulings()[0]`));
	assert.equal(readFileSync(join(r, ".metis", "packs", `${id}.llp`), "utf8"), "% the pack\n");
	assert.deepEqual(ws.events(0, r).map((e) => [e.who, e.kind]), [["backend", "surprise"], ["pi", "take"], ["pi", "ruling"]]);
	assert.deepEqual(ws.events(2, r), py(r, "events", "--since", "2"));
	assert.throws(() => ws.drop_surprise({ member: "m" } as any, "backend", r), (e: any) => e.name === "WorkspaceError" && /a reading or atoms/.test(e.message));
});

test("a dead pid's take is stale: open again, and re-taken with a retake row", () => {
	const r = scratch();
	const id = ws.drop_surprise({ member: "planner", atoms: ["accel"] }, "backend", r);
	const gone = deadPid();
	ws.take_surprise(id, gone, "pi", r);
	const s = ws.surprise(id, r);
	assert.equal(s.status, "open");
	assert.equal(s.stale_take!.pid, gone);
	assert.deepEqual(ws.surprises("open", r), py(r, "surprises", "--status", "open"));
	ws.take_surprise(id, process.pid, "pi", r);
	assert.equal(ws.surprise(id, r).taken!.pid, process.pid);
	const last = ws.events(0, r).at(-1)!;
	assert.equal(last.kind, "retake");
	assert.equal(last.dead_pid, gone);
});

test("one pi loop: node's lock refuses a second holder in the holder's words", () => {
	const r = scratch();
	const l = ws.lock("pi", { mode: "rpc", model: "m" }, process.pid, r);
	assert.equal(l.pid, process.pid);
	assert.equal(ws.loops(r).pi!.alive, true);
	assert.deepEqual(ws.loops(r), py(r, "loops"));
	assert.throws(() => ws.lock("pi", { mode: "tui" }, process.ppid, r), new RegExp(`the pi loop holds this workspace: pid ${process.pid}.*mode rpc`));
	assert.throws(() => ws.unlock("pi", process.ppid, r), /not/);
	assert.equal(ws.unlock("pi", process.pid, r), true);
	const gone = deadPid();
	ws.lock("backend", { port: 8399 }, gone, r);
	assert.equal(ws.loops(r).backend!.alive, false);
	assert.equal(ws.lock("backend", { port: 8400 }, process.pid, r).port, 8400, "a dead pid's lock is taken over");
	assert.equal(ws.events(0, r).at(-1)!.stale_pid, gone);
});

test("the journal, the bundle and a trace from node are py's", () => {
	const r = scratch();
	const row = ws.journal("pi", "progress", { note: "drafting a case" }, r);
	assert.deepEqual(ws.events(0, r), [row]);
	const d = join(r, "domains");
	for (const m of ["boss", "a"]) {
		mkdirSync(join(d, m), { recursive: true });
		writeFileSync(join(d, m, "domain.yaml"), `program: ${m}.llp\nline: the ${m} member\n`);
		writeFileSync(join(d, m, `${m}.llp`), `% ${m}\n`);
	}
	writeFileSync(join(d, "composition.yaml"), "# two members\nname: duo\nspecialists: [a]\ndirect: boss\n");
	assert.deepEqual(ws.bundle(undefined, r), py(r, "bundle"));
	assert.equal(ws.bundle(undefined, r)!.stale, true);
	assert.equal(ws.bundle(undefined, r)!.config, null);
	writeFileSync(join(d, "service.yaml"), "trace: {}\n");
	assert.equal(ws.bundle(undefined, r)!.config, join(resolve(d), "service.yaml"));
	assert.deepEqual(ws.bundle(undefined, r), py(r, "bundle"));
	const t = join(r, ".metis", "traces", "s1");
	mkdirSync(join(t, "checkpoints"), { recursive: true });
	writeFileSync(join(t, "checkpoints", "k0.json"), "{}");
	writeFileSync(join(t, "seg-0.jsonl"), JSON.stringify({ trace: 1, k0: 0, checkpoint: "checkpoints/k0.json", members: {} }) + "\n" +
		[0, 1, 2].map((k) => JSON.stringify({ k })).join("\n") + "\n");
	assert.deepEqual(ws.traces(r), [{ run: "s1", path: "traces/s1", segments: 1 }]);
	assert.deepEqual(ws.trace("s1", r), py(r, "trace", "s1"));
	assert.equal(ws.trace("s1", r).k1, 2);
});

test("the declared trace tools and their command lines are py's", () => {
	assert.deepEqual(ws.tools(), py(null, "tools"));
	assert.ok(ws.tools().tools.some((t) => t.name === "trace_blame"));
	const argv = ws.tool_argv("trace_count", { trace: "t", atom: "a", by: ["b", "c"] });
	assert.deepEqual(argv.slice(1), ["-m", "metis.trace", "count", "t", "a", "--by", "b", "--by", "c"]);
	assert.throws(() => ws.tool_argv("trace_count", { trace: "t" }), /atom required/);
	assert.throws(() => ws.tool_argv("trace_sort", {}), /not a declared trace tool/);
	assert.ok(existsSync(argv[0]));
});
