import io
import json
import tempfile
import unittest
from pathlib import Path

from branch_set import (
    AccessKind,
    Branch,
    BranchSet,
    BranchStatus,
    InstrumentHistory,
    PredictionElsewhere,
    RecordPresence,
    RecordState,
    SuppressionCause,
    TriageClass,
)


class BranchSetTests(unittest.TestCase):
    def make_branch(self, branch_id="b1", cost=3.0, state=RecordState.INSTRUMENT_EXISTS_UNRUN):
        return Branch(
            id=branch_id,
            generator="generator",
            origin_pattern="origin-domain",
            predicted_divergence="predicted divergence",
            discriminator="cheap test",
            cost=cost,
            suppression_cause=SuppressionCause.PRIOR,
            predicts_elsewhere=[
                PredictionElsewhere(
                    pattern="distant pattern",
                    domain="distant-domain",
                    already_in_record=RecordPresence.UNKNOWN,
                    record_state=state,
                )
            ],
            instrument_history=[
                InstrumentHistory(
                    phenomenon_before="signal was ungradeable",
                    made_readable="signal timing",
                    discipline_crossed="physics to biology",
                    question_askable_date="2020-01-01",
                    instrument_built_date="2020-01-11",
                )
            ],
        )

    def test_json_round_trip_is_lossless(self):
        original = BranchSet([self.make_branch()])
        encoded = original.serialize()
        self.assertEqual(BranchSet.load(encoded), original)
        parsed = json.loads(encoded)
        self.assertEqual(parsed["schema_version"], "1.0")
        self.assertEqual(parsed["branches"][0]["instrument_history"][0]["lag"], 10)

    def test_load_from_path_and_write(self):
        branch_set = BranchSet([self.make_branch()])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "branches.json"
            branch_set.write(path)
            self.assertEqual(BranchSet.load(path), branch_set)

    def test_queue_is_open_and_cost_ordered(self):
        expensive = self.make_branch("expensive", 10)
        cheap = self.make_branch("cheap", 1)
        eliminated = self.make_branch("eliminated", 0)
        eliminated.eliminate("cheap")
        branch_set = BranchSet([expensive, eliminated, cheap])
        self.assertEqual([item.id for item in branch_set.test_queue()], ["cheap", "expensive"])
        self.assertEqual(branch_set.eliminated_set(), [eliminated])
        self.assertEqual(eliminated.discriminator, "cheap test")

    def test_origin_domain_is_rejected_as_landing_site(self):
        with self.assertRaisesRegex(ValueError, "must differ"):
            Branch(
                id="bad",
                generator="g",
                origin_pattern="same-domain",
                predicted_divergence="d",
                discriminator="test",
                cost=1,
                suppression_cause="prior",
                predicts_elsewhere=[
                    PredictionElsewhere(
                        pattern="p",
                        domain="same-domain",
                        already_in_record="unknown",
                        record_state="no_measurement_needed",
                    )
                ],
            )

    def test_unknown_record_requires_machine_state(self):
        with self.assertRaisesRegex(ValueError, "record_state is required"):
            PredictionElsewhere(
                pattern="p",
                domain="elsewhere",
                already_in_record="unknown",
            )

    def test_triage_prints_each_declared_rule(self):
        states = [
            RecordState.INSTRUMENT_EXISTS_UNRUN,
            RecordState.COMPONENTS_EXIST_UNASSEMBLED,
            RecordState.NO_MEASUREMENT_NEEDED,
            RecordState.MISSING_PIECE,
        ]
        branches = [self.make_branch(f"b{index}", state=state) for index, state in enumerate(states)]
        output = io.StringIO()
        results = BranchSet(branches).triage(stream=output)
        self.assertEqual(
            [item.result for item in results],
            [
                TriageClass.ANSWERABLE_NOW,
                TriageClass.BUILDABLE,
                TriageClass.SIMULABLE,
                TriageClass.BLOCKED,
            ],
        )
        self.assertEqual(results[-1].label, "blocked(prior)")
        self.assertIn("instrument_exists_unrun -> answerable_now", output.getvalue())
        self.assertIn("missing_piece + suppression_cause=prior -> blocked(prior)", output.getvalue())

    def test_access_cause_requires_access_kind(self):
        with self.assertRaisesRegex(ValueError, "access_kind is required"):
            Branch(
                id="bad",
                generator="g",
                origin_pattern="o",
                predicted_divergence="d",
                discriminator="test",
                cost=1,
                suppression_cause="access",
            )
        valid = self.make_branch()
        valid.suppression_cause = SuppressionCause.ACCESS
        valid.access_kind = AccessKind.INSTRUMENT_MISSING
        valid.__post_init__()
        self.assertEqual(valid.access_kind, AccessKind.INSTRUMENT_MISSING)

    def test_status_and_eliminator_are_consistent(self):
        with self.assertRaisesRegex(ValueError, "eliminated_by"):
            Branch(
                id="bad",
                generator="g",
                origin_pattern="o",
                predicted_divergence="d",
                discriminator="test",
                cost=1,
                status=BranchStatus.ELIMINATED,
                suppression_cause="prior",
            )

    def test_branch_packet_keeps_full_set_behind_active_branch(self):
        branch_set = BranchSet([self.make_branch("one"), self.make_branch("two")])
        packet = branch_set.branch_packet("one")
        self.assertEqual(packet["active_branch_id"], "one")
        self.assertEqual(len(packet["branch_set"]["branches"]), 2)

    def test_unknown_fields_are_rejected(self):
        data = BranchSet([self.make_branch()]).to_dict()
        data["surprise"] = True
        with self.assertRaisesRegex(ValueError, "unknown branch set field"):
            BranchSet.from_dict(data)


if __name__ == "__main__":
    unittest.main()
