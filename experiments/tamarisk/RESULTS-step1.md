# RDDL Tamarisk — step 1 results: a catalog born from the header (2026-10-10)

This is subject rddl-tier1 (s-8f820524), domain 2 of 7 (the subject's step
3). **It stops here at the USER's checkpoint.** Nothing is committed.

## Artifacts

- `header.txt`: the seed. It is the rddlrepository header verbatim
  (`IPPC2014/Tamarisk/MDP/domain.rddl`, lines 1–39), **read as latin-1**
  per the shelf GOTCHA, 1884 chars. The one non-ASCII byte, 0x96 in the
  Muneepeerakul page range "351?63", decodes under latin-1 to U+0096 (a
  C1 control). In cp1252 it is the en-dash the author meant. It is kept
  as latin-1 says.
- `step1-language-card.txt`: the session card. It is the Wildfire card v2
  (generic grammar, the doctrine paragraph, the generic WEIGHT PORTS
  section), unchanged; there is no domain content.
- `seat-claude.sh`: the contained `claude -p` seat (claude-opus-5-5).
- `step1-transcript.md`: the birth session (formalize). Its accept refused
  (finding 2).
- `step1b-accept-transcript.md`: the accept session (`metis --plugin
  tamarisk_plugin:make`: load the seat's candidate verbatim, revise,
  accept, trace).
- `step1-candidate-from-formalize.llp`: exactly what the seat emitted.
- `tamarisk_born.llp`: **the born catalog.** It is that candidate's body
  byte-identical, under the verbatim header as `%` comments.
- `tamarisk_plugin.py`: prior-flat base bindings (0.5) for the seat's
  ports.
- `step1b-export-after-load-LOSSY.llp`: kept as the evidence for
  finding 3.

## The session

`formalize` went **green in 1 round, gated as revise** (base edit), with no
findings. The born file re-gates ok with its own scenario (9 `#init`
atoms, `#steps 12`) and the ports bound. It is **classified a
class-F counterexample**: `eradicate` produces `cost`, which may already
be present, so multiset counts aren't 0/1 (the reward-bookkeeping atom,
see gap 7).

`trace` (seed 1): `restore[r3,s2]`, `eradicate[r1,s1]`,
`restore[r2,s2]`, `restore[r1,s1]`, then `intervene_done`, then
`growth_done`. The interventions clear the only tamarisk before
anything can spread.

## The born catalog

- Three stages, `act → grow → assess`. Types are `reach {r1 r2 r3}` and
  `slot {s1 s2}`; the instance is illustrative and flagged. Atoms are
  `native/tamarisk/empty(reach, slot)` and `downstream(reach, reach)`
  facts (illustrative r1→r2→r3).
- **The seat put the rates in weight ports at birth**: `pdown(R)`,
  `pup(R)`, `pcompete(R)`, each referenced as a complement pair
  (`spread_down`, `spread_up`, `compete`). This is the first born catalog
  to do so. It is the card v2's effect: the header gives no numbers,
  only "spread downstream and sometimes upstream", "compete", "a fixed
  rate".
- `native_spread` is deterministic within a reach (from "native species
  that spread at a fixed rate").
- `assess` derives `penalty(R)` for invaded or vulnerable reaches, and
  `cost` tokens count interventions.

## Fidelity against the cpfs (for the checkpoint — recorded, not fixed)

1. **Interventions are spontaneous events, not actions.** `eradicate` and
   `restore` fire on any slot, always succeed, and need no action atom.
   In RDDL they are per-reach actions (max-nondef-actions = 1) that
   succeed stochastically (ERADICATION-RATE, RESTORATION-RATE), and
   eradication fails on a fully invaded reach.
2. **No deaths:** DEATH-RATE-TAMARISK and DEATH-RATE-NATIVE are absent.
3. **No exogenous production** (EXOGENOUS-PROD-RATE-*) into empty slots.
4. **Native "spread" is deterministic within a reach.** The cpfs comment
   says natives arrive only exogenously, despite the header's "spread at
   a fixed rate".
5. **Competition shape differs.** RDDL lets tamarisk and native coexist
   in a slot for one step, then resolves it with COMPETITION-WIN-RATE-*.
   Here a neighbor reach's tamarisk replaces a native directly.
6. **Spread is noisy-or** in RDDL, over same-reach (downstream rate),
   downstream and upstream sources. Here spread runs only between
   adjacent reaches, with no within-reach spread.
7. The reward is modeled as state (`cost`, `penalty`), even though metis
   grounds without reward. This also causes the class-F counterexample.
8. The topology is illustrative (3 reaches × 2 slots). Instance 1 has 4
   reaches × 2 slots, with slots named per reach (`s1s1`, `s1s2`, …).

## Notch-target audit (architect's request; the Wildfire correction)

There are **17 real non-fluents: 10 dynamics (the notch ground truth) and
7 reward.**

- **Dynamics:** ERADICATION-RATE 0.9, RESTORATION-RATE 0.9,
  DOWNSTREAM-SPREAD-RATE 0.6, UPSTREAM-SPREAD-RATE 0.15,
  DEATH-RATE-TAMARISK 0.05, DEATH-RATE-NATIVE 0.05,
  EXOGENOUS-PROD-RATE-NATIVE 0.1, EXOGENOUS-PROD-RATE-TAMARISK 0.1,
  COMPETITION-WIN-RATE-NATIVE 0.2, COMPETITION-WIN-RATE-TAMARISK 0.8
  (domain defaults; the instances may override).
- **Reward, not targets:** COST-PER-INVADED-REACH, COST-PER-TREE,
  COST-PER-EMPTY-SLOT, ERADICATION-COST, RESTORATION-COST,
  RESTORATION-COST-FOR-EMPTY-SLOT, RESTORATION-COST-FOR-INVADED-SLOT.

Two shape notes for step 2a:
- The seat's ports take a reach argument (`pdown(D)`), while the truth is
  one global constant per law. The per-reach notch rows should come out
  equal (a structure check).
- Spread is noisy-or over sources. A per-source port fits exactly only
  if each source is its own draw, which the loop must discover.

## Findings (step 1)

1. **Card v2 → ports at birth.** No literal weights were invented, and
   no unrolling. The doctrine plus port syntax works from the header
   alone.
2. **The formalize gate and the revise gate disagree on unbound ports**
   (loop, mine). `formalize`'s repair loop gates prior-only (no
   registry), so a ported catalog goes green. `revise`/`gate` pass the
   session's bindings, so the same candidate is a finding in a
   plugin-less session. And **`accept` was not atomic**: it switched the
   loop state (base source, revision flag) before re-serving, the
   re-serve then refused with a raw `PortError`, and the loop was left
   half-switched. **Fixed** in metispy: accept re-serves FIRST and
   refuses cleanly with the hint (`plugin SPEC` / `metis --plugin`),
   leaving the state untouched (test). The formalize/revise asymmetry
   itself is left as is, because the seat cannot bind ports, so a
   repair loop that demanded bindings would spin. Your call.
3. **`load FILE` stored `pretty(parse(FILE))`** (loop). The
   pretty-printer drops `%%` docs (the approval units) and `#`
   directives, so gate → accept → export carried a doc-less, directive-less
   world with ⊕ expanded into `-1`/`-2` rules. The gate didn't object.
   **Fixed:** the candidate is the file verbatim unless includes were
   spliced (test). Open question: should the gate warn when rules lack
   `%%` docs? The skill says docs are mandatory.
4. **A heredoc paste hangs the terminal REPL** (not fixed). Pasting
   `text <<EOF … EOF` as one block into an idle `metis` hung inside the
   heredoc twice; the same paste worked once right after startup.
   `cmdloop` reads prompts through `readline` while `_heredoc` reads
   `sys.stdin.readline()`, so a whole paste can land in readline's buffer
   and starve the heredoc. The workaround used: send `text <<EOF`, then
   the body, then `EOF` separately (byte-exact, 1884 chars).
5. latin-1 vs cp1252: see the `header.txt` note above.

## Tool changes this step (metispy, uncommitted, tests green)

- `loop/verbs.cmd_accept`: atomic, with a clean refusal and hint on
  unbound ports.
- `loop/verbs.cmd_load`: verbatim candidate.
- Tests: `tests/fw/test_plugin.py::test_accept_with_unbound_ports_is_refused_atomically`
  and `tests/loop/test_loop_fixes.py::test_load_keeps_the_candidate_verbatim`.
  tests/loop + test_plugin: 42 passed.

## Acceptance (step 1)

The catalog gates green from the header alone (formalize 1 round; revise
ok; the born file re-gates ok with the ports bound prior-flat). The
transcripts are kept. **The human checkpoint is pending (the user).**
