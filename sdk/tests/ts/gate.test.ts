// The SDK's gate, TypeScript face (loop-parity s-72d9d36b), against the py SDK's own CLI: a
// proposal's plan, a refusal remembered across calls (its next plan carries since_diff), a confirm
// that writes exactly the plan, the rules' words as GateError. Run by tests/test_ts_face.py, or:
//   METIS_LOOP_SDK_PY=<python with the SDK> CAT=<metis-catalog> [METIS_LOOP_SDK_GATE_TS=<its gate.ts>] \
//     node --experimental-strip-types --test sdk/tests/ts/gate.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

type Face = typeof import("../../metis_loop_sdk/ts/gate.ts");
const gate: Face = await import(
	process.env.METIS_LOOP_SDK_GATE_TS ? pathToFileURL(process.env.METIS_LOOP_SDK_GATE_TS).href : "../../metis_loop_sdk/ts/gate.ts");
// the fixtures' catalog: $CAT, named (test_ts_face.py sets it; never a checkout beside this one)
const CAT = process.env.CAT ?? (() => { throw new Error("CAT: the metis-catalog the fixtures are copied from"); })();

// a .llp write is checked by metisc (the catalog's metisc(): METISC, else PATH)
const HAS_METISC = (() => {
	try {
		return !!JSON.parse(execFileSync(process.env.METIS_LOOP_SDK_PY ?? "python3", ["-c", "import json; from metis import catalog; print(json.dumps(catalog.metisc()))"], { encoding: "utf8" }));
	} catch {
		return false;
	}
})();

function scratch(): { root: string; state: string } {
	const root = mkdtempSync(join(tmpdir(), "gate-ts-test-"));
	cpSync(join(CAT, "domains", "plant"), join(root, "domains", "plant"), {
		recursive: true, filter: (s) => !/\/(records|build|__pycache__)(\/|$)/.test(s),
	});
	return { root, state: join(root, ".metis") };
}

test("propose, refuse, propose again with since_diff, confirm writes exactly the plan", () => {
	const o = scratch();
	rmSync(join(o.root, "domains", "plant", "README.md"), { force: true });            // an edit makes the file it lacks
	const pl = gate.propose("edit", "plant", { path: "README.md", old: "", new: "# plant\n\nA plant.\n" }, o);
	assert.equal(pl.kind, "edit");
	assert.equal(pl.token.length, 16);
	assert.deepEqual(pl.findings, []);
	const rd = pl.files.find((f) => f.path === "domains/plant/README.md")!;
	assert.ok(rd.diff.includes("+A plant."));
	assert.deepEqual(gate.refuse(pl.token, o.state), { refused: pl.files.map((f) => f.path) });
	const again = gate.propose("edit", "plant", { path: "README.md", old: "", new: "# plant\n\nA plant, watered.\n" }, o);
	assert.ok(again.files.find((f) => f.path === "domains/plant/README.md")!.since_diff!.includes("+A plant, watered."));
	const out = gate.confirm(again.token, o.state);
	assert.ok(out.written.includes("domains/plant/README.md"));
	assert.match(readFileSync(join(o.root, "domains", "plant", "README.md"), "utf8"), /A plant, watered\./);
	assert.deepEqual(JSON.parse(readFileSync(join(o.state, "gate.json"), "utf8")).plans, {});
});

test("a program's edit serves it after the write (metisc checks it)", { skip: !HAS_METISC && "no metisc" }, () => {
	const o = scratch();
	const old = readFileSync(join(o.root, "domains", "plant", "plant.llp"), "utf8");
	const pl = gate.propose("edit", "plant", { path: "plant.llp", old, new: old + "% one more line\n" }, o);
	assert.equal(pl.reopen, true);
	const out = gate.confirm(pl.token, o.state);
	assert.deepEqual(out.written, ["domains/plant/plant.llp"]);
	assert.equal(out.serve!.program, join(o.root, "domains", "plant", "plant.llp"));
	assert.ok(existsSync(join(o.state, "gate.json")));
});

test("the rules' words reach the caller, named as the face names its verbs", () => {
	const o = scratch();
	assert.throws(() => gate.propose("new", "plant", { text: "x" }, o), /^GateError: catalog new: plant: the catalog has it: change it with edit/);
	assert.throws(() => gate.confirm("0000000000000000", o.state), /gate confirm: not approved: no such plan/);
	assert.throws(() => gate.propose("take", "plant", { src: o.root }, { ...o, root: o.root }), /catalog take: .*plant/);
});
