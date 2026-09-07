"""Frame estimation by probe selection and collapse reading.

Partition (load-bearing)::

    hand-authored probe library  -->  frame_probe.py  -->  frame estimate
    (input, human only)               selection + collapse reading ONLY

This module contains no probe generator.  A model that writes its own probes
reads its own frame back and calls it a finding, so ``Probe`` refuses any
author kind other than ``human`` and nothing here can mint a probe record.

Flow::

    library
      |
      | validity gate (runs FIRST, per probe)
      |   emitter_marker_load high          -> BLOCKED(contaminated)
      |   between/within variance ratio ~ 1 -> UNKNOWN_measurable (reads the PERSON)
      |   ratio >> 1                        -> VALID
      v
    loop
      probe 1 -> collapse observed -> narrow to frame set
      probe n -> selected for MAX separation of the remaining set (not importance)
      stop on confirmation (one frame) or UNKNOWN (contradiction / inseparable)
      out: frame estimate, remaining set, probes spent
      |
      +-- identity model (behaviour only, no interior)
      |     three observations -> fixed_position | instrument | UNKNOWN_measurable
      |     NULL REQUIRED: alternative generators filed as an open, untested BranchSet
      |
      +-- known failure: instrument read as inconsistency / evasion / masking, then a
          search for the "real" identity underneath.  Same shape as assuming a value
          exists, finding none, and reporting ABSENCE instead of WRONG_INSTRUMENT.

F addition: a term with N live senses is N branches with one origin pattern.
N senses raises intake priority.

Coupling record: does a model collapse an ambiguous term to one sense or hold
all senses as jointly intended.  One term, one turn.  Logged per model per
update boundary.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

from branch_set import Branch, BranchSet, SuppressionCause, _check_keys, _nonempty
from preference_free_rank import CriterionResult

PROBE_SCHEMA_VERSION = "1.0"
COUPLING_SCHEMA_VERSION = "1.0"

CONTAMINATED = "contaminated"
UNCALIBRATED = "uncalibrated"
PROBE_BUDGET = "probe_budget"
WRONG_INSTRUMENT = "WRONG_INSTRUMENT"
UNTESTED = "UNTESTED"


# --------------------------------------------------------------------------
# probe record (input; hand-authored)
# --------------------------------------------------------------------------


class AuthorKind(str, Enum):
    """The only admissible author kind.  Anything else is rejected at load."""

    HUMAN = "human"


Observation = Tuple[str, ...]
RawObservation = Union[str, Sequence[str], Mapping[str, float]]


def _weights(sense_space: Sequence[str], raw: RawObservation, where: str) -> Tuple[float, ...]:
    """Normalise a calibration observation to a weight vector over senses."""

    index = {sense: i for i, sense in enumerate(sense_space)}
    vector = [0.0] * len(sense_space)
    if isinstance(raw, str):
        items: Iterable[Tuple[str, float]] = [(raw, 1.0)]
    elif isinstance(raw, Mapping):
        items = [(str(k), float(v)) for k, v in raw.items()]
    else:
        items = [(str(sense), 1.0) for sense in raw]
    for sense, weight in items:
        if sense not in index:
            raise ValueError(f"{where}: unknown sense {sense!r}")
        if not math.isfinite(weight) or weight < 0:
            raise ValueError(f"{where}: weights must be finite and non-negative")
        vector[index[sense]] += weight
    total = sum(vector)
    if total <= 0:
        raise ValueError(f"{where}: an observation must select at least one sense")
    return tuple(w / total for w in vector)


@dataclass(frozen=True)
class Probe:
    """One hand-authored probe.  ``author_kind`` must be human."""

    id: str
    term_or_phrase: str
    sense_space: Tuple[str, ...]
    frame_index: Dict[str, Tuple[str, ...]]
    emitter_marker_load: float
    author: str
    author_kind: AuthorKind = AuthorKind.HUMAN
    calibration: Dict[str, Tuple[Tuple[float, ...], ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _nonempty(self.id, "id"))
        object.__setattr__(self, "term_or_phrase", _nonempty(self.term_or_phrase, "term_or_phrase"))
        object.__setattr__(self, "author", _nonempty(self.author, "author"))
        try:
            kind = self.author_kind if isinstance(self.author_kind, AuthorKind) else AuthorKind(self.author_kind)
        except ValueError as exc:
            raise ValueError(
                "probes are hand-authored input; author_kind must be 'human' "
                "(a model generating its own probes reads its own frame back)"
            ) from exc
        object.__setattr__(self, "author_kind", kind)

        senses = tuple(_nonempty(s, "sense") for s in self.sense_space)
        if not senses or len(set(senses)) != len(senses):
            raise ValueError("sense_space must be a non-empty list of unique senses")
        object.__setattr__(self, "sense_space", senses)

        index: Dict[str, Tuple[str, ...]] = {}
        for sense, frames in dict(self.frame_index).items():
            if sense not in senses:
                raise ValueError(f"frame_index sense {sense!r} is not in sense_space")
            if isinstance(frames, str):
                frames = (frames,)
            frame_tuple = tuple(_nonempty(f, "frame") for f in frames)
            if len(set(frame_tuple)) != len(frame_tuple):
                raise ValueError(f"frame_index[{sense!r}] lists a frame twice")
            index[sense] = frame_tuple
        for sense in senses:
            index.setdefault(sense, ())
        if not any(index.values()):
            raise ValueError("frame_index must map at least one sense to a frame")
        object.__setattr__(self, "frame_index", index)

        try:
            load = float(self.emitter_marker_load)
        except (TypeError, ValueError) as exc:
            raise ValueError("emitter_marker_load must be a number in [0, 1]") from exc
        if not math.isfinite(load) or not 0.0 <= load <= 1.0:
            raise ValueError("emitter_marker_load must be a number in [0, 1]")
        object.__setattr__(self, "emitter_marker_load", load)

        calibration: Dict[str, Tuple[Tuple[float, ...], ...]] = {}
        for frame, observations in dict(self.calibration).items():
            frame = _nonempty(frame, "calibration frame")
            rows = []
            for raw in observations:
                if isinstance(raw, tuple) and raw and all(isinstance(x, float) for x in raw):
                    if len(raw) != len(senses) or abs(sum(raw) - 1.0) > 1e-9:
                        raise ValueError(f"calibration[{frame!r}]: malformed weight vector")
                    rows.append(tuple(raw))
                else:
                    rows.append(_weights(senses, raw, f"calibration[{frame!r}]"))
            calibration[frame] = tuple(rows)
        object.__setattr__(self, "calibration", calibration)

    @property
    def frames(self) -> Tuple[str, ...]:
        """Frames this probe speaks to, in first-seen order."""

        seen: List[str] = []
        for sense in self.sense_space:
            for frame in self.frame_index[sense]:
                if frame not in seen:
                    seen.append(frame)
        return tuple(seen)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "term_or_phrase": self.term_or_phrase,
            "sense_space": list(self.sense_space),
            "frame_index": {sense: list(frames) for sense, frames in self.frame_index.items()},
            "emitter_marker_load": self.emitter_marker_load,
            "author": self.author,
            "author_kind": self.author_kind.value,
            "calibration": {
                frame: [dict(zip(self.sense_space, row)) for row in rows]
                for frame, rows in self.calibration.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Probe":
        _check_keys(
            data,
            (
                "id",
                "term_or_phrase",
                "sense_space",
                "frame_index",
                "emitter_marker_load",
                "author",
                "author_kind",
                "calibration",
            ),
            "probe",
        )
        if "author_kind" not in data:
            raise ValueError("probe must declare author_kind ('human'); it is not defaulted on load")
        return cls(
            id=data["id"],
            term_or_phrase=data["term_or_phrase"],
            sense_space=tuple(data["sense_space"]),
            frame_index={k: tuple(v) if not isinstance(v, str) else (v,) for k, v in data["frame_index"].items()},
            emitter_marker_load=data["emitter_marker_load"],
            author=data["author"],
            author_kind=data["author_kind"],
            calibration={k: tuple(v) for k, v in data.get("calibration", {}).items()},
        )


def load_library(source: Union[str, os.PathLike, Mapping[str, Any]]) -> List[Probe]:
    """Load a hand-authored probe library from JSON text, a path, or a mapping."""

    if isinstance(source, Mapping):
        data: Any = source
    else:
        if isinstance(source, os.PathLike):
            raw = Path(source).read_text(encoding="utf-8")
        else:
            stripped = source.lstrip()
            if stripped.startswith("{"):
                raw = source
            else:
                raw = Path(source).read_text(encoding="utf-8")
        data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("probe library JSON must be an object")
    _check_keys(data, ("schema_version", "probes"), "probe library")
    if data.get("schema_version") != PROBE_SCHEMA_VERSION:
        raise ValueError(f"unsupported probe schema_version; expected {PROBE_SCHEMA_VERSION!r}")
    probes = [Probe.from_dict(item) for item in data.get("probes", [])]
    ids = [probe.id for probe in probes]
    if len(ids) != len(set(ids)):
        raise ValueError("probe ids must be unique")
    return probes


# --------------------------------------------------------------------------
# validity gate (runs first)
# --------------------------------------------------------------------------


class GateStatus(str, Enum):
    VALID = "valid"
    UNKNOWN_MEASURABLE = "UNKNOWN_measurable"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class GateResult:
    probe_id: str
    status: GateStatus
    rule: str
    emitter_marker_load: float
    between_frame_variance: Optional[float] = None
    within_frame_variance: Optional[float] = None
    ratio: Optional[float] = None
    blocker: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "status": self.status.value,
            "rule": self.rule,
            "emitter_marker_load": self.emitter_marker_load,
            "between_frame_variance": self.between_frame_variance,
            "within_frame_variance": self.within_frame_variance,
            "ratio": None if self.ratio is None or math.isinf(self.ratio) else self.ratio,
            "blocker": self.blocker,
        }

    def to_criterion_result(self) -> Optional[CriterionResult]:
        if self.status is GateStatus.VALID:
            return None
        if self.status is GateStatus.BLOCKED:
            return CriterionResult.blocked(self.blocker or CONTAMINATED, note=self.rule)
        return CriterionResult.unknown_measurable(note=self.rule)


def _sq_distance(a: Sequence[float], b: Sequence[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b))


def frame_variances(probe: Probe) -> Optional[Tuple[float, float]]:
    """(between, within) variance of calibration collapse vectors across frames.

    One-way decomposition over sense-weight vectors.  Returns None when the
    calibration cannot support it (fewer than two frames, or fewer than two
    observations in any frame).
    """

    groups = [rows for rows in probe.calibration.values() if rows]
    if len(groups) < 2 or any(len(rows) < 2 for rows in groups):
        return None
    dim = len(probe.sense_space)
    total = sum(len(rows) for rows in groups)
    grand = [sum(row[i] for rows in groups for row in rows) / total for i in range(dim)]
    means = [[sum(row[i] for row in rows) / len(rows) for i in range(dim)] for rows in groups]
    between = sum(len(rows) * _sq_distance(mean, grand) for rows, mean in zip(groups, means))
    between /= len(groups) - 1
    within = sum(_sq_distance(row, mean) for rows, mean in zip(groups, means) for row in rows)
    within /= total - len(groups)
    return between, within


@dataclass(frozen=True)
class ValidityGate:
    """Declared thresholds.  ``valid_ratio`` is what ">> 1" means here."""

    valid_ratio: float = 4.0
    contamination_load: float = 0.5

    def __post_init__(self) -> None:
        if self.valid_ratio <= 1.0:
            raise ValueError("valid_ratio must exceed 1")
        if not 0.0 < self.contamination_load <= 1.0:
            raise ValueError("contamination_load must lie in (0, 1]")

    def check(self, probe: Probe) -> GateResult:
        load = probe.emitter_marker_load
        if load >= self.contamination_load:
            return GateResult(
                probe.id,
                GateStatus.BLOCKED,
                rule=(
                    f"emitter_marker_load={load:.2f} >= {self.contamination_load} -> "
                    f"blocked({CONTAMINATED}): emitting the probe declares the prober's frame"
                ),
                emitter_marker_load=load,
                blocker=CONTAMINATED,
            )
        variances = frame_variances(probe)
        if variances is None:
            return GateResult(
                probe.id,
                GateStatus.BLOCKED,
                rule=(
                    f"calibration needs >= 2 frames with >= 2 observations each -> "
                    f"blocked({UNCALIBRATED})"
                ),
                emitter_marker_load=load,
                blocker=UNCALIBRATED,
            )
        between, within = variances
        if within == 0.0 and between == 0.0:
            return GateResult(
                probe.id,
                GateStatus.UNKNOWN_MEASURABLE,
                rule="no variance between or within frames -> probe separates nothing; UNKNOWN_measurable",
                emitter_marker_load=load,
                between_frame_variance=between,
                within_frame_variance=within,
                ratio=None,
            )
        ratio = math.inf if within == 0.0 else between / within
        if ratio >= self.valid_ratio:
            return GateResult(
                probe.id,
                GateStatus.VALID,
                rule=f"between/within={ratio:.3g} >= {self.valid_ratio} -> valid",
                emitter_marker_load=load,
                between_frame_variance=between,
                within_frame_variance=within,
                ratio=ratio,
            )
        return GateResult(
            probe.id,
            GateStatus.UNKNOWN_MEASURABLE,
            rule=(
                f"between/within={ratio:.3g} < {self.valid_ratio} -> probe reads the PERSON, "
                "not the frame; UNKNOWN_measurable"
            ),
            emitter_marker_load=load,
            between_frame_variance=between,
            within_frame_variance=within,
            ratio=ratio,
        )


# --------------------------------------------------------------------------
# collapse reading
# --------------------------------------------------------------------------


class CollapseReading(str, Enum):
    COLLAPSED = "collapsed"
    HELD = "held"
    PARTIAL = "partial"


def read_collapse(sense_space: Sequence[str], observed: Iterable[str]) -> Tuple[CollapseReading, Observation]:
    """Structural reading of which senses a response treated as intended."""

    senses = tuple(sense_space)
    seen: List[str] = []
    for sense in observed:
        if sense not in senses:
            raise ValueError(f"observed sense {sense!r} is not in the probe's sense_space")
        if sense not in seen:
            seen.append(sense)
    if not seen:
        raise ValueError("an observation must name at least one sense")
    ordered = tuple(s for s in senses if s in seen)
    if len(ordered) == 1:
        return CollapseReading.COLLAPSED, ordered
    if len(ordered) == len(senses):
        return CollapseReading.HELD, ordered
    return CollapseReading.PARTIAL, ordered


# --------------------------------------------------------------------------
# selection + narrowing loop
# --------------------------------------------------------------------------


class SessionOutcome(str, Enum):
    OPEN = "open"
    CONFIRMED = "confirmed"
    UNKNOWN_MEASURABLE = "UNKNOWN_measurable"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class Step:
    probe_id: str
    reading: CollapseReading
    observed: Observation
    remaining_before: Tuple[str, ...]
    remaining_after: Tuple[str, ...]
    rule: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "reading": self.reading.value,
            "observed": list(self.observed),
            "remaining_before": list(self.remaining_before),
            "remaining_after": list(self.remaining_after),
            "rule": self.rule,
        }


@dataclass
class FrameEstimate:
    outcome: SessionOutcome
    frame: Optional[str]
    remaining: Tuple[str, ...]
    probes_spent: List[Step]
    gate_results: List[GateResult]
    rule: str
    blocker: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "frame": self.frame,
            "remaining": list(self.remaining),
            "probes_spent": [step.to_dict() for step in self.probes_spent],
            "gate_results": [result.to_dict() for result in self.gate_results],
            "rule": self.rule,
            "blocker": self.blocker,
        }

    def to_criterion_result(self) -> CriterionResult:
        if self.outcome is SessionOutcome.CONFIRMED:
            return CriterionResult.variable_unidentified(
                note=json.dumps({"frame": self.frame, "rule": self.rule}, sort_keys=True)
            )
        if self.outcome is SessionOutcome.BLOCKED:
            return CriterionResult.blocked(self.blocker or PROBE_BUDGET, note=self.rule)
        return CriterionResult.unknown_measurable(note=self.rule)


def _cells(probe: Probe, remaining: Sequence[str]) -> Dict[str, Tuple[str, ...]]:
    """Remaining set after each single-sense collapse of ``probe``."""

    informed = set(probe.frames)
    uninformed = tuple(f for f in remaining if f not in informed)
    cells = {}
    for sense in probe.sense_space:
        consistent = set(probe.frame_index[sense])
        cells[sense] = tuple(f for f in remaining if f in consistent) + uninformed
    return cells


def separation_score(probe: Probe, remaining: Sequence[str]) -> float:
    """Expected size of the remaining set after this probe (lower = more separation).

    Uniform over candidate frames; the weight of a cell is its own size.  No
    importance weighting enters.
    """

    n = len(remaining)
    if n == 0:
        return 0.0
    return sum(len(cell) ** 2 for cell in _cells(probe, remaining).values()) / n


class FrameProbeSession:
    """Select probes for maximal separation and narrow on observed collapse.

    Observations are supplied by the caller (a human reader or a transcript
    reader).  The session never generates probes and never infers senses
    from text.
    """

    def __init__(
        self,
        library: Sequence[Probe],
        *,
        frames: Optional[Iterable[str]] = None,
        gate: Optional[ValidityGate] = None,
        max_probes: Optional[int] = None,
    ) -> None:
        if not library:
            raise ValueError("a probe library is required; this module does not generate probes")
        ids = [probe.id for probe in library]
        if len(ids) != len(set(ids)):
            raise ValueError("probe ids must be unique")
        if max_probes is not None and max_probes < 1:
            raise ValueError("max_probes must be positive")
        self.gate = gate or ValidityGate()
        self.gate_results = [self.gate.check(probe) for probe in library]
        self._probes = {probe.id: probe for probe in library}
        self.valid_ids = [
            probe.id for probe, result in zip(library, self.gate_results)
            if result.status is GateStatus.VALID
        ]
        if frames is None:
            seen: List[str] = []
            for probe_id in self.valid_ids:
                for frame in self._probes[probe_id].frames:
                    if frame not in seen:
                        seen.append(frame)
            frames = seen
        self.remaining: Tuple[str, ...] = tuple(dict.fromkeys(_nonempty(f, "frame") for f in frames))
        self.max_probes = max_probes
        self.steps: List[Step] = []
        self._spent: Set[str] = set()

    # -- selection ---------------------------------------------------------

    def next_probe(self) -> Optional[Probe]:
        """The unspent valid probe with the greatest separation of the remaining set."""

        if len(self.remaining) <= 1:
            return None
        if self.max_probes is not None and len(self.steps) >= self.max_probes:
            return None
        best: Optional[Tuple[float, str]] = None
        for probe_id in self.valid_ids:
            if probe_id in self._spent:
                continue
            score = separation_score(self._probes[probe_id], self.remaining)
            if score >= len(self.remaining) - 1e-12:
                continue  # cannot narrow the remaining set
            key = (score, probe_id)
            if best is None or key < best:
                best = key
        return self._probes[best[1]] if best else None

    # -- narrowing ---------------------------------------------------------

    def observe(self, probe_id: str, observed: Iterable[str]) -> Step:
        if probe_id not in self._probes:
            raise KeyError(probe_id)
        if probe_id not in self.valid_ids:
            raise ValueError(f"probe {probe_id!r} did not pass the validity gate")
        if probe_id in self._spent:
            raise ValueError(f"probe {probe_id!r} already spent")
        probe = self._probes[probe_id]
        reading, senses = read_collapse(probe.sense_space, observed)
        consistent = set(probe.frame_index[senses[0]])
        for sense in senses[1:]:
            consistent &= set(probe.frame_index[sense])
        informed = set(probe.frames)
        before = self.remaining
        after = tuple(f for f in before if f in consistent or f not in informed)
        rule = (
            f"{reading.value} {list(senses)} -> frames consistent {sorted(consistent)}; "
            f"{len(before)} -> {len(after)} remaining"
        )
        step = Step(probe_id, reading, senses, before, after, rule)
        self.steps.append(step)
        self._spent.add(probe_id)
        self.remaining = after
        return step

    # -- result ------------------------------------------------------------

    def result(self) -> FrameEstimate:
        spent = len(self.steps)
        if len(self.remaining) == 1:
            return FrameEstimate(
                SessionOutcome.CONFIRMED,
                self.remaining[0],
                self.remaining,
                list(self.steps),
                list(self.gate_results),
                rule=f"one frame remains after {spent} probe(s) -> confirmed",
            )
        if not self.remaining:
            return FrameEstimate(
                SessionOutcome.UNKNOWN_MEASURABLE,
                None,
                self.remaining,
                list(self.steps),
                list(self.gate_results),
                rule=f"observations consistent with no candidate frame after {spent} probe(s) -> UNKNOWN_measurable",
            )
        if self.max_probes is not None and spent >= self.max_probes:
            return FrameEstimate(
                SessionOutcome.BLOCKED,
                None,
                self.remaining,
                list(self.steps),
                list(self.gate_results),
                rule=f"{len(self.remaining)} frames remain at max_probes={self.max_probes} -> blocked({PROBE_BUDGET})",
                blocker=PROBE_BUDGET,
            )
        if self.next_probe() is None:
            if not self.valid_ids:
                return FrameEstimate(
                    SessionOutcome.BLOCKED,
                    None,
                    self.remaining,
                    list(self.steps),
                    list(self.gate_results),
                    rule="no probe passed the validity gate -> blocked(no_valid_probe)",
                    blocker="no_valid_probe",
                )
            return FrameEstimate(
                SessionOutcome.UNKNOWN_MEASURABLE,
                None,
                self.remaining,
                list(self.steps),
                list(self.gate_results),
                rule=(
                    f"{len(self.remaining)} frames remain and no valid probe separates them "
                    f"after {spent} probe(s) -> UNKNOWN_measurable"
                ),
            )
        return FrameEstimate(
            SessionOutcome.OPEN,
            None,
            self.remaining,
            list(self.steps),
            list(self.gate_results),
            rule=f"{len(self.remaining)} frames remain; probes available",
        )


def run_session(
    library: Sequence[Probe],
    respond: Callable[[Probe], Iterable[str]],
    *,
    frames: Optional[Iterable[str]] = None,
    gate: Optional[ValidityGate] = None,
    max_probes: Optional[int] = None,
) -> FrameEstimate:
    """Drive a session to a stop; ``respond`` supplies the observed senses."""

    session = FrameProbeSession(library, frames=frames, gate=gate, max_probes=max_probes)
    while True:
        probe = session.next_probe()
        if probe is None:
            return session.result()
        session.observe(probe.id, respond(probe))
        outcome = session.result().outcome
        if outcome is not SessionOutcome.OPEN:
            return session.result()


# --------------------------------------------------------------------------
# identity model: behaviour only, no interior
# --------------------------------------------------------------------------


class Grade(str, Enum):
    LOW = "low"
    HIGH = "high"
    UNOBSERVED = "unobserved"


class IdentityModel(str, Enum):
    FIXED_POSITION = "fixed_position"
    INSTRUMENT = "instrument"
    UNKNOWN_MEASURABLE = "UNKNOWN_measurable"


BEHAVIOUR = "behavior"


@dataclass(frozen=True)
class IdentityObservations:
    """Three behavioural observations.  No self-report, no interior field exists."""

    boundary_cost: Grade
    prior_frames_defended: Grade
    variance_reported_as_conflict: Grade
    source: str = BEHAVIOUR

    def __post_init__(self) -> None:
        for name in ("boundary_cost", "prior_frames_defended", "variance_reported_as_conflict"):
            value = getattr(self, name)
            object.__setattr__(self, name, value if isinstance(value, Grade) else Grade(value))
        if self.source != BEHAVIOUR:
            raise ValueError("identity observations are graded from behavior only; no interior source")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_cost": self.boundary_cost.value,
            "prior_frames_defended": self.prior_frames_defended.value,
            "variance_reported_as_conflict": self.variance_reported_as_conflict.value,
            "source": self.source,
        }


IDENTITY_ORIGIN = "identity_three_observations"


def identity_null_branch_set(model: IdentityModel, *, cost: float = 1.0) -> BranchSet:
    """What else produces the same three observations.  Open and untested."""

    discriminator = f"{UNTESTED}: vary context stakes and prober frame; re-observe the three"
    if model is IdentityModel.INSTRUMENT:
        rows = [
            ("instrument", "identity = instrument; frames are tools, context-variance is the reading",
             "low boundary cost persists across high-stakes contexts; no defence at any stake level"),
            ("no_prior_position", "never held the prior frame; there was nothing to exit or defend",
             "same low cost when a frame the subject demonstrably held earlier is exited"),
            ("low_stakes", "frames carry no cost for this subject in this context",
             "cost appears once the context raises the stakes of the frame"),
            ("accommodation", "mirrors the prober's frame; compliance, not instrument",
             "collapse tracks the prober's emitter markers rather than the term"),
            ("suppressed_report", "conflict present but unreported (masking)",
             "conflict report appears under conditions that relax the suppression"),
        ]
        origin = f"{IDENTITY_ORIGIN}:instrument_pattern"
    elif model is IdentityModel.FIXED_POSITION:
        rows = [
            ("fixed_position", "identity = fixed position; frame boundary is an identity boundary",
             "defence and conflict report persist when role and sunk cost are removed"),
            ("role_constraint", "an external role requires defending the frame",
             "defence disappears when the role is lifted"),
            ("sunk_cost", "investment in the prior frame independent of identity",
             "defence scales with investment, not with identity claims"),
            ("real_conflict", "the frames genuinely conflict in this context; the report is accurate",
             "conflict report vanishes in contexts where the frames are compatible"),
        ]
        origin = f"{IDENTITY_ORIGIN}:fixed_position_pattern"
    else:
        raise ValueError("null branch set requires a graded identity model")
    return BranchSet(
        [
            Branch(
                id=branch_id,
                generator=generator,
                origin_pattern=origin,
                predicted_divergence=divergence,
                discriminator=discriminator,
                cost=cost,
                suppression_cause=SuppressionCause.PRIOR,
            )
            for branch_id, generator, divergence in rows
        ]
    )


@dataclass
class IdentityReading:
    model: IdentityModel
    rule: str
    observations: IdentityObservations
    null_branch_set: Optional[BranchSet]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model.value,
            "rule": self.rule,
            "observations": self.observations.to_dict(),
            "null_branch_set": self.null_branch_set.to_dict() if self.null_branch_set else None,
        }


def grade_identity(observations: IdentityObservations) -> IdentityReading:
    """Grade fixed_position | instrument from the three observations only.

    The null branch set is attached whenever a model is graded: the grade is
    a candidate generator among alternatives, all open and untested.
    """

    grades = (
        observations.boundary_cost,
        observations.prior_frames_defended,
        observations.variance_reported_as_conflict,
    )
    if Grade.UNOBSERVED in grades:
        return IdentityReading(
            IdentityModel.UNKNOWN_MEASURABLE,
            "an observation is missing -> UNKNOWN_measurable (observe, do not infer)",
            observations,
            None,
        )
    if all(g is Grade.HIGH for g in grades):
        model = IdentityModel.FIXED_POSITION
        rule = "cost paid, prior frames defended, variance reported as conflict -> fixed_position (candidate; null set open)"
    elif all(g is Grade.LOW for g in grades):
        model = IdentityModel.INSTRUMENT
        rule = (
            "no boundary cost, no defence, variance reported as variance -> instrument "
            "(candidate; null set open). Context-variance is the reading; do not search "
            "for a position underneath"
        )
    else:
        return IdentityReading(
            IdentityModel.UNKNOWN_MEASURABLE,
            "mixed grades -> UNKNOWN_measurable (neither pattern; do not force one)",
            observations,
            None,
        )
    return IdentityReading(model, rule, observations, identity_null_branch_set(model))


# --------------------------------------------------------------------------
# known failure to encode
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class KnownFailure:
    name: str
    observed_pattern: str
    misread_as: Tuple[str, ...]
    then: str
    same_shape_as: str
    correct_return: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "observed_pattern": self.observed_pattern,
            "misread_as": list(self.misread_as),
            "then": self.then,
            "same_shape_as": self.same_shape_as,
            "correct_return": self.correct_return,
        }


MISREAD_LABELS = ("inconsistency", "evasion", "masking")

INSTRUMENT_MISREAD = KnownFailure(
    name="instrument_read_as_evasion",
    observed_pattern="identity=instrument: frames change with context at no boundary cost",
    misread_as=MISREAD_LABELS,
    then="model searches for the 'real' identity underneath",
    same_shape_as="assuming a value exists, finding none, reporting ABSENCE instead of WRONG_INSTRUMENT",
    correct_return=WRONG_INSTRUMENT,
)

KNOWN_FAILURES: Tuple[KnownFailure, ...] = (INSTRUMENT_MISREAD,)


def underlying_position(reading: IdentityReading) -> CriterionResult:
    """Answer "what is the real position underneath?" without committing the failure.

    For an instrument-graded subject the question applies the wrong
    instrument: there is no fixed value to be absent.  The return is
    OUT_OF_ENVELOPE tagged WRONG_INSTRUMENT, never an absence.
    """

    if reading.model is IdentityModel.INSTRUMENT:
        return CriterionResult.out_of_envelope(
            f"{WRONG_INSTRUMENT}: subject graded instrument; a fixed position is not the "
            "quantity present. Context-variance is the reading, not a mask over one."
        )
    if reading.model is IdentityModel.FIXED_POSITION:
        return CriterionResult.unknown_measurable(
            note="graded fixed_position; the content of the position is not read by this instrument"
        )
    return CriterionResult.unknown_measurable(note=reading.rule)


def label_reading(reading: IdentityReading, label: str) -> CriterionResult:
    """Guard a free-text label against the known misread."""

    normalized = label.strip().lower()
    if reading.model is IdentityModel.INSTRUMENT and normalized in MISREAD_LABELS:
        return CriterionResult.out_of_envelope(
            f"{WRONG_INSTRUMENT}: label {label!r} on an instrument-graded subject is the known "
            f"failure {INSTRUMENT_MISREAD.name}"
        )
    return CriterionResult.unknown_measurable(note=f"label {label!r} recorded; not a measurement")


# --------------------------------------------------------------------------
# F addition: term-level branch sets (N live senses = N branches)
# --------------------------------------------------------------------------

TERM_DISCRIMINATOR = "frame probe collapse reading: one term, one turn"


def term_branch_set(probe: Probe, *, cost: float = 1.0) -> BranchSet:
    """Each live sense is a branch; the term is the shared origin pattern."""

    return BranchSet(
        [
            Branch(
                id=f"{probe.id}:{sense}",
                generator=f"sense: {sense}",
                origin_pattern=probe.term_or_phrase,
                predicted_divergence=(
                    f"collapse to {sense!r} indexes frames {list(probe.frame_index[sense])}"
                    if probe.frame_index[sense]
                    else f"collapse to {sense!r} indexes no frame"
                ),
                discriminator=TERM_DISCRIMINATOR,
                cost=cost,
                suppression_cause=SuppressionCause.PRIOR,
            )
            for sense in probe.sense_space
        ]
    )


@dataclass(frozen=True)
class TermIntake:
    term: str
    probe_id: str
    n_senses: int
    priority: int
    branch_set: BranchSet

    def to_dict(self) -> Dict[str, Any]:
        return {
            "term": self.term,
            "probe_id": self.probe_id,
            "n_senses": self.n_senses,
            "priority": self.priority,
            "branch_set": self.branch_set.to_dict(),
        }


def term_intake_queue(library: Sequence[Probe], *, cost: float = 1.0) -> List[TermIntake]:
    """Intake order: N live senses raises priority (same rule as mechanisms)."""

    items = [
        TermIntake(
            term=probe.term_or_phrase,
            probe_id=probe.id,
            n_senses=len(probe.sense_space),
            priority=len(probe.sense_space),
            branch_set=term_branch_set(probe, cost=cost),
        )
        for probe in library
    ]
    return sorted(items, key=lambda item: (-item.priority, item.term, item.probe_id))


# --------------------------------------------------------------------------
# coupling record: collapse vs hold, per model per update boundary
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CouplingEntry:
    model: str
    update_boundary: str
    date: str
    reading: CollapseReading
    term: Optional[str] = None
    observed: Tuple[str, ...] = ()
    note: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "model", _nonempty(self.model, "model"))
        object.__setattr__(self, "update_boundary", _nonempty(self.update_boundary, "update_boundary"))
        object.__setattr__(self, "date", _nonempty(self.date, "date"))
        object.__setattr__(
            self,
            "reading",
            self.reading if isinstance(self.reading, CollapseReading) else CollapseReading(self.reading),
        )
        object.__setattr__(self, "observed", tuple(self.observed))
        if self.term is not None:
            object.__setattr__(self, "term", _nonempty(self.term, "term"))

    @property
    def key(self) -> Tuple[str, str, Optional[str]]:
        return (self.model, self.update_boundary, self.term)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "update_boundary": self.update_boundary,
            "date": self.date,
            "reading": self.reading.value,
            "term": self.term,
            "observed": list(self.observed),
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CouplingEntry":
        _check_keys(
            data,
            ("model", "update_boundary", "date", "reading", "term", "observed", "note"),
            "coupling entry",
        )
        return cls(
            model=data["model"],
            update_boundary=data["update_boundary"],
            date=data["date"],
            reading=data["reading"],
            term=data.get("term"),
            observed=tuple(data.get("observed", ())),
            note=data.get("note"),
        )


SEED_COUPLING_ENTRY = CouplingEntry(
    model="GPT",
    update_boundary="2026-09-07",
    date="2026-09-07",
    reading=CollapseReading.HELD,
    term=None,
    note="held all senses as jointly intended; term not recorded in the work order, date used as update boundary",
)


@dataclass
class CouplingLog:
    entries: List[CouplingEntry] = field(default_factory=list)
    schema_version: str = COUPLING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != COUPLING_SCHEMA_VERSION:
            raise ValueError(f"unsupported coupling schema_version; expected {COUPLING_SCHEMA_VERSION!r}")
        self.entries = [
            item if isinstance(item, CouplingEntry) else CouplingEntry.from_dict(item)
            for item in self.entries
        ]
        keys = [entry.key for entry in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("one entry per (model, update_boundary, term)")

    def add(self, entry: CouplingEntry) -> None:
        if any(existing.key == entry.key for existing in self.entries):
            raise ValueError(f"entry already logged for {entry.key}")
        self.entries.append(entry)

    def for_model(self, model: str) -> List[CouplingEntry]:
        return sorted(
            (entry for entry in self.entries if entry.model == model),
            key=lambda entry: (entry.update_boundary, entry.date, entry.term or ""),
        )

    def latest(self, model: str) -> Optional[CouplingEntry]:
        rows = self.for_model(model)
        return rows[-1] if rows else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def serialize(self, *, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, ensure_ascii=False, allow_nan=False)

    def write(self, path: Union[str, os.PathLike]) -> None:
        Path(path).write_text(self.serialize() + "\n", encoding="utf-8")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CouplingLog":
        _check_keys(data, ("schema_version", "entries"), "coupling log")
        return cls(entries=list(data.get("entries", [])), schema_version=data["schema_version"])

    @classmethod
    def load(cls, source: Union[str, os.PathLike]) -> "CouplingLog":
        if isinstance(source, os.PathLike):
            raw = Path(source).read_text(encoding="utf-8")
        else:
            stripped = source.lstrip()
            raw = source if stripped.startswith("{") else Path(source).read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("coupling log JSON must be an object")
        return cls.from_dict(data)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    gate_cmd = sub.add_parser("gate", help="run the validity gate over a hand-authored library")
    gate_cmd.add_argument("library")

    run_cmd = sub.add_parser("run", help="select probes; read observed senses from stdin, one line per probe")
    run_cmd.add_argument("library")
    run_cmd.add_argument("--frames", nargs="*", default=None)
    run_cmd.add_argument("--max-probes", type=int, default=None)

    identity_cmd = sub.add_parser("identity", help="grade identity model from three behavioural observations")
    for name in ("boundary-cost", "defended", "conflict"):
        identity_cmd.add_argument(f"--{name}", choices=[g.value for g in Grade], required=True)

    intake_cmd = sub.add_parser("intake", help="term-level branch sets ordered by number of live senses")
    intake_cmd.add_argument("library")

    coupling_cmd = sub.add_parser("coupling", help="print a coupling log")
    coupling_cmd.add_argument("path")

    args = parser.parse_args(argv)
    if args.command == "gate":
        gate = ValidityGate()
        for probe in load_library(args.library):
            result = gate.check(probe)
            print(f"{probe.id:<24} {result.status.value:<20} {result.rule}")
        return 0
    if args.command == "run":
        library = load_library(args.library)

        def respond(probe: Probe) -> List[str]:
            print(f"probe {probe.id}: {probe.term_or_phrase}  senses={list(probe.sense_space)}", file=sys.stderr)
            line = sys.stdin.readline()
            if not line:
                raise SystemExit("no observation supplied")
            return [item.strip() for item in line.split(",") if item.strip()]

        estimate = run_session(library, respond, frames=args.frames, max_probes=args.max_probes)
        print(json.dumps(estimate.to_dict(), indent=2, sort_keys=True))
        return 0
    if args.command == "identity":
        reading = grade_identity(
            IdentityObservations(args.boundary_cost, args.defended, args.conflict)
        )
        print(json.dumps(reading.to_dict(), indent=2, sort_keys=True))
        return 0
    if args.command == "intake":
        for item in term_intake_queue(load_library(args.library)):
            print(f"priority={item.priority} senses={item.n_senses} {item.term} [{item.probe_id}]")
        return 0
    log = CouplingLog.load(args.path)
    for entry in log.entries:
        print(f"{entry.model:<12} {entry.update_boundary:<12} {entry.reading.value:<10} term={entry.term}")
    return 0


__all__ = [
    "BEHAVIOUR",
    "CONTAMINATED",
    "COUPLING_SCHEMA_VERSION",
    "IDENTITY_ORIGIN",
    "INSTRUMENT_MISREAD",
    "KNOWN_FAILURES",
    "MISREAD_LABELS",
    "PROBE_BUDGET",
    "PROBE_SCHEMA_VERSION",
    "SEED_COUPLING_ENTRY",
    "TERM_DISCRIMINATOR",
    "UNCALIBRATED",
    "UNTESTED",
    "WRONG_INSTRUMENT",
    "AuthorKind",
    "CollapseReading",
    "CouplingEntry",
    "CouplingLog",
    "FrameEstimate",
    "FrameProbeSession",
    "GateResult",
    "GateStatus",
    "Grade",
    "IdentityModel",
    "IdentityObservations",
    "IdentityReading",
    "KnownFailure",
    "Probe",
    "SessionOutcome",
    "Step",
    "TermIntake",
    "ValidityGate",
    "frame_variances",
    "grade_identity",
    "identity_null_branch_set",
    "label_reading",
    "load_library",
    "read_collapse",
    "run_session",
    "separation_score",
    "term_branch_set",
    "term_intake_queue",
    "underlying_position",
]


if __name__ == "__main__":
    sys.exit(main())
