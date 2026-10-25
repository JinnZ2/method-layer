# reasoning-layer

CC0. Standard library only (plus `git`; `unshare` and `setpriv` for runs).
Work order: "Reasoning Layer for the Tool Inventory", issued 2026-10-23.

```text
LAYER 1  APPARATUS.yaml      one entry point; name/shape/read_order/corpus_default_to_avoid = AUTHOR
LAYER 2  cards/<id>.yaml     one card per layer-3 program + the 8 shared tools/*.md documents
LAYER 3  layer3/             the inventory, byte copies, pinned by layer3.sha256; never edited
render   READ_FIRST.md       model-facing; generated, never hand-edited
```

## Energy map

Where content enters, where it is held, where it is refused.

```text
layer 3 ---------------------------------------------------------------+
  | effective row = historical row, overridden by addendum new/changed  |
  | absent paths dropped (kept in the record)                           |
  v                                                                     |
program set  (is_program: .py; not tests/ dir; not test_*.py;           |
              not __init__/conftest; standalone selftests IN)           |
  + CORE_DOCS (the 8 identical tools/*.md named in the work order)      |
  |                                                                     |
  v                         git archive <snapshot commit>, both repos   |
generate.py  ------------>  sha12 of bytes == layer-3 sha12 ?  -- no -> REPORTED, card keeps layer 3
  | static extraction only (ast; nothing executed)                     |
  |   docstring -> purpose   argparse/main() -> input   samples -> output
  |   imports / shared files / sibling selftests / same bytes -> related
  |   run guess: selftest name > --selftest/--example/--demo literal > bare __main__
  |   safety scan: deletes-files | network | credentials -> run blocked
  v                                                                     |
merge with existing card                                                |
  AUTHOR fields   "AUTHOR" written once, when absent; NEVER touched after
  DRAFT fields    {mark: DRAFT, value, basis}: refreshed; a plain value = confirmed, left alone
  integrity       always from layer 3  <----------------------------------+
  run_result      kept while bytes + command unchanged; else reset UNRUN (stale)
  v
run_examples.py   python3 <card's own path> [plain args] only
  sandbox: unshare -n + setpriv nobody (read-only tree) | unshare -rn + chmod a-w | none -> exit 3
  per run: tool's own top folder = disposable writable copy; rest = symlinks, read-only
  60 s, process group killed; first 40 lines captured; exit 0 -> RUN, else FAILED
  v
validate.py       FAIL: pin, schema, integrity, coverage, orphan, run_claim,
                        author_provenance, references, check_record
                  REPORT: AUTHOR gaps per card, disuse
```

Refusals that are deliberate:

```text
AUTHOR field empty          -> "[not yet written]" in READ_FIRST, never a guess
generated text              -> mark: DRAFT, with the basis that produced it
no safe run command         -> UNRUN, with the reason
safety flag                 -> UNRUN, never executed (lexical scan: false positives kept)
FAILED run                  -> run_result FAILED; card status stays UNRUN (FAILED is not RUN)
run command edited by hand  -> executed only in the form python3 <card path> [plain args]
M-gate / R-router /         -> no file in layer 3, so no card and no wrapper; they stay
  architecture audit           UNRUN / PROPOSED where the inventory records them
differing duplicates        -> separate cards, id@sim / id@ml; never merged or cleaned
read_order unset            -> READ_FIRST follows faces order and says it is a filing order
```

## Commands

Run from `reasoning-layer/`. `PATH_SIM` / `PATH_ML` are git clones holding the
snapshot commits (`198937ec...` Simulators, `e9fbfe98...` method-layer);
shallow clones need `git fetch --depth 1 origin <commit>` first.

```sh
python3 generate.py --simulators PATH_SIM --method-layer PATH_ML            # build / refresh
python3 generate.py --simulators PATH_SIM --method-layer PATH_ML --check    # exit 1 if anything would change
python3 run_examples.py --simulators PATH_SIM --method-layer PATH_ML --workdir /tmp [--only ID ...] [--rerun]
python3 validate.py              # exit 0 = no FAIL, 1 = FAIL, 3 = cannot run
python3 validate.py --json
cd .. && python3 -m unittest discover -s reasoning-layer/tests -v
```

`--workdir` must be traversable by `nobody` when running as root (the
exported trees and per-run HOME live there).

## Card fields

```text
field          owner          form
-------------  -------------  ------------------------------------------------
id             generate       slug of the path: lower-case, / -> --, .py dropped;
                              @sim / @ml only when one path differs across repos
kind           generate       program | method_document
tool           generate       <repo>/<path> of the first location
face_of        AUTHOR
purpose        DRAFT          first paragraph of module docstring (or leading comment;
                              documents: first heading + first paragraph)
forces_step    AUTHOR
pick_up_when   AUTHOR
skip_when      AUTHOR
input          DRAFT          argparse calls / main() signature / sys.argv indexing
output         DRAFT          samples/<stem>* files + one line summarising the run capture
run            DRAFT          {value: command or null, basis, safety: [flags]}
run_result     run_examples   {status RUN|UNRUN|FAILED, captured, date, command, sha12, ...}
wrong_read     AUTHOR
right_read     AUTHOR
related        DRAFT          [{id, via}]: imports, imported-by, sibling-selftest,
                              selftest-of, mentions <file>, shares <file> (<= 8 users), same-bytes
selftest       DRAFT          {in_file, sibling, is_selftest}
check_record   problem run    [{run, checked yes|no, result picked_up|skipped, because, date}]
status         run_examples   RUN only with run_result RUN; PROPOSED kept if set by hand
integrity      layer 3        LIST of {repo, path, sha12, commit, last_change, ...}:
                              two entries when the same bytes sit in both repos
_provenance    generate       hash of every value generate.py wrote, per field
```

To confirm a DRAFT field, replace the whole `{mark: DRAFT, ...}` mapping with a
plain value. Generate then leaves it alone. To write an AUTHOR field,
replace `AUTHOR` with text, a `|` block, or a list of strings.

Cards are written in a YAML subset (block mappings and lists, plain /
quoted / `|` scalars, `[a, b]` flow lists, comments). A hand edit outside
that subset makes `validate.py` fail with the line number, so nothing
is silently misread.

## Problem runs (patch 2026-10-25)

```text
problem_runs.yaml   {runs: [{id, problem, date}]}       registered by whoever runs a problem
     |
     v  for EVERY run id, EVERY card carries one check_record entry:
        run: <id>   checked: yes   result: picked_up | skipped   because: <matched condition>   date
     |
validate.py FAIL    a run with any card missing or checked: no       (unrecorded = E3, defaulted slot)
                    skipped with empty because
                    an entry for a run the registry does not list
validate.py REPORT  disuse: cards never picked up across the recorded runs
                    reported only; no card is ever removed for disuse
generate.py         keeps check_record and problem_runs.yaml as found; creates the registry once
```

`because` should name the `pick_up_when` / `skip_when` condition that matched.
While those fields are still AUTHOR, nothing can check that link, so it is not enforced.

## Decisions taken where the work order left room

```text
layer 3 location     byte copies in layer3/ + sha256 pin; no tracked copy existed in either repo
program rule         stated in rl_common.is_program, one clause per outcome; __init__.py and
                     conftest.py are excluded (they appear as Python rows in layer 3)
integrity shape      always a list, so a two-location card and a one-location card share a shape
method documents     the 8 named in section 4 only; the other identical tools/*.md
                     (fitness_bin_self_test.md, telling_installs_the_limit.md) have no card
faces order          8 shared documents, then programs in both repos, then method-layer, then
                     Simulators by path (so by project folder)
cwd for runs         the repository root of the snapshot tree (paths in run are repo-relative)
```

## Out of scope here

- Section 9 evaluation harness: PROPOSED, not built (it needs cards with AUTHOR
  fields written, plus Kavik's problems and rubric).
- Files added to either main branch after the layer-3 snapshot have no card
  until the inventory records them.
