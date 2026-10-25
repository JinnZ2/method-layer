"""Shared machinery for the reasoning layer: layer-3 reader, card model,
YAML subset, schema subset, renderer.

Standard library only.  Nothing here interprets the method: every value this
module produces is either copied from layer 3, extracted mechanically from a
file's bytes, or the literal placeholder ``AUTHOR``.

```text
LAYER 3  layer3/INVENTORY_2026-10-14.txt (+ metadata json)   read, never written
   |       parse_inventory(): historical rows, then addendum rows override
   v
effective rows {repo: {path: Row}}  --is_program()-->  program set
   |                                 --CORE_DOCS------>  8 shared method documents
   v
LAYER 2  cards/<id>.yaml    fields: GENERATED = {mark: DRAFT, value, basis}
   |                                AUTHOR    = literal "AUTHOR" until Kavik writes it
   v
LAYER 1  APPARATUS.yaml     faces generated; name/shape/read_order/... AUTHOR
   |
   v
READ_FIRST.md   render only; AUTHOR -> [not yet written], DRAFT -> visible marker
```

Ownership of card fields (enforced by generate.py and validate.py):

```text
AUTHOR      face_of forces_step pick_up_when skip_when wrong_read right_read
GENERATED   purpose input output run related selftest     (DRAFT until replaced)
run_examples.py   run_result, status (RUN only with a captured run)
problem run check_record: one entry per card per run in problem_runs.yaml
layer 3     integrity
```
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
LAYER3_DIR = HERE / "layer3"
LAYER3_TXT = LAYER3_DIR / "INVENTORY_2026-10-14.txt"
LAYER3_META = LAYER3_DIR / "inventory_update_metadata.json"
LAYER3_PIN = HERE / "layer3.sha256"
CARDS_DIR = HERE / "cards"
APPARATUS_PATH = HERE / "APPARATUS.yaml"
PROBLEM_RUNS_PATH = HERE / "problem_runs.yaml"
READ_FIRST_PATH = HERE / "READ_FIRST.md"
SCHEMA_DIR = HERE / "schema"

AUTHOR = "AUTHOR"
DRAFT = "DRAFT"
GENERATOR_ID = "reasoning-layer/generate.py"

REPOS = ("Simulators", "method-layer")
REPO_SHORT = {"Simulators": "sim", "method-layer": "ml"}

CARD_AUTHOR_FIELDS = (
    "face_of", "forces_step", "pick_up_when", "skip_when", "wrong_read", "right_read",
)
CARD_GENERATED_FIELDS = ("purpose", "input", "output", "run", "related", "selftest")
APPARATUS_AUTHOR_FIELDS = ("name", "shape", "read_order", "corpus_default_to_avoid")

CARD_FIELD_ORDER = (
    "id", "kind", "tool", "face_of", "purpose", "forces_step", "pick_up_when",
    "skip_when", "input", "output", "run", "run_result", "wrong_read",
    "right_read", "related", "selftest", "check_record", "status", "integrity", "_provenance",
)

# Work order section 4, "Card priority": the eight tools/*.md method documents
# named there.  Only these documents get cards; every other card is a program.
CORE_DOCS = (
    "tools/bin_self_test.md",
    "tools/bin_slack_conservation.md",
    "tools/contested_area_hidden_assumption.md",
    "tools/coupling_and_accumulation.md",
    "tools/held_tie_precision.md",
    "tools/landauer_floor_vs_run_cost.md",
    "tools/natural_two_senses.md",
    "tools/uncounted_observer_isolation.md",
)

CAPTURE_LINES = 40
CAPTURE_LINE_CHARS = 300


# ---------------------------------------------------------------------------
# program rule (layer 3: "Standalone selftest programs are shown as source
# programs; regression test modules are supporting files")
# ---------------------------------------------------------------------------

_SELFTEST_NAME = re.compile(r"^(selftest|self_test)(_.*)?\.py$|^.*_selftest\.py$")


def is_standalone_selftest(path: str) -> bool:
    return bool(_SELFTEST_NAME.match(path.rsplit("/", 1)[-1]))


def is_program(path: str) -> Tuple[bool, str]:
    """Return (included, rule) for one layer-3 path.  The rule string names
    the clause that decided, so a disagreement can be pointed at one line."""
    if not path.endswith(".py"):
        return False, "not .py"
    base = path.rsplit("/", 1)[-1]
    if base in ("__init__.py", "conftest.py"):
        return False, "package marker / pytest config"
    if is_standalone_selftest(path):
        return True, "standalone selftest"
    dirs = path.split("/")[:-1]
    if "tests" in dirs or "test" in dirs:
        return False, "under a tests/ directory (regression test module)"
    if base.startswith("test_"):
        return False, "test_*.py (regression test module)"
    return True, "non-test python"


# ---------------------------------------------------------------------------
# layer 3
# ---------------------------------------------------------------------------

_ROW = re.compile(
    r"^(?P<path>.+?) \| (?P<lines>\d+) \| (?P<bytes>\d+) \| (?P<sha12>[0-9a-f]{12}) \| "
    r"(?P<date>\S+)(?: \| FLAGS: (?P<flags>.*))?$"
)
_REPO_HIST = re.compile(r"^#{10} (?P<repo>\S+)\s+\((?P<n>\d+) files\) #{10}$")
_REPO_NEW = re.compile(r"^#{10} NEW IN (?P<repo>\S+): .* #{10}$")
_HEAD = re.compile(r"^(?P<repo>\S+) main: (?P<sha>[0-9a-f]{7,40})$")


class Layer3Error(Exception):
    pass


@dataclass
class Row:
    repo: str
    path: str
    lines: int
    bytes: int
    sha12: str
    date: str
    flags: List[str]
    source: str  # historical | new | changed
    last_commit: Optional[str] = None
    sha256: Optional[str] = None


@dataclass
class Layer3:
    rows: Dict[str, Dict[str, Row]]
    heads: Dict[str, str]
    absent: Dict[str, List[str]]
    txt_sha256: str
    pair_check: Dict[str, Tuple[str, str, str]] = field(default_factory=dict)

    def programs(self) -> List[Row]:
        out = []
        for repo in REPOS:
            for path in sorted(self.rows.get(repo, {})):
                if is_program(path)[0]:
                    out.append(self.rows[repo][path])
        return out

    def row(self, repo: str, path: str) -> Optional[Row]:
        return self.rows.get(repo, {}).get(path)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_layer3_pin(pin: Path = LAYER3_PIN, base: Path = LAYER3_DIR) -> List[str]:
    """Compare layer-3 files against the pinned sha256 list.  Returns problems."""
    problems = []
    if not pin.exists():
        return ["layer-3 pin file missing: %s" % pin]
    for line in pin.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split("  ", 1)
        p = base / name
        if not p.exists():
            problems.append("layer-3 file missing: %s" % name)
        elif sha256_file(p) != digest:
            problems.append("layer-3 file changed: %s" % name)
    return problems


def parse_inventory(text: str, meta: Optional[dict] = None) -> Layer3:
    """Parse the inventory TXT.  Historical rows first; addendum rows for new
    or changed paths override them; absent paths are dropped from the
    effective set (they stay recorded in ``absent``)."""
    rows: Dict[str, Dict[str, Row]] = {r: {} for r in REPOS}
    heads: Dict[str, str] = {}
    absent: Dict[str, List[str]] = {r: [] for r in REPOS}
    pair: Dict[str, Tuple[str, str, str]] = {}
    repo: Optional[str] = None
    mode = None  # historical | addendum
    sub = None   # new | changed | absent
    in_pair = False

    for raw in text.splitlines():
        line = raw.rstrip("\n")
        m = _REPO_HIST.match(line)
        if m and m.group("repo") in REPOS:
            repo, mode, sub, in_pair = m.group("repo"), "historical", None, False
            continue
        m = _REPO_NEW.match(line)
        if m and m.group("repo") in REPOS:
            repo, mode, sub, in_pair = m.group("repo"), "addendum", None, False
            continue
        if line.startswith("=== "):
            repo, mode, sub = None, None, None
            in_pair = "PAIR CHECK" in line
            continue
        m = _HEAD.match(line)
        if m and m.group("repo") in REPOS:
            heads[m.group("repo")] = m.group("sha")  # last occurrence wins: addendum heads
            continue
        if in_pair:
            pm = re.match(r"^(\S+)\s+(IDENTICAL|DIFFERS)\s+sim=([0-9a-f]{12}) ml=([0-9a-f]{12})$", line)
            if pm:
                pair[pm.group(1)] = (pm.group(2), pm.group(3), pm.group(4))
            continue
        if repo is None:
            continue
        if line.startswith("--- "):
            if mode == "addendum":
                low = line.lower()
                if "absent" in low:
                    sub = "absent"
                elif "changed" in low:
                    sub = "changed"
                else:
                    sub = "new"
            continue
        if mode == "addendum" and sub == "absent":
            if line.strip() and line.strip() != "(none)":
                absent[repo].append(line.strip())
            continue
        m = _ROW.match(line)
        if not m:
            continue
        flags = [f.strip() for f in (m.group("flags") or "").split(",") if f.strip()]
        r = Row(repo, m.group("path"), int(m.group("lines")), int(m.group("bytes")),
                m.group("sha12"), m.group("date"), flags,
                "historical" if mode == "historical" else sub)
        if mode == "historical" and r.path in rows[repo]:
            raise Layer3Error("duplicate historical row: %s %s" % (repo, r.path))
        rows[repo][r.path] = r

    for repo_name in REPOS:
        for p in absent[repo_name]:
            rows[repo_name].pop(p, None)

    if meta is not None:
        for kind in ("new", "changed"):
            for repo_name, entries in meta.get(kind, {}).items():
                for e in entries:
                    r = rows.get(repo_name, {}).get(e["path"])
                    if r is None or r.sha12 != e["sha12"]:
                        raise Layer3Error("metadata json disagrees with TXT: %s %s" % (repo_name, e["path"]))
                    r.last_commit = e.get("last_commit")
                    r.sha256 = e.get("sha256")
        for repo_name, sha in meta.get("heads", {}).items():
            if heads.get(repo_name) and not sha.startswith(heads[repo_name]):
                raise Layer3Error("metadata head disagrees with TXT: %s" % repo_name)
            heads[repo_name] = sha

    return Layer3(rows, heads, absent, hashlib.sha256(text.encode("utf-8")).hexdigest(), pair)


def load_layer3(txt: Path = LAYER3_TXT, meta: Optional[Path] = LAYER3_META) -> Layer3:
    m = json.loads(meta.read_text(encoding="utf-8")) if meta and meta.exists() else None
    return parse_inventory(txt.read_text(encoding="utf-8"), m)


# ---------------------------------------------------------------------------
# ids
# ---------------------------------------------------------------------------

def slug(path: str) -> str:
    stem = path[:-3] if path.endswith(".py") else path
    s = stem.lower().replace("/", "--")
    s = re.sub(r"[^a-z0-9._-]+", "-", s).strip("-")
    return s


def card_path(card_id: str, cards_dir: Path = CARDS_DIR) -> Path:
    return cards_dir / (card_id + ".yaml")


def field_hash(value: Any) -> str:
    blob = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def is_draft(value: Any) -> bool:
    return isinstance(value, dict) and value.get("mark") == DRAFT


def draft(value: Any, basis: str) -> Dict[str, Any]:
    return {"mark": DRAFT, "value": value, "basis": basis}


def output_with_capture(output: Dict[str, Any], rr: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """DRAFT output = sample files + one line summarising the latest run capture."""
    vals = [v for v in (output.get("value") or []) if not str(v).startswith("run capture:")]
    if rr and rr.get("status") in ("RUN", "FAILED"):
        vals.append("run capture: %s, exit %s, %s lines, sha12 %s (see run_result)" % (
            rr["status"], rr.get("exit_code"), rr.get("output_lines"), rr.get("output_sha12")))
    out = dict(output)
    out["value"] = vals if (vals or output.get("value") is not None) else None
    return out


def is_author_empty(value: Any) -> bool:
    return value == AUTHOR or value is None or value == ""


def order_card(card: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: card[k] for k in CARD_FIELD_ORDER if k in card}
    for k in card:
        if k not in out:
            out[k] = card[k]
    return out


# ---------------------------------------------------------------------------
# YAML subset
#
# Emitted: block mappings and sequences, two-space indent; strings plain when
# unambiguous, block literal (| or |-) when multi-line, JSON double-quoted
# otherwise.  Loaded: the same, plus single-quoted scalars, flow lists of
# scalars ([a, b]), {} / [], comments, null/~/true/false/ints.  Anything else
# raises YamlError with a line number: hand edits stay inside this subset.
# ---------------------------------------------------------------------------

class YamlError(ValueError):
    pass


_PLAIN_SAFE = re.compile(r"^[A-Za-z0-9_./(][^\n]*$")
_INT = re.compile(r"^[-+]?\d+$")
_RESERVED = {"null", "~", "true", "false", "yes", "no", "on", "off", "Null", "NULL",
             "True", "False", "TRUE", "FALSE", "Yes", "No", "On", "Off"}
_KEY_SAFE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


def _plain_ok(s: str) -> bool:
    if not s or s != s.strip() or s in _RESERVED or _INT.match(s):
        return False
    if not _PLAIN_SAFE.match(s):
        return False
    if ": " in s or " #" in s or s.endswith(":") or "\t" in s:
        return False
    if any(ord(c) < 0x20 or ord(c) == 0x7f for c in s):
        return False
    if re.match(r"^[-+]?(\d+\.\d*|\.\d+|\d+[eE][-+]?\d+)$", s):
        return False
    return True


def _block_ok(s: str) -> bool:
    if "\n" not in s or "\r" in s:
        return False
    body = s[:-1] if s.endswith("\n") else s
    if body.endswith("\n") or not body:
        return False
    lines = body.split("\n")
    if not lines[0] or lines[0][:1] in (" ", "\t"):
        return False
    for ln in lines:
        if ln and not ln.strip():
            return False
        if any((ord(c) < 0x20 and c != "\t") or ord(c) == 0x7f for c in ln):
            return False
    return True


def _scalar(v: Any) -> str:
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return v if _plain_ok(v) else json.dumps(v, ensure_ascii=False)
    raise YamlError("cannot emit %r" % type(v))


def _key(k: str) -> str:
    return k if _KEY_SAFE.match(k) else json.dumps(k, ensure_ascii=False)


def _emit(v: Any, indent: int, out: List[str]) -> None:
    pad = " " * indent
    if isinstance(v, dict):
        for k, val in v.items():
            _emit_entry(pad + _key(k) + ":", val, indent, out)
    elif isinstance(v, list):
        for item in v:
            if isinstance(item, dict) and item:
                sub: List[str] = []
                _emit(item, indent + 2, sub)
                sub[0] = pad + "- " + sub[0][indent + 2:]
                out.extend(sub)
            else:
                _emit_entry(pad + "-", item, indent, out)
    else:
        raise YamlError("top level must be a mapping or list")


def _emit_entry(head: str, val: Any, indent: int, out: List[str]) -> None:
    if isinstance(val, dict):
        if not val:
            out.append(head + " {}")
        else:
            out.append(head)
            _emit(val, indent + 2, out)
    elif isinstance(val, list):
        if not val:
            out.append(head + " []")
        else:
            out.append(head)
            _emit(val, indent + 2, out)
    elif isinstance(val, str) and _block_ok(val):
        out.append(head + (" |" if val.endswith("\n") else " |-"))
        body = val[:-1] if val.endswith("\n") else val
        for ln in body.split("\n"):
            out.append((" " * (indent + 2) + ln) if ln else "")
    else:
        out.append(head + " " + _scalar(val))


def dump_yaml(obj: Any, header: str = "") -> str:
    out: List[str] = []
    if header:
        out.extend("# " + h if h else "#" for h in header.split("\n"))
    _emit(obj, 0, out)
    return "\n".join(out) + "\n"


class _Loader:
    def __init__(self, text: str):
        self.raw = text.split("\n")
        self.i = 0

    def _skip(self) -> None:
        while self.i < len(self.raw):
            s = self.raw[self.i].strip()
            if s and not s.startswith("#"):
                return
            self.i += 1

    def _peek(self) -> Optional[Tuple[int, str]]:
        self._skip()
        if self.i >= len(self.raw):
            return None
        ln = self.raw[self.i]
        if "\t" in ln[: len(ln) - len(ln.lstrip())]:
            raise YamlError("line %d: tab in indentation" % (self.i + 1))
        return len(ln) - len(ln.lstrip(" ")), ln.strip()

    def err(self, msg: str) -> YamlError:
        return YamlError("line %d: %s" % (self.i + 1, msg))

    def block(self, indent: int) -> Any:
        p = self._peek()
        if p is None:
            return None
        ind, text = p
        if ind != indent:
            raise self.err("unexpected indentation")
        if text == "-" or text.startswith("- "):
            return self.seq(indent)
        return self.mapping(indent)

    def seq(self, indent: int) -> List[Any]:
        out: List[Any] = []
        while True:
            p = self._peek()
            if p is None or p[0] < indent:
                return out
            ind, text = p
            if ind > indent:
                raise self.err("unexpected indentation in sequence")
            if not (text == "-" or text.startswith("- ")):
                return out
            rest = text[1:].strip()
            if not rest:
                self.i += 1
                nxt = self._peek()
                out.append(self.block(nxt[0]) if nxt and nxt[0] > indent else None)
            elif rest in ("|", "|-", "|+"):
                self.i += 1
                out.append(self.literal(indent, rest))
            elif self._is_key(rest):
                line = self.raw[self.i]
                col = len(line) - len(line.lstrip(" ")) + 2
                self.raw[self.i] = " " * col + rest
                out.append(self.mapping(col))
            else:
                self.i += 1
                out.append(self.inline(rest))

    def _split_key(self, text: str) -> Optional[Tuple[str, str]]:
        if text.startswith('"'):
            try:
                dec = json.JSONDecoder()
                k, end = dec.raw_decode(text)
            except ValueError:
                return None
            rest = text[end:]
            if not rest.startswith(":"):
                return None
            return k, rest[1:].strip()
        m = re.match(r"^([^:\s\"'#\[\]{}-][^:]*?|[A-Za-z0-9_-][^:]*?):(\s|$)(.*)$", text)
        if not m:
            return None
        return m.group(1).strip(), m.group(3).strip()

    def _is_key(self, text: str) -> bool:
        if text.startswith(("'", "[", "{")):
            return False
        return self._split_key(text) is not None

    def mapping(self, indent: int) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        while True:
            p = self._peek()
            if p is None or p[0] < indent:
                return out
            ind, text = p
            if ind > indent:
                raise self.err("unexpected indentation in mapping")
            if text == "-" or text.startswith("- "):
                return out
            kv = self._split_key(text)
            if kv is None:
                raise self.err("expected 'key: value'")
            k, rest = kv
            if k in out:
                raise self.err("duplicate key %r" % k)
            self.i += 1
            if rest in ("|", "|-", "|+"):
                out[k] = self.literal(indent, rest)
            elif rest == "" or rest.startswith("#"):
                nxt = self._peek()
                if nxt and nxt[0] > indent:
                    out[k] = self.block(nxt[0])
                elif nxt and nxt[0] == indent and (nxt[1] == "-" or nxt[1].startswith("- ")):
                    out[k] = self.seq(indent)
                else:
                    out[k] = None
            else:
                out[k] = self.inline(rest)

    def literal(self, indent: int, style: str) -> str:
        lines: List[str] = []
        block_ind = None
        while self.i < len(self.raw):
            ln = self.raw[self.i]
            if not ln.strip():
                lines.append("")
                self.i += 1
                continue
            ind = len(ln) - len(ln.lstrip(" "))
            if ind <= indent:
                break
            if block_ind is None:
                block_ind = ind
            if ind < block_ind:
                raise self.err("block scalar line less indented than its first line")
            lines.append(ln[block_ind:])
            self.i += 1
        while lines and lines[-1] == "":
            lines.pop()
            if style == "|+":
                raise self.err("'|+' with trailing blank lines is outside the subset")
        body = "\n".join(lines)
        return body if style == "|-" else body + "\n"

    def inline(self, s: str) -> Any:
        s = s.strip()
        if s.startswith('"'):
            try:
                v, end = json.JSONDecoder().raw_decode(s)
            except ValueError as e:
                raise self.err("bad double-quoted scalar: %s" % e)
            tail = s[end:].strip()
            if tail and not tail.startswith("#"):
                raise self.err("text after quoted scalar")
            return v
        if s.startswith("'"):
            m = re.match(r"^'((?:[^']|'')*)'\s*(#.*)?$", s)
            if not m:
                raise self.err("bad single-quoted scalar")
            return m.group(1).replace("''", "'")
        if s.startswith("["):
            if not s.endswith("]"):
                raise self.err("flow list must close on the same line")
            inner = s[1:-1].strip()
            if not inner:
                return []
            return [self.inline(p) for p in _split_flow(inner, self)]
        if s == "{}":
            return {}
        if s.startswith("{"):
            raise self.err("flow mappings other than {} are outside the subset")
        if " #" in s:
            s = s.split(" #", 1)[0].rstrip()
        if s in ("null", "~", "Null", "NULL"):
            return None
        if s in ("true", "True", "TRUE"):
            return True
        if s in ("false", "False", "FALSE"):
            return False
        if _INT.match(s):
            return int(s)
        return s


def _split_flow(inner: str, ld: _Loader) -> List[str]:
    parts, cur, q = [], "", None
    i = 0
    while i < len(inner):
        c = inner[i]
        if q:
            cur += c
            if c == "\\" and q == '"' and i + 1 < len(inner):
                cur += inner[i + 1]
                i += 1
            elif c == q:
                q = None
        elif c in "\"'":
            q = c
            cur += c
        elif c == ",":
            parts.append(cur.strip())
            cur = ""
        elif c in "[]{}":
            raise ld.err("nested flow collections are outside the subset")
        else:
            cur += c
        i += 1
    if q:
        raise ld.err("unterminated quote in flow list")
    parts.append(cur.strip())
    return parts


def load_yaml(text: str) -> Any:
    ld = _Loader(text)
    p = ld._peek()
    if p is None:
        return None
    v = ld.block(p[0])
    if ld._peek() is not None:
        raise ld.err("trailing content")
    return v


def read_yaml(path: Path) -> Any:
    return load_yaml(path.read_text(encoding="utf-8"))


def write_if_changed(path: Path, text: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


CARD_HEADER = (
    "Reasoning-layer card.  Fields reading AUTHOR are Kavik's to write.\n"
    "Fields with mark: DRAFT were extracted by generate.py and are refreshed on rerun;\n"
    "replace a DRAFT mapping with a plain value to confirm it and stop the refresh.\n"
    "integrity comes from layer 3; run_result and status come from run_examples.py."
)


def write_card(card: Dict[str, Any], cards_dir: Path = CARDS_DIR) -> bool:
    return write_if_changed(card_path(card["id"], cards_dir), dump_yaml(order_card(card), CARD_HEADER))


def load_cards(cards_dir: Path = CARDS_DIR) -> Dict[str, Dict[str, Any]]:
    cards = {}
    for p in sorted(cards_dir.glob("*.yaml")):
        c = read_yaml(p)
        if not isinstance(c, dict):
            raise YamlError("%s: card is not a mapping" % p.name)
        cards[p.stem] = c
    return cards


# ---------------------------------------------------------------------------
# JSON-schema subset: type, enum, const, required, properties,
# additionalProperties (bool or schema), items, minItems, pattern, anyOf, $ref
# (local #/$defs/...).  Enough for schema/*.json; nothing else is honoured.
# ---------------------------------------------------------------------------

_TYPES = {
    "object": dict, "array": list, "string": str, "integer": int,
    "boolean": bool, "null": type(None),
}


def _type_ok(v: Any, t: str) -> bool:
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    return isinstance(v, _TYPES[t])


def schema_errors(v: Any, schema: Dict[str, Any], root: Optional[Dict[str, Any]] = None,
                  where: str = "$") -> List[str]:
    root = root or schema
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            return ["%s: unsupported $ref %s" % (where, ref)]
        return schema_errors(v, root["$defs"][ref[len("#/$defs/"):]], root, where)
    errs: List[str] = []
    if "anyOf" in schema:
        if not any(not schema_errors(v, s, root, where) for s in schema["anyOf"]):
            errs.append("%s: matches none of anyOf" % where)
        return errs
    t = schema.get("type")
    if t is not None:
        ts = t if isinstance(t, list) else [t]
        if not any(_type_ok(v, x) for x in ts):
            return ["%s: expected %s, got %s" % (where, "/".join(ts), type(v).__name__)]
    if "const" in schema and v != schema["const"]:
        errs.append("%s: must be %r" % (where, schema["const"]))
    if "enum" in schema and v not in schema["enum"]:
        errs.append("%s: %r not in %r" % (where, v, schema["enum"]))
    if isinstance(v, str) and "pattern" in schema and not re.search(schema["pattern"], v):
        errs.append("%s: %r does not match %s" % (where, v, schema["pattern"]))
    if isinstance(v, list):
        if len(v) < schema.get("minItems", 0):
            errs.append("%s: fewer than %d items" % (where, schema["minItems"]))
        if "items" in schema:
            for i, item in enumerate(v):
                errs += schema_errors(item, schema["items"], root, "%s[%d]" % (where, i))
    if isinstance(v, dict):
        for k in schema.get("required", []):
            if k not in v:
                errs.append("%s: missing %s" % (where, k))
        props = schema.get("properties", {})
        addl = schema.get("additionalProperties", True)
        for k, val in v.items():
            if k in props:
                errs += schema_errors(val, props[k], root, "%s.%s" % (where, k))
            elif addl is False:
                errs.append("%s: unexpected key %s" % (where, k))
            elif isinstance(addl, dict):
                errs += schema_errors(val, addl, root, "%s.%s" % (where, k))
    return errs


def load_schema(name: str, schema_dir: Path = SCHEMA_DIR) -> Dict[str, Any]:
    return json.loads((schema_dir / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# READ_FIRST.md
# ---------------------------------------------------------------------------

GAP = "[not yet written]"


def _txt(v: Any) -> str:
    """Render a field value; AUTHOR-empty -> GAP, DRAFT -> marked."""
    if is_author_empty(v):
        return GAP
    if is_draft(v):
        inner = v.get("value")
        if inner is None or inner == [] or inner == "":
            return "**[DRAFT]** (none extracted: %s)" % v.get("basis", "")
        return "**[DRAFT]** " + _txt(inner)
    if isinstance(v, list):
        return "; ".join(_txt(x) for x in v) if v else GAP
    if isinstance(v, dict):
        return ", ".join("%s=%s" % (k, _txt(x)) for k, x in v.items())
    return str(v)


def _cell(v: Any) -> str:
    return _txt(v).replace("|", "\\|").replace("\n", "<br>")


def _fence(text: str) -> str:
    ticks = "```"
    while ticks in text:
        ticks += "`"
    return ticks + "text\n" + text.rstrip("\n") + "\n" + ticks


def integrity_line(card: Dict[str, Any]) -> str:
    parts = []
    for loc in card.get("integrity", []):
        parts.append("%s/%s sha12=%s commit=%s last_change=%s" % (
            loc.get("repo"), loc.get("path"), loc.get("sha12"),
            str(loc.get("commit", ""))[:12], loc.get("last_change")))
    return " · ".join(parts)


def faces_in_order(apparatus: Dict[str, Any], cards: Dict[str, Dict[str, Any]]) -> Tuple[List[str], bool]:
    """Return (card ids in reading order, authored?)."""
    ap = apparatus.get("apparatus", {})
    ro = ap.get("read_order")
    if isinstance(ro, list) and ro:
        return [x for x in ro if x in cards], True
    ids = [f.get("id") for f in ap.get("faces", []) or [] if isinstance(f, dict)]
    return [x for x in ids if x in cards], False


def render_read_first(apparatus: Dict[str, Any], cards: Dict[str, Dict[str, Any]]) -> str:
    ap = apparatus.get("apparatus", {})
    order, authored = faces_in_order(apparatus, cards)
    name = ap.get("name")
    out: List[str] = []
    out.append("# READ FIRST: %s" % (GAP if is_author_empty(name) else name))
    out.append("")
    out.append("Rendered by `reasoning-layer/generate.py` (and `run_examples.py`) from "
               "`APPARATUS.yaml` and `cards/`. Do not edit this file; edit those.")
    out.append("")
    out.append("Markers: `%s` = a field only Kavik writes, still empty. "
               "`[DRAFT]` = extracted mechanically from the file, not confirmed. "
               "RUN = executed here with output captured; UNRUN = exists, not executed; "
               "FAILED = executed, nonzero exit or timeout." % GAP)
    out.append("")
    out.append("## Shape")
    out.append("")
    out.append(_txt(ap.get("shape")))
    out.append("")
    out.append("## Corpus default to avoid")
    out.append("")
    out.append(_txt(ap.get("corpus_default_to_avoid")))
    out.append("")
    out.append("## Read order")
    out.append("")
    if authored:
        out.append("Authored read_order, %d cards." % len(order))
    else:
        out.append("read_order: %s. Cards below follow the generated `faces` order in "
                   "APPARATUS.yaml (8 shared method documents first, then programs by "
                   "folder). That order is a filing order, not a reading of the method." % GAP)
    out.append("")
    out.append("## Tool selection")
    out.append("")
    out.append("Choose from the problem's conditions; not picking a tool is a choice.")
    out.append("")
    out.append("Every problem run checks every card and records `check_record` "
               "{run, checked, result, because, date}; an unrecorded skip is a defaulted slot. "
               "Cards are never removed for disuse.")
    out.append("")
    out.append("| card | pick_up_when | skip_when | picked_up / skipped |")
    out.append("|---|---|---|---|")
    for cid in order:
        c = cards[cid]
        recs = [r for r in c.get("check_record") or [] if isinstance(r, dict)]
        out.append("| `%s` | %s | %s | %d / %d |" % (
            cid, _cell(c.get("pick_up_when")), _cell(c.get("skip_when")),
            sum(1 for r in recs if r.get("result") == "picked_up"),
            sum(1 for r in recs if r.get("result") == "skipped")))
    out.append("")
    out.append("## Cards")
    for cid in order:
        c = cards[cid]
        rr = c.get("run_result") or {}
        out.append("")
        out.append("### %s" % cid)
        out.append("")
        out.append("`%s` · kind=%s · status=%s · face_of: %s" % (
            c.get("tool"), c.get("kind"), c.get("status"), _txt(c.get("face_of"))))
        out.append("")
        out.append("**forces_step:** %s" % _txt(c.get("forces_step")))
        out.append("")
        out.append("| wrong_read | right_read |")
        out.append("|---|---|")
        out.append("| %s | %s |" % (_cell(c.get("wrong_read")), _cell(c.get("right_read"))))
        out.append("")
        run = c.get("run")
        cmd = run.get("value") if is_draft(run) else run
        mark = "[DRAFT] " if is_draft(run) else ""
        if cmd:
            out.append("**run:** %s`%s` → %s%s" % (
                mark, cmd, rr.get("status", "UNRUN"),
                (" (exit %s, %s)" % (rr.get("exit_code"), rr.get("date"))) if rr.get("status") in ("RUN", "FAILED") else ""))
        else:
            out.append("**run:** %snone (%s) → %s" % (
                mark, run.get("basis", "") if isinstance(run, dict) else "", rr.get("status", "UNRUN")))
        if rr.get("reason"):
            out.append("")
            out.append("run note: %s" % rr["reason"])
        if rr.get("captured"):
            out.append("")
            out.append(_fence(rr["captured"]))
        out.append("")
        out.append("integrity: %s" % integrity_line(c))
        out.append("")
        out.append("purpose: %s  " % _txt(c.get("purpose")))
        out.append("input: %s  " % _txt(c.get("input")))
        out.append("output: %s  " % _txt(c.get("output")))
        recs = [r for r in c.get("check_record") or [] if isinstance(r, dict)]
        n_pick = sum(1 for r in recs if r.get("result") == "picked_up")
        n_skip = sum(1 for r in recs if r.get("result") == "skipped")
        out.append("check_record: %d entries, picked_up %d, skipped %d  " % (len(recs), n_pick, n_skip))
        rel = c.get("related")
        if is_draft(rel):
            ids = ["%s (%s)" % (r.get("id"), r.get("via")) for r in rel.get("value") or []]
            out.append("related: **[DRAFT]** %s" % ("; ".join(ids) if ids else "none extracted"))
        else:
            out.append("related: %s" % _txt(rel))
    out.append("")
    return "\n".join(out)
