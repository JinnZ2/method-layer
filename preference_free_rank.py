"""Envelope-aware, preference-free ranking by Pareto dominance.

Criterion measurements and physics envelopes are supplied by callers.  The
module never learns a terminal criterion, invents weights, or converts an
unknown state into a numeric score.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from branch_set import BranchSet


class CriterionName(str, Enum):
    BITS_RETURNED_PER_ENERGY = "bits_returned_per_energy"
    REVERSIBILITY = "reversibility"
    COST_ASYMMETRY = "cost_asymmetry"
    DEPENDENCY_ADDED = "dependency_added"
    CYCLE_SURVIVAL = "cycle_survival"


class Direction(str, Enum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


class ReturnClass(str, Enum):
    SCORED = "SCORED"
    UNKNOWN_MEASURABLE = "UNKNOWN_measurable"
    UNKNOWN_BUILDABLE = "UNKNOWN_buildable"
    UNKNOWN_SIMULABLE = "UNKNOWN_simulable"
    BLOCKED = "BLOCKED"
    OUT_OF_ENVELOPE = "OUT_OF_ENVELOPE"
    VARIABLE_UNIDENT = "VARIABLE_UNIDENT"


class EnvelopeStatus(str, Enum):
    IN_ENVELOPE = "in_envelope"
    OUT_OF_ENVELOPE = "out_of_envelope"


@dataclass(frozen=True)
class CriterionResult:
    """A typed criterion result; non-score classes can never carry a score."""

    return_class: ReturnClass
    value: Optional[float] = None
    blocker: Optional[str] = None
    note: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.return_class, ReturnClass):
            object.__setattr__(self, "return_class", ReturnClass(self.return_class))
        if self.return_class is ReturnClass.SCORED:
            if self.value is None:
                raise ValueError("SCORED requires a numeric value")
            try:
                numeric = float(self.value)
            except (TypeError, ValueError) as exc:
                raise ValueError("SCORED requires a finite numeric value") from exc
            if not math.isfinite(numeric):
                raise ValueError("SCORED requires a finite numeric value")
            object.__setattr__(self, "value", numeric)
            if self.blocker is not None:
                raise ValueError("SCORED cannot carry a blocker")
        elif self.value is not None:
            raise ValueError(f"{self.return_class.value} cannot carry a numeric score")
        if self.return_class is ReturnClass.BLOCKED:
            if not isinstance(self.blocker, str) or not self.blocker.strip():
                raise ValueError("BLOCKED requires a named blocker")
        elif self.blocker is not None:
            raise ValueError("only BLOCKED may carry a blocker")

    @classmethod
    def scored(cls, value: float, note: Optional[str] = None) -> "CriterionResult":
        return cls(ReturnClass.SCORED, value=value, note=note)

    @classmethod
    def unknown_measurable(cls, note: Optional[str] = None) -> "CriterionResult":
        return cls(ReturnClass.UNKNOWN_MEASURABLE, note=note)

    @classmethod
    def unknown_buildable(cls, note: Optional[str] = None) -> "CriterionResult":
        return cls(ReturnClass.UNKNOWN_BUILDABLE, note=note)

    @classmethod
    def unknown_simulable(cls, note: Optional[str] = None) -> "CriterionResult":
        return cls(ReturnClass.UNKNOWN_SIMULABLE, note=note)

    @classmethod
    def blocked(cls, blocker: str, note: Optional[str] = None) -> "CriterionResult":
        return cls(ReturnClass.BLOCKED, blocker=blocker, note=note)

    @classmethod
    def variable_unidentified(cls, note: Optional[str] = None) -> "CriterionResult":
        return cls(ReturnClass.VARIABLE_UNIDENT, note=note)

    @classmethod
    def out_of_envelope(cls, behavior: str) -> "CriterionResult":
        return cls(ReturnClass.OUT_OF_ENVELOPE, note=behavior)

    @property
    def envelope_status(self) -> EnvelopeStatus:
        if self.return_class is ReturnClass.OUT_OF_ENVELOPE:
            return EnvelopeStatus.OUT_OF_ENVELOPE
        return EnvelopeStatus.IN_ENVELOPE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "return_class": self.return_class.value,
            "value": self.value,
            "blocker": self.blocker,
            "note": self.note,
            "envelope_status": self.envelope_status.value,
        }


Measurement = Union[float, int, CriterionResult]


@dataclass(frozen=True)
class CriterionSpec:
    """One measurable criterion and its declared validity envelope."""

    name: CriterionName
    direction: Direction
    valid_envelope: Callable[[Any], bool]
    out_of_envelope: str
    measure: Callable[[Any], Measurement]

    def __post_init__(self) -> None:
        if not isinstance(self.name, CriterionName):
            object.__setattr__(self, "name", CriterionName(self.name))
        if not isinstance(self.direction, Direction):
            object.__setattr__(self, "direction", Direction(self.direction))
        if not callable(self.valid_envelope):
            raise TypeError("valid_envelope must be callable")
        if not callable(self.measure):
            raise TypeError("measure must be callable")
        if not isinstance(self.out_of_envelope, str) or not self.out_of_envelope.strip():
            raise ValueError("out_of_envelope must declare boundary behavior")

    def evaluate(self, state: Any) -> CriterionResult:
        if not bool(self.valid_envelope(state)):
            return CriterionResult.out_of_envelope(self.out_of_envelope)
        measured = self.measure(state)
        if isinstance(measured, CriterionResult):
            return measured
        if isinstance(measured, bool):
            raise TypeError("criterion measurements cannot be boolean scores")
        if isinstance(measured, (int, float)):
            return CriterionResult.scored(measured)
        raise TypeError("measure must return a number or CriterionResult")


@dataclass(frozen=True)
class TerminalCriterion:
    """An external, non-learned physics floor."""

    name: str
    evaluate: Callable[[Any], bool]
    failure_blocker: str = "physics_floor"

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("terminal criterion name must be non-empty")
        if not callable(self.evaluate):
            raise TypeError("terminal criterion evaluate must be callable")
        if not isinstance(self.failure_blocker, str) or not self.failure_blocker.strip():
            raise ValueError("failure_blocker must be non-empty")


@dataclass(frozen=True)
class Option:
    id: str
    value: Any

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("option id must be a non-empty string")


@dataclass
class OptionEvaluation:
    option_id: str
    criterion_results: Dict[CriterionName, CriterionResult]
    terminal_passed: bool
    rollout_depth: int
    envelope_exit_depth: Optional[int] = None
    pareto_rank: Optional[int] = None

    @property
    def fully_scored(self) -> bool:
        return self.terminal_passed and bool(self.criterion_results) and all(
            result.return_class is ReturnClass.SCORED
            for result in self.criterion_results.values()
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "option_id": self.option_id,
            "criterion_results": {
                name.value: result.to_dict()
                for name, result in self.criterion_results.items()
            },
            "terminal_passed": self.terminal_passed,
            "rollout_depth": self.rollout_depth,
            "envelope_exit_depth": self.envelope_exit_depth,
            "pareto_rank": self.pareto_rank,
        }


@dataclass(frozen=True)
class DominanceCredit:
    winner: str
    loser: str
    criteria: Tuple[CriterionName, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "winner": self.winner,
            "loser": self.loser,
            "criteria": [criterion.value for criterion in self.criteria],
        }


@dataclass
class RankingResult:
    evaluations: List[OptionEvaluation]
    fronts: List[List[str]]
    unresolved: List[str]
    credit_assignment: List[DominanceCredit]

    def evaluation_for(self, option_id: str) -> OptionEvaluation:
        for evaluation in self.evaluations:
            if evaluation.option_id == option_id:
                return evaluation
        raise KeyError(option_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fronts": self.fronts,
            "unresolved": self.unresolved,
            "evaluations": [evaluation.to_dict() for evaluation in self.evaluations],
            "credit_assignment": [credit.to_dict() for credit in self.credit_assignment],
        }


Rollout = Callable[[Any, int], Any]


class PreferenceFreeRanker:
    """Rank fully measured options into unweighted Pareto fronts.

    Incomplete options are reported as unresolved peers.  They are never treated
    as worse than measured options and no return class is collapsed into another.
    """

    def __init__(
        self,
        criteria: Sequence[CriterionSpec],
        terminal_criterion: Optional[TerminalCriterion] = None,
    ) -> None:
        if not criteria:
            raise ValueError("at least one criterion is required")
        names = [criterion.name for criterion in criteria]
        if len(names) != len(set(names)):
            raise ValueError("criterion names must be unique")
        self.criteria = tuple(criteria)
        self.terminal_criterion = terminal_criterion

    def _evaluate_state(self, state: Any) -> Dict[CriterionName, CriterionResult]:
        return {criterion.name: criterion.evaluate(state) for criterion in self.criteria}

    @staticmethod
    def _outside(results: Mapping[CriterionName, CriterionResult]) -> bool:
        return any(
            result.return_class is ReturnClass.OUT_OF_ENVELOPE
            for result in results.values()
        )

    def _evaluate_option(
        self,
        option: Option,
        rollout: Optional[Rollout],
        max_rollout_depth: int,
    ) -> OptionEvaluation:
        if self.terminal_criterion is not None and not bool(
            self.terminal_criterion.evaluate(option.value)
        ):
            blocked = CriterionResult.blocked(
                self.terminal_criterion.failure_blocker,
                note=f"failed external terminal criterion: {self.terminal_criterion.name}",
            )
            return OptionEvaluation(
                option_id=option.id,
                criterion_results={criterion.name: blocked for criterion in self.criteria},
                terminal_passed=False,
                rollout_depth=0,
            )

        state = option.value
        results = self._evaluate_state(state)
        if self._outside(results):
            return OptionEvaluation(
                option_id=option.id,
                criterion_results=results,
                terminal_passed=True,
                rollout_depth=0,
                envelope_exit_depth=0,
            )

        reached = 0
        if rollout is not None:
            for depth in range(1, max_rollout_depth + 1):
                state = rollout(state, depth)
                candidate = self._evaluate_state(state)
                if self._outside(candidate):
                    return OptionEvaluation(
                        option_id=option.id,
                        criterion_results=candidate,
                        terminal_passed=True,
                        rollout_depth=depth - 1,
                        envelope_exit_depth=depth,
                    )
                results = candidate
                reached = depth

        return OptionEvaluation(
            option_id=option.id,
            criterion_results=results,
            terminal_passed=True,
            rollout_depth=reached,
        )

    def _dominance(
        self, left: OptionEvaluation, right: OptionEvaluation
    ) -> Tuple[bool, Tuple[CriterionName, ...]]:
        if not left.fully_scored or not right.fully_scored:
            return False, ()
        no_worse = True
        strict: List[CriterionName] = []
        for criterion in self.criteria:
            left_value = left.criterion_results[criterion.name].value
            right_value = right.criterion_results[criterion.name].value
            assert left_value is not None and right_value is not None
            if criterion.direction is Direction.MAXIMIZE:
                if left_value < right_value:
                    no_worse = False
                    break
                if left_value > right_value:
                    strict.append(criterion.name)
            else:
                if left_value > right_value:
                    no_worse = False
                    break
                if left_value < right_value:
                    strict.append(criterion.name)
        return no_worse and bool(strict), tuple(strict)

    def rank(
        self,
        options: Iterable[Option],
        *,
        rollout: Optional[Rollout] = None,
        max_rollout_depth: int = 0,
    ) -> RankingResult:
        if isinstance(max_rollout_depth, bool) or not isinstance(max_rollout_depth, int):
            raise TypeError("max_rollout_depth must be an integer")
        if max_rollout_depth < 0:
            raise ValueError("max_rollout_depth cannot be negative")
        if rollout is None and max_rollout_depth:
            raise ValueError("a rollout function is required when max_rollout_depth is positive")

        option_list = list(options)
        ids = [option.id for option in option_list]
        if len(ids) != len(set(ids)):
            raise ValueError("option ids must be unique")
        evaluations = [
            self._evaluate_option(option, rollout, max_rollout_depth)
            for option in option_list
        ]
        complete = [evaluation for evaluation in evaluations if evaluation.fully_scored]
        unresolved = [
            evaluation.option_id for evaluation in evaluations if not evaluation.fully_scored
        ]

        dominates: Dict[str, set] = {evaluation.option_id: set() for evaluation in complete}
        dominated_by_count: Dict[str, int] = {
            evaluation.option_id: 0 for evaluation in complete
        }
        credits: List[DominanceCredit] = []
        for left in complete:
            for right in complete:
                if left is right:
                    continue
                is_dominant, strict = self._dominance(left, right)
                if is_dominant:
                    dominates[left.option_id].add(right.option_id)
                    dominated_by_count[right.option_id] += 1
                    credits.append(DominanceCredit(left.option_id, right.option_id, strict))

        by_id = {evaluation.option_id: evaluation for evaluation in complete}
        fronts: List[List[str]] = []
        current = sorted(
            option_id for option_id, count in dominated_by_count.items() if count == 0
        )
        rank_number = 1
        assigned = set()
        while current:
            fronts.append(current)
            next_front = set()
            for option_id in current:
                assigned.add(option_id)
                by_id[option_id].pareto_rank = rank_number
                for loser in dominates[option_id]:
                    dominated_by_count[loser] -= 1
                    if dominated_by_count[loser] == 0:
                        next_front.add(loser)
            current = sorted(next_front - assigned)
            rank_number += 1

        return RankingResult(
            evaluations=evaluations,
            fronts=fronts,
            unresolved=unresolved,
            credit_assignment=sorted(
                credits,
                key=lambda credit: (
                    credit.winner,
                    credit.loser,
                    tuple(item.value for item in credit.criteria),
                ),
            ),
        )


def rank_options(
    options: Iterable[Option],
    criteria: Sequence[CriterionSpec],
    *,
    terminal_criterion: Optional[TerminalCriterion] = None,
    rollout: Optional[Rollout] = None,
    max_rollout_depth: int = 0,
) -> RankingResult:
    return PreferenceFreeRanker(criteria, terminal_criterion).rank(
        options,
        rollout=rollout,
        max_rollout_depth=max_rollout_depth,
    )


def rank_branch_set(
    branch_set: BranchSet,
    criteria: Sequence[CriterionSpec],
    *,
    terminal_criterion: Optional[TerminalCriterion] = None,
    rollout: Optional[Rollout] = None,
    max_rollout_depth: int = 0,
) -> RankingResult:
    """Use a BranchSet's open branches as the option enumerator."""

    options = [Option(branch.id, branch) for branch in branch_set.test_queue()]
    return rank_options(
        options,
        criteria,
        terminal_criterion=terminal_criterion,
        rollout=rollout,
        max_rollout_depth=max_rollout_depth,
    )


__all__ = [
    "CriterionName",
    "CriterionResult",
    "CriterionSpec",
    "Direction",
    "DominanceCredit",
    "EnvelopeStatus",
    "Option",
    "OptionEvaluation",
    "PreferenceFreeRanker",
    "RankingResult",
    "ReturnClass",
    "TerminalCriterion",
    "rank_branch_set",
    "rank_options",
]
