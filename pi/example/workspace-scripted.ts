// The workspace's flow end to end with the model's choices scripted (docs/WORKSPACE.md §4; loop-workspace
// s-5b4be5fa step 3): the same extensions pi loads (metis-workspace, metis-repl), their tools called in the loop's
// order by this script instead of a model, against the real processes — the workspace face, the real judge
// (propose.sh), the catalog's gate with a scripted person, `metisc build .` — at 0 USD (no brain writes the
// ruling's words). A surprise the backend drops is taken, judged on its trace, ruled, applied at the person's
// confirm, and the bundle is rebuilt: the backend's STALE flips.
//
//   node/bin/node --experimental-strip-types example/workspace-scripted.ts DIR SPEC.json
//
// DIR is the workspace (DIR/domains/ the bundle, DIR/.metis/traces/<run>/ the trace). SPEC.json:
//   {"surprise": {member, trace: "traces/<run>", k, atoms|reading, words, config?},
//    "pack": "FILE.llp", "config"?: "the service config", "apply": {"path": "<member>/<member>.llp", "after": "a unique line"}}
// apply: an accepted pack is written into that file after that line, through catalog_edit (the gate's plan, the
// person's confirm). The run's transcript is DIR/.metis/workspace-scripted.md.
import { appendFileSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import repl from "../extensions/metis-repl.ts";
import workspace from "../extensions/metis-workspace.ts";
import * as ws from "../extensions/sdk/workspace.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const PKGS = join(HERE, "..", "..", "..");
const dir = resolve(process.argv[2] ?? ".");
const spec = JSON.parse(readFileSync(resolve(process.argv[3] ?? join(dir, "spec.json")), "utf8"));
const sdkPy = process.env.METIS_LOOP_SDK_PY ?? join(PKGS, ".venv", "bin", "python");
Object.assign(process.env, {
	METIS_CATALOG: dir,
	METIS_LOOP_SDK_PY: sdkPy,
	METIS_LOOP_METIS: process.env.METIS_LOOP_METIS ?? join(PKGS, ".venv", "bin", "metis"),
	METIS_LOOP_RUN: join(dir, ".metis"),
	METIS_LOOP_RECORDS: join(dir, ".metis", "records"),
	METIS_LOOP_LLP: "",
	METIS_LOOP_MODE: "tui",
	MODEL: "script:workspace-scripted",
});
process.chdir(dir);

const log = join(dir, ".metis", "workspace-scripted.md");
writeFileSync(log, `# the workspace's flow, scripted (${new Date().toISOString()}; 0 USD: no brain)\n\n`);
const say = (s: string) => {
	appendFileSync(log, s + "\n");
	console.log(s);
};
const t0 = Date.now();
const secs = () => ((Date.now() - t0) / 1000).toFixed(0);

const tools = new Map<string, any>();
const on = new Map<string, ((e: any, c: any) => any)[]>();
const api: any = {
	registerTool: (t: any) => tools.set(t.name, t),
	registerCommand: () => {},
	on: (ev: string, h: any) => on.set(ev, [...(on.get(ev) ?? []), h]),
	sendMessage: () => {},
};
const emit = async (ev: string, e: any, c: any) => {
	let r;
	for (const h of on.get(ev) ?? []) r = await h(e, c);
	return r;
};
const person = { hasUI: true, ui: { notify: (m: string) => say(`  _notify: ${m}_`), confirm: async (title: string) => (say(`  **gate**: ${title} — **the person approves**`), true) } };

let n = 0;
async function call(name: string, args: Record<string, unknown>): Promise<any> {
	const id = `w${++n}`;
	say(`→ \`${name}\` ${JSON.stringify(args).slice(0, 300)}  _[${secs()} s]_`);
	const blocked = await emit("tool_call", { toolName: name, toolCallId: id, input: args }, person);
	if (blocked?.block) {
		say(`  ← BLOCKED: ${blocked.reason}`);
		throw new Error(`blocked: ${blocked.reason}`);
	}
	const r = await tools.get(name).execute(id, args);
	say(`  ← ${r.content.map((c: any) => c.text).join("\n").slice(0, 2500).replace(/\n/g, "\n    ")}`);
	return r;
}

repl(api);
workspace(api);
await emit("session_start", {}, person);
try {
	say("## the backend drops a surprise\n");
	const id = ws.drop_surprise(spec.surprise, "backend", dir);
	say(`  dropped ${id}: ${JSON.stringify(spec.surprise)}\n`);
	say("## the pi loop\n");
	await call("workspace_context", {});
	const next = await call("surprise_next", {});
	if (next.details.surprise?.id !== id) throw new Error(`surprise_next took ${next.details.surprise?.id}, not ${id}`);
	await call("journal", { words: `on surprise ${id}: ${spec.surprise.words ?? ""}` });
	const pack = readFileSync(resolve(spec.pack), "utf8");
	const j = await call("pack_propose", { id, pack, ...(spec.config ? { config: spec.config } : {}) });
	say(`\n**verdict: ${j.details.verdict}** (${j.details.ruling})\n`);
	if (j.details.verdict === "accepted" && spec.apply) {
		say("## applied at the person's confirm\n");
		const [domain] = String(spec.apply.path).split("/");
		const file = join(dir, "domains", spec.apply.path);
		const text = readFileSync(file, "utf8");
		if (text.split(spec.apply.after).length !== 2) throw new Error(`apply.after is not one line of ${file}`);
		await call("catalog_edit", { domain, path: String(spec.apply.path).split("/").slice(1).join("/"), old_string: spec.apply.after, new_string: `${spec.apply.after}\n${pack.trimEnd()}` });
		say(`\n  bundle after the apply: ${JSON.stringify(ws.bundle(undefined, dir))}\n`);
		say("## the bundle rebuilt\n");
		await call("bundle_build", {});
		await call("journal", { words: `surprise ${id} ruled ${j.details.verdict}, applied, the bundle rebuilt` });
	}
	say(`\n## the trail (the journal)\n\n${ws.events(0, dir).map((e) => "    " + JSON.stringify(e)).join("\n")}\n`);
	say(`cost: ${JSON.stringify(ws.cost(dir))}; ${secs()} s`);
} finally {
	await emit("session_shutdown", {}, {});
}
