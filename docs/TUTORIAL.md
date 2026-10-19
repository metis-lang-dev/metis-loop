# Metis through the REPL — three worlds

A working tour of the language and its semantics, driven entirely
from the metis shell — the ONE kernel REPL (SPEC.md §2): the loop
merged into it on 2026-10-01, and every UI is a wrapper over it.
Every transcript below was executed; every number is exact. With
metispy installed (`pip install -e .` into the shared env):

    metis FILE.llp          # the shell: serve a catalog, drive it
    metis --json FILE.llp   # the wire: {op, arg} JSON lines, one
                            # result per line — what every UI wraps

The prompt is `llp> `, with line editing, history and tab-completed
commands. Commands are bare words — `help` lists them; `events`
shows what can fire. The scene comes from the file's `#`-directive
lines (metis-lang spec §8), and a `#init ATOM N` / `#steps N` line
typed at the prompt applies to the live session — the file syntax
IS the shell syntax.

One idea carries the whole system: **a catalog is one program read
three ways** — proof theory (typing, admission, canonical identity),
derivations (traces: the futures themselves), and denotation (the
exact probability measure over those futures). The shell exposes all
three: `gate` is the proof-theory reading, `trace`/`step`/`run` the
derivation reading, `query`/`map` the measure reading. They can
never disagree, because they are readings of the same object.

---

## World 1 — a coin and a market (resources, stages, packs)

The smallest complete catalog (`metis-lang/corpus/packbase.llp`),
served with its scene pinned by directives. It introduces the three
primitives everything else builds on: linear rules, stages with
quiescence, and weight ports.

    catalog packbase 1.
    layers (dyn pack).
    stages (roll note).
    namespace st produce (dyn).
    pred coin : st.   pred heads : st.   pred tails : st.
    weight ph reads {}.
    stage roll {
      %% heads branch.
      h [dyn] : coin -o heads  @w ph.
      %% tails branch.
      t [dyn] : coin -o tails  @w ~ph.
    }
    %% roll committed -> note stage.
    qui rn [dyn] : roll -o note.
    #init coin 1
    #init mkt 1
    #steps 4

**Read `-o` as spending.** `coin -o heads` is a linear-logic lolli:
firing it CONSUMES one `coin` and PRODUCES one `heads`. State is a
multiset of resources, not a set of facts — this is why metis needs
no frame axioms and no `retract`: what a rule doesn't mention, it
doesn't touch; what it consumes is gone. A world where things are
used up, held, and handed over (fuel, tokens, attention, right of
way) is modeled by writing exactly that.

**Stages sequence the drama.** Rules live in stages; the `qui` link
fires only at *quiescence* — when no rule in the stage can fire any
more. So `roll` runs until settled, then control passes to `note`.
Termination is not a counter; it is the world running out of moves.

**Weights are ports, not numbers.** `@w ph` prices the heads branch
by the port `ph`; `~ph` is its complement. Unbound (as here), ports
evaluate in prior mode — a deliberate doctrine called *structure
from text, numbers from data*: rules commit to structure, weights
arrive later from a registry (runtime geometry) or from notching
(learning). Nothing in a catalog is a made-up probability.

The session:

    $ metis world1.llp
    metis shell — world1.llp (catalog packbase, key 060bc3b3d218…)
    stage roll | coin:1 mkt:1
    llp> events
      1. h  w=1  p=0.5
      2. t  w=1  p=0.5
    llp> query heads
    P[heads present after 4 steps] = 0.5
    llp> map
    map p=0.5
      1 | roll/h
      2 | roll/rn
      3 | (quiesce)
      4 | (quiesce)
    final (done)
      heads  ·
      mkt    ·
    llp> run 4
    t rn
    stage (done) | mkt:1 tails:1

**The key in the banner is the proof-theory reading.** Serving the
file parses, typechecks and computes the canonical `program_key`
(`060bc3…`) — the same key any toolchain (python, OCaml `metisc`)
computes for this ground program. Identity is semantic, not
textual: rename variables, reorder rules, split files with
`include` — the key is unchanged (and `parse(pretty(a)) = a`: the
catalog IS its own presentation).

**`run` samples ONE future; `query` prices them ALL.** `step` fires
one event (by number or name, or sampled); `run N` walks on the
seeded reference sampler — the same seed gives the same trajectory
in the python and C++ samplers; `undo` takes it back, `reset`
returns to the file's `#init`. The `query` answer is not sampling:
it is the exact measure, every reachable future weighted and summed
(this world has two). Ceptre, the ancestor system, could only run
traces; metis prices them: that is the denotational reading. `map`
is the third readout on the same object — the single most probable
derivation.

**A pack extends the world without touching it**
(`metis-lang/corpus/packmark.llp`):

    catalog packmark 1.
    extends packbase.
    namespace mk produce (pack).
    pred mkt : mk.   pred seen : mk.   pred unseen : mk.
    stage note {
      %% pack observes heads: reads base state, writes only its own.
      obs [pack] : mkt * $heads -o seen.
      %% pack observes tails: the complement observation.
      obt [pack] : mkt * $tails -o unseen.
    }

This is the loop half of the shell — text, candidate, gates, world:

    llp> text <<EOF
    %% a market note observes the coin outcome.
    EOF
    llp> load metis-lang/corpus/packmark.llp
    { ok: true, lines: 14 }
    llp> gate
    { ok: true,
      classification: "class-F candidate (statics admit; Z-check applies with bindings)",
      findings: [],
      rules: [[obs, "pack observes heads: …"], [obt, "…"]],
      scenarios: [{ key: "e486d08e4318…", support: 2,
                    diffs: [[mkt, 1, 0], [seen, 0, 0.5], [unseen, 0, 0.5]] }] }
    llp> accept
    { ok: true, accepted_packs: 1, key: "e486d08e4318…" }
    llp> query seen
    P[seen present after 4 steps] = 0.5

**`accept` re-serves the merged world LIVE.** The key moved
(`060bc3…` → `e486d0…`): the session is now playing the extended
world — new events, same counts, no restart. The gate report
already priced the change before it happened: the scenario `diffs`
are exact before/after marginals (`mkt` 1→0 because the pack spends
it; `seen`/`unseen` split the coin's mass).

**`$` reads without consuming; containment does the rest.**
`$heads` is a persist premise. What the pack may NOT do is produce
or consume base atoms — that is **containment admission**, the type
system rather than a lint. Try it: change `obs` to also produce
`heads` and `gate` answers

    findings: ["pack/obs: layer 'pack' may not produce 'heads' (namespace 'st')"]

Packs observe and constrain; they can never enable base behavior.
This is what makes learned and formalized extensions safe by
construction.

---

## World 2 — the love triangle (grounding, multiplicity, plot)

The Ceptre lineage: Martens' A-Midsummer-Night's-Dream tutorial
program, ported rule-for-rule (`metis-catalog/domains/ceptre/love_triangle/
love_triangle.llp`, the original `.cep` committed beside it). It
introduces first-order rules, grounding, and the pricing of
multiplicity — on a story instead of a machine.

(Attribution: the two rules quoted below are from the Ceptre love
triangle, a port of interactive-lp's example, Copyright © 2023 Chris
Martens, under the Anti-Capitalist Software License v1.4, not this
repository's Apache-2.0 grant; see metis-catalog `domains/ceptre/README.md`.)

    stage go {
      %% A loves B while C loves A: C seethes at A and at B. B may be C
      %% (the origin's only neq is C<>A): requited love angers C at self.
      jealousy [story] : $eros(A,B) * $eros(C,A) * C <> A
        -o anger(C,A) * anger(C,B).
      %% three angers at the beloved and the love dies (multiplicity-3
      %% premise: 3!=6 transition tokens — the falling-factorial gate).
      move_on [story] : eros(A,B) * anger(A,B) * anger(A,B) * anger(A,B)
        -o one.
    }

**Rules are first-order schemas; grounding makes them concrete.**
`jealousy` speaks of any A, B, C; `C <> A` is the distinctness
guard (the original's hand-written `neq` fact table, now sugar);
`-o one` is the linear unit — produce nothing. Given a cast, the
Π-grounding instantiates every consistent substitution, and from
then on everything is the ground machinery of World 1.

The session:

    $ metis metis-catalog/domains/ceptre/love_triangle/love_triangle.llp
    metis shell — love_triangle.llp (catalog love-triangle, key e648d2c47888…)
    stage go | eros(helena,hermia):1 eros(helena,lysander):1
               eros(hermia,helena):1 eros(lysander,hermia):1
    llp> events
      1. jealousy[A=hermia,B=helena,C=helena]    w=1  p=0.2
      2. jealousy[A=lysander,B=hermia,C=helena]  w=1  p=0.2
      3. jealousy[A=helena,B=hermia,C=hermia]    w=1  p=0.2
      4. jealousy[A=helena,B=lysander,C=hermia]  w=1  p=0.2
      5. jealousy[A=hermia,B=helena,C=lysander]  w=1  p=0.2

**The file brought its own scene.** The catalog carries the
origin's `context init` and `#trace` as `#`-directive lines
(metis-lang spec §8) — compiler-invisible, interpreter-visible —
so serving the file IS setting the stage; a committed catalog's
leading comment block is likewise its TEXT (the approved unit).
**Event labels carry the substitution:** every enabled transition
names its rule AND its cast — the derivation reading stays legible
after grounding. (Includes are spliced on serve; the canonical key
is invariant under file splits, so the one-file and the split form
are the same program.)

    llp> query anger(hermia,helena) 1
    P[anger(hermia,helena) present after 1 steps] = 0.4
    llp> query anger(hermia,hermia) 1
    P[anger(hermia,hermia) present after 1 steps] = 0.2

**Multiplicity is priced, not merely possible.** Five ground events
are enabled in act one; at parity weights each fires 1/5. The 0.4
is 2/5 because TWO distinct instantiations produce that same atom —
the falling-factorial semantics counts token-level instances,
bit-exactly the choice rule of the original interpreter (Theorem 1).
Where the origin could sample and eyeball, metis states P = 2/5 as
a theorem about the same program. The same pricing runs through
`move_on`: its triple premise on a count-3 atom is 3! = 6
transition tokens, and the measure charges all six.

    llp> trace
    case love_triangle steps=6 seeds=3
    I eros(helena,hermia) 1
    …
    T 1 — 6 events, 4 beats
      1 | jealousy [A=helena,B=hermia,C=hermia]
        | jealousy [A=hermia,B=helena,C=lysander]
      2 | jealousy [A=helena,B=lysander,C=hermia]
        | jealousy [A=hermia,B=helena,C=lysander]
      3 | jealousy [A=helena,B=hermia,C=hermia]
      4 | move_on  [A=hermia,B=helena]
    F 1 go
      anger  (hermia,hermia):2 (hermia,lysander) (lysander,helena):2
             (lysander,hermia):2
      eros   (helena,hermia) (helena,lysander) (lysander,hermia)
    …
    Q anger(hermia,helena) 1/3 exact=0.718202

**`trace` replays the file's embedded `#`-case (= `metisc --run`),
rendered as Foata beats.** Lines sharing a beat number fired
INDEPENDENTLY — no shared resources, any order, same world; the
indented continuation lines are the concurrency being shown, not
hidden. Final states print as predicate tables; a `#query`
directive closes with sampled-vs-exact agreement. Session state is
untouched — `trace` is an instrument, not a move. The origin's
`#interactive` (a human picks the next step) is the `step`-by-menu
you already have — the same measure, reweighted; inference stays
exact under direction.

---

## World 3 — the road handles (guards, ports, decisions)

The production encoding pattern, on the corpus fixture
(`metis-catalog/domains/road/scenes/road_close_instance.llp`, an instance that
`include`s the handles domain). It introduces Horn guards,
reads-scoped ports, and the tick — the shape the vehicle runtime
actually serves.

    stages (ego world check).
    weight rss reads {gclose, on(ego,L) if islane(L),
                      on(alfa,L) if islane(L)}.
    stage check {
      %% same lane and close at decision time: the hazard fires with
      %% the rss-priced probability (the port reads gap + lane
      %% occupancy and the GEOMETRY behind the handles).
      hit [dyn] : ck * $gclose * $on(ego,L) * $on(alfa,L)
        -o crash * ckd  @w rss.
      %% the tick passes clean (complement mass of the same port).
      ok [dyn] : ck -o ckd  @w ~rss.
    }

**Horn guards prune at ground time.** `if islane(L)` is
backward-chaining: lane adjacency is derived, not enumerated, and
impossible instantiations never enter the program.

**Ports carry the continuous world — under contract.** The `reads`
clause declares exactly which atoms the `rss` binding may consult;
the geometry (real gaps, speeds) stays behind the port. This is not
style: the declared scope is what makes the encoding factorizable
(class-F) and therefore compilable to the IR artifact the vehicle
interprets. The measure lives on qualitative classes
(`gclose`/`gsafe`); exact quantities ride as metadata.

The session — the scene typed live, in directive syntax:

    $ metis metis-catalog/domains/road/scenes/road_close_instance.llp
    llp> #init emvt 1
    llp> #init cmd(keep) 1
    llp> #init gclose 1
    llp> #init on(ego,l2) 1
    llp> #init on(alfa,l2) 1
    llp> #steps 6
    llp> query crash
    P[crash present after 6 steps] = 0.25
    llp> map
    map p=0.5
      1 | ego/mkeep
      2 | ego/ew
      3 | world/abo
      4 | world/wc
      5 | check/ok
      6 | check/cb
    final ego
      cmd    (keep)
      emvt   ·
      gsafe  ·
      on     (alfa,l2) (ego,l2)

**The stages ARE the tick, and `map` narrates it.** Ego commits a
command, the world moves, the check stage prices the outcome — read
the MAP events left to right and that is the tick pipeline.
`crash: 0.25` under `keep` behind a close lead IS the decision
input: the planner scores candidate commands by exactly these
hazard marginals, lexicographically (safety, then progress). A
decision is explained by the same numbers that made it.

**The same program scores what actually happens.** At runtime each
observed transition is evaluated against the measure; likelihood 0
means no rule covers it — the surprise record that triggers the
loop. A missing behavior is a missing rule, never a bad number.

---

## Changing a world: extension vs revision

Two verbs, two doctrines (SPEC.md §4):

- **`gate` + `accept` — a pack.** Only adds, containment-checked;
  base state readable via `$`, never producible or consumable
  without an explicit namespace grant. `accept` re-serves the
  merged world live.
- **`revise` + `accept` — a base edit.** The candidate replaces
  the world; accepted packs drop (re-propose them), the key moves,
  and the before/after exact measure diff on the current scene is
  printed — the consistency instrument. Tabula rasa = serve a
  blank catalog and `revise` it.

Rule text is never REPL input: edit the file, `save` the session's
scene back as directives, `reload` (alias `edit`) to recompile with
state carried over — degrade-to-last-good if the edit is broken.

---

## Closing the loop — a surprise becomes a rule

The whole improvement cycle, in one session (SPEC.md §1): the
runtime logged an outcome no rule covers — a shepherd's flock came
through a wolf night *safe*, and the meadow world cannot derive
`safe` at all. The sink holds the record; the session turns it into
an admitted pack and verifies the fix. The world, its sink and the
recorded session live in metis-catalog `demo/synthetic-meadow/`
(run from there; `meadow_plugin` binds the world's weight port `pk`
at 0.5 — an unbound port refuses to serve).

    $ metis --plugin meadow_plugin:make meadow.llp
    llp> sink runs/sink.jsonl
    { ok: true, records: [{idx: 0, kind: "unmodeled", likelihood: 0,
                           steps: 6, observed: {safe: 1}}] }
    llp> record 0
    { ok: true, kind: "unmodeled",
      init: {wolf: 1, sheep: 3, night: 2, tally: 2}, steps: 6 }
    llp> replay
    { ok: true, logged_likelihood: 0, likelihood: 0,
      explains: false, fixed: false }

**Likelihood 0 is structural.** No parameter can create missing
support — a missing behavior is a missing rule, never a bad number.
`record` adopted the record's tick as the scene (`#init`/`#steps`),
so every instrument now speaks about that tick.

    llp> mine
    { observed: {safe: 1}, hint: "state what happened that the world
      cannot derive; quote atoms; that text is the approved unit" }
    llp> mine %% the shepherd tallies the flock at rest: a fed wolf means a loss, a hungry one safety.
    llp> formalize
    (drafts via the llm endpoint — `llm` shows, sets AND validates
     it: for ollama it checks the server and whether the model is
     pulled. The metis dot file seeds it ($METIS_CONFIG |
     ./.metis.toml | ~/.config/metis/config.toml: [llm] endpoint,
     [ollama] host/model under $OLLAMA_HOST/$OLLAMA_MODEL);
     `anthropic[:MODEL]` or `command:ARGV` are the alternatives;
     findings feed back, <= 4 rounds. The doctrine split: narration
     runs local, formalization deserves the stronger model. Or
     write it yourself: `llp <<EOF`, or `load` it — here, the
     shepherd pack of World 1's shape.)
    llp> gate
    { ok: true, scenarios: [{ support: 5,
        diffs: [[loss, 0, 0.828125], [safe, 0, 0.390625],
                [tally, 1, 0]] }] }
    llp> accept
    { ok: true, accepted_packs: 1, key: "1cdc8c1a1072…" }
    llp> replay
    { ok: true, logged_likelihood: 0, likelihood: 0.21875,
      explains: true,
      explanation_events: ["catch", "evade", "hr", "n1", "n2"],
      fixed: true }

**`fixed: true` is the loop's success criterion**: the same record
that scored zero now carries positive mass, and the MAP explanation
narrates it — one catch, one evade, settle, then the tally rules
price the loss and the safety. The candidate never becomes the
world without `accept`, and nothing in the drafting seat can touch
the verdict: the model proposes, the gates dispose, the human
approves.

`export` writes the world out as files; `narrate` reads the session
back as prose (Foata beats + `%%` docs through the same llm
endpoint); `show` inspects the loop state; `version` says exactly
what is running (package, source + git, python, config, endpoint). The Loop Console shows
the same queue, reports and keys for the approval seat; the loop
bus runs N `metis --json` interpreters over one named pipe — one
program, three readings, every surface a wrapper over this shell.
