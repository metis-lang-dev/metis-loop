# The loop's policy, once (loop-parity s-72d9d36b)

Two loops write into a catalog: the human loop's console (metis-loop) and pi's
agentic loop (metis-agentic-loop). They are two hosts over one policy: the loop
SDK's `metis_loop_sdk.gate` (Python, and its TypeScript face `ts/gate.ts`, the same
code through the gate's CLI). A rule of the loop changes there, once, and both loops
follow it. The catalog's mechanics under it (plan, apply, edit, take, readme, the
skeleton) are `metis_loop_sdk.catalog`.

## A write is a proposal the person confirms

```
plan = propose(kind, domain, args)    # the files it would write, each with its diff; its token
        the person reads the diff     # console: the apply dialog; pi: ctx.ui.confirm at tool_call
confirm(token)                        # writes exactly that plan
refuse(token)                         # the person said no: remembered
```

The kinds are:

| kind | writes | args |
|---|---|---|
| `program` | the domain's program; a new domain also gets its domain.yaml (program, its host when `<d>_host.py` sits there, clock, records) | `text` (the candidate the loop gated), `display`, `line` |
| `served` | the program the REPL serves, as it is (a seed); a package seed comes whole from the seed's catalog, with its own domain.yaml | `text`, `display`, `line` |
| `extension` | `domains/<d>/extensions/<name>.llp` | `name`, `text` |
| `intents` | intent.yaml and its generated files; without `text`, the program's skeleton (no model); a world without commands gets a note and no write | `text`? |
| `readme` | the README: the person's or model's title and summary paragraph, every other part by the SDK | `text`, `title` |
| `edit` | one exact edit of a file as it is on disk (comments and all; a `.llp` edit adds no diagnostic) | `path`, `old`, `new`, `replace_all` |
| `take` | the domain into another catalog (a README of the run when it has none), then its bundle | `src` |

## The rules

1. **Confirm writes exactly the plan the person read.** A plan is named by its token.
   If its source changed since (the same proposal now plans other texts), confirm
   refuses and nothing is written.
2. **A refused proposal is remembered**, per catalog and file. The next plan of that
   file carries `since_diff`, what changed since the refusal, before its diff against
   the disk. A write of the file forgets it.
3. **Seed first.** In a seeded run (`seed.json` in the loop's state), until the seed's
   domain is in the catalog: no program and no extension of a domain the catalog
   lacks, and the seed is served under its own name only.
4. **README refused.** An edit of a file that was never written, because its proposal
   was refused, goes through the proposal again (its plan shows what changed since).
5. **A plan with nothing to write** (a note) needs no confirmation.
6. **An applied program that won't load never replaces the one served.** The loop goes
   on serving the program it served, its candidate and its session kept, and says why
   the new one did not load. Two mechanisms, as the host attaches:
   - **the kernel's**: metispy's wire `reload [PATH]` re-serves in place, with the host
     as attached. When PATH does not load, it answers `ok: false` with the findings
     and keeps the program, its candidate and the session. When it loads, it serves it
     fresh, as a new open. pi's loop uses it when the host is unchanged.
   - **a new process**, when the host changes: D4 names a host on the operator's argv
     only, never on the wire. The process that was serving keeps serving until the new
     one answers, and stays when the new one cannot load. pi's loop does this for a new
     host; the console builds the new interpreter in-process and replaces the live one
     only when everything compiles.

Where the loop keeps its state: the catalog's `.metis/` (`catalog.state()`). The
gate's memory over a CLI is `.metis/gate.json`; a console keeps it in its process.
