// The language in front of the model (language-rag, the architect's design of 2026-11-05; gpt-oss s-0f23f8cd step 3):
// deterministic, lexical retrieval at the two moments the model writes the language. No model, no embeddings.
//   layer 1  examplesFor: whole rules of the member's own units over the surprise's atoms, for surprise_next
//   layer 2  refusalHelp: a refusal answered with what fixes it (the construct's paragraph, the nearest well-formed
//            rule of the unit, a lint row's check) for pack_propose
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { nocomment, RULE_HEAD } from "./rules.ts";

/** One line of the language a pack is written in (the architect's grammar line; under 40 words). */
export const GRAMMAR =
	"A pack's text is metis only: `drop NAME.` lines, `pred` lines, and `stage S { … }` around new rules. A rule: " +
	"`name [layer] : premises -o effects.`; `$p` reads p, a bare p is consumed; `%%` is the person's line.";

export type UnitRule = { name: string; path: string; line: number; stage: string | null; doc: string | null; text: string; preds: Set<string> };

/** The predicates a rule's text names: every identifier outside parentheses after its head, `$` dropped (the
 *  arguments are constants or variables, never predicates). */
export function predsOf(text: string): Set<string> {
	const body = text.replace(RULE_HEAD, "").replace(/-o\b/g, " ").replace(/@w\b/g, " ");
	let flat = "";
	let depth = 0;
	for (const c of body) {
		if (c === "(") depth++;
		else if (c === ")") depth = Math.max(0, depth - 1);
		else if (depth === 0) flat += c;
	}
	return new Set((flat.match(/[a-z][a-z0-9_]*/g) ?? []).filter((x) => x !== "o"));
}

/** The rules of a unit's text, whole: name, path:line, the stage they sit in, the %% line, the text to its "." */
export function unitRules(path: string, text: string): UnitRule[] {
	const out: UnitRule[] = [];
	const lines = text.split("\n");
	let stage: string | null = null;
	for (let i = 0; i < lines.length; i++) {
		const st = lines[i].match(/^\s*stage\s+([a-z0-9_]+)\s*\{/);
		if (st) { stage = st[1]; continue; }
		const m = lines[i].match(RULE_HEAD);
		if (!m) continue;
		let j = i;
		while (j < lines.length - 1 && !nocomment(lines[j]).trimEnd().endsWith(".")) j++;
		const t = lines.slice(i, j + 1).map((x) => x.trim()).join("\n");
		const doc = i > 0 && /^\s*%%/.test(lines[i - 1]) ? lines[i - 1].trim() : null;
		out.push({ name: m[1], path, line: i + 1, stage, doc, text: t, preds: predsOf(nocomment(t)) });
		i = j;
	}
	return out;
}

/** The predicates a unit declares (`pred NAME …`, `bwd NAME …`, ports). */
export function declared(text: string): Set<string> {
	const out = new Set<string>();
	for (const l of text.split("\n")) {
		const m = nocomment(l).match(/^\s*(?:pred|bwd|weight|guard|input|output)\s+([a-z][a-z0-9_]*)/);
		if (m) out.add(m[1]);
	}
	return out;
}

/** What a trace says of the surprise's tick (or window): the rules fired there, the atoms taken (`+take(other)` →
 *  take). TRACE: the run's directory (seg-*.jsonl). */
export function firedAt(trace: string, member: string, k0: number, k1: number = k0): { rules: Set<string>; atoms: Set<string> } {
	const rules = new Set<string>();
	const atoms = new Set<string>();
	let segs: string[] = [];
	try { segs = readdirSync(trace).filter((f) => /^seg-\d+\.jsonl$/.test(f)).sort(); } catch { return { rules, atoms }; }
	for (const f of segs) {
		for (const l of readFileSync(join(trace, f), "utf8").split("\n")) {
			if (!l.startsWith('{"k"')) continue;
			let row: any;
			try { row = JSON.parse(l); } catch { continue; }
			if (!(row.k >= k0 && row.k <= k1)) continue;
			for (const it of row.members?.[member]?.seq ?? []) {
				for (const x of it.step ?? it.beat ?? it.fired ?? []) rules.add(String(x).split("[")[0]);
				for (const x of it.take ?? []) { const a = String(x).replace(/^[+-]/, "").match(/^[a-z][a-z0-9_]*/); if (a) atoms.add(a[0]); }
			}
		}
	}
	return { rules, atoms };
}

/** Layer 1: the rules of FILES that name the most of SEEDS (a fired rule counts three), whole, best first, 3 to MAX
 *  of them within CAP characters. → [] when nothing matches. */
export function pickExamples(files: { path: string; text: string }[], seeds: Set<string>, fired: Set<string> = new Set(), max = 8, cap = 2000): UnitRule[] {
	const all = files.flatMap((f) => unitRules(f.path, f.text));
	const scored = all
		.map((r, i) => ({ r, i, s: [...r.preds].filter((p) => seeds.has(p)).length + (fired.has(r.name) ? 3 : 0) }))
		.filter((x) => x.s > 0)
		.sort((a, b) => b.s - a.s || a.i - b.i);
	const out: UnitRule[] = [];
	let size = 0;
	for (const { r } of scored) {
		const n = r.text.length + (r.doc?.length ?? 0) + r.path.length + 20;
		if (out.length >= max || (out.length >= 3 && size + n > cap)) break;
		out.push(r);
		size += n;
	}
	return out;
}

/** The section surprise_next prints: the grammar line, the seeds, the rules whole with where they sit. */
export function examplesSection(ex: UnitRule[], seeds: Set<string>): string {
	if (!ex.length) return "";
	return [
		"## examples: whole rules of this member over the surprise's atoms (copy their shape; the pack is written like them)",
		GRAMMAR,
		`(the atoms: ${[...seeds].sort().join(", ")})`,
		...ex.flatMap((r) => ["", `% ${r.path}:${r.line}${r.stage ? ` (stage ${r.stage})` : ""}`, ...(r.doc ? [r.doc] : []), r.text]),
	].join("\n");
}

/** The seeds of a surprise: its atoms, the trace's fired rules' predicates and taken atoms at its tick, and the
 *  words of its reading and words that are predicates the units declare. */
export function seedsOf(s: any, traceDir: string | null, files: { path: string; text: string }[]): { seeds: Set<string>; fired: Set<string> } {
	const decl = new Set(files.flatMap((f) => [...declared(f.text)]));
	const seeds = new Set<string>();
	for (const a of s.atoms ?? []) { const m = String(a).match(/^[$+-]?([a-z][a-z0-9_]*)/); if (m) seeds.add(m[1]); }
	let fired = new Set<string>();
	const w = Array.isArray(s.window) ? s.window : null;
	const k0 = w ? w[0] : s.k;
	const k1 = w ? w[1] : s.k;
	if (traceDir && k0 != null && existsSync(traceDir)) {
		const f = firedAt(traceDir, s.member, Number(k0), Number(k1));
		fired = f.rules;
		for (const a of f.atoms) seeds.add(a);
		const rules = files.flatMap((x) => unitRules(x.path, x.text));
		for (const r of rules) if (fired.has(r.name)) for (const p of r.preds) seeds.add(p);
	}
	for (const t of `${s.reading ?? ""} ${s.words ?? ""}`.toLowerCase().match(/[a-z][a-z0-9_]*/g) ?? []) if (decl.has(t)) seeds.add(t);
	return { seeds, fired };
}

// ---- layer 2: the refusal that corrects ---------------------------------------------------------------------------

/** The link's refusals by class: the error's text → the construct's paragraph (spec 00; the architect's table, about
 *  15 rows, replaces this draft). */
export const REFUSALS: { re: RegExp; spec: string; text: string }[] = [
	{ re: /lex error: .*bad character '='/, spec: "spec 00 §1",
	  text: "A `key=value` line is not metis: the pack's text is rules and declarations only. The file a pack amends is pack_propose's unit argument, never a line of the pack." },
	{ re: /lex error/, spec: "spec 00 §1",
	  text: "The tokens are idents, numbers, strings, `-o`, `:-`, `<>`, `@w`, `..`, `%%` doc lines, `%` comments and the punctuation { } ( ) . , * : [ ] ~ $; any other character is a lex error. No prose outside `%%` lines." },
	{ re: /parse error: .*expected '\.'/, spec: "spec 00 §2",
	  text: "`.` ends every declaration; a rule sits inside `stage S { … }` as `name [layer] : body -o head.`, its %% line above it. A bare rule outside a stage block does not parse." },
	{ re: /parse error: .*expected -o/, spec: "spec 00 §2",
	  text: "A rule's body is atoms joined by `*`, then `-o`, then the head. There is no negation in a body (`~` and `not` are not premises): say the absence with an atom a rule produces, or with the state the other case leaves." },
	{ re: /parse error/, spec: "spec 00 §2",
	  text: "rule ::= [%% doc] ident \"[\" layer \"]\" \":\" body \"-o\" head \".\"; body ::= atom (\"*\" atom)*; atom ::= [\"$\"] ident [\"(\" term (\",\" term)* \")\"]; head ::= \"()\" | atom (\"*\" atom)*." },
	{ re: /undeclared predicate '([^']+)'/, spec: "spec 00 §5",
	  text: "Every predicate a rule names is declared (`pred NAME(args) : layer.`) in the unit or a unit it includes. A pack that brings a new atom brings its `pred` line; a name that exists is spelled as the unit spells it." },
	{ re: /repeats|duplicate/, spec: "the pack's merge",
	  text: "The pack's rule is a rule the unit has (the same premises and effects, or the same name). To change a rule, `drop NAME.` it and write the new one; a second draft changes the premise the refusal named, never only the name." },
	{ re: /I5 .*gating program, but no rule reads tick__grant/, spec: "the interface check I5",
	  text: "This member gates itself: the rule that starts its motion reads the grant, as the unit's own rules do (`$tick__grant(…)` among its premises). Keep that premise when you rewrite such a rule." },
];

/** A lint row's check, from the pattern catalogue (CHECKS.md §3: the **Ln `name`** paragraph). */
export function lintParagraph(code: string, checks: string): string | null {
	const m = new RegExp(`\\*\\*${code}([ *\`][\\s\\S]*?)(?:\\n\\n|$)`).exec(checks);
	return m ? `**${code}${m[1]}`.replace(/\s+/g, " ").trim() : null;
}

/** Layer 2: what a refusal's document gets beside it: the construct's paragraph for a link error, the nearest
 *  well-formed rule of the unit (layer 1's scoring on the refused pack's predicates), the check of each lint row
 *  named. "" when the document names nothing this answers. */
export function refusalHelp(doc: string, pack: string, unitFiles: { path: string; text: string }[], checks = ""): string {
	const out: string[] = [];
	const why = (doc.match(/## Why it is refused\n([\s\S]*?)(?:\n## |$)/)?.[1] ?? doc).trim();
	const hit = REFUSALS.find((r) => r.re.test(why));
	if (hit) out.push(`${hit.spec}: ${hit.text}`);
	const codes = [...new Set(why.match(/\bL\d{1,2}\b/g) ?? [])];
	for (const c of codes) {
		const p = checks ? lintParagraph(c, checks) : null;
		if (p) out.push(p);
	}
	if (hit || /link refused|parse|lex/.test(why)) {
		const seeds = new Set<string>();
		for (const r of unitRules("pack", pack)) for (const p of r.preds) seeds.add(p);
		const names = new Set(unitRules("pack", pack).map((r) => r.name));
		for (const m of pack.matchAll(/^\s*drop\s+([a-z][a-z0-9_]*)/gm)) names.add(m[1]);
		const near = pickExamples(unitFiles, seeds, names, 2, 900);
		if (near.length) out.push("the nearest well-formed rules of the unit:", ...near.flatMap((r) => [`% ${r.path}:${r.line}${r.stage ? ` (stage ${r.stage})` : ""}`, ...(r.doc ? [r.doc] : []), r.text]));
	}
	return out.length ? ["## what fixes it", GRAMMAR, ...out].join("\n") : "";
}
