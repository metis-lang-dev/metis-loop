// metis-workspace (docs/WORKSPACE.md §5; loop-workspace s-5b4be5fa step 3) against stand-ins, at 0 USD: no model,
// no pi session. A surprise the backend drops is taken by the loop and ruled through the pack verb (a scripted
// judge in propose.sh's place: its ruling.md and evidence.json), the bundle rebuilds (a scripted metisc), the
// journal carries the trail, the trace verbs are the declared ones, and one pi loop holds a workspace.
//   node/bin/node --experimental-strip-types --test test/workspace.test.ts
// The workspace face is metispy's (metis.catalog.workspace) through the SDK's ./sdk/workspace.ts: TEST_SDK_PY is
// a python with both.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { once } from "node:events";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import workspace, { schema, tracePath } from "../extensions/metis-workspace.ts";
import * as ws from "../extensions/sdk/workspace.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const PKGS = join(HERE, "..", "..", "..");
const PY = process.env.TEST_SDK_PY ?? join(PKGS, ".venv", "bin", "python");
process.env.METIS_LOOP_SDK_PY = PY;

function fakePi() {
	const tools = new Map<string, any>();
	const on = new Map<string, ((e: any, c: any) => any)[]>();
	return {
		tools,
		emit: async (ev: string, e: any, c: any) => {
			let r;
			for (const h of on.get(ev) ?? []) r = (await h(e, c)) ?? r;
			return r;
		},
		api: {
			registerTool: (t: any) => tools.set(t.name, t),
			registerCommand: () => {},
			on: (ev: string, h: any) => on.set(ev, [...(on.get(ev) ?? []), h]),
			sendMessage: () => {},
		} as any,
	};
}
const notes: string[] = [];
const ctx = { hasUI: true, ui: { confirm: async () => true, notify: (m: string) => notes.push(m) } };

function exe(path: string, body: string) {
	writeFileSync(path, body);
	chmodSync(path, 0o755);
	return path;
}

/** A workspace: a two-member composition with a build record, its README, a trace dir; the stand-ins beside it. */
function scratch() {
	const r = mkdtempSync(join(tmpdir(), "ws-pi-"));
	mkdirSync(join(r, "domains", "lamp"), { recursive: true });
	writeFileSync(join(r, "README.md"), "# the lamp workspace\n");
	writeFileSync(join(r, "domains", "composition.yaml"), "# the lamp and its switch\nname: lampset\ndirect: lamp\n");
	writeFileSync(join(r, "domains", "lamp", "domain.yaml"), "display: the lamp\nline: a desk lamp\nprogram: lamp.llp\n");
	writeFileSync(join(r, "domains", "lamp", "lamp.llp"), "catalog lamp 1.\n% the lamp's rules\n");
	mkdirSync(join(r, ".metis", "traces", "s1"), { recursive: true });
	const bin = mkdtempSync(join(tmpdir(), "ws-pi-bin-"));
	// metisc build .: a new build record with the next image (the hash's form: <name>.v-<hex>)
	exe(join(bin, "metisc"), `#!/bin/sh
[ "$1" = build ] || exit 2
mkdir -p build; n=$(cat build/n 2>/dev/null || echo 0); n=$((n+1)); echo $n > build/n
printf 'image lampset.v-abc%s\\n' "$n" > build/lampset.build
echo "built lampset v-abc$n"
`);
	// propose.sh: the judge's two files, its verdict from STUB_VERDICT, its arguments recorded; STUB_COST: the brain's
	// per-call log (RUN/cost.jsonl) with that cost; STUB_CRASH: it spends, then dies before any ruling
	exe(join(bin, "propose"), `#!/bin/sh
run=""; prev=""; for a in "$@"; do [ "$prev" = --run ] && run="$a"; prev="$a"; done
mkdir -p "$run"; printf '%s\\n' "$@" > "${bin}/propose.args"
[ -z "$STUB_COST" ] || printf '{"ts": "t", "who": "judge", "model": "openrouter/m", "cost": %s, "usage_before": 0}\\n' "$STUB_COST" > "$run/cost.jsonl"
[ -z "$STUB_CRASH" ] || exit 3
printf '# Ruling: %s\\n\\nThe gate %s it. 0 USD.\\n' "$STUB_VERDICT" "$STUB_VERDICT" > "$run/ruling.md"
printf '{"verdict": "%s", "receipt": {"moved": ["lamp"]}, "lint": [], "reads_absent": []}' "$STUB_VERDICT" > "$run/evidence.json"
case "$STUB_VERDICT" in accepted) exit 0 ;; "not judged") exit 2 ;; *) exit 1 ;; esac
`);
	Object.assign(process.env, { METIS_CATALOG: r, METISC: join(bin, "metisc"), METIS_LOOP_PROPOSE: join(bin, "propose"), MODEL: "stub/script", METIS_LOOP_MODE: "tui" });
	return { r, bin };
}

test("metis-workspace: its tools, the trace verbs as declared, their schemas as JSON schema", () => {
	scratch();
	const p = fakePi();
	workspace(p.api);
	const declared = ws.tools().tools.map((t) => t.name);
	assert.ok(declared.includes("trace_case") && declared.includes("lint"), declared.join(" "));
	assert.deepEqual([...p.tools.keys()].sort(), ["bundle_build", "journal", "pack_propose", "surprise_list", "surprise_next", "workspace_context", ...declared].sort());
	const c = p.tools.get("trace_case").parameters;
	assert.equal(c.type, "object");
	assert.equal(c.properties.at.type, "integer");
	assert.equal(c.properties.after.items.type, "string");
	assert.ok(!("positional" in c.properties.trace) && !("flag" in c.properties.at));
	assert.deepEqual(schema({ type: "ARRAY", items: { type: "STRING", flag: "--x" } }), { type: "array", items: { type: "string" } });
});

test("metis-workspace: a dropped surprise taken, judged, ruled; the bundle rebuilt; the journal's trail", async () => {
	const { r, bin } = scratch();
	const p = fakePi();
	workspace(p.api);
	await p.emit("session_start", {}, ctx);
	try {
		assert.equal(ws.loops(r).pi!.pid, process.pid);                                  // the session holds the lock
		const ctxText = (await p.tools.get("workspace_context").execute("c", {})).content[0].text;
		assert.match(ctxText, /the lamp workspace/);
		assert.match(ctxText, /"stale": true/);                                           // no build yet
		assert.equal((await p.tools.get("surprise_next").execute("n0", {})).content[0].text, "no open surprise");
		const id = ws.drop_surprise({ member: "lamp", trace: "traces/s1", k: 7, atoms: ["lit"], words: "it should have stayed dark", config: "service.yaml" }, "backend", r);
		const next = await p.tools.get("surprise_next").execute("n1", {});
		assert.equal(next.details.surprise.id, id);
		assert.match(next.content[0].text, /it should have stayed dark/);
		assert.match(next.content[0].text, /% the lamp's rules/);                         // the member's program
		assert.equal(ws.surprise(id, r).status, "taken");
		assert.equal(ws.surprise(id, r).taken.pid, process.pid);
		// a paid brain without a budget is refused before anything runs
		await assert.rejects(p.tools.get("pack_propose").execute("j0", { id, pack: "% x", brain: "openrouter/m" }), /needs a budget/);
		process.env.STUB_VERDICT = "accepted";
		const j = await p.tools.get("pack_propose").execute("j1", { id, pack: "stage go {\n  dark [dyn] : $late * now -o ().\n}" });
		assert.equal(j.details.verdict, "accepted");
		const args = readFileSync(join(bin, "propose.args"), "utf8").split("\n");
		assert.equal(args[args.indexOf("--member") + 1], "lamp");
		assert.equal(args[args.indexOf("--trace") + 1], join(r, ".metis", "traces", "s1"));   // the workspace run, as a path
		assert.equal(args[args.indexOf("--config") + 1], join(r, "service.yaml"));           // the surprise's config
		assert.equal(args[args.indexOf("--composition") + 1], "domains");
		const ruled = ws.surprise(id, r);
		assert.equal(ruled.status, "ruled");
		assert.equal(ruled.ruling.verdict, "accepted");
		assert.match(readFileSync(join(r, ".metis", "rulings", `${id}.md`), "utf8"), /^# Ruling: accepted/);
		assert.match(readFileSync(join(r, ".metis", "packs", `${id}.llp`), "utf8"), /dark \[dyn\]/);
		await assert.rejects(p.tools.get("pack_propose").execute("j2", { id, pack: "% again" }), /ruled already/);
		// the bundle rebuilt: the image moves, STALE clears
		const b1 = await p.tools.get("bundle_build").execute("b1", {});
		assert.equal(b1.details.code, 0);
		assert.equal(b1.details.before, null);
		assert.equal(b1.details.after, "abc1");
		assert.equal(ws.bundle(undefined, r)!.stale, false);
		const b2 = await p.tools.get("bundle_build").execute("b2", {});
		assert.match(b2.content[0].text, /^image abc1 -> abc2/);
		await p.tools.get("journal").execute("w", { words: "ruled the lamp's surprise\nsecond line dropped" });
		const kinds = ws.events(0, r).filter((e) => e.who === "pi").map((e) => e.kind);
		assert.deepEqual(kinds, ["lock", "take", "judging", "ruling", "built", "built", "say"]);
		assert.equal(ws.events(0, r).at(-1)!.words, "ruled the lamp's surprise");
		assert.equal(ws.cost(r).total, 0);                                               // 0 USD: no brain, nothing spent
	} finally {
		await p.emit("session_shutdown", {}, {});
	}
	assert.equal(ws.loops(r).pi, null);                                                   // released at the session's end
});

test("metis-workspace: a refused pack is ruled refused; a surprise not taken is not judged", async () => {
	const { r } = scratch();
	const p = fakePi();
	workspace(p.api);
	await p.emit("session_start", {}, ctx);
	const id = ws.drop_surprise({ member: "lamp", trace: "traces/s1", k: 3, atoms: ["lit"], config: "service.yaml" }, "backend", r);
	await assert.rejects(p.tools.get("pack_propose").execute("j", { id, pack: "% x" }), /not taken: surprise_next first/);
	await p.tools.get("surprise_next").execute("n", {});
	const none = ws.drop_surprise({ member: "lamp", trace: "traces/s1", k: 4, atoms: ["lit"] }, "backend", r);
	ws.take_surprise(none, process.pid, "pi", r);
	await assert.rejects(p.tools.get("pack_propose").execute("j", { id: none, pack: "% x" }), /no service config/);   // none named anywhere
	process.env.STUB_VERDICT = "refused";
	const j = await p.tools.get("pack_propose").execute("j", { id, pack: "% x" });
	assert.equal(j.details.verdict, "refused");
	assert.equal(ws.surprise(id, r).ruling.verdict, "refused");
	await p.emit("session_shutdown", {}, {});
});

test("metis-workspace: a paid brain's spend reaches cost.jsonl, ruled or not; a take without a ruling releases itself", async () => {
	const { r } = scratch();
	const p = fakePi();
	workspace(p.api);
	await p.emit("session_start", {}, ctx);
	try {
		const a = ws.drop_surprise({ member: "lamp", trace: "traces/s1", k: 1, atoms: ["lit"], config: "service.yaml" }, "backend", r);
		const b = ws.drop_surprise({ member: "lamp", trace: "traces/s1", k: 2, atoms: ["lit"], config: "service.yaml" }, "backend", r);
		const c = ws.drop_surprise({ member: "lamp", trace: "traces/s1", k: 3, atoms: ["lit"], config: "service.yaml" }, "backend", r);
		for (let i = 0; i < 3; i++) await p.tools.get("surprise_next").execute(`n${i}`, {});
		Object.assign(process.env, { STUB_VERDICT: "accepted", STUB_COST: "0.0123" });
		const j = await p.tools.get("pack_propose").execute("ja", { id: a, pack: "% x", brain: "openrouter/m", budget: 0.5 });
		assert.equal(j.details.spent, 0.0123);                                            // from the brain's own log, not the document
		process.env.STUB_CRASH = "1";
		await assert.rejects(p.tools.get("pack_propose").execute("jb", { id: b, pack: "% x", brain: "openrouter/m", budget: 0.5 }), /wrote no ruling[\s\S]*is released: open again/);
		delete process.env.STUB_CRASH;
		assert.equal(ws.surprise(b, r).status, "open");                                   // a take without a ruling releases itself
		const cost = ws.cost(r);
		assert.equal(cost.calls, 2);                                                      // the crashed run's spend too
		assert.ok(Math.abs(cost.total - 0.0246) < 1e-9, String(cost.total));
		const rows = readFileSync(ws.path("cost", {}, r), "utf8").trim().split("\n").map((l) => JSON.parse(l));
		assert.deepEqual(rows.map((x) => x.surprise), [a, b]);
		Object.assign(process.env, { STUB_VERDICT: "not judged", STUB_COST: "" });
		const nj = await p.tools.get("pack_propose").execute("jc", { id: c, pack: "% x" });
		assert.equal(nj.details.ruling, null);
		assert.equal(ws.surprise(c, r).status, "open");                                   // no verdict: no ruling, released, taken again later
		assert.ok(ws.events(0, r).some((e) => e.kind === "not_judged" && e.surprise === c && /not judged/.test(String(e.reason))));
		assert.ok(ws.events(0, r).some((e) => e.kind === "not_judged" && e.surprise === b && /exit 3/.test(String(e.reason))));
		const again = await p.tools.get("surprise_next").execute("again", {});
		assert.ok([b, c].includes(again.details.surprise.id));                            // a released one is taken again (ids of one second sort by their hex)
	} finally {
		delete process.env.STUB_COST;
		await p.emit("session_shutdown", {}, {});
	}
});

test("metis-workspace: a loop that did not get the lock reads, and never takes, rules or builds", async () => {
	const { r } = scratch();
	const holder = spawn("sleep", ["30"]);
	try {
		ws.lock("pi", { mode: "rpc", model: "m" }, holder.pid!, r);
		const p = fakePi();
		workspace(p.api);
		notes.length = 0;
		await p.emit("session_start", {}, ctx);
		assert.match(notes.join("\n"), /holds this workspace/);
		assert.match((await p.tools.get("workspace_context").execute("c", {})).content[0].text, /the lamp workspace/);
		ws.drop_surprise({ member: "lamp", trace: "traces/s1", k: 1, atoms: ["lit"], config: "service.yaml" }, "backend", r);
		const held = new RegExp(`does not hold the workspace: pid ${holder.pid} \\(mode rpc`);
		await assert.rejects(p.tools.get("surprise_next").execute("n", {}), held);
		await assert.rejects(p.tools.get("bundle_build").execute("b", {}), held);
		await assert.rejects(p.tools.get("pack_propose").execute("j", { id: ws.surprises("open", r)[0].id, pack: "% x" }), held);
		assert.equal(ws.surprises("open", r).length, 1);                                    // nothing taken
		await p.emit("session_shutdown", {}, {});
		assert.equal(ws.loops(r).pi!.pid, holder.pid);                                      // the holder's lock untouched
	} finally {
		holder.kill();
	}
});

test("metis-workspace: a trace argument is a path, a workspace run resolved under .metis/", () => {
	const { r } = scratch();
	assert.equal(tracePath("traces/s1", r), join(r, ".metis", "traces", "s1"));
	assert.equal(tracePath("s1", r), join(r, ".metis", "traces", "s1"));
	assert.equal(tracePath("/abs/t", r), "/abs/t");
});

test("loop.sh: one pi loop per workspace: a live holder refuses a second start, a dead one's lock is taken over", async () => {
	const { r } = scratch();
	const holder = spawn("sleep", ["30"]);
	try {
		ws.lock("pi", { mode: "rpc", model: "m" }, holder.pid!, r);
		const e = { ...process.env, METIS_LOOP_PI: join(HERE, "stub", "pi"), METIS_CONFIG: "", METIS_LOOP_SDK_PY: PY, METIS_LOOP_TAKE_INTO: "", METIS_LOOP_LLP: "" };
		const a = spawnSync(join(HERE, "..", "loop.sh"), [], { encoding: "utf8", cwd: r, env: e as any });
		assert.equal(a.status, 1);
		assert.match(a.stderr, new RegExp(`a pi loop runs in .* already \\(pid ${holder.pid}, .*mode rpc\\): one per workspace`));
		const gone = once(holder, "exit");
		holder.kill();
		await gone;                                                                       // reaped: its pid is gone
		const b = spawnSync(join(HERE, "..", "loop.sh"), [], { encoding: "utf8", cwd: r, env: e as any });
		assert.equal(b.status, 0, b.stderr);
		assert.equal(JSON.parse(b.stdout).env.METIS_LOOP_MODE, "tui");
		const c = spawnSync(join(HERE, "..", "loop.sh"), ["--mode", "rpc"], { encoding: "utf8", cwd: r, env: e as any });
		assert.equal(JSON.parse(c.stdout).env.METIS_LOOP_MODE, "rpc");
	} finally {
		holder.kill();
	}
	assert.ok(existsSync(join(r, ".metis")));
});

test("metis-workspace: past the session's budget the loop refuses further model turns, journals it and releases the lock", async () => {
	const { r } = scratch();
	process.env.METIS_LOOP_BUDGET = "0.05";
	try {
		const p = fakePi();
		workspace(p.api);
		let aborted = 0;
		const c = { ...ctx, abort: () => aborted++ };
		await p.emit("session_start", {}, c);
		const msg = (cost: number) => ({ message: { role: "assistant", model: "deepseek/deepseek-v4-pro", usage: { cost: { total: cost } } } });
		await p.emit("message_end", { message: { role: "user" } }, c);                     // no cost: no row
		await p.emit("message_end", msg(0.03), c);
		assert.equal(ws.cost(r).total, 0.03);
		assert.equal((await p.emit("input", { text: "go on" }, c)).action, "continue");
		assert.equal(await p.emit("tool_call", { toolName: "journal", input: {} }, c), undefined);
		assert.equal(ws.loops(r).pi!.pid, process.pid);
		notes.length = 0;
		await p.emit("message_end", msg(0.03), c);                                          // 0.06 >= 0.05: over
		assert.equal(aborted, 1);
		assert.equal(ws.loops(r).pi, null);                                                 // the lock released, pi not killed
		assert.match(notes.join("\n"), /budget is spent: 0\.0600 of 0\.05 USD/);
		const b = ws.events(0, r).filter((x) => x.kind === "budget");
		assert.equal(b.length, 1);
		assert.equal(b[0].budget, 0.05);
		assert.equal((await p.emit("input", { text: "go on" }, c)).action, "handled");     // the person's turn reaches no model
		const t = await p.emit("tool_call", { toolName: "surprise_next", input: {} }, c);
		assert.equal(t.block, true);
		assert.equal(t.terminate, true);
		const rows = readFileSync(ws.path("cost", {}, r), "utf8").trim().split("\n").map((l) => JSON.parse(l));
		assert.deepEqual(rows.map((x) => [x.who, x.cost]), [["pi", 0.03], ["pi", 0.03]]);
		assert.equal(rows[1].usage_before, 0.03);
		await p.emit("message_end", msg(0.03), c);                                          // a late message is still logged, not re-journaled
		assert.equal(ws.events(0, r).filter((x) => x.kind === "budget").length, 1);
		await p.emit("session_shutdown", {}, {});
	} finally {
		delete process.env.METIS_LOOP_BUDGET;
	}
});

test("loop.sh: deepseek v4 pro by default, with a budget; a paid model without one is refused; the first line says both", () => {
	const { r } = scratch();
	const e: Record<string, string | undefined> = { ...process.env, METIS_LOOP_PI: join(HERE, "stub", "pi"), METIS_CONFIG: "", METIS_LOOP_SDK_PY: PY, METIS_LOOP_TAKE_INTO: "",
		METIS_LOOP_LLP: "", OPENROUTER_API_KEY: "sk-or-v1-" + "0".repeat(64) };       // a fake key: the stub pi calls nothing
	delete e.MODEL;
	delete e.METIS_LOOP_BUDGET;
	const run = (args: string[], extra: Record<string, string> = {}) => spawnSync(join(HERE, "..", "loop.sh"), args, { encoding: "utf8", cwd: r, env: { ...e, ...extra } as any });
	const a = run([]);
	assert.equal(a.status, 0, a.stderr);
	const out = JSON.parse(a.stdout);
	assert.equal(out.args[out.args.indexOf("--model") + 1], "openrouter/deepseek/deepseek-v4-pro");
	assert.equal(out.env.METIS_LOOP_BUDGET, "1.00");
	assert.equal(a.stderr.split("\n")[0], "loop.sh: MODEL=openrouter/deepseek/deepseek-v4-pro budget=1.00 USD");
	assert.match(readFileSync(out.env.METIS_CONFIG, "utf8"), /openai-command --base-url https:\/\/openrouter.ai\/api\/v1 --model deepseek\/deepseek-v4-pro/);  // formalize follows it
	assert.equal(JSON.parse(run(["--budget", "0.3"]).stdout).env.METIS_LOOP_BUDGET, "0.3");
	assert.equal(JSON.parse(run([], { METIS_LOOP_BUDGET: "2" }).stdout).env.METIS_LOOP_BUDGET, "2");
	const empty = run([], { METIS_LOOP_BUDGET: "" });
	assert.equal(empty.status, 1);
	assert.match(empty.stderr, /is paid: give --budget USD/);
	assert.match(run(["--budget", "lots"]).stderr, /a positive number of USD/);
	const free = run([], { MODEL: "stub/script" });
	assert.equal(free.stderr.split("\n")[0], "loop.sh: MODEL=stub/script budget=none USD");
});
