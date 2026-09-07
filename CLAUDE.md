# CLAUDE.md

Guidance for working in this repository. Public; nothing here is private.

## What this repository is

A **method layer (F)**: notation, transport, ranking and detection tools
that sit downstream of simulations and upstream of nothing.

```text
simulations (G)  -->  method-layer (F)  -->  nothing
                         |
                         +-- branch_set.py           hold N generators, triage gaps
                         +-- preference_free_rank.py rank by Pareto fronts, no weights
                         +-- rank_detector.py        detect delta-rank from dim(k), never declare it
                         +-- frame_probe.py          select hand-authored probes, read collapse, estimate frame
```

It is **not** a simulation repository. No physics is modelled here; the
tools only preserve, order, and measure what a caller supplies.

## Hard constraints

```text
python >= 3.8, standard library ONLY      no numpy, no pip, no runtime deps
pure functions + dataclasses + str Enums  every record has to_dict / from_dict
deterministic                             every random draw takes a seed
tests: python3 -m unittest discover -s tests -v   must stay green, < ~10 s
license: CC0                              no attribution, nothing proprietary
```

## Energy map of the layer

Where information flows, where it is held, where it is refused.

```text
                     intake: N generators fit one result
                                   |
                     BranchSet (lossless JSON, schema 1.0)
                     - eliminated records are KEPT, never dropped
                     - test_queue(): cheapest discriminator first
                     - triage(): reads record_state + suppression_cause ONLY
                                   |
             +---------------------+----------------------+
             v                                            v
   preference_free_rank                            rank_detector
   - envelope check BEFORE measure                 - fixed sample density
   - Pareto fronts, no weights                     - sweep scale k
   - non-score classes are PEERS,                  - PCA participation ratio
     never collapsed into a score                  - read dim(k): flat / step / drift / noisy
             |                                            |
             v                                            v
   RankingResult                                   DetectionResult
   fronts + unresolved + credit                    outcome + rule + curve
                                                   ACTIVATION -> VARIABLE_UNIDENT (to G)
                                                   mechanisms -> BranchSet    (to F)
```

Bottlenecks and refusals are deliberate:

```text
envelope exit        -> OUT_OF_ENVELOPE, never a score
unknown / blocked    -> stays unresolved, never ranked below a scored option
dim(k) drift         -> UNKNOWN_measurable, never scored
below sample floor   -> BLOCKED(sample_floor)
noise floor          -> not a named variable; UNKNOWN_measurable
probe reads person   -> UNKNOWN_measurable; contaminated probe -> BLOCKED
instrument identity  -> WRONG_INSTRUMENT (OUT_OF_ENVELOPE), never absence
```

## frame_probe.py in one picture

```text
hand-authored probes (input, human only)   <-- NEVER generated here
   |
   | gate FIRST: emitter load high -> BLOCKED(contaminated)
   |             between/within ~ 1 -> UNKNOWN_measurable (reads the person)
   v
select for MAX separation of remaining frames (not importance)
observe collapse: collapsed | held | partial  -> narrow
stop: one frame | UNKNOWN | budget
   |
   +-- identity: 3 behavioural observations -> fixed_position | instrument | UNKNOWN
   |   null set REQUIRED, filed open + UNTESTED
   +-- known failure: instrument read as evasion -> WRONG_INSTRUMENT, never ABSENCE
   +-- F: N live senses = N branches, one origin; N raises priority
   +-- coupling_record.json: collapse vs hold, per model per update boundary
```

Do not write probes, probe libraries, or example probe files into this
repository. Tests use fixtures labelled as such; that is the limit.

## rank_detector.py in one picture

```text
resolution artifact          dimensional activation
new points ON manifold       new points OFF manifold, one direction
dim(k) flat                  dim(k) steps UP toward fine k, then holds
more samples -> same rank    finer SCALE -> higher rank

instrument: hold density fixed, sweep k, read the curve.

null construction (required before real use):
  anisotropic noise | curvature | nonuniform density  -> must read flat
  positive control: thick_manifold                     -> must read activation
  report false-positive rate; do not hide it

order test: crop (zoom in) vs coarse_grain (zoom out)
  commutator on the dim reading; 0 is a real result
scope-out (graph / connection density): flagged, not started
```

Known limit: with only one normal direction, off-manifold noise and a real
activation are the same geometry. With two or more, the null-space isotropy
gate separates them. Say this when it matters; do not paper over it.

## Conventions when editing

- Keep the module docstring diagrams current; they are the spec.
- Every classification returns a `rule` string naming the tolerance that
  fired. Declared tolerances only; never fit them to a dataset in a test.
- New return classes are peers of the existing ones. Do not add ordering.
- New records: frozen dataclass where possible, `to_dict()`, enum values
  as strings, validation in `__post_init__`, `_check_keys` on load.
- Tests are synthetic and seeded. If a threshold needs changing, change it in
  the constructor default and say why in the commit message.
- README documents the user-facing surface; CLAUDE.md documents the shape.

## Commands

```sh
python3 -m unittest discover -s tests -v          # full suite
python3 rank_detector.py null                     # null construction report
python3 rank_detector.py null --rank 2 --n-points 3000 --positive-thickness 0.2
python3 rank_detector.py detect points.json       # read a dim(k) curve
python3 rank_detector.py order points.json 0.3 0.03
python3 frame_probe.py gate library.json          # validity gate over a hand-authored library
python3 frame_probe.py identity --boundary-cost low --defended low --conflict low
```
