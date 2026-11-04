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
//                       program, each unit it includes as its signature (declarations, rule names with their %%
//                       lines: loop-prompt, PROMPT.md §2), the earlier rulings on the same member
//   rule_text           named rules whole, with path:line, from the member's units
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
// A ruling is never applied here: catalog_edit (metis-repl) keeps the person's gate.
// The lock: one pi loop per workspace (§2.3). This session takes .metis/loop/pi.json at its start (loop.sh
// refuses first when a live one holds it) and releases it at its end.
//
// Environment (loop.sh sets them):
//   METIS_CATALOG      the workspace (DIR; unset: the cwd)
//   METIS_LOOP_SDK_PY  a python with the loop SDK and metispy (the face runs `python -m metis.catalog.workspace`)
//   METIS_LOOP_MODE    tui | rpc (the lock's mode)          MODEL   the pi model (the lock's model)
//   METIS_LOOP_TOOLS   workspace | seed | all: the tool set (lib/toolset.ts; seed registers none of these)
//   METISC             metisc for bundle_build (else metisc on PATH)
//   METIS_LOOP_PROPOSE propose.sh for pack_propose (else ../propose.sh beside this file)
import { execFile, spawnSync } from "node:child_process";
import { appendFileSync, existsSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Type } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { cap } from "./lib/jsonl.ts";
// pi's own path resolution for read (not exported by the package: imported by its file, so the guard resolves a path
// exactly as the read tool will: a leading @ stripped, ~ expanded, file:// converted, the macOS variants tried)
import { resolveReadPath } from "../node_modules/@earendil-works/pi-coding-agent/dist/core/tools/path-utils.js";
import { writeRoot } from "./lib/roots.ts";
import { scoped, toolset } from "./lib/toolset.ts";
import * as catalog from "./sdk/catalog.ts";
import * as ws from "./sdk/workspace.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const LOOP_REPO = resolve(HERE, "..", "..");             // metis-loop: its loop/chat.py and loop/chat_tools.json
const CHAT_READ = new Set(["status", "surprises", "replay", "why", "diff", "ruling"]);   // loop/chat.py READ

/** A chat command's line from its declaration and the model's arguments: "/" + name, the positionals in their order
 *  (quoted when they hold a space), then the flags ("/why speed --at 41"). */
export function chatLine(t: any, params: Record<string, unknown>): string {
	const props = Object.entries((t.parameters && t.parameters.properties) || {}) as [string, any][];
	const q = (v: unknown) => { const x = String(v); return /[\s"']/.test(x) ? JSON.stringify(x) : x; };
	const pos = props.filter(([, d]) => d.positional !== undefined).sort((a, b) => a[1].positional - b[1].positional);
	const words = [`/${t.name}`];
	for (const [k] of pos) if (params[k] !== undefined && params[k] !== null && params[k] !== "") words.push(q(params[k]));
	for (const [k, d] of props) if (d.flag && params[k] !== undefined && params[k] !== null && params[k] !== "") words.push(d.flag, q(params[k]));
	return words.join(" ");
}
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

// every child in the 6G scope (the subject's rule), as propose.sh caps itself: systemd-run when it can start a
// user scope here (probed once; a host or CI runner without a user session runs the child plain)
const CAP = ["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=6G", "-p", "MemorySwapMax=0"];
let capped: boolean | undefined;
function cap6g(): string[] {
	if (capped === undefined) capped = spawnSync(CAP[0], [...CAP.slice(1), "true"], { stdio: "ignore", timeout: 10000 }).status === 0;
	return capped ? CAP : [];
}

/** Run a command in DIR, asynchronously (the judge takes minutes), in the 6G scope: its code, stdout, stderr. */
function run(cmd: string, args: string[], cwd: string, env: NodeJS.ProcessEnv = process.env): Promise<{ code: number; out: string; err: string }> {
	const [c, ...a] = [...cap6g(), cmd, ...args];
	return new Promise((done) => {
		execFile(c, a, { cwd, env, maxBuffer: 1 << 26, encoding: "utf8" }, (e: any, out, err) =>
			done({ code: e ? (typeof e.code === "number" ? e.code : 127) : 0, out: String(out ?? ""), err: String(err ?? e?.message ?? "") }),
		);
	});
}

const text = (s: string, details: any = {}, n = 4000) => ({ content: [{ type: "text" as const, text: cap(s, n) }], details });

/** The units a member's program includes, the program first, transitively, each resolved by the compiler's own rule
 *  (metispy's `python -m metis.catalog units NAME`: own = in the domain dir, shared = the family's under METIS_HOME,
 *  std = iface/). An include found nowhere throws with the catalog's words. */
export function units(name: string, root: string): { path: string; kind: "own" | "shared" | "std" }[] {
	const out = catalog.cli(["units", name], undefined, root);
	if (out && typeof out === "object" && "error" in out) throw new Error(String(out.error));
	return Object.entries(out as Record<string, "own" | "shared" | "std">).map(([path, kind]) => ({ path, kind }));
}

const RULE_HEAD = /^\s*([a-z][a-z0-9_]*)\s*\[([a-z0-9_,\s]+)\]\s*:/;
const DECL = /^\s*(catalog|extends|include|layers|stages|types|type|pred|bwd|weight|namespace)\b/;
const nocomment = (l: string) => l.replace(/\s+%(?!%).*$/, "").trimEnd();

/** The file a generated unit is made from ("% DERIVED from SRC by …" on its first line), absolute; else null. */
export function derivedFrom(path: string, text: string): string | null {
	const m = text.match(/^% DERIVED from (\S+)/);
	return m ? resolve(dirname(path), m[1]) : null;
}

const SKILLS = resolve(HERE, "..", "skills");           // pi.sh's --skill directories (loop-prompt, PROMPT.md §2)

/** The person's key file (loop.sh's METIS_OPENROUTER_ENV, default ~/.config/metis/openrouter.env), as a real path. */
function keyFile(): string {
	const k = process.env.METIS_OPENROUTER_ENV || join(homedir(), ".config", "metis", "openrouter.env");
	try {
		return realpathSync(k);
	} catch {
		return resolve(k);
	}
}

/** pi's built-in read (pi.sh --tools +read, for the skills' SKILL.md and their files) is kept to the skills and the
 *  workspace. PATH is resolved as the read tool resolves it (pi's resolveReadPath against CWD, pi's cwd), then to its
 *  real path (a symlink is judged by what it points at): refused when it is the key file (whatever its name), any
 *  `.env`, or outside both the skills and the workspace ROOT (nina's review of step 2). → the refusal, or null. */
export function readRefusal(path: string, root: string, cwd: string = process.cwd(), skills = SKILLS, key = keyFile()): string | null {
	const raw = String(path || "");
	let real = resolveReadPath(raw, cwd);
	try {
		real = realpathSync(real);
	} catch {
		// a path that does not exist: judged as resolved (read says it is missing)
	}
	const realOf = (d: string) => { try { return realpathSync(d); } catch { return resolve(d); } };
	const under = (d: string) => { const rd = realOf(d); return real === rd || real.startsWith(rd + "/"); };
	if (real === realOf(key)) return `read ${raw}: the key file is never read here`;
	if (/(^|\/)[^/]*\.env$/.test(real)) return `read ${raw}: an .env file is never read here (a key lives in it)`;
	if (under(skills) || under(root)) return null;
	return `read ${raw}: outside the skills (${skills}) and the workspace (${root}); this loop reads only those`;
}

/** The rule names of a unit's text (the rule heads, in order). */
export function ruleNames(text: string): string[] {
	return text.split("\n").map((l) => l.match(RULE_HEAD)?.[1]).filter((x): x is string => !!x);
}

/** A unit's signature (loop-prompt, PROMPT.md §2): its declarations (catalog, layers, stages, types, pred, bwd,
 *  weight, include … one line each, the comment dropped; a type over several lines as `type T {…} (N names)`) and
 *  every rule's name and layer under its stage, with its %% line; no rule bodies (rule_text gives a rule whole).
 *  `generated`: the names make writes into a generated unit that its source has no rule for, marked "(generated)". */
export function signature(text: string, generated: Set<string> = new Set()): string {
	const out: string[] = [];
	const lines = text.split("\n");
	for (let i = 0; i < lines.length; i++) {
		const l = lines[i];
		const st = l.match(/^\s*stage\s+([a-z0-9_]+)\s*\{/);
		if (st) { out.push(`stage ${st[1]}:`); continue; }
		const r = l.match(RULE_HEAD);
		if (r) {
			const doc = i > 0 && /^\s*%%/.test(lines[i - 1]) ? "  " + lines[i - 1].trim() : "";
			out.push(`  ${r[1]} [${r[2].replace(/\s+/g, "")}]${generated.has(r[1]) ? " (generated)" : ""}${doc}`);
			continue;
		}
		if (!DECL.test(l)) continue;
		const d = nocomment(l).trim();
		if (d.includes("{") && !d.includes("}")) {          // nina: a type over several lines, never printed open
			let body = d.slice(d.indexOf("{") + 1);
			let j = i;
			while (!body.includes("}") && j < lines.length - 1) body += " " + nocomment(lines[++j]);
			const names = body.split("}")[0].split(/[\s,]+/).filter(Boolean);
			out.push(`${d.slice(0, d.indexOf("{")).trim()} {…} (${names.length} names)`);
			i = j;
			continue;
		}
		out.push(d);
	}
	return out.join("\n");
}

/** One rule whole at line i of `lines` (its %% line, its text to the line ending in "."): [doc?, …lines]. */
function ruleAt(lines: string[], i: number): string[] {
	let j = i;
	while (j < lines.length - 1 && !nocomment(lines[j]).endsWith(".")) j++;
	const doc = i > 0 && /^\s*%%/.test(lines[i - 1]) ? [lines[i - 1].trim()] : [];
	return [...doc, ...lines.slice(i, j + 1).map((x) => x.trim())];
}

/** The rules named, whole, from the files given: each as "path:line" then its text; a name found nowhere is listed
 *  as such. A rule ends at the first line (comment dropped) ending in ".". A generated unit (`src` given: its
 *  % DERIVED source) gives the SOURCE's rule at the source's path:line, the text an edit takes, with the line it runs
 *  as in the generated file; a rule only make writes says so (nina's review of step 1). */
export function ruleText(files: { path: string; text: string; src?: { path: string; text: string } }[], names: string[]): string {
	const want = new Set(names.map((n) => String(n).split("[")[0].trim()).filter(Boolean));
	const found = new Set<string>();
	const out: string[] = [];
	for (const f of files) {
		const lines = f.text.split("\n");
		const sl = f.src ? f.src.text.split("\n") : [];
		for (let i = 0; i < lines.length; i++) {
			const m = lines[i].match(RULE_HEAD);
			if (!m || !want.has(m[1])) continue;
			found.add(m[1]);
			if (!f.src) {
				out.push(`${f.path}:${i + 1}`, ...ruleAt(lines, i), "");
				continue;
			}
			const k = sl.findIndex((x) => x.match(RULE_HEAD)?.[1] === m[1]);
			if (k < 0) {
				out.push(`${f.path}:${i + 1} (generated by make, no rule in ${f.src.path}: amend the generator's input, not this rule)`, ...ruleAt(lines, i), "");
				continue;
			}
			out.push(`${f.src.path}:${k + 1}`, ...ruleAt(sl, k), `(runs as generated in ${f.path}:${i + 1}: ${ruleAt(lines, i).filter((x) => !x.startsWith("%%")).join(" ")})`, "");
		}
	}
	const missing = [...want].filter((n) => !found.has(n));
	if (missing.length) out.push(`not a rule of these units: ${missing.join(", ")}`);
	return out.join("\n").trim();
}

/** Whose a shared unit is, from its path (nina's review of step 1): under $METIS_HOME the family's, inside the
 *  bundle's directory the bundle's, else shared. */
export function whoseUnit(path: string, home: string | undefined, bundleDir: string | null): string {
	const under = (p: string, d: string) => { const rp = resolve(p), rd = resolve(d); return rp === rd || rp.startsWith(rd + "/"); };
	if (home && under(path, home)) return "the family's, under METIS_HOME";
	if (bundleDir && under(path, bundleDir)) return "the bundle's";
	return "shared";
}

const json = (o: unknown) => JSON.stringify(o, null, 1);

/** The candidate's firings on the trace, from the judge's fired-diff rows: how many of its rules' firings (by base name)
 * the candidate rows carry, in how many rows, from which tick to which. */
export function firings(e: any): { count: number; rows: number; of_rows: number; first: number | null; last: number | null } {
	const mine = new Set(((e?.rules ?? []) as string[]).map((r) => String(r).split("[")[0]));
	const rows = (e?.rows ?? []) as any[];
	let count = 0, hit = 0, first: number | null = null, last: number | null = null;
	for (const row of rows) {
		const n = ((row?.fired?.candidate ?? []) as string[]).filter((x) => mine.has(String(x).split("[")[0])).length;
		if (!n) continue;
		count += n;
		hit++;
		if (first === null) first = row.k;
		last = row.k;
	}
	return { count, rows: hit, of_rows: rows.length, first, last };
}

export default function (host: ExtensionAPI) {
	// the tool set by mode (lib/toolset.ts): none in the standalone catalog loop (--seed); the lock is taken either way
	const set = toolset();
	const pi = scoped(host, () => set !== "seed");
	const root = () => resolve(writeRoot());
	let locked = false;
	const held = new Set<string>();                    // the surprises this session took (surprise_next)
	let lastMember = "";                              // the member of the surprise taken last (rule_text's default)
	// the writes (take, rule, build) are the lock holder's only: a loop that did not get the lock reads and no more
	const mustHold = (r: string) => {
		if (locked) return;
		const h = ws.loops(r).pi;
		throw new Error(h ? `this pi loop does not hold the workspace: pid ${h.pid} (mode ${h.mode}, started ${h.started}) does; one pi loop per workspace` : "this pi loop does not hold the workspace's lock (session_start took none)");
	};

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
			"Take the oldest open surprise (this loop's, until its ruling) and get what it needs: the record (member, trace, tick k or window, the atoms or reading, the person's words), the member's program, each unit it includes as its signature (declarations, rule names with their %% lines; rule_text gives a rule whole), and the rulings of earlier surprises on the same member. None open: says so. Then draft a case (trace_case) and a pack, and judge it with pack_propose.",
		parameters: Type.Object({}),
		async execute() {
			const r = root();
			mustHold(r);
			const open = ws.surprises("open", r);
			if (!open.length) return text("no open surprise", { surprise: null });
			const s = open[0];
			ws.take_surprise(s.id, process.pid, "pi", r); // the face journals the take
			held.add(s.id);                                // released at the session's end unless ruled (F7)
			let program: string | null = null;
			let source = "";
			try {
				const g = catalog.get(s.member, r);
				program = g?.program ? resolve(r, g.program) : null;
				if (program && existsSync(program)) source = readFileSync(program, "utf8");
			} catch {
				// a member the catalog does not list: the record alone
			}
			// the units it includes, resolved as the compiler does: a family's under METIS_HOME are the member's rules too
			let inc: ReturnType<typeof units> = [];
			let incErr = "";
			if (program && source) {
				try {
					inc = units(s.member, r).filter((u) => resolve(u.path) !== resolve(program!));
				} catch (e: any) {
					incErr = e.message;
				}
			}
			const read = (p: string) => (existsSync(p) ? readFileSync(p, "utf8") : "");
			lastMember = s.member;
			const earlier = ws.rulings(r).filter((x: any) => x.id !== s.id && ws.surprise(x.id, r)?.member === s.member);
			let bdir: string | null = null;
			try {
				const b = ws.bundle(undefined, r);
				bdir = b?.composition ? dirname(resolve(r, b.composition)) : null;
			} catch {
				// no bundle: no unit is the bundle's
			}
			const unitView = (u: { path: string; kind: string }) => {
				if (u.kind === "std") return ["", `## included (the language's standard unit): ${u.path}`];
				const t = read(u.path);
				const src = derivedFrom(u.path, t);
				const whose = u.kind === "shared" ? whoseUnit(u.path, process.env.METIS_HOME, bdir) : "the member's own";
				const mine = src ? new Set(ruleNames(read(src))) : null;
				const gen = mine ? new Set(ruleNames(t).filter((n) => !mine.has(n))) : new Set<string>();
				return ["", `## included (${whose}): ${u.path}`,
					src ? `(generated from ${src} by make: a pack that amends it gives unit=${src}, never this file. rule_text reads a rule there; (generated) marks a rule only make writes)`
						: "(a pack that amends it gives unit=<this path>)",
					signature(t, gen)];
			};
			const body = [
				`## surprise ${s.id} (taken)`,
				json(s),
				"",
				`## the member's program${program ? ` (${program})` : ""}`,
				source || "(not found in the catalog)",
				...(inc.some((u) => u.kind !== "std") ? ["", "(each included unit as its signature: declarations, and every rule's name with its %% line; rule_text gives rules whole)"] : []),
				...inc.flatMap(unitView),
				...(incErr ? ["", `## its includes could not be resolved: ${incErr}`] : []),
				"",
				"## earlier rulings on this member",
				earlier.length ? json(earlier.map((x: any) => ({ id: x.id, verdict: x.verdict, md: x.md }))) : "(none)",
			].join("\n");
			return text(body, { surprise: s, program, units: inc, earlier: earlier.map((x: any) => x.id) }, 40000);
		},
	});

	pi.registerTool({
		name: "rule_text",
		label: "rules, whole",
		description:
			"The named rules whole (their %% line, every premise and effect), each with its path:line, from the member's program and the units it includes, as the compiler resolves them. Default member: the one of the surprise taken last. Read before a pack that amends a rule.",
		parameters: Type.Object({
			names: Type.Array(Type.String(), { description: "rule names, as the signature or a blame row gives them" }),
			member: Type.Optional(Type.String({ description: "the member (default: the surprise taken last)" })),
		}),
		async execute(_id, p: any) {
			const r = root();
			const m = String(p.member || lastMember || "");
			if (!m) throw new Error("rule_text: name the member (no surprise taken yet)");
			const read = (x: string) => (existsSync(x) ? readFileSync(x, "utf8") : "");
			const files = units(m, r).filter((u) => u.kind !== "std").map((u) => {
				const t = read(u.path);
				const src = derivedFrom(u.path, t);
				return { path: u.path, text: t, ...(src && existsSync(src) ? { src: { path: src, text: read(src) } } : {}) };
			});
			return text(ruleText(files, (p.names || []) as string[]) || "(no rules named)", { member: m }, 8000);
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

	// ---- the chat's read-only commands, as declared (loop/chat_tools.json; loop-chat step 3, CHAT.md §2) ------
	// The person may ask in words for what the chat's /status, /replay, /why … answer: these run the same answer
	// (python -m loop.chat --root DIR "/replay …", 0 USD), so the person need not know the slash.
	let chatDecl: any[] = [];
	try {
		chatDecl = JSON.parse(readFileSync(join(LOOP_REPO, "loop", "chat_tools.json"), "utf8")).tools;
	} catch (e: any) {
		console.error(`metis-workspace: no chat tools (${e.message})`);
	}
	for (const t of chatDecl.filter((x: any) => CHAT_READ.has(x.name))) {
		pi.registerTool({
			name: `chat_${t.name}`,
			label: `/${t.name}`,
			description: `the chat's /${t.name}, answered by the backend at 0 USD: ${t.description}. Run it when the person asks for it in words; report its rows as they print.`,
			parameters: Type.Unsafe(schema(t.parameters)),
			async execute(_id, params: any) {
				const r = root();
				const line = chatLine(t, params || {});
				const env = { ...process.env, PYTHONPATH: [LOOP_REPO, process.env.PYTHONPATH].filter(Boolean).join(":") };
				const res = await run(process.env.METIS_LOOP_SDK_PY || "python3", ["-m", "loop.chat", "--root", r, line], r, env);
				return text(`${res.code === 0 ? "" : `exit ${res.code}\n`}${res.out}${res.err ? `\n${res.err}` : ""}`.trim() || "(no output)", { line, code: res.code });
			},
		});
	}

	// ---- the pack verb: the judgement, as the surprise's ruling -------------------------------------
	pi.registerTool({
		name: "pack_propose",
		label: "judge a pack",
		description:
			"Judge a candidate pack for a taken surprise (propose.sh: the gate cascade, every member's goldens, the cases, the fired diff on the trace's replay, the lint rows; no world). The verdict is the gate's, mechanically; the ruling (rulings/<id>.md) and the pack (packs/<id>.llp) are written as the surprise's, which makes it ruled. Nothing is applied: the person applies an accepted pack through catalog_edit. Takes minutes.",
		parameters: Type.Object({
			id: Type.String({ description: "the surprise's id (surprise_next)" }),
			pack: Type.String({ description: "the pack's text: rules in `stage S { }`, `pred` lines, `drop NAME`; or a whole program" }),
			cases: Type.Optional(Type.Array(Type.String(), { description: "case files (trace_case --into) the pack must pass" })),
			unit: Type.Optional(Type.String({ description: "the file the pack amends (default: the member's program)" })),
			brain: Type.Optional(Type.String({ description: "who writes the ruling's words: script:FILE (0 USD) or openrouter/<id> (needs budget); none: the evidence alone" })),
			budget: Type.Optional(Type.Number({ description: "a paid brain's cap, USD" })),
		}),
		async execute(_id, p) {
			const r = root();
			mustHold(r);
			const s = ws.surprise(p.id, r);
			if (s.status === "ruled") throw new Error(`surprise ${p.id} is ruled already`);
			if (s.status !== "taken") throw new Error(`surprise ${p.id} is not taken: surprise_next first`);
			if (!s.trace) throw new Error(`surprise ${p.id} has no trace: nothing to replay (the ruling would have no fired diff)`);
			if (p.brain?.startsWith("openrouter/") && !(p.budget && p.budget > 0)) throw new Error("a paid brain needs a budget (USD)");
			const b = ws.bundle(undefined, r);
			// the service config: the surprise's (the run it was dropped from), else the bundle's service.yaml; never the
			// model's guess (the alf drive's L3: a guessed config crashed the judge, then a ruling "refused: 'v3'")
			const config = (s as any).config ?? (b as any)?.config;
			if (!config) throw new Error(`surprise ${p.id} cannot be judged here: no service config (the surprise names none, ` +
				`and the bundle has no service.yaml beside its composition.yaml). The judge replays the bundle on its service ` +
				`config: say so to the person; do not write one.`);
			const tmp = mkdtempSync(join(tmpdir(), "pack-propose-"));
			let spent = 0;
			try {
				const pack = join(tmp, "pack.llp");
				writeFileSync(pack, p.pack.endsWith("\n") ? p.pack : p.pack + "\n");
				const argv = ["--pack", pack, "--member", s.member, "--trace", tracePath(s.trace, r), "--root", r, "--config", resolve(r, config), "--run", join(tmp, "run")];
				if (b) argv.push("--composition", dirname(b.composition));
				if (p.unit) {
					const u = resolve(r, String(p.unit));
					const gen = existsSync(u) ? derivedFrom(u, readFileSync(u, "utf8")) : null;
					if (gen) throw new Error(`unit=${p.unit} is generated from ${gen} by make: give unit=${gen}, never the generated file`);
					argv.push("--unit", p.unit);
				}
				for (const c of p.cases ?? []) argv.push("--case", resolve(r, c));
				if (p.brain) argv.push("--brain", p.brain);
				if (p.budget) argv.push("--budget", String(p.budget));
				ws.journal("pi", "judging", { surprise: p.id }, r);
				const res = await run(process.env.METIS_LOOP_PROPOSE || join(HERE, "..", "propose.sh"), argv, r);
				const md = join(tmp, "run", "ruling.md");
				const ev = join(tmp, "run", "evidence.json");
				if (!existsSync(md) || !existsSync(ev)) {
					const why = `propose.sh wrote no ruling (exit ${res.code}): ${(res.err || res.out).trim().slice(-1500)}`;
					release(p.id, `no ruling: exit ${res.code}`, r);
					throw new Error(`${why}\nsurprise ${p.id} is released: open again`);
				}
				const e = JSON.parse(readFileSync(ev, "utf8"));
				const doc = readFileSync(md, "utf8");
				spent = logSpend(join(tmp, "run"), p.id, r);
				if (e.verdict === "not judged") {
					// past the time budget: no verdict at all, so no ruling; the take releases itself (the architect's
					// ruling): the next loop, or this one with a longer budget, takes it again
					release(p.id, `not judged: ${(e.reasons ?? []).join("; ") || "the time budget ran out"}`, r);
					return text(`not judged (the time budget ran out): surprise ${p.id} is released, open again; judge it again with a longer budget\n\n${doc}`, { verdict: e.verdict, ruling: null, code: res.code, spent });
				}
				// beside the verdict, for the person (the brake_late lesson, step 4): when the candidate is first enabled and how
				// often its rules fire where the fired rows differ from the record
				const fields = { moved: e.moved ?? e.receipt?.moved ?? [], lint: e.lint ?? [], reads_absent: e.reads_absent ?? [], spent, member: s.member, trace: s.trace,
					first_enabled: e.first_enabled ?? null, open_loop_after: e.open_loop_after ?? null, inert: !!e.inert, firings: firings(e) };
				// the face journals the ruling
				const ruling = ws.rule(p.id, doc, String(e.verdict), { pack: readFileSync(pack, "utf8"), fields, who: "pi" }, r);
				return text(`${e.verdict}: ${ruling}\n\n${doc}`, { verdict: e.verdict, ruling, code: res.code, spent });
			} finally {
				logSpend(join(tmp, "run"), p.id, r); // a run that spent and then wrote no ruling still leaves its spend
				rmSync(tmp, { recursive: true, force: true });
			}
		},
	});

	// a take that ends without a ruling releases itself: surprises/<id>.taken removed, a not_judged row with the reason
	function release(id: string, reason: string, r: string) {
		held.delete(id);
		rmSync(ws.path("taken", { id }, r), { force: true });
		ws.journal("pi", "not_judged", { surprise: id, reason: reason.slice(0, 400) }, r);
	}

	// the brain's own per-call log (RUN/cost.jsonl: {ts, who, model, cost, usage_before}) into the workspace's, once
	const logged = new Set<string>();
	function logSpend(run: string, id: string, r: string): number {
		const f = join(run, "cost.jsonl");
		if (!existsSync(f)) return 0;
		let sum = 0;
		const rows: any[] = [];
		for (const l of readFileSync(f, "utf8").split("\n")) {
			if (!l.trim()) continue;
			try {
				rows.push(JSON.parse(l));
			} catch {
				rows.push({ unparsed: l.slice(0, 400) }); // kept, never thrown: a bad line must not hide the run's own error
			}
		}
		for (const x of rows) sum += Number(x.cost) || 0;
		if (!logged.has(f)) {
			logged.add(f);
			for (const x of rows) appendFileSync(ws.path("cost", {}, r), JSON.stringify({ ...x, surprise: id }) + "\n");
		}
		return sum;
	}

	// ---- the bundle ---------------------------------------------------------------------------------
	pi.registerTool({
		name: "bundle_build",
		label: "build the bundle",
		description: "Rebuild the workspace's bundle (`metisc build .` where its composition is) after an applied ruling: the image hash before and after, and metisc's account. The backend sees the new build and shows its sessions STALE.",
		parameters: Type.Object({}),
		async execute() {
			const r = root();
			mustHold(r);
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
	const unlockSession = () => {
		// the takes this session holds and did not rule are released (the architect's F7: after a stop the surprise
		// stayed TAKEN): .taken removed, a not_judged row; a ruled one has its ruling and is left as it is
		const r = root();
		for (const id of [...held]) {
			try {
				const s = ws.surprise(id, r);
				if (s && s.status === "taken" && s.taken && s.taken.pid === process.pid) release(id, "the pi loop ended without a ruling", r);
			} catch {
				// a surprise gone with the workspace: nothing to release
			}
			held.delete(id);
		}
		if (!locked) return;
		try {
			ws.unlock("pi", process.pid, root());
		} catch {
			// the workspace gone with the session: nothing to release
		}
		locked = false;
	};
	pi.on("session_shutdown", unlockSession);

	// ---- the budget: the session's spend on a paid model (loop.sh --budget / METIS_LOOP_BUDGET) -------
	// The cost is observed here (pi's usage on each assistant message, the provider's prices): each paid
	// message is a cost.jsonl row (who: pi); the per-request cap stays in agent/models.json and the SDK's
	// command face. Past the budget the session REFUSES (the architect's rule): no further model turn (the
	// person's input is handled here, a tool call is blocked and ends the batch, the running turn is
	// aborted), a `budget` journal row with the spend, and the lock released. pi is not killed.
	const budget = Number(process.env.METIS_LOOP_BUDGET || 0) || 0;
	let spent = 0;
	let requests = 0;
	let over = false;
	const refusal = () => `the session's budget is spent: ${spent.toFixed(4)} of ${budget} USD (loop.sh --budget); no further model turns`;
	// one log, one cap: a paid row of this session, pi's own or the kernel's formalize (its SDK face logs each call to
	// $METIS_LOOP_RECORDS/formalize-calls.jsonl; the new rows are picked up here as who: formalize)
	const charge = (r: string, row: Record<string, unknown>, ctx: any) => {
		const cost = Number(row.cost) || 0;
		if (cost <= 0) return;
		let before = 0;
		try {
			before = ws.cost(r).total;
		} catch {
			// no workspace state yet: the first row starts it
		}
		spent += cost;
		appendFileSync(ws.path("cost", {}, r), JSON.stringify({ ts: new Date().toISOString(), ...row, cost, usage_before: before, session_spent: spent }) + "\n");
		if (budget > 0 && spent >= budget && !over) {
			over = true;
			ws.journal("pi", "budget", { spent, budget }, r);
			ctx?.ui?.notify?.(`metis-workspace: ${refusal()}`, "error");
			unlockSession();
			ctx?.abort?.();
		}
	};
	let formalizeSeen = -1; // lines of formalize-calls.jsonl already charged (-1: not yet read: what was there is not this session's)
	const formalizeLog = () => (process.env.METIS_LOOP_RECORDS ? join(process.env.METIS_LOOP_RECORDS, "formalize-calls.jsonl") : null);
	const syncFormalize = (ctx: any) => {
		const f = formalizeLog();
		if (!f) return;
		const lines = existsSync(f) ? readFileSync(f, "utf8").split("\n").filter((l) => l.trim()) : [];
		if (formalizeSeen < 0) {
			formalizeSeen = lines.length;
			return;
		}
		const fresh = lines.slice(formalizeSeen);
		formalizeSeen = lines.length;
		const r = root();
		for (const l of fresh) {
			let x: any = {};
			try {
				x = JSON.parse(l);
			} catch {
				continue; // a bad line is the face's to explain, never a reason to lose the session
			}
			charge(r, { who: "formalize", model: x.model ?? null, cost: x.cost }, ctx);
		}
	};
	pi.on("session_start", async () => syncFormalize(null)); // the log's lines before this session are not its spend
	pi.on("message_end", async (e: any, ctx: any) => {
		const m = e.message;
		if (m?.role === "assistant") requests++;
		syncFormalize(ctx);
		const cost = Number(m?.role === "assistant" ? m?.usage?.cost?.total : 0) || 0;
		if (cost > 0) charge(root(), { who: "pi", model: m.model ?? process.env.MODEL ?? null, cost }, ctx);
	});
	pi.on("input", async (_e: any, ctx: any) => {
		if (!over) return { action: "continue" };
		ctx?.ui?.notify?.(`metis-workspace: ${refusal()}`, "error");
		return { action: "handled" };
	});
	let calls = 0;
	pi.on("tool_call", async (e: any, ctx: any) => {
		if (over) return { block: true, reason: refusal(), terminate: true };
		if (e?.toolName === "read") {
			const no = readRefusal(String(e?.input?.path ?? ""), root(), ctx?.cwd || process.cwd());
			if (no) return { block: true, reason: no };
		}
		calls++;
		return undefined;
	});
	// past half the budget every tool reply carries the spend, so wandering has a price the model can see
	pi.on("tool_result", async (e: any, ctx: any) => {
		syncFormalize(ctx); // a repl_formalize just spent: charged before the reply says the spend
		if (!(budget > 0) || spent < budget / 2) return undefined;
		const line = `[budget: ${spent.toFixed(4)} of ${budget} USD spent; ${calls} tool calls, ${requests} model requests in this session. Finish the surprise, or stop.]`;
		return { content: [...(e.content ?? []), { type: "text", text: line }] };
	});
}
