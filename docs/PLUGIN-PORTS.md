# Python port plugins — real values and time in the REPL

Status: DESIGN (2026-10-09, architect) — kernel face validated
hands-on; REPL plumbing and env lifecycle are the work. The C++
runtime (theia) binds real ports; this interface is the Python
prototyping twin, under the SAME contract, so a prototyped domain
transfers by reimplementing bindings only.

## Doctrine (what already decides the shape)

Real values never enter the measure: the catalog's measure lives on
QUALITATIVE classes (`gclose`/`gsafe`), exact quantities stay behind
weight ports under a declared read contract — `weight rss(V) reads
{gclose(V), on(ego,L) if islane(L), ...}` (road_handles3.llp is the
reference). The declared scope is what makes the encoding
factorizable (class-F) and compilable to the IR artifact the vehicle
interprets: the port is opaque CODE but symbolically SCOPED.

## What exists today (validated 2026-10-09, scratchpad port_proto.py)

- Syntax: `weight f(args) reads {pattern [if guard], ...}` compiles;
  `@w f(args)` / `@w ~f(args)` reference it (complement pair).
- `metis.fw.registry.Registry` — THE seam ("BT.cpp registerNodeType"):
  `weight(name, callable|float|table)` base bindings (total),
  `overlay(name, binding)` experience-over-base (miss -> fall
  through), `inputs/outputs/guards` dicts (currently unconsumed).
- `metis.lang.weight_policy(prog, doc.ports, reg.weight_bindings())`
  -> policy for ForwardProjection/SampledProjection: EXERCISED — a
  Python callable reading live env state priced P[crash] 0.3, env
  mutation re-priced it 0.9, an overlay overrode to 0.42 and popped.
- `metis.lang.compiler.factor_hooks` — the factored/IR tier: ground
  read-scopes per event, ScopeViolation on out-of-scope reads
  (the teeth live HERE; the sampling tier's weight_policy does NOT
  yet wrap counts in ScopedCounts — gap G5).
- `metis.kernel.notch` — fits ports from episodes (Dirichlet
  posterior per declared-scope row, exact-smoother EM for partial
  observation), shipping an OVERLAY registry + human row sheet.
  Learning never edits the catalog.

## The gap: no REPL plumbing

The terminal `metis` shell builds its measure with no registry: a
catalog with ports cannot be served interactively, no env can tick,
and the instruments know nothing of external state.

## The plugin protocol

```python
class PortPlugin(Protocol):
    def bind(self, reg: Registry) -> None
        # register weight/guard bindings. PURITY CONTRACT: a binding
        # is a function of (args, declared-scope counts, env
        # snapshot) — nothing else. Out-of-scope reads are a bug the
        # factored tier rejects; the interactive tier must too (G5).
    def tick(self, counts: dict) -> list[str]
        # the INPUT face: the env advances one world beat and
        # returns do-lines ("+atom [n]" / "-atom") — exogenous
        # input IS an intervention stream, applied through the
        # ledger, first-class in log/graph/why/whatif.
    def on_event(self, name: str, args: tuple) -> None
        # the OUTPUT face: a fired event actuates the env
        # (metis chooses `open_turn`, the env moves the motor).
    def snapshot(self) -> object
    def restore(self, snap: object) -> None
        # REQUIRED. fork/back/undo/reset/whatif snapshot the env
        # with the world or the counterfactual instruments LIE.
```

Env state mutates ONLY in tick/on_event; snapshot is total. That
purity+snapshot pair is exactly the determinism contract the theia
C++ ports need (deterministic replay) — hence "prototyping is
comprehensive": what passes here transfers.

## Attachment

- `#plugin package.module:factory` directive (scene-level, like
  `#init`; factory(case) -> PortPlugin). TERMINAL ONLY — D4: the
  web/shared console never imports operator code; `plugin` joins
  transcript on the D4 refusal list.
- REPL verbs: `plugin [SPEC|off]` load/show; `ports` — declared
  ports, bound/unbound, ground scopes; `port f(args)` — evaluate one
  binding against the current counts (debug probe).
- Config: `[ports] plugin = "pkg.mod:factory"` in the metis dot file.

## Repl integration points

1. serve/reload/accept: rebuild policy via `reg.weight_bindings()`;
   unbound port = refuse to serve (fail-fast, BT.cpp rule).
2. `_sample`/step: after each fired event, `on_event`; at each beat
   boundary (or settle-stage entry in tick-stage catalogs),
   `tick(counts)` -> apply dos through the ledger.
3. fork/_ifork/back/undo/reset: push/pop `plugin.snapshot()` beside
   the world snapshot.
4. records: `surprise_record` gains `env` (snapshot hash + optional
   blob) so `recover()` replays honestly against the same env.
5. gate/revise: scenario runs take the bound registry; a candidate
   referencing an unbound port is a FINDING, not a crash.
6. notch verb: fit overlays from the session's episodes
   (kernel.notch), print the row sheet, `accept` ships the overlay —
   never a catalog edit.
7. G5: wrap the sampling-tier counts in ScopedCounts so the
   interactive tier enforces `reads` like the factored tier does.

## Time-dependent patterns

- Discrete tick: the bridge idiom (board -> stride -> settle qui
  cycle); `tick()` fires on settle entry — one env beat per world
  minute. Elevators synchrony lands here too: the env ticks, the
  catalog interleaves within the beat.
- Continuous time: the env integrates ODEs between beats; the
  catalog sees only class atoms (`hot/cold`, `rising/falling`)
  emitted by tick() and prices transitions by ports reading them.
  Timestamps ride as record metadata, never as measure.

## Prototyping targets (comprehensive = these all run in the REPL)

1. PyRDDLGymPlugin (generic): env = a pyRDDLGym instance; action
   atoms -> on_event accumulates the action dict; observations ->
   tick dos; continuous IPPC domains (HVAC, Reservoir, PowerGen)
   become exercisable — qualitative catalog + plugin reals; notch
   fits the transition ports from episodes (step-2a generalized).
2. The road continuous reference (metis/domains/road/continuous.py)
   rehosted as a PortPlugin — parity check against its fitted tables.
3. A clock-only plugin for pure time-dependence (cron-world: atoms
   appear on schedule) — the minimal conformance test.

## Conformance fixtures (metis-catalog domains/ports/port-proto/, all green 2026-10-09; README there)

1. `port_proto.py` + `sensor.llp` — weights/overlay/scope: env flip
   re-prices P[crash] 0.3→0.9 exactly; overlay 0.42 + pop; shows G5
   (sampling tier lacks ScopedCounts teeth).
2. `reservoir_proto.py` + `reservoir.llp` — real-valued: the level
   (real) behind `pspill`, season clock behind `prain`; 14-day
   episode, spills occur only under the high class; release
   actuation feeds back into the env.
3. `clock_proto.py` + `clock.llp` — time face: scheduled door and
   customer injections as do-interventions into a live Repl; the
   ledger interleaves dos with fired events and `why missed` names
   the lose rule. Surfaced G6: `do_step` at quiescence latches
   stage=DONE and the world never revives — with an env attached,
   exogenous tick input must REVIVE a quiescent world (a shop with
   no customers is quiet, not dead). Same area as the bridge
   post-terminal qui-spin finding.

The fixtures drive internal APIs (`weight_policy`, `onecmd("do …")`,
`_candidates`); the native `#plugin` implementation replaces exactly
those call sites and must run all three from the REPL.

## Open questions

- do-lines vs a dedicated exogenous-event kind in the ledger
  (interventions are honest but flavor the counterfactual columns;
  an `obs` kind may read better in whatif output).
- env in the cone: exact tiers treat port values as constants per
  snapshot; a tick that CHANGES env mid-horizon breaks the static
  cone — horizon segmentation per beat, or sampled tier only.
- gate scenarios for port catalogs: who supplies the env fixture
  (the plugin's factory takes the scenario row?).
