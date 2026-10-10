# RDDL Wildfire — step 1 results: a catalog born from the header (2026-10-10)

This is subject rddl-tier1 (s-8f820524), domain 1 of 7. It reruns the
elevators recipe's step 1. **It stops here at the USER's checkpoint.**

## Artifacts (this directory)

- `header.txt`: the seed. It is the rddlrepository header verbatim
  (`archive/competitions/IPPC2014/Wildfire/MDP/domain.rddl`, lines 1–35, the
  `//` block). Only the CRLF line ends are normalized; the content is
  byte-exact, 1559 chars, and the REPL confirmed 1559. `ProblemInfo.desc`
  ("A boolean version of the wildfire fighting domain.") is a sentence of the
  header, so nothing was added.
- `step1-language-card.txt`: the session-only formalize system prompt. It is
  the elevators v3 card (generic grammar plus a toy bakery, with no domain
  content) plus ONE generic paragraph carrying the formalization doctrine:
  model the mechanism, not the ledger; no per-value unrolling or token
  multiplicities; deterministic consequences in a settle stage; no invented
  rates or instance facts; illustrative instances flagged in `%`.
- `seat-claude.sh`: the contained `claude -p` seat (no tools, no MCP, no
  settings, no persistence, `claude-opus-5-5`), as used for elevators.
- `step1-transcript.md`: the full terminal session. It is the REPL's own
  `transcript` (the lab notebook), logged from the first command.
- `step1-candidate-from-formalize.llp`: exactly what was accepted (`export`
  of the world).
- `wildfire_born.llp`: **the born catalog.** It is the candidate's body
  byte-identical, under the source header carried verbatim as `%` comments
  (the provenance doctrine).

## The session

The terminal `metis` ran on a blank scratch world, inside tmux session
`wildfire` (attach to watch), with `METIS_CONFIG=` (hermetic).

1. `transcript step1-transcript.md`; `llm command:…/seat-claude.sh`;
   `formalize system <<EOF` (the card, 4848 chars); `text <<EOF` with the
   header and `EOF` (1559 chars).
2. `formalize`: **1 round, green, "gated_as: revise (base edit)", no
   findings, about a minute.** All three elevators loop fixes held. The
   card prevented the cold start, and a blank world gates as revise. No
   directive problem: the candidate's `#init`/`#steps` were adopted on
   accept.
3. `accept`: key `4f579c52…`, with 22 `#init` lines and `#steps 40` adopted.
4. `trace` (seed 1, 40 events, 22 beats): see_fire tallies → `counted` →
   ignite branches → `spreaded` → `put_out` → `managed` → refresh/rest →
   `stepped` → the next count. At beat 18, `reach_target[C=c11]`: the fire
   reached the target.
5. The born file re-gated with its own scenario: ok, **class-F candidate**,
   no findings, no warnings. Scenario support is 8 states at 8 steps and 1515
   at 16.

## The born catalog (what the prose became)

- Four stages in a qui cycle: `count → spread → manage → reset` (lockstep).
  The seat built the synchronous step itself, as a cycle of settle stages;
  nothing taught it RDDL's tick.
- k ("the number of neighbors on fire") is a **walked path, not unrolled**.
  It is `tally(cell, nbcount)` over a `bwd next(k0..k8)` chain: `see_fire`
  steps the tally up once per burning neighbor (`seen`/`unseen` marks), and
  `unsee_fire` steps it back down when a neighbor is put out. This is the
  doctrine's bridge-declarative shape, produced unprompted by any example of
  it.
- `ignite`: `fresh(C) * $tally(C, K) -o (burning(C) @w 1 | held(C) @w 1)`.
  It **reads K but prices nothing with it.** The seat wrote that "the
  logistic in k is not expressible as a literal weight without per-k rule
  variants; k is read here so the law can be attached as data, and the
  choice uses the default weights until then." The doctrine held: no invented
  numbers, and no per-k unrolling. See finding 1.
- Manager: `put_out` (crew × burning → extinguished) or `idle`, one crew
  action per step. `reach_target` marks a burning target `lost`.
- Instance facts are illustrative and flagged in `%`: a 2×2 Moore grid
  (c00..c11), target c11, one cell burning, one crew.

## Fidelity against the RDDL cpfs (for the checkpoint — recorded, not fixed)

The header is all the seat saw. These are the gaps between the born
catalog and the generator (`domain.rddl` cpfs and instances). They are
what step 2's surprise loop should find:

1. **Ignition rate is flat 1:1.** P(ignite) = 0.5 for every k, k=0
   included. The truth is 1/(1+e^(4.5−k)): k=0 gives 0.011, k=1 gives 0.029,
   k=4 gives 0.38. A cell with NO burning neighbor ignites half the time
   here. This is the largest surprise source, and the notch target (see
   finding 2).
2. **Targets ignite only next to a burning neighbor** (the "Modification"
   in the cpfs). The header doesn't say so; the catalog has no such guard.
3. **`cut-out` and `out-of-fuel` are absent.** The header describes the
   fire, not the actions. The actions live in the pvariables/cpfs, which the
   seat never saw. Burned cells: RDDL burning persists until put out (this
   matches), and out-of-fuel blocks re-ignition (here `extinguished`
   matches for put-out cells).
4. **One crew action per step is invented.** RDDL allows concurrent
   actions, capped per instance by max-nondef-actions.
5. The topology (Moore 2×2) and the target placement are illustrative.
   The instances define NEIGHBOR and TARGET, and the recorder will speak
   them.

## Findings (step 1)

1. **The weight-port case, met in the wild.** The header states a
   NUMERIC law over a count (`p = 1/(1+exp(4.5−k))`). Under the doctrine,
   the honest literal-weight catalog cannot carry it: per-k variants are
   forbidden, and token multiplicities distort the measure. The seat
   correctly left it as "data to attach". Two routes for step 2a:
   - (a) A port, `weight pign(K) reads {}` on `ignite`, bound by a
     registry (the step-1 port-plugins work makes this serveable now). Its
     notch rows are per-K, and the ground truth is the logistic per k.
   - (b) Literal per-K weights fitted by notch, which needs per-K rule
     instances. This is an architect/user call.

   Note: the shelf table's "4 real (spread/ign.)" notch targets are the
   COST/PENALTY non-fluents, i.e. reward parameters. They are not dynamics,
   and metis grounds without reward. The real dynamics ground truth is the
   logistic (offset 4.5, slope 1 in k), scored per k from episodes.
2. **Loop health: the elevators fixes held.** It went green in one round
   on a blank world (the card, revise-gating, directive adoption). No
   timeout and no parse starvation.
3. The born world has no source of fuel loss besides put-out, so a cell
   held at k=0 re-rolls every step. With finding 1, an unattended 2×2 grid
   burns out fast: the trace hits `reach_target` by beat 18.

## Acceptance (step 1)

The catalog gates green from the header alone (formalize/revise ok, no
findings; the born file re-gates ok, class-F). The transcript is kept.
**The human checkpoint is pending (the user).** Step 2 (the pyRDDLGym
episodes through `rddl_recorder.py`) waits for it.
