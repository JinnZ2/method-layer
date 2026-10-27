"""
gap_instruments.py -- evidence notation, method-layer form. CC0, stdlib only.

Records evidence about coordination systems, physical limits, discrepancies
and abstentions. It assigns no verdict. validate() reports whether a record
is complete and internally consistent. It never checks whether the evidence
is true.

This module reshapes the instrument delivered on 2026-10-25 to this
repository's conventions: str Enums, frozen dataclasses, tuples instead of
lists, and to_dict / from_dict with _check_keys. The delivered text and its
eight marked fixes (F1-F8) are in the Simulators repository, at
gap-instruments/. A byte copy of that working copy is at
tools/gap_instruments.py here. The PROPOSED example instances are left out:
this repository ships no sourced example content. Only blank templates
remain.

Shape
-----
    caller supplies Evidence(value, status, source, unit, uncertainty)
        |
        | the enum is checked at construction: an unknown status raises
        v
    record.validate() -> tuple of strings, each one an UNRESOLVED line
    gap_summary(record) -> status counts, NOT_RECORDED counted apart
        |
        v
    verdict: never assigned here

Refusals that are deliberate
----------------------------
    MEASURED/ESTIMATED without source  -> UNRESOLVED, never accepted silently
    axis never recorded                -> NOT_RECORDED, kept apart from GAP (F4)
    "", whitespace, GAP, "replace:..." -> blank, not reasoned (F1, F6)
    unknown count                      -> None, never 0
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field, fields
from enum import Enum
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional, Tuple

from branch_set import _check_keys


class Status(str, Enum):
    MEASURED = "MEASURED"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"
    GAP = "GAP"


class Availability(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    RESTRICTED = "RESTRICTED"
    NOT_CHECKED = "NOT_CHECKED"
    UNKNOWN = "UNKNOWN"


class Tristate(str, Enum):
    YES = "YES"
    NO = "NO"
    UNKNOWN = "UNKNOWN"
    NOT_TESTED = "NOT_TESTED"


class AbstentionType(str, Enum):       # F2: the vocabulary is checked
    DECLINED_TO_AUDIT = "declined_to_audit"
    NO_ASSESSMENT_POSSIBLE = "no_assessment_possible"
    CHOSE_NEUTRALITY = "chose_neutrality"
    DEFERRED = "deferred"
    DID_NOT_REACH = "did_not_reach"


AXES = MappingProxyType({
    "anchor": "What invariant forces revision of this claim?",
    "bound": "What external limit cannot be exceeded by relabeling?",
    "coupling": "Does consequence reach the party that decided?",
    "update": "What forces revision, on what timescale?",
    "error_visibility": "Can the system detect its own decoupling?",
})


def _blank(value: Optional[str]) -> bool:
    """F1/F6: empty, whitespace, GAP or a template placeholder is a blank."""
    v = (value or "").strip()
    return (not v or v == "GAP" or v.lower().startswith("replace:")
            or "specify" in v.lower())


def _set(obj: Any, name: str, value: Any) -> None:
    object.__setattr__(obj, name, value)


def _coerce_enums(obj: Any, enums: Mapping[str, type]) -> None:
    for name, cls in enums.items():
        _set(obj, name, cls(getattr(obj, name)))


def _count(value: Any, name: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative int or None (unknown)")
    return value


# ---------------------------------------------------------------- records
@dataclass(frozen=True)
class Evidence:
    value: str = ""
    status: Status = Status.GAP
    source: str = ""
    unit: str = ""
    uncertainty: str = ""

    def __post_init__(self) -> None:
        _coerce_enums(self, {"status": Status})

    def validate(self, label: str) -> Tuple[str, ...]:
        out = []
        if self.status in (Status.MEASURED, Status.ESTIMATED):
            tag = self.status.value
            if not self.value.strip():
                out.append(f"{label}: {tag} but value empty")
            if not self.source.strip():
                out.append(f"{label}: {tag} but no source")
            if not self.uncertainty.strip():
                out.append(f"{label}: {tag} but uncertainty not stated")
        return tuple(out)


@dataclass(frozen=True)
class Observability:
    """Can the record see its own misses? A None count means unknown."""
    outputs_total: Optional[int] = None
    outputs_evaluated: Optional[int] = None
    independently_verified: Optional[int] = None
    evaluator_independent_of_generator: Tristate = Tristate.UNKNOWN
    shared_failure_modes: str = ""
    detection_method: Evidence = field(default_factory=Evidence)
    undetected_error_estimate: Evidence = field(default_factory=Evidence)

    def __post_init__(self) -> None:
        _coerce_enums(self, {"evaluator_independent_of_generator": Tristate})
        for n in ("outputs_total", "outputs_evaluated", "independently_verified"):
            _set(self, n, _count(getattr(self, n), n))

    def unevaluated_fraction(self) -> Optional[float]:
        t, e = self.outputs_total, self.outputs_evaluated
        if t and e is not None and e <= t:
            return (t - e) / t
        return None

    def validate(self, label: str = "observability") -> Tuple[str, ...]:
        out = []
        t, e, v = self.outputs_total, self.outputs_evaluated, self.independently_verified
        if t is not None and e is not None and e > t:
            out.append(f"{label}: evaluated > total")
        if e is not None and v is not None and v > e:
            out.append(f"{label}: verified > evaluated")
        if (self.evaluator_independent_of_generator is Tristate.NO
                and not self.shared_failure_modes.strip()):
            out.append(f"{label}: evaluator not independent but shared failure modes unstated")
        out += self.detection_method.validate(f"{label}.detection_method")
        out += self.undetected_error_estimate.validate(f"{label}.undetected_error_estimate")
        return tuple(out)


@dataclass(frozen=True)
class CoordinationSystem:
    name: str
    instance_of: str                    # concrete object + place + period
    axes: Mapping[str, Evidence] = field(default_factory=dict)
    observability: Observability = field(default_factory=Observability)
    notes: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _set(self, "axes", MappingProxyType(dict(self.axes)))
        _set(self, "notes", tuple(self.notes))

    def validate(self) -> Tuple[str, ...]:
        out = [f"axis missing: {a}" for a in AXES if a not in self.axes]
        out += [f"axis not in AXES: {a}" for a in self.axes if a not in AXES]   # F3
        for a, ev in self.axes.items():
            out += ev.validate(f"axis.{a}")
        if _blank(self.instance_of):
            out.append("instance_of unspecified: label without dated instance")
        out += self.observability.validate()
        return tuple(out)


@dataclass(frozen=True)
class InstanceChange:
    """The label stayed; the configuration changed. One row per dated change."""
    label: str
    date: str
    change: str
    mechanism_before: str = ""
    mechanism_after: str = ""
    evidence: Evidence = field(default_factory=Evidence)

    def validate(self) -> Tuple[str, ...]:
        out = list(self.evidence.validate(f"change[{self.date}]"))
        if not self.date.strip():
            out.append("instance change: date missing")
        if not self.label.strip():                                       # F7
            out.append("instance change: label missing")
        return tuple(out)


_LIMIT_EVIDENCE = ("external_bound", "ai_reported_limit", "independent_measurement",
                   "observed_response", "instrumentation_method")
_LIMIT_AVAIL = ("sensor_availability", "calibration_status",
                "configuration_status", "access_status")


@dataclass(frozen=True)
class PhysicalLimitRecord:
    record_id: str
    system_instance: str
    operating_condition: str
    physical_quantity: str
    external_bound: Evidence = field(default_factory=Evidence)
    ai_reported_limit: Evidence = field(default_factory=Evidence)
    independent_measurement: Evidence = field(default_factory=Evidence)
    observed_response: Evidence = field(default_factory=Evidence)
    instrumentation_method: Evidence = field(default_factory=Evidence)
    sensor_availability: Availability = Availability.UNKNOWN
    calibration_status: Availability = Availability.UNKNOWN
    configuration_status: Availability = Availability.UNKNOWN
    access_status: Availability = Availability.UNKNOWN
    observability: Observability = field(default_factory=Observability)
    notes: str = ""

    def __post_init__(self) -> None:
        _coerce_enums(self, {n: Availability for n in _LIMIT_AVAIL})

    def validate(self) -> Tuple[str, ...]:
        out = []
        for n in _LIMIT_EVIDENCE:
            out += getattr(self, n).validate(n)
        for n in ("system_instance", "operating_condition", "physical_quantity"):
            if _blank(getattr(self, n)):                                 # F6
                out.append(f"{n} unspecified")
        out += self.observability.validate()
        return tuple(out)


@dataclass(frozen=True)
class DiscrepancyRecord:
    record_id: str
    linked_limit_record_id: str
    expected: Evidence = field(default_factory=Evidence)
    observed: Evidence = field(default_factory=Evidence)
    candidate_explanations: Tuple[str, ...] = ()
    tested_explanations: Tuple[str, ...] = ()
    unresolved_questions: Tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        for n in ("candidate_explanations", "tested_explanations", "unresolved_questions"):
            _set(self, n, tuple(getattr(self, n)))

    def validate(self) -> Tuple[str, ...]:
        out = list(self.expected.validate("expected") + self.observed.validate("observed"))
        if not self.linked_limit_record_id.strip():
            out.append("linked_limit_record_id unspecified")
        if (self.expected.unit and self.observed.unit
                and self.expected.unit != self.observed.unit):
            out.append("expected and observed units differ")
        for t in self.tested_explanations:                               # F5
            if t not in self.candidate_explanations:
                out.append(f"tested explanation not among candidates: {t!r}")
        return tuple(out)


_HANDLING_TRI = ("system_reported_detection", "requested_more_evidence",
                 "outcome_independently_checked")


@dataclass(frozen=True)
class DiscrepancyHandling:
    """What the system DID about a discrepancy. Outputs, not inferred awareness."""
    record_id: str
    linked_discrepancy_id: str
    system_reported_detection: Tristate = Tristate.NOT_TESTED
    requested_more_evidence: Tristate = Tristate.NOT_TESTED
    action_taken: Evidence = field(default_factory=Evidence)
    output_before: Evidence = field(default_factory=Evidence)
    output_after: Evidence = field(default_factory=Evidence)
    outcome_independently_checked: Tristate = Tristate.NOT_TESTED
    outcome_evidence: Evidence = field(default_factory=Evidence)

    def __post_init__(self) -> None:
        _coerce_enums(self, {n: Tristate for n in _HANDLING_TRI})

    def validate(self) -> Tuple[str, ...]:
        out = []
        for n in ("action_taken", "output_before", "output_after", "outcome_evidence"):
            out += getattr(self, n).validate(n)
        if (self.outcome_independently_checked is Tristate.YES
                and self.outcome_evidence.status is Status.GAP):
            out.append("outcome marked checked but outcome_evidence is GAP")
        if not self.linked_discrepancy_id.strip():
            out.append("linked_discrepancy_id unspecified")
        return tuple(out)


@dataclass(frozen=True)
class Abstention:
    """A non-audit is a read. Falsifiable only with these fields filled."""
    date: str
    actor: str
    decision_point: str
    abstention_type: AbstentionType
    available_at_time: str
    would_have_counted_as: str = "GAP"
    review_trigger: str = "GAP"

    def __post_init__(self) -> None:
        _coerce_enums(self, {"abstention_type": AbstentionType})       # F2

    def validate(self) -> Tuple[str, ...]:
        out = []
        if _blank(self.would_have_counted_as):                           # F1
            out.append("abstention: defaulted, not reasoned (would_have_counted_as)")
        if _blank(self.review_trigger):
            out.append("abstention: closer, not binding (review_trigger)")
        return tuple(out)


RECORDS = (Evidence, Observability, CoordinationSystem, InstanceChange,
           PhysicalLimitRecord, DiscrepancyRecord, DiscrepancyHandling, Abstention)


# ------------------------------------------------------- serialisation
def to_dict(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    if type(obj) in RECORDS:
        return {f.name: to_dict(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, Mapping):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, tuple):
        return [to_dict(v) for v in obj]
    return obj


_NESTED = {
    "observability": Observability, "detection_method": Evidence,
    "undetected_error_estimate": Evidence, "evidence": Evidence,
    "expected": Evidence, "observed": Evidence,
    **{n: Evidence for n in _LIMIT_EVIDENCE},
    **{n: Evidence for n in ("action_taken", "output_before", "output_after",
                             "outcome_evidence")},
}


def from_dict(cls: type, data: Mapping[str, Any]) -> Any:
    if cls not in RECORDS:
        raise ValueError(f"not a gap_instruments record: {cls!r}")
    if not isinstance(data, Mapping):
        raise ValueError(f"{cls.__name__} must be a mapping")
    _check_keys(data, [f.name for f in fields(cls)], cls.__name__)
    kwargs = {}
    for k, v in data.items():
        if k == "axes" and cls is CoordinationSystem:
            v = {a: from_dict(Evidence, e) for a, e in v.items()}
        elif k in _NESTED and isinstance(v, Mapping):
            v = from_dict(_NESTED[k], v)
        elif isinstance(v, list):
            v = tuple(v)
        kwargs[k] = v
    return cls(**kwargs)


# --------------------------------------------------------- summaries
def _walk_evidence(obj: Any, prefix: str = "") -> Iterable[Tuple[str, Evidence]]:
    if isinstance(obj, Evidence):
        yield prefix, obj
    elif type(obj) in RECORDS:
        for f in fields(obj):
            yield from _walk_evidence(getattr(obj, f.name), f"{prefix}{f.name}.")
    elif isinstance(obj, Mapping):
        for k, v in obj.items():
            yield from _walk_evidence(v, f"{prefix}{k}.")


def gap_summary(record: Any) -> dict:
    """Status counts. F4: an axis never recorded is NOT_RECORDED, kept apart
    from GAP and included in the total, so omission cannot raise the fraction."""
    counts = {s.value: 0 for s in Status}
    for _, ev in _walk_evidence(record):
        counts[ev.status.value] += 1
    if isinstance(record, CoordinationSystem):
        counts["NOT_RECORDED"] = sum(1 for a in AXES if a not in record.axes)
    total = sum(counts.values())
    counts["filled_fraction"] = (round((counts["MEASURED"] + counts["ESTIMATED"]) / total, 3)
                                 if total else None)
    return counts


def question_template(claim: str) -> CoordinationSystem:
    """Not a classifier. Returns the questions; the reader supplies evidence."""
    return CoordinationSystem(
        name=f"CLAIM: {claim}", instance_of="",
        axes={a: Evidence(value=f"? {q}") for a, q in AXES.items()})


def main(argv: Optional[Tuple[str, ...]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] != "--claim" or len(argv) < 2 or not " ".join(argv[1:]).strip():
        print('usage: python3 gap_instruments.py --claim "..."', file=sys.stderr)
        return 2                                                         # F8
    t = question_template(" ".join(argv[1:]))
    print(t.name)
    for a, ev in t.axes.items():
        print(f"  {a:<17}: [{ev.status.value}] {ev.value}")
    for line in t.validate():
        print("  UNRESOLVED:", line)
    print(f"  summary: {gap_summary(t)}")
    print("  verdict: NOT ASSIGNED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
