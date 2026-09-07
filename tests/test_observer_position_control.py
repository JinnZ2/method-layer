"""Mechanics tests on synthetic coding records with planted structure.

No record here is a published source; ``synthetic_corpus`` says so in every
``source_ref``.
"""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from preference_free_rank import ReturnClass
from observer_position_control import (
    PREDICTION,
    THIN,
    AdaptiveAccount,
    BehaviorCode,
    Cause,
    Intensity,
    LabelClass,
    LiteratureType,
    ObserverPositionControl,
    Outcome,
    Position,
    SourceRecord,
    contingency,
    corpus_to_dict,
    cramers_v,
    load_corpus,
    main,
    stratified_effect,
    synthetic_corpus,
)


def record(**overrides):
    base = dict(
        id="r1",
        source_ref="unit-test fixture (not a published source)",
        position=Position.OWN,
        label_class=LabelClass.NEED,
        attributed_cause=Cause.FUNCTION,
        adaptive_account=AdaptiveAccount.SUPPLIED,
        null_offered=False,
        test_proposed=False,
        decade=1990,
        literature_type=LiteratureType.PSYCHOLOGY,
        intensity=Intensity.MODERATE,
        behavior=BehaviorCode(True, True, True),
        coded_blind=True,
        coder="fixture",
    )
    base.update(overrides)
    return SourceRecord(**base)


class RecordTests(unittest.TestCase):
    def test_round_trip_and_enum_coercion(self):
        item = record(position="1_non_human_species", label_class="pathology")
        self.assertIs(item.position, Position.NON_HUMAN)
        self.assertTrue(item.pathologising)
        self.assertEqual(SourceRecord.from_dict(item.to_dict()), item)
        self.assertEqual(item.behavior.signature, "111")

    def test_validation(self):
        with self.assertRaises(ValueError):
            record(decade=1995)
        with self.assertRaises(ValueError):
            record(label_class="disorder")
        with self.assertRaises(ValueError):
            record(coded_blind="yes")
        with self.assertRaises(ValueError):
            SourceRecord.from_dict({**record().to_dict(), "extra": 1})
        with self.assertRaises(ValueError):
            BehaviorCode.from_dict({"test_phase_absent": True})
        with self.assertRaises(ValueError):
            SourceRecord.from_dict({"id": "x"})

    def test_corpus_load_and_schema(self):
        records = synthetic_corpus(3, seed=1)
        payload = corpus_to_dict(records)
        self.assertEqual(load_corpus(payload), records)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corpus.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(load_corpus(str(path)), records)
        with self.assertRaises(ValueError):
            load_corpus({"schema_version": "0.1", "records": []})
        with self.assertRaises(ValueError):
            load_corpus({"schema_version": "1.0", "records": [records[0].to_dict()] * 2})

    def test_synthetic_records_are_labelled_synthetic(self):
        for item in synthetic_corpus(2, seed=0):
            self.assertIn("SYNTHETIC", item.source_ref)
            self.assertTrue(item.coded_blind)


class ArithmeticTests(unittest.TestCase):
    def test_contingency_and_cramers_v(self):
        records = [
            record(id="a", position=Position.NON_HUMAN, label_class=LabelClass.PATHOLOGY),
            record(id="b", position=Position.NON_HUMAN, label_class=LabelClass.PATHOLOGY),
            record(id="c", position=Position.OWN, label_class=LabelClass.NEED),
            record(id="d", position=Position.OWN, label_class=LabelClass.NEED),
        ]
        table = contingency(records)
        self.assertEqual(table[Position.NON_HUMAN.value][LabelClass.PATHOLOGY.value], 2)
        self.assertAlmostEqual(cramers_v(table), 1.0)
        self.assertIsNone(cramers_v(contingency(records[:2])))

    def test_stratified_effect_weights_and_collinearity(self):
        records = []
        for i in range(4):
            records.append(record(id=f"e{i}", position=Position.NON_HUMAN, label_class=LabelClass.PATHOLOGY, decade=1960))
            records.append(record(id=f"f{i}", position=Position.OWN, label_class=LabelClass.NEED, decade=1960))
            records.append(record(id=f"g{i}", position=Position.NON_HUMAN, label_class=LabelClass.ARTIFACT, decade=2000))
            records.append(record(id=f"h{i}", position=Position.OWN, label_class=LabelClass.VIRTUE, decade=2000))
        effect = stratified_effect(records, lambda r: r.decade, "decade", min_cell=3, min_strata=2)
        self.assertAlmostEqual(effect.effect, 1.0)
        self.assertEqual(effect.strata_used, ("1960", "2000"))
        self.assertFalse(effect.collinear)
        split = [r for r in records if (r.position is Position.NON_HUMAN) == (r.decade == 1960)]
        inseparable = stratified_effect(split, lambda r: r.decade, "decade", min_cell=3, min_strata=2)
        self.assertIsNone(inseparable.effect)
        self.assertTrue(inseparable.collinear)
        self.assertIn("inseparable", inseparable.rule)


class ControlTests(unittest.TestCase):
    control = ObserverPositionControl()

    def test_thresholds_are_declared_and_validated(self):
        self.assertEqual(self.control.thresholds()["effect_min"], 0.2)
        with self.assertRaises(ValueError):
            ObserverPositionControl(effect_min=0.0)
        with self.assertRaises(ValueError):
            ObserverPositionControl(min_cell=0)

    def test_planted_effect_survives_all_nulls(self):
        for seed in (0, 1):
            result = self.control.run(synthetic_corpus(40, observer_effect=0.6, seed=seed))
            self.assertIs(result.outcome, Outcome.OBSERVER_INDEXED, result.rule)
            self.assertGreater(result.raw_effect, 0.4)
            self.assertGreater(result.residual_effect, 0.2)
            self.assertEqual(result.behavior_spread, 0.0)
            criterion = result.to_criterion_result()
            self.assertIs(criterion.return_class, ReturnClass.SCORED)
            self.assertAlmostEqual(criterion.value, result.residual_effect)
            # Positions 1 and 3 carry the planted direction; position 2 sits at base rate.
            # The generator plants pathologising vs not, not the sub-class, so position 3's
            # modal label may be "virtue", which the registered prediction does not name.
            self.assertTrue(result.prediction_check[Position.NON_HUMAN.value]["agrees"])
            self.assertNotIn(
                result.prediction_check[Position.OWN.value]["modal_label"], ("pathology", "artifact")
            )

    def test_large_corpus_reads_the_joint_residual(self):
        result = self.control.run(synthetic_corpus(150, observer_effect=0.6, seed=0))
        self.assertIs(result.outcome, Outcome.OBSERVER_INDEXED)
        self.assertIn("residual kind: joint", result.rule)
        self.assertTrue(result.residual.stratifier.startswith("joint"))

    def test_no_planted_effect_reads_no_effect(self):
        result = self.control.run(synthetic_corpus(40, seed=0))
        self.assertIs(result.outcome, Outcome.NO_EFFECT)
        criterion = result.to_criterion_result()
        self.assertIs(criterion.return_class, ReturnClass.SCORED)
        self.assertEqual(criterion.value, 0.0)

    def test_pure_confounds_read_confounded(self):
        cases = {
            "decade": dict(decade_confound=1.0),
            "literature_type": dict(literature_confound=1.0),
            "intensity": dict(severity_confound=1.0),
            "decade": dict(decade_confound=0.5),
            "literature_type": dict(literature_confound=0.5),
        }
        for name, kwargs in cases.items():
            result = self.control.run(synthetic_corpus(40, seed=0, **kwargs))
            self.assertIs(result.outcome, Outcome.CONFOUNDED, (name, result.rule))
            self.assertIn(name, result.rule)
            self.assertIs(result.to_criterion_result().return_class, ReturnClass.UNKNOWN_MEASURABLE)

    def test_effect_plus_partial_confound_survives_but_total_confound_is_inseparable(self):
        partial = self.control.run(synthetic_corpus(40, observer_effect=0.6, decade_confound=0.5, seed=0))
        self.assertIs(partial.outcome, Outcome.OBSERVER_INDEXED)
        self.assertLess(partial.residual_effect, partial.raw_effect)
        total = self.control.run(synthetic_corpus(40, observer_effect=0.6, decade_confound=1.0, seed=0))
        self.assertIs(total.outcome, Outcome.CONFOUNDED)
        self.assertIn("inseparable", total.rule)

    def test_main_null_behaviour_differs_returns_nothing(self):
        result = self.control.run(synthetic_corpus(40, observer_effect=0.6, behavior_mismatch_in_own=0.6, seed=0))
        self.assertIs(result.outcome, Outcome.BEHAVIOR_DIFFERS)
        self.assertGreaterEqual(result.behavior_spread, 0.3)
        self.assertIs(result.to_criterion_result().return_class, ReturnClass.UNKNOWN_MEASURABLE)
        self.assertEqual(result.stratified, [])

    def test_non_matching_records_are_excluded_before_labels_are_read(self):
        records = synthetic_corpus(40, observer_effect=0.6, behavior_mismatch_in_own=0.2, seed=0)
        result = self.control.run(records)
        self.assertLess(result.n_matched, result.n_blind)
        self.assertEqual(sum(sum(row.values()) for row in result.contingency.values()), result.n_matched)

    def test_thin_corpus_is_unknown_measurable(self):
        result = self.control.run(synthetic_corpus(3, observer_effect=0.6, seed=0))
        self.assertIs(result.outcome, Outcome.UNKNOWN_MEASURABLE)
        self.assertIn(THIN, result.rule)
        criterion = result.to_criterion_result()
        self.assertIs(criterion.return_class, ReturnClass.UNKNOWN_MEASURABLE)

    def test_non_blind_records_do_not_enter(self):
        records = [
            SourceRecord.from_dict({**r.to_dict(), "coded_blind": False})
            for r in synthetic_corpus(10, observer_effect=0.6, seed=0)
        ]
        result = self.control.run(records)
        self.assertEqual(result.n_blind, 0)
        self.assertIs(result.outcome, Outcome.UNKNOWN_MEASURABLE)

    def test_prediction_is_registered_and_reported_not_returned(self):
        self.assertEqual(PREDICTION[Position.OWN], (LabelClass.NEED, LabelClass.ADAPTATION))
        result = self.control.run(synthetic_corpus(40, observer_effect=-0.6, seed=0))
        # Effect in the opposite direction: still a measured effect, prediction disagrees.
        self.assertIs(result.outcome, Outcome.OBSERVER_INDEXED)
        self.assertLess(result.residual_effect, 0)
        self.assertFalse(result.prediction_check[Position.OWN.value]["agrees"])
        text = result.format()
        self.assertIn("prediction", text)
        json.dumps(result.to_dict())


class CliTests(unittest.TestCase):
    def test_synthetic_and_prediction_commands(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(main(["synthetic", "--effect", "0.6", "--json"]), 0)
            self.assertEqual(main(["prediction"]), 0)
        text = buffer.getvalue()
        self.assertIn('"observer_indexed"', text)
        self.assertIn("registered before running", text)

    def test_run_command_on_corpus_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corpus.json"
            path.write_text(json.dumps(corpus_to_dict(synthetic_corpus(30, seed=2))), encoding="utf-8")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                self.assertEqual(main(["run", str(path)]), 0)
            self.assertIn("OBSERVER POSITION CONTROL", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
