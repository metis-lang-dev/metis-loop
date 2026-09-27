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

The smallest complete catalog (`metis-lang/corpus/packbase.llp`):

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

`:gate` is the proof-theory reading: parse, roundtrip
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

`:trace` samples ONE future (seeded, portable — the same seed gives
the same trajectory in the python and C++ samplers). `:marginals` is
not sampling: it is the **exact measure**, every reachable future
weighted and summed (support: 2 — this world has two futures).
Ceptre, the ancestor system, could only run traces; metis prices
them: that is the denotational reading.

**Now the market — a pack** (`packmark.llp`):

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

`$heads` is a **persist premise**: read without consuming. And note
what the pack may NOT do: produce or consume base atoms. That is
**containment admission** — the type system, not a lint. Try it:
change `obs` to produce `heads` and `:gate` answers
`layer 'pack' may not produce 'heads' (namespace 'st')`. Packs
observe and constrain; they can never enable base behavior. This is
what makes learned/formalized extensions safe by construction.

---

## World 2 — the love triangle (grounding, multiplicity, plot)

The Ceptre lineage: Martens' A-Midsummer-Night's-Dream tutorial
program, ported rule-for-rule (`metis-catalog/domains/fiction/
love_triangle.llp`, with the original `.cep` beside it).

    μ> :init eros(helena,hermia)=1,eros(hermia,helena)=1,eros(helena,lysander)=1,eros(lysander,hermia)=1
    μ> :steps 1
    μ> :load metis-catalog/domains/fiction/love_triangle.llp
    μ> :gate
    { ok: true, classification: "counterexample: jealousy[A=helena,
      B=helena,C=hermia]: multiplicity 2 …", … }
    μ> :accept

Two new things. First, rules here are **first-order schemas**:
`jealousy` speaks of any lovers A, B, C with distinctness (`<>`)
guards — and grounding instantiates them over the declared cast.
Trace labels show the substitution explicitly:

    μ> :trace 5
    { events: ["go/jealousy[A=lysander,B=hermia,C=helena]"], … }
    μ> :trace 9
    { events: ["go/jealousy[A=helena,B=lysander,C=hermia]"], … }

Second, **multiplicity is priced, not merely possible**. The exact
measure over act one:

    μ> :marginals anger(hermia,helena) anger(hermia,hermia)
    { support: 5, marginals: {anger(hermia,helena): 0.4,
                              anger(hermia,hermia): 0.2} }

Five ground events are enabled; at parity weights each fires 1/5.
The 0.4 is 2/5 because TWO distinct instantiations produce that
same atom — the falling-factorial semantics counts token-level
instances, which is bit-exactly the choice rule of the original
interpreter (Theorem 1). Where the origin could sample and eyeball,
metis states P = 2/5 as a theorem about the same program.

    μ> :map
    { prob: 0.2, events: ["go/jealousy[A=helena,B=hermia,C=hermia]"], … }

`:map` is the Viterbi reading: the modal derivation — in a story
domain, the most probable plot. The gate's classification line
("counterexample: … multiplicity 2") is the factored-statics report
being honest: this program is exact-filter territory, not
clique-tree territory; nothing is rejected, the boundary is named.

The origin's `#interactive` (a human picks the next step) maps to
the policy hook: the same measure, reweighted — inference stays
exact under direction.

---

## World 3 — the road handles (guards, ports, decisions)

The production encoding pattern, on the corpus fixture
(`metis-catalog/scenes/road_close_instance.llp` — an INSTANCE that
`include`s the handles domain; `:load` splices includes and the
canonical key is invariant under the split).

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

What this world adds:

- **Horn guards** prune instantiations at ground time (lane
  adjacency is derived, not enumerated).
- **Ports with `reads` contracts** (`rss`, gap classes): the
  continuous world enters ONLY through declared, scope-checked
  ports — which is exactly what makes the encoding factorizable
  (class-F) and therefore IR-compilable for the vehicle runtime.
- **The tick as stages**: the MAP narrates it — ego commits a
  command, the world moves, the check stage prices the outcome.
  `crash: 0.25` under `keep` behind a close lead IS the decision
  input: the planner scores candidate commands by exactly these
  hazard marginals, lexicographically (safety, then progress).
- **The surprise doctrine**: at runtime the same program scores each
  observed transition; likelihood 0 means no rule covers what
  happened — the loop's trigger. A missing behavior is a missing
  rule, never a bad number.

---

## Changing a world: extension vs revision

Two verbs, two doctrines (SPEC.md §4):

- `:gate` + `:accept` — a PACK: only adds, containment-checked;
  base state readable via `$`, never producible or consumable
  without an explicit namespace grant.
- `:revise` + `:accept` — a BASE EDIT: the candidate replaces the
  world; accepted packs drop (re-propose them), the key moves, and
  the before/after exact measure diff on the current scene is
  printed — the consistency instrument.

From here: `:formalize CMD` puts a model in the drafting seat with
the gates as referee (the loop), and `:save` writes the world out.
The same worlds, keys and numbers appear in the Loop Console and in
the metis-catalog corpus gates — one program, three readings,
every surface a wrapper.
