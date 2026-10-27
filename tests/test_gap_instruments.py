"""Tests for gap_instruments.py (method-layer form). F1-F8 mirror the
fixes marked in the Simulators working copy."""
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gap_instruments as G  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _full_axes(status=G.Status.MEASURED):
    return {a: G.Evidence("v", status, "src", "", "+/- 1") for a in G.AXES}


class EvidenceTests(unittest.TestCase):
    def test_unknown_status_raises(self):
        with self.assertRaises(ValueError):
            G.Evidence("x", "TRUE")

    def test_measured_needs_source_and_uncertainty(self):
        issues = G.Evidence("x", "MEASURED").validate("e")
        self.assertIn("e: MEASURED but no source", issues)
        self.assertIn("e: MEASURED but uncertainty not stated", issues)

    def test_unknown_needs_nothing(self):
        self.assertEqual(G.Evidence("x", "UNKNOWN").validate("e"), ())

    def test_frozen(self):
        with self.assertRaises(Exception):
            G.Evidence().status = G.Status.MEASURED


class CoordinationTests(unittest.TestCase):
    def test_complete_record_is_clean(self):
        s = G.CoordinationSystem("n", "bridge X, 1990-2000", _full_axes())
        self.assertEqual(s.validate(), ())

    def test_F3_axis_typo_reported(self):
        axes = _full_axes()
        axes["ancor"] = axes.pop("anchor")
        issues = G.CoordinationSystem("n", "x 1990", axes).validate()
        self.assertIn("axis not in AXES: ancor", issues)
        self.assertIn("axis missing: anchor", issues)

    def test_F4_not_recorded_in_denominator(self):
        s = G.CoordinationSystem("n", "x 1990",
                                 {"anchor": G.Evidence("v", "MEASURED", "s", "", "1")})
        summ = G.gap_summary(s)
        self.assertEqual(summ["NOT_RECORDED"], 4)
        self.assertEqual(summ["GAP"], 2)               # observability evidence
        self.assertAlmostEqual(summ["filled_fraction"], round(1 / 7, 3))

    def test_empty_record_fraction_is_none_not_zero(self):
        self.assertIsNone(G.gap_summary(G.Abstention(
            "d", "a", "p", "deferred", "x"))["filled_fraction"])

    def test_blank_instance_reported(self):
        issues = G.CoordinationSystem("n", "specify country", _full_axes()).validate()
        self.assertIn("instance_of unspecified: label without dated instance", issues)

    def test_template_all_gap(self):
        t = G.question_template("c")
        self.assertTrue(all(e.status is G.Status.GAP for e in t.axes.values()))


class ObservabilityTests(unittest.TestCase):
    def test_counts(self):
        o = G.Observability(10, 4, 5)
        self.assertEqual(o.unevaluated_fraction(), 0.6)
        self.assertIn("observability: verified > evaluated", o.validate())

    def test_unknown_count_is_none(self):
        self.assertIsNone(G.Observability().unevaluated_fraction())

    def test_negative_count_raises(self):
        with self.assertRaises(ValueError):
            G.Observability(outputs_total=-1)

    def test_not_independent_needs_shared_modes(self):
        o = G.Observability(evaluator_independent_of_generator="NO")
        self.assertTrue(any("shared failure modes" in i for i in o.validate()))


class OtherRecordTests(unittest.TestCase):
    def test_F5_stray_tested_explanation(self):
        d = G.DiscrepancyRecord("d1", "l1", candidate_explanations=["a"],
                                tested_explanations=["a", "b"])
        self.assertIn("tested explanation not among candidates: 'b'", d.validate())

    def test_F6_replace_placeholder_unspecified(self):
        r = G.PhysicalLimitRecord("r", "replace: hardware", "ok", "temperature")
        self.assertIn("system_instance unspecified", r.validate())

    def test_F7_empty_label(self):
        self.assertIn("instance change: label missing",
                      G.InstanceChange("", "1979", "c").validate())

    def test_F2_abstention_type_checked(self):
        with self.assertRaises(ValueError):
            G.Abstention("d", "a", "p", "made_up", "x")

    def test_F1_empty_counts_as_not_reasoned(self):
        a = G.Abstention("d", "a", "p", "deferred", "x", "", "   ")
        self.assertEqual(len(a.validate()), 2)

    def test_filled_abstention_clean(self):
        a = G.Abstention("d", "a", "p", "deferred", "x",
                         "a missed signal", "next audit 2027-01")
        self.assertEqual(a.validate(), ())

    def test_handling_checked_without_evidence(self):
        h = G.DiscrepancyHandling("h", "d", outcome_independently_checked="YES")
        self.assertIn("outcome marked checked but outcome_evidence is GAP", h.validate())


class RoundTripTests(unittest.TestCase):
    def test_round_trip_every_record(self):
        recs = [
            G.CoordinationSystem("n", "x 1990", _full_axes(), G.Observability(3, 2),
                                 ("note",)),
            G.PhysicalLimitRecord("r", "hw", "load", "temp", sensor_availability="AVAILABLE"),
            G.DiscrepancyRecord("d", "r", candidate_explanations=["a"]),
            G.DiscrepancyHandling("h", "d"),
            G.InstanceChange("lab", "1979", "c"),
            G.Abstention("d", "a", "p", "did_not_reach", "x"),
        ]
        for r in recs:
            self.assertEqual(G.from_dict(type(r), G.to_dict(r)), r)

    def test_unknown_key_refused(self):
        with self.assertRaises(ValueError):
            G.from_dict(G.Evidence, {"value": "x", "colour": "red"})


class CliTests(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, os.path.join(ROOT, "gap_instruments.py"), *args],
                              capture_output=True, text=True)

    def test_F8_claim_without_text_exits_2(self):
        self.assertEqual(self._run("--claim").returncode, 2)
        self.assertEqual(self._run("--claim", "  ").returncode, 2)

    def test_claim_prints_template(self):
        p = self._run("--claim", "x")
        self.assertEqual(p.returncode, 0)
        self.assertIn("verdict: NOT ASSIGNED", p.stdout)


class CopyTests(unittest.TestCase):
    def test_tools_copy_runs_its_selftest(self):
        p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "gap_instruments.py"),
                            "--selftest"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("selftest ok", p.stdout)


if __name__ == "__main__":
    unittest.main()
