// metis-workspace — the pi loop in its workspace (docs/WORKSPACE.md §5.1; loop-workspace s-5b4be5fa step 3).
// The third extension, beside metis-repl and metis-domain: the tools that meet the backend in DIR/.metis/
// (files and a watch, never a socket: §2.4), over the loop SDK's TypeScript workspace face (./sdk/workspace.ts,
// metispy's metis.catalog.workspace; the .metis/ layout lives once, in its LAYOUT table). No workspace code of
// its own: every read and write is the face's, every trace verb the declared tool's (metis/trace_tools.json).
//
//   workspace_context   the text a brain is given first, the bundle, the loops, the surprises by status
//   surprise_list       the surprises (open | taken | ruled)
//   surprise_next       the oldest open surprise, TAKEN by this loop (its pid in surprises/<id>.taken), with what
//                       it needs: the record (member, trace, k or window, the person's words), the member's
//                       program, the earlier rulings on the same member
//   trace_* / lint      every declared verb of metis.trace and metis.lint, one tool each, generated at load
//                       from the declaration table (nothing written here that the verbs do not declare)
//   pack_propose        the pack verb (propose.sh: the gate cascade, the goldens, the cases, the fired diff on the
//                       trace's replay, the lint rows): its document and evidence become the surprise's ruling
//                       (rulings/<id>.md + .json, the pack in packs/<id>.llp); the model's words only with a brain
//                       (script:FILE at 0 USD, or openrouter/<id> with a budget; its spend in cost.jsonl)
//   bundle_build        `metisc build .` where the composition is, the image hash before and after (the
//                       backend's watch then flips STALE: §2.4)
//   journal             one line of the loop's own progress, in words, for the UI
//
// A ruling is never applied here: catalog_apply / catalog_edit (metis-repl) keep the person's gate.
// The lock: one pi loop per workspace (§2.3). This session takes .metis/loop/pi.json at its start (loop.sh
// refuses first when a live one holds it) and releases it at its end.
//
// Environment (loop.sh sets them):
//   METIS_CATALOG      the workspace (DIR; unset: the cwd)
//   METIS_LOOP_SDK_PY  a python with the loop SDK and metispy (the face runs `python -m metis.catalog.workspace`)
//   METIS_LOOP_MODE    tui | rpc (the lock's mode)          MODEL   the pi model (the lock's model)
//   METISC             metisc for bundle_build (else metisc on PATH)
//   METIS_LOOP_PROPOSE propose.sh for pack_propose (else ../propose.sh beside this file)
import { execFile } from "node:child_process";
import { appendFileSync, existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Type } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { cap } from "./lib/jsonl.ts";
import { writeRoot } from "./lib/roots.ts";
import * as catalog from "./sdk/catalog.ts";
import * as ws from "./sdk/workspace.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const TRACE_ARGS = new Set(["trace", "trace_a", "trace_b"]);

/** The declaration table's schema (OBJECT/STRING…, positional/flag) as a JSON schema pi can show the model. */
export function schema(p: any): any {
	if (!p || typeof p !== "object") return p;
	const out: any = {};
	for (const [k, v] of Object.entries(p)) {
		if (k === "positional" || k === "flag") continue;
		if (k === "type" && typeof v === "string") out.type = v.toLowerCase();
		else if (k === "properties") out.properties = Object.fromEntries(Object.entries(v as any).map(([n, s]) => [n, schema(s)]));
		else if (k === "items") out.items = schema(v);
		else out[k] = v;
	}
	return out;
}

/** A trace argument as the verb needs it: a path; a workspace one ("traces/<run>", "<run>") under .metis/. */
export function tracePath(v: string, root: string): string {
	if (isAbsolute(v)) return v;
	const st = ws.root(root).state;
	for (const c of [join(st, v), join(st, "traces", v), join(root, v)]) if (existsSync(c)) return c;
	return join(st, v);
}

/** Run a command in DIR, asynchronously (the judge takes minutes): its code, stdout, stderr. */
function run(cmd: string, args: string[], cwd: string, env: NodeJS.ProcessEnv = process.env): Promise<{ code: number; out: string; err: string }> {
	return new Promise((done) => {
		execFile(cmd, args, { cwd, env, maxBuffer: 1 << 26, encoding: "utf8" }, (e: any, out, err) =>
			done({ code: e ? (typeof e.code === "number" ? e.code : 127) : 0, out: String(out ?? ""), err: String(err ?? e?.message ?? "") }),
		);
	});
}

const text = (s: string, details: any = {}) => ({ content: [{ type: "text" as const, text: cap(s) }], details });
const json = (o: unknown) => JSON.stringify(o, null, 1);

export default function (pi: ExtensionAPI) {
	const root = () => resolve(writeRoot());
	let locked = false;

	// ---- the workspace: what a brain is given first ------------------------------------------------
	pi.registerTool({
		name: "workspace_context",
		label: "the workspace",
		description: "The workspace this loop runs in: its README, the bundle (composition, members, image, STALE and why), the loops (this one, the backend), and the surprises by status. Call it first.",
		parameters: Type.Object({}),
		async execute() {
			const r = root();
			const s = ws.surprises(undefined, r);
			const by: Record<string, number> = {};
			for (const x of s) by[x.status] = (by[x.status] ?? 0) + 1;
			const body = [ws.context(undefined, r), "", "## bundle", json(ws.bundle(undefined, r)), "", "## loops", json(ws.loops(r)), "", "## surprises", json(by)].join("\n");
			return text(body, { root: r, surprises: by });
		},
	});

	// ---- the surprises ------------------------------------------------------------------------------
	pi.registerTool({
		name: "surprise_list",
		label: "the surprises",
		description: "The surprises dropped to the loop (oldest first), each with its status: open (waiting), taken (a loop is on it), ruled (its ruling written).",
		parameters: Type.Object({ status: Type.Optional(Type.Union([Type.Literal("open"), Type.Literal("taken"), Type.Literal("ruled")])) }),
		async execute(_id, p) {
			const s = ws.surprises(p.status as ws.Status | undefined, root());
			return text(s.length ? json(s.map((x) => ({ id: x.id, ts: x.ts, member: x.member, trace: x.trace, k: x.k, window: x.window, status: x.status, words: x.words }))) : "(none)", { surprises: s });
		},
	});

	pi.registerTool({
		name: "surprise_next",
		label: "take the next surprise",
		description:
			"Take the oldest open surprise (this loop's, until its ruling) and get what it needs: the record (member, trace, tick k or window, the atoms or reading, the person's words), the member's program, and the rulings of earlier surprises on the same member. None open: says so. Then draft a case (trace_case) and a pack, and judge it with pack_propose.",
		parameters: Type.Object({}),
		async execute() {
			const r = root();
			const open = ws.surprises("open", r);
			if (!open.length) return text("no open surprise", { surprise: null });
			const s = open[0];
			ws.take_surprise(s.id, process.pid, "pi", r); // the face journals the take
			let program: string | null = null;
			let source = "";
			try {
				const g = catalog.get(s.member, r);
				program = g?.program ? resolve(r, g.program) : null;
				if (program && existsSync(program)) source = readFileSync(program, "utf8");
			} catch {
				// a member the catalog does not list: the record alone
			}
			const earlier = ws.rulings(r).filter((x: any) => x.id !== s.id && ws.surprise(x.id, r)?.member === s.member);
			const body = [
				`## surprise ${s.id} (taken)`,
				json(s),
				"",
				`## the member's program${program ? ` (${program})` : ""}`,
				source || "(not found in the catalog)",
				"",
				"## earlier rulings on this member",
				earlier.length ? json(earlier.map((x: any) => ({ id: x.id, verdict: x.verdict, md: x.md }))) : "(none)",
			].join("\n");
			return text(body, { surprise: s, program, earlier: earlier.map((x: any) => x.id) });
		},
	});

	// ---- the trace verbs, as declared (metis/trace_tools.json) --------------------------------------
	let declared: ws.Tool[] = [];
	try {
		declared = ws.tools().tools;
	} catch (e: any) {
		console.error(`metis-workspace: no trace tools (${e.message})`);
	}
	for (const t of declared) {
		pi.registerTool({
			name: t.name,
			label: t.verb ? `${t.module} ${t.verb}` : t.module,
			description: `${t.module}${t.verb ? " " + t.verb : ""}: ${t.description}. A trace is a path, or a workspace run ("traces/<run>").`,
			parameters: Type.Unsafe(schema(t.parameters)),
			async execute(_id, params: any) {
				const r = root();
				const args: Record<string, unknown> = { ...params };
				for (const k of Object.keys(args)) if (TRACE_ARGS.has(k) && typeof args[k] === "string") args[k] = tracePath(String(args[k]), r);
				const argv = ws.tool_argv(t.name, args);
				const res = await run(argv[0], argv.slice(1), r);
				return text(`${res.code === 0 ? "" : `exit ${res.code}\n`}${res.out}${res.err ? `\n${res.err}` : ""}`.trim() || "(no output)", { argv, code: res.code });
			},
		});
	}

	// ---- the pack verb: the judgement, as the surprise's ruling -------------------------------------
	pi.registerTool({
		name: "pack_propose",
		label: "judge a pack",
		description:
			"Judge a candidate pack for a taken surprise (propose.sh: the gate cascade, every member's goldens, the cases, the fired diff on the trace's replay, the lint rows; no world). The verdict is the gate's, mechanically; the ruling (rulings/<id>.md) and the pack (packs/<id>.llp) are written as the surprise's, which makes it ruled. Nothing is applied: the person applies an accepted pack through catalog_apply / catalog_edit. Takes minutes.",
		parameters: Type.Object({
			id: Type.String({ description: "the surprise's id (surprise_next)" }),
			pack: Type.String({ description: "the pack's text: rules in `stage S { }`, `pred` lines, `drop NAME`; or a whole program" }),
			config: Type.Optional(Type.String({ description: "the run's service config (default: the surprise's config)" })),
			cases: Type.Optional(Type.Array(Type.String(), { description: "case files (trace_case --into) the pack must pass" })),
			unit: Type.Optional(Type.String({ description: "the file the pack amends (default: the member's program)" })),
			brain: Type.Optional(Type.String({ description: "who writes the ruling's words: script:FILE (0 USD) or openrouter/<id> (needs budget); none: the evidence alone" })),
			budget: Type.Optional(Type.Number({ description: "a paid brain's cap, USD" })),
		}),
		async execute(_id, p) {
			const r = root();
			const s = ws.surprise(p.id, r);
			if (s.status === "ruled") throw new Error(`surprise ${p.id} is ruled already`);
			if (s.status !== "taken") throw new Error(`surprise ${p.id} is not taken: surprise_next first`);
			if (!s.trace) throw new Error(`surprise ${p.id} has no trace: nothing to replay (the ruling would have no fired diff)`);
			const config = p.config ?? (s as any).config;
			if (!config) throw new Error(`surprise ${p.id} names no service config: give config`);
			if (p.brain?.startsWith("openrouter/") && !(p.budget && p.budget > 0)) throw new Error("a paid brain needs a budget (USD)");
			const b = ws.bundle(undefined, r);
			const tmp = mkdtempSync(join(tmpdir(), "pack-propose-"));
			try {
				const pack = join(tmp, "pack.llp");
				writeFileSync(pack, p.pack.endsWith("\n") ? p.pack : p.pack + "\n");
				const argv = ["--pack", pack, "--member", s.member, "--trace", tracePath(s.trace, r), "--root", r, "--config", resolve(r, config), "--run", join(tmp, "run")];
				if (b) argv.push("--composition", dirname(b.composition));
				if (p.unit) argv.push("--unit", p.unit);
				for (const c of p.cases ?? []) argv.push("--case", resolve(r, c));
				if (p.brain) argv.push("--brain", p.brain);
				if (p.budget) argv.push("--budget", String(p.budget));
				ws.journal("pi", "judging", { surprise: p.id }, r);
				const res = await run(process.env.METIS_LOOP_PROPOSE || join(HERE, "..", "propose.sh"), argv, r);
				const md = join(tmp, "run", "ruling.md");
				const ev = join(tmp, "run", "evidence.json");
				if (!existsSync(md) || !existsSync(ev)) throw new Error(`propose.sh wrote no ruling (exit ${res.code}): ${(res.err || res.out).trim().slice(-1500)}`);
				const e = JSON.parse(readFileSync(ev, "utf8"));
				const doc = readFileSync(md, "utf8");
				const spent = Number(e.spent ?? (doc.match(/([0-9.]+) USD/) ?? [])[1] ?? 0) || 0;
				const fields = { moved: e.moved ?? e.receipt?.moved ?? [], lint: e.lint ?? [], reads_absent: e.reads_absent ?? [], spent, member: s.member, trace: s.trace };
				// the face journals the ruling
				const ruling = ws.rule(p.id, doc, String(e.verdict), { pack: readFileSync(pack, "utf8"), fields, who: "pi" }, r);
				if (spent > 0) appendFileSync(ws.path("cost", {}, r), JSON.stringify({ ts: new Date().toISOString(), who: "judge", model: p.brain, cost: spent, surprise: p.id }) + "\n");
				return text(`${e.verdict}: ${ruling}\n\n${doc}`, { verdict: e.verdict, ruling, code: res.code, spent });
			} finally {
				rmSync(tmp, { recursive: true, force: true });
			}
		},
	});

	// ---- the bundle ---------------------------------------------------------------------------------
	pi.registerTool({
		name: "bundle_build",
		label: "build the bundle",
		description: "Rebuild the workspace's bundle (`metisc build .` where its composition is) after an applied ruling: the image hash before and after, and metisc's account. The backend sees the new build and shows its sessions STALE.",
		parameters: Type.Object({}),
		async execute() {
			const r = root();
			const before = ws.bundle(undefined, r);
			if (!before) throw new Error("the workspace has no bundle (no domains/composition.yaml)");
			const cdir = join(r, dirname(before.composition));
			const res = await run(process.env.METISC || "metisc", ["build", "."], cdir);
			const after = ws.bundle(undefined, r);
			ws.journal("pi", "built", { bundle: before.name, image: after?.image ?? null, before: before.image, code: res.code }, r);
			const head = res.code === 0 ? `image ${before.image ?? "(none)"} -> ${after?.image ?? "(none)"}${after?.stale ? ` (still STALE: ${after.why})` : ""}` : `metisc build failed (exit ${res.code})`;
			return text(`${head}\n${res.out}${res.err ? `\n${res.err}` : ""}`.trim(), { before: before.image, after: after?.image ?? null, code: res.code });
		},
	});

	// ---- the journal: the loop's own words for the UI -----------------------------------------------
	pi.registerTool({
		name: "journal",
		label: "note progress",
		description: "One line of this loop's progress, in words, for the person watching the workspace (the UI's feed). Short: what you are doing and why.",
		parameters: Type.Object({ words: Type.String({ description: "one line" }) }),
		async execute(_id, p) {
			const row = ws.journal("pi", "say", { words: p.words.split("\n")[0].slice(0, 400) }, root());
			return text("noted", { row });
		},
	});

	// ---- the lock: one pi loop per workspace ---------------------------------------------------------
	pi.on("session_start", async (_e, ctx) => {
		try {
			ws.lock("pi", { mode: process.env.METIS_LOOP_MODE || "tui", cwd: root(), model: process.env.MODEL || null }, process.pid, root());
			locked = true; // the face journals the lock
		} catch (e: any) {
			ctx.ui.notify(`metis-workspace: ${e.message}`, "error");
		}
	});
	pi.on("session_shutdown", () => {
		if (!locked) return;
		try {
			ws.unlock("pi", process.pid, root());
		} catch {
			// the workspace gone with the session: nothing to release
		}
		locked = false;
	});
}
