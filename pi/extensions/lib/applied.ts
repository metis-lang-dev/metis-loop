// The apply tied to the ruling (loop-prompt s-3591d53b step 5, the architect's F1). In a workspace, an edit of a .llp
// through catalog_edit is the apply of an ACCEPTED ruling: every rule the edit adds or rewrites is a rule of an
// accepted ruling's pack (packs/<id>.llp), compared by text with comments and spacing dropped; otherwise the edit is
// refused in words before the person is asked. An edit that changes no rule (a comment, a declaration) is allowed and
// said to apply nothing, so the loop cannot report it as a fix. ruling="undo" reverses an applied edit exactly (the
// journal's `applied` row keeps the two texts' sha256, never the texts).
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import * as ws from "../sdk/workspace.ts";
import { changedRules, rulesOf } from "./rules.ts";

export type EditLike = { domain: string; path: string; old_string: string; new_string: string; ruling?: string };
export type Applied = { ids: string[]; domain: string; path: string; old_sha: string; new_sha: string; undo?: boolean };

export const sha = (s: string) => createHash("sha256").update(s).digest("hex");

/** A ruling's pack text (its `pack` as the face writes it: relative to .metis/, or to the root). */
export function packText(rel: string, r: string): string {
	const f = rel.startsWith(".metis/") || rel.startsWith("/") ? resolve(r, rel) : join(r, ".metis", rel);
	return existsSync(f) ? readFileSync(f, "utf8") : "";
}

/** What the edit P applies in the workspace R: {say, applied} or a thrown Error with the refusal's words. */
export function applied(p: EditLike, r: string): { say: string; applied?: Applied } {
	const old_sha = sha(p.old_string), new_sha = sha(p.new_string);
	if (p.ruling === "undo") {
		const rows = ws.events(0, r).filter((e: any) => (e.who === "pi" || e.who === "backend") && e.kind === "applied" && e.new_sha === old_sha && e.old_sha === new_sha);   // pi's or the console's /apply
		if (!rows.length) throw new Error("undo: no applied edit is reversed by this one (old_string must be the text an applied edit wrote, new_string the text it replaced)");
		const ids = [...new Set<string>(rows.flatMap((e: any) => (Array.isArray(e.surprise) ? e.surprise : [e.surprise]).map(String)))];
		return { say: ` Reverses the applied edit of ruling ${ids.join(", ")}.`, applied: { ids, domain: p.domain, path: p.path, old_sha, new_sha, undo: true } };
	}
	const changed = changedRules(p.old_string, p.new_string);
	if (!changed.length) return { say: " No rule changed: this edit applies no ruling (a comment or a declaration is not a fix)." };
	const accepted = ws.rulings(r).filter((x: any) => x.verdict === "accepted" && x.pack);
	const packs = accepted.map((x: any) => ({ id: String(x.id), rules: new Set(rulesOf(packText(String(x.pack), r)).map((q) => q.text)) }));
	const hit = (t: string) => packs.find((k) => k.rules.has(t));
	const miss = changed.filter((c) => !hit(c.text));
	if (miss.length)
		throw new Error(
			`not the judged pack: ${miss.length} rule(s) of this edit (${miss.map((m) => m.name).join(", ")}) are in no accepted ruling` +
			(accepted.length ? ` (accepted: ${accepted.map((x: any) => x.id).join(", ")})` : " (none in this workspace)") +
			". Judge the pack with pack_propose; then apply its rules as they were accepted, word for word. A comment-only edit applies nothing.",
		);
	const ids = [...new Set(changed.map((c) => hit(c.text)!.id))];
	return { say: ` Applies the accepted ruling ${ids.join(", ")}.`, applied: { ids, domain: p.domain, path: p.path, old_sha, new_sha } };
}
