#!/usr/bin/env python3
"""Check the reasoning layer against layer 3 and the schemas.

CC0.  Standard library only.  Reads; never writes.

```text
check                 FAIL when                                              source of truth
--------------------  -----------------------------------------------------  ----------------
layer3_pin            a layer-3 file differs from layer3.sha256              layer3.sha256
schema                a card / APPARATUS.yaml breaks schema/*.json           schema/
integrity             card path / sha12 / commit / date != layer-3 row       layer 3
coverage              a layer-3 program (or core doc) has no card            layer 3
orphan                a card names a location layer 3 does not list as one   layer 3
run_claim             RUN without captured output; status RUN while          run_result
                      run_result is not RUN; RUN capture for other bytes
author_provenance     an AUTHOR field holds a value generate.py wrote        _provenance.written
references            read_order / faces / related name a missing card       cards/
author_gaps           never fails: count of AUTHOR fields still empty        cards/, APPARATUS
```

Exit 0 = no FAIL, 1 = FAIL, 3 = cannot run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rl_common as rl  # noqa: E402


class Check:
    def __init__(self, name: str) -> None:
        self.name = name
        self.fails: List[str] = []
        self.info: List[str] = []

    @property
    def state(self) -> str:
        return "FAIL" if self.fails else "PASS"

    def to_dict(self) -> Dict[str, Any]:
        return {"check": self.name, "state": self.state, "fails": self.fails, "info": self.info}


def expected_locations(l3: rl.Layer3) -> Dict[Tuple[str, str], rl.Row]:
    out = {(r.repo, r.path): r for r in l3.programs()}
    for path in rl.CORE_DOCS:
        for repo in rl.REPOS:
            r = l3.row(repo, path)
            if r is not None:
                out[(repo, path)] = r
    return out


def validate(base: Path, l3: rl.Layer3, pin_problems: List[str]) -> List[Check]:
    cards_dir = base / "cards"
    checks = {n: Check(n) for n in ("layer3_pin", "schema", "integrity", "coverage", "orphan",
                                    "run_claim", "author_provenance", "references", "author_gaps")}
    checks["layer3_pin"].fails += pin_problems

    card_schema = rl.load_schema("card.schema.json", base / "schema")
    ap_schema = rl.load_schema("apparatus.schema.json", base / "schema")

    cards: Dict[str, Dict[str, Any]] = {}
    for p in sorted(cards_dir.glob("*.yaml")):
        try:
            c = rl.read_yaml(p)
        except rl.YamlError as e:
            checks["schema"].fails.append("%s: %s" % (p.name, e))
            continue
        if not isinstance(c, dict):
            checks["schema"].fails.append("%s: not a mapping" % p.name)
            continue
        cards[p.stem] = c
        for e in rl.schema_errors(c, card_schema):
            checks["schema"].fails.append("%s: %s" % (p.name, e))
        if c.get("id") != p.stem:
            checks["schema"].fails.append("%s: id %r does not match file name" % (p.name, c.get("id")))

    ap_path = base / "APPARATUS.yaml"
    apparatus: Dict[str, Any] = {}
    if not ap_path.exists():
        checks["schema"].fails.append("APPARATUS.yaml missing")
    else:
        try:
            apparatus = rl.read_yaml(ap_path) or {}
            for e in rl.schema_errors(apparatus, ap_schema):
                checks["schema"].fails.append("APPARATUS.yaml: %s" % e)
        except rl.YamlError as e:
            checks["schema"].fails.append("APPARATUS.yaml: %s" % e)

    # integrity / coverage / orphan
    expected = expected_locations(l3)
    covered: Dict[Tuple[str, str], str] = {}
    for cid, c in cards.items():
        for loc in c.get("integrity") or []:
            if not isinstance(loc, dict):
                continue
            key = (loc.get("repo"), loc.get("path"))
            if key in covered:
                checks["orphan"].fails.append("%s/%s carried by two cards: %s, %s" % (key[0], key[1], covered[key], cid))
            covered[key] = cid
            row = l3.row(*key) if key[0] in rl.REPOS else None
            if row is None:
                checks["integrity"].fails.append("%s: %s/%s has no layer-3 row" % (cid, key[0], key[1]))
                continue
            if key not in expected:
                checks["orphan"].fails.append("%s: %s/%s is in layer 3 but is not a program or core doc (%s)"
                                              % (cid, key[0], key[1], rl.is_program(key[1])[1]))
            if loc.get("sha12") != row.sha12:
                checks["integrity"].fails.append("%s: %s/%s sha12 %s != layer 3 %s" % (cid, key[0], key[1], loc.get("sha12"), row.sha12))
            if loc.get("commit") != l3.heads.get(key[0]):
                checks["integrity"].fails.append("%s: %s commit %s != layer-3 snapshot %s" % (cid, key[0], loc.get("commit"), l3.heads.get(key[0])))
            if loc.get("last_change") != row.date:
                checks["integrity"].fails.append("%s: %s/%s last_change %s != layer 3 %s" % (cid, key[0], key[1], loc.get("last_change"), row.date))
            if loc.get("snapshot_bytes") in ("MISMATCH", "ABSENT"):
                checks["integrity"].fails.append("%s: %s/%s snapshot bytes %s" % (cid, key[0], key[1], loc["snapshot_bytes"]))
        tool = c.get("tool")
        locs = ["%s/%s" % (l.get("repo"), l.get("path")) for l in c.get("integrity") or [] if isinstance(l, dict)]
        if locs and tool not in locs:
            checks["integrity"].fails.append("%s: tool %s is not one of its integrity locations" % (cid, tool))
    missing = sorted(k for k in expected if k not in covered)
    for repo, path in missing:
        checks["coverage"].fails.append("no card for %s/%s" % (repo, path))
    checks["coverage"].info.append("layer-3 locations expected %d, carried %d"
                                   % (len(expected), sum(1 for k in expected if k in covered)))

    # run claims
    for cid, c in cards.items():
        rr = c.get("run_result") or {}
        st = c.get("status")
        if rr.get("status") == "RUN" and not str(rr.get("captured") or "").strip():
            checks["run_claim"].fails.append("%s: run_result RUN with nothing captured" % cid)
        if st == "RUN" and rr.get("status") != "RUN":
            checks["run_claim"].fails.append("%s: status RUN but run_result is %s" % (cid, rr.get("status")))
        if rr.get("status") in ("RUN", "FAILED"):
            shas = {l.get("sha12") for l in c.get("integrity") or [] if isinstance(l, dict)}
            if rr.get("sha12") not in shas:
                checks["run_claim"].fails.append("%s: %s capture is for bytes %s, card is %s"
                                                 % (cid, rr["status"], rr.get("sha12"), sorted(shas)))
            run = c.get("run")
            cmd = run.get("value") if rl.is_draft(run) else run
            if rr.get("command") != cmd:
                checks["run_claim"].fails.append("%s: capture is for command %r, card runs %r" % (cid, rr.get("command"), cmd))
            if not rr.get("date"):
                checks["run_claim"].fails.append("%s: %s without a date" % (cid, rr["status"]))
    n = {s: sum(1 for c in cards.values() if (c.get("run_result") or {}).get("status") == s) for s in ("RUN", "FAILED", "UNRUN")}
    checks["run_claim"].info.append("run_result RUN %d, FAILED %d, UNRUN %d" % (n["RUN"], n["FAILED"], n["UNRUN"]))

    # provenance: a non-placeholder AUTHOR value whose hash generate.py recorded as its own write
    for cid, c in cards.items():
        written = (c.get("_provenance") or {}).get("written") or {}
        for f in rl.CARD_AUTHOR_FIELDS:
            v = c.get(f)
            if rl.is_author_empty(v):
                continue
            if rl.is_draft(v):
                checks["author_provenance"].fails.append("%s: AUTHOR field %s carries a DRAFT mark" % (cid, f))
            elif written.get(f) == rl.field_hash(v):
                checks["author_provenance"].fails.append("%s: AUTHOR field %s was filled by the generator" % (cid, f))
    ap = apparatus.get("apparatus", {}) if isinstance(apparatus, dict) else {}
    for f in rl.APPARATUS_AUTHOR_FIELDS:
        if rl.is_draft(ap.get(f)):
            checks["author_provenance"].fails.append("APPARATUS: AUTHOR field %s carries a DRAFT mark" % f)

    # references
    ro = ap.get("read_order")
    if isinstance(ro, list):
        for x in ro:
            if x not in cards:
                checks["references"].fails.append("read_order names missing card %s" % x)
    for f in ap.get("faces") or []:
        if isinstance(f, dict):
            if f.get("id") not in cards:
                checks["references"].fails.append("faces names missing card %s" % f.get("id"))
            elif f.get("card") != "cards/%s.yaml" % f.get("id"):
                checks["references"].fails.append("face %s points at %s" % (f.get("id"), f.get("card")))
    face_ids = {f.get("id") for f in ap.get("faces") or [] if isinstance(f, dict)}
    for cid in sorted(set(cards) - face_ids):
        checks["references"].fails.append("card %s is not a face in APPARATUS.yaml" % cid)
    for cid, c in cards.items():
        rel = c.get("related")
        items = rel.get("value") if rl.is_draft(rel) else rel
        for r in items or []:
            rid = r.get("id") if isinstance(r, dict) else r
            if rid not in cards:
                checks["references"].fails.append("%s: related names missing card %s" % (cid, rid))

    # author gaps (report only)
    gaps = checks["author_gaps"]
    per = {cid: sum(1 for f in rl.CARD_AUTHOR_FIELDS if rl.is_author_empty(c.get(f))) for cid, c in cards.items()}
    hist: Dict[int, int] = {}
    for v in per.values():
        hist[v] = hist.get(v, 0) + 1
    gaps.info.append("AUTHOR fields per card: %d; empty, by count: %s"
                     % (len(rl.CARD_AUTHOR_FIELDS), ", ".join("%d empty -> %d cards" % (k, hist[k]) for k in sorted(hist, reverse=True))))
    gaps.info.append("APPARATUS AUTHOR fields empty: %s" % (
        ", ".join(f for f in rl.APPARATUS_AUTHOR_FIELDS if rl.is_author_empty(ap.get(f)) or ap.get(f) == rl.AUTHOR) or "none"))
    gaps.info.append("per_card " + json.dumps(per, sort_keys=True))
    return list(checks.values())


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", type=Path, default=rl.HERE, help="reasoning-layer directory")
    ap.add_argument("--inventory", type=Path, default=None, help="layer-3 TXT (default: pinned copy under --base)")
    ap.add_argument("--meta", type=Path, default=None, help="layer-3 metadata json")
    ap.add_argument("--json", action="store_true", help="machine-readable rows")
    ap.add_argument("--limit", type=int, default=15, help="FAIL lines printed per check (text mode)")
    a = ap.parse_args(argv)

    txt = a.inventory or a.base / "layer3" / rl.LAYER3_TXT.name
    meta = a.meta or a.base / "layer3" / rl.LAYER3_META.name
    try:
        pin = rl.check_layer3_pin(a.base / "layer3.sha256", a.base / "layer3") if a.inventory is None else []
        l3 = rl.load_layer3(txt, meta)
    except (OSError, rl.Layer3Error) as e:
        print("cannot run: %s" % e)
        return 3
    checks = validate(a.base, l3, pin)
    if a.json:
        print(json.dumps([c.to_dict() for c in checks], indent=2, ensure_ascii=False))
    else:
        for c in checks:
            state = "REPORT" if c.name == "author_gaps" else c.state
            print("%-18s %s" % (c.name, state))
            for line in c.info:
                if not line.startswith("per_card "):
                    print("    " + line)
            for line in c.fails[: a.limit]:
                print("    FAIL " + line)
            if len(c.fails) > a.limit:
                print("    ... %d more (use --json)" % (len(c.fails) - a.limit))
    return 1 if any(c.fails for c in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
