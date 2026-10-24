"""Tests for the reasoning layer.  Synthetic fixtures only (labelled as such);
no repository clone, no network.  Run from the repository root:

    python3 -m unittest discover -s reasoning-layer/tests -v
"""

import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import generate  # noqa: E402
import rl_common as rl  # noqa: E402
import run_examples  # noqa: E402
import validate  # noqa: E402

SIM_HEAD = "a" * 40
ML_HEAD = "b" * 40

# FIXTURE: synthetic tool bytes; not repository content.
TOOL_A = b'"""Fixture tool A.\n\nSecond paragraph."""\nimport sys\nimport helper\n\nif __name__ == "__main__":\n    print("a")\n'
HELPER = b'"""Fixture helper module."""\nX = 1\n'
SELFTEST = b'"""Fixture selftest."""\nprint("selftest ok")\n'
SHARED = b'"""Fixture shared tool."""\nimport argparse\np = argparse.ArgumentParser()\np.add_argument("--selftest", action="store_true", help="run checks")\nif __name__ == "__main__":\n    p.parse_args()\n'
DIFF_SIM = b'"""Fixture differing, sim side."""\n'
DIFF_ML = b'"""Fixture differing, ml side."""\n'
DOC = b"# Fixture doc\n\nFirst paragraph of the fixture doc.\n\nSecond.\n"
TEST_MOD = b"import unittest\n"
DANGER = b'"""Fixture danger."""\nimport shutil\nif __name__ == "__main__":\n    shutil.rmtree("x")\n'


def _row(path, data, date="2026-10-01"):
    return "%s | %d | %d | %s | %s" % (path, data.count(b"\n"), len(data), generate.sha12(data), date)


def fixture(sim_override=None):
    sim = {
        "proj/tool_a.py": TOOL_A,
        "proj/helper.py": HELPER,
        "proj/selftest.py": SELFTEST,
        "proj/danger.py": DANGER,
        "tools/shared.py": SHARED,
        "tools/diff.py": DIFF_SIM,
        "tools/bin_self_test.md": DOC,
        "tests/test_shared.py": TEST_MOD,
        "proj/__init__.py": b"",
    }
    if sim_override:
        sim.update(sim_override)
    ml = {
        "tools/shared.py": SHARED,
        "tools/diff.py": DIFF_ML,
        "tools/bin_self_test.md": DOC,
        "root_tool.py": TOOL_A,
    }
    lines = ["INVENTORY fixture", "Simulators main: aaaaaaa", "method-layer main: bbbbbbb", "",
             "########## Simulators  (%d files) ##########" % len(sim), "", "--- proj/  (n files) ---"]
    hist_sim = {k: v for k, v in sim.items() if k != "proj/danger.py"}
    for p in sorted(hist_sim):
        lines.append(_row(p, hist_sim[p]))
    lines += ["", "########## method-layer  (%d files) ##########" % len(ml), ""]
    for p in sorted(ml):
        lines.append(_row(p, ml[p]))
    lines += ["", "=== ADDENDUM fixture ===",
              "Simulators main: " + SIM_HEAD, "method-layer main: " + ML_HEAD, "",
              "########## NEW IN Simulators: 1 paths; current tracked files 9 ##########",
              "--- New non-test Python source programs (1) ---",
              _row("proj/danger.py", DANGER, "2026-10-14"),
              "--- Existing paths with changed bytes (0); earlier rows retained ---",
              "--- Historical paths absent from current snapshot (1); historical records retained ---",
              "gone/old.py", "",
              "########## NEW IN method-layer: 0 paths; current tracked files 4 ##########",
              "--- Historical paths absent from current snapshot (0); historical records retained ---",
              "(none)", ""]
    return "\n".join(lines) + "\n", {"Simulators": sim, "method-layer": ml}


class Workspace:
    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="rl-test-"))
        shutil.copytree(HERE / "schema", self.dir / "schema")

    def build(self, text, snaps, check=False):
        l3 = rl.parse_inventory(text)
        rep, changed = generate.build(l3, snaps, self.dir / "cards", self.dir / "APPARATUS.yaml",
                                      self.dir / "READ_FIRST.md", check)
        return l3, rep, changed

    def card(self, cid):
        return rl.read_yaml(rl.card_path(cid, self.dir / "cards"))

    def put(self, card):
        rl.write_card(card, self.dir / "cards")

    def checks(self, l3):
        return {c.name: c for c in validate.validate(self.dir, l3, [])}

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class YamlSubset(unittest.TestCase):
    def test_roundtrip_seeded(self):
        rng = random.Random(7)
        alphabet = "ab: #-'\"\n\t\\|>{}[],0123456789é→ "
        for _ in range(400):
            s = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 30)))
            obj = {"k": s, "lst": [s, {"x": s, "y": [s]}], "n": None, "b": True, "i": 3, "e": [], "d": {}}
            self.assertEqual(rl.load_yaml(rl.dump_yaml(obj)), obj, repr(s))

    def test_hand_edited_forms(self):
        text = (
            "# comment\n"
            "a: plain words here\n"
            "b: 'single ''quoted'''\n"
            "c: |\n  line one\n\n  line three\n"
            "d: |-\n  no newline\n"
            "e: [x, \"y z\", 3]\n"
            "f:\n- one\n- two\n"
            "g: value # trailing comment\n"
        )
        v = rl.load_yaml(text)
        self.assertEqual(v["a"], "plain words here")
        self.assertEqual(v["b"], "single 'quoted'")
        self.assertEqual(v["c"], "line one\n\nline three\n")
        self.assertEqual(v["d"], "no newline")
        self.assertEqual(v["e"], ["x", "y z", 3])
        self.assertEqual(v["f"], ["one", "two"])
        self.assertEqual(v["g"], "value")

    def test_outside_subset_raises(self):
        for bad in ("a: {x: 1}\n", "a: [1, [2]]\n", "a: 1\na: 2\n", "a:\n\tb: 1\n"):
            with self.assertRaises(rl.YamlError, msg=bad):
                rl.load_yaml(bad)


class Layer3Parse(unittest.TestCase):
    def test_rows_heads_absent(self):
        text, _ = fixture()
        l3 = rl.parse_inventory(text)
        self.assertEqual(l3.heads, {"Simulators": SIM_HEAD, "method-layer": ML_HEAD})
        self.assertEqual(l3.row("Simulators", "proj/danger.py").source, "new")
        self.assertEqual(l3.absent["Simulators"], ["gone/old.py"])
        self.assertIsNone(l3.row("Simulators", "gone/old.py"))

    def test_metadata_disagreement_raises(self):
        text, _ = fixture()
        meta = {"new": {"Simulators": [{"path": "proj/danger.py", "sha12": "0" * 12}]}}
        with self.assertRaises(rl.Layer3Error):
            rl.parse_inventory(text, meta)

    def test_program_rule(self):
        cases = {
            "tools/fitness_bin_self_test.py": True, "x/selftest.py": True, "x/tool.py": True,
            "tests/test_x.py": False, "x/test_y.py": False, "x/tests/helper.py": False,
            "x/__init__.py": False, "x/README.md": False, "x/gate_null_test.py": True,
        }
        for path, want in cases.items():
            self.assertEqual(rl.is_program(path)[0], want, path)

    def test_pinned_copy_matches(self):
        self.assertEqual(rl.check_layer3_pin(), [])


class Generate(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()
        self.text, self.snaps = fixture()
        self.l3, self.rep, _ = self.ws.build(self.text, self.snaps)

    def tearDown(self):
        self.ws.close()

    def test_card_set(self):
        ids = sorted(p.stem for p in (self.ws.dir / "cards").glob("*.yaml"))
        self.assertEqual(ids, sorted([
            "proj--tool_a", "proj--helper", "proj--selftest", "proj--danger", "tools--shared",
            "tools--diff@sim", "tools--diff@ml", "tools--bin_self_test.md", "root_tool"]))
        self.assertEqual(self.rep.problems, 0, self.rep.lines)

    def test_identical_in_both_repos_is_one_card(self):
        c = self.ws.card("tools--shared")
        self.assertEqual([l["repo"] for l in c["integrity"]], ["Simulators", "method-layer"])
        doc = self.ws.card("tools--bin_self_test.md")
        self.assertEqual(doc["kind"], "method_document")
        self.assertEqual(len(doc["integrity"]), 2)

    def test_core_docs_come_first(self):
        ap = rl.read_yaml(self.ws.dir / "APPARATUS.yaml")["apparatus"]
        ids = [f["id"] for f in ap["faces"]]
        self.assertEqual(ids[0], "tools--bin_self_test.md")
        self.assertEqual(ids[1], "tools--shared")
        for f in rl.APPARATUS_AUTHOR_FIELDS:
            self.assertEqual(ap[f], rl.AUTHOR)

    def test_author_fields_are_placeholders(self):
        for p in (self.ws.dir / "cards").glob("*.yaml"):
            c = rl.read_yaml(p)
            for f in rl.CARD_AUTHOR_FIELDS:
                self.assertEqual(c[f], rl.AUTHOR, (p.name, f))
            for f in rl.CARD_GENERATED_FIELDS:
                self.assertTrue(rl.is_draft(c[f]), (p.name, f))

    def test_extraction(self):
        a = self.ws.card("proj--tool_a")
        self.assertEqual(a["purpose"]["value"], "Fixture tool A.")
        self.assertIn({"id": "proj--helper", "via": "imports"}, a["related"]["value"])
        self.assertEqual(a["run"]["value"], "python3 proj/tool_a.py")
        s = self.ws.card("tools--shared")
        self.assertEqual(s["run"]["value"], "python3 tools/shared.py --selftest")
        self.assertTrue(any(v.startswith("--selftest") for v in s["input"]["value"]))
        d = self.ws.card("proj--danger")
        self.assertEqual(d["run"]["safety"], ["deletes-files"])
        self.assertIsNone(self.ws.card("proj--helper")["run"]["value"])

    def test_idempotent(self):
        _, _, changed = self.ws.build(self.text, self.snaps)
        self.assertEqual(changed, 0)

    def test_author_edit_survives_rerun(self):
        c = self.ws.card("proj--tool_a")
        c["forces_step"] = "fixture author text"
        c["purpose"] = "confirmed by hand"
        self.ws.put(c)
        ap_path = self.ws.dir / "APPARATUS.yaml"
        ap = rl.read_yaml(ap_path)
        ap["apparatus"]["shape"] = "fixture shape"
        ap["apparatus"]["faces"].reverse()
        ap_path.write_text(rl.dump_yaml(ap), encoding="utf-8")
        self.ws.build(self.text, self.snaps)
        c2 = self.ws.card("proj--tool_a")
        self.assertEqual(c2["forces_step"], "fixture author text")
        self.assertEqual(c2["purpose"], "confirmed by hand")
        ap2 = rl.read_yaml(ap_path)["apparatus"]
        self.assertEqual(ap2["shape"], "fixture shape")
        self.assertEqual([f["id"] for f in ap2["faces"]], [f["id"] for f in ap["apparatus"]["faces"]])
        self.assertEqual(self.ws.checks(self.l3)["author_provenance"].fails, [])

    def test_draft_refreshes_and_stale_run_resets(self):
        c = self.ws.card("proj--tool_a")
        c["run_result"] = {"status": "RUN", "captured": "a", "date": "2026-10-24",
                           "command": "python3 proj/tool_a.py", "sha12": c["integrity"][0]["sha12"], "exit_code": 0}
        c["status"] = "RUN"
        self.ws.put(c)
        new_a = TOOL_A.replace(b"Fixture tool A.", b"Fixture tool A, edited.")
        text, snaps = fixture({"proj/tool_a.py": new_a})
        l3, rep, _ = self.ws.build(text, snaps)
        c2 = self.ws.card("proj--tool_a")
        self.assertEqual(c2["purpose"]["value"], "Fixture tool A, edited.")
        self.assertEqual(c2["run_result"]["status"], "UNRUN")
        self.assertIn("stale", c2["run_result"]["reason"])
        self.assertEqual(c2["status"], "UNRUN")

    def test_snapshot_mismatch_reported(self):
        snaps = {k: dict(v) for k, v in self.snaps.items()}
        snaps["Simulators"]["proj/helper.py"] = b"changed\n"
        rep, _ = generate.build(self.l3, snaps, self.ws.dir / "cards", self.ws.dir / "APPARATUS.yaml",
                                self.ws.dir / "READ_FIRST.md", check=True)
        self.assertTrue(any("proj/helper.py snapshot sha12" in ln for ln in rep.lines))

    def test_render_marks_gaps(self):
        text = (self.ws.dir / "READ_FIRST.md").read_text(encoding="utf-8")
        self.assertIn("## Tool selection", text)
        self.assertIn("| `tools--bin_self_test.md` | [not yet written] | [not yet written] |", text)
        self.assertIn("**forces_step:** [not yet written]", text)
        self.assertIn("**[DRAFT]**", text)
        self.assertNotIn("AUTHOR |", text)
        self.assertLess(text.index("## Shape"), text.index("## Corpus default to avoid"))
        self.assertLess(text.index("## Corpus default to avoid"), text.index("## Cards"))


class Validate(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()
        self.text, self.snaps = fixture()
        self.l3, _, _ = self.ws.build(self.text, self.snaps)

    def tearDown(self):
        self.ws.close()

    def failing(self):
        return {n: c.fails for n, c in self.ws.checks(self.l3).items() if c.fails}

    def test_fresh_passes(self):
        self.assertEqual(self.failing(), {})

    def test_sha_mismatch_fails(self):
        c = self.ws.card("proj--helper")
        c["integrity"][0]["sha12"] = "0" * 12
        self.ws.put(c)
        self.assertIn("integrity", self.failing())

    def test_missing_card_fails(self):
        rl.card_path("proj--helper", self.ws.dir / "cards").unlink()
        f = self.failing()
        self.assertIn("coverage", f)
        self.assertIn("references", f)

    def test_run_without_capture_fails(self):
        c = self.ws.card("proj--tool_a")
        c["status"] = "RUN"
        c["run_result"].update(status="RUN", captured="", date="2026-10-24")
        self.ws.put(c)
        self.assertIn("run_claim", self.failing())

    def test_status_run_without_run_result_fails(self):
        c = self.ws.card("proj--tool_a")
        c["status"] = "RUN"
        self.ws.put(c)
        self.assertIn("run_claim", self.failing())

    def test_generator_filled_author_field_fails(self):
        c = self.ws.card("proj--tool_a")
        c["wrong_read"] = "a guess"
        c["_provenance"]["written"]["wrong_read"] = rl.field_hash("a guess")
        self.ws.put(c)
        self.assertIn("author_provenance", self.failing())

    def test_human_filled_author_field_passes(self):
        c = self.ws.card("proj--tool_a")
        c["wrong_read"] = "written by hand"
        self.ws.put(c)
        self.assertEqual(self.failing(), {})

    def test_read_order_missing_card_fails(self):
        p = self.ws.dir / "APPARATUS.yaml"
        ap = rl.read_yaml(p)
        ap["apparatus"]["read_order"] = ["proj--tool_a", "no-such-card"]
        p.write_text(rl.dump_yaml(ap), encoding="utf-8")
        self.assertIn("references", self.failing())

    def test_author_gaps_reported_not_failed(self):
        gaps = self.ws.checks(self.l3)["author_gaps"]
        self.assertEqual(gaps.fails, [])
        self.assertTrue(any("6 empty -> 9 cards" in ln for ln in gaps.info))


class RunExamples(unittest.TestCase):
    def test_command_form(self):
        ok, _ = run_examples.parse_command("python3 a/b.py --selftest", ["a/b.py"])
        self.assertEqual(ok, ["a/b.py", "--selftest"])
        for bad in ("python3 other.py", "bash a/b.py", "python3 a/b.py ; rm -rf x",
                    "python3 a/b.py ../x", "python3 a/b.py /etc/passwd"):
            self.assertIsNone(run_examples.parse_command(bad, ["a/b.py"])[0], bad)

    def test_capture_head(self):
        out = "\n".join("line %d" % i for i in range(100)).encode() + b"\n" + b"x" * 500
        head, n, _ = run_examples.capture_head(out)
        lines = head.split("\n")
        self.assertEqual(n, 101)
        self.assertEqual(len(lines), rl.CAPTURE_LINES + 1)
        self.assertTrue(lines[-1].startswith("[... 61 more lines]"))

    def test_blocked_and_unrun_never_execute(self):
        text, snaps = fixture()
        ws = Workspace()
        try:
            ws.build(text, snaps)
            tree = ws.dir / "tree"
            for p, data in snaps["Simulators"].items():
                (tree / p).parent.mkdir(parents=True, exist_ok=True)
                (tree / p).write_bytes(data)
            trees = {"Simulators": tree, "method-layer": tree}
            for cid, reason in (("proj--danger", "blocked by safety scan"),
                                ("proj--helper", "no safe run command")):
                rr = run_examples.run_one(ws.card(cid), trees, "none-needed", ws.dir, 5, "2026-10-24")
                self.assertEqual(rr["status"], "UNRUN")
                self.assertIn(reason, rr["reason"])
        finally:
            ws.close()

    def test_sandboxed_run(self):
        mode = run_examples.detect_sandbox()
        if mode is None:
            self.skipTest("no network-isolating sandbox here")
        work = next((w for w in (Path(tempfile.gettempdir()), Path("/tmp"))
                     if mode != "netns+nobody" or run_examples.traversable_by_nobody(w.resolve())), None)
        if work is None:
            self.skipTest("no temp dir traversable by nobody")
        text, snaps = fixture()
        ws = Workspace()
        root = Path(tempfile.mkdtemp(prefix="rl-tree-", dir=str(work)))
        try:
            ws.build(text, snaps)
            tree = root / "t"
            tree.mkdir()
            for p, data in snaps["Simulators"].items():
                (tree / p).parent.mkdir(parents=True, exist_ok=True)
                (tree / p).write_bytes(data)
            os_tree = {"Simulators": tree, "method-layer": tree}
            homes = root / "h"
            homes.mkdir()
            homes.chmod(0o777)
            root.chmod(0o755)
            rr = run_examples.run_one(ws.card("proj--selftest"), os_tree, mode, homes, 20, "2026-10-24")
            self.assertEqual(rr["status"], "RUN", rr)
            self.assertEqual(rr["captured"], "selftest ok")
            self.assertEqual(rr["sandbox"], mode)
            # FIXTURE: a tool that writes beside itself gets a disposable copy
            (tree / "proj" / "writer.py").write_bytes(b'open("proj/out.txt", "w").write("x"); print("wrote")\n')
            card = ws.card("proj--selftest")
            card["run"]["value"] = "python3 proj/writer.py"
            card["integrity"][0]["path"] = "proj/writer.py"
            card["integrity"][0]["sha12"] = generate.sha12((tree / "proj" / "writer.py").read_bytes())
            rr = run_examples.run_one(card, os_tree, mode, homes, 20, "2026-10-24")
            self.assertEqual(rr["status"], "RUN", rr)
            self.assertFalse((tree / "proj" / "out.txt").exists())
        finally:
            shutil.rmtree(root, ignore_errors=True)
            ws.close()


if __name__ == "__main__":
    unittest.main()
