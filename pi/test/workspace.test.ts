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
import { appendFileSync, chmodSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import workspace, { chatLine, derivedFrom, firings, readRefusal, ruleNames, ruleText, schema, signature, tracePath, whoseUnit } from "../extensions/metis-workspace.ts";
import repl from "../extensions/metis-repl.ts";
import domain from "../extensions/metis-domain.ts";
import { scoped } from "../extensions/lib/toolset.ts";
import * as ws from "../extensions/sdk/workspace.ts";
import { applied, sha } from "../extensions/lib/applied.ts";
import { changedRules } from "../extensions/lib/rules.ts";

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
	const chat = ["chat_diff", "chat_replay", "chat_ruling", "chat_status", "chat_surprises", "chat_why"];   // loop-chat step 3
	assert.deepEqual([...p.tools.keys()].sort(), ["bundle_build", "journal", "pack_propose", "rule_text", "surprise_list", "surprise_next", "workspace_context", ...declared, ...chat].sort());
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

test("metis-workspace: pack_propose never guesses a config: none on the surprise or the bundle is refused in words (the alf drive's L3)", async () => {
	const { r } = scratch();
	const p = fakePi();
	workspace(p.api);
	await p.emit("session_start", {}, ctx);
	try {
		assert.ok(!("config" in p.tools.get("pack_propose").parameters.properties));        // the model cannot pass one
		const id = ws.drop_surprise({ member: "lamp", trace: "traces/s1", k: 1, atoms: ["lit"] }, "backend", r);
		await p.tools.get("surprise_next").execute("n", {});
		assert.equal(ws.bundle(undefined, r)!.config, null);
		await assert.rejects(p.tools.get("pack_propose").execute("j", { id, pack: "% x" }),
			/cannot be judged here: no service config .*no service.yaml beside its composition.yaml.*do not write one/);
	} finally {
		await p.emit("session_shutdown", {}, {});
	}
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

test("metis-workspace: the session's end releases its takes that were not ruled (the architect's F7)", async () => {
	const { r } = scratch();
	const p = fakePi();
	workspace(p.api);
	await p.emit("session_start", {}, ctx);
	const a = ws.drop_surprise({ member: "lamp", trace: "traces/s1", k: 1, atoms: ["lit"], config: "service.yaml" }, "backend", r);
	const b = ws.drop_surprise({ member: "lamp", trace: "traces/s1", k: 2, atoms: ["lit"], config: "service.yaml" }, "backend", r);
	await p.tools.get("surprise_next").execute("n1", {});
	await p.tools.get("surprise_next").execute("n2", {});
	Object.assign(process.env, { STUB_VERDICT: "accepted", STUB_COST: "" });
	await p.tools.get("pack_propose").execute("ja", { id: a, pack: "% x" });
	assert.equal(ws.surprise(a, r).status, "ruled");
	assert.equal(ws.surprise(b, r).status, "taken");
	await p.emit("session_shutdown", {}, {});
	assert.equal(ws.surprise(a, r).status, "ruled");                                  // a ruled one is left as it is
	assert.equal(ws.surprise(b, r).status, "open");                                   // the unruled take is released
	assert.ok(!existsSync(ws.path("taken", { id: b }, r)));
	assert.ok(ws.events(0, r).some((e) => e.kind === "not_judged" && e.surprise === b && /ended without a ruling/.test(String(e.reason))));
	assert.equal(ws.loops(r).pi, null);                                               // and the lock
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
		assert.equal(JSON.parse(b.stdout).env.METIS_LOOP_TOOLS, "workspace");                // DIR has a bundle
		assert.equal(JSON.parse(spawnSync(join(HERE, "..", "loop.sh"), [], { encoding: "utf8", cwd: r, env: { ...e, METIS_LOOP_TOOLS: "all" } as any }).stdout).env.METIS_LOOP_TOOLS, "all");
		const bare = mkdtempSync(join(tmpdir(), "ws-pi-bare-"));
		assert.equal(JSON.parse(spawnSync(join(HERE, "..", "loop.sh"), [], { encoding: "utf8", cwd: bare, env: { ...e, METIS_CATALOG: bare } as any }).stdout).env.METIS_LOOP_TOOLS, "seed");   // no bundle
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
	// pascal (loop-test): --help prints the header and starts nothing, with no key and no SDK
	const h = spawnSync(join(HERE, "..", "loop.sh"), ["--help"], { encoding: "utf8", cwd: r, env: { PATH: process.env.PATH } as any });
	assert.equal(h.status, 0, h.stderr);
	assert.match(h.stdout, /^loop\.sh — the agentic loop/);
	assert.match(h.stdout, /--budget USD/);
	assert.doesNotMatch(h.stdout, /set -euo|^#/m);
	// the architect's F5: no key in the environment, the person's key file is read when private (mode 600), else refused
	const kd = mkdtempSync(join(tmpdir(), "ws-key-"));
	const kf = join(kd, "openrouter.env");
	writeFileSync(kf, "OPENROUTER_API_KEY=sk-or-v1-" + "1".repeat(64) + "\n");
	chmodSync(kf, 0o600);
	const nokey = { OPENROUTER_API_KEY: "", METIS_OPENROUTER_ENV: kf };
	const fromFile = run([], nokey);
	assert.equal(fromFile.status, 0, fromFile.stderr);
	assert.match(fromFile.stderr, new RegExp(`OPENROUTER_API_KEY from ${kf}`));
	assert.ok(!fromFile.stderr.includes("sk-or-v1-") && !fromFile.stdout.includes("sk-or-v1-"));   // never printed
	chmodSync(kf, 0o644);
	const loose = run([], nokey);
	assert.equal(loose.status, 1);
	assert.match(loose.stderr, /is not private \(chmod 600 it\): not read[\s\S]*needs OPENROUTER_API_KEY/);
	// nina's review: the file is PARSED, never sourced: a bare key, a spaced line, a trailing command: nothing runs, no
	// key in any output, and only a clean OPENROUTER_API_KEY= line (export, quotes, spaces around =) is read
	const fake = "sk-or-v1-" + "2".repeat(64);
	const ran = join(kd, "ran");
	for (const [body, ok] of [[fake + "\n", false], [`OPENROUTER_API_KEY = ${fake}\n`, true], [`OPENROUTER_API_KEY=${fake} touch ${ran}\n`, true],
		[`touch ${ran}\nexport OPENROUTER_API_KEY="${fake}"\n`, true], [`# no key here\n$(touch ${ran})\n`, false]] as [string, boolean][]) {
		writeFileSync(kf, body);
		chmodSync(kf, 0o600);
		const o = run([], nokey);
		assert.ok(!existsSync(ran), `nothing in the file runs: ${JSON.stringify(body)}`);
		assert.ok(!o.stderr.includes(fake) && !o.stdout.includes(fake), `no key in the output: ${JSON.stringify(body)}`);
		assert.equal(o.status, ok ? 0 : 1, `${JSON.stringify(body)}: ${o.stderr}`);
		if (ok) assert.match(o.stderr, /OPENROUTER_API_KEY from /);
		else assert.match(o.stderr, /has no OPENROUTER_API_KEY= line: not read[\s\S]*needs OPENROUTER_API_KEY/);
	}
	const none = run([], { OPENROUTER_API_KEY: "", METIS_OPENROUTER_ENV: "" });
	assert.equal(none.status, 1);
	assert.match(none.stderr, /needs OPENROUTER_API_KEY: the environment, or a key file/);
	// loop-prompt: reasoning on by default (pi's level); METIS_LOOP_THINKING=off|low|… is pi's suffix on a model without one
	assert.equal(run([], { METIS_LOOP_THINKING: "off" }).stderr.split("\n")[0], "loop.sh: MODEL=openrouter/deepseek/deepseek-v4-pro:off budget=1.00 USD");
	assert.equal(run([], { METIS_LOOP_THINKING: "low" }).stderr.split("\n")[0], "loop.sh: MODEL=openrouter/deepseek/deepseek-v4-pro:low budget=1.00 USD");
	assert.equal(run([], { METIS_LOOP_THINKING: "off", MODEL: "openrouter/x:high" }).stderr.split("\n")[0], "loop.sh: MODEL=openrouter/x:high budget=1.00 USD");
	assert.equal(run([], { METIS_LOOP_THINKING: "on" }).stderr.split("\n")[0], "loop.sh: MODEL=openrouter/deepseek/deepseek-v4-pro budget=1.00 USD");
	assert.equal(run([], { METIS_LOOP_THINKING: "" }).stderr.split("\n")[0], "loop.sh: MODEL=openrouter/deepseek/deepseek-v4-pro budget=1.00 USD");
	assert.match(run([], { METIS_LOOP_THINKING: "lots" }).stderr, /METIS_LOOP_THINKING=lots: off \| minimal/);
	const free = run([], { MODEL: "stub/script" });
	assert.equal(free.stderr.split("\n")[0], "loop.sh: MODEL=stub/script budget=none USD");
});

test("metis-workspace: surprise_next shows the member's program whole and each unit it includes as its signature; rule_text gives a rule whole; no primer", async () => {
	const { r } = scratch();
	const home = mkdtempSync(join(tmpdir(), "ws-pi-home-"));
	writeFileSync(join(home, "fam.llp"), "pred late : lamp.   % the clock's\nstage progress {\n  go_on [dyn] : $busy * go -o ().\n}\nstage safety {\n  %% Too late to stop: I stop.\n  stop_late [dyn] : $busy * $late\n      * now -o ().\n}\n");
	writeFileSync(join(r, "domains", "bund.llp"), "pred dim : lamp.\n");                   // a file of the bundle's directory
	writeFileSync(join(r, "domains", "lamp", "lamp.llp"), "catalog lamp 1.\ninclude \"fam.llp\".\ninclude \"../bund.llp\".\n% the lamp's own words\n");
	process.env.METIS_HOME = home;
	try {
		const p = fakePi();
		workspace(p.api);
		await p.emit("session_start", {}, ctx);
		ws.drop_surprise({ member: "lamp", trace: "traces/s1", k: 2, atoms: ["late"], config: "service.yaml" }, "backend", r);
		const out = await p.tools.get("surprise_next").execute("n", {});
		const t = out.content[0].text;
		assert.ok(t.includes("% the lamp's own words"), t);                                 // the program itself, whole
		assert.ok(t.includes(`## included (the family's, under METIS_HOME): ${join(home, "fam.llp")}\n(a pack that amends it gives unit=<this path>)`), t);
		assert.ok(t.includes("pred late : lamp.\nstage progress:\n  go_on [dyn]\nstage safety:\n  stop_late [dyn]  %% Too late to stop: I stop."), t);
		assert.ok(!t.includes("$busy * $late"), t);                                         // no bodies
		assert.ok(!t.includes("the clock's"), t);                                           // nor comments
		assert.doesNotMatch(t, /how a rule is written|every rule names its layer/);         // the primer is the prompt's (PROMPT.md §2)
		assert.ok(t.includes(`## included (the bundle's): ${join(r, "domains", "bund.llp")}\n(a pack that amends it gives unit=<this path>)\npred dim : lamp.`), t);
		assert.deepEqual(out.details.units, [{ path: join(home, "fam.llp"), kind: "shared" }, { path: join(r, "domains", "bund.llp"), kind: "shared" }]);
		const whole = (await p.tools.get("rule_text").execute("w", { names: ["stop_late", "nope"] })).content[0].text;
		assert.equal(whole, `${join(home, "fam.llp")}:7\n%% Too late to stop: I stop.\nstop_late [dyn] : $busy * $late\n* now -o ().\n\nnot a rule of these units: nope`);
		await p.emit("session_shutdown", {}, {});
	} finally {
		delete process.env.METIS_HOME;
	}
});

test("pack_propose: a pack's unit= names the source, never a file make generates (the architect, nina's review of step 1)", async () => {
	const { r } = scratch();
	const p = fakePi();
	workspace(p.api);
	await p.emit("session_start", {}, ctx);
	try {
		mkdirSync(join(r, "domains", "lamp", "tree"));
		writeFileSync(join(r, "domains", "lamp", "tree", "lamp_domain.llp"), "% DERIVED from ../lamp_domain.llp by gen (make): edit that file, never this one.\n");
		const id = ws.drop_surprise({ member: "lamp", trace: "traces/s1", k: 1, atoms: ["lit"], config: "service.yaml" }, "backend", r);
		await p.tools.get("surprise_next").execute("n", {});
		await assert.rejects(p.tools.get("pack_propose").execute("j", { id, pack: "% x", unit: "domains/lamp/tree/lamp_domain.llp" }),
			new RegExp(`unit=domains/lamp/tree/lamp_domain.llp is generated from ${join(r, "domains", "lamp", "lamp_domain.llp")} by make: give unit=`));
		assert.equal(ws.surprise(id, r).status, "taken");                                 // nothing judged, nothing ruled
	} finally {
		await p.emit("session_shutdown", {}, {});
	}
});

test("signature of an alfworld unit (the tree's nav, generated): declarations and rule names, the source it is made from", () => {
	// metis-worlds alfworld/domains/hier/tree/nav_domain.llp, trimmed to its shape (the bundle's generated unit)
	const nav = [
		"% DERIVED from ../nav_domain.llp by world/gen_hier.py tree (make): edit that file, never this one.",
		"% nav_domain — going places",
		"catalog nav_domain 1.",
		'provenance text "ALFWorld navigation as a lifted specialist" "2026-10-22".',
		"layers (dyn).",
		"stages (act).",
		"types (receptacle location).   % completed by the instance that includes this file (spec 12)",
		'include "iface/alfworld.llp".   % the family\'s crossing preds',
		"namespace nav produce (dyn).",
		"pred recat(receptacle, location) : nav.          % the receptacle's location",
		"pred at(location) : nav.",
		"stage act {",
		"  begin [dyn] : $goto(X0) * idle -o busy * tick__active(nav).",
		"  %% I go to {R}.",
		"  go [dyn] : goto(R) * at(L) * $recat(R, L2) * L <> L2 * busy * $tick__grant(nav, motion) -o at(L2) * reached(R) * idle * tick__done(nav).",
		"  %% {R} is right here.",
		"  here [dyn] : goto(R) * $at(L) * $recat(R, L) * busy -o reached(R) * idle * tick__done(nav).",
		"}",
	].join("\n");
	assert.equal(signature(nav), [
		"catalog nav_domain 1.", "layers (dyn).", "stages (act).", "types (receptacle location).", 'include "iface/alfworld.llp".',
		"namespace nav produce (dyn).", "pred recat(receptacle, location) : nav.", "pred at(location) : nav.",
		"stage act:", "  begin [dyn]", "  go [dyn]  %% I go to {R}.", "  here [dyn]  %% {R} is right here.",
	].join("\n"));
	assert.equal(derivedFrom("/w/hier/tree/nav_domain.llp", nav), "/w/hier/nav_domain.llp");
	assert.equal(derivedFrom("/w/hier/nav_domain.llp", "% nav_domain\n"), null);
	assert.match(ruleText([{ path: "t.llp", text: nav }], ["go[dyn]"]), /^t\.llp:15\n%% I go to \{R\}\.\n {0}go \[dyn\] : goto\(R\)/);
	// nina's review of step 1: a generated unit's rules come from its source (the text an edit takes), and a rule only
	// make writes says so; the signature marks those
	const src = ["catalog nav_domain 1.", "stage act {", "  %% I go to {R}.", "  go [dyn] : goto(R) * at(L) * $recat(R, L2) * L <> L2 -o at(L2) * reached(R).", "}"].join("\n");
	const gen = new Set(ruleNames(nav).filter((n) => !ruleNames(src).includes(n)));
	assert.deepEqual([...gen], ["begin", "here"]);
	assert.match(signature(nav, gen), /  begin \[dyn\] \(generated\)\n  go \[dyn\]  %% I go to \{R\}\.\n  here \[dyn\] \(generated\)  %% \{R\} is right here\./);
	const both = ruleText([{ path: "/w/hier/tree/nav_domain.llp", text: nav, src: { path: "/w/hier/nav_domain.llp", text: src } }], ["go", "begin"]);
	assert.equal(both, [
		"/w/hier/tree/nav_domain.llp:13 (generated by make, no rule in /w/hier/nav_domain.llp: amend the generator's input, not this rule)",
		"begin [dyn] : $goto(X0) * idle -o busy * tick__active(nav).",
		"",
		"/w/hier/nav_domain.llp:4",
		"%% I go to {R}.",
		"go [dyn] : goto(R) * at(L) * $recat(R, L2) * L <> L2 -o at(L2) * reached(R).",
		"(runs as generated in /w/hier/tree/nav_domain.llp:15: go [dyn] : goto(R) * at(L) * $recat(R, L2) * L <> L2 * busy * $tick__grant(nav, motion) -o at(L2) * reached(R) * idle * tick__done(nav).)",
	].join("\n"));
	// a type over several lines is never printed open
	assert.equal(signature("type alfkind {\n  apple bowl\n  cup }.\npred x : y."), "type alfkind {…} (3 names)\npred x : y.");
	// whose a shared unit is: by its path
	assert.equal(whoseUnit("/c/domains/fam.llp", "/c/domains", "/w/hier"), "the family's, under METIS_HOME");
	assert.equal(whoseUnit("/w/hier/capacity.llp", "/c/domains", "/w/hier"), "the bundle's");
	assert.equal(whoseUnit("/w/director_domain.llp", "/c/domains", "/w/hier"), "shared");
	assert.equal(whoseUnit("/w/hier2/x.llp", undefined, "/w/hier"), "shared");
});

test("the tool sets by mode (loop-prompt, PROMPT.md §3): workspace = the surprise loop's tools and catalog_edit; seed = none of the workspace's", () => {
	scratch();
	const names = (set: string | null, only = false) => {
		if (set) process.env.METIS_LOOP_TOOLS = set;
		else delete process.env.METIS_LOOP_TOOLS;
		try {
			const p = fakePi();
			if (!only) {
				repl(p.api);
				domain(p.api);
			}
			workspace(p.api);
			return [...p.tools.keys()].sort();
		} finally {
			delete process.env.METIS_LOOP_TOOLS;
		}
	};
	const mine = names(null, true);                                   // metis-workspace's own
	const all = names(null), w = names("workspace"), s = names("seed");
	assert.deepEqual(w, [...mine, "catalog_edit"].sort());
	assert.ok(w.length <= 30, `${w.length} tools in a workspace`);
	assert.ok(!s.some((n) => mine.includes(n)), s.join(" "));
	for (const n of ["catalog_new", "catalog_edit", "catalog_take", "domain_open"]) assert.ok(s.includes(n), n);
	// the REPL's verbs (repl_text, repl_formalize …) register later, at the session's start: the same filter holds then
	const got: string[] = [];
	const sp = scoped({ registerTool: (d: any) => got.push(d.name), n: 1 } as any, (n) => n === "catalog_edit");
	sp.registerTool({ name: "repl_text" });
	sp.registerTool({ name: "catalog_edit" });
	assert.deepEqual(got, ["catalog_edit"]);
	assert.equal((sp as any).n, 1);
	assert.deepEqual([...new Set([...s, ...mine])].sort(), all);
	assert.deepEqual(names("bogus"), all);                            // an unknown set: every tool, and says so
});

test("metis-workspace: the chat's read-only commands are tools: their line from the declaration, answered on the workspace", async () => {
	const why = { name: "why", parameters: { properties: { atom: { type: "STRING", positional: 0 }, at: { type: "INTEGER", flag: "--at" } } } };
	assert.equal(chatLine(why, { atom: "brake_late", at: 41 }), "/why brake_late --at 41");
	assert.equal(chatLine({ name: "replay", parameters: { properties: { run: { positional: 0 }, window: { positional: 1 } } } }, { window: "412..430" }), "/replay 412..430");
	assert.equal(chatLine({ name: "status", parameters: { properties: {} } }, {}), "/status");
	assert.equal(chatLine({ name: "surprises", parameters: { properties: { status: { positional: 0 } } } }, { status: "a b" }), '/surprises "a b"');
	scratch();
	const p = fakePi();
	workspace(p.api);
	const r = await p.tools.get("chat_status").execute("c1", {});
	assert.match(r.content[0].text, /surprises: 0 open, 0 taken, 0 ruled/, r.content[0].text);
	assert.equal(r.details.line, "/status");
});

test("the system prompt: a workspace surprise is ruled through pack_propose; the person's own loop is the seed-domain skill's", () => {
	const t = readFileSync(join(HERE, "..", "prompts", "loop-system.md"), "utf8");
	assert.match(t, /the explanation is a pack, never a hand edit of the program/);
	assert.match(t, /Judge it with `pack_propose`/);
	assert.match(t, /The verdict is the gate's, never yours, and the ruling is written whatever it says/);
	assert.match(t, /read the skill `seed-domain` first/);
	for (const n of ["repl_text", "repl_formalize", "repl_gate", "catalog_new", "catalog_take", "domain_open"]) assert.ok(!t.includes(n), `${n} is the seed-domain skill's`);
});

test("the system prompt: the chat (loop-chat step 3, CHAT.md §2): words at every turn's end, a take in one turn, the intents", () => {
	const t = readFileSync(join(HERE, "..", "prompts", "loop-system.md"), "utf8");
	assert.match(t, /## The chat/);
	assert.match(t, /End every turn with at least one line of words/);
	assert.match(t, /in ONE turn/);
	for (const intent of ["take", "explain", "why", "propose", "apply", "replay", "status", "narrate", "compare", "undo", "what changed"])
		assert.ok(t.includes(`*${intent}`), intent);
	for (const tool of ["chat_status", "chat_replay", "chat_why", "chat_diff", "chat_ruling", "chat_surprises"]) assert.ok(t.includes(tool), tool);
});

test("metis-workspace: past half the budget each tool reply carries the spend; the kernel's formalize spend is charged too", async () => {
	const { r } = scratch();
	const recs = mkdtempSync(join(tmpdir(), "ws-pi-recs-"));
	const flog = join(recs, "formalize-calls.jsonl");
	writeFileSync(flog, JSON.stringify({ model: "deepseek/deepseek-v4-pro", cost: 0.5 }) + "\n");       // before this session: not its spend
	Object.assign(process.env, { METIS_LOOP_BUDGET: "0.10", METIS_LOOP_RECORDS: recs });
	try {
		const p = fakePi();
		workspace(p.api);
		const c = { ...ctx, abort: () => {} };
		await p.emit("session_start", {}, c);
		const msg = (cost: number) => ({ message: { role: "assistant", model: "deepseek/deepseek-v4-pro", usage: { cost: { total: cost } } } });
		const reply = { content: [{ type: "text", text: "the tool's own" }] };
		await p.emit("message_end", msg(0.03), c);
		assert.equal(await p.emit("tool_call", { toolName: "journal", input: {} }, c), undefined);
		assert.equal(await p.emit("tool_result", reply, c), undefined);                    // 0.03 < 0.05: nothing said
		appendFileSync(flog, JSON.stringify({ model: "deepseek/deepseek-v4-pro", cost: 0.025, tokens: 300 }) + "\n");   // a repl_formalize
		const said = await p.emit("tool_result", reply, c);
		assert.equal(said.content[0].text, "the tool's own");
		assert.match(said.content[1].text, /^\[budget: 0\.0550 of 0\.1 USD spent; 1 tool calls, 1 model requests in this session\. Finish the surprise, or stop\.\]$/);
		const rows = readFileSync(ws.path("cost", {}, r), "utf8").trim().split("\n").map((l) => JSON.parse(l));
		assert.deepEqual(rows.map((x) => [x.who, x.cost]), [["pi", 0.03], ["formalize", 0.025]]);   // one log: the old 0.5 is not charged
		assert.equal(ws.cost(r).total, 0.055);
		appendFileSync(flog, JSON.stringify({ model: "deepseek/deepseek-v4-pro", cost: 0.05 }) + "\n");
		await p.emit("message_end", { message: { role: "user" } }, c);                       // picked up at the next message: 0.105 >= 0.10
		assert.equal(ws.events(0, r).filter((x) => x.kind === "budget").length, 1);
		assert.equal(ws.loops(r).pi, null);
		await p.emit("session_shutdown", {}, {});
	} finally {
		delete process.env.METIS_LOOP_BUDGET;
		delete process.env.METIS_LOOP_RECORDS;
	}
});

test("pi.sh: a checkout without pi installed says the fix (the architect's F4: exit 127 and no word)", () => {
	const d = mkdtempSync(join(tmpdir(), "pi-sh-"));
	writeFileSync(join(d, "pi.sh"), readFileSync(join(HERE, "..", "pi.sh"), "utf8"));
	chmodSync(join(d, "pi.sh"), 0o755);
	const r = spawnSync(join(d, "pi.sh"), ["--mode", "rpc"], { encoding: "utf8" });
	assert.equal(r.status, 127);
	assert.match(r.stderr, new RegExp(`pi.sh: pi is not installed in ${d} .*run ${d}/setup.sh once`));
});

test("loop.sh: its own option after pi's arguments is refused, not handed to pi", () => {
	const { r } = scratch();
	const e = { ...process.env, METIS_LOOP_PI: join(HERE, "stub", "pi"), METIS_CONFIG: "", METIS_LOOP_SDK_PY: PY, MODEL: "stub/script" };
	const a = spawnSync(join(HERE, "..", "loop.sh"), ["--mode", "rpc", "--budget", "1"], { encoding: "utf8", cwd: r, env: e as any });
	assert.equal(a.status, 2);
	assert.match(a.stderr, /--budget after pi's arguments: give loop.sh's options first/);
	assert.equal(spawnSync(join(HERE, "..", "loop.sh"), ["--budget", "1", "--mode", "rpc", "--name", "s"], { encoding: "utf8", cwd: r, env: e as any }).status, 0);   // pi's own --name passes
});

test("metis-workspace: the ruling counts the candidate's firings beside its verdict (step 4, the brake_late lesson)", () => {
	// the shape of the judge's evidence.json: round 3's rule-target-2 (two rows, brake_target where the record kept the limit)
	const e = {
		rules: ["accel", "brake_target", "keep_limit"],
		rows: [
			{ k: 401, fired: { record: ["decide", "keep_limit", "back"], candidate: ["decide", "brake_target[R=brake_min_correct]", "back"] } },
			{ k: 481, fired: { record: ["decide", "keep_limit", "back"], candidate: ["decide", "brake_target[R=brake_min_correct]", "back"] } },
			{ k: 500, fired: { record: ["decide", "back"], candidate: ["decide", "back", "decide"] } },
		],
	};
	assert.deepEqual(firings(e), { count: 2, rows: 2, of_rows: 3, first: 401, last: 481 });
	assert.deepEqual(firings({}), { count: 0, rows: 0, of_rows: 0, first: null, last: null });
});

test("the prompt and the skills (loop-prompt step 2, PROMPT.md §2-3): sizes, every tool named exists in its mode, each SKILL.md parses; pi's read stays inside", () => {
	scratch();
	const set = (mode: string | null) => {
		if (mode) process.env.METIS_LOOP_TOOLS = mode;
		else delete process.env.METIS_LOOP_TOOLS;
		try {
			const p = fakePi();
			repl(p.api);
			domain(p.api);
			workspace(p.api);
			return new Set([...p.tools.keys(), "read"]);                 // pi's read: pi.sh --tools +read
		} finally {
			delete process.env.METIS_LOOP_TOOLS;
		}
	};
	const wsSet = set("workspace"), all = set(null);
	const named = (text: string) => [...text.matchAll(/`([a-z][a-z0-9_]*)`/g)].map((m) => m[1]);
	const prompt = readFileSync(join(HERE, "..", "prompts", "loop-system.md"), "utf8");
	assert.ok(Buffer.byteLength(prompt) <= 7168, `the system prompt is ${Buffer.byteLength(prompt)} bytes (≤ 7 KB)`);
	const missing = named(prompt).filter((n) => !wsSet.has(n));
	assert.deepEqual(missing, [], "every tool the prompt names is registered in a workspace");
	const dirs = readdirSync(join(HERE, "..", "skills"), { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => d.name).sort();
	assert.deepEqual(dirs, ["metis-language", "seed-domain", "surprise-ruling"]);
	for (const m of prompt.matchAll(/skill `([a-z-]+)`/g)) assert.ok(dirs.includes(m[1]), `the prompt names skill ${m[1]}`);
	for (const d of dirs) {
		const text = readFileSync(join(HERE, "..", "skills", d, "SKILL.md"), "utf8");
		assert.ok(Buffer.byteLength(text) <= 8192, `${d}/SKILL.md is ${Buffer.byteLength(text)} bytes (≤ 8 KB)`);
		const fm = text.match(/^---\nname: ([a-z0-9-]+)\ndescription: (.+)\n---\n/);
		assert.ok(fm, `${d}/SKILL.md opens with its frontmatter`);
		assert.equal(fm![1], d);
		assert.ok(fm![2].length >= 80 && fm![2].length <= 1024, `${d}'s description is ${fm![2].length} characters (pi: ≤ 1024)`);
		assert.match(fm![2], /Load (when|before)/, `${d}'s description says when to load it`);
		const unknown = named(text).filter((n) => /_/.test(n) && !all.has(n) && !/^(tick__|intent_)/.test(n));
		const tools = named(text).filter((n) => all.has(n));
		// the REPL's verbs and the domain's tools register at the session's start (metis's help, the agent's declaration):
		// only the families registered at load are checked here
		assert.deepEqual(unknown.filter((n) => /^(catalog|trace|chat|surprise|pack|bundle|workspace|rule)_/.test(n)), [], `${d} names only tools that exist`);
		assert.ok(d === "metis-language" || tools.length > 0, `${d} names its tools`);
	}
	for (const f of readdirSync(join(HERE, "..", "skills", "surprise-ruling", "rulings")).filter((x) => x !== "README.md"))
		assert.ok(existsSync(join(HERE, "..", "skills", "surprise-ruling", "rulings", f)), f);
	const sh = readFileSync(join(HERE, "..", "pi.sh"), "utf8");
	assert.match(sh, /--no-builtin-tools --tools \+read /);                // +read adds read; a bare `read` would be an allowlist dropping the extensions' tools
	assert.match(sh, /SKILLS\+=\(--skill /);
	// pi's read: the skills and the workspace, never elsewhere, never an .env, never the key file; a path resolved as pi's
	// read resolves it (nina's review of step 2: @, ~, file:// and a symlink)
	const r = mkdtempSync(join(tmpdir(), "ws-read-"));
	const kd = mkdtempSync(join(tmpdir(), "ws-key-"));
	const key = join(kd, "my-openrouter-key");                         // any name: refused by its real path
	writeFileSync(key, "OPENROUTER_API_KEY=x\n");
	writeFileSync(join(r, "README.md"), "x\n");
	const no = (p: string) => readRefusal(p, r, r, undefined, key);
	assert.equal(no(join(HERE, "..", "skills", "metis-language", "SKILL.md")), null);
	assert.equal(no("README.md"), null);
	assert.equal(no("@README.md"), null);
	assert.equal(no(`file://${join(r, "README.md")}`), null);
	for (const p of ["@~/.ssh/id_ed25519", "@/etc/passwd", "file:///etc/passwd", "~/.bashrc", "/etc/passwd", "../elsewhere/x.llp"])
		assert.match(no(p) ?? "", /outside the skills .* and the workspace/, p);
	assert.match(no("~/.config/metis/openrouter.env") ?? "", /\.env file|key file|outside/);
	assert.match(no(key) ?? "", /the key file is never read here/);
	assert.match(no(`@${key}`) ?? "", /the key file/);
	symlinkSync(key, join(r, "notes.txt"));                            // a symlink in the workspace to the key file
	assert.match(no("notes.txt") ?? "", /the key file is never read here/);
	symlinkSync("/etc/passwd", join(r, "pw.txt"));                     // … or to anything outside
	assert.match(no("pw.txt") ?? "", /outside/);
	writeFileSync(join(r, "service.env"), "K=1\n");
	assert.match(no("service.env") ?? "", /\.env file/);
});

test("metis-workspace: pi's read is blocked outside the skills and the workspace, at the tool call", async () => {
	const { r } = scratch();
	const p = fakePi();
	workspace(p.api);
	const no = await p.emit("tool_call", { toolName: "read", input: { path: "@/etc/hostname" } }, { ...ctx, cwd: r });
	assert.equal(no.block, true);
	assert.match(no.reason, /outside the skills/);
	assert.equal(await p.emit("tool_call", { toolName: "read", input: { path: "README.md" } }, { ...ctx, cwd: r }), undefined);   // pi's cwd
	assert.equal(await p.emit("tool_call", { toolName: "surprise_list", input: {} }, ctx), undefined);
});

test("catalog_edit in a workspace is the apply of an ACCEPTED ruling, or refused in words; a comment-only edit applies nothing (the architect's F1, step 5)", async () => {
	const { r } = scratch();
	process.env.METIS_LOOP_TOOLS = "workspace";
	const p = fakePi();
	workspace(p.api);
	repl(p.api);
	await p.emit("session_start", {}, ctx);
	try {
		const id = ws.drop_surprise({ member: "lamp", trace: "traces/s1", k: 7, atoms: ["lit"], words: "w", config: "service.yaml" }, "backend", r);
		await p.tools.get("surprise_next").execute("n", {});
		const edit = (input: any) => p.emit("tool_call", { toolName: "catalog_edit", toolCallId: "e" + Math.random(), input }, ctx);
		// no ruling yet: a rule is refused before the person is asked
		const none = await edit({ domain: "lamp", path: "lamp.llp", old_string: "% the lamp's rules\n", new_string: "% the lamp's rules\nstage go {\n  dark [dyn] : $late -o ().\n}\n" });
		assert.equal(none.block, true);
		assert.match(none.reason, /not the judged pack: 1 rule\(s\) of this edit \(dark\) are in no accepted ruling \(none in this workspace\)/);
		process.env.STUB_VERDICT = "accepted";
		await p.tools.get("pack_propose").execute("j", { id, pack: "stage go {\n  %% I go dark late.\n  dark [dyn] : $late * now -o ().\n}" });
		// a rule that is not the accepted pack's
		const other = await edit({ domain: "lamp", path: "lamp.llp", old_string: "% the lamp's rules\n", new_string: "% the lamp's rules\nstage go {\n  dark [dyn] : $late -o ().\n}\n" });
		assert.equal(other.block, true);
		assert.match(other.reason, new RegExp(`\\(dark\\) are in no accepted ruling \\(accepted: ${id}\\)`));
		// the accepted pack's rule, another %% line and spacing: it applies (the gate's own plan follows)
		const ok = applied({ domain: "lamp", path: "lamp.llp", old_string: "% the lamp's rules\n", new_string: "% the lamp's rules\nstage go {\n  %% my own words\n  dark [dyn] :   $late * now\n    -o ().\n}\n" }, r);
		assert.equal(ok.say, ` Applies the accepted ruling ${id}.`);
		assert.deepEqual(ok.applied!.ids, [id]);
		// a comment-only edit applies nothing, and says so
		const note = applied({ domain: "lamp", path: "lamp.llp", old_string: "% the lamp's rules\n", new_string: "% the lamp's rules, fixed\n" }, r);
		assert.match(note.say, /No rule changed: this edit applies no ruling/);
		assert.equal(note.applied, undefined);
		// undo: only the exact reversal of an applied edit
		ws.journal("pi", "applied", { surprise: id, domain: "lamp", path: "lamp.llp", old_sha: sha("A"), new_sha: sha("B") }, r);
		assert.throws(() => applied({ domain: "lamp", path: "lamp.llp", old_string: "B", new_string: "C", ruling: "undo" }, r), /undo: no applied edit is reversed/);
		const un = applied({ domain: "lamp", path: "lamp.llp", old_string: "B", new_string: "A", ruling: "undo" }, r);
		assert.match(un.say, new RegExp(`Reverses the applied edit of ruling ${id}`));
		assert.equal(un.applied!.undo, true);
		// not a .llp, or not a workspace: no tie
		assert.equal(changedRules("a [dyn] : x -o y.", "%% doc\na [dyn] :  x -o y .").length, 0);
	} finally {
		await p.emit("session_shutdown", {}, {});
		delete process.env.METIS_LOOP_TOOLS;
	}
});

test("pack_propose: a bare unit name is found under the bundle; a name no file has is refused in words and the take kept (the architect's F3, step 5)", async () => {
	const { r, bin } = scratch();
	const p = fakePi();
	workspace(p.api);
	await p.emit("session_start", {}, ctx);
	try {
		const id = ws.drop_surprise({ member: "lamp", trace: "traces/s1", k: 7, atoms: ["lit"], words: "w", config: "service.yaml" }, "backend", r);
		await p.tools.get("surprise_next").execute("n", {});
		await assert.rejects(p.tools.get("pack_propose").execute("j0", { id, pack: "% x", unit: "nothing.llp" }), /unit=nothing\.llp: no such file under [\s\S]*stays taken/);
		assert.equal(ws.surprise(id, r).status, "taken");                              // not released
		process.env.STUB_VERDICT = "accepted";
		const j = await p.tools.get("pack_propose").execute("j1", { id, pack: "% x", unit: "lamp.llp" });
		assert.match(j.content[0].text, /^unit lamp\.llp read as domains\/lamp\/lamp\.llp\naccepted/);
		const args = readFileSync(join(bin, "propose.args"), "utf8").split("\n");
		assert.equal(args[args.indexOf("--unit") + 1], "domains/lamp/lamp.llp");
	} finally {
		await p.emit("session_shutdown", {}, {});
	}
});
