# ui — voice navigation over the loop console page, lifted

Two files make the domain. **`ui_domain.llp` is the lifted base**: every rule of voice
navigation over any widget tree — focus as one linear token (the root when nothing
else), the browser's focus events as the input port, widget-local commands before
global ones, modal dialogs that hold the focus, picks by name or by number with an
explicit ambiguity state, show and hide, command and dictation modes, and a refusal
with its reason for every command no rule took. **`ui.llp` is the concrete
extension**: it includes the base and adds only facts — the loop console's widgets as a
type, the tree (`child/2`), the roles (`role/2`), the dialog's entry (`entry/2`) — and
the start. It adds no rule. The design is grounded in the research report on the
subject (docs/voice-ui-research.md): its eight principles are the base's sections.

The navigation agent (metis-agent, Gemma E2B, local — the NAVIGATION brain, never the
formalization brain) types the person's words into one command. **The host is the
page**: a fired rule's event is a frame the page carries out (focus a widget, show or
hide a dock, number a list, pick an entry), and the page reports back through the
input port.

| file | what |
|---|---|
| `ui_domain.llp` | the base: types `role`, `act`, `mode`, `num`; the facts an instance supplies (`child`, `role`, `entry`); `inside/2` by Horn rules; the stage pipeline `clear → sync → local → global → post` with its `qui` links; every rule with its `%%` line |
| `ui.llp` | the loop console: 21 widgets (ids in comments), the tree, the roles, `entry(apply, apply)`, the start. The dialog panel (fsttm-web's, the one input) is the dock `talk` (#dock-talk): `dialog` is a role of the base and `voice` a word of its rules, so neither names a widget; an instance of another page (the world page, the synthetic page) uses `talk` for its panel too |
| `cases/*.llp` | the cases, each including the program with its init: `ui` (go to catalog), `ui_dialog` (the APPLY dialog refuses exit), `ui_named` (go by name), `ui_mouse` (a mouse focus drops the numbers), `ui_pick` (a pick after a mouse focus into the list), `ui_absent` (a GO or SHOW to a widget the page does not have now is refused), `ui_present` (the same widget present and hidden: shown first, then focused), and the rest of `cases/` |
| `intent.yaml` | the card: GO(widget), EXIT, HOME, BACK, PICK(name | number), NUMBERS, SHOW(widget), CLOSE, CANCEL, MODE(to), HELP, UNKNOWN |
| `intent/ui-corpus.tsv` | 91 rows: the examples and held-out paraphrases, the REPL's commands as UNKNOWN here |
| `ui_host.py` | the page as host (the implementer's), below |

## The input port (the page → the model)

Widgets that know their own activation report it. The page registers `focusin` on the
document (mouse and keyboard produce the same events; the model cannot tell and must
not), coalesces one `+enter(W)` per focus change, sends `+blur` when the focus leaves
every widget (the viewport), `+opened(D)` / `+closed(D)` when a dialog rises or falls,
`+shown(W)` / `-hidden(W)` (and the reverse) when it shows or hides a dock itself, and
`+picked` / `+nothing_picked` / `+ambiguous` as the answer to a pick. **When a page takes a domain over** (a reload, a new tab after the old one closed, the
owner changing), the program still holds the old page's state, so the new page reports its
full visible state once when its hello claim succeeds: its real focus (`+enter(W)`, or
`+blur`), every dock's `+shown(W)` / `+hidden(W)`, and for every dialog of the instance
`+closed(D)` when it is not up or `+opened(D)` when it is — the rules then release a modal
the old page left (`dialog_close`) or consume the stray report (`p_closed`); the sampler
starts after that report.

**A widget the page has only sometimes** (v6.5, console-nav step 2 F3: the loop console's
editor needs an open catalog). The page says it on the port, as the pair `present(W)` /
`absent(W)`; the instance starts every widget present, and the takeover report restates
the pair for the widgets the page has only sometimes (`+absent(editor)` while no catalog is
open, `+present(editor)` when one opens). `go_hidden` and `show` take `$present(W)`; a GO or a
SHOW to an absent widget is refused by `p_go_absent` / `p_show_absent`, "{W} is not on the page
now." The instance's own reason (the console: say "load <package>" first) is the page's band
text, not the base's line. `observe()` returns
the page's real `focused(W)`, `shown`/`hidden`, `present`/`absent` and `modal` atoms: a focus change the
port missed — the standards' silent cases (a removed element, `aria-activedescendant`,
the viewport) — is a surprise record.

## The effects (the model → the page)

| event | the page does |
|---|---|
| `go_child`, `go_named`, `go_hidden`, `go_in_dialog`, `exit`, `exit_in_dialog`, `home`, `back`, `move` (no-op: it was the person's), `close` (focus to the parent) | focus the widget (and show the dock first for `go_hidden`) |
| `show`, `close` | show / hide the dock |
| `numbers` | number the focused list's entries 1–9 (an ephemeral bijection, re-derived per pass) |
| `jump`, `jump_to` | page-wide hint mode (Vimium's `f`, Emacs avy): label every reachable actionable widget 1–9 — inside the dialog only while one is up; with a letter, only those whose name starts with it; more than nine → the first nine and say so |
| `jump_pick` | resolve the label; answer `+jumped(W)` (W a widget of the type) or `+nothing_picked` |
| `cancel_*`, `clear_numbers`, `blur_numbers`, `go/exit/home/back_numbers`, `clear_jump`, `blur_jump`, `*_jump` | remove the numbers or the labels (any move, by voice or by hand, invalidates them) |
| `pick`, `pick_n`, `pick_choice` | resolve the payload's name, or the number, against the focused list; answer `+picked`, `+nothing_picked` or `+ambiguous` (and number the candidates) |
| `dictate`, `command`, `mode_back`, `hold_*`, `release` | set the input mode (command / dictation / held) and show it in the band; held = push-to-talk: the voice goes to the page's own channel while the key is down (the page sends cmd_hold / cmd_release as typed intents through the wire's `intent` frame, no model pass) |
| `help` | the words name the focus: "You are in {W}. From here you can say…" |
| every outcome | the replier's words (the rule's `%%` line) |

## Why the pipeline

Each beat is one pass: `clear` drops the transients a manual focus move invalidates
(the numbers, a pending choice), `sync` applies the port to the focus and the dialogs,
`local` serves the focused widget, `global` moves around the tree, `post` refuses what
no stage took, with the reason — so every command is consumed exactly once, most local
first, and no two rules of one command are enabled at once by construction. The
manifest's `clock: {lockstep: true}` makes the watch read once per pass.

`V <> constant` is not in the toolchain yet (metispy refuses it; metisc's run fails),
so guards against the root or a role go through fact tables (`child(P, F)` for "not
the root", `notlist/notdock/noneditable` over the role type); `P <> F` between two
variables works in both toolchains.
