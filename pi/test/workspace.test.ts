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
			for (const h of on.get(ev) ?? []) await h(e, c);
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
	// propose.sh: the judge's two files, its verdict from STUB_VERDICT, its arguments recorded
	exe(join(bin, "propose"), `#!/bin/sh
run=""; prev=""; for a in "$@"; do [ "$prev" = --run ] && run="$a"; prev="$a"; done
mkdir -p "$run"; printf '%s\\n' "$@" > "${bin}/propose.args"
printf '# Ruling: %s\\n\\nThe gate %s it. 0 USD.\\n' "$STUB_VERDICT" "$STUB_VERDICT" > "$run/ruling.md"
printf '{"verdict": "%s", "receipt": {"moved": ["lamp"]}, "lint": [], "reads_absent": []}' "$STUB_VERDICT" > "$run/evidence.json"
[ "$STUB_VERDICT" = accepted ]
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
	const id = ws.drop_surprise({ member: "lamp", trace: "traces/s1", k: 3, atoms: ["lit"], config: "service.yaml" }, "backend", r);
	await assert.rejects(p.tools.get("pack_propose").execute("j", { id, pack: "% x" }), /not taken: surprise_next first/);
	await p.tools.get("surprise_next").execute("n", {});
	process.env.STUB_VERDICT = "refused";
	const j = await p.tools.get("pack_propose").execute("j", { id, pack: "% x" });
	assert.equal(j.details.verdict, "refused");
	assert.equal(ws.surprise(id, r).ruling.verdict, "refused");
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
