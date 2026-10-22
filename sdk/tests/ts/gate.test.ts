// The SDK's gate, TypeScript face (loop-parity s-72d9d36b), against the py SDK's own CLI: a
// proposal's plan, a refusal remembered across calls (its next plan carries since_diff), a confirm
// that writes exactly the plan, the rules' words as GateError. Run by tests/test_ts_face.py, or:
//   METIS_LOOP_SDK_PY=<python with the SDK> CAT=<metis-catalog> [METIS_LOOP_SDK_GATE_TS=<its gate.ts>] \
//     node --experimental-strip-types --test sdk/tests/ts/gate.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { cpSync, existsSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

type Face = typeof import("../../metis_loop_sdk/ts/gate.ts");
const gate: Face = await import(
	process.env.METIS_LOOP_SDK_GATE_TS ? pathToFileURL(process.env.METIS_LOOP_SDK_GATE_TS).href : "../../metis_loop_sdk/ts/gate.ts");
// the fixtures' catalog: $CAT, named (test_ts_face.py sets it; never a checkout beside this one)
const CAT = process.env.CAT ?? (() => { throw new Error("CAT: the metis-catalog the fixtures are copied from"); })();

function scratch(): { root: string; state: string } {
	const root = mkdtempSync(join(tmpdir(), "gate-ts-test-"));
	cpSync(join(CAT, "domains", "plant"), join(root, "domains", "plant"), {
		recursive: true, filter: (s) => !/\/(records|build|__pycache__)(\/|$)/.test(s),
	});
	return { root, state: join(root, ".metis") };
}

test("propose, refuse, propose again with since_diff, confirm writes exactly the plan", () => {
	const o = scratch();
	const pl = gate.propose("readme", "plant", { text: "A plant.", title: "a plant" }, o);
	assert.equal(pl.kind, "readme");
	assert.equal(pl.token.length, 16);
	const rd = pl.files.find((f) => f.path === "domains/plant/README.md")!;
	assert.ok(rd.diff.includes("+A plant."));
	assert.deepEqual(gate.refuse(pl.token, o.state), { refused: pl.files.map((f) => f.path) });
	const again = gate.propose("readme", "plant", { text: "A plant, watered.", title: "a plant" }, o);
	assert.ok(again.files.find((f) => f.path === "domains/plant/README.md")!.since_diff!.includes("+A plant, watered."));
	const out = gate.confirm(again.token, o.state);
	assert.ok(out.written.includes("domains/plant/README.md"));
	assert.match(readFileSync(join(o.root, "domains", "plant", "README.md"), "utf8"), /A plant, watered\./);
	assert.deepEqual(JSON.parse(readFileSync(join(o.state, "gate.json"), "utf8")).plans, {});
});

test("a program's plan serves it after the write; a note needs no write", () => {
	const o = scratch();
	const text = readFileSync(join(o.root, "domains", "plant", "plant.llp"), "utf8") + "% one more line\n";
	const pl = gate.propose("program", "plant", { text }, o);
	assert.equal(pl.reopen, true);
	const out = gate.confirm(pl.token, o.state);
	assert.deepEqual(out.written, ["domains/plant/plant.llp"]);
	assert.equal(out.serve!.program, join(o.root, "domains", "plant", "plant.llp"));
	assert.ok(existsSync(join(o.state, "gate.json")));
});

test("the rules' words reach the caller, named as the face names its verbs", () => {
	const o = scratch();
	assert.throws(() => gate.propose("readme", "lamp", { text: "x" }, o), /^GateError: catalog readme: no domain lamp in the loop's catalog yet: its README follows its program/);
	assert.throws(() => gate.confirm("0000000000000000", o.state), /gate confirm: not approved: no such plan/);
	assert.throws(() => gate.propose("take", "plant", { src: o.root }, { ...o, root: o.root }), /catalog take: .*plant/);
});
