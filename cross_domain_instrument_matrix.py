"""
Cross-domain instrument matrix.

Purpose
-------
Map how different methodological traditions handle five interface questions:

    R = representation
    D = discriminability
    P = provenance recoverability
    T = transformation / scope
    V = instrument validation

This is a comparative instrument, not a claim that the domains are equivalent.

Important:
    - "unmeasured" is not "absent"
    - "partial" is not "failure"
    - "no row" is neither: it is not-yet-looked-at, and is printed as such
    - a gap is an observation about the current instrument/interface
    - evidence status is retained explicitly
    - no status is promoted merely because several domains appear similar
    - there is no FAIL state anywhere in this file (CoverageError is a
      check that refuses to load an incomplete matrix, not a cell status)

Lineage
-------
[obs]  Directly established from inspected source/repository material.
[lit]  Literature/source-supported.
[inf]  Model-generated inference or proposed mapping.
[open]  Deliberately unresolved.
[gap]  Missing measurement or inaccessible evidence.

Lineage is PER CELL.  Two lineages exist and are kept apart:

    Evidence.lineage    how the source CLAIM was established
                        ([lit] literature, [obs] this repository)
    Instrument.lineage  how the R/D/P/T/V STATUS of this cell was established
                        (authoritative for the matrix)

Rule for the cell tag (applied to every row, external and method-layer):

    [obs] / [lit]  the status follows from the source's own stated behaviour
                   or vocabulary with no translation step: the source names
                   the axis quantity, or does the thing the axis names.
    [inf]          a translation step is needed: the source does X, and this
                   matrix reads X as the axis quantity.  The mapping is ours.
    [open]         the reading is a placeholder for an interface this matrix
                   deliberately holds open (the P column of the method layer).
    [gap]          the status could not be established from inspectable
                   material.

Re-tag record.  Rows were originally tagged through one shared Evidence
object per source ([lit] external, [obs] method-layer).  That tag is kept
on ``prior_lineage`` and the reason for any change on ``lineage_reason``;
nothing is overwritten.  ``LINEAGE_DISTRIBUTION_BEFORE_RETAG`` keeps the
prior distribution readable.

Energy map
----------
::

    Instrument rows (one record = one cell reading, tagged per cell)
        |
        +-- coverage_check()     every module on disk has >= 1 row, else CoverageError
        |                        (runs at import; a silent omission cannot recur)
        +-- matrix()             key -> axis -> Cell
        |     Cell keeps EVERY record; status = strongest unresolved (rule named)
        |     records differ in status -> Cell.collided; collisions() lists them
        |     a collision is a result: not resolved, not averaged, no winner
        +-- contradiction_scan() where do records' evidence disagree?
        |     zero is a real finding and is recorded as one
        |     what the scan cannot see is a [gap] in MATRIX_GAPS
        +-- lineage_distribution()  [obs]/[lit]/[inf]/[open]/[gap] counts,
                                    before and after the re-tag

Collision vs CONTRADICTORY:

    collision      two or more RECORDS in one cell disagree on status
                   (a property of the cell, held alongside its reported status)
    CONTRADICTORY  the EVIDENCE for one record does not agree with itself or
                   with other evidence in the same cell (a record status)

The matrix is intended to be broken.

CC0
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional


class Status(str, Enum):
    COVERED = "covered"
    PARTIAL = "partial"
    UNMEASURED = "unmeasured"
    CONTRADICTORY = "contradictory"


class Axis(str, Enum):
    REPRESENTATION = "R"
    DISCRIMINABILITY = "D"
    PROVENANCE = "P"
    TRANSFORMATION = "T"
    VALIDATION = "V"


AXES: tuple[Axis, ...] = (
    Axis.REPRESENTATION,
    Axis.DISCRIMINABILITY,
    Axis.PROVENANCE,
    Axis.TRANSFORMATION,
    Axis.VALIDATION,
)

LINEAGE_TAGS: tuple[str, ...] = ("[obs]", "[lit]", "[inf]", "[open]", "[gap]")

# Reported cell status when records disagree: the strongest unresolved state.
# Declared here so the rule is inspectable; the constituent records are kept.
STATUS_PRIORITY = {
    Status.COVERED: 0,
    Status.PARTIAL: 1,
    Status.UNMEASURED: 2,
    Status.CONTRADICTORY: 3,
}


def _check_lineage(tag: str, name: str) -> None:
    if tag not in LINEAGE_TAGS:
        raise ValueError(f"{name} must be one of {', '.join(LINEAGE_TAGS)}; got {tag!r}")


@dataclass(frozen=True)
class Evidence:
    """A source and the claim taken from it.

    ``lineage`` is the lineage of the CLAIM.  It is not the lineage of any
    cell; cells carry their own (``Instrument.lineage``).
    """

    source: str
    claim: str
    lineage: str

    def __post_init__(self) -> None:
        _check_lineage(self.lineage, "Evidence.lineage")

    def to_dict(self) -> dict:
        return {"source": self.source, "claim": self.claim, "claim_lineage": self.lineage}


@dataclass(frozen=True)
class Instrument:
    """One cell reading: domain::instrument x axis -> status, with its own lineage.

    ``prior_lineage``   the tag this row carried before the per-cell re-tag
                        ("" for rows that had no prior tag)
    ``lineage_reason``  why the row carries the tag it does; required when
                        the tag changed from ``prior_lineage``
    """

    domain: str
    instrument: str
    axis: Axis
    status: Status
    evidence: Evidence
    lineage: str
    note: str = ""
    prior_lineage: str = ""
    lineage_reason: str = ""

    def __post_init__(self) -> None:
        _check_lineage(self.lineage, "Instrument.lineage")
        if self.prior_lineage:
            _check_lineage(self.prior_lineage, "Instrument.prior_lineage")
            if self.prior_lineage != self.lineage and not self.lineage_reason.strip():
                raise ValueError(
                    f"{self.key}[{self.axis.value}]: lineage changed "
                    f"{self.prior_lineage} -> {self.lineage} without a lineage_reason"
                )

    @property
    def key(self) -> str:
        return f"{self.domain}::{self.instrument}"

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "instrument": self.instrument,
            "axis": self.axis.value,
            "status": self.status.value,
            "evidence": self.evidence.to_dict(),
            "lineage": self.lineage,
            "prior_lineage": self.prior_lineage,
            "lineage_reason": self.lineage_reason,
            "note": self.note,
        }


# ---------------------------------------------------------------------------
# External evidence
#
# Evidence.lineage here is [lit]: the claim is literature-supported.  The
# cell tags below are mostly [inf]: R/D/P/T/V is this matrix's vocabulary,
# not the source's.
# ---------------------------------------------------------------------------

NIST_TRACEABILITY = Evidence(
    source="NIST metrological traceability guidance",
    claim=(
        "Measurement results can be related to references through a "
        "documented, unbroken chain; traceability does not itself establish "
        "fitness for purpose."
    ),
    lineage="[lit]",
)

NIST_MEASUREMENT_INFO = Evidence(
    source="NIST information requirements for dimensional measurement",
    claim=(
        "Dimensional measurement can require information about the design, "
        "quality directives, measurement resources, and measurement rules."
    ),
    lineage="[lit]",
)

W3C_PROV = Evidence(
    source="W3C PROV",
    claim=(
        "Provenance can be represented through entities, activities, and "
        "agents, including generation and use relations."
    ),
    lineage="[lit]",
)

NASA_VV = Evidence(
    source="NASA systems engineering verification and validation guidance",
    claim=(
        "Requirements can be linked to verification methods and documented "
        "with conditions, methods, and verification status."
    ),
    lineage="[lit]",
)

FAA_SMS = Evidence(
    source="FAA safety-management / compliance guidance",
    claim=(
        "Deviations, hazards, and errors can be treated as safety information "
        "for investigation, root-cause analysis, and organizational learning."
    ),
    lineage="[lit]",
)

SOFTWARE_ORACLE = Evidence(
    source="Software-testing literature on the test-oracle problem",
    claim=(
        "Testing requires some mechanism for determining whether observed "
        "behavior is acceptable; specifications, models, contracts, "
        "metamorphic relations, and human judgment are possible oracles."
    ),
    lineage="[lit]",
)

METAMORPHIC_TESTING = Evidence(
    source="Software-testing literature on metamorphic testing",
    claim=(
        "When a direct oracle is unavailable, relations between transformed "
        "inputs and outputs can provide testable constraints."
    ),
    lineage="[lit]",
)

COARSE_GRAINING = Evidence(
    source="Information-geometry / renormalization literature",
    claim=(
        "Coarse-graining can be treated as a transformation between scales "
        "under which some distinctions remain informative while others lose "
        "distinguishability."
    ),
    lineage="[lit]",
)


# Shared re-tag reasons.  Per-cell reasons override these where the cell
# has something specific to say.
EXTERNAL_MAPPING_IS_OURS = (
    "R/D/P/T/V is this matrix's vocabulary, not the source's; the status is "
    "our mapping of the source's claim onto the axis."
)
SOURCE_NAMES_THE_AXIS = (
    "the source's own vocabulary is the axis quantity; no mapping step."
)
NON_CLAIM_IS_OURS = (
    "the absence of a claim is our reading of the source's scope, not a "
    "statement the source makes."
)


# ---------------------------------------------------------------------------
# External instrument descriptions
#
# These are intentionally mappings onto the five axes, not claims that the
# source itself uses this exact R/D/P/T/V vocabulary.  The data now says so:
# every cell where the mapping is ours is tagged [inf].
# ---------------------------------------------------------------------------

EXTERNAL_INSTRUMENTS: tuple[Instrument, ...] = (
    Instrument(
        domain="metrology",
        instrument="metrological traceability chain",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=NIST_TRACEABILITY,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Measurement result and reference relationship are explicitly represented.",
    ),
    Instrument(
        domain="metrology",
        instrument="metrological traceability chain",
        axis=Axis.DISCRIMINABILITY,
        status=Status.COVERED,
        evidence=NIST_TRACEABILITY,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Measurement uncertainty and comparison to reference are explicit.",
    ),
    Instrument(
        domain="metrology",
        instrument="metrological traceability chain",
        axis=Axis.PROVENANCE,
        status=Status.COVERED,
        evidence=NIST_TRACEABILITY,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=(
            "traceability is not the source's word for provenance; reading the "
            "documented chain as provenance recoverability is our mapping."
        ),
        note="The documented chain is itself the provenance structure.",
    ),
    Instrument(
        domain="metrology",
        instrument="measurement system characterization",
        axis=Axis.TRANSFORMATION,
        status=Status.PARTIAL,
        evidence=NIST_MEASUREMENT_INFO,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Measurement resources and rules matter, but this matrix does not "
             "claim a general scope operator from the source.",
    ),
    Instrument(
        domain="metrology",
        instrument="measurement system characterization",
        axis=Axis.VALIDATION,
        status=Status.COVERED,
        evidence=NIST_TRACEABILITY,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=(
            "fitness for purpose is the source's term; reading it as instrument "
            "validation is our mapping."
        ),
        note="Traceability and fitness-for-purpose are explicitly distinguished.",
    ),

    Instrument(
        domain="systems engineering",
        instrument="requirements verification matrix",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=NASA_VV,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Requirement, verification method, conditions, and status are represented.",
    ),
    Instrument(
        domain="systems engineering",
        instrument="requirements verification matrix",
        axis=Axis.DISCRIMINABILITY,
        status=Status.COVERED,
        evidence=NASA_VV,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Verification methods distinguish whether a requirement is satisfied.",
    ),
    Instrument(
        domain="systems engineering",
        instrument="requirements verification matrix",
        axis=Axis.PROVENANCE,
        status=Status.COVERED,
        evidence=NASA_VV,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Requirement-to-verification linkage preserves decision lineage.",
    ),
    Instrument(
        domain="systems engineering",
        instrument="requirements verification matrix",
        axis=Axis.TRANSFORMATION,
        status=Status.PARTIAL,
        evidence=NASA_VV,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Requirement decomposition and verification flow are represented, "
             "but this is not treated as a general coarse-graining model.",
    ),
    Instrument(
        domain="systems engineering",
        instrument="requirements verification matrix",
        axis=Axis.VALIDATION,
        status=Status.COVERED,
        evidence=NASA_VV,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=(
            "the source's validation is system validation; the axis is instrument "
            "validation.  Same word, different object; the mapping is ours."
        ),
        note="Verification and validation are explicitly distinguished.",
    ),

    Instrument(
        domain="aviation safety",
        instrument="safety management / compliance reporting",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=FAA_SMS,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Deviations and safety information become explicit records.",
    ),
    Instrument(
        domain="aviation safety",
        instrument="safety management / compliance reporting",
        axis=Axis.DISCRIMINABILITY,
        status=Status.PARTIAL,
        evidence=FAA_SMS,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Investigation seeks to distinguish causes and contributing factors, "
             "but this matrix does not assert a universal discriminator.",
    ),
    Instrument(
        domain="aviation safety",
        instrument="safety management / compliance reporting",
        axis=Axis.PROVENANCE,
        status=Status.COVERED,
        evidence=FAA_SMS,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Reporting and investigation preserve the path from event to analysis.",
    ),
    Instrument(
        domain="aviation safety",
        instrument="safety management / compliance reporting",
        axis=Axis.TRANSFORMATION,
        status=Status.PARTIAL,
        evidence=FAA_SMS,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Deviation -> investigation -> corrective action is a transformation chain.",
    ),
    Instrument(
        domain="aviation safety",
        instrument="safety management / compliance reporting",
        axis=Axis.VALIDATION,
        status=Status.COVERED,
        evidence=FAA_SMS,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=(
            "organizational learning and feedback are the source's terms; reading "
            "them as instrument validation is our mapping."
        ),
        note="Safety-management processes explicitly emphasize learning and feedback.",
    ),

    Instrument(
        domain="software testing",
        instrument="test oracle",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=SOFTWARE_ORACLE,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Expected behavior can be represented by a specification, model, contract, etc.",
    ),
    Instrument(
        domain="software testing",
        instrument="test oracle",
        axis=Axis.DISCRIMINABILITY,
        status=Status.COVERED,
        evidence=SOFTWARE_ORACLE,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=(
            "the source says 'determine whether behaviour is acceptable'; reading "
            "that as discriminability between candidates is our mapping."
        ),
        note="The oracle separates acceptable from unacceptable observations.",
    ),
    Instrument(
        domain="software testing",
        instrument="test oracle",
        axis=Axis.PROVENANCE,
        status=Status.PARTIAL,
        evidence=SOFTWARE_ORACLE,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="The oracle's origin can be documented, but provenance is not the "
             "primary function of the oracle problem.",
    ),
    Instrument(
        domain="software testing",
        instrument="test oracle",
        axis=Axis.TRANSFORMATION,
        status=Status.PARTIAL,
        evidence=SOFTWARE_ORACLE,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Model/specification transformations may be involved, but this "
             "does not establish a general transformation theory.",
    ),
    Instrument(
        domain="software testing",
        instrument="test oracle",
        axis=Axis.VALIDATION,
        status=Status.COVERED,
        evidence=SOFTWARE_ORACLE,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=(
            "oracle adequacy is the source's problem; reading it as instrument "
            "validation is our mapping."
        ),
        note="The adequacy of the oracle is itself a recognized testing problem.",
    ),

    Instrument(
        domain="software testing",
        instrument="metamorphic testing",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=METAMORPHIC_TESTING,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Relations between source and transformed test cases are represented.",
    ),
    Instrument(
        domain="software testing",
        instrument="metamorphic testing",
        axis=Axis.DISCRIMINABILITY,
        status=Status.COVERED,
        evidence=METAMORPHIC_TESTING,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Violations of declared metamorphic relations discriminate behavior.",
    ),
    Instrument(
        domain="software testing",
        instrument="metamorphic testing",
        axis=Axis.PROVENANCE,
        status=Status.PARTIAL,
        evidence=METAMORPHIC_TESTING,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Test transformations can be recorded, but provenance is not the primary object.",
    ),
    Instrument(
        domain="software testing",
        instrument="metamorphic testing",
        axis=Axis.TRANSFORMATION,
        status=Status.COVERED,
        evidence=METAMORPHIC_TESTING,
        lineage="[lit]",
        prior_lineage="[lit]",
        lineage_reason=SOURCE_NAMES_THE_AXIS,
        note="Transformation is explicitly part of the test construction.",
    ),
    Instrument(
        domain="software testing",
        instrument="metamorphic testing",
        axis=Axis.VALIDATION,
        status=Status.COVERED,
        evidence=METAMORPHIC_TESTING,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Useful specifically where a conventional direct oracle is unavailable.",
    ),

    Instrument(
        domain="information geometry",
        instrument="coarse-graining / distinguishability analysis",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=COARSE_GRAINING,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Representations at different scales are explicitly compared.",
    ),
    Instrument(
        domain="information geometry",
        instrument="coarse-graining / distinguishability analysis",
        axis=Axis.DISCRIMINABILITY,
        status=Status.COVERED,
        evidence=COARSE_GRAINING,
        lineage="[lit]",
        prior_lineage="[lit]",
        lineage_reason=(
            "distinguishability is the source's own quantity; discriminability "
            "is the same quantity under this matrix's name."
        ),
        note="Distinguishability is the quantity being tracked under coarse-graining.",
    ),
    Instrument(
        domain="information geometry",
        instrument="coarse-graining / distinguishability analysis",
        axis=Axis.PROVENANCE,
        status=Status.UNMEASURED,
        evidence=COARSE_GRAINING,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=NON_CLAIM_IS_OURS,
        note="This matrix does not claim that provenance recovery is preserved.",
    ),
    Instrument(
        domain="information geometry",
        instrument="coarse-graining / distinguishability analysis",
        axis=Axis.TRANSFORMATION,
        status=Status.COVERED,
        evidence=COARSE_GRAINING,
        lineage="[lit]",
        prior_lineage="[lit]",
        lineage_reason=SOURCE_NAMES_THE_AXIS,
        note="Scale transformation/coarse-graining is central.",
    ),
    Instrument(
        domain="information geometry",
        instrument="coarse-graining / distinguishability analysis",
        axis=Axis.VALIDATION,
        status=Status.PARTIAL,
        evidence=COARSE_GRAINING,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=EXTERNAL_MAPPING_IS_OURS,
        note="Mathematical consistency is available, but this is not mapped to "
             "instrument validation in the metrological sense.",
    ),

    Instrument(
        domain="provenance modeling",
        instrument="W3C PROV",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=W3C_PROV,
        lineage="[lit]",
        prior_lineage="[lit]",
        lineage_reason=(
            "PROV is a representation model and the claim says 'represented'; "
            "no mapping step."
        ),
        note="Entities, activities, agents, uses, and generations are represented.",
    ),
    Instrument(
        domain="provenance modeling",
        instrument="W3C PROV",
        axis=Axis.DISCRIMINABILITY,
        status=Status.UNMEASURED,
        evidence=W3C_PROV,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=NON_CLAIM_IS_OURS,
        note="PROV represents provenance; it is not itself a discriminator of hypotheses.",
    ),
    Instrument(
        domain="provenance modeling",
        instrument="W3C PROV",
        axis=Axis.PROVENANCE,
        status=Status.COVERED,
        evidence=W3C_PROV,
        lineage="[lit]",
        prior_lineage="[lit]",
        lineage_reason=SOURCE_NAMES_THE_AXIS,
        note="Provenance is the primary object.",
    ),
    Instrument(
        domain="provenance modeling",
        instrument="W3C PROV",
        axis=Axis.TRANSFORMATION,
        status=Status.COVERED,
        evidence=W3C_PROV,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=(
            "activities are the source's term; reading them as transformations "
            "is our mapping."
        ),
        note="Activities mediate generation/use relationships.",
    ),
    Instrument(
        domain="provenance modeling",
        instrument="W3C PROV",
        axis=Axis.VALIDATION,
        status=Status.UNMEASURED,
        evidence=W3C_PROV,
        lineage="[inf]",
        prior_lineage="[lit]",
        lineage_reason=NON_CLAIM_IS_OURS,
        note="Validation of a measurement instrument is outside this model's primary role.",
    ),
)


# ---------------------------------------------------------------------------
# method-layer evidence
#
# One Evidence per module, each claim naming the behaviour actually inspected.
# METHOD_LAYER_EVIDENCE is the shared object the rows used before the per-cell
# re-tag; it is kept readable and is no longer referenced by any row.
# ---------------------------------------------------------------------------

METHOD_LAYER_EVIDENCE = Evidence(
    source="JinnZ2/method-layer repository",
    claim=(
        "The repository contains tools for preserving candidate generators, "
        "preference-free ranking, detecting rank changes, frame probing, and "
        "observer-position analysis."
    ),
    lineage="[obs]",
)

BRANCH_SET_EVIDENCE = Evidence(
    source="JinnZ2/method-layer branch_set.py",
    claim=(
        "BranchSet holds N generator-derived branches in lossless JSON "
        "(schema 1.0); eliminated branches are kept and carry eliminated_by; "
        "each branch carries a cost; test_queue() orders discriminators "
        "cheapest first; triage() reads record_state and suppression_cause only."
    ),
    lineage="[obs]",
)

PREFERENCE_FREE_RANK_EVIDENCE = Evidence(
    source="JinnZ2/method-layer preference_free_rank.py",
    claim=(
        "Each criterion declares a valid_envelope callable and an "
        "out_of_envelope behaviour; the envelope is checked before measurement; "
        "results are return classes (SCORED, UNKNOWN_measurable, BLOCKED, "
        "OUT_OF_ENVELOPE) that are never collapsed into a score; ranking is "
        "Pareto dominance over declared criteria with DominanceCredit per "
        "pair; rollout_depth and envelope_exit_depth are recorded."
    ),
    lineage="[obs]",
)

RANK_DETECTOR_EVIDENCE = Evidence(
    source="JinnZ2/method-layer rank_detector.py",
    claim=(
        "detect() runs null construction per regime (anisotropic noise, "
        "curvature, nonuniform density, combined) with a thick_manifold "
        "positive control before any reading is released; one record is swept "
        "over radius k and dim(k) is read as flat/step/drift/noisy; a confound "
        "that reads activation returns BLOCKED(null_construction); crop and "
        "coarse_grain are explicit operators whose commutator on the dim "
        "reading is reported; the docstring lists what the detector cannot "
        "distinguish and names the null run behind every threshold."
    ),
    lineage="[obs]",
)

FRAME_PROBE_EVIDENCE = Evidence(
    source="JinnZ2/method-layer frame_probe.py",
    claim=(
        "Probe records are hand-authored input carrying author, an "
        "author_kind that must be human, and per-frame calibration; the gate "
        "runs first (emitter_marker_load high -> BLOCKED(contaminated); "
        "between/within ~ 1 -> UNKNOWN_measurable); probes are selected for "
        "maximum separation of the remaining frames; collapse is read as "
        "collapsed / held / partial; identity requires a null set filed open."
    ),
    lineage="[obs]",
)

OBSERVER_POSITION_CONTROL_EVIDENCE = Evidence(
    source="JinnZ2/method-layer observer_position_control.py",
    claim=(
        "SourceRecord carries source_ref, coder, a required-but-unverified "
        "coded_blind flag and a blind BehaviorCode; null a (behaviour spread "
        ">= behavior_spread_max -> BEHAVIOR_DIFFERS) runs first and restricts "
        "every later step to full-pattern matches; nulls b, c, d stratify by "
        "decade, literature type and intensity with Mantel-Haenszel weights; "
        "the residual is joint strata, else the weakest single stratification "
        "(labelled); Outcome is OBSERVER_INDEXED / BEHAVIOR_DIFFERS / "
        "CONFOUNDED / NO_EFFECT / UNKNOWN_measurable; five thresholds are "
        "declared and were set on the synthetic corpus; the prediction is "
        "registered in the module and reported against the result, never "
        "returned as it; the docstring lists four things the control cannot "
        "distinguish; a synthetic corpus generator exists as an instrument "
        "check and says so in every record."
    ),
    lineage="[obs]",
)

PROVENANCE_COLUMN_HELD_OPEN = (
    "the provenance interface between measurement lineage and candidate "
    "lineage is the question this matrix holds open "
    "(method_layer_provenance_gaps); PARTIAL is a placeholder reading by "
    "inference, not an established mapping."
)


# ---------------------------------------------------------------------------
# method-layer mapping
#
# [obs] where the repository behaviour is the axis quantity in the module's
# own terms; [inf] where the mapping is ours; [open] for the P column.
# ---------------------------------------------------------------------------

METHOD_LAYER_INSTRUMENTS: tuple[Instrument, ...] = (
    Instrument(
        domain="method-layer",
        instrument="BranchSet",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=BRANCH_SET_EVIDENCE,
        lineage="[obs]",
        prior_lineage="[obs]",
        lineage_reason=(
            "branch records, status and eliminated_by are inspectable fields "
            "with to_dict/from_dict; representation is read directly."
        ),
        note="Candidate generators and branch state remain represented.",
    ),
    Instrument(
        domain="method-layer",
        instrument="BranchSet",
        axis=Axis.DISCRIMINABILITY,
        status=Status.COVERED,
        evidence=BRANCH_SET_EVIDENCE,
        lineage="[inf]",
        prior_lineage="[obs]",
        lineage_reason=(
            "BranchSet orders discriminators (test_queue) and holds their "
            "outcome; it does not run them.  Reading bookkeeping of "
            "discriminators as 'discriminability covered' is our mapping."
        ),
        note="Branches remain open until a discriminator is run.",
    ),
    Instrument(
        domain="method-layer",
        instrument="BranchSet",
        axis=Axis.PROVENANCE,
        status=Status.PARTIAL,
        evidence=BRANCH_SET_EVIDENCE,
        lineage="[open]",
        prior_lineage="[obs]",
        lineage_reason=PROVENANCE_COLUMN_HELD_OPEN,
        note="Branch records preserve generator/origin/discriminator state, "
             "but the relationship to an external measurement provenance chain "
             "has not yet been formally tested.",
    ),
    Instrument(
        domain="method-layer",
        instrument="BranchSet",
        axis=Axis.TRANSFORMATION,
        status=Status.PARTIAL,
        evidence=BRANCH_SET_EVIDENCE,
        lineage="[inf]",
        prior_lineage="[obs]",
        lineage_reason=(
            "eliminate / reopen transitions are inspectable; calling them a "
            "transformation record is our mapping."
        ),
        note="Branch state changes through measurement and elimination, but "
             "a general transformation graph is not yet formalized.",
    ),
    Instrument(
        domain="method-layer",
        instrument="BranchSet",
        axis=Axis.VALIDATION,
        status=Status.COVERED,
        evidence=BRANCH_SET_EVIDENCE,
        lineage="[inf]",
        prior_lineage="[obs]",
        lineage_reason=(
            "cost, status and eliminated_by are discriminator bookkeeping; the "
            "module validates its records, not its discriminators.  Whether "
            "that constitutes instrument validation is our mapping."
        ),
        note="Discriminators have explicit state, cost, and outcome handling.",
    ),

    Instrument(
        domain="method-layer",
        instrument="preference_free_rank",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=PREFERENCE_FREE_RANK_EVIDENCE,
        lineage="[obs]",
        prior_lineage="[obs]",
        lineage_reason=(
            "criteria, envelopes and return classes are explicit dataclasses "
            "and enums; representation is read directly."
        ),
        note="Criteria, validity envelopes, and unresolved classes are explicit.",
    ),
    Instrument(
        domain="method-layer",
        instrument="preference_free_rank",
        axis=Axis.DISCRIMINABILITY,
        status=Status.COVERED,
        evidence=PREFERENCE_FREE_RANK_EVIDENCE,
        lineage="[obs]",
        prior_lineage="[obs]",
        lineage_reason=(
            "Pareto dominance over declared criteria is the module's own "
            "separation of candidates, and it refuses to separate where it "
            "cannot (unresolved classes stay peers); no mapping step."
        ),
        note="Pareto dominance is determined only from declared criteria.",
    ),
    Instrument(
        domain="method-layer",
        instrument="preference_free_rank",
        axis=Axis.PROVENANCE,
        status=Status.PARTIAL,
        evidence=PREFERENCE_FREE_RANK_EVIDENCE,
        lineage="[open]",
        prior_lineage="[obs]",
        lineage_reason=PROVENANCE_COLUMN_HELD_OPEN,
        note="Credit assignment records which criteria establish dominance; "
             "external measurement lineage is not yet formally linked.",
    ),
    Instrument(
        domain="method-layer",
        instrument="preference_free_rank",
        axis=Axis.TRANSFORMATION,
        status=Status.PARTIAL,
        evidence=PREFERENCE_FREE_RANK_EVIDENCE,
        lineage="[inf]",
        prior_lineage="[obs]",
        lineage_reason=(
            "rollout_depth and envelope_exit_depth are recorded; reading them "
            "as a scope operator is our mapping."
        ),
        note="Rollout depth and envelope boundaries are represented, but "
             "transformation provenance is not yet a first-class graph.",
    ),
    Instrument(
        domain="method-layer",
        instrument="preference_free_rank",
        axis=Axis.VALIDATION,
        status=Status.COVERED,
        evidence=PREFERENCE_FREE_RANK_EVIDENCE,
        lineage="[obs]",
        prior_lineage="[obs]",
        lineage_reason=(
            "valid_envelope is the criterion's declared range of validity and "
            "is checked before measurement; the module names validity itself."
        ),
        note="Measurements outside declared envelopes are refused rather than scored.",
    ),

    Instrument(
        domain="method-layer",
        instrument="rank_detector",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=RANK_DETECTOR_EVIDENCE,
        lineage="[obs]",
        prior_lineage="[obs]",
        lineage_reason=(
            "outcome, blocking and curve states are explicit records with "
            "rule strings; representation is read directly."
        ),
        note="Resolution, topology/rank, density, scale, and outcome states are explicit.",
    ),
    Instrument(
        domain="method-layer",
        instrument="rank_detector",
        axis=Axis.DISCRIMINABILITY,
        status=Status.COVERED,
        evidence=RANK_DETECTOR_EVIDENCE,
        lineage="[obs]",
        prior_lineage="[obs]",
        lineage_reason=(
            "separating resolution artifact from dimensional activation is the "
            "module's stated question and the null suite is that separation in "
            "the module's own terms.  Declared limits are carried, not hidden: "
            "with one normal direction off-manifold noise and activation are "
            "the same geometry; two activations read AMBIGUOUS; rank-2 at "
            "pure-Python sample sizes reads AMBIGUOUS."
        ),
        note="Null suite and discriminators separate activation from confounds where supported.",
    ),
    Instrument(
        domain="method-layer",
        instrument="rank_detector",
        axis=Axis.PROVENANCE,
        status=Status.PARTIAL,
        evidence=RANK_DETECTOR_EVIDENCE,
        lineage="[open]",
        prior_lineage="[obs]",
        lineage_reason=PROVENANCE_COLUMN_HELD_OPEN,
        note="The detector records outcome and blocking state, but its "
             "measurement lineage has not yet been joined formally to BranchSet.",
    ),
    Instrument(
        domain="method-layer",
        instrument="rank_detector",
        axis=Axis.TRANSFORMATION,
        status=Status.COVERED,
        evidence=RANK_DETECTOR_EVIDENCE,
        lineage="[obs]",
        prior_lineage="[obs]",
        lineage_reason=(
            "crop / coarse_grain and their commutator are explicit operators; "
            "scope is an operator in the module's own vocabulary."
        ),
        note="Scope/scale is explicitly treated as an operator affecting the reading.",
    ),
    Instrument(
        domain="method-layer",
        instrument="rank_detector",
        axis=Axis.VALIDATION,
        status=Status.COVERED,
        evidence=RANK_DETECTOR_EVIDENCE,
        lineage="[obs]",
        prior_lineage="[obs]",
        lineage_reason=(
            "null construction and a positive control run inside detect() "
            "before any reading is released, and the threshold table names the "
            "null run that set each threshold; that is instrument validation "
            "in the module's own words."
        ),
        note="Null construction and confound checks are mandatory.",
    ),

    Instrument(
        domain="method-layer",
        instrument="frame_probe",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=FRAME_PROBE_EVIDENCE,
        lineage="[obs]",
        prior_lineage="[obs]",
        lineage_reason=(
            "probe, frame, collapse and calibration records are explicit "
            "dataclasses with to_dict; representation is read directly."
        ),
        note="Probe senses, frames, collapse states, and calibration are represented.",
    ),
    Instrument(
        domain="method-layer",
        instrument="frame_probe",
        axis=Axis.DISCRIMINABILITY,
        status=Status.COVERED,
        evidence=FRAME_PROBE_EVIDENCE,
        lineage="[obs]",
        prior_lineage="[obs]",
        lineage_reason=(
            "selection for maximum separation of the remaining frames is "
            "discriminability in the module's own vocabulary."
        ),
        note="Probes are selected to separate remaining frame hypotheses.",
    ),
    Instrument(
        domain="method-layer",
        instrument="frame_probe",
        axis=Axis.PROVENANCE,
        status=Status.PARTIAL,
        evidence=FRAME_PROBE_EVIDENCE,
        lineage="[open]",
        prior_lineage="[obs]",
        lineage_reason=PROVENANCE_COLUMN_HELD_OPEN,
        note="Human-authored probes preserve authorship metadata, but broader "
             "measurement provenance remains an open interface.",
    ),
    Instrument(
        domain="method-layer",
        instrument="frame_probe",
        axis=Axis.TRANSFORMATION,
        status=Status.PARTIAL,
        evidence=FRAME_PROBE_EVIDENCE,
        lineage="[inf]",
        prior_lineage="[obs]",
        lineage_reason=(
            "narrowing a frame set by observed collapse is inspectable; "
            "reading the narrowing as a transformation record is our mapping."
        ),
        note="Probe responses narrow a hypothesis set; a general transformation "
             "record is not yet formalized.",
    ),
    Instrument(
        domain="method-layer",
        instrument="frame_probe",
        axis=Axis.VALIDATION,
        status=Status.COVERED,
        evidence=FRAME_PROBE_EVIDENCE,
        lineage="[obs]",
        prior_lineage="[obs]",
        lineage_reason=(
            "the gate validates the probe before it is used and refuses a "
            "contaminated one (CONTAMINATED, UNCALIBRATED are named blockers); "
            "validation of the instrument in the module's own terms."
        ),
        note="Contamination and calibration gates can block interpretation.",
    ),

    # observer_position_control: rows added by the repair.  No prior tag.
    Instrument(
        domain="method-layer",
        instrument="observer_position_control",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=OBSERVER_POSITION_CONTROL_EVIDENCE,
        lineage="[obs]",
        lineage_reason=(
            "SourceRecord, BehaviorCode, the label x position contingency, "
            "StratifiedEffect and ObserverPositionResult are explicit records "
            "with to_dict; every stratified effect carries a rule string; the "
            "prediction is registered in the module.  Representation is read "
            "directly."
        ),
        note="Records, contingency, stratified effects, residual, thresholds "
             "and the registered prediction are all explicit.",
    ),
    Instrument(
        domain="method-layer",
        instrument="observer_position_control",
        axis=Axis.DISCRIMINABILITY,
        status=Status.PARTIAL,
        evidence=OBSERVER_POSITION_CONTROL_EVIDENCE,
        lineage="[obs]",
        lineage_reason=(
            "the module separates OBSERVER_INDEXED from BEHAVIOR_DIFFERS, "
            "CONFOUNDED, NO_EFFECT and UNKNOWN_measurable through nulls a-d, "
            "and its docstring names four things it cannot distinguish "
            "(position from competence; coding bias in the input; an observer "
            "effect from a selection effect in corpus assembly; positions 1 "
            "and 2 when literature type is collinear).  PARTIAL is the "
            "module's own statement, not our reading."
        ),
        note="Nulls a-d and MH stratification discriminate the outcome classes; "
             "four confounds are declared indistinguishable by the module itself.",
    ),
    Instrument(
        domain="method-layer",
        instrument="observer_position_control",
        axis=Axis.PROVENANCE,
        status=Status.PARTIAL,
        evidence=OBSERVER_POSITION_CONTROL_EVIDENCE,
        lineage="[open]",
        lineage_reason=PROVENANCE_COLUMN_HELD_OPEN,
        note="Each record carries source_ref, coder and coded_blind; the blind "
             "flag is required, not verified (docstring); the result names "
             "strata used and dropped by label but does not retain which "
             "records entered each stratum.",
    ),
    Instrument(
        domain="method-layer",
        instrument="observer_position_control",
        axis=Axis.TRANSFORMATION,
        status=Status.PARTIAL,
        evidence=OBSERVER_POSITION_CONTROL_EVIDENCE,
        lineage="[inf]",
        lineage_reason=(
            "the restriction chain corpus -> blind -> full-pattern matches -> "
            "strata is inspectable and its counts (n_records, n_blind, "
            "n_matched) are retained; reading that chain as a transformation "
            "/ scope record is our mapping."
        ),
        note="Restriction steps are counted and dropped strata are named; the "
             "excluded records themselves are not listed in the result and "
             "no general transformation record exists.",
    ),
    Instrument(
        domain="method-layer",
        instrument="observer_position_control",
        axis=Axis.VALIDATION,
        status=Status.PARTIAL,
        evidence=OBSERVER_POSITION_CONTROL_EVIDENCE,
        lineage="[obs]",
        lineage_reason=(
            "the synthetic corpus is declared an instrument check and says so "
            "in every record; it is exercised by the test suite and the CLI "
            "but is NOT run inside run() (unlike rank_detector's null "
            "construction), and the docstring says the thresholds were set on "
            "that same synthetic corpus.  PARTIAL is read from the module's "
            "own statements."
        ),
        note="Instrument check exists (planted effect recovered, planted "
             "confound rejected) but is not mandatory per run; thresholds "
             "were set on the check corpus.",
    ),
)


ALL_INSTRUMENTS = EXTERNAL_INSTRUMENTS + METHOD_LAYER_INSTRUMENTS


# ---------------------------------------------------------------------------
# Lineage distribution
# ---------------------------------------------------------------------------

# Distribution before the per-cell re-tag: one shared tag per source.
# Kept so the prior state stays readable next to the current one.
LINEAGE_DISTRIBUTION_BEFORE_RETAG: dict[str, int] = {
    "[obs]": 20,
    "[lit]": 35,
    "[inf]": 0,
    "[open]": 0,
    "[gap]": 0,
}
LINEAGE_DISTRIBUTION_BEFORE_RETAG_NOTE = (
    "55 rows; four method-layer modules x 5 axes tagged [obs] through the "
    "shared METHOD_LAYER_EVIDENCE object; 35 external rows tagged [lit] "
    "through their shared Evidence objects; observer_position_control had "
    "no rows.  Zero [inf] rows: the tag was declared and never used."
)


def lineage_distribution(
    instruments: Iterable[Instrument] = ALL_INSTRUMENTS,
) -> dict[str, int]:
    """Count of rows per lineage tag.  Every tag is reported, zero included."""

    counts = {tag: 0 for tag in LINEAGE_TAGS}
    for item in instruments:
        counts[item.lineage] += 1
    return counts


# ---------------------------------------------------------------------------
# Coverage: every module in the repository has at least one row
# ---------------------------------------------------------------------------

# module file name (without .py) -> instrument name used in the rows
MODULE_INSTRUMENT_NAMES: dict[str, str] = {
    "branch_set": "BranchSet",
    "preference_free_rank": "preference_free_rank",
    "rank_detector": "rank_detector",
    "frame_probe": "frame_probe",
    "observer_position_control": "observer_position_control",
}

METHOD_LAYER_DOMAIN = "method-layer"


class CoverageError(RuntimeError):
    """A module in the repository has no row in the matrix."""


@dataclass(frozen=True)
class CoverageReport:
    modules: tuple[str, ...]
    zero_row_modules: tuple[str, ...]
    unmapped_modules: tuple[str, ...]
    unrowed_cells: tuple[tuple[str, str], ...]
    rule: str

    @property
    def ok(self) -> bool:
        return not self.zero_row_modules and not self.unmapped_modules

    def to_dict(self) -> dict:
        return {
            "modules": list(self.modules),
            "zero_row_modules": list(self.zero_row_modules),
            "unmapped_modules": list(self.unmapped_modules),
            "unrowed_cells": [list(cell) for cell in self.unrowed_cells],
            "ok": self.ok,
            "rule": self.rule,
        }


def repository_modules(root: Optional[Path] = None) -> tuple[str, ...]:
    """Module names on disk next to this file, excluding this file and tests."""

    root = Path(__file__).resolve().parent if root is None else Path(root)
    own = Path(__file__).stem
    names = []
    for path in sorted(root.glob("*.py")):
        if path.stem == own or path.stem.startswith("test"):
            continue
        names.append(path.stem)
    return tuple(names)


def coverage_check(
    instruments: Iterable[Instrument] = ALL_INSTRUMENTS,
    root: Optional[Path] = None,
) -> CoverageReport:
    """Report which repository modules have zero rows, and which cells have none.

    zero rows for a module   -> CoverageReport.ok is False (assert_coverage raises)
    no row for one cell      -> listed as unrowed; that is not-yet-looked-at,
                                distinct from UNMEASURED, and does not fail
    """

    rows: dict[str, set[str]] = {}
    for item in instruments:
        if item.domain == METHOD_LAYER_DOMAIN:
            rows.setdefault(item.instrument, set()).add(item.axis.value)

    modules = repository_modules(root)
    zero = []
    unmapped = []
    for module in modules:
        name = MODULE_INSTRUMENT_NAMES.get(module)
        if name is None:
            unmapped.append(module)
        elif not rows.get(name):
            zero.append(module)

    unrowed = []
    for key in sorted({item.key for item in instruments}):
        present = {item.axis.value for item in instruments if item.key == key}
        for axis in AXES:
            if axis.value not in present:
                unrowed.append((key, axis.value))

    rule = (
        f"coverage: {len(modules)} modules on disk; "
        f"{len(zero)} with zero rows; {len(unmapped)} not mapped to an instrument name; "
        f"{len(unrowed)} unrowed cells (not-yet-looked-at, not unmeasured)"
    )
    return CoverageReport(
        modules=modules,
        zero_row_modules=tuple(zero),
        unmapped_modules=tuple(unmapped),
        unrowed_cells=tuple(unrowed),
        rule=rule,
    )


def assert_coverage(
    instruments: Iterable[Instrument] = ALL_INSTRUMENTS,
    root: Optional[Path] = None,
) -> CoverageReport:
    """Raise CoverageError, loudly, if any repository module has zero rows."""

    report = coverage_check(instruments, root)
    if not report.ok:
        lines = [report.rule]
        for module in report.zero_row_modules:
            lines.append(f"  zero rows: {module} (instrument {MODULE_INSTRUMENT_NAMES[module]!r})")
        for module in report.unmapped_modules:
            lines.append(f"  not in MODULE_INSTRUMENT_NAMES: {module}")
        lines.append(
            "  add rows for every axis (UNMEASURED with a [gap] note where the "
            "status cannot be established); absence is not a state"
        )
        raise CoverageError("\n".join(lines))
    return report


# ---------------------------------------------------------------------------
# Matrix operations
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Cell:
    """Every record that landed in one domain::instrument x axis cell.

    ``status`` is the reported reading (strongest unresolved state, by
    STATUS_PRIORITY).  The records are kept; nothing is dropped.
    """

    key: str
    axis: Axis
    records: tuple[Instrument, ...]

    def __post_init__(self) -> None:
        if not self.records:
            raise ValueError(f"{self.key}[{self.axis.value}]: a Cell needs at least one record")

    @property
    def statuses(self) -> tuple[Status, ...]:
        return tuple(sorted({r.status for r in self.records}, key=lambda s: STATUS_PRIORITY[s]))

    @property
    def status(self) -> Status:
        return max((r.status for r in self.records), key=lambda s: STATUS_PRIORITY[s])

    @property
    def collided(self) -> bool:
        return len(self.statuses) > 1

    @property
    def lineages(self) -> tuple[str, ...]:
        return tuple(r.lineage for r in self.records)

    @property
    def rule(self) -> str:
        if len(self.records) == 1:
            return "single record"
        if self.collided:
            return (
                f"collision: {len(self.records)} records, statuses "
                f"{'/'.join(s.value for s in self.statuses)}; reported = strongest "
                "unresolved (STATUS_PRIORITY); all records retained"
            )
        return f"{len(self.records)} records agree"

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "axis": self.axis.value,
            "status": self.status.value,
            "collided": self.collided,
            "rule": self.rule,
            "records": [r.to_dict() for r in self.records],
        }


@dataclass(frozen=True)
class Collision:
    """A cell whose records disagree on status.  A result, not an error."""

    key: str
    axis: Axis
    reported: Status
    readings: tuple[tuple[Status, str, str], ...]   # (status, source, lineage)
    rule: str

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "axis": self.axis.value,
            "reported": self.reported.value,
            "readings": [
                {"status": s.value, "source": src, "lineage": lin}
                for s, src, lin in self.readings
            ],
            "rule": self.rule,
        }


def matrix(
    instruments: Iterable[Instrument] = ALL_INSTRUMENTS,
) -> dict[str, dict[str, Cell]]:
    """
    Return:

        domain::instrument -> {axis: Cell}

    Every record that occupies a cell is retained in that Cell.  The Cell's
    reported ``status`` is the strongest unresolved state; when the records
    disagree the Cell is ``collided`` and the disagreement is retrievable.
    Nothing is averaged and no record is discarded.
    """

    grouped: dict[str, dict[str, list[Instrument]]] = {}
    for item in instruments:
        grouped.setdefault(item.key, {}).setdefault(item.axis.value, []).append(item)

    result: dict[str, dict[str, Cell]] = {}
    for key, axes in grouped.items():
        result[key] = {
            axis: Cell(key=key, axis=Axis(axis), records=tuple(records))
            for axis, records in axes.items()
        }
    return result


def collisions(
    instruments: Iterable[Instrument] = ALL_INSTRUMENTS,
) -> list[Collision]:
    """Cells holding records of differing status, with source and lineage of each."""

    cells = matrix(instruments)
    found = []
    for key in sorted(cells):
        for axis in AXES:
            cell = cells[key].get(axis.value)
            if cell is None or not cell.collided:
                continue
            found.append(
                Collision(
                    key=key,
                    axis=axis,
                    reported=cell.status,
                    readings=tuple(
                        (r.status, r.evidence.source, r.lineage) for r in cell.records
                    ),
                    rule=cell.rule,
                )
            )
    return found


def candidate_gaps(
    instruments: Iterable[Instrument] = ALL_INSTRUMENTS,
) -> list[Instrument]:
    """
    Return cells that currently warrant further instrumentation.

    This does NOT classify them as defects.

    A gap may represent:
        - an interface not yet specified,
        - a measurement not yet run,
        - a provenance relation not yet modeled,
        - or a genuinely missing instrument.
    """
    return [
        item
        for item in instruments
        if item.status in {
            Status.PARTIAL,
            Status.UNMEASURED,
            Status.CONTRADICTORY,
        }
    ]


def method_layer_provenance_gaps() -> list[Instrument]:
    """
    Narrow view of the suspected interface discontinuity between
    measurement provenance and candidate provenance.

    The output is intentionally a candidate-gap list, not a defect report.
    """
    return [
        item
        for item in METHOD_LAYER_INSTRUMENTS
        if item.axis == Axis.PROVENANCE
        and item.status == Status.PARTIAL
    ]


# ---------------------------------------------------------------------------
# Contradiction scan
#
# CONTRADICTORY is a record status meaning "the evidence does not agree".
# Whether it is empty because nothing contradicts or because nobody looked
# is stated here, as data.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContradictionScan:
    scope: str
    method: str
    n_cells: int
    n_records: int
    contradictory_records: tuple[tuple[str, str], ...]   # (key, axis) carrying CONTRADICTORY
    evidence_disagreements: tuple[tuple[str, str], ...]  # (key, axis) with >1 source and >1 status
    lineage: str
    rule: str

    def to_dict(self) -> dict:
        return {
            "scope": self.scope,
            "method": self.method,
            "n_cells": self.n_cells,
            "n_records": self.n_records,
            "contradictory_records": [list(c) for c in self.contradictory_records],
            "evidence_disagreements": [list(c) for c in self.evidence_disagreements],
            "lineage": self.lineage,
            "rule": self.rule,
        }


def contradiction_scan(
    instruments: Iterable[Instrument] = ALL_INSTRUMENTS,
) -> ContradictionScan:
    """Scan the evidence set for disagreement.  Zero is a real finding.

    Two things are scanned:
        1. records already carrying CONTRADICTORY
        2. cells where records from DIFFERENT sources report DIFFERENT
           statuses (evidence disagreeing with evidence)

    What is NOT scanned, and cannot be from this file: disagreement inside a
    single claim, or between a claim and the source text it summarises.  Each
    source contributes one claim string and the source text is not here.
    That limit is MATRIX_GAPS[contradiction scan].
    """

    items = list(instruments)
    cells = matrix(items)
    carrying = tuple(
        (item.key, item.axis.value) for item in items if item.status is Status.CONTRADICTORY
    )
    disagreements = []
    n_cells = 0
    for key in sorted(cells):
        for axis in AXES:
            cell = cells[key].get(axis.value)
            if cell is None:
                continue
            n_cells += 1
            sources = {r.evidence.source for r in cell.records}
            if len(sources) > 1 and cell.collided:
                disagreements.append((key, axis.value))
    rule = (
        f"scan ran over {n_cells} cells / {len(items)} records: "
        f"{len(carrying)} records carry CONTRADICTORY; "
        f"{len(disagreements)} cells hold disagreeing evidence from more than one source"
        + ("; zero is the finding, not an absence of looking" if not carrying and not disagreements else "")
    )
    return ContradictionScan(
        scope="every cell of the instrument set passed in; status and source per record",
        method=(
            "1. records with status CONTRADICTORY; "
            "2. cells with > 1 source and > 1 status.  "
            "Within-claim contradiction is out of reach (one claim per source, "
            "no source text here): see MATRIX_GAPS."
        ),
        n_cells=n_cells,
        n_records=len(items),
        contradictory_records=carrying,
        evidence_disagreements=tuple(disagreements),
        lineage="[obs]",
        rule=rule,
    )


# ---------------------------------------------------------------------------
# Gaps that are not cells
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MatrixGap:
    subject: str
    lineage: str
    note: str

    def __post_init__(self) -> None:
        _check_lineage(self.lineage, "MatrixGap.lineage")

    def to_dict(self) -> dict:
        return {"subject": self.subject, "lineage": self.lineage, "note": self.note}


MATRIX_GAPS: tuple[MatrixGap, ...] = (
    MatrixGap(
        subject="contradiction scan",
        lineage="[gap]",
        note=(
            "CONTRADICTORY cannot be populated from the current evidence set "
            "beyond what contradiction_scan() reaches: every source contributes "
            "exactly one claim string and no source text is in this file, so "
            "a claim cannot be checked against itself or against its source.  "
            "Populating the status needs either a second independent reading "
            "per cell or the source text.  The scan's zero result is real "
            "within its scope and says nothing outside it."
        ),
    ),
)


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def print_matrix(
    instruments: Iterable[Instrument] = ALL_INSTRUMENTS,
) -> None:
    """
    Human-readable matrix.  A collided cell is marked with ``*``; a cell
    with no row prints ``norow`` (not-yet-looked-at, distinct from unmeasured).
    """
    m = matrix(instruments)

    print("Cross-domain instrument matrix")
    print()
    print("Legend:")
    print("  covered       = explicitly represented/measured")
    print("  partial       = some relevant structure, incomplete interface")
    print("  unmeasured    = not established by this instrument")
    print("  contradictory = evidence does not agree")
    print("  norow         = no record in this cell; not yet looked at")
    print("  *             = collision: records in this cell disagree; see collisions()")
    print()

    for key in sorted(m):
        cells = m[key]
        parts = []
        for axis in AXES:
            cell = cells.get(axis.value)
            if cell is None:
                parts.append(f"{axis.value}=norow")
            else:
                parts.append(f"{axis.value}={cell.status.value}{'*' if cell.collided else ''}")
        print(f"{key}: {' '.join(parts)}")


def print_collisions(
    instruments: Iterable[Instrument] = ALL_INSTRUMENTS,
) -> None:
    found = collisions(instruments)
    print(f"Collisions: {len(found)}")
    for c in found:
        print(f"- {c.key} [{c.axis.value}] reported={c.reported.value}")
        for status, source, lineage in c.readings:
            print(f"    {status.value:<13} {lineage:<6} {source}")
        print(f"  rule: {c.rule}")


def print_candidate_gaps(
    instruments: Iterable[Instrument] = ALL_INSTRUMENTS,
) -> None:
    """
    Print candidate measurement/interface gaps with provenance preserved.
    """
    print("Candidate gaps")
    print()

    for item in candidate_gaps(instruments):
        print(
            f"- {item.domain}::{item.instrument} "
            f"[{item.axis.value}] "
            f"{item.status.value}"
        )
        print(f"  source: {item.evidence.source}")
        print(f"  lineage: {item.lineage}"
              + (f" (was {item.prior_lineage})" if item.prior_lineage and item.prior_lineage != item.lineage else ""))
        print(f"  note: {item.note}")

    print()
    print("Gaps that are not cells")
    for gap in MATRIX_GAPS:
        print(f"- {gap.subject} {gap.lineage}")
        print(f"  note: {gap.note}")


def print_lineage_distribution(
    instruments: Iterable[Instrument] = ALL_INSTRUMENTS,
) -> None:
    now = lineage_distribution(instruments)
    print("Lineage distribution (cells)")
    print(f"  {'tag':<7} {'before':>6} {'after':>6}")
    for tag in LINEAGE_TAGS:
        print(f"  {tag:<7} {LINEAGE_DISTRIBUTION_BEFORE_RETAG[tag]:>6} {now[tag]:>6}")
    print(f"  {'total':<7} {sum(LINEAGE_DISTRIBUTION_BEFORE_RETAG.values()):>6} {sum(now.values()):>6}")
    print(f"  non-cell gaps: {len(MATRIX_GAPS)}")
    print(f"  before: {LINEAGE_DISTRIBUTION_BEFORE_RETAG_NOTE}")
    if now["[inf]"] == 0:
        print("  WARNING: zero [inf] rows; the mapping cannot all be observation")


def print_contradiction_scan(
    instruments: Iterable[Instrument] = ALL_INSTRUMENTS,
) -> None:
    scan = contradiction_scan(instruments)
    print("Contradiction scan")
    print(f"  scope:  {scan.scope}")
    print(f"  method: {scan.method}")
    print(f"  result: {scan.rule}")
    for key, axis in scan.contradictory_records:
        print(f"    CONTRADICTORY record: {key} [{axis}]")
    for key, axis in scan.evidence_disagreements:
        print(f"    evidence disagrees: {key} [{axis}]")


def print_coverage(report: CoverageReport) -> None:
    print("Coverage")
    print(f"  {report.rule}")
    for module in report.modules:
        print(f"  {module:<28} -> {MODULE_INSTRUMENT_NAMES.get(module, '(unmapped)')}")
    for key, axis in report.unrowed_cells:
        print(f"  norow: {key} [{axis}]")


# Runs at import.  A module with zero rows cannot be silent again.
COVERAGE = assert_coverage()


if __name__ == "__main__":
    print_coverage(COVERAGE)
    print()
    print_matrix()
    print()
    print_collisions()
    print()
    print_contradiction_scan()
    print()
    print_lineage_distribution()
    print()
    print_candidate_gaps()

    print()
    print("Narrow suspected provenance interface:")
    for item in method_layer_provenance_gaps():
        print(
            f"- {item.instrument}::{item.axis.value} "
            f"{item.status.value} {item.lineage}"
        )
