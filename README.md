# method-layer

Two small, **preference-free** Python tools for preserving candidate generators and ranking options by declared, re-runnable physical criteria. This repository is a notation and ranking layer, **not a simulation repository**.

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

## Validation

Run the dependency-free test suite from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

## License

[CC0 1.0 Universal](LICENSE). No attribution is required.
