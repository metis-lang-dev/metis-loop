# metis transcript — base.llp

- opened 2026-10-10 12:36:54
- catalog wildfire, key fa0745b5fe3e9b8ff7ccad98942e54428efe810244311f10bc42deabfc740ddd
- llm seat: (default)
- plugin: wildfire_plugin:make (WildfirePorts)
- stage open, 0 fired

### system prompt `formalize` (in effect; source: builtin)

```text
You are a formalizer for LLP, a typed linear-logic behavior-catalog
language. Emit ONLY LLP source, no fences, no prose.
```

### system prompt `narrate` (in effect; source: builtin)

```text
You narrate one certified run of a linear-logic story engine. The
material has three parts: the run in beats, the final state, and
the rules. Use ONLY the material — never invent events, sentiments,
places or motives that are not in it.

How to read it: every event in the trace names a RULE, and that
rule's %% comment says what the event means — tell the event in the
%% comment's words. Events sharing one beat number are causally
INDEPENDENT: simultaneous, their listed order carries no
information — never imply sequence inside a beat; use "at the same
time"/"meanwhile" or one plural sentence. Order ACROSS beats is
real: "then"/"because" is licensed there. Aggregate repeated
similar events instead of enumerating them. Bindings name the
roles ([C=ann] means ann acts). Close from the final state.

Write a titled prose chronicle of the run (about 250-350 words),
then a short "narrator's note" (3-5 sentences) on how the beat
structure shaped the telling. No markdown lists.

Work exactly like these two examples.

== example 1, the material ==
== the run, in beats ==
T 1 — 4 events, 3 beats
  1 | build_straw
    | build_brick
  2 | blow_straw
  3 | blow_brick
== the final state ==
F 1 go
  brickhouse  ·
== the rules (with their approved doc comments) ==
stage go {
  %% a pig spends the straw on a straw house.
  build_straw [story] : pig * straw -o strawhouse.
  %% a pig spends the bricks on a brick house.
  build_brick [story] : pig * bricks -o brickhouse.
  %% the wolf blows the straw house down: the HOUSE is consumed, the
  %% wolf only $-read — he walks on to the next house.
  blow_straw [story] : $wolf * strawhouse -o ().
  %% the wolf huffs at the brick house: now the WOLF is consumed and
  %% the house only $-read — it stands, he is spent.
  blow_brick [story] : wolf * $brickhouse -o ().
}

== example 1, the narration ==
The Straw and the Brick

At the same time, two pigs built: one spent its straw on a straw
house, the other laid its bricks into a brick house. No order holds
between the two — they share a beat. Then the wolf blew the straw
house down; the house was consumed, and the wolf, in the rule's own
words, walked on to the next house. Then he huffed at the brick
house — and this time it was the wolf who was consumed while the
house stood: he was spent. The final state keeps exactly one atom,
and it is the brick house, still standing over the quiet that
remains.

Narrator's note: Beat 1 held two independent builds, so they are
told in one simultaneous sentence, and nothing in the telling
orders them. Beats 2 and 3 are consecutive, so "then" is licensed
twice. Who survives each blow is not fairy-tale memory: it is read
off the %% comments — the straw rule consumes the house, the brick
rule consumes the wolf.

== example 2, the material ==
== the run, in beats ==
T 2 — 6 events, 3 beats
  1 | catch
    | catch
    | evade
  2 | hr
  3 | n1
    | n1
    | n2
== the final state ==
F 2 rest
  fed     2
  hungry  ·
  loss    2
  safe    ·
== the rules (with their approved doc comments) ==
stage hunt {
  %% the wolf takes a sheep in the night and is fed.
  catch [dyn] : wolf * sheep * night -o wolf * fed  @w pk.
  %% the night passes; the wolf stays hungry.
  evade [dyn] : wolf * night -o wolf * hungry  @w ~pk.
}
%% the hunt settles into rest.
qui hr [dyn] : hunt -o rest.
stage rest {
  %% the shepherd counts a loss: a fed wolf means a sheep is gone.
  n1 [pack] : tally * $fed -o loss.
  %% the shepherd counts the flock safe: the wolf went hungry.
  n2 [pack] : tally * $hungry -o safe.
}

== example 2, the narration ==
Two Losses and a Mercy

The nights belonged to the wolf. Twice he took a sheep and was fed,
and once — in the same stretch of nights, no telling which came
first — the night passed and he stayed hungry. Then the hunt
settled into rest. Then the shepherd made his counts, all at once:
two losses, one for each night the wolf was fed, and one count of
safety for the night he went hungry. The final tally stands as the
ledger says: two fed, one hungry, two losses, one safe.

Narrator's note: The three hunt events share a beat, so the two
catches are aggregated into "twice" and the evade rides the same
simultaneous sentence. The quiescence link is the only "then" the
story needs — hunt, settle, count. The shepherd's verdicts quote
their own rules: a loss IS a fed wolf, safety IS a hungry one, and
the final state is the ledger the closing reads from.

The examples end here. Below is YOUR material — one run, the real
one. Narrate it the same way: one titled chronicle, one narrator's
note, and nothing else. Do not mention the examples.
```

## 2026-10-10 12:36:54 — `llm command:/home/axadmin/repo/perotheia-packages/metis-loop/experiments/wildfire/seat-claude.sh`

```text
llm: command:/home/axadmin/repo/perotheia-packages/metis-loop/experiments/wildfire/seat-claude.sh
```

_llm seat: command:/home/axadmin/repo/perotheia-packages/metis-loop/experiments/wildfire/seat-claude.sh_

## 2026-10-10 12:36:54 — `formalize system <<EOF`

heredoc:

```text
You are a formalizer for LLP, a typed linear-logic behavior-cataloglanguage. Emit ONLY LLP source: no fences, no prose, nothing else.If the world is BLANK, emit ONE standalone base catalog (no `extends`);otherwise emit a PACK over the base vocabulary you are shown (below).If the OBSERVED atoms in the text are not the base's vocabulary at all,a pack cannot explain them (it may not produce base atoms, and the basenever produces the observed ones): emit instead a revised standaloneBASE written in the observed vocabulary — it replaces the world.LLP syntax, exactly as shown (every declaration ends with "."; acomment line starts with "%"; a doc line starts with "%%"):catalog NAME 1.provenance text "WHAT IT FORMALIZES" "YYYY-MM-DD".layers (L ...).                       the rule layersstages (S ...).                       stage names, each defined belowtype T {c1 c2 c3}.                    a finite type (range: {n0..n4})namespace NS produce (L ...).         which layers may produce its atomspred p(T1, T2) : NS.                  a RESOURCE predicate (linear state)bwd q(T1, T2).                        a static (Horn) predicate ...q(c1, c2).                            ... and its factsstage S {  %% a doc line quoting the approved text: MANDATORY before every rule  name [L] : BODY -o HEAD.}%% a doc line (mandatory on links too)qui name [L] : S1 -o S2.              switch stage when S1 can fire nothing more#init ATOM N                          optional: an initial state (ground atoms)#steps NBODY is atoms joined by "*": a plain atom is CONSUMED, `$atom` is readand KEPT, a bwd atom is a static guard, `X <> Y` requires distinct.HEAD is atoms joined by "*", or `()` for nothing. `@w NUM` after thehead is the rule's relative choice weight among enabled rules(default 1); alternatives share one body: `-o (h1 @w 0.7 | h2 @w 0.3)`.Variables are Capitalized and take their types from the predicatesignatures; constants and all names are lowercase identifiers (letters,digits, `_` or `-`; no dots). Every predicate used must be declared.A complete, valid example (a toy, unrelated domain):catalog bakery 1.provenance text "a toy bakery" "2026-10-08".layers (dyn).stages (day night).type oven {o1 o2}.type grade {g0..g2}.namespace bk produce (dyn).pred dough : bk.pred loaf(grade) : bk.pred hot(oven) : bk.pred cold(oven) : bk.pred sold : bk.bwd next(grade, grade).next(g0, g1).next(g1, g2).stage day {  %% "an oven heats up"  heat [dyn] : cold(O) -o hot(O).  %% "a hot oven bakes dough into a plain loaf, and stays hot"  bake [dyn] : $hot(O) * dough -o loaf(g0) @w 3.  %% "a loaf is improved one grade, or spoiled"  finish [dyn] : loaf(G) * next(G, H) -o (loaf(H) @w 0.8 | () @w 0.2).  %% "two ovens cannot be the same oven"  swap [dyn] : hot(O) * cold(P) * O <> P -o cold(O) * hot(P).  %% "a top-grade loaf is sold"  sell [dyn] : loaf(g2) -o sold.}stage night {  %% "at night a hot oven cools"  cool [dyn] : hot(O) -o cold(O).}%% "when nothing more happens by day, night falls"qui dusk [dyn] : day -o night.#init dough 2#init cold(o1) 1#init cold(o2) 1#steps 8A PACK extends the base: it REUSES the base's types and predicates(never re-declares them — a type is only ever declared with itsconstants), may read and consume base atoms, declares its OWN newpredicates in its OWN namespace, and adds rules to the base's stages:catalog PACKNAME 1.extends BASENAME.provenance text "WHAT IT FORMALIZES" "YYYY-MM-DD".namespace NS2 produce (L ...).pred newp(T1) : NS2.                  only NEW predicates/types herestage S {                             a stage the base declares  %% doc quoting the approved text  name [L] : BODY -o HEAD.}A complete, valid pack over the bakery example above:catalog bakery-delivery 1.extends bakery.provenance text "a toy pack" "2026-10-09".namespace dl produce (dyn).pred van(oven) : dl.pred delivered(grade) : dl.
stage day {
  %% "a van at a hot oven takes a loaf away"
  load [dyn] : $van(O) * $hot(O) * loaf(G) -o delivered(G).
}

MODEL THE MECHANISM, NOT THE LEDGER. Never encode a number by
authoring-time computation: no per-value rule variants (r2/r5/r8
copies differing only in a count), no enumerated max/min pair facts,
no token multiplicities (consuming k copies of a token multiplies the
rule's weight by the number of ways to choose them, distorting the
measure). Make a quantity a PATH the world walks — `bwd` chain facts
like next(g0, g1) — and a rate DATA. A deterministic consequence of a
step goes in a settle stage whose rules must fire before the `qui`
link moves on. Do not invent rates or instance facts the text does
not give: use the default weight unless the text states a number;
where an instance is needed for `#init`, keep it small and say in a
`%` comment that it is illustrative.

WEIGHT PORTS — a rate that is DATA, supplied at serve time by a
binding (fitted from observations), never a number written in the
file. Declare the port with variable formals and its read scope
(`reads {}` when the rate depends only on its arguments), and
reference it from a complement pair of outcomes:

weight pbake(G) reads {}.             a port: the rate for grade G
stage day {
  %% "a loaf rises one grade at a rate that depends on its grade"
  rise [dyn] : loaf(G) * next(G, H) -o (loaf(H) @w pbake(G) | loaf(G) @w ~pbake(G)).
}

`@w f(X)` prices an outcome with the port's value, `@w ~f(X)` with one
minus it. One port per law: a rate that varies with a quantity takes
that quantity as its ARGUMENT (one rule, one port), never one rule
per value.
```

```text
formalize system prompt: session (5606 chars)
```

### system prompt `formalize` (changed; source: session)

```text
You are a formalizer for LLP, a typed linear-logic behavior-cataloglanguage. Emit ONLY LLP source: no fences, no prose, nothing else.If the world is BLANK, emit ONE standalone base catalog (no `extends`);otherwise emit a PACK over the base vocabulary you are shown (below).If the OBSERVED atoms in the text are not the base's vocabulary at all,a pack cannot explain them (it may not produce base atoms, and the basenever produces the observed ones): emit instead a revised standaloneBASE written in the observed vocabulary — it replaces the world.LLP syntax, exactly as shown (every declaration ends with "."; acomment line starts with "%"; a doc line starts with "%%"):catalog NAME 1.provenance text "WHAT IT FORMALIZES" "YYYY-MM-DD".layers (L ...).                       the rule layersstages (S ...).                       stage names, each defined belowtype T {c1 c2 c3}.                    a finite type (range: {n0..n4})namespace NS produce (L ...).         which layers may produce its atomspred p(T1, T2) : NS.                  a RESOURCE predicate (linear state)bwd q(T1, T2).                        a static (Horn) predicate ...q(c1, c2).                            ... and its factsstage S {  %% a doc line quoting the approved text: MANDATORY before every rule  name [L] : BODY -o HEAD.}%% a doc line (mandatory on links too)qui name [L] : S1 -o S2.              switch stage when S1 can fire nothing more#init ATOM N                          optional: an initial state (ground atoms)#steps NBODY is atoms joined by "*": a plain atom is CONSUMED, `$atom` is readand KEPT, a bwd atom is a static guard, `X <> Y` requires distinct.HEAD is atoms joined by "*", or `()` for nothing. `@w NUM` after thehead is the rule's relative choice weight among enabled rules(default 1); alternatives share one body: `-o (h1 @w 0.7 | h2 @w 0.3)`.Variables are Capitalized and take their types from the predicatesignatures; constants and all names are lowercase identifiers (letters,digits, `_` or `-`; no dots). Every predicate used must be declared.A complete, valid example (a toy, unrelated domain):catalog bakery 1.provenance text "a toy bakery" "2026-10-08".layers (dyn).stages (day night).type oven {o1 o2}.type grade {g0..g2}.namespace bk produce (dyn).pred dough : bk.pred loaf(grade) : bk.pred hot(oven) : bk.pred cold(oven) : bk.pred sold : bk.bwd next(grade, grade).next(g0, g1).next(g1, g2).stage day {  %% "an oven heats up"  heat [dyn] : cold(O) -o hot(O).  %% "a hot oven bakes dough into a plain loaf, and stays hot"  bake [dyn] : $hot(O) * dough -o loaf(g0) @w 3.  %% "a loaf is improved one grade, or spoiled"  finish [dyn] : loaf(G) * next(G, H) -o (loaf(H) @w 0.8 | () @w 0.2).  %% "two ovens cannot be the same oven"  swap [dyn] : hot(O) * cold(P) * O <> P -o cold(O) * hot(P).  %% "a top-grade loaf is sold"  sell [dyn] : loaf(g2) -o sold.}stage night {  %% "at night a hot oven cools"  cool [dyn] : hot(O) -o cold(O).}%% "when nothing more happens by day, night falls"qui dusk [dyn] : day -o night.#init dough 2#init cold(o1) 1#init cold(o2) 1#steps 8A PACK extends the base: it REUSES the base's types and predicates(never re-declares them — a type is only ever declared with itsconstants), may read and consume base atoms, declares its OWN newpredicates in its OWN namespace, and adds rules to the base's stages:catalog PACKNAME 1.extends BASENAME.provenance text "WHAT IT FORMALIZES" "YYYY-MM-DD".namespace NS2 produce (L ...).pred newp(T1) : NS2.                  only NEW predicates/types herestage S {                             a stage the base declares  %% doc quoting the approved text  name [L] : BODY -o HEAD.}A complete, valid pack over the bakery example above:catalog bakery-delivery 1.extends bakery.provenance text "a toy pack" "2026-10-09".namespace dl produce (dyn).pred van(oven) : dl.pred delivered(grade) : dl.
stage day {
  %% "a van at a hot oven takes a loaf away"
  load [dyn] : $van(O) * $hot(O) * loaf(G) -o delivered(G).
}

MODEL THE MECHANISM, NOT THE LEDGER. Never encode a number by
authoring-time computation: no per-value rule variants (r2/r5/r8
copies differing only in a count), no enumerated max/min pair facts,
no token multiplicities (consuming k copies of a token multiplies the
rule's weight by the number of ways to choose them, distorting the
measure). Make a quantity a PATH the world walks — `bwd` chain facts
like next(g0, g1) — and a rate DATA. A deterministic consequence of a
step goes in a settle stage whose rules must fire before the `qui`
link moves on. Do not invent rates or instance facts the text does
not give: use the default weight unless the text states a number;
where an instance is needed for `#init`, keep it small and say in a
`%` comment that it is illustrative.

WEIGHT PORTS — a rate that is DATA, supplied at serve time by a
binding (fitted from observations), never a number written in the
file. Declare the port with variable formals and its read scope
(`reads {}` when the rate depends only on its arguments), and
reference it from a complement pair of outcomes:

weight pbake(G) reads {}.             a port: the rate for grade G
stage day {
  %% "a loaf rises one grade at a rate that depends on its grade"
  rise [dyn] : loaf(G) * next(G, H) -o (loaf(H) @w pbake(G) | loaf(G) @w ~pbake(G)).
}

`@w f(X)` prices an outcome with the port's value, `@w ~f(X)` with one
minus it. One port per law: a rate that varies with a quantity takes
that quantity as its ARGUMENT (one rule, one port), never one rule
per value.
```

## 2026-10-10 12:36:54 — `sink sinks/iter0-transitions--iter1-world--frame-neg-tick.jsonl`

```text
{
 "ok": true,
 "file": "sinks/iter0-transitions--iter1-world--frame-neg-tick.jsonl",
 "records": [
  {
   "idx": 0,
   "kind": "rare",
   "likelihood": 0.005,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 0,
    "burning(x1,y3)": 0,
    "burning(x2,y1)": 0,
    "burning(x2,y2)": 0,
    "burning(x2,y3)": 0,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 1,
    "burning(x3,y3)": 0,
    "out_of_fuel(x1,y1)": 0,
    "out_of_fuel(x1,y2)": 0,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 0,
    "out_of_fuel(x2,y2)": 0,
    "out_of_fuel(x2,y3)": 0,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 0,
    "out_of_fuel(x3,y3)": 0,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 1,
    "not_burning(x1,y3)": 1,
    "not_burning(x2,y1)": 1,
    "not_burning(x2,y2)": 1,
    "not_burning(x2,y3)": 1,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 0,
    "not_burning(x3,y3)": 1,
    "not_out_of_fuel(x1,y1)": 1,
    "not_out_of_fuel(x1,y2)": 1,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 1,
    "not_out_of_fuel(x2,y2)": 1,
    "not_out_of_fuel(x2,y3)": 1,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 1,
    "not_out_of_fuel(x3,y3)": 1
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep0 seed1 t6",
   "mined": false
  },
  {
   "idx": 1,
   "kind": "rare",
   "likelihood": 0.028,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 0,
    "burning(x1,y3)": 0,
    "burning(x2,y1)": 0,
    "burning(x2,y2)": 0,
    "burning(x2,y3)": 1,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 1,
    "burning(x3,y3)": 0,
    "out_of_fuel(x1,y1)": 0,
    "out_of_fuel(x1,y2)": 1,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 1,
    "out_of_fuel(x2,y2)": 0,
    "out_of_fuel(x2,y3)": 0,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 1,
    "out_of_fuel(x3,y3)": 0,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 1,
    "not_burning(x1,y3)": 1,
    "not_burning(x2,y1)": 1,
    "not_burning(x2,y2)": 1,
    "not_burning(x2,y3)": 0,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 0,
    "not_burning(x3,y3)": 1,
    "not_out_of_fuel(x1,y1)": 1,
    "not_out_of_fuel(x1,y2)": 0,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 0,
    "not_out_of_fuel(x2,y2)": 1,
    "not_out_of_fuel(x2,y3)": 1,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 0,
    "not_out_of_fuel(x3,y3)": 1
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep0 seed1 t19",
   "mined": false
  },
  {
   "idx": 2,
   "kind": "rare",
   "likelihood": 0.022,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 1,
    "burning(x1,y3)": 1,
    "burning(x2,y1)": 0,
    "burning(x2,y2)": 0,
    "burning(x2,y3)": 0,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 0,
    "burning(x3,y3)": 0,
    "out_of_fuel(x1,y1)": 1,
    "out_of_fuel(x1,y2)": 0,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 0,
    "out_of_fuel(x2,y2)": 0,
    "out_of_fuel(x2,y3)": 0,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 0,
    "out_of_fuel(x3,y3)": 0,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 0,
    "not_burning(x1,y3)": 0,
    "not_burning(x2,y1)": 1,
    "not_burning(x2,y2)": 1,
    "not_burning(x2,y3)": 1,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 1,
    "not_burning(x3,y3)": 1,
    "not_out_of_fuel(x1,y1)": 0,
    "not_out_of_fuel(x1,y2)": 1,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 1,
    "not_out_of_fuel(x2,y2)": 1,
    "not_out_of_fuel(x2,y3)": 1,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 1,
    "not_out_of_fuel(x3,y3)": 1
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep1 seed2 t7",
   "mined": false
  },
  {
   "idx": 3,
   "kind": "rare",
   "likelihood": 0.001,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 1,
    "burning(x1,y3)": 1,
    "burning(x2,y1)": 1,
    "burning(x2,y2)": 0,
    "burning(x2,y3)": 1,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 0,
    "burning(x3,y3)": 0,
    "out_of_fuel(x1,y1)": 1,
    "out_of_fuel(x1,y2)": 1,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 0,
    "out_of_fuel(x2,y2)": 0,
    "out_of_fuel(x2,y3)": 0,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 0,
    "out_of_fuel(x3,y3)": 0,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 0,
    "not_burning(x1,y3)": 0,
    "not_burning(x2,y1)": 0,
    "not_burning(x2,y2)": 1,
    "not_burning(x2,y3)": 0,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 1,
    "not_burning(x3,y3)": 1,
    "not_out_of_fuel(x1,y1)": 0,
    "not_out_of_fuel(x1,y2)": 0,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 1,
    "not_out_of_fuel(x2,y2)": 1,
    "not_out_of_fuel(x2,y3)": 1,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 1,
    "not_out_of_fuel(x3,y3)": 1
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep1 seed2 t9",
   "mined": false
  },
  {
   "idx": 4,
   "kind": "rare",
   "likelihood": 0.037880181788073355,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 1,
    "burning(x1,y3)": 1,
    "burning(x2,y1)": 1,
    "burning(x2,y2)": 0,
    "burning(x2,y3)": 1,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 1,
    "burning(x3,y3)": 0,
    "out_of_fuel(x1,y1)": 1,
    "out_of_fuel(x1,y2)": 1,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 1,
    "out_of_fuel(x2,y2)": 0,
    "out_of_fuel(x2,y3)": 1,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 0,
    "out_of_fuel(x3,y3)": 0,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 0,
    "not_burning(x1,y3)": 0,
    "not_burning(x2,y1)": 0,
    "not_burning(x2,y2)": 1,
    "not_burning(x2,y3)": 0,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 0,
    "not_burning(x3,y3)": 1,
    "not_out_of_fuel(x1,y1)": 0,
    "not_out_of_fuel(x1,y2)": 0,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 0,
    "not_out_of_fuel(x2,y2)": 1,
    "not_out_of_fuel(x2,y3)": 0,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 1,
    "not_out_of_fuel(x3,y3)": 1
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep1 seed2 t10",
   "mined": false
  },
  {
   "idx": 5,
   "kind": "rare",
   "likelihood": 0.01,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 0,
    "burning(x1,y3)": 0,
    "burning(x2,y1)": 0,
    "burning(x2,y2)": 0,
    "burning(x2,y3)": 0,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 1,
    "burning(x3,y3)": 0,
    "out_of_fuel(x1,y1)": 1,
    "out_of_fuel(x1,y2)": 0,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 1,
    "out_of_fuel(x2,y2)": 0,
    "out_of_fuel(x2,y3)": 0,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 0,
    "out_of_fuel(x3,y3)": 1,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 1,
    "not_burning(x1,y3)": 1,
    "not_burning(x2,y1)": 1,
    "not_burning(x2,y2)": 1,
    "not_burning(x2,y3)": 1,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 0,
    "not_burning(x3,y3)": 1,
    "not_out_of_fuel(x1,y1)": 0,
    "not_out_of_fuel(x1,y2)": 1,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 0,
    "not_out_of_fuel(x2,y2)": 1,
    "not_out_of_fuel(x2,y3)": 1,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 1,
    "not_out_of_fuel(x3,y3)": 0
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep2 seed3 t33",
   "mined": false
  },
  {
   "idx": 6,
   "kind": "rare",
   "likelihood": 0.02681488882033728,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 0,
    "burning(x1,y3)": 0,
    "burning(x2,y1)": 0,
    "burning(x2,y2)": 0,
    "burning(x2,y3)": 1,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 1,
    "burning(x3,y3)": 0,
    "out_of_fuel(x1,y1)": 1,
    "out_of_fuel(x1,y2)": 0,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 1,
    "out_of_fuel(x2,y2)": 0,
    "out_of_fuel(x2,y3)": 0,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 1,
    "out_of_fuel(x3,y3)": 1,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 1,
    "not_burning(x1,y3)": 1,
    "not_burning(x2,y1)": 1,
    "not_burning(x2,y2)": 1,
    "not_burning(x2,y3)": 0,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 0,
    "not_burning(x3,y3)": 1,
    "not_out_of_fuel(x1,y1)": 0,
    "not_out_of_fuel(x1,y2)": 1,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 0,
    "not_out_of_fuel(x2,y2)": 1,
    "not_out_of_fuel(x2,y3)": 1,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 0,
    "not_out_of_fuel(x3,y3)": 0
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep2 seed3 t35",
   "mined": false
  },
  {
   "idx": 7,
   "kind": "rare",
   "likelihood": 0.016,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 0,
    "burning(x1,y3)": 0,
    "burning(x2,y1)": 0,
    "burning(x2,y2)": 0,
    "burning(x2,y3)": 0,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 0,
    "burning(x3,y3)": 1,
    "out_of_fuel(x1,y1)": 1,
    "out_of_fuel(x1,y2)": 0,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 1,
    "out_of_fuel(x2,y2)": 0,
    "out_of_fuel(x2,y3)": 0,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 0,
    "out_of_fuel(x3,y3)": 0,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 1,
    "not_burning(x1,y3)": 1,
    "not_burning(x2,y1)": 1,
    "not_burning(x2,y2)": 1,
    "not_burning(x2,y3)": 1,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 1,
    "not_burning(x3,y3)": 0,
    "not_out_of_fuel(x1,y1)": 0,
    "not_out_of_fuel(x1,y2)": 1,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 0,
    "not_out_of_fuel(x2,y2)": 1,
    "not_out_of_fuel(x2,y3)": 1,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 1,
    "not_out_of_fuel(x3,y3)": 1
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep3 seed4 t12",
   "mined": false
  },
  {
   "idx": 8,
   "kind": "rare",
   "likelihood": 0.02760940404464357,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 0,
    "burning(x1,y3)": 0,
    "burning(x2,y1)": 0,
    "burning(x2,y2)": 0,
    "burning(x2,y3)": 1,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 0,
    "burning(x3,y3)": 1,
    "out_of_fuel(x1,y1)": 1,
    "out_of_fuel(x1,y2)": 0,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 1,
    "out_of_fuel(x2,y2)": 0,
    "out_of_fuel(x2,y3)": 0,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 1,
    "out_of_fuel(x3,y3)": 1,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 1,
    "not_burning(x1,y3)": 1,
    "not_burning(x2,y1)": 1,
    "not_burning(x2,y2)": 1,
    "not_burning(x2,y3)": 0,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 1,
    "not_burning(x3,y3)": 0,
    "not_out_of_fuel(x1,y1)": 0,
    "not_out_of_fuel(x1,y2)": 1,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 0,
    "not_out_of_fuel(x2,y2)": 1,
    "not_out_of_fuel(x2,y3)": 1,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 0,
    "not_out_of_fuel(x3,y3)": 0
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep3 seed4 t19",
   "mined": false
  },
  {
   "idx": 9,
   "kind": "rare",
   "likelihood": 0.018612403639141593,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 1,
    "burning(x1,y3)": 0,
    "burning(x2,y1)": 0,
    "burning(x2,y2)": 0,
    "burning(x2,y3)": 1,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 0,
    "burning(x3,y3)": 1,
    "out_of_fuel(x1,y1)": 1,
    "out_of_fuel(x1,y2)": 0,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 1,
    "out_of_fuel(x2,y2)": 0,
    "out_of_fuel(x2,y3)": 1,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 1,
    "out_of_fuel(x3,y3)": 1,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 0,
    "not_burning(x1,y3)": 1,
    "not_burning(x2,y1)": 1,
    "not_burning(x2,y2)": 1,
    "not_burning(x2,y3)": 0,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 1,
    "not_burning(x3,y3)": 0,
    "not_out_of_fuel(x1,y1)": 0,
    "not_out_of_fuel(x1,y2)": 1,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 0,
    "not_out_of_fuel(x2,y2)": 1,
    "not_out_of_fuel(x2,y3)": 0,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 0,
    "not_out_of_fuel(x3,y3)": 0
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep3 seed4 t20",
   "mined": false
  },
  {
   "idx": 10,
   "kind": "rare",
   "likelihood": 0.021,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 0,
    "burning(x1,y3)": 1,
    "burning(x2,y1)": 0,
    "burning(x2,y2)": 1,
    "burning(x2,y3)": 0,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 0,
    "burning(x3,y3)": 0,
    "out_of_fuel(x1,y1)": 0,
    "out_of_fuel(x1,y2)": 0,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 0,
    "out_of_fuel(x2,y2)": 0,
    "out_of_fuel(x2,y3)": 0,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 0,
    "out_of_fuel(x3,y3)": 0,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 1,
    "not_burning(x1,y3)": 0,
    "not_burning(x2,y1)": 1,
    "not_burning(x2,y2)": 0,
    "not_burning(x2,y3)": 1,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 1,
    "not_burning(x3,y3)": 1,
    "not_out_of_fuel(x1,y1)": 1,
    "not_out_of_fuel(x1,y2)": 1,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 1,
    "not_out_of_fuel(x2,y2)": 1,
    "not_out_of_fuel(x2,y3)": 1,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 1,
    "not_out_of_fuel(x3,y3)": 1
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep4 seed5 t3",
   "mined": false
  },
  {
   "idx": 11,
   "kind": "rare",
   "likelihood": 0.012,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 0,
    "burning(x1,y3)": 1,
    "burning(x2,y1)": 1,
    "burning(x2,y2)": 1,
    "burning(x2,y3)": 0,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 0,
    "burning(x3,y3)": 0,
    "out_of_fuel(x1,y1)": 0,
    "out_of_fuel(x1,y2)": 0,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 0,
    "out_of_fuel(x2,y2)": 1,
    "out_of_fuel(x2,y3)": 0,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 0,
    "out_of_fuel(x3,y3)": 0,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 1,
    "not_burning(x1,y3)": 0,
    "not_burning(x2,y1)": 0,
    "not_burning(x2,y2)": 0,
    "not_burning(x2,y3)": 1,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 1,
    "not_burning(x3,y3)": 1,
    "not_out_of_fuel(x1,y1)": 1,
    "not_out_of_fuel(x1,y2)": 1,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 1,
    "not_out_of_fuel(x2,y2)": 0,
    "not_out_of_fuel(x2,y3)": 1,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 1,
    "not_out_of_fuel(x3,y3)": 1
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep4 seed5 t5",
   "mined": false
  },
  {
   "idx": 12,
   "kind": "rare",
   "likelihood": 0.016951926674148892,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 1,
    "burning(x1,y2)": 1,
    "burning(x1,y3)": 1,
    "burning(x2,y1)": 1,
    "burning(x2,y2)": 1,
    "burning(x2,y3)": 1,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 1,
    "burning(x3,y3)": 1,
    "out_of_fuel(x1,y1)": 0,
    "out_of_fuel(x1,y2)": 1,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 1,
    "out_of_fuel(x2,y2)": 1,
    "out_of_fuel(x2,y3)": 1,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 1,
    "out_of_fuel(x3,y3)": 0,
    "not_burning(x1,y1)": 0,
    "not_burning(x1,y2)": 0,
    "not_burning(x1,y3)": 0,
    "not_burning(x2,y1)": 0,
    "not_burning(x2,y2)": 0,
    "not_burning(x2,y3)": 0,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 0,
    "not_burning(x3,y3)": 0,
    "not_out_of_fuel(x1,y1)": 1,
    "not_out_of_fuel(x1,y2)": 0,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 0,
    "not_out_of_fuel(x2,y2)": 0,
    "not_out_of_fuel(x2,y3)": 0,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 0,
    "not_out_of_fuel(x3,y3)": 1
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep4 seed5 t11",
   "mined": false
  },
  {
   "idx": 13,
   "kind": "rare",
   "likelihood": 0.014,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 0,
    "burning(x1,y3)": 1,
    "burning(x2,y1)": 1,
    "burning(x2,y2)": 0,
    "burning(x2,y3)": 0,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 0,
    "burning(x3,y3)": 0,
    "out_of_fuel(x1,y1)": 0,
    "out_of_fuel(x1,y2)": 0,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 0,
    "out_of_fuel(x2,y2)": 0,
    "out_of_fuel(x2,y3)": 0,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 0,
    "out_of_fuel(x3,y3)": 0,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 1,
    "not_burning(x1,y3)": 0,
    "not_burning(x2,y1)": 0,
    "not_burning(x2,y2)": 1,
    "not_burning(x2,y3)": 1,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 1,
    "not_burning(x3,y3)": 1,
    "not_out_of_fuel(x1,y1)": 1,
    "not_out_of_fuel(x1,y2)": 1,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 1,
    "not_out_of_fuel(x2,y2)": 1,
    "not_out_of_fuel(x2,y3)": 1,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 1,
    "not_out_of_fuel(x3,y3)": 1
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep5 seed6 t1",
   "mined": false
  },
  {
   "idx": 14,
   "kind": "unmodeled",
   "likelihood": 0.0,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 1,
    "burning(x1,y3)": 1,
    "burning(x2,y1)": 1,
    "burning(x2,y2)": 0,
    "burning(x2,y3)": 1,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 0,
    "burning(x3,y3)": 0,
    "out_of_fuel(x1,y1)": 0,
    "out_of_fuel(x1,y2)": 0,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 1,
    "out_of_fuel(x2,y2)": 0,
    "out_of_fuel(x2,y3)": 0,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 0,
    "out_of_fuel(x3,y3)": 0,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 0,
    "not_burning(x1,y3)": 0,
    "not_burning(x2,y1)": 0,
    "not_burning(x2,y2)": 1,
    "not_burning(x2,y3)": 0,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 1,
    "not_burning(x3,y3)": 1,
    "not_out_of_fuel(x1,y1)": 1,
    "not_out_of_fuel(x1,y2)": 1,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 0,
    "not_out_of_fuel(x2,y2)": 1,
    "not_out_of_fuel(x2,y3)": 1,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 1,
    "not_out_of_fuel(x3,y3)": 1
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep5 seed6 t5",
   "mined": false
  },
  {
   "idx": 15,
   "kind": "rare",
   "likelihood": 0.023,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 0,
    "burning(x1,y3)": 1,
    "burning(x2,y1)": 0,
    "burning(x2,y2)": 0,
    "burning(x2,y3)": 1,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 0,
    "burning(x3,y3)": 0,
    "out_of_fuel(x1,y1)": 0,
    "out_of_fuel(x1,y2)": 0,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 0,
    "out_of_fuel(x2,y2)": 0,
    "out_of_fuel(x2,y3)": 0,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 0,
    "out_of_fuel(x3,y3)": 0,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 1,
    "not_burning(x1,y3)": 0,
    "not_burning(x2,y1)": 1,
    "not_burning(x2,y2)": 1,
    "not_burning(x2,y3)": 0,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 1,
    "not_burning(x3,y3)": 1,
    "not_out_of_fuel(x1,y1)": 1,
    "not_out_of_fuel(x1,y2)": 1,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 1,
    "not_out_of_fuel(x2,y2)": 1,
    "not_out_of_fuel(x2,y3)": 1,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 1,
    "not_out_of_fuel(x3,y3)": 1
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep6 seed7 t3",
   "mined": false
  },
  {
   "idx": 16,
   "kind": "rare",
   "likelihood": 0.003295103157322601,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 0,
    "burning(x1,y3)": 1,
    "burning(x2,y1)": 0,
    "burning(x2,y2)": 1,
    "burning(x2,y3)": 1,
    "burning(x3,y1)": 1,
    "burning(x3,y2)": 0,
    "burning(x3,y3)": 1,
    "out_of_fuel(x1,y1)": 0,
    "out_of_fuel(x1,y2)": 1,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 0,
    "out_of_fuel(x2,y2)": 1,
    "out_of_fuel(x2,y3)": 1,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 1,
    "out_of_fuel(x3,y3)": 0,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 1,
    "not_burning(x1,y3)": 0,
    "not_burning(x2,y1)": 1,
    "not_burning(x2,y2)": 0,
    "not_burning(x2,y3)": 0,
    "not_burning(x3,y1)": 0,
    "not_burning(x3,y2)": 1,
    "not_burning(x3,y3)": 0,
    "not_out_of_fuel(x1,y1)": 1,
    "not_out_of_fuel(x1,y2)": 0,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 1,
    "not_out_of_fuel(x2,y2)": 0,
    "not_out_of_fuel(x2,y3)": 0,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 0,
    "not_out_of_fuel(x3,y3)": 1
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep6 seed7 t10",
   "mined": false
  },
  {
   "idx": 17,
   "kind": "rare",
   "likelihood": 0.025,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 0,
    "burning(x1,y3)": 1,
    "burning(x2,y1)": 0,
    "burning(x2,y2)": 0,
    "burning(x2,y3)": 1,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 0,
    "burning(x3,y3)": 0,
    "out_of_fuel(x1,y1)": 0,
    "out_of_fuel(x1,y2)": 0,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 1,
    "out_of_fuel(x2,y2)": 0,
    "out_of_fuel(x2,y3)": 0,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 1,
    "out_of_fuel(x3,y3)": 0,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 1,
    "not_burning(x1,y3)": 0,
    "not_burning(x2,y1)": 1,
    "not_burning(x2,y2)": 1,
    "not_burning(x2,y3)": 0,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 1,
    "not_burning(x3,y3)": 1,
    "not_out_of_fuel(x1,y1)": 1,
    "not_out_of_fuel(x1,y2)": 1,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 0,
    "not_out_of_fuel(x2,y2)": 1,
    "not_out_of_fuel(x2,y3)": 1,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 0,
    "not_out_of_fuel(x3,y3)": 1
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep7 seed8 t11",
   "mined": false
  },
  {
   "idx": 18,
   "kind": "rare",
   "likelihood": 0.016,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 0,
    "burning(x1,y3)": 1,
    "burning(x2,y1)": 1,
    "burning(x2,y2)": 0,
    "burning(x2,y3)": 0,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 0,
    "burning(x3,y3)": 0,
    "out_of_fuel(x1,y1)": 0,
    "out_of_fuel(x1,y2)": 0,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 0,
    "out_of_fuel(x2,y2)": 0,
    "out_of_fuel(x2,y3)": 0,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 0,
    "out_of_fuel(x3,y3)": 0,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 1,
    "not_burning(x1,y3)": 0,
    "not_burning(x2,y1)": 0,
    "not_burning(x2,y2)": 1,
    "not_burning(x2,y3)": 1,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 1,
    "not_burning(x3,y3)": 1,
    "not_out_of_fuel(x1,y1)": 1,
    "not_out_of_fuel(x1,y2)": 1,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 1,
    "not_out_of_fuel(x2,y2)": 1,
    "not_out_of_fuel(x2,y3)": 1,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 1,
    "not_out_of_fuel(x3,y3)": 1
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep8 seed9 t1",
   "mined": false
  },
  {
   "idx": 19,
   "kind": "rare",
   "likelihood": 0.008,
   "steps": 256,
   "observed": {
    "burning(x1,y1)": 0,
    "burning(x1,y2)": 0,
    "burning(x1,y3)": 1,
    "burning(x2,y1)": 1,
    "burning(x2,y2)": 0,
    "burning(x2,y3)": 0,
    "burning(x3,y1)": 0,
    "burning(x3,y2)": 0,
    "burning(x3,y3)": 0,
    "out_of_fuel(x1,y1)": 1,
    "out_of_fuel(x1,y2)": 1,
    "out_of_fuel(x1,y3)": 1,
    "out_of_fuel(x2,y1)": 0,
    "out_of_fuel(x2,y2)": 0,
    "out_of_fuel(x2,y3)": 0,
    "out_of_fuel(x3,y1)": 0,
    "out_of_fuel(x3,y2)": 0,
    "out_of_fuel(x3,y3)": 0,
    "not_burning(x1,y1)": 1,
    "not_burning(x1,y2)": 1,
    "not_burning(x1,y3)": 0,
    "not_burning(x2,y1)": 0,
    "not_burning(x2,y2)": 1,
    "not_burning(x2,y3)": 1,
    "not_burning(x3,y1)": 1,
    "not_burning(x3,y2)": 1,
    "not_burning(x3,y3)": 1,
    "not_out_of_fuel(x1,y1)": 0,
    "not_out_of_fuel(x1,y2)": 0,
    "not_out_of_fuel(x1,y3)": 0,
    "not_out_of_fuel(x2,y1)": 1,
    "not_out_of_fuel(x2,y2)": 1,
    "not_out_of_fuel(x2,y3)": 1,
    "not_out_of_fuel(x3,y1)": 1,
    "not_out_of_fuel(x3,y2)": 1,
    "not_out_of_fuel(x3,y3)": 1
   },
   "source": "Wildfire_MDP_ippc2014 i1 ep9 seed10 t32",
   "mined": false
  }
 ]
}
```

## 2026-10-10 12:36:54 — `record 0`

```text
{
 "ok": true,
 "idx": 0,
 "kind": "rare",
 "likelihood": 0.005,
 "steps": 256,
 "observed": {
  "burning(x1,y1)": 0,
  "burning(x1,y2)": 0,
  "burning(x1,y3)": 0,
  "burning(x2,y1)": 0,
  "burning(x2,y2)": 0,
  "burning(x2,y3)": 0,
  "burning(x3,y1)": 0,
  "burning(x3,y2)": 1,
  "burning(x3,y3)": 0,
  "out_of_fuel(x1,y1)": 0,
  "out_of_fuel(x1,y2)": 0,
  "out_of_fuel(x1,y3)": 1,
  "out_of_fuel(x2,y1)": 0,
  "out_of_fuel(x2,y2)": 0,
  "out_of_fuel(x2,y3)": 0,
  "out_of_fuel(x3,y1)": 0,
  "out_of_fuel(x3,y2)": 0,
  "out_of_fuel(x3,y3)": 0,
  "not_burning(x1,y1)": 1,
  "not_burning(x1,y2)": 1,
  "not_burning(x1,y3)": 1,
  "not_burning(x2,y1)": 1,
  "not_burning(x2,y2)": 1,
  "not_burning(x2,y3)": 1,
  "not_burning(x3,y1)": 1,
  "not_burning(x3,y2)": 0,
  "not_burning(x3,y3)": 1,
  "not_out_of_fuel(x1,y1)": 1,
  "not_out_of_fuel(x1,y2)": 1,
  "not_out_of_fuel(x1,y3)": 0,
  "not_out_of_fuel(x2,y1)": 1,
  "not_out_of_fuel(x2,y2)": 1,
  "not_out_of_fuel(x2,y3)": 1,
  "not_out_of_fuel(x3,y1)": 1,
  "not_out_of_fuel(x3,y2)": 1,
  "not_out_of_fuel(x3,y3)": 1
 },
 "source": "Wildfire_MDP_ippc2014 i1 ep0 seed1 t6",
 "mined": false,
 "init": {
  "out_of_fuel(x1,y3)": 1,
  "not_burning(x1,y1)": 1,
  "not_burning(x1,y2)": 1,
  "not_burning(x1,y3)": 1,
  "not_burning(x2,y1)": 1,
  "not_burning(x2,y2)": 1,
  "not_burning(x2,y3)": 1,
  "not_burning(x3,y1)": 1,
  "not_burning(x3,y2)": 1,
  "not_burning(x3,y3)": 1,
  "not_out_of_fuel(x1,y1)": 1,
  "not_out_of_fuel(x1,y2)": 1,
  "not_out_of_fuel(x2,y1)": 1,
  "not_out_of_fuel(x2,y2)": 1,
  "not_out_of_fuel(x2,y3)": 1,
  "not_out_of_fuel(x3,y1)": 1,
  "not_out_of_fuel(x3,y2)": 1,
  "not_out_of_fuel(x3,y3)": 1,
  "tick": 1
 },
 "program_key": "ea1cb962d41f5e26661464acac11fe928fb5c66d7c061d70f0e3068062581861"
}
```

## 2026-10-10 12:37:16 — `replay`

```text
{
 "ok": false,
 "error": "exact filter retained 500001 states (budget 500000) at step 26/256 \u2014 lower the horizon, or this is clique-tree/factored territory"
}
```

## 2026-10-10 12:37:31 — `reset`

```text
stage open
  not_burning      (x1,y1) (x1,y2) (x1,y3) (x2,y1) (x2,y2) (x2,y3) (x3,y1)
                   (x3,y2) (x3,y3)
  not_out_of_fuel  (x1,y1) (x1,y2) (x2,y1) (x2,y2) (x2,y3) (x3,y1) (x3,y2)
                   (x3,y3)
  out_of_fuel      (x1,y3)
  tick             ·
```

## 2026-10-10 12:37:48 — `query burning(x3,y2) @frame`

```text
P[burning(x3,y2) at @frame (read when the cone settles)] = 0.01333 ± 0.0097
  tier         sampled n=600, 95% ± ci (2.3 s) — exact refused: exact filter retained 100002 states (budget 100000) at step 22/32 — lower the horizon, or this is clique-tree/factored territory
               (arms paired by common random numbers — variance reduction only, no cross-world coupling)
  readout      @frame (read when the cone settles)
  cone here    tracking 186 of 220 atoms · 460 of 553 events (stage-closed: links reachable) · key 3d3ea7c4c2b9
```

## 2026-10-10 12:38:00 — `query burning(x2,y2) @frame`

```text
P[burning(x2,y2) at @frame (read when the cone settles)] = 0 ± 0.0048
  tier         sampled n=400, 95% ± ci (1.5 s) — exact refused: exact filter retained 100002 states (budget 100000) at step 22/32 — lower the horizon, or this is clique-tree/factored territory
               (arms paired by common random numbers — variance reduction only, no cross-world coupling)
  readout      @frame (read when the cone settles)
  cone here    tracking 186 of 220 atoms · 460 of 553 events (stage-closed: links reachable) · key 3d3ea7c4c2b9
```

## 2026-10-10 12:38:13 — `mine Observed in the real wildfire (instance 1; records of sinks/iter0-transitions--iter1-world--frame-neg-tick.jsonl, the world of iteration 1 replayed on the same 400 steps; interface unchanged: atom or not_<atom> per observed fluent, the action atoms, one tick; read when nothing more can happen). The world explains the step's structure: 380 of 400 steps are no surprise. The 20 that are (19 rare, 1 not reached) are all steps where cells started burning (record 0: burning(x3,y2) starts with no neighbor burning; record 3: burning(x2,y1) and burning(x2,y3) start in the same step). How OFTEN a cell that is not burning and not out_of_fuel starts burning is a rate that depends only on k, the number of its neighbors burning at the start of the step, for target and non-target cells alike, except that a target with k=0 never starts. That rate is DATA, fitted from the episodes - not a number in the text, and the counts quoted before (k=0 6 of 494 ... k=4 1 of 1) are evidence for fitting it, not rules: one start in one exposure does not make a start certain. The law is ONE rule over the count k for every cell that may start, its two outcomes (starts burning / stays not_burning) priced by a weight port pign(K) of the count and its complement - never one rule per count, never a count that makes a start sure. Everything else the world does stays as it is.`

```text
{
 "ok": true,
 "chars": 1360
}
```

## 2026-10-10 12:39:17 — `formalize`

```text
{
 "ok": true,
 "backend": "command:/home/axadmin/repo/perotheia-packages/metis-loop/experiments/wildfire/seat-claude.sh",
 "rounds": 1,
 "gated_as": "revise (base edit)",
 "findings": []
}
```

#### candidate snapshot (after `formalize`)

```llp
catalog wildfire 4.
provenance text "the real wildfire (rddlrepository Wildfire_MDP_ippc2014, instance 1) as observed: burning and out_of_fuel per cell, put_out and cut_out actions, one tick per step; ignition revised to one rule priced by a fitted weight port pign(K) of the burning-neighbor count" "2026-10-10".
layers (dyn).
stages (open count act screen ignite).
type xc {x1 x2 x3}.
type yc {y1 y2 y3}.
% k counts burning neighbors, 0..8
type nbcount {k0..k8}.
% position in a cell's neighbor list; s8 is past the end of the longest list
type slot {s0..s8}.
namespace wf produce (dyn).
pred burning(xc, yc) : wf.
pred not_burning(xc, yc) : wf.
pred out_of_fuel(xc, yc) : wf.
pred not_out_of_fuel(xc, yc) : wf.
pred put_out(xc, yc) : wf.
pred cut_out(xc, yc) : wf.
pred tick : wf.
pred walk(xc, yc) : wf.
pred cell(xc, yc) : wf.
pred fresh(xc, yc) : wf.
pred held(xc, yc) : wf.
pred tally(xc, yc, nbcount) : wf.
pred scan(xc, yc, slot) : wf.
bwd next(nbcount, nbcount).
next(k0, k1).
next(k1, k2).
next(k2, k3).
next(k3, k4).
next(k4, k5).
next(k5, k6).
next(k6, k7).
next(k7, k8).
bwd nextslot(slot, slot).
nextslot(s0, s1).
nextslot(s1, s2).
nextslot(s2, s3).
nextslot(s3, s4).
nextslot(s4, s5).
nextslot(s5, s6).
nextslot(s6, s7).
nextslot(s7, s8).
% the cells x1..x3 by y1..y3, visited once per step in this order
bwd firstcell(xc, yc).
firstcell(x1, y1).
bwd nextcell(xc, yc, xc, yc).
nextcell(x1, y1, x1, y2).
nextcell(x1, y2, x1, y3).
nextcell(x1, y3, x2, y1).
nextcell(x2, y1, x2, y2).
nextcell(x2, y2, x2, y3).
nextcell(x2, y3, x3, y1).
nextcell(x3, y1, x3, y2).
nextcell(x3, y2, x3, y3).
bwd lastcell(xc, yc).
lastcell(x3, y3).
% the instance's directed neighbor relation, each cell's list walked in order
bwd nb(xc, yc, slot, xc, yc).
nb(x1, y1, s0, x1, y2).
nb(x1, y1, s1, x2, y1).
nb(x1, y1, s2, x2, y2).
nb(x1, y2, s0, x1, y1).
nb(x1, y2, s1, x1, y3).
nb(x1, y2, s2, x2, y1).
nb(x1, y2, s3, x2, y2).
nb(x1, y2, s4, x2, y3).
nb(x1, y3, s0, x2, y2).
nb(x1, y3, s1, x2, y3).
nb(x2, y1, s0, x1, y1).
nb(x2, y1, s1, x1, y2).
nb(x2, y1, s2, x2, y2).
nb(x2, y1, s3, x3, y1).
nb(x2, y1, s4, x3, y2).
nb(x2, y2, s0, x1, y1).
nb(x2, y2, s1, x1, y2).
nb(x2, y2, s2, x1, y3).
nb(x2, y2, s3, x2, y1).
nb(x2, y2, s4, x2, y3).
nb(x2, y2, s5, x3, y1).
nb(x2, y2, s6, x3, y2).
nb(x2, y2, s7, x3, y3).
nb(x2, y3, s0, x1, y2).
nb(x2, y3, s1, x1, y3).
nb(x2, y3, s2, x2, y2).
nb(x2, y3, s3, x3, y2).
nb(x2, y3, s4, x3, y3).
nb(x3, y1, s0, x2, y1).
nb(x3, y1, s1, x2, y2).
nb(x3, y1, s2, x3, y2).
nb(x3, y2, s0, x2, y1).
nb(x3, y2, s1, x2, y2).
nb(x3, y2, s2, x2, y3).
nb(x3, y2, s3, x3, y1).
nb(x3, y2, s4, x3, y3).
nb(x3, y3, s0, x2, y2).
nb(x3, y3, s1, x2, y3).
nb(x3, y3, s2, x3, y2).
% the slot just past the end of each cell's neighbor list
bwd nbend(xc, yc, slot).
nbend(x1, y1, s3).
nbend(x1, y2, s5).
nbend(x1, y3, s2).
nbend(x2, y1, s5).
nbend(x2, y2, s8).
nbend(x2, y3, s5).
nbend(x3, y1, s3).
nbend(x3, y2, s5).
nbend(x3, y3, s3).
bwd target(xc, yc).
target(x2, y2).
target(x2, y3).
target(x3, y1).
bwd plain(xc, yc).
plain(x1, y1).
plain(x1, y2).
plain(x1, y3).
plain(x2, y1).
plain(x3, y2).
plain(x3, y3).
% the ignition rate for a cell with K burning neighbors: DATA, fitted from the episodes at serve time
weight pign(K) reads {}.
stage open {
  %% "a step starts from a state holding, for EACH observed fluent, either its atom (true) or not_<atom> (false) ... plus the action atoms taken that step ... and one tick atom"
  begin [dyn] : tick * firstcell(X, Y) -o cell(X, Y) * walk(X, Y).
  %% "for the cells X in x1 x2 x3, Y in y1 y2 y3"
  visit [dyn] : walk(X, Y) * nextcell(X, Y, U, V) -o cell(U, V) * walk(U, V).
  %% "for the cells X in x1 x2 x3, Y in y1 y2 y3"
  close [dyn] : walk(X, Y) * lastcell(X, Y) -o ().
}
stage count {
  %% "a cell that is not burning and not out_of_fuel starts burning ... a rate that depends only on k, the number of its neighbors burning at the start of the step"
  ready [dyn] : cell(X, Y) * $not_burning(X, Y) * $not_out_of_fuel(X, Y) -o fresh(X, Y) * tally(X, Y, k0) * scan(X, Y, s0).
  %% "Every cell that was burning at the start of a step is out_of_fuel at its end"
  hold [dyn] : cell(X, Y) * $burning(X, Y) -o held(X, Y).
  %% "A cell that is out_of_fuel and not burning never started burning."
  spent [dyn] : cell(X, Y) * $not_burning(X, Y) * $out_of_fuel(X, Y) -o ().
  %% "k, the number of its neighbors burning at the start of the step"
  see_fire [dyn] : scan(X, Y, S) * tally(X, Y, K) * nb(X, Y, S, U, V) * $burning(U, V) * nextslot(S, S2) * next(K, K2) -o scan(X, Y, S2) * tally(X, Y, K2).
  %% "k, the number of its neighbors burning at the start of the step"
  see_none [dyn] : scan(X, Y, S) * nb(X, Y, S, U, V) * $not_burning(U, V) * nextslot(S, S2) -o scan(X, Y, S2).
  %% "The instance's neighbor relation (directed: cell: its neighbors)"
  scan_done [dyn] : scan(X, Y, S) * nbend(X, Y, S) -o ().
}
stage act {
  %% "a burning cell stayed burning 1149 times and stopped 28 times, every stop in a step whose action was put_out on that cell"
  douse [dyn] : put_out(X, Y) * burning(X, Y) -o not_burning(X, Y).
  %% "put_out on a cell that is not burning changes nothing (record 0: put_out(x2,y2); record 33: put_out(x2,y1) while burning(x2,y2) starts)"
  put_idle [dyn] : put_out(X, Y) * $not_burning(X, Y) -o ().
  %% "Every cell that was burning at the start of a step is out_of_fuel at its end (1177 of 1177; record 10: burning(x1,y3) gains out_of_fuel(x1,y3))"
  burn_fuel [dyn] : held(X, Y) * not_out_of_fuel(X, Y) -o out_of_fuel(X, Y).
  %% "Every cell that was burning at the start of a step is out_of_fuel at its end"
  burnt [dyn] : held(X, Y) * $out_of_fuel(X, Y) -o ().
  %% "cut_out on a non-target cell makes it out_of_fuel (66 of 66; record 3: cut_out(x2,y1))"
  cut [dyn] : cut_out(X, Y) * plain(X, Y) * not_out_of_fuel(X, Y) -o out_of_fuel(X, Y).
  %% "cut_out on a non-target cell makes it out_of_fuel"
  cut_bare [dyn] : cut_out(X, Y) * $out_of_fuel(X, Y) -o ().
  %% "cut_out on a target cell that is not burning leaves it not_out_of_fuel (19 of 19)"
  cut_target [dyn] : cut_out(X, Y) * target(X, Y) -o ().
}
stage screen {
  %% "for target and non-target cells alike, except that a target with k=0 never starts"
  calm_target_k0 [dyn] : fresh(X, Y) * tally(X, Y, k0) * target(X, Y) -o ().
}
stage ignite {
  %% "The law is ONE rule over the count k for every cell that may start, its two outcomes (starts burning / stays not_burning) priced by a weight port pign(K) of the count and its complement"
  catch [dyn] : fresh(X, Y) * tally(X, Y, K) * not_burning(X, Y) -o (burning(X, Y) @w pign(K) | not_burning(X, Y) @w ~pign(K)).
}
%% "the neighbors burning at the start of the step" are read before anything changes
qui tally_up [dyn] : open -o count.
%% "Many cells change within ONE step, all at once."
qui apply [dyn] : count -o act.
%% "except that a target with k=0 never starts"
qui sift [dyn] : act -o screen.
%% "How OFTEN a cell that is not burning and not out_of_fuel starts burning is a rate that depends only on k"
qui spread [dyn] : screen -o ignite.
```

## 2026-10-10 12:39:29 — `#steps 2`

```text
steps 2
```

## 2026-10-10 12:39:39 — `accept`

```text
{
 "ok": true,
 "diffs": [],
 "dropped_packs": 0,
 "accepted_packs": 0,
 "key": "82c3f0665340419fad744f2098ce2a48948bb213617957a199645001d621e8cd"
}
```

**accepted** — the world is now key 82c3f0665340419fad744f2098ce2a48948bb213617957a199645001d621e8cd

## 2026-10-10 12:39:41 — `export iter2-world`

```text
{
 "ok": true,
 "dir": "iter2-world",
 "files": 2
}
```

---
_transcript closed 2026-10-10 13:55:46_
