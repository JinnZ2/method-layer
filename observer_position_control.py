"""Observer-position control: is a label set by the behaviour or by the describer?

QUESTION
========
Is the maladaptive / adaptive label set by the behaviour described, or by
whether the describer stands inside the population described?

DESIGN
======
Label extraction, not new observation.  The published corpus is the data.
This module ships NO corpus and NO source list: coding records are
hand-authored input, exactly as probes are in ``frame_probe``.  What ships is
the contingency arithmetic, the nulls, and a synthetic corpus generator used
only to verify that the arithmetic recovers a planted effect and rejects a
planted confound.

Behaviour pattern, held fixed (coded blind to source, per record)::

    high-cost avoidance of affectively-neutral novelty
    + absence of a test phase
    + arousal that does not clear

Describer positions::

    1  human describing a NON-HUMAN species
    2  human describing OUT-GROUP humans (ethnographic, historical, clinical)
    3  human describing their OWN population

Extracted per source::

    label_class        pathology | artifact | adaptation | need | virtue
    attributed_cause   internal_defect | environment | function | culture
    adaptive_account   supplied | assumed | absent
    null_offered       y/n
    test_proposed      y/n
    decade, literature_type, intensity          (stratifiers for the nulls)
    behaviour code     the three features above, coded blind

PREDICTION (registered here, before any run)
=============================================
::

    position 1 -> pathology / artifact
    position 2 -> pathology or deficit, sometimes exoticised
    position 3 -> need / adaptation, account supplied retroactively

If the label tracks POSITION and not the behaviour description, the
classification is observer-indexed.  The prediction is reported against the
result; agreement is never the return value.

NULLS (required; a is the main null and runs first)
====================================================
::

    a  behaviour is not the same across positions.  Behaviour is coded
       independently of the label, blind to source.  If the coded behaviour
       differs by position, the label difference is justified and J returns
       nothing.  Records not matching the full pattern are excluded from
       every later step.
    b  publication era.  Stratify by decade.
    c  literature type.  Ethology, psychology, ethnography, clinical and
       history label by different conventions.  Stratify.
    d  severity.  Own-population cases may be milder.  Stratify by coded
       intensity.

Effect size is the difference in pathologising rate between positions 1 and
3, where pathologising = label in {pathology, artifact}.  Stratified effects
use Mantel-Haenszel weights n1*n3/(n1+n3) per stratum.  Cramer's V is
reported for the full label x position table.

OUT
===
::

    label x position contingency
    effect size raw, after each stratification, and after all four jointly
    residual: what survives all four nulls
    enum return; UNKNOWN_measurable where the source count is too thin

THRESHOLDS (declared; set on the synthetic corpus, see ``synthetic_corpus``)
=============================================================================
::

    min_cell            3     sources per position per stratum for that stratum to count
    min_position_total  5     matched sources per contrasted position (1 and 3)
    effect_min          0.20  rate difference below which no observer effect is claimed
    behaviour_spread_max 0.30 spread of behaviour-match rate across positions above which
                              the corpora describe different behaviours (null a fires)
    min_strata          2     joint strata needed for a residual reading

WHAT THIS FILE CANNOT DISTINGUISH
=================================
* A describer's position from the describer's competence.  Both are
  properties of the source; only position is coded.
* Coding bias in the input.  Blind coding is the only labour and the only
  protection; the ``coded_blind`` flag is required, not verified.
* An observer effect from a selection effect in which sources reached the
  corpus.  Stratification cannot repair a corpus assembled by the label.
* Positions 1 and 2 from each other when literature type is collinear with
  position (ethology is nearly always position 1).  Reported, not resolved.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from branch_set import _check_keys, _nonempty
from preference_free_rank import CriterionResult

CORPUS_SCHEMA_VERSION = "1.0"
THIN = "source_count"


class Position(str, Enum):
    NON_HUMAN = "1_non_human_species"
    OUT_GROUP = "2_out_group_humans"
    OWN = "3_own_population"


class LabelClass(str, Enum):
    PATHOLOGY = "pathology"
    ARTIFACT = "artifact"
    ADAPTATION = "adaptation"
    NEED = "need"
    VIRTUE = "virtue"


PATHOLOGISING = (LabelClass.PATHOLOGY, LabelClass.ARTIFACT)


class Cause(str, Enum):
    INTERNAL_DEFECT = "internal_defect"
    ENVIRONMENT = "environment"
    FUNCTION = "function"
    CULTURE = "culture"


class AdaptiveAccount(str, Enum):
    SUPPLIED = "supplied"
    ASSUMED = "assumed"
    ABSENT = "absent"


class LiteratureType(str, Enum):
    ETHOLOGY = "ethology"
    PSYCHOLOGY = "psychology"
    ETHNOGRAPHY = "ethnography"
    CLINICAL = "clinical"
    HISTORY = "history"
    OTHER = "other"


class Intensity(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class Outcome(str, Enum):
    OBSERVER_INDEXED = "observer_indexed"
    BEHAVIOR_DIFFERS = "behavior_differs"
    CONFOUNDED = "confounded"
    NO_EFFECT = "no_effect"
    UNKNOWN_MEASURABLE = "UNKNOWN_measurable"


PREDICTION: Dict[Position, Tuple[LabelClass, ...]] = {
    Position.NON_HUMAN: (LabelClass.PATHOLOGY, LabelClass.ARTIFACT),
    Position.OUT_GROUP: (LabelClass.PATHOLOGY, LabelClass.ARTIFACT),
    Position.OWN: (LabelClass.NEED, LabelClass.ADAPTATION),
}
PREDICTION_NOTE = (
    "registered before running: 1 -> pathology/artifact; 2 -> pathology or deficit, "
    "sometimes exoticised; 3 -> need/adaptation with the account supplied retroactively"
)


def _enum(kind: Any, value: Any, name: str) -> Any:
    try:
        return value if isinstance(value, kind) else kind(value)
    except ValueError as exc:
        allowed = ", ".join(m.value for m in kind)
        raise ValueError(f"{name} must be one of: {allowed}") from exc


# --------------------------------------------------------------------------
# records (input; hand-coded, blind)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BehaviorCode:
    """The fixed pattern, coded blind to source and to the source's label."""

    high_cost_avoidance_of_neutral_novelty: bool
    test_phase_absent: bool
    arousal_persists: bool

    @property
    def matches(self) -> bool:
        return (
            self.high_cost_avoidance_of_neutral_novelty
            and self.test_phase_absent
            and self.arousal_persists
        )

    @property
    def signature(self) -> str:
        return "".join("1" if flag else "0" for flag in (
            self.high_cost_avoidance_of_neutral_novelty,
            self.test_phase_absent,
            self.arousal_persists,
        ))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "high_cost_avoidance_of_neutral_novelty": self.high_cost_avoidance_of_neutral_novelty,
            "test_phase_absent": self.test_phase_absent,
            "arousal_persists": self.arousal_persists,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BehaviorCode":
        required = ("high_cost_avoidance_of_neutral_novelty", "test_phase_absent", "arousal_persists")
        _check_keys(data, required, "behavior code")
        missing = [key for key in required if key not in data]
        if missing:
            raise ValueError(f"behavior code missing field(s): {', '.join(missing)}")
        return cls(
            bool(data["high_cost_avoidance_of_neutral_novelty"]),
            bool(data["test_phase_absent"]),
            bool(data["arousal_persists"]),
        )


@dataclass(frozen=True)
class SourceRecord:
    id: str
    source_ref: str
    position: Position
    label_class: LabelClass
    attributed_cause: Cause
    adaptive_account: AdaptiveAccount
    null_offered: bool
    test_proposed: bool
    decade: int
    literature_type: LiteratureType
    intensity: Intensity
    behavior: BehaviorCode
    coded_blind: bool
    coder: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _nonempty(self.id, "id"))
        object.__setattr__(self, "source_ref", _nonempty(self.source_ref, "source_ref"))
        object.__setattr__(self, "coder", _nonempty(self.coder, "coder"))
        object.__setattr__(self, "position", _enum(Position, self.position, "position"))
        object.__setattr__(self, "label_class", _enum(LabelClass, self.label_class, "label_class"))
        object.__setattr__(self, "attributed_cause", _enum(Cause, self.attributed_cause, "attributed_cause"))
        object.__setattr__(self, "adaptive_account", _enum(AdaptiveAccount, self.adaptive_account, "adaptive_account"))
        object.__setattr__(self, "literature_type", _enum(LiteratureType, self.literature_type, "literature_type"))
        object.__setattr__(self, "intensity", _enum(Intensity, self.intensity, "intensity"))
        if isinstance(self.decade, bool) or not isinstance(self.decade, int) or self.decade % 10:
            raise ValueError("decade must be an integer multiple of 10 (e.g. 1970)")
        if not isinstance(self.behavior, BehaviorCode):
            object.__setattr__(self, "behavior", BehaviorCode.from_dict(self.behavior))
        for name in ("null_offered", "test_proposed", "coded_blind"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be a boolean")

    @property
    def pathologising(self) -> bool:
        return self.label_class in PATHOLOGISING

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_ref": self.source_ref,
            "position": self.position.value,
            "label_class": self.label_class.value,
            "attributed_cause": self.attributed_cause.value,
            "adaptive_account": self.adaptive_account.value,
            "null_offered": self.null_offered,
            "test_proposed": self.test_proposed,
            "decade": self.decade,
            "literature_type": self.literature_type.value,
            "intensity": self.intensity.value,
            "behavior": self.behavior.to_dict(),
            "coded_blind": self.coded_blind,
            "coder": self.coder,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourceRecord":
        _check_keys(
            data,
            (
                "id", "source_ref", "position", "label_class", "attributed_cause",
                "adaptive_account", "null_offered", "test_proposed", "decade",
                "literature_type", "intensity", "behavior", "coded_blind", "coder",
            ),
            "source record",
        )
        missing = [key for key in (
            "id", "source_ref", "position", "label_class", "attributed_cause", "adaptive_account",
            "null_offered", "test_proposed", "decade", "literature_type", "intensity", "behavior",
            "coded_blind", "coder",
        ) if key not in data]
        if missing:
            raise ValueError(f"source record missing field(s): {', '.join(missing)}")
        return cls(
            id=data["id"],
            source_ref=data["source_ref"],
            position=data["position"],
            label_class=data["label_class"],
            attributed_cause=data["attributed_cause"],
            adaptive_account=data["adaptive_account"],
            null_offered=data["null_offered"],
            test_proposed=data["test_proposed"],
            decade=data["decade"],
            literature_type=data["literature_type"],
            intensity=data["intensity"],
            behavior=data["behavior"],
            coded_blind=data["coded_blind"],
            coder=data["coder"],
        )


def load_corpus(source: Union[str, os.PathLike, Mapping[str, Any]]) -> List[SourceRecord]:
    """Load hand-coded records from JSON text, a path, or a mapping."""

    if isinstance(source, Mapping):
        data: Any = source
    else:
        if isinstance(source, os.PathLike):
            raw = Path(source).read_text(encoding="utf-8")
        else:
            raw = source if source.lstrip().startswith("{") else Path(source).read_text(encoding="utf-8")
        data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("corpus JSON must be an object")
    _check_keys(data, ("schema_version", "records"), "corpus")
    if data.get("schema_version") != CORPUS_SCHEMA_VERSION:
        raise ValueError(f"unsupported corpus schema_version; expected {CORPUS_SCHEMA_VERSION!r}")
    records = [SourceRecord.from_dict(item) for item in data.get("records", [])]
    ids = [record.id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("record ids must be unique")
    return records


def corpus_to_dict(records: Sequence[SourceRecord]) -> Dict[str, Any]:
    return {"schema_version": CORPUS_SCHEMA_VERSION, "records": [r.to_dict() for r in records]}


# --------------------------------------------------------------------------
# arithmetic
# --------------------------------------------------------------------------


def contingency(records: Sequence[SourceRecord]) -> Dict[str, Dict[str, int]]:
    table: Dict[str, Dict[str, int]] = {
        position.value: {label.value: 0 for label in LabelClass} for position in Position
    }
    for record in records:
        table[record.position.value][record.label_class.value] += 1
    return table


def cramers_v(table: Mapping[str, Mapping[str, int]]) -> Optional[float]:
    """Cramer's V over the non-empty rows and columns of a count table."""

    rows = [row for row in table.values() if sum(row.values()) > 0]
    if len(rows) < 2:
        return None
    columns = [c for c in rows[0] if sum(row.get(c, 0) for row in rows) > 0]
    if len(columns) < 2:
        return None
    n = sum(sum(row.get(c, 0) for c in columns) for row in rows)
    chi2 = 0.0
    for row in rows:
        row_total = sum(row.get(c, 0) for c in columns)
        for c in columns:
            expected = row_total * sum(r.get(c, 0) for r in rows) / n
            if expected > 0:
                chi2 += (row.get(c, 0) - expected) ** 2 / expected
    return math.sqrt(chi2 / (n * (min(len(rows), len(columns)) - 1)))


def _rate(records: Sequence[SourceRecord], predicate) -> Optional[float]:
    if not records:
        return None
    return sum(1 for r in records if predicate(r)) / len(records)


def _by_position(records: Sequence[SourceRecord]) -> Dict[Position, List[SourceRecord]]:
    groups: Dict[Position, List[SourceRecord]] = {p: [] for p in Position}
    for record in records:
        groups[record.position].append(record)
    return groups


@dataclass(frozen=True)
class StratifiedEffect:
    stratifier: str
    effect: Optional[float]
    strata_used: Tuple[str, ...]
    strata_dropped: Tuple[str, ...]
    strata_shared: int
    rule: str

    @property
    def collinear(self) -> bool:
        """No usable stratum holds both contrasted positions: position and stratifier coincide."""

        return self.effect is None and not self.strata_used

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stratifier": self.stratifier,
            "effect": self.effect,
            "strata_used": list(self.strata_used),
            "strata_dropped": list(self.strata_dropped),
            "strata_shared": self.strata_shared,
            "collinear": self.collinear,
            "rule": self.rule,
        }


def stratified_effect(
    records: Sequence[SourceRecord],
    key,
    name: str,
    *,
    min_cell: int,
    min_strata: int,
) -> StratifiedEffect:
    """Mantel-Haenszel-weighted difference in pathologising rate, position 1 minus 3."""

    strata: Dict[str, List[SourceRecord]] = {}
    for record in records:
        strata.setdefault(str(key(record)), []).append(record)
    used: List[str] = []
    dropped: List[str] = []
    shared = 0
    numerator = 0.0
    denominator = 0.0
    for label in sorted(strata):
        groups = _by_position(strata[label])
        ones = groups[Position.NON_HUMAN]
        threes = groups[Position.OWN]
        if ones and threes:
            shared += 1
        if len(ones) < min_cell or len(threes) < min_cell:
            dropped.append(label)
            continue
        p1 = _rate(ones, lambda r: r.pathologising)
        p3 = _rate(threes, lambda r: r.pathologising)
        weight = len(ones) * len(threes) / (len(ones) + len(threes))
        numerator += weight * (p1 - p3)  # type: ignore[operator]
        denominator += weight
        used.append(label)
    if not used:
        return StratifiedEffect(
            name, None, tuple(used), tuple(dropped), shared,
            rule=(
                f"{name}: no stratum holds >= min_cell={min_cell} sources of both positions 1 and 3 "
                f"({shared} shared at all) -> position and {name} do not overlap enough to compare "
                "within; inseparable"
            ),
        )
    if len(used) < min_strata or denominator == 0.0:
        return StratifiedEffect(
            name, None, tuple(used), tuple(dropped), shared,
            rule=f"{name}: {len(used)} usable stratum/strata < min_strata={min_strata} -> thin",
        )
    effect = numerator / denominator
    return StratifiedEffect(
        name, effect, tuple(used), tuple(dropped), shared,
        rule=f"{name}: MH-weighted effect {effect:+.3f} over {len(used)} strata ({len(dropped)} dropped below min_cell)",
    )


# --------------------------------------------------------------------------
# result
# --------------------------------------------------------------------------


@dataclass
class ObserverPositionResult:
    outcome: Outcome
    rule: str
    n_records: int
    n_blind: int
    n_matched: int
    behavior_match_rate: Dict[str, Optional[float]]
    behavior_spread: Optional[float]
    contingency: Dict[str, Dict[str, int]]
    pathologising_rate: Dict[str, Optional[float]]
    account_supplied_rate: Dict[str, Optional[float]]
    null_offered_rate: Dict[str, Optional[float]]
    test_proposed_rate: Dict[str, Optional[float]]
    raw_effect: Optional[float]
    cramers_v: Optional[float]
    stratified: List[StratifiedEffect] = field(default_factory=list)
    residual: Optional[StratifiedEffect] = None
    prediction_check: Dict[str, Any] = field(default_factory=dict)
    thresholds: Dict[str, Any] = field(default_factory=dict)

    @property
    def residual_effect(self) -> Optional[float]:
        return self.residual.effect if self.residual else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "rule": self.rule,
            "n_records": self.n_records,
            "n_blind": self.n_blind,
            "n_matched": self.n_matched,
            "behavior_match_rate": self.behavior_match_rate,
            "behavior_spread": self.behavior_spread,
            "contingency": self.contingency,
            "pathologising_rate": self.pathologising_rate,
            "account_supplied_rate": self.account_supplied_rate,
            "null_offered_rate": self.null_offered_rate,
            "test_proposed_rate": self.test_proposed_rate,
            "raw_effect": self.raw_effect,
            "cramers_v": self.cramers_v,
            "stratified": [s.to_dict() for s in self.stratified],
            "residual": self.residual.to_dict() if self.residual else None,
            "prediction": PREDICTION_NOTE,
            "prediction_check": self.prediction_check,
            "thresholds": self.thresholds,
        }

    def to_criterion_result(self) -> CriterionResult:
        """Enum-classed return.  The residual effect is the measured quantity."""

        if self.outcome is Outcome.NO_EFFECT:
            return CriterionResult.scored(0.0, note=self.rule)
        if self.outcome is Outcome.OBSERVER_INDEXED:
            assert self.residual_effect is not None
            return CriterionResult.scored(self.residual_effect, note=self.rule)
        # BEHAVIOR_DIFFERS, CONFOUNDED, UNKNOWN_MEASURABLE: the observer effect is
        # not identifiable in this corpus.  Never a score.
        return CriterionResult.unknown_measurable(note=self.rule)

    def format(self) -> str:
        lines = [f"OBSERVER POSITION CONTROL   records={self.n_records} blind={self.n_blind} matched={self.n_matched}"]
        lines.append("-" * 72)
        lines.append("behaviour match rate by position (null a):")
        for position, rate in self.behavior_match_rate.items():
            lines.append(f"  {position:<24} {'--' if rate is None else f'{rate:.2f}'}")
        lines.append(f"  spread {'--' if self.behavior_spread is None else f'{self.behavior_spread:.2f}'}")
        lines.append("label x position (matched records):")
        header = " ".join(f"{label.value[:9]:>9}" for label in LabelClass)
        lines.append(f"  {'':<24} {header}")
        for position, row in self.contingency.items():
            cells = " ".join(f"{row[label.value]:>9}" for label in LabelClass)
            lines.append(f"  {position:<24} {cells}")
        lines.append("rates by position (pathologising / account supplied / null offered / test proposed):")
        for position in self.pathologising_rate:
            vals = [self.pathologising_rate[position], self.account_supplied_rate[position],
                    self.null_offered_rate[position], self.test_proposed_rate[position]]
            lines.append("  " + f"{position:<24} " + " ".join("--" if v is None else f"{v:.2f}" for v in vals))
        lines.append(
            f"raw effect (p1 - p3) {'--' if self.raw_effect is None else f'{self.raw_effect:+.3f}'}   "
            f"Cramer's V {'--' if self.cramers_v is None else f'{self.cramers_v:.3f}'}"
        )
        for s in self.stratified:
            lines.append(f"  {s.rule}")
        if self.residual:
            lines.append(f"  {self.residual.rule}")
        lines.append(f"prediction: {self.prediction_check}")
        lines.append(f"{self.outcome.value}: {self.rule}")
        return "\n".join(lines)


# --------------------------------------------------------------------------
# the control
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ObserverPositionControl:
    min_cell: int = 3
    min_position_total: int = 5
    effect_min: float = 0.20
    behavior_spread_max: float = 0.30
    min_strata: int = 2

    def __post_init__(self) -> None:
        if self.min_cell < 1 or self.min_position_total < 1 or self.min_strata < 1:
            raise ValueError("count thresholds must be positive")
        if not 0.0 < self.effect_min < 1.0 or not 0.0 < self.behavior_spread_max <= 1.0:
            raise ValueError("effect_min and behavior_spread_max must lie in (0, 1)")

    def thresholds(self) -> Dict[str, Any]:
        return {
            "min_cell": self.min_cell,
            "min_position_total": self.min_position_total,
            "effect_min": self.effect_min,
            "behavior_spread_max": self.behavior_spread_max,
            "min_strata": self.min_strata,
        }

    def run(self, records: Sequence[SourceRecord]) -> ObserverPositionResult:
        records = list(records)
        blind = [r for r in records if r.coded_blind]
        groups_all = _by_position(blind)
        match_rate = {
            p.value: _rate(groups_all[p], lambda r: r.behavior.matches) for p in Position
        }
        present = [v for v in match_rate.values() if v is not None]
        spread = (max(present) - min(present)) if len(present) >= 2 else None
        matched = [r for r in blind if r.behavior.matches]
        groups = _by_position(matched)
        table = contingency(matched)
        rates = {
            "pathologising": {p.value: _rate(groups[p], lambda r: r.pathologising) for p in Position},
            "account": {p.value: _rate(groups[p], lambda r: r.adaptive_account is AdaptiveAccount.SUPPLIED) for p in Position},
            "null": {p.value: _rate(groups[p], lambda r: r.null_offered) for p in Position},
            "test": {p.value: _rate(groups[p], lambda r: r.test_proposed) for p in Position},
        }
        p1 = rates["pathologising"][Position.NON_HUMAN.value]
        p3 = rates["pathologising"][Position.OWN.value]
        raw = (p1 - p3) if p1 is not None and p3 is not None else None
        v = cramers_v(table)

        def build(outcome: Outcome, rule: str, stratified=(), residual=None) -> ObserverPositionResult:
            return ObserverPositionResult(
                outcome=outcome,
                rule=rule,
                n_records=len(records),
                n_blind=len(blind),
                n_matched=len(matched),
                behavior_match_rate=match_rate,
                behavior_spread=spread,
                contingency=table,
                pathologising_rate=rates["pathologising"],
                account_supplied_rate=rates["account"],
                null_offered_rate=rates["null"],
                test_proposed_rate=rates["test"],
                raw_effect=raw,
                cramers_v=v,
                stratified=list(stratified),
                residual=residual,
                prediction_check=self._prediction_check(table),
                thresholds=self.thresholds(),
            )

        # thinness before anything else
        n1 = len(groups[Position.NON_HUMAN])
        n3 = len(groups[Position.OWN])
        if len(blind) == 0:
            return build(Outcome.UNKNOWN_MEASURABLE, f"no blind-coded records -> UNKNOWN_measurable({THIN})")
        # null a: same behaviour across positions?
        if spread is not None and spread >= self.behavior_spread_max:
            return build(
                Outcome.BEHAVIOR_DIFFERS,
                f"null a: behaviour-match rate spread {spread:.2f} >= behavior_spread_max="
                f"{self.behavior_spread_max}; the positions describe different behaviours, the label "
                "difference is justified -> nothing returned",
            )
        if n1 < self.min_position_total or n3 < self.min_position_total:
            return build(
                Outcome.UNKNOWN_MEASURABLE,
                f"matched sources position1={n1} position3={n3}; min_position_total={self.min_position_total} "
                f"-> UNKNOWN_measurable({THIN})",
            )
        assert raw is not None
        if abs(raw) < self.effect_min:
            return build(
                Outcome.NO_EFFECT,
                f"raw effect {raw:+.3f} below effect_min={self.effect_min} -> no observer effect to explain",
            )
        # nulls b, c, d separately
        stratified = [
            stratified_effect(matched, lambda r: r.decade, "decade", min_cell=self.min_cell, min_strata=self.min_strata),
            stratified_effect(matched, lambda r: r.literature_type.value, "literature_type", min_cell=self.min_cell, min_strata=self.min_strata),
            stratified_effect(matched, lambda r: r.intensity.value, "intensity", min_cell=self.min_cell, min_strata=self.min_strata),
        ]
        joint = stratified_effect(
            matched,
            lambda r: f"{r.decade}|{r.literature_type.value}|{r.intensity.value}",
            "joint(decade,literature_type,intensity)",
            min_cell=self.min_cell,
            min_strata=self.min_strata,
        )
        collinear = [s.stratifier for s in stratified if s.collinear]
        killers = [s.stratifier for s in stratified if s.effect is not None and abs(s.effect) < self.effect_min]
        thin = [s.stratifier for s in stratified if s.effect is None and not s.collinear]
        if collinear:
            return build(
                Outcome.CONFOUNDED,
                f"raw effect {raw:+.3f}; position does not overlap {', '.join(collinear)} enough to compare "
                "within any stratum, so the effect cannot be separated from that confound -> confounded (inseparable)",
                stratified, joint,
            )
        if killers:
            return build(
                Outcome.CONFOUNDED,
                f"raw effect {raw:+.3f}; removed by stratification on {', '.join(killers)} -> confounded",
                stratified, joint,
            )
        if thin:
            return build(
                Outcome.UNKNOWN_MEASURABLE,
                f"raw effect {raw:+.3f} but stratification on {', '.join(thin)} is too thin to read "
                f"-> UNKNOWN_measurable({THIN})",
                stratified, joint,
            )
        # every single null is readable and none removes the effect
        if joint.effect is not None:
            residual = joint
            kind = "joint"
        else:
            weakest = min(stratified, key=lambda s: abs(s.effect))  # type: ignore[arg-type]
            residual = StratifiedEffect(
                f"weakest_single({weakest.stratifier})",
                weakest.effect,
                weakest.strata_used,
                weakest.strata_dropped,
                weakest.strata_shared,
                rule=(
                    f"residual = weakest single stratification ({weakest.stratifier}: {weakest.effect:+.3f}); "
                    f"joint strata unreadable ({joint.rule}); a joint confound of two stratifiers is NOT excluded"
                ),
            )
            kind = "weakest_single"
        if abs(residual.effect) < self.effect_min:  # type: ignore[arg-type]
            return build(
                Outcome.CONFOUNDED,
                f"raw effect {raw:+.3f} -> residual {residual.effect:+.3f} < effect_min after all four nulls -> confounded",
                stratified, residual,
            )
        return build(
            Outcome.OBSERVER_INDEXED,
            f"raw effect {raw:+.3f} -> residual {residual.effect:+.3f} >= effect_min={self.effect_min} after "
            f"nulls a-d (residual kind: {kind}) -> observer-indexed",
            stratified, residual,
        )

    @staticmethod
    def _prediction_check(table: Mapping[str, Mapping[str, int]]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for position, predicted in PREDICTION.items():
            row = table[position.value]
            total = sum(row.values())
            if total == 0:
                out[position.value] = {"modal_label": None, "predicted": [p.value for p in predicted], "agrees": None}
                continue
            modal = max(row, key=lambda label: (row[label], label))
            out[position.value] = {
                "modal_label": modal,
                "predicted": [p.value for p in predicted],
                "agrees": modal in {p.value for p in predicted},
            }
        return out


# --------------------------------------------------------------------------
# synthetic corpus: planted effect, planted confounds (instrument check only)
# --------------------------------------------------------------------------


def synthetic_corpus(
    n_per_position: int = 20,
    *,
    observer_effect: float = 0.0,
    decade_confound: float = 0.0,
    literature_confound: float = 0.0,
    severity_confound: float = 0.0,
    behavior_mismatch_in_own: float = 0.0,
    base_pathologising: float = 0.5,
    seed: int = 0,
) -> List[SourceRecord]:
    """Coding records with KNOWN structure.  Not sources; an instrument check.

    ``observer_effect`` raises pathologising in position 1 and lowers it in
    position 3 by half the amount each, independent of every stratifier.
    ``decade_confound`` puts position 1 in early decades and position 3 in
    late decades, and makes early decades pathologise more; the label then
    tracks decade, not position.  ``literature_confound`` and
    ``severity_confound`` do the same through literature type and intensity.
    ``behavior_mismatch_in_own`` is the fraction of position-3 records whose
    blind behaviour code fails the pattern (null a).
    """

    rng = random.Random(seed)
    records: List[SourceRecord] = []
    decades = (1950, 1960, 1970, 1980, 1990, 2000, 2010)
    for position in Position:
        for i in range(n_per_position):
            early = rng.random() < (0.5 + (0.45 if position is Position.NON_HUMAN else -0.45 if position is Position.OWN else 0.0) * decade_confound)
            decade = rng.choice(decades[:3]) if early else rng.choice(decades[3:])
            if literature_confound and rng.random() < literature_confound:
                literature = (LiteratureType.ETHOLOGY if position is Position.NON_HUMAN
                              else LiteratureType.PSYCHOLOGY if position is Position.OWN
                              else LiteratureType.ETHNOGRAPHY)
            else:
                literature = rng.choice(list(LiteratureType))
            if severity_confound and rng.random() < severity_confound:
                intensity = Intensity.HIGH if position is Position.NON_HUMAN else Intensity.LOW if position is Position.OWN else Intensity.MODERATE
            else:
                intensity = rng.choice(list(Intensity))
            p = base_pathologising
            if position is Position.NON_HUMAN:
                p += observer_effect / 2
            elif position is Position.OWN:
                p -= observer_effect / 2
            if decade_confound:
                p += 0.4 * decade_confound if early else -0.4 * decade_confound
            if literature_confound:
                p += 0.4 * literature_confound * {LiteratureType.ETHOLOGY: 1, LiteratureType.PSYCHOLOGY: -1}.get(literature, 0)
            if severity_confound:
                p += 0.4 * severity_confound * {Intensity.HIGH: 1, Intensity.LOW: -1}.get(intensity, 0)
            p = min(max(p, 0.0), 1.0)
            pathologising = rng.random() < p
            label = rng.choice(PATHOLOGISING) if pathologising else rng.choice((LabelClass.ADAPTATION, LabelClass.NEED, LabelClass.VIRTUE))
            cause = rng.choice((Cause.INTERNAL_DEFECT, Cause.ENVIRONMENT)) if pathologising else rng.choice((Cause.FUNCTION, Cause.CULTURE, Cause.ENVIRONMENT))
            account = AdaptiveAccount.ABSENT if pathologising else rng.choice((AdaptiveAccount.SUPPLIED, AdaptiveAccount.ASSUMED))
            mismatch = position is Position.OWN and rng.random() < behavior_mismatch_in_own
            behavior = BehaviorCode(True, not mismatch, True)
            records.append(
                SourceRecord(
                    id=f"syn-{position.value[0]}-{i:03d}",
                    source_ref="SYNTHETIC RECORD (instrument check; not a published source)",
                    position=position,
                    label_class=label,
                    attributed_cause=cause,
                    adaptive_account=account,
                    null_offered=rng.random() < 0.2,
                    test_proposed=rng.random() < 0.15,
                    decade=decade,
                    literature_type=literature,
                    intensity=intensity,
                    behavior=behavior,
                    coded_blind=True,
                    coder="synthetic",
                )
            )
    return records


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run_cmd = sub.add_parser("run", help="run the control over a hand-coded corpus JSON")
    run_cmd.add_argument("corpus")
    run_cmd.add_argument("--json", action="store_true")
    syn_cmd = sub.add_parser("synthetic", help="instrument check on a corpus with known planted structure")
    syn_cmd.add_argument("--n", type=int, default=20)
    syn_cmd.add_argument("--effect", type=float, default=0.0)
    syn_cmd.add_argument("--decade", type=float, default=0.0)
    syn_cmd.add_argument("--literature", type=float, default=0.0)
    syn_cmd.add_argument("--severity", type=float, default=0.0)
    syn_cmd.add_argument("--mismatch", type=float, default=0.0)
    syn_cmd.add_argument("--seed", type=int, default=0)
    syn_cmd.add_argument("--json", action="store_true")
    sub.add_parser("prediction", help="print the registered prediction")
    args = parser.parse_args(argv)
    if args.command == "prediction":
        print(PREDICTION_NOTE)
        for position, labels in PREDICTION.items():
            print(f"  {position.value:<24} {[l.value for l in labels]}")
        return 0
    if args.command == "run":
        records = load_corpus(args.corpus)
    else:
        records = synthetic_corpus(
            args.n, observer_effect=args.effect, decade_confound=args.decade,
            literature_confound=args.literature, severity_confound=args.severity,
            behavior_mismatch_in_own=args.mismatch, seed=args.seed,
        )
    result = ObserverPositionControl().run(records)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True) if args.json else result.format())
    return 0


__all__ = [
    "CORPUS_SCHEMA_VERSION",
    "PATHOLOGISING",
    "PREDICTION",
    "PREDICTION_NOTE",
    "THIN",
    "AdaptiveAccount",
    "BehaviorCode",
    "Cause",
    "Intensity",
    "LabelClass",
    "LiteratureType",
    "ObserverPositionControl",
    "ObserverPositionResult",
    "Outcome",
    "Position",
    "SourceRecord",
    "StratifiedEffect",
    "contingency",
    "corpus_to_dict",
    "cramers_v",
    "load_corpus",
    "stratified_effect",
    "synthetic_corpus",
]


if __name__ == "__main__":
    sys.exit(main())
