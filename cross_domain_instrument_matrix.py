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
    - a gap is an observation about the current instrument/interface
    - evidence status is retained explicitly
    - no status is promoted merely because several domains appear similar

Lineage
-------
[obs]  Directly established from inspected source/repository material.
[lit]  Literature/source-supported.
[inf]  Model-generated inference or proposed mapping.
[open]  Deliberately unresolved.
[gap]  Missing measurement or inaccessible evidence.

The matrix is intended to be broken.

CC0
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


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


@dataclass(frozen=True)
class Evidence:
    source: str
    claim: str
    lineage: str


@dataclass(frozen=True)
class Instrument:
    domain: str
    instrument: str
    axis: Axis
    status: Status
    evidence: Evidence
    note: str = ""


# ---------------------------------------------------------------------------
# External evidence
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


# ---------------------------------------------------------------------------
# External instrument descriptions
#
# These are intentionally mappings onto the five axes, not claims that the
# source itself uses this exact R/D/P/T/V vocabulary.
# ---------------------------------------------------------------------------

EXTERNAL_INSTRUMENTS: tuple[Instrument, ...] = (
    Instrument(
        domain="metrology",
        instrument="metrological traceability chain",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=NIST_TRACEABILITY,
        note="Measurement result and reference relationship are explicitly represented.",
    ),
    Instrument(
        domain="metrology",
        instrument="metrological traceability chain",
        axis=Axis.DISCRIMINABILITY,
        status=Status.COVERED,
        evidence=NIST_TRACEABILITY,
        note="Measurement uncertainty and comparison to reference are explicit.",
    ),
    Instrument(
        domain="metrology",
        instrument="metrological traceability chain",
        axis=Axis.PROVENANCE,
        status=Status.COVERED,
        evidence=NIST_TRACEABILITY,
        note="The documented chain is itself the provenance structure.",
    ),
    Instrument(
        domain="metrology",
        instrument="measurement system characterization",
        axis=Axis.TRANSFORMATION,
        status=Status.PARTIAL,
        evidence=NIST_MEASUREMENT_INFO,
        note="Measurement resources and rules matter, but this matrix does not "
             "claim a general scope operator from the source.",
    ),
    Instrument(
        domain="metrology",
        instrument="measurement system characterization",
        axis=Axis.VALIDATION,
        status=Status.COVERED,
        evidence=NIST_TRACEABILITY,
        note="Traceability and fitness-for-purpose are explicitly distinguished.",
    ),

    Instrument(
        domain="systems engineering",
        instrument="requirements verification matrix",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=NASA_VV,
        note="Requirement, verification method, conditions, and status are represented.",
    ),
    Instrument(
        domain="systems engineering",
        instrument="requirements verification matrix",
        axis=Axis.DISCRIMINABILITY,
        status=Status.COVERED,
        evidence=NASA_VV,
        note="Verification methods distinguish whether a requirement is satisfied.",
    ),
    Instrument(
        domain="systems engineering",
        instrument="requirements verification matrix",
        axis=Axis.PROVENANCE,
        status=Status.COVERED,
        evidence=NASA_VV,
        note="Requirement-to-verification linkage preserves decision lineage.",
    ),
    Instrument(
        domain="systems engineering",
        instrument="requirements verification matrix",
        axis=Axis.TRANSFORMATION,
        status=Status.PARTIAL,
        evidence=NASA_VV,
        note="Requirement decomposition and verification flow are represented, "
             "but this is not treated as a general coarse-graining model.",
    ),
    Instrument(
        domain="systems engineering",
        instrument="requirements verification matrix",
        axis=Axis.VALIDATION,
        status=Status.COVERED,
        evidence=NASA_VV,
        note="Verification and validation are explicitly distinguished.",
    ),

    Instrument(
        domain="aviation safety",
        instrument="safety management / compliance reporting",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=FAA_SMS,
        note="Deviations and safety information become explicit records.",
    ),
    Instrument(
        domain="aviation safety",
        instrument="safety management / compliance reporting",
        axis=Axis.DISCRIMINABILITY,
        status=Status.PARTIAL,
        evidence=FAA_SMS,
        note="Investigation seeks to distinguish causes and contributing factors, "
             "but this matrix does not assert a universal discriminator.",
    ),
    Instrument(
        domain="aviation safety",
        instrument="safety management / compliance reporting",
        axis=Axis.PROVENANCE,
        status=Status.COVERED,
        evidence=FAA_SMS,
        note="Reporting and investigation preserve the path from event to analysis.",
    ),
    Instrument(
        domain="aviation safety",
        instrument="safety management / compliance reporting",
        axis=Axis.TRANSFORMATION,
        status=Status.PARTIAL,
        evidence=FAA_SMS,
        note="Deviation -> investigation -> corrective action is a transformation chain.",
    ),
    Instrument(
        domain="aviation safety",
        instrument="safety management / compliance reporting",
        axis=Axis.VALIDATION,
        status=Status.COVERED,
        evidence=FAA_SMS,
        note="Safety-management processes explicitly emphasize learning and feedback.",
    ),

    Instrument(
        domain="software testing",
        instrument="test oracle",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=SOFTWARE_ORACLE,
        note="Expected behavior can be represented by a specification, model, contract, etc.",
    ),
    Instrument(
        domain="software testing",
        instrument="test oracle",
        axis=Axis.DISCRIMINABILITY,
        status=Status.COVERED,
        evidence=SOFTWARE_ORACLE,
        note="The oracle separates acceptable from unacceptable observations.",
    ),
    Instrument(
        domain="software testing",
        instrument="test oracle",
        axis=Axis.PROVENANCE,
        status=Status.PARTIAL,
        evidence=SOFTWARE_ORACLE,
        note="The oracle's origin can be documented, but provenance is not the "
             "primary function of the oracle problem.",
    ),
    Instrument(
        domain="software testing",
        instrument="test oracle",
        axis=Axis.TRANSFORMATION,
        status=Status.PARTIAL,
        evidence=SOFTWARE_ORACLE,
        note="Model/specification transformations may be involved, but this "
             "does not establish a general transformation theory.",
    ),
    Instrument(
        domain="software testing",
        instrument="test oracle",
        axis=Axis.VALIDATION,
        status=Status.COVERED,
        evidence=SOFTWARE_ORACLE,
        note="The adequacy of the oracle is itself a recognized testing problem.",
    ),

    Instrument(
        domain="software testing",
        instrument="metamorphic testing",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=METAMORPHIC_TESTING,
        note="Relations between source and transformed test cases are represented.",
    ),
    Instrument(
        domain="software testing",
        instrument="metamorphic testing",
        axis=Axis.DISCRIMINABILITY,
        status=Status.COVERED,
        evidence=METAMORPHIC_TESTING,
        note="Violations of declared metamorphic relations discriminate behavior.",
    ),
    Instrument(
        domain="software testing",
        instrument="metamorphic testing",
        axis=Axis.PROVENANCE,
        status=Status.PARTIAL,
        evidence=METAMORPHIC_TESTING,
        note="Test transformations can be recorded, but provenance is not the primary object.",
    ),
    Instrument(
        domain="software testing",
        instrument="metamorphic testing",
        axis=Axis.TRANSFORMATION,
        status=Status.COVERED,
        evidence=METAMORPHIC_TESTING,
        note="Transformation is explicitly part of the test construction.",
    ),
    Instrument(
        domain="software testing",
        instrument="metamorphic testing",
        axis=Axis.VALIDATION,
        status=Status.COVERED,
        evidence=METAMORPHIC_TESTING,
        note="Useful specifically where a conventional direct oracle is unavailable.",
    ),

    Instrument(
        domain="information geometry",
        instrument="coarse-graining / distinguishability analysis",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=COARSE_GRAINING,
        note="Representations at different scales are explicitly compared.",
    ),
    Instrument(
        domain="information geometry",
        instrument="coarse-graining / distinguishability analysis",
        axis=Axis.DISCRIMINABILITY,
        status=Status.COVERED,
        evidence=COARSE_GRAINING,
        note="Distinguishability is the quantity being tracked under coarse-graining.",
    ),
    Instrument(
        domain="information geometry",
        instrument="coarse-graining / distinguishability analysis",
        axis=Axis.PROVENANCE,
        status=Status.UNMEASURED,
        evidence=COARSE_GRAINING,
        note="This matrix does not claim that provenance recovery is preserved.",
    ),
    Instrument(
        domain="information geometry",
        instrument="coarse-graining / distinguishability analysis",
        axis=Axis.TRANSFORMATION,
        status=Status.COVERED,
        evidence=COARSE_GRAINING,
        note="Scale transformation/coarse-graining is central.",
    ),
    Instrument(
        domain="information geometry",
        instrument="coarse-graining / distinguishability analysis",
        axis=Axis.VALIDATION,
        status=Status.PARTIAL,
        evidence=COARSE_GRAINING,
        note="Mathematical consistency is available, but this is not mapped to "
             "instrument validation in the metrological sense.",
    ),

    Instrument(
        domain="provenance modeling",
        instrument="W3C PROV",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=W3C_PROV,
        note="Entities, activities, agents, uses, and generations are represented.",
    ),
    Instrument(
        domain="provenance modeling",
        instrument="W3C PROV",
        axis=Axis.DISCRIMINABILITY,
        status=Status.UNMEASURED,
        evidence=W3C_PROV,
        note="PROV represents provenance; it is not itself a discriminator of hypotheses.",
    ),
    Instrument(
        domain="provenance modeling",
        instrument="W3C PROV",
        axis=Axis.PROVENANCE,
        status=Status.COVERED,
        evidence=W3C_PROV,
        note="Provenance is the primary object.",
    ),
    Instrument(
        domain="provenance modeling",
        instrument="W3C PROV",
        axis=Axis.TRANSFORMATION,
        status=Status.COVERED,
        evidence=W3C_PROV,
        note="Activities mediate generation/use relationships.",
    ),
    Instrument(
        domain="provenance modeling",
        instrument="W3C PROV",
        axis=Axis.VALIDATION,
        status=Status.UNMEASURED,
        evidence=W3C_PROV,
        note="Validation of a measurement instrument is outside this model's primary role.",
    ),
)


# ---------------------------------------------------------------------------
# method-layer mapping
#
# These rows are deliberately labeled [obs] where the repository behavior
# establishes the relationship and [inf] where the mapping is ours.
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

METHOD_LAYER_INSTRUMENTS: tuple[Instrument, ...] = (
    Instrument(
        domain="method-layer",
        instrument="BranchSet",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Candidate generators and branch state remain represented.",
    ),
    Instrument(
        domain="method-layer",
        instrument="BranchSet",
        axis=Axis.DISCRIMINABILITY,
        status=Status.COVERED,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Branches remain open until a discriminator is run.",
    ),
    Instrument(
        domain="method-layer",
        instrument="BranchSet",
        axis=Axis.PROVENANCE,
        status=Status.PARTIAL,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Branch records preserve generator/origin/discriminator state, "
             "but the relationship to an external measurement provenance chain "
             "has not yet been formally tested.",
    ),
    Instrument(
        domain="method-layer",
        instrument="BranchSet",
        axis=Axis.TRANSFORMATION,
        status=Status.PARTIAL,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Branch state changes through measurement and elimination, but "
             "a general transformation graph is not yet formalized.",
    ),
    Instrument(
        domain="method-layer",
        instrument="BranchSet",
        axis=Axis.VALIDATION,
        status=Status.COVERED,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Discriminators have explicit state, cost, and outcome handling.",
    ),

    Instrument(
        domain="method-layer",
        instrument="preference_free_rank",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Criteria, validity envelopes, and unresolved classes are explicit.",
    ),
    Instrument(
        domain="method-layer",
        instrument="preference_free_rank",
        axis=Axis.DISCRIMINABILITY,
        status=Status.COVERED,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Pareto dominance is determined only from declared criteria.",
    ),
    Instrument(
        domain="method-layer",
        instrument="preference_free_rank",
        axis=Axis.PROVENANCE,
        status=Status.PARTIAL,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Credit assignment records which criteria establish dominance; "
             "external measurement lineage is not yet formally linked.",
    ),
    Instrument(
        domain="method-layer",
        instrument="preference_free_rank",
        axis=Axis.TRANSFORMATION,
        status=Status.PARTIAL,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Rollout depth and envelope boundaries are represented, but "
             "transformation provenance is not yet a first-class graph.",
    ),
    Instrument(
        domain="method-layer",
        instrument="preference_free_rank",
        axis=Axis.VALIDATION,
        status=Status.COVERED,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Measurements outside declared envelopes are refused rather than scored.",
    ),

    Instrument(
        domain="method-layer",
        instrument="rank_detector",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Resolution, topology/rank, density, scale, and outcome states are explicit.",
    ),
    Instrument(
        domain="method-layer",
        instrument="rank_detector",
        axis=Axis.DISCRIMINABILITY,
        status=Status.COVERED,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Null suite and discriminators separate activation from confounds where supported.",
    ),
    Instrument(
        domain="method-layer",
        instrument="rank_detector",
        axis=Axis.PROVENANCE,
        status=Status.PARTIAL,
        evidence=METHOD_LAYER_EVIDENCE,
        note="The detector records outcome and blocking state, but its "
             "measurement lineage has not yet been joined formally to BranchSet.",
    ),
    Instrument(
        domain="method-layer",
        instrument="rank_detector",
        axis=Axis.TRANSFORMATION,
        status=Status.COVERED,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Scope/scale is explicitly treated as an operator affecting the reading.",
    ),
    Instrument(
        domain="method-layer",
        instrument="rank_detector",
        axis=Axis.VALIDATION,
        status=Status.COVERED,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Null construction and confound checks are mandatory.",
    ),

    Instrument(
        domain="method-layer",
        instrument="frame_probe",
        axis=Axis.REPRESENTATION,
        status=Status.COVERED,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Probe senses, frames, collapse states, and calibration are represented.",
    ),
    Instrument(
        domain="method-layer",
        instrument="frame_probe",
        axis=Axis.DISCRIMINABILITY,
        status=Status.COVERED,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Probes are selected to separate remaining frame hypotheses.",
    ),
    Instrument(
        domain="method-layer",
        instrument="frame_probe",
        axis=Axis.PROVENANCE,
        status=Status.PARTIAL,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Human-authored probes preserve authorship metadata, but broader "
             "measurement provenance remains an open interface.",
    ),
    Instrument(
        domain="method-layer",
        instrument="frame_probe",
        axis=Axis.TRANSFORMATION,
        status=Status.PARTIAL,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Probe responses narrow a hypothesis set; a general transformation "
             "record is not yet formalized.",
    ),
    Instrument(
        domain="method-layer",
        instrument="frame_probe",
        axis=Axis.VALIDATION,
        status=Status.COVERED,
        evidence=METHOD_LAYER_EVIDENCE,
        note="Contamination and calibration gates can block interpretation.",
    ),
)


ALL_INSTRUMENTS = EXTERNAL_INSTRUMENTS + METHOD_LAYER_INSTRUMENTS


# ---------------------------------------------------------------------------
# Matrix operations
# ---------------------------------------------------------------------------

def matrix(
    instruments: Iterable[Instrument] = ALL_INSTRUMENTS,
) -> dict[str, dict[str, Status]]:
    """
    Return:

        domain::instrument -> {axis: status}

    If several records occupy the same cell, the strongest unresolved state
    is retained rather than silently averaging them.
    """
    result: dict[str, dict[str, Status]] = {}

    priority = {
        Status.COVERED: 0,
        Status.PARTIAL: 1,
        Status.UNMEASURED: 2,
        Status.CONTRADICTORY: 3,
    }

    for item in instruments:
        key = f"{item.domain}::{item.instrument}"
        axis = item.axis.value

        if key not in result:
            result[key] = {}

        existing = result[key].get(axis)

        if existing is None or priority[item.status] > priority[existing]:
            result[key][axis] = item.status

    return result


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


def print_matrix(
    instruments: Iterable[Instrument] = ALL_INSTRUMENTS,
) -> None:
    """
    Human-readable matrix.
    """
    m = matrix(instruments)

    print("Cross-domain instrument matrix")
    print()
    print("Legend:")
    print("  covered       = explicitly represented/measured")
    print("  partial       = some relevant structure, incomplete interface")
    print("  unmeasured    = not established by this instrument")
    print("  contradictory = evidence does not agree")
    print()

    for key in sorted(m):
        cells = m[key]
        values = " ".join(
            f"{axis}={cells.get(axis, Status.UNMEASURED).value}"
            for axis in (
                Axis.REPRESENTATION.value,
                Axis.DISCRIMINABILITY.value,
                Axis.PROVENANCE.value,
                Axis.TRANSFORMATION.value,
                Axis.VALIDATION.value,
            )
        )
        print(f"{key}: {values}")


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
        print(f"  lineage: {item.evidence.lineage}")
        print(f"  note: {item.note}")


if __name__ == "__main__":
    print_matrix()
    print()
    print_candidate_gaps()

    print()
    print("Narrow suspected provenance interface:")
    for item in method_layer_provenance_gaps():
        print(
            f"- {item.instrument}::{item.axis.value} "
            f"{item.status.value}"
        )
