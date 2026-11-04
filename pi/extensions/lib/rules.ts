// The rules of a unit's text, and what an edit changes among them (loop-prompt s-3591d53b step 5, the architect's
// F1: the apply is tied to the ruling). A rule is its head line `name [layer] : …` through the first line that ends in
// `.`; its text is compared with comments dropped and whitespace collapsed, so the %% line above it and the spacing
// never decide whether it is the judged pack's rule (nor a space before `.`, `,` or `)`).

export const RULE_HEAD = /^\s*([a-z][a-z0-9_]*)\s*\[([a-z0-9_,\s]+)\]\s*:/;

export type Rule = { name: string; text: string };

/** A line without its `%` comment (a `%%` doc line is all comment). */
export function nocomment(l: string): string {
	const i = l.indexOf("%");
	return i < 0 ? l : l.slice(0, i);
}

/** The rules of TEXT: name and normalized text (comments dropped, whitespace collapsed), in order. */
export function rulesOf(text: string): Rule[] {
	const out: Rule[] = [];
	const lines = text.split("\n");
	for (let i = 0; i < lines.length; i++) {
		const m = lines[i].match(RULE_HEAD);
		if (!m) continue;
		let body = nocomment(lines[i]);
		let j = i;
		while (!body.trimEnd().endsWith(".") && j < lines.length - 1) body += " " + nocomment(lines[++j]);
		out.push({ name: m[1], text: body.replace(/\s+/g, " ").replace(/\s+([.,)])/g, "$1").trim() });
		i = j;
	}
	return out;
}

/** The rules NEW has that OLD has not (by normalized text): what an edit adds or rewrites; [] for an edit that
 *  changes no rule (a comment, a declaration, a README). */
export function changedRules(oldText: string, newText: string): Rule[] {
	const had = new Set(rulesOf(oldText).map((r) => r.text));
	return rulesOf(newText).filter((r) => !had.has(r.text));
}
