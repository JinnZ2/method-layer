#!/usr/bin/env python3
"""Build or refresh the reasoning-layer card skeletons from both repositories.

CC0.  Standard library only (plus the ``git`` executable to read snapshots).

```text
layer 3 (layer3/*.txt, pinned by layer3.sha256)
   | program set = is_program() over effective rows  + CORE_DOCS (8 shared .md)
   v
git archive <snapshot commit>  for Simulators and method-layer   (bytes, not checkouts)
   | sha256[:12] of snapshot bytes  vs  layer-3 sha12   -> mismatch REPORTED, card keeps layer 3
   | same path + same sha12 in both repos               -> ONE card, two integrity rows
   v
extract (ast, no execution): docstring | argparse / main() | imports | samples | selftest
   |                         safety scan: delete / network / credential cues -> run blocked
   v
merge with the existing card:
   AUTHOR fields      written as "AUTHOR" only when absent; never touched after
   DRAFT fields       refreshed; a field no longer marked DRAFT is left alone
   integrity          always from layer 3
   run_result         kept while bytes + command unchanged, else reset to UNRUN
   v
cards/<id>.yaml  ->  APPARATUS.yaml faces (existing order kept, new ids appended)
                 ->  READ_FIRST.md
```

Usage::

    python3 generate.py --simulators PATH --method-layer PATH
    python3 generate.py ... --check     # exit 1 if any file would change
"""

from __future__ import annotations

import argparse
import ast
import warnings
import hashlib
import io
import re
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rl_common as rl  # noqa: E402

# ---------------------------------------------------------------------------
# snapshot access
# ---------------------------------------------------------------------------

Snapshot = Dict[str, bytes]


def git_snapshot(repo_dir: Path, commit: str) -> Snapshot:
    """Every tracked file at ``commit``, read from ``git archive``."""
    proc = subprocess.run(["git", "-C", str(repo_dir), "archive", "--format=tar", commit],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise SystemExit("git archive %s in %s failed: %s" % (commit, repo_dir, proc.stderr.decode(errors="replace").strip()))
    out: Snapshot = {}
    with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as tf:
        for m in tf.getmembers():
            if m.isfile():
                f = tf.extractfile(m)
                if f is not None:
                    out[m.name] = f.read()
    return out


def sha12(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


# ---------------------------------------------------------------------------
# extraction (static; nothing is executed)
# ---------------------------------------------------------------------------

SAFETY_RULES = (
    ("deletes-files", re.compile(r"\bshutil\.rmtree\b|\bos\.(remove|unlink|rmdir|removedirs)\b|\.unlink\(|\.rmdir\(")),
    ("network", re.compile(r"^\s*(import|from)\s+(urllib\.request|urllib3|requests|http\.client|httpx|aiohttp|socket|smtplib|ftplib|paramiko)\b|\burlopen\(", re.M)),
    ("credentials", re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|secret[_-]?key|password|getpass|github_token|anthropic_api_key|openai_api_key)\b")),
)

_PATH_LIT = re.compile(r"^[\w./-]+\.(json|jsonl|csv|tsv|md|txt|yaml|yml)$")
_MD_PATH = re.compile(r"`([\w./-]+\.(?:py|md|json|jsonl|csv|txt))`")


def safety_flags(src: str) -> List[str]:
    return [name for name, rx in SAFETY_RULES if rx.search(src)]


def first_paragraph(text: str, limit: int = 600) -> str:
    para = []
    for ln in text.strip().splitlines():
        if not ln.strip():
            if para:
                break
            continue
        para.append(ln.strip())
    s = " ".join(para)
    return s if len(s) <= limit else s[: limit - 3].rstrip() + "..."


def leading_comment(src: str) -> str:
    lines = []
    for ln in src.splitlines():
        s = ln.strip()
        if s.startswith("#!") or re.match(r"#.*coding[:=]", s):
            continue
        if s.startswith("#"):
            lines.append(s.lstrip("#").strip())
        elif not s and not lines:
            continue
        else:
            break
    return first_paragraph("\n".join(lines))


def _const(node: Any) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        vals = [_const(e) for e in node.elts]
        return vals if all(v is not None for v in vals) else None
    return None


class _Scan(ast.NodeVisitor):
    def __init__(self) -> None:
        self.args: List[Dict[str, Any]] = []
        self.subcommands: List[Tuple[str, str]] = []
        self.imports: List[Tuple[int, str, List[str]]] = []
        self.strings: Set[str] = set()
        self.argv_index = False
        self.main_sig: Optional[str] = None
        self.main_guard = False
        self.selftest_func = False
        self.cli_flags: Set[str] = set()

    def visit_Call(self, node: ast.Call) -> None:
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else "")
        if name == "add_argument":
            flags = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            kw = {k.arg: _const(k.value) for k in node.keywords if k.arg}
            self.cli_flags.update(f for f in flags if f.startswith("-"))
            if flags:
                self.args.append({"flags": flags, **{k: v for k, v in kw.items()
                                                     if k in ("help", "action", "required", "choices", "default", "nargs")}})
        elif name == "add_parser" and node.args and isinstance(node.args[0], ast.Constant):
            kw = {k.arg: _const(k.value) for k in node.keywords if k.arg}
            self.subcommands.append((str(node.args[0].value), str(kw.get("help") or "")))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for a in node.names:
            self.imports.append((0, a.name, []))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.imports.append((node.level, node.module or "", [a.name for a in node.names]))

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and len(node.value) < 200:
            self.strings.add(node.value)

    def visit_Compare(self, node: ast.Compare) -> None:
        sides = [node.left] + list(node.comparators)
        mentions_argv = any("argv" in _names(s) for s in sides)
        if mentions_argv:
            for side in sides:
                for c in _flag_consts(side):
                    self.cli_flags.add(c)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        v = node.value
        if isinstance(v, ast.Attribute) and v.attr == "argv" and isinstance(v.value, ast.Name) and v.value.id == "sys":
            self.argv_index = True
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name == "main" and self.main_sig is None:
            self.main_sig = "main(%s)" % ast.unparse(node.args) if hasattr(ast, "unparse") else "main(...)"
        if node.name in ("selftest", "_selftest", "self_test", "run_selftest"):
            self.selftest_func = True
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        t = node.test
        if (isinstance(t, ast.Compare) and isinstance(t.left, ast.Name) and t.left.id == "__name__"
                and any(isinstance(c, ast.Constant) and c.value == "__main__" for c in t.comparators)):
            self.main_guard = True
        self.generic_visit(node)


def _names(node: Any) -> Set[str]:
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
    return out


def _flag_consts(node: Any) -> List[str]:
    vals = [node] if isinstance(node, ast.Constant) else (
        list(node.elts) if isinstance(node, (ast.List, ast.Tuple, ast.Set)) else [])
    return [v.value for v in vals if isinstance(v, ast.Constant) and isinstance(v.value, str)
            and v.value.startswith("-")]


def describe_arg(a: Dict[str, Any]) -> str:
    s = "/".join(a["flags"])
    bits = []
    for k in ("action", "nargs", "choices", "default", "required"):
        if a.get(k) is not None:
            bits.append("%s=%s" % (k, a[k]))
    if bits:
        s += " (" + ", ".join(str(b) for b in bits) + ")"
    if a.get("help"):
        s += ": " + " ".join(str(a["help"]).split())
    return s


def _positional_or_required(scan: _Scan) -> bool:
    for a in scan.args:
        if not any(f.startswith("-") for f in a["flags"]):
            if a.get("nargs") not in ("?", "*"):
                return True
        if a.get("required") is True:
            return True
    return False


def guess_run(path: str, src: str, scan: Optional[_Scan]) -> Tuple[Optional[str], str]:
    if rl.is_standalone_selftest(path):
        return "python3 %s" % path, "file name is a standalone selftest"
    for flag in ("--selftest", "--self-test", "--example", "--demo"):
        if scan is not None:
            if flag in scan.cli_flags:
                return "python3 %s %s" % (path, flag), "%s is an argparse flag or compared against argv" % flag
        elif re.search(r"[\"']%s[\"']" % re.escape(flag), src):
            return "python3 %s %s" % (path, flag), "literal %s in source (source did not parse)" % flag
    if scan is not None:
        subs = {s for s, _ in scan.subcommands}
        for sub in ("selftest", "demo", "example"):
            if sub in subs:
                return "python3 %s %s" % (path, sub), "argparse subcommand %r" % sub
        if scan.main_guard and not scan.subcommands and not _positional_or_required(scan) and not scan.argv_index:
            return "python3 %s" % path, "__main__ guard; no positional/required args, no sys.argv indexing"
        if not scan.main_guard:
            return None, "no __main__ guard (module, not a script)"
        return None, "needs arguments the source does not supply an example for"
    return None, "source did not parse; no run guessed"


def resolve_imports(path: str, scan: _Scan, files: Set[str]) -> List[str]:
    """Repo files the module imports, by plain path resolution.  sys.path tricks
    are not followed beyond the tool's directory and the repository root."""
    here = PurePosixPath(path).parent
    found: List[str] = []

    def probe(base: PurePosixPath, dotted: str) -> Optional[str]:
        if not dotted:
            return None
        rel = PurePosixPath(*dotted.split("."))
        for cand in (base / (str(rel) + ".py"), base / rel / "__init__.py"):
            c = str(cand)
            if c.startswith("./"):
                c = c[2:]
            if c in files:
                return c
        return None

    for level, mod, names in scan.imports:
        bases: List[PurePosixPath]
        if level:
            b = here
            for _ in range(level - 1):
                b = b.parent
            bases = [b]
        else:
            bases = [here, PurePosixPath(".")]
        for base in bases:
            hit = probe(base, mod)
            subs = [probe(base, (mod + "." if mod else "") + n) for n in names]
            for h in [hit] + subs:
                if h and h != path and h not in found:
                    found.append(h)
            if hit or any(subs):
                break
    return found


def referenced_files(path: str, strings: Set[str], files: Set[str]) -> List[str]:
    here = PurePosixPath(path).parent
    out = []
    for s in sorted(strings):
        if not _PATH_LIT.match(s):
            continue
        for cand in (str(here / s), s):
            c = cand[2:] if cand.startswith("./") else cand
            if c in files and c != path and c not in out:
                out.append(c)
                break
    return out


_SAMPLE_INDEX: Dict[int, Dict[str, List[str]]] = {}


def sample_files(path: str, files: Set[str]) -> List[str]:
    idx = _SAMPLE_INDEX.get(id(files))
    if idx is None:
        idx = {}
        for f in sorted(files):
            d, _, name = f.rpartition("/")
            if d == "samples" or d.endswith("/samples"):
                idx.setdefault(d, []).append(name)
        _SAMPLE_INDEX[id(files)] = idx
    p = PurePosixPath(path)
    sdir = str(p.parent / "samples")
    sdir = sdir[2:] if sdir.startswith("./") else sdir
    stem = p.stem
    return ["%s/%s" % (sdir, n) for n in idx.get(sdir, [])
            if n.startswith(stem + ".") or n.startswith(stem + "_")]


def sibling_selftests(path: str, files: Set[str]) -> List[str]:
    p = PurePosixPath(path)
    d, stem = p.parent, p.stem
    cands = [d / "selftest.py", d / ("%s_selftest.py" % stem), d / ("test_%s.py" % stem),
             d / "tests" / ("test_%s.py" % stem), PurePosixPath("tests") / ("test_%s.py" % stem)]
    out = []
    for c in cands:
        s = str(c)
        s = s[2:] if s.startswith("./") else s
        if s in files and s != path:
            out.append(s)
    return out


def extract_program(path: str, data: bytes, files: Set[str]) -> Dict[str, Any]:
    src = data.decode("utf-8", errors="replace")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(src)
        scan: Optional[_Scan] = _Scan()
        scan.visit(tree)
        doc = ast.get_docstring(tree)
        parse_note = None
    except SyntaxError as e:
        scan, doc, tree = None, None, None
        parse_note = "ast parse failed: %s line %s" % (e.msg, e.lineno)

    if doc:
        purpose = rl.draft(first_paragraph(doc), "first paragraph of module docstring")
    else:
        lc = leading_comment(src)
        purpose = rl.draft(lc or None, "leading comment block" if lc else (parse_note or "no module docstring"))

    if scan is None:
        inp = rl.draft(None, parse_note or "")
    elif scan.args or scan.subcommands:
        vals = ["subcommand %s%s" % (s, (": " + " ".join(h.split())) if h else "") for s, h in scan.subcommands]
        vals += [describe_arg(a) for a in scan.args]
        inp = rl.draft(vals, "argparse calls in source")
    elif scan.main_sig:
        inp = rl.draft([scan.main_sig] + (["reads sys.argv by index"] if scan.argv_index else []), "main() signature")
    elif scan.argv_index:
        inp = rl.draft(["reads sys.argv by index"], "sys.argv subscript in source")
    else:
        inp = rl.draft([], "no argparse, no main(), no sys.argv indexing found")

    samples = sample_files(path, files)
    out_val = ["sample: %s" % s for s in samples]
    output = rl.draft(out_val, "samples/ files named after the tool; refreshed from run capture by run_examples.py")

    cmd, basis = guess_run(path, src, scan)
    flags = safety_flags(src)
    run = rl.draft(cmd, basis)
    run["safety"] = flags

    sibs = sibling_selftests(path, files)
    st = {
        "in_file": bool(re.search(r"[\"']--?self-?test[\"']", src)) or bool(scan and scan.selftest_func),
        "sibling": sibs,
        "is_selftest": rl.is_standalone_selftest(path),
    }
    selftest = rl.draft(st, "selftest flag/function in source; selftest.py / test_<stem>.py beside it")

    imports = resolve_imports(path, scan, files) if scan else []
    refs = referenced_files(path, scan.strings, files) if scan else []
    return {"purpose": purpose, "input": inp, "output": output, "run": run,
            "selftest": selftest, "_imports": imports, "_refs": refs + samples, "_siblings": sibs}


def extract_doc(path: str, data: bytes, files: Set[str]) -> Dict[str, Any]:
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    title = next((ln.lstrip("#").strip() for ln in lines if ln.startswith("#")), "")
    body = []
    started = False
    for ln in lines:
        if ln.startswith("#"):
            if started and body:
                break
            started = True
            continue
        if started:
            body.append(ln)
    para = first_paragraph("\n".join(body))
    purpose = rl.draft(("%s: %s" % (title, para)) if title and para else (title or para or None),
                       "first heading + first paragraph of the document")
    refs = []
    for m in _MD_PATH.finditer(text):
        p = m.group(1)
        for cand in (str(PurePosixPath(path).parent / p), p):
            if cand in files and cand != path and cand not in refs:
                refs.append(cand)
                break
    run = rl.draft(None, "method document; nothing to execute")
    run["safety"] = []
    return {
        "purpose": purpose,
        "input": rl.draft(None, "method document; not a program"),
        "output": rl.draft(None, "method document; not a program"),
        "run": run,
        "selftest": rl.draft(None, "method document"),
        "_imports": [], "_refs": refs, "_siblings": [],
    }


# ---------------------------------------------------------------------------
# card set
# ---------------------------------------------------------------------------

PROBLEM_RUNS_HEADER = (
    "Problem runs.  One entry per run: {id, problem, date}.  For every run listed here,\n"
    "EVERY card carries a check_record entry {run, checked: yes, result: picked_up | skipped,\n"
    "because, date}.  validate.py fails a run where any card is missing or checked: no,\n"
    "and a skip with an empty because (unrecorded skip = E3, defaulted slot).\n"
    "generate.py creates this file once and never edits it."
)


class Report:
    def __init__(self) -> None:
        self.lines: List[str] = []
        self.problems = 0

    def note(self, msg: str) -> None:
        self.lines.append("  " + msg)

    def problem(self, msg: str) -> None:
        self.problems += 1
        self.lines.append("  PROBLEM " + msg)


def plan_cards(l3: rl.Layer3) -> List[Dict[str, Any]]:
    """One entry per card: id, kind, locations (layer-3 rows)."""
    groups: Dict[Tuple[str, str], List[rl.Row]] = {}
    for r in l3.programs():
        groups.setdefault((r.path, r.sha12), []).append(r)
    by_path: Dict[str, Set[str]] = {}
    for (path, sha), rows in groups.items():
        by_path.setdefault(path, set()).add(sha)

    plans = []
    for (path, sha), rows in groups.items():
        rows = sorted(rows, key=lambda r: rl.REPOS.index(r.repo))
        cid = rl.slug(path)
        if len(by_path[path]) > 1:
            cid += "@" + rl.REPO_SHORT[rows[0].repo]
        plans.append({"id": cid, "kind": "program", "rows": rows})

    for path in rl.CORE_DOCS:
        rows = [l3.row(repo, path) for repo in rl.REPOS]
        rows = [r for r in rows if r is not None]
        if not rows:
            continue
        shas = {r.sha12 for r in rows}
        if len(shas) == 1:
            plans.append({"id": rl.slug(path), "kind": "method_document", "rows": rows})
        else:  # not expected for the named eight; kept apart, never merged
            for r in rows:
                plans.append({"id": rl.slug(path) + "@" + rl.REPO_SHORT[r.repo], "kind": "method_document", "rows": [r]})
    ids = [p["id"] for p in plans]
    if len(ids) != len(set(ids)):
        raise SystemExit("card id collision: %s" % sorted({i for i in ids if ids.count(i) > 1}))
    return plans


def face_order(plans: List[Dict[str, Any]]) -> List[str]:
    def key(p: Dict[str, Any]) -> Tuple[int, int, str]:
        repos = {r.repo for r in p["rows"]}
        path = p["rows"][0].path
        if p["kind"] == "method_document":
            return (0, rl.CORE_DOCS.index(path), path)
        if len(repos) == 2:
            return (1, 0, path)
        if repos == {"method-layer"}:
            return (2, 0, path)
        return (3, 0, path)
    return [p["id"] for p in sorted(plans, key=key)]


def merge_card(old: Optional[Dict[str, Any]], plan: Dict[str, Any], gen: Dict[str, Any],
               related: List[Dict[str, str]], l3: rl.Layer3, snap_ok: Dict[Tuple[str, str], str]) -> Dict[str, Any]:
    old = old or {}
    rows: List[rl.Row] = plan["rows"]
    card: Dict[str, Any] = {"id": plan["id"], "kind": plan["kind"],
                            "tool": "%s/%s" % (rows[0].repo, rows[0].path)}
    prov_old = (old.get("_provenance") or {}).get("written", {})
    written: Dict[str, str] = {}

    for f in rl.CARD_AUTHOR_FIELDS:
        if f in old:
            card[f] = old[f]
            if f in prov_old:
                written[f] = prov_old[f]
        else:
            card[f] = rl.AUTHOR
            written[f] = rl.field_hash(rl.AUTHOR)

    gen = dict(gen)
    gen["related"] = rl.draft(related, "imports, imported-by, shared/sample files, sibling selftests, same bytes")
    for f in rl.CARD_GENERATED_FIELDS:
        if f in old and not rl.is_draft(old[f]):
            card[f] = old[f]
            if f in prov_old:
                written[f] = prov_old[f]
        else:
            card[f] = gen[f]
            written[f] = rl.field_hash(gen[f])

    integrity = []
    for r in rows:
        loc = {"repo": r.repo, "path": r.path, "sha12": r.sha12, "commit": l3.heads[r.repo],
               "last_change": r.date, "layer3_row": r.source}
        if r.last_commit:
            loc["last_commit"] = r.last_commit
        loc["snapshot_bytes"] = snap_ok.get((r.repo, r.path), "NOT_CHECKED")
        integrity.append(loc)
    card["integrity"] = integrity
    card["check_record"] = old.get("check_record", [])  # written by problem runs, never by generate

    run = card["run"]
    cmd = run.get("value") if rl.is_draft(run) else run
    rr_old = old.get("run_result")
    cur_sha = rows[0].sha12
    if isinstance(rr_old, dict) and rr_old.get("status") in ("RUN", "FAILED") and \
            rr_old.get("sha12") == cur_sha and rr_old.get("command") == cmd:
        card["run_result"] = rr_old
    elif isinstance(rr_old, dict) and rr_old.get("status") == "UNRUN" and rr_old.get("command") == cmd \
            and rr_old.get("sha12") in (None, cur_sha):
        card["run_result"] = rr_old
    else:
        reason = "not yet executed"
        if isinstance(rr_old, dict) and rr_old.get("status") in ("RUN", "FAILED"):
            reason = "previous %s capture is stale: tool bytes or run command changed" % rr_old["status"]
        card["run_result"] = {"status": "UNRUN", "captured": "", "date": "", "command": cmd,
                              "sha12": cur_sha, "reason": reason}

    if rl.is_draft(card["output"]) and plan["kind"] == "program":
        card["output"] = rl.output_with_capture(card["output"], card["run_result"])

    if old.get("status") == "PROPOSED":
        card["status"] = "PROPOSED"
    else:
        card["status"] = "RUN" if card["run_result"].get("status") == "RUN" else "UNRUN"

    card["_provenance"] = {"generator": rl.GENERATOR_ID, "layer3_txt_sha256": l3.txt_sha256,
                           "written": {k: written[k] for k in sorted(written)}}
    return card


def build(l3: rl.Layer3, snaps: Dict[str, Snapshot], cards_dir: Path, apparatus_path: Path,
          read_first_path: Path, check: bool = False) -> Tuple[Report, int]:
    rep = Report()
    files = {repo: set(snaps.get(repo, {})) for repo in rl.REPOS}
    plans = plan_cards(l3)

    snap_ok: Dict[Tuple[str, str], str] = {}
    for p in plans:
        for r in p["rows"]:
            data = snaps.get(r.repo, {}).get(r.path)
            if data is None:
                snap_ok[(r.repo, r.path)] = "ABSENT"
                rep.problem("%s/%s in layer 3 but not in snapshot %s" % (r.repo, r.path, l3.heads[r.repo][:12]))
            elif sha12(data) != r.sha12:
                snap_ok[(r.repo, r.path)] = "MISMATCH"
                rep.problem("%s/%s snapshot sha12 %s != layer 3 %s" % (r.repo, r.path, sha12(data), r.sha12))
            else:
                snap_ok[(r.repo, r.path)] = "MATCH"

    # snapshot programs layer 3 does not list
    for repo in rl.REPOS:
        for path in sorted(files[repo]):
            if rl.is_program(path)[0] and l3.row(repo, path) is None:
                rep.problem("%s/%s is a program at the snapshot but has no layer-3 row (no card made)" % (repo, path))

    loc_to_id: Dict[Tuple[str, str], str] = {}
    for p in plans:
        for r in p["rows"]:
            loc_to_id[(r.repo, r.path)] = p["id"]

    gens: Dict[str, Dict[str, Any]] = {}
    for p in plans:
        r = p["rows"][0]
        data = snaps.get(r.repo, {}).get(r.path, b"")
        ex = extract_doc if p["kind"] == "method_document" else extract_program
        gens[p["id"]] = ex(r.path, data, files[r.repo])

    # related: imports / imported-by / shared files / siblings / same bytes
    rel: Dict[str, List[Dict[str, str]]] = {p["id"]: [] for p in plans}

    def add(a: str, b: str, via: str) -> None:
        if a != b and not any(x["id"] == b and x["via"] == via for x in rel[a]):
            rel[a].append({"id": b, "via": via})

    file_users: Dict[Tuple[str, str], List[str]] = {}
    for p in plans:
        r = p["rows"][0]
        g = gens[p["id"]]
        for imp in g["_imports"]:
            tgt = loc_to_id.get((r.repo, imp))
            if tgt:
                add(p["id"], tgt, "imports")
                add(tgt, p["id"], "imported-by")
        for s in g["_siblings"]:
            tgt = loc_to_id.get((r.repo, s))
            if tgt:
                add(p["id"], tgt, "sibling-selftest")
                add(tgt, p["id"], "selftest-of")
        for f in g["_refs"]:
            tgt = loc_to_id.get((r.repo, f))
            if tgt:
                add(p["id"], tgt, "mentions %s" % f)
            else:
                file_users.setdefault((r.repo, f), []).append(p["id"])
    for (repo, f), users in file_users.items():
        if 1 < len(users) <= 8:
            for a in users:
                for b in users:
                    add(a, b, "shares %s" % f)
    by_sha: Dict[Tuple[str, str], List[str]] = {}
    for p in plans:
        for r in p["rows"]:
            by_sha.setdefault((r.repo, r.sha12), []).append(p["id"])
    for ids in by_sha.values():
        for a in ids:
            for b in ids:
                add(a, b, "same-bytes")

    cards_dir.mkdir(parents=True, exist_ok=True)
    changed = 0
    existing_ids = {pth.stem for pth in cards_dir.glob("*.yaml")}
    planned_ids = {p["id"] for p in plans}
    for orphan in sorted(existing_ids - planned_ids):
        rep.problem("card %s has no layer-3 program; left in place, not deleted" % orphan)

    cards: Dict[str, Dict[str, Any]] = {}
    for p in plans:
        cp = rl.card_path(p["id"], cards_dir)
        old = rl.read_yaml(cp) if cp.exists() else None
        g = {k: v for k, v in gens[p["id"]].items() if not k.startswith("_")}
        related = sorted(rel[p["id"]], key=lambda x: (x["via"], x["id"]))[:24]
        card = rl.order_card(merge_card(old, p, g, related, l3, snap_ok))
        cards[p["id"]] = card
        text = rl.dump_yaml(card, rl.CARD_HEADER)
        if not cp.exists() or cp.read_text(encoding="utf-8") != text:
            changed += 1
            if not check:
                cp.write_text(text, encoding="utf-8")

    # apparatus
    ap_old = rl.read_yaml(apparatus_path) if apparatus_path.exists() else None
    ap_in = (ap_old or {}).get("apparatus", {}) if isinstance(ap_old, dict) else {}
    ap: Dict[str, Any] = {}
    for f in rl.APPARATUS_AUTHOR_FIELDS:
        ap[f] = ap_in.get(f, rl.AUTHOR)
    old_faces = [f for f in (ap_in.get("faces") or []) if isinstance(f, dict) and f.get("id")]
    seen = {f["id"] for f in old_faces}
    faces = list(old_faces)
    for cid in face_order(plans):
        if cid not in seen:
            faces.append({"id": cid, "card": "cards/%s.yaml" % cid})
    for f in faces:
        if f["id"] not in planned_ids:
            rep.problem("APPARATUS face %s has no card in the plan; kept, validate will fail it" % f["id"])
    ap["faces"] = faces
    for k, v in ap_in.items():
        if k not in ap:
            ap[k] = v
    apparatus = {"apparatus": ap}
    for k, v in (ap_old or {}).items() if isinstance(ap_old, dict) else []:
        if k != "apparatus":
            apparatus[k] = v
    ap_text = rl.dump_yaml(apparatus, "LAYER 1.  Read first.  name/shape/read_order/corpus_default_to_avoid are AUTHOR.\n"
                                      "faces is generated from cards/; reorder freely, generate.py keeps your order.")
    if not apparatus_path.exists() or apparatus_path.read_text(encoding="utf-8") != ap_text:
        changed += 1
        if not check:
            apparatus_path.write_text(ap_text, encoding="utf-8")

    pr_path = apparatus_path.parent / rl.PROBLEM_RUNS_PATH.name
    if not pr_path.exists():
        changed += 1
        if not check:
            pr_path.write_text(rl.dump_yaml({"runs": []}, PROBLEM_RUNS_HEADER), encoding="utf-8")

    rf_text = rl.render_read_first(apparatus, cards)
    if not read_first_path.exists() or read_first_path.read_text(encoding="utf-8") != rf_text:
        changed += 1
        if not check:
            read_first_path.write_text(rf_text, encoding="utf-8")

    n_doc = sum(1 for p in plans if p["kind"] == "method_document")
    n_two = sum(1 for p in plans if len(p["rows"]) == 2)
    rep.lines.insert(0, "cards planned: %d (%d method documents, %d programs; %d listed in both repos)"
                     % (len(plans), n_doc, len(plans) - n_doc, n_two))
    rep.lines.insert(1, "files %s: %d" % ("that would change" if check else "written", changed))
    return rep, changed


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--simulators", required=True, type=Path, help="git clone of JinnZ2/Simulators holding the snapshot commit")
    ap.add_argument("--method-layer", required=True, type=Path, help="git clone of JinnZ2/method-layer holding the snapshot commit")
    ap.add_argument("--inventory", type=Path, default=rl.LAYER3_TXT, help="layer-3 TXT (default: pinned copy)")
    ap.add_argument("--meta", type=Path, default=rl.LAYER3_META, help="layer-3 metadata json")
    ap.add_argument("--out", type=Path, default=rl.HERE, help="reasoning-layer directory to write into")
    ap.add_argument("--check", action="store_true", help="write nothing; exit 1 if any file would change")
    a = ap.parse_args(argv)

    if a.inventory == rl.LAYER3_TXT:
        bad = rl.check_layer3_pin()
        if bad:
            print("\n".join(bad))
            return 3
    l3 = rl.load_layer3(a.inventory, a.meta)
    snaps = {"Simulators": git_snapshot(a.simulators, l3.heads["Simulators"]),
             "method-layer": git_snapshot(a.method_layer, l3.heads["method-layer"])}
    rep, changed = build(l3, snaps, a.out / "cards", a.out / "APPARATUS.yaml", a.out / "READ_FIRST.md", a.check)
    print("generate.py  layer3=%s  Simulators@%s  method-layer@%s"
          % (l3.txt_sha256[:12], l3.heads["Simulators"][:12], l3.heads["method-layer"][:12]))
    print("\n".join(rep.lines))
    if a.check and changed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
