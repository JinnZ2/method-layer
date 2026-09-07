"""Lossless transport and triage for uncoalesced candidate generators.

This module deliberately contains no simulation code and uses only the Python
standard library.  A :class:`BranchSet` preserves every candidate, including
eliminated candidates, while exposing cheap-test ordering and gap triage.
"""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, TextIO, Union

SCHEMA_VERSION = "1.0"


class BranchStatus(str, Enum):
    OPEN = "open"
    ELIMINATED = "eliminated"
    SURVIVED = "survived"


class SuppressionCause(str, Enum):
    PRIOR = "prior"
    ACCESS = "access"


class AccessKind(str, Enum):
    NO_VOCABULARY = "no_vocabulary"
    CROSS_DISCIPLINE = "cross_discipline"
    INSTRUMENT_MISSING = "instrument_missing"


class RecordPresence(str, Enum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class RecordState(str, Enum):
    """Machine-readable state used by the gap triage decision table."""

    INSTRUMENT_EXISTS_UNRUN = "instrument_exists_unrun"
    COMPONENTS_EXIST_UNASSEMBLED = "components_exist_unassembled"
    NO_MEASUREMENT_NEEDED = "no_measurement_needed"
    MISSING_PIECE = "missing_piece"


class TriageClass(str, Enum):
    ANSWERABLE_NOW = "answerable_now"
    BUILDABLE = "buildable"
    SIMULABLE = "simulable"
    BLOCKED = "blocked"


def _enum_value(enum_type: Any, value: Any, field_name: str) -> Any:
    try:
        return value if isinstance(value, enum_type) else enum_type(value)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(member.value for member in enum_type)
        raise ValueError(f"{field_name} must be one of: {allowed}") from exc


def _nonempty(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _check_keys(data: Mapping[str, Any], allowed: Iterable[str], record: str) -> None:
    extras = sorted(set(data) - set(allowed))
    if extras:
        raise ValueError(f"unknown {record} field(s): {', '.join(extras)}")


@dataclass(frozen=True)
class PredictionElsewhere:
    pattern: str
    domain: str
    already_in_record: RecordPresence
    record_state: Optional[RecordState] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "pattern", _nonempty(self.pattern, "pattern"))
        object.__setattr__(self, "domain", _nonempty(self.domain, "domain"))
        object.__setattr__(
            self,
            "already_in_record",
            _enum_value(RecordPresence, self.already_in_record, "already_in_record"),
        )
        if self.record_state is not None:
            object.__setattr__(
                self,
                "record_state",
                _enum_value(RecordState, self.record_state, "record_state"),
            )
        if self.already_in_record is RecordPresence.UNKNOWN and self.record_state is None:
            raise ValueError(
                "record_state is required when already_in_record is unknown so triage "
                "can run without reading free text"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern": self.pattern,
            "domain": self.domain,
            "already_in_record": self.already_in_record.value,
            "record_state": self.record_state.value if self.record_state else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PredictionElsewhere":
        _check_keys(
            data,
            ("pattern", "domain", "already_in_record", "record_state"),
            "prediction",
        )
        return cls(
            pattern=data["pattern"],
            domain=data["domain"],
            already_in_record=data["already_in_record"],
            record_state=data.get("record_state"),
        )


@dataclass(frozen=True)
class InstrumentHistory:
    phenomenon_before: str
    made_readable: str
    discipline_crossed: str
    question_askable_date: str
    instrument_built_date: str

    def __post_init__(self) -> None:
        for name in ("phenomenon_before", "made_readable", "discipline_crossed"):
            object.__setattr__(self, name, _nonempty(getattr(self, name), name))
        question_date = self._parse_date(self.question_askable_date, "question_askable_date")
        built_date = self._parse_date(self.instrument_built_date, "instrument_built_date")
        if built_date < question_date:
            raise ValueError("instrument_built_date cannot precede question_askable_date")

    @staticmethod
    def _parse_date(value: str, field_name: str) -> date:
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be an ISO-8601 date (YYYY-MM-DD)") from exc

    @property
    def lag_days(self) -> int:
        """Observed access lag; it is not a measure of problem difficulty."""

        question_date = self._parse_date(self.question_askable_date, "question_askable_date")
        built_date = self._parse_date(self.instrument_built_date, "instrument_built_date")
        return (built_date - question_date).days

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phenomenon_before": self.phenomenon_before,
            "made_readable": self.made_readable,
            "discipline_crossed": self.discipline_crossed,
            "question_askable_date": self.question_askable_date,
            "instrument_built_date": self.instrument_built_date,
            "lag": self.lag_days,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "InstrumentHistory":
        _check_keys(
            data,
            (
                "phenomenon_before",
                "made_readable",
                "discipline_crossed",
                "question_askable_date",
                "instrument_built_date",
                "lag",
            ),
            "instrument history",
        )
        item = cls(
            phenomenon_before=data["phenomenon_before"],
            made_readable=data["made_readable"],
            discipline_crossed=data["discipline_crossed"],
            question_askable_date=data["question_askable_date"],
            instrument_built_date=data["instrument_built_date"],
        )
        if "lag" in data and data["lag"] != item.lag_days:
            raise ValueError("serialized lag does not match the two dates")
        return item


@dataclass
class Branch:
    id: str
    generator: str
    origin_pattern: str
    predicted_divergence: str
    discriminator: str
    cost: float
    status: BranchStatus = BranchStatus.OPEN
    eliminated_by: Optional[str] = None
    suppression_cause: SuppressionCause = SuppressionCause.PRIOR
    access_kind: Optional[AccessKind] = None
    predicts_elsewhere: List[PredictionElsewhere] = field(default_factory=list)
    instrument_history: List[InstrumentHistory] = field(default_factory=list)

    def __post_init__(self) -> None:
        for name in (
            "id",
            "generator",
            "origin_pattern",
            "predicted_divergence",
            "discriminator",
        ):
            setattr(self, name, _nonempty(getattr(self, name), name))
        try:
            self.cost = float(self.cost)
        except (TypeError, ValueError) as exc:
            raise ValueError("cost must be a finite, non-negative number") from exc
        if not math.isfinite(self.cost) or self.cost < 0:
            raise ValueError("cost must be a finite, non-negative number")
        self.status = _enum_value(BranchStatus, self.status, "status")
        self.suppression_cause = _enum_value(
            SuppressionCause, self.suppression_cause, "suppression_cause"
        )
        if self.access_kind is not None:
            self.access_kind = _enum_value(AccessKind, self.access_kind, "access_kind")
        if self.suppression_cause is SuppressionCause.ACCESS and self.access_kind is None:
            raise ValueError("access_kind is required when suppression_cause is access")
        if self.suppression_cause is SuppressionCause.PRIOR and self.access_kind is not None:
            raise ValueError("access_kind must be None when suppression_cause is prior")
        if self.status is BranchStatus.ELIMINATED:
            self.eliminated_by = _nonempty(self.eliminated_by, "eliminated_by")
        elif self.eliminated_by is not None:
            raise ValueError("eliminated_by is only valid for an eliminated branch")

        self.predicts_elsewhere = [
            item if isinstance(item, PredictionElsewhere) else PredictionElsewhere.from_dict(item)
            for item in self.predicts_elsewhere
        ]
        self.instrument_history = [
            item if isinstance(item, InstrumentHistory) else InstrumentHistory.from_dict(item)
            for item in self.instrument_history
        ]
        for prediction in self.predicts_elsewhere:
            if prediction.domain == self.origin_pattern:
                raise ValueError(
                    "predicts_elsewhere.domain must differ from origin_pattern; "
                    "the origin cannot validate the generator that suggested it"
                )

    def eliminate(self, eliminated_by: str) -> None:
        self.status = BranchStatus.ELIMINATED
        self.eliminated_by = _nonempty(eliminated_by, "eliminated_by")

    def mark_survived(self) -> None:
        self.status = BranchStatus.SURVIVED
        self.eliminated_by = None

    def reopen(self) -> None:
        self.status = BranchStatus.OPEN
        self.eliminated_by = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "generator": self.generator,
            "origin_pattern": self.origin_pattern,
            "predicted_divergence": self.predicted_divergence,
            "discriminator": self.discriminator,
            "cost": self.cost,
            "status": self.status.value,
            "eliminated_by": self.eliminated_by,
            "suppression_cause": self.suppression_cause.value,
            "access_kind": self.access_kind.value if self.access_kind else None,
            "predicts_elsewhere": [item.to_dict() for item in self.predicts_elsewhere],
            "instrument_history": [item.to_dict() for item in self.instrument_history],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Branch":
        _check_keys(
            data,
            (
                "id",
                "generator",
                "origin_pattern",
                "predicted_divergence",
                "discriminator",
                "cost",
                "status",
                "eliminated_by",
                "suppression_cause",
                "access_kind",
                "predicts_elsewhere",
                "instrument_history",
            ),
            "branch",
        )
        return cls(
            id=data["id"],
            generator=data["generator"],
            origin_pattern=data["origin_pattern"],
            predicted_divergence=data["predicted_divergence"],
            discriminator=data["discriminator"],
            cost=data["cost"],
            status=data.get("status", BranchStatus.OPEN.value),
            eliminated_by=data.get("eliminated_by"),
            suppression_cause=data["suppression_cause"],
            access_kind=data.get("access_kind"),
            predicts_elsewhere=data.get("predicts_elsewhere", []),
            instrument_history=data.get("instrument_history", []),
        )


@dataclass(frozen=True)
class Gap:
    branch_id: str
    prediction: PredictionElsewhere

    def to_dict(self) -> Dict[str, Any]:
        return {"branch_id": self.branch_id, "prediction": self.prediction.to_dict()}


@dataclass(frozen=True)
class TriageResult:
    branch_id: str
    pattern: str
    domain: str
    result: TriageClass
    blocker: Optional[SuppressionCause]
    rule: str

    @property
    def label(self) -> str:
        if self.result is TriageClass.BLOCKED:
            return f"blocked({self.blocker.value})"
        return self.result.value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "pattern": self.pattern,
            "domain": self.domain,
            "result": self.result.value,
            "blocker": self.blocker.value if self.blocker else None,
            "rule": self.rule,
        }


JsonSource = Union[str, bytes, os.PathLike, TextIO]


@dataclass
class BranchSet:
    branches: List[Branch] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"unsupported schema_version {self.schema_version!r}; expected {SCHEMA_VERSION!r}"
            )
        self.branches = [
            item if isinstance(item, Branch) else Branch.from_dict(item) for item in self.branches
        ]
        self._check_unique_ids()

    def _check_unique_ids(self) -> None:
        seen = set()
        for branch in self.branches:
            if branch.id in seen:
                raise ValueError(f"duplicate branch id: {branch.id}")
            seen.add(branch.id)

    def add(self, branch: Branch) -> None:
        if not isinstance(branch, Branch):
            raise TypeError("branch must be a Branch")
        if any(item.id == branch.id for item in self.branches):
            raise ValueError(f"duplicate branch id: {branch.id}")
        self.branches.append(branch)

    def get(self, branch_id: str) -> Branch:
        for branch in self.branches:
            if branch.id == branch_id:
                return branch
        raise KeyError(branch_id)

    def test_queue(self) -> List[Branch]:
        """Return open branches in cheapest-discriminator order."""

        return sorted(
            (branch for branch in self.branches if branch.status is BranchStatus.OPEN),
            key=lambda branch: (branch.cost, branch.id),
        )

    def eliminated_set(self) -> List[Branch]:
        """Return full eliminated records; eliminated data is never discarded."""

        return [
            branch for branch in self.branches if branch.status is BranchStatus.ELIMINATED
        ]

    def gap_list(self) -> List[Gap]:
        return [
            Gap(branch.id, prediction)
            for branch in self.branches
            for prediction in branch.predicts_elsewhere
            if prediction.already_in_record is RecordPresence.UNKNOWN
        ]

    def triage(self, stream: Optional[TextIO] = sys.stdout) -> List[TriageResult]:
        """Triage every gap from record_state and suppression_cause only.

        The selected rule is printed by default.  Pass ``stream=None`` to suppress
        printing while retaining each rule in the returned records.
        """

        results: List[TriageResult] = []
        for gap in self.gap_list():
            branch = self.get(gap.branch_id)
            state = gap.prediction.record_state
            cause = branch.suppression_cause
            if state is RecordState.INSTRUMENT_EXISTS_UNRUN:
                result = TriageClass.ANSWERABLE_NOW
                blocker = None
                rule = "instrument_exists_unrun -> answerable_now"
            elif state is RecordState.COMPONENTS_EXIST_UNASSEMBLED:
                result = TriageClass.BUILDABLE
                blocker = None
                rule = "components_exist_unassembled -> buildable"
            elif state is RecordState.NO_MEASUREMENT_NEEDED:
                result = TriageClass.SIMULABLE
                blocker = None
                rule = "no_measurement_needed -> simulable"
            elif state is RecordState.MISSING_PIECE:
                result = TriageClass.BLOCKED
                blocker = cause
                rule = f"missing_piece + suppression_cause={cause.value} -> blocked({cause.value})"
            else:  # Construction validation makes this unreachable.
                raise RuntimeError("unrecognized record state")
            triaged = TriageResult(
                branch_id=branch.id,
                pattern=gap.prediction.pattern,
                domain=gap.prediction.domain,
                result=result,
                blocker=blocker,
                rule=rule,
            )
            results.append(triaged)
            if stream is not None:
                print(rule, file=stream)
        return results

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "branches": [branch.to_dict() for branch in self.branches],
        }

    def serialize(self, *, indent: Optional[int] = 2) -> str:
        """Serialize the complete set to stable JSON."""

        return json.dumps(
            self.to_dict(),
            indent=indent,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BranchSet":
        _check_keys(data, ("schema_version", "branches"), "branch set")
        return cls(
            schema_version=data["schema_version"],
            branches=[Branch.from_dict(item) for item in data.get("branches", [])],
        )

    @classmethod
    def load(cls, source: JsonSource) -> "BranchSet":
        """Load from JSON text, UTF-8 bytes, a path, or a text file object."""

        if hasattr(source, "read"):
            raw = source.read()  # type: ignore[union-attr]
        elif isinstance(source, bytes):
            raw = source.decode("utf-8")
        elif isinstance(source, os.PathLike):
            raw = Path(source).read_text(encoding="utf-8")
        elif isinstance(source, str):
            stripped = source.lstrip()
            if stripped.startswith("{"):
                raw = source
            else:
                path = Path(source)
                raw = path.read_text(encoding="utf-8") if path.exists() else source
        else:
            raise TypeError("source must be JSON text, bytes, a path, or a text file")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("branch-set JSON must contain an object at the top level")
        return cls.from_dict(data)

    def write(self, path: Union[str, os.PathLike], *, indent: Optional[int] = 2) -> None:
        Path(path).write_text(self.serialize(indent=indent) + "\n", encoding="utf-8")

    def branch_packet(self, branch_id: str) -> Dict[str, Any]:
        """Expose one active branch while keeping the complete set behind it."""

        return {
            "active_branch_id": self.get(branch_id).id,
            "active_branch": self.get(branch_id).to_dict(),
            "branch_set": self.to_dict(),
        }

    def iter_branch_packets(self) -> Iterator[Dict[str, Any]]:
        for branch in self.branches:
            yield self.branch_packet(branch.id)


__all__ = [
    "SCHEMA_VERSION",
    "AccessKind",
    "Branch",
    "BranchSet",
    "BranchStatus",
    "Gap",
    "InstrumentHistory",
    "PredictionElsewhere",
    "RecordPresence",
    "RecordState",
    "SuppressionCause",
    "TriageClass",
    "TriageResult",
]
