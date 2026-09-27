# Metis through the REPL — three worlds

A working tour of the language and its semantics, driven entirely
from `metis-loop repl`. Every transcript below was executed; every
number is exact. Start it with the metispy env active:

    PYTHONPATH=path/to/metispy metis-loop repl        # or: python -m loop.cli repl

One idea carries the whole system: **a catalog is one program read
three ways** — proof theory (typing, admission, canonical identity),
derivations (traces: the futures themselves), and denotation (the
exact probability measure over those futures). The REPL exposes all
three: `:gate` is the proof-theory reading, `:trace` the derivation
reading, `:marginals`/`:map` the measure reading. They can never
disagree, because they are readings of the same object.

---

## World 1 — a coin and a market (resources, stages, packs)

The smallest complete catalog (`metis-lang/corpus/packbase.llp`).
It introduces the three primitives everything else builds on: linear
rules, stages with quiescence, and weight ports.

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

    μ> :init coin=1,mkt=1
    μ> :steps 4
    μ> :text <<EOF
    %% a coin is flipped once; it lands heads or tails.
    EOF
    μ> :llp <<EOF   (the catalog above)
    ...
    μ> :gate
    { ok: true, classification: "class-F candidate …",
      rules: [[h, "heads branch."], [t, "tails branch."], …],
      scenarios: [{ key: "060bc3b3…", support: 2, … }] }
    μ> :accept

**`:gate` is the proof-theory reading.** Parse, roundtrip
(`parse(pretty(a)) = a` — the catalog IS its own presentation),
typecheck, and the canonical `program_key` (`060bc3…`) — the same
key any toolchain (python, OCaml `metisc`) computes for this ground
program. Identity is semantic, not textual: rename variables,
reorder rules, split files with `include` — the key is unchanged.

    μ> :trace 1
    { events: ["roll/t", "roll/rn"], final: {mkt:1, tails:1} }
    μ> :trace 3
    { events: ["roll/h", "roll/rn"], final: {heads:1, mkt:1} }
    μ> :marginals heads tails
    { support: 2, marginals: {heads: 0.5, tails: 0.5} }
    μ> :map
    { prob: 0.5, events: ["roll/h", "roll/rn", "(quiesce)", …] }

**`:trace` samples ONE future; `:marginals` prices them ALL.** The
trace is seeded and portable — the same seed gives the same
trajectory in the python and C++ samplers. The marginals are not
sampling: they are the exact measure, every reachable future
weighted and summed (`support: 2` — this world has two futures).
Ceptre, the ancestor system, could only run traces; metis prices
them: that is the denotational reading. `:map` is the third readout
on the same object — the single most probable derivation.

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

    μ> :gate      (against the accepted world)
    { ok: true, … }
    μ> :accept
    μ> :marginals seen unseen
    { marginals: {seen: 0.5, unseen: 0.5} }

**`$` reads without consuming; containment does the rest.**
`$heads` is a persist premise. What the pack may NOT do is produce
or consume base atoms — that is **containment admission**, the type
system rather than a lint. Try it: change `obs` to produce `heads`
and `:gate` answers `layer 'pack' may not produce 'heads'
(namespace 'st')`. Packs observe and constrain; they can never
enable base behavior. This is what makes learned and formalized
extensions safe by construction.

---

## World 2 — the love triangle (grounding, multiplicity, plot)

The Ceptre lineage: Martens' A-Midsummer-Night's-Dream tutorial
program, ported rule-for-rule (`metis-catalog/domains/fiction/
love_triangle.llp`, the original `.cep` committed beside it). It
introduces first-order rules, grounding, and the pricing of
multiplicity — on a story instead of a machine.

    stage go {
      %% A loves B while C loves A: the rival C seethes at beloved
      %% and rival both.
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

    μ> :init eros(helena,hermia)=1,eros(hermia,helena)=1,eros(helena,lysander)=1,eros(lysander,hermia)=1
    μ> :steps 1
    μ> :load metis-catalog/domains/fiction/love_triangle.llp
    μ> :gate
    { ok: true, classification: "counterexample: jealousy[A=helena,
      B=helena,C=hermia]: multiplicity 2 …", … }
    μ> :accept
    μ> :trace 5
    { events: ["go/jealousy[A=lysander,B=hermia,C=helena]"], … }
    μ> :trace 9
    { events: ["go/jealousy[A=helena,B=lysander,C=hermia]"], … }

**Trace labels carry the substitution.** Every event names its rule
AND its cast — the derivation reading stays legible after
grounding. (The `:load` verb splices `include`s; the canonical key
is invariant under file splits, so loading the one-file or the
split form is the same program.)

    μ> :marginals anger(hermia,helena) anger(hermia,hermia)
    { support: 5, marginals: {anger(hermia,helena): 0.4,
                              anger(hermia,hermia): 0.2} }

**Multiplicity is priced, not merely possible.** Five ground events
are enabled in act one; at parity weights each fires 1/5. The 0.4
is 2/5 because TWO distinct instantiations produce that same atom —
the falling-factorial semantics counts token-level instances,
bit-exactly the choice rule of the original interpreter (Theorem 1).
Where the origin could sample and eyeball, metis states P = 2/5 as
a theorem about the same program. The same pricing runs through
`move_on`: its triple premise on a count-3 atom is 3! = 6
transition tokens, and the measure charges all six.

    μ> :map
    { prob: 0.2, events: ["go/jealousy[A=helena,B=hermia,C=hermia]"], … }

**`:map` is the modal derivation — in a story domain, the most
probable plot.** And the gate's classification line
("counterexample: … multiplicity 2") is the factored-statics report
being honest: this program is exact-filter territory, not
clique-tree territory; nothing is rejected, the boundary is named.
The origin's `#interactive` (a human picks the next step) maps to
the policy hook: the same measure, reweighted — inference stays
exact under direction.

---

## World 3 — the road handles (guards, ports, decisions)

The production encoding pattern, on the corpus fixture
(`metis-catalog/scenes/road_close_instance.llp`, an instance that
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

The session:

    μ> :init emvt=1,cmd(keep)=1,gclose=1,on(ego,l2)=1,on(alfa,l2)=1
    μ> :steps 6
    μ> :load metis-catalog/scenes/road_close_instance.llp
    μ> :gate
    { ok: true, classification: "class-F candidate …",
      rules: [[mkeep, "hold the lane."], [mleft, "…"], …] }
    μ> :accept
    μ> :marginals crash gclose gsafe
    { support: 3, marginals: {crash: 0.25, gclose: 0.5, gsafe: 0.5} }
    μ> :map
    { prob: 0.5, events: ["ego/mkeep", "ego/ew", "world/abo",
                          "world/wc", "check/ok", "check/cb"], … }

**The stages ARE the tick, and `:map` narrates it.** Ego commits a
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

- **`:gate` + `:accept` — a pack.** Only adds, containment-checked;
  base state readable via `$`, never producible or consumable
  without an explicit namespace grant.
- **`:revise` + `:accept` — a base edit.** The candidate replaces
  the world; accepted packs drop (re-propose them), the key moves,
  and the before/after exact measure diff on the current scene is
  printed — the consistency instrument.

From here: `:formalize CMD` puts a model in the drafting seat with
the gates as referee (the loop), and `:save` writes the world out.
The same worlds, keys and numbers appear in the Loop Console and in
the metis-catalog corpus gates — one program, three readings, every
surface a wrapper.
