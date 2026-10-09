# RDDL elevators — step 1 results: a catalog born from prose (2026-10-08)

Artifacts (this directory): `step1-transcript.txt` (the full terminal
session, pty-driven `metis`, verbatim), `step1-language-card.txt` (the
session-only formalizer prompt, verbatim), `step1-candidate-from-
formalize.llp` (what the formalizer emitted and `revise` gated green),
`elevators_born.llp` (the born catalog: that candidate's catalog body
byte-identical, its own `#init`/`#steps` with ", " → "," inside atoms).

## Setup

- World: rddlrepository `Elevators_MDP_ippc2011` (IPPC 2011, the
  version pyRDDLGym will run; `domain.rddl` from the installed
  rddlrepository). Seed text = its header, lines 1–27, VERBATIM (the
  `//` comment block). `ProblemInfo.desc` ("This domain has a number of
  elevators delivering passengers to either the top or the bottom
  floor.") is a sentence of the header — nothing to add.
- pyRDDLGym + rddlrepository installed into the venv via metispy's
  declared `sysadmin` extra.
- Terminal: `metis` with no file (blank scratch world), driven in a
  pseudo-terminal (readline, heredocs exactly as typed).
- Formalize seat: `llm command:claude -p --tools "" --strict-mcp-config
  --setting-sources "" --no-session-persistence --model
  claude-opus-5-5` (default effort). Plain `claude -p` also works
  (stdout is clean, 4.4 s for a one-word reply) but hands the
  formalizer the built-in tools and the project/user settings; the
  contained form is a pure completion (2.8 s).

## The session (see the transcript)

1. `llm …`; `text <<EOF` header `EOF` (1393 chars).
2. `formalize` — 4 rounds, FAILED: `parse: 2:17: expected ., got '1'`.
   The model invented a language: dotted names (`elevators.at`),
   `const`, a `rule` keyword, `persistent`, `extends scratch 1.`.
3. `formalize system` → the prompt is two lines (built-in default and
   the user's `~/.config/metis/prompts/formalize.txt` alike); the
   formalizer's only syntax reference is the BASE vocabulary — on a
   blank world, an empty stage.
4. `formalize system <<EOF` — a session-only LANGUAGE card (generic
   grammar + a toy bakery example, checked to compile; no domain
   content; approved by the architect as fair).
5. `formalize` — one claude -p call exceeded the backend's 600 s
   timeout (`TimeoutExpired`). Re-measured outside the REPL: the same
   prompt took 29 s; the retry in the REPL ran 4 rounds in 1 m 45 s.
   A one-off stall, not effort — default effort kept.
6. `formalize` — 4 rounds, FAILED: `pack adds stage 'run' — stage set
   is the kernel's` (every round).
7. `revise` — the same candidate gated as a BASE EDIT: ok, no findings,
   "unclassified (no scenario provided)".
8. `accept` — key f89a2f6e…; `trace` → "no #steps directive".
9. The candidate's own `#init`/`#steps` sent as REPL lines: the
   `#init at(e0, f0) 1` form is "bad directive" (space inside the
   atom); re-sent with ", " → "," — a mechanical whitespace fix.
10. `trace` (seed 1, 60 events, 13 beats): arrivals, moves, open/turn,
    close, board (#7 `board[E=e1,F=f4,D=down,X=bottom]`), first
    delivery at beat 13 (`alight[E=e0,F=f4,X=top]`).
11. `save elevators_born.llp` wrote the BLANK scratch body + the
    current state (finding 7) — the born catalog was rebuilt from the
    accepted candidate (body byte-identical, verified by diff); it
    serves in a fresh `metis` (key 6a498be59c12 with its init) and is
    diagnostics-clean in metisc.

## The born catalog (what the prose became)

One stage `run`, one layer; types elevator {e0 e1}, floor {f0..f4},
dir, dest {top bottom}; resources at/closed/open/heading/free/waiting/
riding/delivered; Horn tables step(dir,floor,floor), opposite,
toward(dir,dest), goal(dest,floor), busy(floor), quiet(floor). Rules:
arrive_busy / arrive_quiet (⊕: arrival vs none), move, noop, open_same,
open_turn, close, board, alight — every one with a %% doc quoting the
header.

## Findings (step 1)

1. **Cold-start gap (loop defect).** On a blank world the formalizer
   has NO language reference: FORMALIZE is two lines and syntax is
   learned only from the base vocabulary. Recommendation: the prompt
   builder ships a built-in LANGUAGE card (spec 00's grammar + one toy
   example) whenever the base vocabulary is below a threshold — home:
   the prompts/formalize.txt layering — so blank-world formalization
   works out of the box.
2. **Repair signal starved by the first parse error.** Each failing
   round reported only `parse: 2:17 …`; the model never learned how
   much of its candidate was unparsed. Recommendation: say "parse
   stopped at line N; the rest of the candidate is unchecked".
3. **The repair loop gates the wrong mode on a blank world.**
   `formalize` always gates as a PACK against the served world, so a
   base-shaped catalog fails every round ("pack adds stage") even
   though `revise` passes it at once. Recommendation: on a blank (or
   explicitly replaced) world, formalize's rounds gate as `revise` does.
4. **The formalizer fabricated instance facts and weights.** The prose
   names no counts or rates; the catalog asserts 2 elevators, 5 floors,
   floors f0/f2 "busy" and f1/f3/f4 "quiet", arrival weights 0.4 / 0.1,
   move @w 2, board/alight @w 3, noop @w 0.2. All invented — the
   no-invented-weights doctrine says weights come from data: step 2a's
   notching against the instance's ARRIVE-PARAM is exactly the check.
5. **Directives don't survive revise/accept.** The candidate's own
   `#init`/`#steps` were not adopted as the session's case; the world
   was born with no scenario.
6. **`#init ATOM N` rejects a space inside the atom** (`at(e0, f0)`)
   — the formatting the model naturally wrote; the card's toy example
   happened to show no multi-argument `#init`.
7. **`save` after a blank-world accept writes the blank body** (the
   served FILE's text) plus the current state; `export` is the verb for
   the accepted world — a trap for exactly this workflow.
8. The 600 s backend timeout fired once (step 5); not reproducible (29 s
   and 1 m 45 s for 4 rounds on re-measure).

## Observation for step 2 (recorded, not acted on)

The arrival ⊕'s "no arrival" branch is an ordinary EVENT: each
"Bernoulli draw" happens per fired event, competing with moves, not per
time step — the trace is full of `arrive_quiet-2`. That is the
interleaving-vs-tick gap the experiment wants the surprise loop to
DISCOVER; per the brief, nothing was pre-taught.

## Acceptance (step 1)

Catalog gates green from the header alone (revise ok, no findings;
metisc clean) — with the session-only language card (finding 1) and
two mechanical carry-overs (findings 5–6). Transcript kept. Human
checkpoint: pending.
