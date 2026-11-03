// metis_loop_sdk/ts/workspace.ts — the workspace's face for node (loop-workspace s-5b4be5fa step 1,
// docs/WORKSPACE.md §2): metispy's metis.catalog.workspace, at parity with it, for a TypeScript consumer
// (the pi loop's metis-workspace.ts, the console's widgets later). Like catalog.ts it has no workspace code
// of its own: each function is one call of `python -m metis.catalog.workspace … --json`, and the .metis/
// layout lives once, in the py LAYOUT table this face reads through layout(). The names are py's, one for
// one (tests/ts/workspace.test.ts holds them to it). Node built-ins only, erasable TypeScript only.
//
//   import * as ws from ".../metis_loop_sdk/ts/workspace.ts";   // `python -m metis_loop_sdk.web ts`: where
//   ws.bundle()                         // {name, composition, members, image, golden, config, build, stale, why} | null
//   ws.surprises("open")                // the open surprises, oldest first
//   const id = ws.drop_surprise({ member: "responder", trace: "traces/s1", k: 41, words: "…", atoms: [...] })
//   ws.take_surprise(id)                // this process takes it (its pid in surprises/<id>.taken)
//   ws.rule(id, documentText, "accepted", { pack: packText, fields: { moved: [], spent: 0 } })
//   ws.lock("pi", { mode: "rpc", model, cwd })   // one pi loop per workspace: a second throws the holder's line
//   ws.events(since)                    // the journal's rows from row SINCE on
//   ws.tool_argv("trace_count", { trace, atom })  // a declared trace verb's command line
//
// The python: $METIS_LOOP_SDK_PY (a python with the SDK installed), else python3. The workspace: each
// call's `r`, else the CLI's own rule ($METIS_CATALOG, else the process's cwd). The CLI's refusals
// ({"error"}, exit 1) throw as WorkspaceError.
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

export type Who = "backend" | "pi" | "judge" | "world";
export type Status = "open" | "taken" | "ruled";
export type LockKind = "pi" | "backend";
/** The .metis/ layout (metis.catalog.workspace LAYOUT): each path relative to .metis/, {id}/{run}/{kind} to fill. */
export type Layout = {
	format: string;
	state: string;
	id: string;
	who: Who[];
	locks: LockKind[];
	status: Status[];
	paths: Record<string, { path: string; kind: "dir" | "json" | "jsonl" | "text"; writer: string; what: string }>;
};
export type Bundle = {
	name: string;
	composition: string;
	members: string[];
	image: string | null;
	golden: string | null;
	/** the service config a run of the bundle takes (propose.sh --config), absolute: composition.yaml's
	 *  `service:`, else service.yaml beside it, else null */
	config: string | null;
	build: string | null;
	stale: boolean;
	why: string | null;
};
/** A surprise as dropped: member and reading or atoms; trace ("traces/<run>"), k, k0, window, words when there are. */
export type SurpriseIn = {
	member: string;
	reading?: unknown;
	atoms?: string[];
	trace?: string;
	k?: number;
	k0?: number;
	window?: [number, number];
	words?: string;
	who?: Who;
	[more: string]: unknown;
};
/** status: ruled (its ruling exists), taken (a live pid's .taken: `taken`), else open; an open one over a dead
 *  pid's .taken carries it as `stale_take`, and the next take_surprise re-takes it (journal `retake`). */
export type Surprise = SurpriseIn & {
	id: string;
	ts: string;
	who: Who;
	status: Status;
	taken?: { pid: number; ts: string };
	stale_take?: { pid: number; ts: string };
	ruling?: any;
};
export type Lock = { pid: number; started: string; alive?: boolean; [field: string]: unknown };
export type Row = { ts: string; who: Who; kind: string; [ptr: string]: unknown };
export type Cost = { total: number; calls: number; by_model: Record<string, number>; by_who: Record<string, number> };
export type Tool = { name: string; module: string; verb: string | null; description: string; parameters: any };

/** The workspace CLI's own refusal ({"error"}), or the CLI failing to run. */
export class WorkspaceError extends Error {
	verb: string;
	constructor(verb: string, message: string) {
		super(`workspace ${verb}: ${message}`);
		this.name = "WorkspaceError";
		this.verb = verb;
	}
}

/** The CLI itself: `cli(["bundle"])`, its JSON answer. `input` is stdin (for `-`); `r` the workspace (--root). */
export function cli(args: string[], input?: string, r?: string): any {
	const py = process.env.METIS_LOOP_SDK_PY || "python3";
	try {
		return JSON.parse(
			execFileSync(py, ["-m", "metis.catalog.workspace", ...(r ? ["--root", r] : []), ...args, "--json"], {
				input: input ?? "",
				encoding: "utf8",
				maxBuffer: 1 << 26,
				stdio: ["pipe", "pipe", "pipe"],
			}),
		);
	} catch (e: any) {
		let err: string | undefined;
		try {
			err = JSON.parse(String(e.stdout ?? "")).error;
		} catch {
			// not the CLI's answer: the process itself failed
		}
		if (err) throw new WorkspaceError(args[0], err);
		throw new WorkspaceError(args[0], `${py} -m metis.catalog.workspace: ${String(e.stderr || e.message).trim().slice(-500)}`);
	}
}

let LAYOUT: Layout | undefined;

/** The .metis/ layout, the one table (read once a process from the py face). */
export function layout(): Layout {
	return (LAYOUT ??= cli(["layout"]));
}

/** The workspace's root and its .metis/ (made: whether a write has made it yet). */
export function root(r?: string): { root: string; state: string; made: boolean } {
	return cli(["root"], undefined, r);
}

/** The layout's path NAME under the workspace's .metis/, {id}/{run}/{kind} filled from FILL (py's Workspace.path). */
export function path(name: string, fill: Record<string, string> = {}, r?: string): string {
	const row = layout().paths[name];
	if (!row) throw new WorkspaceError("path", `no layout path ${JSON.stringify(name)}`);
	const rel = row.path.replace(/\{(\w+)\}/g, (_, k) => {
		if (fill[k] === undefined) throw new WorkspaceError("path", `${name}: {${k}} not given`);
		return fill[k];
	});
	return join(root(r).state, rel).replace(/\/$/, "");      // a dir's path as py's Path prints it
}

/** The bundle (NAME: that package's composition), or null when the workspace has none. */
export function bundle(name?: string, r?: string): Bundle | null {
	return cli(["bundle", ...(name ? [name] : [])], undefined, r);
}

/** The text a brain is given first; PATTERNS: the patterns catalog's path (else $METIS_PATTERNS). */
export function context(patterns?: string, r?: string): string {
	return cli(["context", ...(patterns ? ["--patterns", patterns] : [])], undefined, r).context;
}

export function traces(r?: string): { run: string; path: string; segments: number }[] {
	return cli(["traces"], undefined, r);
}

/** One trace: its k range, the checkpoints' ticks, the first segment's header. */
export function trace(run: string, r?: string): { run: string; path: string; k0: number; k1: number; checkpoints: number[]; header: any } {
	return cli(["trace", run], undefined, r);
}

export function surprises(status?: Status, r?: string): Surprise[] {
	return cli(["surprises", ...(status ? ["--status", status] : [])], undefined, r);
}

export function surprise(id: string, r?: string): Surprise {
	return cli(["surprise", id], undefined, r);
}

/** Drop a surprise (the backend's write by default): → its id. */
export function drop_surprise(rec: SurpriseIn, who: Who = "backend", r?: string): string {
	return cli(["drop", "-", "--who", rec.who ?? who], JSON.stringify(rec), r).id;
}

/** Take a surprise: PID (default this process) in surprises/<id>.taken; refused while a live pid holds it, a dead
 *  pid's take re-taken (journal `retake`, naming the dead pid). */
export function take_surprise(id: string, pid: number = process.pid, who: Who = "pi", r?: string): string {
	return cli(["take", id, "--pid", String(pid), "--who", who], undefined, r).id;
}

/** The ruling of ID: the document's text, the verdict, the pack's text and the json's other fields
 *  (moved, lint, reads_absent, spent …). → the ruling json's path relative to .metis/. */
export function rule(
	id: string,
	ruling: string,
	verdict: string,
	o: { pack?: string; fields?: Record<string, unknown>; who?: Who } = {},
	r?: string,
): string {
	const args = ["rule", id, "--ruling", "-", "--verdict", verdict, "--who", o.who ?? "pi"];
	if (o.fields) args.push("--fields", JSON.stringify(o.fields));
	if (o.pack === undefined) return cli(args, ruling, r).ruling;
	// two texts: the pack goes through a file the CLI reads
	const tmp = mkdtempSync(join(tmpdir(), "workspace-ts-"));
	try {
		const f = join(tmp, "pack.llp");
		writeFileSync(f, o.pack);
		return cli([...args, "--pack", f], ruling, r).ruling;
	} finally {
		rmSync(tmp, { recursive: true, force: true });
	}
}

export function rulings(r?: string): any[] {
	return cli(["rulings"], undefined, r);
}

/** Append one row {ts, who, kind, ...PTRS} to the journal (pointers, never bodies). → the row. */
export function journal(who: Who, kind: string, ptrs: Record<string, unknown> = {}, r?: string): Row {
	return cli(["journal", "--who", who, "--kind", kind, "--fields", JSON.stringify(ptrs)], undefined, r);
}

/** The journal's rows from row SINCE on (the caller keeps the count it has read). */
export function events(since = 0, r?: string): Row[] {
	return cli(["events", "--since", String(since)], undefined, r);
}

export function cost(r?: string): Cost {
	return cli(["cost"], undefined, r);
}

/** {pi, backend}: each lock or null; alive false when its pid is gone (stale: the next lock takes it over). */
export function loops(r?: string): { pi: Lock | null; backend: Lock | null } {
	return cli(["loops"], undefined, r);
}

/** Take KIND's lock for PID (default this process) with FIELDS (pi: mode, cwd, model, socket; backend: port);
 *  throws the holder's line while a live pid holds it. */
export function lock(kind: LockKind, fields: Record<string, unknown> = {}, pid: number = process.pid, r?: string): Lock {
	return cli(["lock", kind, "--pid", String(pid), "--fields", JSON.stringify(fields)], undefined, r);
}

/** Release KIND's lock (its holder PID, default this process; anyone once the holder is gone). */
export function unlock(kind: LockKind, pid: number = process.pid, r?: string): boolean {
	return cli(["unlock", kind, "--pid", String(pid)], undefined, r).released;
}

/** The trace verbs and lint as declared tools (metispy's metis/trace_tools.json). */
export function tools(): { format: string; tools: Tool[] } {
	return cli(["tools"]);
}

/** A declared tool's command line ([python, -m, module, verb?, …]); an undeclared or missing argument throws. */
export function tool_argv(name: string, args: Record<string, unknown> = {}): string[] {
	return cli(["argv", name, "--args", JSON.stringify(args)]).argv;
}
