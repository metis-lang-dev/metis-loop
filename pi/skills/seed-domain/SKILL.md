---
name: seed-domain
description: The catalog's own loop, without a workspace bundle - formalize a person's prose into a program, make a program or a seed a catalog domain (catalog_new), exercise it (domain_open, intents, the clock; a world without intents through domain_ports and domain_episodes), revise it by an extension, write its README, take it into the person's catalog (catalog_take). Load when the task names a seed, or the catalog has no bundle.
---

# The catalog's own loop

These are the loop's steps as they were driven before the workspace (pi/prompts/loop-system.md up to loop-prompt), with their tools. A seeded start (the task names a seed program) skips formalize: the seed is the person's program. Make it the domain with `catalog_new` program=served, and never change its rules unless the person asks and approves the diff.

1. **formalize**: put the person's prose in the REPL (`repl_text` with the prose as its arg), draft the program (`repl_formalize` with an EMPTY arg: it drafts from the text; its arg would name an LLM backend), check it (`repl_revise` for a whole program, `repl_gate` for an extension) and read the findings; until it passes, change the text and draft again. `repl_show` with arg llp prints the draft; `repl_state` and `repl_show` with arg `base` read what a served program has (its atoms, rules, `#init` and `#query` lines, its header).
2. **new**: `catalog_new` with program=candidate (or program=served for a seed) makes the program a domain of the catalog; give display (its short name) and line (one line on what the world is). The person approves every write: a refused write is their decision, ask what to change. The next proposal of a refused file shows the person what changed since. Once the domain is in the catalog, every change to it is `catalog_edit`, never catalog_new again.
3. **intents**: give `intents: true` in that same `catalog_new`: it drafts the person's verbs from the program (`cmd_*` atoms). A package seed that brought its own `intent.yaml` keeps it; a world without commands gets no intent.yaml, or one that knows only UNKNOWN: the result says which. Say which it is.
4. **exercise**: `domain_open` starts the domain; say intents (`intent_<verb>`), advance time (`domain_clock`), read it (`domain_state`, `domain_why`, `domain_events`).
5. **surprise**: when the world reads differently from the program, a surprise message arrives. Read it, then explain what the program misses: find what the world reported before the difference (`domain_why` on the atoms that changed, `domain_events`: the world's own `do +ATOM` lines) and name it as the cause. A rule whose premise is only the atom that changed (`X -o Y` alone) explains nothing: it says the difference always happens.
6. **revise**: the explanation is an extension of the domain, never an edit of its program. Describe the missing behaviour with `repl_text`: the surprise's words (what the world did that the program does not say), then the extension's shape, exactly: `An extension: catalog <domain>_<name> 1. extends <domain>. stage <stage> with only the new rule(s) and no declarations (the atoms are the domain's).` Formalize drafts what the text asks for: without that line it drafts the whole program again, and the gate refuses a whole program as an extension. Draft it (`repl_formalize`, empty arg; its result says `gated_as: pack`), `repl_gate` it, read it (`repl_show` with arg llp), then write it with `catalog_edit`: path=extensions/<name>.llp, old_string empty (the file is new), new_string the gated text as repl_show printed it.
7. **re-exercise**: `domain_open` again; the same situation must now be explained.
8. **take** (only when the person asks): `catalog_take` with the domain takes it from this loop's catalog into the person's, behind the same approval, with its README.

## A world without intents

A domain without intents (domain_open names no intent verb: a world whose program acts, an RDDL world whose host is a simulator) is exercised through its world, not through intents: `domain_ports` (what its host observes, derives and acts, its gym), `domain_world` (a scenario, in the names domain_ports gives), `domain_clock`, and `domain_episodes` (seeded episodes measured: the outcomes, the program's likelihood of what the world did, the surprises, the mismatched atoms; run the n the task gives, and wait for no other). Record what they show, each surprise and the likelihood as measured; do not fix it with an extension or a weight. Change the program only when it cannot run against its host (it does not load, or cannot read or answer the host's ports), with `catalog_edit`, and say why.

## The README

`catalog_new` writes it from your readme_title (what the world is) and readme_summary (one paragraph: what the program tells); the SDK writes the rest from the files. A package seed that brought its own keeps it. In your paragraph:

- every claim has a source you can name: a rule, a header line, or an output shown in this session;
- one run is one sample: never say what "always" or "only" happens from it;
- quote names exactly as the program writes them (its `catalog` line, its atoms).

To fix what the person points out: while the domain is not yet written (the person refused it), send `catalog_new` again with only that fix; once it is written, `catalog_edit` with path=README.md and the exact old and new text.

## Edits

Every change to a file the catalog already has goes through `catalog_edit`: a comment, a header line, a sentence of the README, a value in domain.yaml or intent.yaml, one rule's text. A file the domain lacks (a first README.md or intent.yaml, an extension) is `catalog_edit` with old_string empty and the whole text as new_string. Never formalize or revise for such a change: they reprint the whole program, and its comments are lost.
