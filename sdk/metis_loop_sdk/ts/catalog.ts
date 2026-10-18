// metis_loop_sdk/ts/catalog.ts — the loop SDK's catalog for node (fiction-port s-e3d0942d
// step 1): the same catalog as metis_loop_sdk.catalog, at parity with it, for a TypeScript
// consumer (metis-agentic-loop's pi extensions). It has no catalog code of its own: each
// function is one call of the py SDK's CLI, `python -m metis_loop_sdk.catalog … --json`, so
// both faces are one code and one tag. Node built-ins only, erasable TypeScript only
// (node --experimental-strip-types and pi's loader both run it as it is).
//
//   import * as catalog from ".../metis_loop_sdk/ts/catalog.ts";   // `python -m metis_loop_sdk.catalog ts`: where
//   catalog.get("dog")                       // the domain: manifest, program, serves, host, has, fingerprint
//   catalog.plan("lamp", { program })        // what apply would write: [{path, new, diff}]
//   catalog.apply("lamp", { program, manifest, display, line })
//   catalog.edit("lamp", { path: "lamp.llp", old_string, new_string })   // one exact edit of a file on disk
//   catalog.take("lamp", from, { readmeFromRun: run }, into)
//   catalog.readme("lamp", { from, run, summary, title })   // the README of a loop run's domain
//
// The python: $METIS_LOOP_SDK_PY (a python with the SDK installed), else python3. The
// root: each call's `root`, else the CLI's own rule ($METIS_CATALOG, else the sibling
// checkout). The SDK's refusals ({"error"}, exit 1) throw as CatalogError.
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

/** One file a write would change: its path (relative to the root), new or not, its unified diff
 *  against the file on disk, its text; since_diff: the diff from the earlier proposal `since` gave. */
export type Planned = { path: string; new: boolean; diff: string; text: string; since_diff?: string };
/** A plan's options: since {path: text}, the earlier (refused) proposals to diff each file from. */
export type PlanOpts = { since?: Record<string, string> };
/** What a write wrote: the paths, the diff, the domain's fingerprint after it (null: no manifest). */
export type Applied = { written: string[]; diff: string; fingerprint: string | null };
/** A write's texts (apply, plan): the program, extensions by name, intent.yaml (or
 *  intentsSkeleton: one drafted from the program), domain.yaml's keys to set (or its whole
 *  text), the README, the host's Python (as the file the manifest's host names, beside
 *  domain.yaml), intent/<name>-corpus.tsv, and the manifest's display and line (one line
 *  each) — py's plan/apply keywords, one for one. */
export type Write = {
	program?: string;
	extensions?: Record<string, string>;
	intents?: string;
	intentsSkeleton?: boolean;
	manifest?: Record<string, unknown> | string;
	readme?: string;
	host?: string;
	corpus?: string;
	display?: string;
	line?: string;
};
/** One exact edit of a domain's file as it is on disk (py's edit()): path relative to the
 *  domain directory; old_string must occur exactly once, unless replace_all. */
export type Edit = { path: string; old_string: string; new_string: string; replace_all?: boolean };
/** readme()'s inputs: the catalog the domain is in, the run directory, and the model's
 *  two parts — summary (the paragraph after the title) and title (after "<name> — "). */
export type ReadmeOpts = { from?: string; run?: string; summary?: string; title?: string };
/** take's README: its text, or readme() from an agentic-loop run directory; else the domain's own. */
export type TakeOpts = { readme?: string; readmeFromRun?: string };

/** The SDK's own refusal (the CLI's {"error"}), or the CLI failing to run. */
export class CatalogError extends Error {
	verb: string;
	constructor(verb: string, message: string) {
		super(`catalog ${verb}: ${message}`);
		this.name = "CatalogError";
		this.verb = verb;
	}
}

/** The CLI itself: `cli(["get", "dog"])`, its JSON answer. `input` is stdin (for `-`
 *  arguments); `root` the catalog root (--root). Throws CatalogError. */
export function cli(args: string[], input?: string, root?: string): any {
	const py = process.env.METIS_LOOP_SDK_PY || "python3";
	try {
		return JSON.parse(
			execFileSync(py, ["-m", "metis_loop_sdk.catalog", ...(root ? ["--root", root] : []), ...args, "--json"], {
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
			// not the SDK's answer: the process itself failed
		}
		if (err) throw new CatalogError(args[0], err);
		throw new CatalogError(args[0], `${py} -m metis_loop_sdk.catalog: ${String(e.stderr || e.message).trim().slice(-500)}`);
	}
}

/** The catalog root the CLI resolves. */
export function root(r?: string): string {
	return cli(["root"], undefined, r).root;
}

/** Every catalog, the domains first (index); `domains`: those only; `consoles`: the agent console's rows. */
export function list(opts: { domains?: boolean; consoles?: boolean } = {}, r?: string): any[] {
	return cli(["list", ...(opts.domains ? ["--domains"] : []), ...(opts.consoles ? ["--consoles"] : [])], undefined, r);
}

/** One domain: its manifest and what the loader derives (program, serves, host, has, fingerprint …). */
export function get(name: string, r?: string): any {
	return cli(["get", name], undefined, r);
}

/** The domain's intent material; `spec`: with intent.yaml read (null without one). */
export function intents(name: string, opts: { spec?: boolean } = {}, r?: string): { name: string; intent: any; spec?: any } {
	return cli(["intents", name, ...(opts.spec ? ["--spec"] : [])], undefined, r);
}

/** A first intent.yaml drafted from the domain's program; null for a world with no commands
 *  when the SDK writes no intent.yaml for one (INTENTLESS). */
export function skeleton(name: string, r?: string): string | null {
	return cli(["intents", name, "--skeleton"], undefined, r).skeleton;
}

/** The command atoms of the domain's program (cmd_X …). */
export function commands(name: string, r?: string): string[] {
	return cli(["intents", name, "--skeleton"], undefined, r).commands;
}

/** The hash over what a reload takes. */
export function fingerprint(name: string, r?: string): string {
	return cli(["fingerprint", name], undefined, r).fingerprint;
}

// a write's texts as the CLI takes them: one on stdin, the others in files of a scratch directory
function writeArgs(w: Write, tmp: string): { args: string[]; input: string } {
	const args: string[] = [];
	let input = "";
	let k = 0;
	const text = (t: string) => {
		if (!input) {
			input = t;
			return "-";
		}
		const f = join(tmp, `t${++k}`);
		writeFileSync(f, t);
		return f;
	};
	if (w.program !== undefined) args.push("--program", text(w.program));
	for (const [n, t] of Object.entries(w.extensions ?? {})) args.push("--extension", `${n}=${text(t)}`);
	if (w.intents !== undefined && w.intentsSkeleton) throw new CatalogError("apply", "intents or intentsSkeleton, not both");
	if (w.intentsSkeleton) args.push("--intents-skeleton");
	else if (w.intents !== undefined) args.push("--intents", text(w.intents));
	if (w.manifest !== undefined) args.push("--manifest", JSON.stringify(w.manifest));
	if (w.readme !== undefined) args.push("--readme", text(w.readme));
	if (w.host !== undefined) args.push("--host", text(w.host));
	if (w.corpus !== undefined) args.push("--corpus", text(w.corpus));
	if (w.display !== undefined) args.push(`--display=${w.display}`);
	if (w.line !== undefined) args.push(`--line=${w.line}`);
	return { args, input };
}

// a dry run's --since: the earlier proposals in a file of the scratch directory
function sinceArgs(o: PlanOpts | undefined, tmp: string): string[] {
	if (!o?.since || !Object.keys(o.since).length) return [];
	const f = join(tmp, "since.json");
	writeFileSync(f, JSON.stringify(o.since));
	return ["--since", f];
}

function scratch<T>(f: (tmp: string) => T): T {
	const tmp = mkdtempSync(join(tmpdir(), "catalog-ts-"));
	try {
		return f(tmp);
	} finally {
		rmSync(tmp, { recursive: true, force: true });
	}
}

function write(name: string, w: Write, dry: boolean, r?: string, o?: PlanOpts): any {
	return scratch((tmp) => {
		const { args, input } = writeArgs(w, tmp);
		return cli(["apply", name, ...args, ...(dry ? ["--dry-run", ...sinceArgs(o, tmp)] : [])], input, r);
	});
}

/** What apply would write, with each file's diff; nothing is written. */
export function plan(name: string, w: Write, r?: string, o?: PlanOpts): Planned[] {
	return write(name, w, true, r, o).files;
}

/** The one validated write (domain.yaml through the loader's check, the intent files generated); never a commit. */
export function apply(name: string, w: Write, r?: string): Applied {
	return write(name, w, false, r);
}

function editArgs(name: string, e: Edit, tmp: string): { args: string[]; input: string } {
	const f = join(tmp, "new");
	writeFileSync(f, e.new_string);
	return { args: ["edit", name, e.path, "--old", "-", "--new", f, ...(e.replace_all ? ["--replace-all"] : [])], input: e.old_string };
}

/** What the edit would write (the file's diff against disk; a program's diagnostics checked):
 *  nothing is written. Refused (CatalogError) when old_string is not there exactly once, the
 *  path leaves the domain, or a .llp edit adds a diagnostic. */
export function planEdit(name: string, e: Edit, r?: string, o?: PlanOpts): Planned[] {
	return scratch((tmp) => {
		const { args, input } = editArgs(name, e, tmp);
		return cli([...args, "--dry-run", ...sinceArgs(o, tmp)], input, r).files;
	});
}

/** One exact edit of a domain's file, through apply's own checks; never formalize, never a commit. */
export function edit(name: string, e: Edit, r?: string): Applied {
	return scratch((tmp) => {
		const { args, input } = editArgs(name, e, tmp);
		return cli(args, input, r);
	});
}

function takeArgs(name: string, from: string, o: TakeOpts): { args: string[]; input: string } {
	if (o.readme !== undefined && o.readmeFromRun) throw new CatalogError("take", "readme or readmeFromRun, not both");
	const args = ["take", name, "--from", from];
	if (o.readme !== undefined) args.push("--readme", "-");
	if (o.readmeFromRun) args.push("--readme-from-run", o.readmeFromRun);
	return { args, input: o.readme ?? "" };
}

/** What take would write into `into`: the domain `name` of the catalog `from`. */
export function planTake(name: string, from: string, o: TakeOpts = {}, into?: string, p?: PlanOpts): Planned[] {
	const { args, input } = takeArgs(name, from, o);
	return scratch((tmp) => cli([...args, "--dry-run", ...sinceArgs(p, tmp)], input, into).files);
}

/** The domain `name` brought over from the catalog `from` into `into`: its domain.yaml, program,
 *  extensions, host, intent.yaml (intent/ generated again), corpus and README. Refused when
 *  `into` has it already. Never a commit. */
export function take(name: string, from: string, o: TakeOpts = {}, into?: string): Applied {
	const { args, input } = takeArgs(name, from, o);
	return cli(args, input, into);
}

/** A README for the domain `name` of the catalog `from` (default: the root), written from
 *  what an agentic-loop run left in `run` (the model and formalize's cost, or its seed): the
 *  SDK writes every mechanical part (where it came from, the program's header, the
 *  extensions, how to run it, the intents), a model only `summary` and `title`.
 *  readme(name, from, run) is the same as readme(name, { from, run }). */
export function readme(name: string, from?: string | ReadmeOpts, run?: string, r?: string): string {
	const o: ReadmeOpts = typeof from === "object" ? from : { from, run };
	const args = ["readme", name, ...(o.from ? ["--from", o.from] : []), ...(o.run ? ["--run", o.run] : [])];
	if (o.title !== undefined) args.push(`--title=${o.title}`);
	if (o.summary !== undefined) args.push("--summary", "-");
	return cli(args, o.summary, r).readme;
}

/** The domain's bundle (build/, git-ignored): the emitter's one-line account. */
export function build(name: string, r?: string): string {
	return cli(["build", name], undefined, r).bundle;
}

/** The catalog widget's directory, URL and files. */
export function widget(): { dir: string; url: string; files: string[] } {
	return cli(["widget"]);
}

/** This face's own directory and files, in the installed SDK. */
export function ts(): { dir: string; files: string[] } {
	return cli(["ts"]);
}
