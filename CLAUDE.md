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
                         +-- observer_position_control.py  does a label track the describer's position? nulls first
                         +-- register_map.py           hold declared claims as layers; refuse joins the declarations forbid
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
   - envelope check BEFORE measure                 - NULL CONSTRUCTION FIRST, per regime
   - Pareto fronts, no weights                     - one fixed record; scale = radius
   - non-score classes are PEERS,                  - PCA participation ratio (Jacobi)
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
null run fails       -> BLOCKED(null_construction); regime not scored
noise floor          -> not a named variable; UNKNOWN_measurable
probe reads person   -> UNKNOWN_measurable; contaminated probe -> BLOCKED
instrument identity  -> WRONG_INSTRUMENT (OUT_OF_ENVELOPE), never absence
behaviour differs    -> label difference justified; J returns nothing
confound inseparable -> UNKNOWN_measurable, never a score
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

## observer_position_control.py in one picture

```text
hand-coded source records (input; blind behaviour code REQUIRED)   <-- no corpus ships here
   |
   | null a FIRST: behaviour-match spread across positions >= 0.30 -> BEHAVIOR_DIFFERS, nothing
   | restrict to full-pattern matches
   v
label x position -> p(pathologising) per position; effect = p1 - p3; Cramer's V
   |
   +-- null b decade | c literature | d intensity   MH-weighted within strata
   +-- residual: joint strata, else weakest single (labelled)
         survives >= 0.20  -> OBSERVER_INDEXED  SCORED(residual)
         removed / no overlap -> CONFOUNDED     UNKNOWN_measurable
         thin              -> UNKNOWN_measurable
prediction registered in the module; reported against the result, never returned as it.
```

Do not add sources, citations, or a corpus to this repository. The synthetic
generator is an instrument check and says so in every record.

## register_map.py in one picture

```text
dict -> load_layer: measurand, range, instrument (incl. harness = datum), grade, resolution
        ALL required or LayerDeclarationError naming EVERY missing field; UNDECLARED sentinel is data
        MEASURED_DISCARDED w/o discard_rule -> loads, FLAG    IMPOSED w/o reason -> loads, FLAG
   |
   +-- can_join(a, b): measurand, range, grade, then instrument LAST (datum offset)
   |     COMMENSURABLE | INCOMMENSURABLE(field) | UNDECLARED(field)   never one return; full table kept
   +-- project(layer, coarser): coarsen ONLY, integer factor ONLY, never upsample
         every drop -> Discard(coarse_cell, source_cell, value, rule); result grade MEASURED_DISCARDED
blanks: NODATA (exists, unmeasured) / NOTFOUND (measured, nothing) are VALUES and survive project()
out of scope, designed for: directionality read from discards and blanks. Not implemented.
```

## rank_detector.py in one picture

```text
resolution artifact          dimensional activation
new points ON manifold       new points OFF manifold, one direction
dim(k) flat                  dim(k) steps UP toward fine k, then holds
more samples -> same rank    finer SCALE -> higher rank

instrument: ONE record, sweep radius k, read the curve.
  density control = radius not neighbour count; rho constant; floor scales
  marked invalid, never widened. Sample count is a separate axis.

null construction (runs inside detect(), before any reading is released):
  anisotropic noise | curvature | nonuniform density | combined -> must not read activation
  positive control: thick_manifold at 8 x floor radius            -> should read activation
  print: FP rate per confound, step each produced, threshold to clear the worst
  any confound reads activation -> BLOCKED(null_construction), regime refused

direction of activation = top eigenvector of the GAIN operator
  G = C_fine/tr - C_coarse/tr ; isotropy = g2/g1 ; prior variance read on C_coarse
plateau = flat relative to its ramp; a same-sign sloped tail is a drift

order test: crop (zoom in) vs coarse_grain (zoom out)
  commutator on the dim reading; 0 is a real result
scope-out (graph / connection density): flagged, not started
```

Known limits (the docstring carries the full list; keep it current):
with only one normal direction, off-manifold noise and a real activation are
the same geometry; two activations read AMBIGUOUS; rank-2 activations at
pure-Python sample sizes read AMBIGUOUS (window ~1 decade, boundary
anisotropy). Say this when it matters; do not paper over it.

Every threshold in `RankDetector.__init__` has a row in the docstring table
naming the null run that set it. Change a threshold -> re-run
`python3 rank_detector.py null` and `--rank 2`, update the row, say why in
the commit message. Synthetic generators: on-manifold noise moves the point
ALONG the patch; a normal term evaluated at the unperturbed position is a
real thickening, not noise.

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
python3 rank_detector.py null --rank 2            # prints the rank-2 positive-control limit
python3 rank_detector.py detect points.json       # null first, then the dim(k) reading
python3 rank_detector.py order --synthetic flat 0.3 0.03   # commutator as a finding
python3 frame_probe.py gate library.json          # validity gate over a hand-authored library
python3 frame_probe.py identity --boundary-cost low --defended low --conflict low
python3 observer_position_control.py synthetic --effect 0.6    # instrument check
python3 observer_position_control.py run corpus.json           # hand-coded corpus
python3 register_map.py join a.json b.json --json              # structured join verdict
python3 register_map.py project layer.json --to 4              # coarsen; every discard carries its rule
```
