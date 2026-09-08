"""register_map regression set from WORK ORDER M, plus mechanics.

Every layer here is a TEST FIXTURE.  Names such as Astra, Opus, Sol and the
numbers attached to them are fixture labels taken from the work order, not
measurements of anything.  Harness names ("provider adapter", "standard
harness") and task sets ("ARC-AGI-3 task set") in cases 1 and 2 are
CONSTRUCTED for the regression set, not records of any real run.
"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "premise-traceability"))

from register_map import (  # noqa: E402
    UNDECLARED,
    Blank,
    Discard,
    FlagCode,
    Grade,
    JoinVerdict,
    Layer,
    LayerDeclarationError,
    ProjectionError,
    can_join,
    load_layer,
    main,
    project,
)


def fixture(**over):
    base = {
        "name": "FIXTURE",
        "measurand": "fixture score",
        "range": "fixture task set",
        "instrument": "fixture harness",
        "grade": "MEASURED_PRESENT",
        "resolution": 1,
        "cells": {},
    }
    base.update(over)
    return base


class RegressionSet(unittest.TestCase):
    def test_1_astra_vs_opus_incommensurable_instrument(self):
        astra = load_layer(fixture(name="FIXTURE Astra", measurand="ARC-AGI-3 score",
                                   range="ARC-AGI-3 task set", instrument="provider adapter",
                                   cells={"0": 99.9}))
        opus = load_layer(fixture(name="FIXTURE Opus", measurand="ARC-AGI-3 score",
                                  range="ARC-AGI-3 task set", instrument="standard harness",
                                  cells={"0": 30.2}))
        result = can_join(astra, opus)
        self.assertIs(result.verdict, JoinVerdict.INCOMMENSURABLE)
        self.assertEqual(result.field, "instrument")
        self.assertTrue(result.instrument_checked)
        self.assertEqual(result.comparisons, {"measurand": "match", "range": "match",
                                              "grade": "match", "instrument": "differ"})
        self.assertIn("datum offset", result.rule)

    def test_2_opus_vs_sol_same_harness_commensurable(self):
        opus = load_layer(fixture(name="FIXTURE Opus", instrument="standard harness", cells={"0": 30.2}))
        sol = load_layer(fixture(name="FIXTURE Sol", instrument="standard harness", cells={"0": 7.8}))
        result = can_join(opus, sol)
        self.assertIs(result.verdict, JoinVerdict.COMMENSURABLE)
        self.assertIsNone(result.field)
        self.assertTrue(result.resolution_match)

    def test_3_collider_trigger_no_menu_loads_with_flag(self):
        layer = load_layer(fixture(name="FIXTURE collider trigger output",
                                   measurand="events passing trigger", range="one run",
                                   instrument="detector + trigger + reconstruction",
                                   grade="MEASURED_DISCARDED"))
        self.assertIs(layer.grade, Grade.MEASURED_DISCARDED)
        codes = [f.code for f in layer.flags]
        self.assertEqual(codes, [FlagCode.DISCARD_RULE_UNDECLARED])
        self.assertIn("Worse than UNMEASURED", layer.flags[0].rule)
        # with the menu declared, no flag
        declared = load_layer(fixture(grade="MEASURED_DISCARDED", discard_rule="trigger menu v3"))
        self.assertEqual(declared.flags, ())

    def test_4_microscopic_reversibility_imposed_range_undeclared(self):
        layer = load_layer(fixture(name="FIXTURE microscopic reversibility",
                                   measurand="detailed balance holds", range=UNDECLARED,
                                   instrument="model constraint", grade="IMPOSED",
                                   reason="identifiability of rate constants"))
        self.assertIs(layer.grade, Grade.IMPOSED)
        self.assertEqual(layer.undeclared_fields, ("range",))
        self.assertEqual(layer.flags, ())
        # without a reason the second mandatory field is flagged
        bare = load_layer(fixture(grade="IMPOSED"))
        self.assertEqual([f.code for f in bare.flags], [FlagCode.REASON_UNDECLARED])

    def test_5_laws_time_symmetric_undeclared_range(self):
        claim = load_layer(fixture(name="FIXTURE 'laws are time-symmetric'",
                                   measurand="T symmetry", range=UNDECLARED,
                                   instrument="inspection of written equations"))
        weak = load_layer(fixture(name="FIXTURE weak sector", measurand="T symmetry",
                                  range="weak interaction", instrument="B meson entanglement"))
        result = can_join(claim, weak)
        self.assertIs(result.verdict, JoinVerdict.UNDECLARED)
        self.assertEqual(result.field, "range")
        # the full table is still there: instrument was checked and differs
        self.assertEqual(result.comparisons["instrument"], "differ")
        self.assertTrue(result.instrument_checked)

    def test_6_edm_limit_vs_quantum_gravity_incommensurable_grade(self):
        edm = load_layer(fixture(name="FIXTURE nEDM", measurand="T violation", range="T symmetry sector",
                                 instrument="neutron EDM search", grade="MEASURED_ABSENT"))
        qg = load_layer(fixture(name="FIXTURE gravity", measurand="T violation", range="T symmetry sector",
                                instrument="neutron EDM search", grade="UNMEASURED"))
        result = can_join(edm, qg)
        self.assertIs(result.verdict, JoinVerdict.INCOMMENSURABLE)
        self.assertEqual(result.field, "grade")
        self.assertIn("MEASURED_ABSENT", result.rule)
        self.assertIn("UNMEASURED", result.rule)

    def test_7_project_coarser_carries_discarded_with_rule(self):
        layer = load_layer(fixture(resolution=1, cells={"0": 1, "1": 2, "2": "NODATA", "3": "NOTFOUND",
                                                        "4": "NODATA", "5": "NODATA", "6": "NOTFOUND", "7": "NODATA"}))
        out = project(layer, 2)
        self.assertIs(out.grade, Grade.MEASURED_DISCARDED)
        self.assertIsNotNone(out.discard_rule)
        self.assertIn("coarsen x2", out.discard_rule)
        self.assertIn("source grade MEASURED_PRESENT", out.discard_rule)
        self.assertEqual(out.resolution, 2)
        # kept values by declared precedence; blanks survive as values
        self.assertEqual(out.cells, {(0,): 1, (1,): Blank.NOTFOUND, (2,): Blank.NODATA, (3,): Blank.NOTFOUND})
        # every drop retrievable with its rule attached
        self.assertEqual(len(out.discards), 4)
        dropped = {(d.source_cell, d.value) for d in out.discards}
        self.assertEqual(dropped, {((1,), 2), ((2,), Blank.NODATA), ((5,), Blank.NODATA), ((7,), Blank.NODATA)})
        for d in out.discards:
            self.assertIn("coarsen x2", d.rule)
            self.assertIn("kept:", d.rule)
        self.assertEqual(out.flags, ())

    def test_8_missing_resolution_raises_naming_it(self):
        data = fixture()
        del data["resolution"]
        with self.assertRaises(LayerDeclarationError) as ctx:
            load_layer(data)
        self.assertEqual(ctx.exception.missing, ("resolution",))
        self.assertIn("resolution", str(ctx.exception))


class Mechanics(unittest.TestCase):
    def test_error_names_every_missing_field(self):
        with self.assertRaises(LayerDeclarationError) as ctx:
            load_layer({"name": "FIXTURE"})
        self.assertEqual(ctx.exception.missing, ("measurand", "range", "instrument", "grade", "resolution"))
        with self.assertRaises(LayerDeclarationError) as ctx:
            load_layer(fixture(range=None, resolution=""))
        self.assertEqual(ctx.exception.missing, ("range", "resolution"))

    def test_blanks_are_values_not_none(self):
        layer = load_layer(fixture(cells={"0": "NODATA", "1": "NOTFOUND", "2": 0}))
        self.assertIs(layer.cells[(0,)], Blank.NODATA)
        self.assertIs(layer.cells[(1,)], Blank.NOTFOUND)
        self.assertEqual(layer.cells[(2,)], 0)
        self.assertEqual(layer.cells_with(Blank.NODATA), ((0,),))
        self.assertEqual(layer.cells_with(Blank.NOTFOUND), ((1,),))
        with self.assertRaises(ValueError):
            load_layer(fixture(cells={"0": None}))
        rendered = layer.format()
        self.assertIn("0          \n", rendered + "\n")   # NODATA renders blank
        self.assertIn("1          -", rendered)             # NOTFOUND renders '-'

    def test_project_refuses_upsample_and_non_integer_factor(self):
        layer = load_layer(fixture(resolution=2, cells={"0": 1}))
        with self.assertRaises(ProjectionError):
            project(layer, 1)
        with self.assertRaises(ProjectionError):
            project(layer, 2)
        with self.assertRaises(ProjectionError):
            project(layer, 3)
        with self.assertRaises(ProjectionError):
            project(load_layer(fixture(resolution=UNDECLARED)), 4)

    def test_project_twice_accumulates_discards_and_2d(self):
        layer = load_layer(fixture(cells={"0,0": "a", "0,1": "b", "1,0": "NODATA", "1,1": "NOTFOUND",
                                          "2,2": "c", "3,3": "d"}))
        once = project(layer, 2)
        self.assertEqual(once.cells, {(0, 0): "a", (1, 1): "c"})
        self.assertEqual(len(once.discards), 4)
        twice = project(once, 4)
        self.assertEqual(twice.cells, {(0, 0): "a"})
        self.assertEqual(len(twice.discards), 5)   # earlier discards retained
        self.assertIn("coarsen x2: 2 -> 4", twice.discard_rule)

    def test_round_trip(self):
        layer = project(load_layer(fixture(cells={"0": 1, "1": "NODATA"})), 2)
        data = layer.to_dict()
        again = load_layer({k: v for k, v in data.items() if k not in ("undeclared_fields", "flags")})
        self.assertEqual(again.cells, layer.cells)
        self.assertEqual(again.discards, layer.discards)
        self.assertEqual(again.grade, layer.grade)
        json.dumps(data)   # serialisable, blanks as strings
        self.assertEqual(data["cells"]["0"], 1)
        self.assertEqual(data["discards"][0]["value"], "NODATA")

    def test_undeclared_and_incommensurable_do_not_collapse(self):
        a = load_layer(fixture(range=UNDECLARED, instrument="x"))
        b = load_layer(fixture(range="r", instrument="y"))
        r = can_join(a, b)
        self.assertIs(r.verdict, JoinVerdict.UNDECLARED)
        self.assertEqual(r.field, "range")
        self.assertEqual(r.comparisons["instrument"], "differ")   # not hidden by the early block
        c = load_layer(fixture(range="q", instrument="x"))
        self.assertIs(can_join(c, b).verdict, JoinVerdict.INCOMMENSURABLE)
        self.assertEqual(can_join(c, b).field, "range")

    def test_join_order_instrument_last(self):
        a = load_layer(fixture(grade="MEASURED_PRESENT", instrument="x"))
        b = load_layer(fixture(grade="UNMEASURED", instrument="y"))
        r = can_join(a, b)
        self.assertEqual(r.field, "grade")               # grade blocks before instrument
        self.assertEqual(r.comparisons["instrument"], "differ")
        self.assertIn("instrument checked last", r.rule)

    def test_unknown_field_and_bad_grade_refused(self):
        with self.assertRaises(ValueError):
            load_layer(fixture(colour="blue"))
        with self.assertRaises(ValueError):
            load_layer(fixture(grade="PLAUSIBLE"))
        with self.assertRaises(ValueError):
            load_layer(fixture(resolution=-1))

    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            a = Path(d, "a.json"); b = Path(d, "b.json"); bad = Path(d, "bad.json")
            a.write_text(json.dumps(fixture(instrument="h1", cells={"0": 1, "1": 2})))
            b.write_text(json.dumps(fixture(instrument="h2")))
            bad.write_text(json.dumps({"name": "FIXTURE"}))
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(["join", str(a), str(b), "--json"]), 0)
            self.assertEqual(json.loads(out.getvalue())["field"], "instrument")
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(["project", str(a), "--to", "2", "--json"]), 0)
            self.assertEqual(json.loads(out.getvalue())["grade"], "MEASURED_DISCARDED")
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(["load", str(a)]), 0)
            self.assertIn("LAYER FIXTURE", out.getvalue())
            err = io.StringIO()
            with redirect_stderr(err):
                self.assertEqual(main(["load", str(bad)]), 2)
            self.assertIn("resolution", err.getvalue())


if __name__ == "__main__":
    unittest.main()
