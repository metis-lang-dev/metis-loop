// The loop SDK's gate, TypeScript face (loop-parity s-72d9d36b): the loop's policy for a
// write into a catalog — propose, the person reads the plan's diff, confirm or refuse —
// through metispy's gate CLI (python -m metis.gate), so both loops follow one policy:
//
//   import * as gate from "./gate.ts";
//   const pl = gate.propose("program", "lamp", { text, display, line }, { root, run, state });
//   pl.files            // [{path, new, diff, text, since_diff?}]: what confirm writes, each with its diff
//   gate.confirm(pl.token, state)   // writes exactly that plan: {written, fingerprint, serve?, bundle?, note?}
//   gate.refuse(pl.token, state)    // the person said no: its texts are remembered (the next plan diffs from them)
//
// state: the loop's state directory (DIR/.metis/), where the gate keeps its memory (gate.json);
// run: the directory with the seed (seed.json) and the run's records (default: state). A rule
// that says no throws GateError with its words, named as the catalog face names its verbs:
// "catalog <kind>: …" for a proposal, "gate confirm: …" / "gate refuse: …" after it.
import { execFileSync } from "node:child_process";
import type { Planned } from "./catalog.ts";

export type Kind = "program" | "served" | "extension" | "intents" | "readme" | "edit" | "take";

/** A plan the person reads: the files confirm writes, its token; note: nothing to write, and why;
 *  say: a word for the loop with the write's result; reopen: the REPL serves the program after it. */
export interface Plan {
	token: string;
	kind: Kind;
	domain: string;
	root: string;
	files: Planned[];
	reopen: boolean;
	note?: string;
	say?: string;
}

/** What confirm wrote; serve: the program (and its host, as --host takes it) to serve after it;
 *  bundle: a take's build, or why it did not build. */
export interface Confirmed {
	written: string[];
	fingerprint: string | null;
	note?: string;
	serve?: { program: string; host: string | null };
	bundle?: string;
}

/** A rule of the gate (or the SDK under it) refused: its message is the rule's words. */
export class GateError extends Error {
	constructor(message: string) {
		super(message);
		this.name = "GateError";
	}
}

function cli(args: string[], state: string, label: string, input = ""): any {
	const py = process.env.METIS_LOOP_SDK_PY || "python3";
	try {
		return JSON.parse(
			execFileSync(py, ["-m", "metis.gate", "--state", state, ...args, "--json"], {
				input,
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
		if (err) throw new GateError(`${label}: ${err}`);
		throw new GateError(`${label}: ${py} -m metis.gate: ${String(e.stderr || e.message).trim().slice(-500)}`);
	}
}

/** A plan of the write `kind` for `domain`: args as the kind takes them (text, display, line, name,
 *  title, path/old/new/replace_all, src). */
export function propose(kind: Kind, domain: string, args: Record<string, unknown>, o: { root: string; state: string; run?: string }): Plan {
	return cli(["propose", kind, domain, "--root", o.root, "--run", o.run ?? o.state], o.state, `catalog ${kind}`, JSON.stringify(args));
}

/** Write exactly the plan `token` names (a source changed since refuses: nothing written). */
export function confirm(token: string, state: string): Confirmed {
	return cli(["confirm", token], state, "gate confirm");
}

/** The person refused the plan `token`: its texts are remembered, per root and file. */
export function refuse(token: string, state: string): { refused: string[] } {
	return cli(["refuse", token], state, "gate refuse");
}
