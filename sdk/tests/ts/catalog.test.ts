// The SDK's TypeScript face against the py SDK's own CLI (fiction-port s-e3d0942d step 1):
// each function answers what the CLI answers, the writes land as the py tests' do, and
// the SDK's refusals throw. Run by tests/test_ts_face.py (node >= 22.6), or:
//   METIS_LOOP_SDK_PY=<python with the SDK> CAT=<metis-catalog> [METIS_LOOP_SDK_TS=<its catalog.ts>] \
//     node --experimental-strip-types --test sdk/tests/ts/catalog.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

// the face under test: $METIS_LOOP_SDK_TS (the installed package's, test_ts_face.py sets it), else this checkout's
type Face = typeof import("../../metis_loop_sdk/ts/catalog.ts");
const catalog: Face = await import(
	process.env.METIS_LOOP_SDK_TS ? pathToFileURL(process.env.METIS_LOOP_SDK_TS).href : "../../metis_loop_sdk/ts/catalog.ts");

const HERE = dirname(fileURLToPath(import.meta.url));
const CAT = process.env.CAT ?? resolve(HERE, "..", "..", "..", "..", "metis-catalog");
const PY = process.env.METIS_LOOP_SDK_PY ?? "python3";

// a scratch catalog: the dog and the plant, and the intent generator (the py tests' fixture)
function scratch(): string {
	const r = mkdtempSync(join(tmpdir(), "catalog-ts-test-"));
	for (const d of ["dog", "plant"])
		cpSync(join(CAT, "domains", d), join(r, "domains", d), {
			recursive: true,
			filter: (s) => !/\/(records|build|__pycache__)(\/|$)/.test(s),
		});
	cpSync(join(CAT, "tools"), join(r, "tools"), { recursive: true, filter: (s) => !s.includes("__pycache__") });
	return r;
}
const py = (r: string, ...args: string[]) =>
	JSON.parse(execFileSync(PY, ["-m", "metis_loop_sdk.catalog", "--root", r, ...args, "--json"], { encoding: "utf8" }));

test("the reads answer what the py CLI answers", () => {
	const r = scratch();
	assert.equal(catalog.root(r), resolve(r));
	assert.deepEqual(catalog.list({}, r), py(r, "list"));
	assert.deepEqual(catalog.list({ domains: true }, r), py(r, "list", "--domains"));
	assert.deepEqual(catalog.list({ consoles: true }, r), py(r, "list", "--consoles"));
	assert.deepEqual(catalog.get("dog", r), py(r, "get", "dog"));
	assert.deepEqual(catalog.intents("dog", { spec: true }, r), py(r, "intents", "dog", "--spec"));
	assert.equal(catalog.skeleton("plant", r), py(r, "intents", "plant", "--skeleton").skeleton);
	assert.equal(catalog.fingerprint("dog", r), py(r, "fingerprint", "dog").fingerprint);
	assert.deepEqual(catalog.widget(), py(r, "widget"));
});

test("plan writes nothing; apply writes the program, the extensions and the intents", () => {
	const r = scratch();
	const prog = readFileSync(join(r, "domains/dog/dog.llp"), "utf8") + "% from ts\n";
	const w = { program: prog, extensions: { tricks: "% an extension\n", "Pet Moves": "% another\n" } };
	const planned = catalog.plan("dog", w, r);
	assert.deepEqual(planned.map((f) => [f.path, f.new]), [
		["domains/dog/dog.llp", false], ["domains/dog/extensions/tricks.llp", true], ["domains/dog/extensions/pet_moves.llp", true]]);
	assert.match(planned[0].diff, /\+% from ts/);
	assert.ok(!existsSync(join(r, "domains/dog/extensions")));
	const before = catalog.fingerprint("dog", r);
	const out = catalog.apply("dog", w, r);
	assert.deepEqual(out.written, planned.map((f) => f.path));                    // three texts: stdin and two files
	assert.equal(readFileSync(join(r, "domains/dog/extensions/pet_moves.llp"), "utf8"), "% another\n");
	assert.ok(out.fingerprint && out.fingerprint !== before);
	assert.deepEqual(catalog.apply("dog", { program: prog }, r).written, []);    // unchanged: nothing
	const it = catalog.apply("plant", { intentsSkeleton: true }, r);
	assert.ok(it.written.includes("domains/plant/intent.yaml"));
	const nu = catalog.apply("bell", { program: "% the bell\n", manifest: { display: "the bell" } }, r);
	assert.deepEqual(nu.written, ["domains/bell/bell.llp", "domains/bell/domain.yaml"]);
	assert.equal(readFileSync(join(r, "domains/bell/domain.yaml"), "utf8"), "display: the bell\nprogram: bell.llp\n");
});

test("take brings a domain over, with a README from the run; build makes its bundle", () => {
	const src = scratch();
	const into = mkdtempSync(join(tmpdir(), "catalog-ts-into-"));
	mkdirSync(join(into, "domains"));
	cpSync(join(src, "tools"), join(into, "tools"), { recursive: true });
	execFileSync("rm", [join(src, "domains/plant/intent/plant-spoken.txt")]);   // empty: take writes none
	const planned = catalog.planTake("plant", src, {}, into);
	assert.ok(planned.some((f) => f.path === "domains/plant/plant_host.py" && f.new));
	assert.ok(!existsSync(join(into, "domains/plant")));
	const out = catalog.take("plant", src, { readme: "# plant, taken\n" }, into);
	assert.ok(out.written.includes("domains/plant/extensions/visitor.llp"));
	assert.equal(readFileSync(join(into, "domains/plant/README.md"), "utf8"), "# plant, taken\n");
	assert.equal(out.fingerprint, catalog.fingerprint("plant", into));
	assert.throws(() => catalog.take("plant", src, {}, into), (e: any) => e instanceof catalog.CatalogError && /already/.test(e.message));
	// readmeFromRun: the run directory's seed (loop.sh --seed writes seed.json) in the README
	const run = mkdtempSync(join(tmpdir(), "catalog-ts-run-"));
	cpSync(src, join(run, "catalog"), { recursive: true });
	execFileSync("rm", ["-f", join(run, "catalog/domains/dog/README.md")]);
	execFileSync(PY, ["-c", `import json,sys; json.dump({"seed": "domains/dog/dog.llp"}, open(sys.argv[1], "w"))`, join(run, "seed.json")]);
	catalog.take("dog", join(run, "catalog"), { readmeFromRun: run }, into);
	assert.match(readFileSync(join(into, "domains/dog/README.md"), "utf8"), /seeded from `domains\/dog\/dog\.llp`/);
	assert.match(catalog.build("plant", into), /plant\.metis/);
	assert.ok(existsSync(join(into, "domains/plant/build/plant.metis")));
});

test("apply's readme, host and corpus; readme() and ts() — py's plan/apply keywords, one for one", () => {
	const r = scratch();
	const w = { readme: "# plant, by hand\n", host: "# the plant's host, again\n", corpus: "water it\tWATER\n" };
	assert.deepEqual(catalog.plan("plant", w, r).map((f) => f.path),
		["domains/plant/README.md", "domains/plant/intent/plant-corpus.tsv", "domains/plant/plant_host.py"]);
	catalog.apply("plant", w, r);                                                      // three texts: stdin and two files
	assert.equal(readFileSync(join(r, "domains/plant/README.md"), "utf8"), w.readme);
	assert.equal(readFileSync(join(r, "domains/plant/plant_host.py"), "utf8"), w.host);
	assert.equal(readFileSync(join(r, "domains/plant/intent/plant-corpus.tsv"), "utf8"), w.corpus);
	assert.equal(catalog.readme("plant", r), py(r, "readme", "plant").readme);
	const run = mkdtempSync(join(tmpdir(), "catalog-ts-run-"));
	execFileSync(PY, ["-c", `import json,sys; json.dump({"seed": "domains/fiction/x.llp"}, open(sys.argv[1], "w"))`, join(run, "seed.json")]);
	assert.equal(catalog.readme("plant", r, run), py(r, "readme", "plant", "--run", run).readme);
	assert.match(catalog.readme("plant", r, run), /seeded from `domains\/fiction\/x\.llp`/);
	assert.deepEqual(catalog.ts(), py(r, "ts"));
	assert.ok(existsSync(join(catalog.ts().dir, "catalog.ts")));
});

test("the SDK's refusals throw as CatalogError, with its words", () => {
	const r = scratch();
	assert.throws(() => catalog.get("nosuch", r), (e: any) => e instanceof catalog.CatalogError && e.verb === "get" && /nosuch/.test(e.message));
	assert.throws(() => catalog.plan("dog", { manifest: { colour: "brown" } }, r), /unknown key/);
	assert.throws(() => catalog.plan("dog", { intents: "x: 1\n", intentsSkeleton: true }, r), /not both/);
	assert.throws(() => catalog.take("dog", r, { readme: "x", readmeFromRun: r }, r), /not both/);
	// a manifest host out of its domain (review R1): take would write another domain's file
	const into = mkdtempSync(join(tmpdir(), "catalog-ts-into-"));
	mkdirSync(join(into, "domains"));
	const mf = join(r, "domains/plant/domain.yaml");
	writeFileSync(mf, readFileSync(mf, "utf8").replace("host: plant_host.py:make", "host: ../dog/victim.py:make"));
	assert.throws(() => catalog.planTake("plant", r, {}, into), /not beside its domain\.yaml/);
});

// loop-fixes s-855d8067: edit, since, display/line, the README's parts, the skeleton of a world with no commands
const HAS_METISC = (() => {
	try {
		return !!JSON.parse(execFileSync(PY, ["-c", "import json; from metis_loop_sdk import catalog; print(json.dumps(catalog.metisc()))"], { encoding: "utf8" }));
	} catch {
		return false;
	}
})();

if (!HAS_METISC && process.env.METIS_LOOP_REQUIRE_METISC) throw new Error("METIS_LOOP_REQUIRE_METISC: no metisc");
test("edit: one exact edit, its diff and since_diff; the refusals", { skip: !HAS_METISC && "no metisc" }, () => {
	const r = scratch();
	const e = { path: "plant.llp", old_string: "% Made in the loop console (new).", new_string: "% Made in the loop console." };
	const planned = catalog.planEdit("plant", e, r);
	assert.deepEqual(planned.map((f) => f.path), ["domains/plant/plant.llp"]);
	assert.deepEqual(planned, py(r, "edit", "plant", "plant.llp", "--old", w(e.old_string), "--new", w(e.new_string), "--dry-run").files);
	const refused = planned[0].text.replace("console.", "console, refused.");
	const again = catalog.planEdit("plant", e, r, { since: { "domains/plant/plant.llp": refused } });
	assert.match(again[0].since_diff!, /^-% Made in the loop console, refused\./m);
	assert.match(again[0].since_diff!, /^\+% Made in the loop console\. Say/m);
	assert.match(readFileSync(join(r, "domains/plant/plant.llp"), "utf8"), /\(new\)/);       // a plan writes nothing
	assert.deepEqual(catalog.edit("plant", e, r).written, ["domains/plant/plant.llp"]);
	assert.equal(readFileSync(join(r, "domains/plant/plant.llp"), "utf8"), planned[0].text);
	assert.throws(() => catalog.edit("plant", e, r), (x: any) => x instanceof catalog.CatalogError && /not in it/.test(x.message));
	assert.throws(() => catalog.planEdit("plant", { path: "plant.llp", old_string: "pred", new_string: "PRED" }, r), /occurs \d+ times/);
	assert.equal(catalog.planEdit("plant", { path: "plant.llp", old_string: "sun", new_string: "light", replace_all: true }, r).length, 1);
	assert.throws(() => catalog.planEdit("plant", { path: "plant.llp", old_string: "moist", new_string: "wet", replace_all: true }, r),
		/extensions\/visitor\.llp: error pred-undeclared/);                                // its extension, against the edited program
	assert.throws(() => catalog.planEdit("plant", { path: "../dog/dog.llp", old_string: "a", new_string: "b" }, r), /not inside/);
	const rule = readFileSync(join(r, "domains/plant/plant.llp"), "utf8").split("\n").find((l) => l.includes(" -o moist"))!;
	assert.throws(() => catalog.planEdit("plant", { path: "plant.llp", old_string: rule, new_string: rule.replace("-o moist", "-o moistt") }, r),
		/adds 1 diagnostic[^]*moistt/);
	// the README, through the same edit
	const rd = catalog.edit("plant", { path: "README.md", old_string: "plant", new_string: "Plant", replace_all: true }, r);
	assert.deepEqual(rd.written, ["domains/plant/README.md"]);
});

// a text in a file, for the py CLI's --old/--new
function w(t: string): string {
	const f = join(mkdtempSync(join(tmpdir(), "catalog-ts-w-")), "t");
	writeFileSync(f, t);
	return f;
}

test("since on plan and planTake; display and line; a plan's text", () => {
	const r = scratch();
	const rd = "# plant\n\nOne.\nTwo.\n";
	const [f] = catalog.plan("plant", { readme: rd }, r, { since: { "domains/plant/README.md": "# plant\n\nOne.\nTwi.\n" } });
	assert.equal(f.text, rd);
	assert.match(f.since_diff!, /^-Twi\.$/m);
	assert.equal(catalog.plan("plant", { readme: rd }, r)[0].since_diff, undefined);
	const into = mkdtempSync(join(tmpdir(), "catalog-ts-into-"));
	mkdirSync(join(into, "domains"));
	cpSync(join(r, "tools"), join(into, "tools"), { recursive: true });            // plant's intents are generated there
	const t = catalog.planTake("plant", r, { readme: rd }, into, { since: { "domains/plant/README.md": "# plant\n" } });
	assert.match(t.find((x) => x.path === "domains/plant/README.md")!.since_diff!, /^\+Two\.$/m);
	const m = catalog.plan("plant", { display: "-the plant", line: "a potted plant: it dries out" }, r);
	assert.deepEqual(m.map((x) => x.path), ["domains/plant/domain.yaml"]);
	assert.match(m[0].text, /^display: -the plant$/m);
	assert.match(m[0].text, /^line: 'a potted plant: it dries out'$/m);
	catalog.apply("plant", { line: "dries out" }, r);
	assert.equal(catalog.get("plant", r).line, "dries out");
	assert.throws(() => catalog.plan("plant", { line: "two\nlines" }, r), /one line/);
});

test("readme(): the mechanical parts from the SDK, the model's summary and title; a world with no commands", () => {
	const r = scratch();
	const quiet = "% a quiet world\ncatalog quiet 1.\npred a : w.\npred b : w.\nstage s {\n  %% a becomes b.\n  ab [w] : a -o b.\n}\n#init a 1\n";
	catalog.apply("quiet", { program: quiet }, r);
	assert.deepEqual(catalog.commands("quiet", r), []);
	assert.deepEqual(catalog.commands("plant", r), py(r, "intents", "plant", "--skeleton").commands);
	assert.equal(catalog.skeleton("quiet", r), null);                                    // the default: no intent.yaml
	const text = catalog.readme("quiet", { from: r, summary: "An a becomes a b.", title: "-a quiet world" });
	assert.equal(text, py(r, "readme", "quiet", "--summary", w("An a becomes a b."), "--title=-a quiet world").readme);
	assert.match(text, /^# quiet — -a quiet world\n\nAn a becomes a b\.\n/);
	assert.match(text, /```text\n% a quiet world\n```/);
	assert.match(text, /`metisc --run quiet\.llp` runs the case its `#` lines give:\n\n```text\n#init a 1\n```/);
	assert.equal(catalog.readme("plant", r), catalog.readme("plant", { from: r }));
});
