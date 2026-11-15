"""Tests for de_weld.py. Fixtures are synthetic; the seeds are CONSTRUCTED."""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import de_weld as D  # noqa: E402
import de_weld_seeds as S  # noqa: E402

A = D.Axis


def inp(*axes, **kw):
    return D.Input(term=kw.pop("term", "t"), sentence=kw.pop("sentence", "s."), axes=axes, **kw)


class Classify(unittest.TestCase):
    def test_four_classes_and_unclassified(self):
        cases = [
            (inp(D.AxisClaim(A.QUALITY, "q")), D.TermClass.THIN),
            (inp(D.AxisClaim(A.DESCRIPTIVE, "d"), D.AxisClaim(A.HARM, "h")), D.TermClass.THICK),
            (inp(D.AxisClaim(A.DESCRIPTIVE, "d")), D.TermClass.DESCRIPTIVE),
            (inp(D.AxisClaim(A.DESCRIPTIVE, "d"), context_valuation="said with contempt"),
             D.TermClass.VALUE_ASSOCIATED),
            (inp(D.AxisClaim(A.MORAL, None)), D.TermClass.UNCLASSIFIED),
            (inp(), D.TermClass.UNCLASSIFIED),
        ]
        for i, want in cases:
            tc, rule = D.classify(i)
            self.assertEqual(tc, want)
            self.assertTrue(rule)

    def test_term_string_reaches_no_classification(self):
        axes = (D.AxisClaim(A.DESCRIPTIVE, "d"), D.AxisClaim(A.QUALITY, "q"))
        base = D.de_weld(inp(*axes, term="safe")).to_dict()
        for t in ("good", "x", "neutral", "é"):
            other = D.de_weld(inp(*axes, term=t)).to_dict()
            other["input"]["term"] = "safe"
            self.assertEqual(other, base)


class CrossAxis(unittest.TestCase):
    def test_every_pair_reported_undeclared_never_defaulted(self):
        i = inp(D.AxisClaim(A.DESCRIPTIVE, "d"), D.AxisClaim(A.QUALITY, "q"),
                D.AxisClaim(A.HARM, "h"),
                couplings=(D.Coupling(2, 0, D.Relation.CONFLICTING),))
        rel = {(c["a"], c["b"]): c["relation"] for c in D.cross_axis(i)}
        self.assertEqual(rel, {(0, 1): "undeclared", (0, 2): "conflicting", (1, 2): "undeclared"})

    def test_undeclared_cannot_be_declared_and_bad_indices_refused(self):
        with self.assertRaises(ValueError):
            D.Coupling(0, 1, D.Relation.UNDECLARED)
        with self.assertRaises(ValueError):
            D.Coupling(1, 1, D.Relation.COUPLED)
        with self.assertRaises(ValueError):
            inp(D.AxisClaim(A.QUALITY, "q"), couplings=(D.Coupling(0, 3, D.Relation.COUPLED),))


class Flag(unittest.TestCase):
    def test_thin_in_judgment_flags(self):
        r = D.de_weld(inp(D.AxisClaim(A.QUALITY, "q"), used_in_judgment=True))
        self.assertEqual(r.flags, (D.Flag.UNGROUNDED_EVALUATION,))

    def test_thin_not_stated_or_not_judgment_does_not_flag(self):
        for u in (None, False):
            r = D.de_weld(inp(D.AxisClaim(A.QUALITY, "q"), used_in_judgment=u))
            self.assertEqual(r.flags, ())
            self.assertTrue(r.flag_rule)

    def test_thick_never_flags_but_evidence_is_reported(self):
        r = D.de_weld(inp(D.AxisClaim(A.DESCRIPTIVE, "d"), D.AxisClaim(A.QUALITY, "q"),
                          used_in_judgment=True))
        self.assertEqual(r.flags, ())
        self.assertEqual(r.descriptive_evidence, "VOID")
        r2 = D.de_weld(inp(D.AxisClaim(A.DESCRIPTIVE, "d", evidence="load test 2026"),
                           D.AxisClaim(A.QUALITY, "q")))
        self.assertEqual(r2.descriptive_evidence, "PRESENT")


class Slots(unittest.TestCase):
    def test_void_kept_and_listed(self):
        i = inp(D.AxisClaim(A.OTHER, None), sentence=None,
                residue=(D.Residue("open?"),))
        r = D.de_weld(i)
        for s in ("sentence", "used_in_judgment", "axes[0](other:(void)).claim",
                  "axes[0](other:(void)).other_name", "residue[0].needs",
                  "residue[0].contested_as_of"):
            self.assertIn(s, r.void_slots)
        self.assertEqual(r.to_dict()["input"]["axes"][0]["claim"], None)

    def test_roundtrip_and_tampered_derivation_refused(self):
        for seed in S.SEEDS:
            d = D.de_weld(seed).to_dict()
            self.assertEqual(D.DeWeld.from_dict(json.loads(json.dumps(d))).to_dict(), d)
        d = D.de_weld(S.SEEDS[0]).to_dict()
        d["term_class"] = "descriptive"
        with self.assertRaises(ValueError):
            D.DeWeld.from_dict(d)
        with self.assertRaises(ValueError):
            D.Input.from_dict({"term": "t", "sentence": "s", "colour": "red"})

    def test_other_name_only_on_other(self):
        with self.assertRaises(ValueError):
            D.AxisClaim(A.QUALITY, "q", other_name="x")


class Seeds(unittest.TestCase):
    def test_seed_terms_and_readings(self):
        got = {s.term: D.de_weld(s) for s in S.SEEDS}
        self.assertEqual(set(got), {"good weapon", "artist", "efficient", "neutral", "safe"})
        self.assertEqual(got["neutral"].term_class, D.TermClass.THIN)
        self.assertEqual(got["neutral"].flags, (D.Flag.UNGROUNDED_EVALUATION,))
        for t in ("good weapon", "artist", "efficient", "safe"):
            self.assertEqual(got[t].term_class, D.TermClass.THICK, t)
        for s in S.SEEDS:
            self.assertIn("CONSTRUCTED", s.provenance)

    def test_script_path_matches_import_path(self):
        out = subprocess.run([sys.executable, os.path.join(ROOT, "de_weld.py"), "seeds"],
                             capture_output=True, text=True, cwd=ROOT, check=True).stdout
        self.assertEqual(out.count("class: thick"), 4)
        self.assertEqual(out.count("class: thin "), 1)
        rc = subprocess.run([sys.executable, os.path.join(ROOT, "de_weld.py"), "--selftest"],
                            capture_output=True, text=True, cwd=ROOT).returncode
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
