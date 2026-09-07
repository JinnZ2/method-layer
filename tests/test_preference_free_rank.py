import unittest

from branch_set import Branch, BranchSet
from preference_free_rank import (
    CriterionName,
    CriterionResult,
    CriterionSpec,
    Direction,
    EnvelopeStatus,
    Option,
    PreferenceFreeRanker,
    ReturnClass,
    TerminalCriterion,
    rank_branch_set,
)


class PreferenceFreeRankTests(unittest.TestCase):
    def criteria(self):
        return [
            CriterionSpec(
                CriterionName.BITS_RETURNED_PER_ENERGY,
                Direction.MAXIMIZE,
                valid_envelope=lambda item: item["within"],
                out_of_envelope="energy model invalid beyond boundary",
                measure=lambda item: item["information"],
            ),
            CriterionSpec(
                CriterionName.DEPENDENCY_ADDED,
                Direction.MINIMIZE,
                valid_envelope=lambda item: item["within"],
                out_of_envelope="coupling model invalid beyond boundary",
                measure=lambda item: item["dependencies"],
            ),
        ]

    def test_pareto_fronts_use_no_weights(self):
        options = [
            Option("dominant", {"within": True, "information": 10, "dependencies": 1}),
            Option("inferior", {"within": True, "information": 5, "dependencies": 2}),
            Option("tradeoff", {"within": True, "information": 12, "dependencies": 3}),
        ]
        result = PreferenceFreeRanker(self.criteria()).rank(options)
        self.assertEqual(result.fronts[0], ["dominant", "tradeoff"])
        self.assertEqual(result.fronts[1], ["inferior"])
        credits = {(item.winner, item.loser) for item in result.credit_assignment}
        self.assertIn(("dominant", "inferior"), credits)

    def test_outside_envelope_never_calls_measurement(self):
        called = []
        criterion = CriterionSpec(
            CriterionName.REVERSIBILITY,
            Direction.MAXIMIZE,
            valid_envelope=lambda item: False,
            out_of_envelope="known phase boundary",
            measure=lambda item: called.append(item),
        )
        result = PreferenceFreeRanker([criterion]).rank([Option("x", object())])
        evaluation = result.evaluation_for("x")
        measured = evaluation.criterion_results[CriterionName.REVERSIBILITY]
        self.assertEqual(called, [])
        self.assertEqual(measured.return_class, ReturnClass.OUT_OF_ENVELOPE)
        self.assertEqual(measured.envelope_status, EnvelopeStatus.OUT_OF_ENVELOPE)
        self.assertEqual(result.unresolved, ["x"])

    def test_unknown_is_peer_not_inferior_score(self):
        criterion = CriterionSpec(
            CriterionName.CYCLE_SURVIVAL,
            Direction.MAXIMIZE,
            valid_envelope=lambda item: True,
            out_of_envelope="cycle not represented",
            measure=lambda item: (
                item["value"]
                if item["value"] is not None
                else CriterionResult.unknown_measurable("instrument exists, unrun")
            ),
        )
        result = PreferenceFreeRanker([criterion]).rank(
            [Option("known", {"value": 1}), Option("unknown", {"value": None})]
        )
        self.assertEqual(result.fronts, [["known"]])
        self.assertEqual(result.unresolved, ["unknown"])
        unknown = result.evaluation_for("unknown")
        self.assertIsNone(unknown.pareto_rank)
        self.assertEqual(
            unknown.criterion_results[CriterionName.CYCLE_SURVIVAL].return_class,
            ReturnClass.UNKNOWN_MEASURABLE,
        )

    def test_rollout_records_depth_before_envelope_exit(self):
        criterion = CriterionSpec(
            CriterionName.REVERSIBILITY,
            Direction.MAXIMIZE,
            valid_envelope=lambda value: value < 3,
            out_of_envelope="state cannot be restored after phase change",
            measure=float,
        )
        result = PreferenceFreeRanker([criterion]).rank(
            [Option("x", 0)],
            rollout=lambda value, depth: value + 1,
            max_rollout_depth=5,
        )
        evaluation = result.evaluation_for("x")
        self.assertEqual(evaluation.rollout_depth, 2)
        self.assertEqual(evaluation.envelope_exit_depth, 3)
        self.assertEqual(
            evaluation.criterion_results[CriterionName.REVERSIBILITY].return_class,
            ReturnClass.OUT_OF_ENVELOPE,
        )

    def test_terminal_physics_floor_blocks_without_scoring(self):
        calls = []
        criterion = CriterionSpec(
            CriterionName.COST_ASYMMETRY,
            Direction.MINIMIZE,
            valid_envelope=lambda item: True,
            out_of_envelope="not applicable",
            measure=lambda item: calls.append(item),
        )
        floor = TerminalCriterion("energy conservation", lambda item: False, "violates_energy_floor")
        result = PreferenceFreeRanker([criterion], floor).rank([Option("x", {})])
        evaluation = result.evaluation_for("x")
        self.assertFalse(evaluation.terminal_passed)
        self.assertEqual(calls, [])
        self.assertEqual(
            evaluation.criterion_results[CriterionName.COST_ASYMMETRY].return_class,
            ReturnClass.BLOCKED,
        )

    def test_non_score_cannot_carry_float(self):
        with self.assertRaisesRegex(ValueError, "cannot carry"):
            CriterionResult(ReturnClass.UNKNOWN_SIMULABLE, value=0.0)

    def test_branch_set_is_an_option_enumerator(self):
        branch_set = BranchSet(
            [
                Branch("expensive", "g", "o", "d", "test", 4, suppression_cause="prior"),
                Branch("cheap", "g", "o", "d", "test", 2, suppression_cause="prior"),
            ]
        )
        criterion = CriterionSpec(
            CriterionName.COST_ASYMMETRY,
            Direction.MINIMIZE,
            valid_envelope=lambda branch: branch.cost > 0,
            out_of_envelope="cost must be positive",
            measure=lambda branch: branch.cost,
        )
        result = rank_branch_set(branch_set, [criterion])
        self.assertEqual(result.fronts, [["cheap"], ["expensive"]])


if __name__ == "__main__":
    unittest.main()
