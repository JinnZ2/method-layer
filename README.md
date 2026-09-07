# method-layer

Four small, **preference-free** Python tools for preserving candidate generators, ranking options by declared, re-runnable physical criteria, detecting a rank change instead of declaring one, and estimating a reader's frame from hand-authored probes. This repository is a notation and ranking layer, **not a simulation repository**.

```text
simulations (G)  ->  method-layer (F)
method-layer (F) ->  nothing
```

The implementation uses only the Python standard library, has no runtime dependencies, and can be copied directly into a Python 3 environment.

## Tools

### `branch_set.py`

`branch_set.py` serializes a held set of candidate generators so it survives transport to a model or a reader. Collapse to a single hypothesis happens at **measurement**, not at intake. The schema version is `1.0` and is versioned independently of the ranking layer.

The intake rule is upstream of both tools:

> When **N generators fit one result**, priority rises. The cheapest discriminator runs first, not the most central one. Each elimination is itself a result.

A branch retains its generator, origin pattern, predicted divergence, discriminator, cost, state, suppression metadata, distant predictions, and instrument history. `test_queue()` returns open branches by ascending cost. `eliminated_set()` keeps full eliminated records. `gap_list()` returns distant predictions whose record presence is unknown.

Each distant prediction must use a domain different from the branch's `origin_pattern`. In schema `1.0`, `origin_pattern` therefore serves as the canonical origin-domain identifier for this validation. The explicit `record_state` enum accompanies unknown record-presence entries because the three-state `already_in_record` field alone cannot deterministically produce the four required triage outcomes.

`triage()` reads **only** `record_state` and `suppression_cause` to choose a result. It prints and returns the rule used:

| Record state | Result |
|---|---|
| `instrument_exists_unrun` | `answerable_now` |
| `components_exist_unassembled` | `buildable` |
| `no_measurement_needed` | `simulable` |
| `missing_piece` | `blocked(prior)` or `blocked(access)` |

Long instrument lag is exposed as `lag_days`. It records **access suppression, not difficulty**.

### `preference_free_rank.py`

`preference_free_rank.py` imports `branch_set` and ranks an option set without weights or a hidden utility function. It uses unweighted **Pareto fronts**: an option moves ahead only when it is no worse on every declared criterion and strictly better on at least one. Options with any non-score return class remain unresolved peers; they are never treated as inferior.

The supported criterion identifiers are:

- `bits_returned_per_energy`
- `reversibility`
- `cost_asymmetry`
- `dependency_added`
- `cycle_survival`

Every `CriterionSpec` must declare a validity predicate and boundary behavior. The measurement function is never called outside that envelope. An out-of-envelope application returns `OUT_OF_ENVELOPE`, never a score.

Return classes are peers:

- `SCORED`
- `UNKNOWN_measurable`
- `UNKNOWN_buildable`
- `UNKNOWN_simulable`
- `BLOCKED(blocker)`
- `OUT_OF_ENVELOPE`
- `VARIABLE_UNIDENT`

A caller may supply an external, non-learned `TerminalCriterion` as a physics floor and a cheap rollout function. The result records the rollout depth reached before envelope exit. `credit_assignment` reports which strictly improved criteria establish each dominance relation.

### `rank_detector.py`

`rank_detector.py` turns `S = (ρ, T, rank)` from notation into a measurement. Two mechanisms produce the same observation, "more visible structure":

```text
resolution artifact          dimensional activation
new points ON manifold       new points OFF manifold, one direction
dim(k) flat                  dim(k) steps UP toward fine k, then holds
more samples -> same rank    finer SCALE -> higher rank
```

The discriminator is not sample count. It is whether local intrinsic dimension varies with **scale** while sample density is held fixed. `RankDetector.detect(points)` keeps the point set fixed, sweeps a neighbourhood radius `k`, estimates local dimension at each `k` by the PCA participation ratio of the neighbourhood covariance (median over seeded centers; stdlib Jacobi eigen-solver), and reads the resulting `dim(k)` curve:

| Curve | Outcome | Return class |
|---|---|---|
| flat | `flat` (resolution only) | `SCORED` with the plateau rank |
| step + plateau, fine side higher, one direction | `activation` at `k_step` | `VARIABLE_UNIDENT` |
| step + plateau, fine side higher, isotropic gain | `noise_floor` | `UNKNOWN_measurable` |
| step + plateau, coarse side higher | `coarse_rise` (curvature / fold) | `UNKNOWN_measurable` |
| monotone drift | `ambiguous` | `UNKNOWN_measurable`, never scored |
| noisy, no plateau, or too few valid scales | `blocked` | `BLOCKED(sample_floor)` |

Every result carries the `rule` that fired and the full curve. On `activation` the result carries an `ActivatedDimension`: `scale_of_appearance`, `direction` (the eigenvector in the coarse-scale null space that gains variance), `prior_variance` (its coarse-scale variance fraction, expected near zero), `consistency` across centers and `null_space_isotropy`. `DetectionResult.to_criterion_result()` is the seam into `preference_free_rank`; a named activated dimension is a previously-collapsed variable entering the record.

**Null construction.** `null_suite()` generates manifolds of known rank with no activation under anisotropic noise, curvature and nonuniform density, each of which can fake a step, and reports the detector's own false-positive rate alongside a positive control. Run it before real use:

```sh
python3 rank_detector.py null
```

Known limit: with only one normal direction, off-manifold noise and a real activation are the same geometry. With two or more normal directions the isotropy of the null-space gain separates them.

**Order test.** `order_test(points, k_in, k_out)` compares zoom-in-then-out (`crop` then `coarse_grain`) against zoom-out-then-in on one record and returns the commutator of the recovered dimension reading. Zero is a real result; on the synthetic manifolds it is zero within tolerance whenever the coarse-grain scale sits below the reading scale.

**Output to F.** `mechanism_branch_set()` files the three mechanisms behind "more visible structure" as one `BranchSet` with a shared origin pattern and the `dim(k)` curve as the discriminator:

```text
undersampled            dim rises with sample count at fixed scale
scale_suppressed        dim(k) steps up toward fine scale; sample-count invariant
dimensionally_collapsed dim(k) flat and sample-count invariant; appears only in a new record
```

`eliminate_from_outcome(branch_set, detection, density_sweep(...))` records eliminations from one reading; ambiguous, blocked and coarse-rise readings eliminate nothing.

Scope-out (zoom out as connection density to neighbouring structures) is a graph measurement, not a manifold one. It is flagged in `SCOPE_OUT_NOTE` and not started.

### `frame_probe.py`

`frame_probe.py` estimates which frame a respondent reads a term under. The probe library is **hand-authored input**; the module runs selection and collapse reading only.

```text
hand-authored probe library  -->  frame_probe.py  -->  frame estimate
(input, author_kind: human)       selection + collapse reading ONLY
```

This partition is load-bearing. A model generating its own probes reads its own frame back and calls it a finding. The module contains no probe generator, `Probe` rejects any `author_kind` other than `human`, and no probe library ships with the repository.

A probe record carries `term_or_phrase`, `sense_space`, `frame_index` (sense to frames), `emitter_marker_load` in `[0, 1]` (does emitting the probe declare the prober's frame), `author`, `author_kind`, and `calibration` (per known frame, the observed collapses of respondents in that frame).

**Validity gate, runs first**, per probe, with declared thresholds:

| Check | Result |
|---|---|
| `emitter_marker_load >= 0.5` | `BLOCKED(contaminated)` |
| calibration too thin to compute variances | `BLOCKED(uncalibrated)` |
| between-frame / within-frame variance `>= 4` | `valid` |
| ratio comparable to 1 | `UNKNOWN_measurable`: the probe reads the person, not the frame |

**Loop.** `FrameProbeSession.next_probe()` selects the unspent valid probe with the greatest separation of the remaining frame set (expected remaining size under a uniform prior; no importance weighting). `observe(probe_id, senses)` reads the collapse as `collapsed`, `held`, or `partial` and narrows to the frames consistent with every observed sense; frames a probe does not speak to survive it. The session stops on confirmation (one frame), on `UNKNOWN_measurable` (contradiction, or no valid probe separates the rest), or on `BLOCKED(probe_budget)`. `result()` returns the frame estimate, the remaining set and the probes spent.

**Identity model.** `grade_identity()` reads three behavioural observations and nothing interior: cost paid at a frame boundary, prior frames defended after exit, context-variance reported as conflict. All high reads `fixed_position`; all low reads `instrument`; anything mixed or unobserved is `UNKNOWN_measurable`. A graded model always arrives with `identity_null_branch_set()`: what else produces the same three observations, filed as an open, untested `BranchSet`.

**Known failure, encoded.** `identity = instrument` read as inconsistency, evasion or masking, followed by a search for the "real" identity underneath. Same shape as assuming a value exists, finding none, and reporting absence instead of the wrong instrument. `underlying_position()` and `label_reading()` return `OUT_OF_ENVELOPE` tagged `WRONG_INSTRUMENT` for an instrument-graded subject; the registry is `KNOWN_FAILURES`.

**F addition.** `term_branch_set(probe)` files a term with N live senses as N branches with one origin pattern. `term_intake_queue(library)` orders terms by sense count: N senses raises priority, the same intake rule as mechanisms.

**Coupling record.** Does a model collapse an ambiguous term to one sense or hold all senses as jointly intended, one term, one turn. `CouplingLog` keeps one entry per model per update boundary; `coupling_record.json` is seeded with GPT holding on 2026-09-07.

```sh
python3 frame_probe.py gate library.json
python3 frame_probe.py run library.json --frames F1 F2 F3   # observed senses on stdin
python3 frame_probe.py identity --boundary-cost low --defended low --conflict low
python3 frame_probe.py intake library.json
python3 frame_probe.py coupling coupling_record.json
```

## Example

```python
from branch_set import (
    Branch,
    BranchSet,
    PredictionElsewhere,
    RecordPresence,
    RecordState,
    SuppressionCause,
)
from preference_free_rank import (
    CriterionName,
    CriterionSpec,
    Direction,
    rank_branch_set,
)

branches = BranchSet([
    Branch(
        id="g-1",
        generator="shared transport bottleneck",
        origin_pattern="cell-biology",
        predicted_divergence="signal changes before bulk concentration",
        discriminator="measure transport latency",
        cost=2.0,
        suppression_cause=SuppressionCause.PRIOR,
        predicts_elsewhere=[
            PredictionElsewhere(
                pattern="matching lag",
                domain="ecology",
                already_in_record=RecordPresence.UNKNOWN,
                record_state=RecordState.INSTRUMENT_EXISTS_UNRUN,
            )
        ],
    )
])

# Lossless JSON transport.
restored = BranchSet.load(branches.serialize())
assert restored == branches

# Triage prints: instrument_exists_unrun -> answerable_now
triage_results = restored.triage()

criteria = [
    CriterionSpec(
        name=CriterionName.BITS_RETURNED_PER_ENERGY,
        direction=Direction.MAXIMIZE,
        valid_envelope=lambda branch: branch.cost > 0,
        out_of_envelope="undefined at zero discriminator cost",
        measure=lambda branch: len(branch.predicted_divergence) / branch.cost,
    )
]
ranking = rank_branch_set(restored, criteria)
print(ranking.fronts)
```

Detecting rank from a point cloud instead of declaring it:

```python
from rank_detector import RankDetector, null_suite, thick_manifold

print(null_suite().format())  # false-positive rate first

points = thick_manifold(3000, 1, 3, thickness=0.1, seed=2)
result = RankDetector().detect(points)
print(result.outcome.value, result.rule)       # activation, step ... at k_step≈0.1
print(result.activated.direction)              # the activated direction
print(result.to_criterion_result().return_class)  # ReturnClass.VARIABLE_UNIDENT
```

## Validation

Run the dependency-free test suite from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

## License

[CC0 1.0 Universal](LICENSE). No attribution is required.
