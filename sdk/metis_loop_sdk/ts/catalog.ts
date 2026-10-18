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
//   catalog.apply("lamp", { program, manifest })
//   catalog.take("lamp", from, { readmeFromRun: run }, into)
//
// The python: $METIS_LOOP_SDK_PY (a python with the SDK installed), else python3. The
// root: each call's `root`, else the CLI's own rule ($METIS_CATALOG, else the sibling
// checkout). The SDK's refusals ({"error"}, exit 1) throw as CatalogError.
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

/** One file a write would change: its path (relative to the root), new or not, its unified diff. */
export type Planned = { path: string; new: boolean; diff: string };
/** What a write wrote: the paths, the diff, the domain's fingerprint after it (null: no manifest). */
export type Applied = { written: string[]; diff: string; fingerprint: string | null };
/** A write's texts (apply, plan): the program, extensions by name, intent.yaml (or
 *  intentsSkeleton: one drafted from the program), domain.yaml's keys to set (or its whole text). */
export type Write = {
	program?: string;
	extensions?: Record<string, string>;
	intents?: string;
	intentsSkeleton?: boolean;
	manifest?: Record<string, unknown> | string;
};
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

/** A first intent.yaml drafted from the domain's program. */
export function skeleton(name: string, r?: string): string {
	return cli(["intents", name, "--skeleton"], undefined, r).skeleton;
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
	return { args, input };
}

function write(name: string, w: Write, dry: boolean, r?: string): any {
	const tmp = mkdtempSync(join(tmpdir(), "catalog-ts-"));
	try {
		const { args, input } = writeArgs(w, tmp);
		return cli(["apply", name, ...args, ...(dry ? ["--dry-run"] : [])], input, r);
	} finally {
		rmSync(tmp, { recursive: true, force: true });
	}
}

/** What apply would write, with each file's diff; nothing is written. */
export function plan(name: string, w: Write, r?: string): Planned[] {
	return write(name, w, true, r).files;
}

/** The one validated write (domain.yaml through the loader's check, the intent files generated); never a commit. */
export function apply(name: string, w: Write, r?: string): Applied {
	return write(name, w, false, r);
}

function takeArgs(name: string, from: string, o: TakeOpts): { args: string[]; input: string } {
	if (o.readme !== undefined && o.readmeFromRun) throw new CatalogError("take", "readme or readmeFromRun, not both");
	const args = ["take", name, "--from", from];
	if (o.readme !== undefined) args.push("--readme", "-");
	if (o.readmeFromRun) args.push("--readme-from-run", o.readmeFromRun);
	return { args, input: o.readme ?? "" };
}

/** What take would write into `into`: the domain `name` of the catalog `from`. */
export function planTake(name: string, from: string, o: TakeOpts = {}, into?: string): Planned[] {
	const { args, input } = takeArgs(name, from, o);
	return cli([...args, "--dry-run"], input, into).files;
}

/** The domain `name` brought over from the catalog `from` into `into`: its domain.yaml, program,
 *  extensions, host, intent.yaml (intent/ generated again), corpus and README. Refused when
 *  `into` has it already. Never a commit. */
export function take(name: string, from: string, o: TakeOpts = {}, into?: string): Applied {
	const { args, input } = takeArgs(name, from, o);
	return cli(args, input, into);
}

/** The domain's bundle (build/, git-ignored): the emitter's one-line account. */
export function build(name: string, r?: string): string {
	return cli(["build", name], undefined, r).bundle;
}

/** The catalog widget's directory, URL and files. */
export function widget(): { dir: string; url: string; files: string[] } {
	return cli(["widget"]);
}
