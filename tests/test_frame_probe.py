"""Mechanics tests.  The probes below are unit-test fixtures, not a probe library."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from branch_set import BranchStatus, SuppressionCause
from preference_free_rank import ReturnClass
from frame_probe import (
    CONTAMINATED,
    INSTRUMENT_MISREAD,
    KNOWN_FAILURES,
    PROBE_BUDGET,
    SEED_COUPLING_ENTRY,
    UNCALIBRATED,
    UNTESTED,
    WRONG_INSTRUMENT,
    CollapseReading,
    CouplingEntry,
    CouplingLog,
    FrameProbeSession,
    GateStatus,
    Grade,
    IdentityModel,
    IdentityObservations,
    Probe,
    SessionOutcome,
    ValidityGate,
    frame_variances,
    grade_identity,
    identity_null_branch_set,
    label_reading,
    load_library,
    main,
    read_collapse,
    run_session,
    separation_score,
    term_branch_set,
    term_intake_queue,
    underlying_position,
)

FIXTURE_AUTHOR = "unit-test fixture (mechanics only; not a probe library)"


def probe_dict(pid, senses, index, load=0.0, calibration=None):
    return {
        "id": pid,
        "term_or_phrase": f"term-{pid}",
        "sense_space": senses,
        "frame_index": index,
        "emitter_marker_load": load,
        "author": FIXTURE_AUTHOR,
        "author_kind": "human",
        "calibration": calibration or {},
    }


def clean_calibration(index):
    """Each frame's respondents collapse to the sense that indexes it."""

    calibration = {}
    for sense, frames in index.items():
        for frame in frames:
            calibration[frame] = [sense, sense, sense]
    return calibration


def library():
    p1_index = {"a": ["F1", "F2"], "b": ["F3", "F4"]}
    p2_index = {"c": ["F1", "F3"], "d": ["F2", "F4"]}
    p5_index = {"i": ["F1"], "j": ["F2"], "k": ["F3", "F4"]}
    return load_library(
        {
            "schema_version": "1.0",
            "probes": [
                probe_dict("p1", ["a", "b"], p1_index, calibration=clean_calibration(p1_index)),
                probe_dict("p2", ["c", "d"], p2_index, calibration=clean_calibration(p2_index)),
                probe_dict("p3", ["e", "f"], {"e": ["F1"], "f": ["F2"]}, load=0.9,
                           calibration=clean_calibration({"e": ["F1"], "f": ["F2"]})),
                probe_dict("p4", ["g", "h"], {"g": ["F1"], "h": ["F2"]},
                           calibration={"F1": ["g", "h", "g", "h"], "F2": ["h", "g", "g", "h"]}),
                probe_dict("p5", ["i", "j", "k"], p5_index, calibration=clean_calibration(p5_index)),
            ],
        }
    )


class ProbeRecordTests(unittest.TestCase):
    def test_round_trip(self):
        probe = library()[0]
        self.assertEqual(Probe.from_dict(probe.to_dict()), probe)
        self.assertEqual(probe.frames, ("F1", "F2", "F3", "F4"))

    def test_partition_author_kind_must_be_human(self):
        data = probe_dict("x", ["a"], {"a": ["F1"]})
        for kind in ("model", "generated", "claude", ""):
            with self.assertRaises(ValueError):
                Probe.from_dict({**data, "author_kind": kind})
        del data["author_kind"]
        with self.assertRaises(ValueError):
            Probe.from_dict(data)

    def test_validation(self):
        with self.assertRaises(ValueError):
            Probe.from_dict(probe_dict("x", [], {}))
        with self.assertRaises(ValueError):
            Probe.from_dict(probe_dict("x", ["a", "a"], {"a": ["F1"]}))
        with self.assertRaises(ValueError):
            Probe.from_dict(probe_dict("x", ["a"], {"zz": ["F1"]}))
        with self.assertRaises(ValueError):
            Probe.from_dict(probe_dict("x", ["a"], {"a": ["F1"]}, load=1.5))
        with self.assertRaises(ValueError):
            Probe.from_dict(probe_dict("x", ["a"], {"a": ["F1"]}, calibration={"F1": ["nope"]}))
        with self.assertRaises(ValueError):
            Probe.from_dict({**probe_dict("x", ["a"], {"a": ["F1"]}), "extra": 1})

    def test_library_loading_from_path_and_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lib.json"
            path.write_text(json.dumps({"schema_version": "1.0", "probes": [probe_dict("x", ["a"], {"a": ["F1"]})]}))
            self.assertEqual(len(load_library(str(path))), 1)
            self.assertEqual(len(load_library(path)), 1)
        with self.assertRaises(ValueError):
            load_library({"schema_version": "0.9", "probes": []})
        with self.assertRaises(ValueError):
            load_library({"schema_version": "1.0", "probes": [probe_dict("x", ["a"], {"a": ["F1"]})] * 2})


class ValidityGateTests(unittest.TestCase):
    def test_contamination_is_checked_first_and_blocks(self):
        result = ValidityGate().check(library()[2])
        self.assertIs(result.status, GateStatus.BLOCKED)
        self.assertEqual(result.blocker, CONTAMINATED)
        self.assertIsNone(result.ratio)
        criterion = result.to_criterion_result()
        self.assertIs(criterion.return_class, ReturnClass.BLOCKED)
        self.assertEqual(criterion.blocker, CONTAMINATED)

    def test_clean_separation_is_valid(self):
        result = ValidityGate().check(library()[0])
        self.assertIs(result.status, GateStatus.VALID)
        self.assertEqual(result.within_frame_variance, 0.0)
        self.assertIsNone(result.to_criterion_result())
        self.assertIsNone(result.to_dict()["ratio"])  # infinite ratio serialises as null

    def test_person_reading_probe_is_unknown_measurable(self):
        result = ValidityGate().check(library()[3])
        self.assertIs(result.status, GateStatus.UNKNOWN_MEASURABLE)
        self.assertIn("PERSON", result.rule)
        self.assertIs(result.to_criterion_result().return_class, ReturnClass.UNKNOWN_MEASURABLE)

    def test_uncalibrated_probe_is_blocked(self):
        probe = Probe.from_dict(probe_dict("x", ["a", "b"], {"a": ["F1"], "b": ["F2"]}))
        result = ValidityGate().check(probe)
        self.assertIs(result.status, GateStatus.BLOCKED)
        self.assertEqual(result.blocker, UNCALIBRATED)
        self.assertIsNone(frame_variances(probe))

    def test_ratio_threshold_is_declared(self):
        probe = Probe.from_dict(
            probe_dict("x", ["a", "b"], {"a": ["F1"], "b": ["F2"]},
                       calibration={"F1": ["a", "a", {"a": 0.6, "b": 0.4}], "F2": ["b", "b", {"a": 0.4, "b": 0.6}]})
        )
        between, within = frame_variances(probe)
        ratio = between / within
        self.assertIs(ValidityGate(valid_ratio=ratio * 0.5).check(probe).status, GateStatus.VALID)
        self.assertIs(ValidityGate(valid_ratio=ratio * 2).check(probe).status, GateStatus.UNKNOWN_MEASURABLE)
        with self.assertRaises(ValueError):
            ValidityGate(valid_ratio=1.0)

    def test_no_variance_anywhere_is_unknown(self):
        probe = Probe.from_dict(
            probe_dict("x", ["a", "b"], {"a": ["F1"], "b": ["F2"]},
                       calibration={"F1": ["a", "a"], "F2": ["a", "a"]})
        )
        self.assertIs(ValidityGate().check(probe).status, GateStatus.UNKNOWN_MEASURABLE)


class CollapseReadingTests(unittest.TestCase):
    def test_readings(self):
        self.assertEqual(read_collapse(["a", "b", "c"], ["b"]), (CollapseReading.COLLAPSED, ("b",)))
        self.assertEqual(read_collapse(["a", "b", "c"], ["c", "a", "b"]), (CollapseReading.HELD, ("a", "b", "c")))
        self.assertEqual(read_collapse(["a", "b", "c"], ["c", "a"]), (CollapseReading.PARTIAL, ("a", "c")))
        with self.assertRaises(ValueError):
            read_collapse(["a"], ["zz"])
        with self.assertRaises(ValueError):
            read_collapse(["a"], [])


class SessionTests(unittest.TestCase):
    def test_gate_runs_first_and_only_valid_probes_are_usable(self):
        session = FrameProbeSession(library())
        self.assertEqual(session.valid_ids, ["p1", "p2", "p5"])
        self.assertEqual(session.remaining, ("F1", "F2", "F3", "F4"))
        with self.assertRaises(ValueError):
            session.observe("p3", ["e"])

    def test_selection_is_by_separation_not_importance(self):
        session = FrameProbeSession(library())
        scores = {pid: separation_score(session._probes[pid], session.remaining) for pid in session.valid_ids}
        self.assertEqual(scores["p1"], 2.0)
        self.assertEqual(scores["p2"], 2.0)
        self.assertEqual(scores["p5"], 1.5)
        self.assertEqual(session.next_probe().id, "p5")

    def test_loop_narrows_to_confirmation(self):
        session = FrameProbeSession(library())
        first = session.observe("p1", ["a"])
        self.assertEqual(first.remaining_after, ("F1", "F2"))
        self.assertIs(session.result().outcome, SessionOutcome.OPEN)
        nxt = session.next_probe()
        self.assertIn(nxt.id, ("p2", "p5"))
        session.observe("p2", ["d"])
        estimate = session.result()
        self.assertIs(estimate.outcome, SessionOutcome.CONFIRMED)
        self.assertEqual(estimate.frame, "F2")
        self.assertEqual(len(estimate.probes_spent), 2)
        self.assertIs(estimate.to_criterion_result().return_class, ReturnClass.VARIABLE_UNIDENT)
        self.assertIsNone(session.next_probe())
        json.dumps(estimate.to_dict())

    def test_held_collapse_intersects_frames(self):
        session = FrameProbeSession(library(), frames=["F1", "F2", "F3", "F4", "F9"])
        step = session.observe("p1", ["a", "b"])
        self.assertIs(step.reading, CollapseReading.HELD)
        # No frame is indexed by both senses; F9 is uninformed by p1 and survives.
        self.assertEqual(step.remaining_after, ("F9",))

    def test_contradiction_stops_on_unknown(self):
        session = FrameProbeSession(library())
        session.observe("p1", ["a"])
        session.observe("p2", ["c"])
        session.observe("p5", ["k"])
        estimate = session.result()
        self.assertIs(estimate.outcome, SessionOutcome.UNKNOWN_MEASURABLE)
        self.assertEqual(estimate.remaining, ())
        self.assertIs(estimate.to_criterion_result().return_class, ReturnClass.UNKNOWN_MEASURABLE)

    def test_inseparable_remaining_set_is_unknown(self):
        lib = load_library({"schema_version": "1.0", "probes": [
            probe_dict("p", ["a", "b"], {"a": ["F1"], "b": ["F2"]},
                       calibration=clean_calibration({"a": ["F1"], "b": ["F2"]}))]})
        session = FrameProbeSession(lib, frames=["F1", "F2", "F3", "F4"])
        session.observe("p", ["a"])
        self.assertEqual(session.remaining, ("F1", "F3", "F4"))
        estimate = session.result()
        self.assertIs(estimate.outcome, SessionOutcome.UNKNOWN_MEASURABLE)
        self.assertIn("no valid probe separates", estimate.rule)

    def test_probe_budget_blocks(self):
        answers = {"p5": ["k"], "p1": ["b"], "p2": ["c"]}
        estimate = run_session(library(), lambda probe: answers[probe.id], max_probes=1)
        self.assertIs(estimate.outcome, SessionOutcome.BLOCKED)
        self.assertEqual(estimate.blocker, PROBE_BUDGET)
        self.assertEqual(len(estimate.probes_spent), 1)
        self.assertEqual(estimate.remaining, ("F3", "F4"))

    def test_no_valid_probe_blocks(self):
        lib = [library()[2], library()[3]]
        estimate = FrameProbeSession(lib, frames=["F1", "F2"]).result()
        self.assertIs(estimate.outcome, SessionOutcome.BLOCKED)
        self.assertEqual(estimate.blocker, "no_valid_probe")

    def test_run_session_confirms(self):
        answers = {"p1": ["b"], "p2": ["c"], "p5": ["k"]}
        estimate = run_session(library(), lambda probe: answers[probe.id])
        self.assertIs(estimate.outcome, SessionOutcome.CONFIRMED)
        self.assertEqual(estimate.frame, "F3")

    def test_empty_library_is_refused(self):
        with self.assertRaises(ValueError):
            FrameProbeSession([])


class IdentityTests(unittest.TestCase):
    def test_instrument_pattern_attaches_open_untested_null_set(self):
        reading = grade_identity(IdentityObservations("low", "low", "low"))
        self.assertIs(reading.model, IdentityModel.INSTRUMENT)
        branches = reading.null_branch_set.branches
        self.assertGreaterEqual(len(branches), 4)
        self.assertTrue(all(b.status is BranchStatus.OPEN for b in branches))
        self.assertTrue(all(UNTESTED in b.discriminator for b in branches))
        self.assertEqual(len({b.origin_pattern for b in branches}), 1)
        self.assertIn("do not search", reading.rule)
        json.dumps(reading.to_dict())

    def test_fixed_position_pattern(self):
        reading = grade_identity(IdentityObservations(Grade.HIGH, Grade.HIGH, Grade.HIGH))
        self.assertIs(reading.model, IdentityModel.FIXED_POSITION)
        ids = [b.id for b in reading.null_branch_set.branches]
        self.assertIn("role_constraint", ids)
        self.assertIn("real_conflict", ids)

    def test_mixed_or_missing_is_unknown_and_has_no_null_set(self):
        for grades in (("high", "low", "low"), ("low", "unobserved", "low")):
            reading = grade_identity(IdentityObservations(*grades))
            self.assertIs(reading.model, IdentityModel.UNKNOWN_MEASURABLE)
            self.assertIsNone(reading.null_branch_set)
        with self.assertRaises(ValueError):
            identity_null_branch_set(IdentityModel.UNKNOWN_MEASURABLE)

    def test_no_interior_source(self):
        with self.assertRaises(ValueError):
            IdentityObservations("low", "low", "low", source="self_report")

    def test_known_failure_returns_wrong_instrument_not_absence(self):
        reading = grade_identity(IdentityObservations("low", "low", "low"))
        result = underlying_position(reading)
        self.assertIs(result.return_class, ReturnClass.OUT_OF_ENVELOPE)
        self.assertTrue(result.note.startswith(WRONG_INSTRUMENT))
        for label in ("evasion", "Inconsistency", "masking"):
            guarded = label_reading(reading, label)
            self.assertIs(guarded.return_class, ReturnClass.OUT_OF_ENVELOPE)
            self.assertIn(INSTRUMENT_MISREAD.name, guarded.note)
        self.assertIs(label_reading(reading, "curious").return_class, ReturnClass.UNKNOWN_MEASURABLE)
        fixed = grade_identity(IdentityObservations("high", "high", "high"))
        self.assertIs(underlying_position(fixed).return_class, ReturnClass.UNKNOWN_MEASURABLE)
        self.assertIs(label_reading(fixed, "evasion").return_class, ReturnClass.UNKNOWN_MEASURABLE)
        self.assertEqual(KNOWN_FAILURES[0].correct_return, WRONG_INSTRUMENT)
        self.assertIn("ABSENCE", KNOWN_FAILURES[0].same_shape_as)


class TermBranchTests(unittest.TestCase):
    def test_n_senses_is_n_branches_with_one_origin(self):
        probe = library()[4]
        branch_set = term_branch_set(probe)
        self.assertEqual(len(branch_set.branches), 3)
        self.assertEqual({b.origin_pattern for b in branch_set.branches}, {probe.term_or_phrase})
        self.assertEqual({b.suppression_cause for b in branch_set.branches}, {SuppressionCause.PRIOR})
        self.assertEqual(type(branch_set).load(branch_set.serialize()), branch_set)

    def test_intake_priority_rises_with_sense_count(self):
        queue = term_intake_queue(library())
        self.assertEqual(queue[0].probe_id, "p5")
        self.assertEqual(queue[0].priority, 3)
        self.assertEqual([item.priority for item in queue], [3, 2, 2, 2, 2])
        self.assertEqual([item.probe_id for item in queue[1:]], ["p1", "p2", "p3", "p4"])
        json.dumps(queue[0].to_dict())


class CouplingTests(unittest.TestCase):
    def test_seed_entry_and_checked_in_record(self):
        self.assertEqual(SEED_COUPLING_ENTRY.model, "GPT")
        self.assertIs(SEED_COUPLING_ENTRY.reading, CollapseReading.HELD)
        self.assertEqual(SEED_COUPLING_ENTRY.update_boundary, "2026-09-07")
        record = Path(__file__).resolve().parent.parent / "coupling_record.json"
        log = CouplingLog.load(record)
        self.assertEqual(log.latest("GPT"), SEED_COUPLING_ENTRY)

    def test_one_entry_per_model_boundary_term(self):
        log = CouplingLog([SEED_COUPLING_ENTRY])
        with self.assertRaises(ValueError):
            log.add(CouplingEntry("GPT", "2026-09-07", "2026-09-08", "held"))
        log.add(CouplingEntry("GPT", "2026-10-01", "2026-10-01", "collapsed", term="bank", observed=("river",)))
        self.assertEqual(log.latest("GPT").update_boundary, "2026-10-01")
        self.assertEqual(len(log.for_model("GPT")), 2)
        self.assertIsNone(log.latest("other"))
        restored = CouplingLog.load(log.serialize())
        self.assertEqual(restored, log)
        with self.assertRaises(ValueError):
            CouplingLog.from_dict({"schema_version": "9", "entries": []})


class CliTests(unittest.TestCase):
    def _library_path(self, directory):
        path = Path(directory) / "lib.json"
        path.write_text(json.dumps({"schema_version": "1.0", "probes": [p.to_dict() for p in library()]}))
        return str(path)

    def test_gate_and_intake_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._library_path(directory)
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                self.assertEqual(main(["gate", path]), 0)
                self.assertEqual(main(["intake", path]), 0)
            text = buffer.getvalue()
            self.assertIn("contaminated", text)
            self.assertIn("priority=3", text)

    def test_identity_and_coupling_commands(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(main(["identity", "--boundary-cost", "low", "--defended", "low", "--conflict", "low"]), 0)
            record = str(Path(__file__).resolve().parent.parent / "coupling_record.json")
            self.assertEqual(main(["coupling", record]), 0)
        text = buffer.getvalue()
        self.assertIn('"instrument"', text)
        self.assertIn("GPT", text)


if __name__ == "__main__":
    unittest.main()
