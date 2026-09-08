"""Register map: hold declared claims as LAYERS; refuse to combine layers whose
declarations do not permit it.

Ported from GIS / cartography, which already solved this: a layer will not
load without projection and datum, blank is a value, and a map that coarsens
silently is the failure mode.  This tool does NOT rank, judge truth, or infer.

Flow::

    dict (one layer)
      |
      | load_layer: EVERY required field or LayerDeclarationError naming
      |             every missing one.  No default, no guess, no warn-and-go.
      |     measurand   what was measured, not what it is called
      |     range       sector / domain where it holds
      |     instrument  what produced the number, INCLUDING scaffold / harness
      |                 (the datum field)
      |     grade       Grade enum, below
      |     resolution  coarseness, stored as a VALUE, never as an absence
      |
      |   MEASURED_DISCARDED without discard_rule -> loads, flag DISCARD_RULE_UNDECLARED
      |   IMPOSED            without reason       -> loads, flag REASON_UNDECLARED
      |   (worse than UNMEASURED for the reader: handling occurred, undeclared)
      v
    Layer
      |
      +-- can_join(a, b) -> JoinResult
      |     measurand, range, grade, then instrument LAST and reported explicitly
      |       COMMENSURABLE
      |       INCOMMENSURABLE(field)   values disagree on the named field
      |       UNDECLARED(field)        the named field is the sentinel UNDECLARED
      |     the two are never one return.  Different problems.
      |
      +-- project(layer, target_resolution) -> Layer
            coarsen ONLY; never upsample; integer factor only (no resampling)
            every dropped cell is a Discard with its rule attached
            result grade = MEASURED_DISCARDED, discard_rule names the step

Blank is a value::

    NODATA     region exists, not measured
    NOTFOUND   region measured, nothing there

Distinct, never collapsed to None / null / zero, and they survive project().
Unsurveyed regions render blank, never interpolated.

Declared absence vs missing: a required field may carry the sentinel string
``UNDECLARED`` (the declarant states the absence); a field that is simply
missing raises.  The first is data; the second is refused.

Downstream (out of scope, designed for): a directionality tool reads the
Discards and blanks.  Therefore every return here is a structured record,
every discard is retrievable with its rule, and NODATA / NOTFOUND survive
every operation.  Directionality is not implemented and not modelled here.

Cells: ``cells`` maps a coordinate to a value.  Coordinates are integer
tuples (JSON keys ``"3"`` or ``"3,7"``); values are JSON scalars or the two
blanks.  Resolution is the cell edge in the declarant's units.

stdlib only.  CC0.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from branch_set import _check_keys, _nonempty

SCHEMA_VERSION = "1.0"
UNDECLARED = "UNDECLARED"

REQUIRED_FIELDS: Tuple[str, ...] = ("measurand", "range", "instrument", "grade", "resolution")
OPTIONAL_FIELDS: Tuple[str, ...] = ("name", "discard_rule", "reason", "cells", "discards", "schema_version")
JOIN_ORDER: Tuple[str, ...] = ("measurand", "range", "grade", "instrument")   # instrument LAST


class Grade(str, Enum):
    MEASURED_PRESENT = "MEASURED_PRESENT"
    MEASURED_ABSENT = "MEASURED_ABSENT"
    MEASURED_DISCARDED = "MEASURED_DISCARDED"    # requires discard_rule
    UNMEASURED = "UNMEASURED"
    UNDERPOWERED = "UNDERPOWERED"
    IMPOSED = "IMPOSED"                          # requires reason


class Blank(str, Enum):
    NODATA = "NODATA"        # region exists, not measured
    NOTFOUND = "NOTFOUND"    # region measured, nothing there


class FlagCode(str, Enum):
    DISCARD_RULE_UNDECLARED = "DISCARD_RULE_UNDECLARED"
    REASON_UNDECLARED = "REASON_UNDECLARED"


class JoinVerdict(str, Enum):
    COMMENSURABLE = "COMMENSURABLE"
    INCOMMENSURABLE = "INCOMMENSURABLE"
    UNDECLARED = "UNDECLARED"


class LayerDeclarationError(ValueError):
    """A layer is missing required declaration(s).  ``missing`` names every one."""

    def __init__(self, missing: Sequence[str], detail: str = "") -> None:
        self.missing = tuple(missing)
        text = "layer refused; missing declaration(s): " + ", ".join(self.missing)
        if detail:
            text += f"; {detail}"
        super().__init__(text)


class ProjectionError(ValueError):
    """project() refused: upsampling, non-integer factor, or undeclared resolution."""


Coord = Tuple[int, ...]
CellValue = Union[int, float, str, bool, Blank]


# --------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Flag:
    code: FlagCode
    rule: str

    def to_dict(self) -> Dict[str, Any]:
        return {"code": self.code.value, "rule": self.rule}


@dataclass(frozen=True)
class Discard:
    """One dropped cell.  Retrievable with its rule, never merely counted."""

    coarse_cell: Coord
    source_cell: Coord
    value: CellValue
    rule: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "coarse_cell": _coord_key(self.coarse_cell),
            "source_cell": _coord_key(self.source_cell),
            "value": _value_out(self.value),
            "rule": self.rule,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Discard":
        _check_keys(data, ("coarse_cell", "source_cell", "value", "rule"), "discard")
        missing = [k for k in ("coarse_cell", "source_cell", "value", "rule") if k not in data]
        if missing:
            raise ValueError(f"discard missing field(s): {', '.join(missing)}")
        return cls(
            coarse_cell=_parse_coord(data["coarse_cell"]),
            source_cell=_parse_coord(data["source_cell"]),
            value=_value_in(data["value"]),
            rule=_nonempty(data["rule"], "discard rule"),
        )


@dataclass(frozen=True)
class Layer:
    measurand: str
    range: str
    instrument: str
    grade: Grade
    resolution: Union[int, float, str]          # a value; UNDECLARED sentinel allowed
    name: str = ""
    discard_rule: Optional[str] = None
    reason: Optional[str] = None
    cells: Dict[Coord, CellValue] = field(default_factory=dict)
    discards: Tuple[Discard, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "measurand", _nonempty(self.measurand, "measurand"))
        object.__setattr__(self, "range", _nonempty(self.range, "range"))
        object.__setattr__(self, "instrument", _nonempty(self.instrument, "instrument"))
        object.__setattr__(self, "grade", self.grade if isinstance(self.grade, Grade) else Grade(self.grade))
        object.__setattr__(self, "resolution", _check_resolution(self.resolution))
        if self.discard_rule is not None:
            object.__setattr__(self, "discard_rule", _nonempty(self.discard_rule, "discard_rule"))
        if self.reason is not None:
            object.__setattr__(self, "reason", _nonempty(self.reason, "reason"))
        cells: Dict[Coord, CellValue] = {}
        dims = None
        for coord, value in dict(self.cells).items():
            c = coord if isinstance(coord, tuple) else _parse_coord(coord)
            if dims is None:
                dims = len(c)
            elif len(c) != dims:
                raise ValueError("all cell coordinates must have the same dimension")
            cells[c] = _value_in(value)
        object.__setattr__(self, "cells", cells)
        object.__setattr__(self, "discards", tuple(self.discards))

    # ---- declaration state -------------------------------------------------

    @property
    def undeclared_fields(self) -> Tuple[str, ...]:
        """Required fields carrying the UNDECLARED sentinel (declared absence)."""

        out = [f for f in ("measurand", "range", "instrument") if getattr(self, f) == UNDECLARED]
        if self.resolution == UNDECLARED:
            out.append("resolution")
        return tuple(out)

    @property
    def flags(self) -> Tuple[Flag, ...]:
        flags: List[Flag] = []
        if self.grade is Grade.MEASURED_DISCARDED and self.discard_rule is None:
            flags.append(Flag(
                FlagCode.DISCARD_RULE_UNDECLARED,
                "grade MEASURED_DISCARDED with no discard_rule: a discard happened and "
                "its rule was not declared.  Worse than UNMEASURED for the reader: "
                "handling occurred.",
            ))
        if self.grade is Grade.IMPOSED and self.reason is None:
            flags.append(Flag(
                FlagCode.REASON_UNDECLARED,
                "grade IMPOSED with no reason: a constraint was adopted and its reason "
                "was not declared.  Worse than UNMEASURED for the reader: a choice was made.",
            ))
        return tuple(flags)

    # ---- blanks ------------------------------------------------------------

    def cells_with(self, blank: Blank) -> Tuple[Coord, ...]:
        return tuple(sorted(c for c, v in self.cells.items() if v is blank))

    # ---- serialisation -----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "name": self.name,
            "measurand": self.measurand,
            "range": self.range,
            "instrument": self.instrument,
            "grade": self.grade.value,
            "resolution": self.resolution,
            "discard_rule": self.discard_rule,
            "reason": self.reason,
            "cells": {_coord_key(c): _value_out(v) for c, v in sorted(self.cells.items())},
            "discards": [d.to_dict() for d in self.discards],
            "undeclared_fields": list(self.undeclared_fields),
            "flags": [f.to_dict() for f in self.flags],
        }

    def format(self) -> str:
        """Render.  NODATA prints blank, NOTFOUND prints '-'.  Nothing is interpolated."""

        head = [
            f"LAYER {self.name or '(unnamed)'}",
            f"  measurand   {self.measurand}",
            f"  range       {self.range}",
            f"  instrument  {self.instrument}",
            f"  grade       {self.grade.value}",
            f"  resolution  {self.resolution}",
        ]
        if self.discard_rule:
            head.append(f"  discard_rule {self.discard_rule}")
        if self.reason:
            head.append(f"  reason      {self.reason}")
        for flag in self.flags:
            head.append(f"  FLAG {flag.code.value}: {flag.rule}")
        if self.undeclared_fields:
            head.append(f"  undeclared  {', '.join(self.undeclared_fields)}")
        if self.cells:
            head.append("  cells")
            for coord, value in sorted(self.cells.items()):
                shown = "" if value is Blank.NODATA else "-" if value is Blank.NOTFOUND else str(value)
                head.append(f"    {_coord_key(coord):<10} {shown}")
        if self.discards:
            head.append(f"  discards ({len(self.discards)}, each with rule)")
            for d in self.discards:
                head.append(f"    {_coord_key(d.source_cell)} -> {_coord_key(d.coarse_cell)} "
                            f"dropped {_value_out(d.value)!r}: {d.rule}")
        return "\n".join(head)


@dataclass(frozen=True)
class JoinResult:
    """Structured.  ``comparisons`` holds every field even when an early field blocks."""

    verdict: JoinVerdict
    field: Optional[str]
    comparisons: Dict[str, str]        # field -> match | differ | undeclared
    instrument_checked: bool
    resolution_match: bool
    rule: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "field": self.field,
            "comparisons": dict(self.comparisons),
            "instrument_checked": self.instrument_checked,
            "resolution_match": self.resolution_match,
            "rule": self.rule,
        }


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _coord_key(coord: Coord) -> str:
    return ",".join(str(c) for c in coord)


def _parse_coord(raw: Any) -> Coord:
    if isinstance(raw, tuple):
        return tuple(int(c) for c in raw)
    if isinstance(raw, list):
        return tuple(int(c) for c in raw)
    if isinstance(raw, bool):
        raise ValueError(f"cell coordinate must be integer(s); got {raw!r}")
    if isinstance(raw, int):
        return (raw,)
    if isinstance(raw, str):
        try:
            return tuple(int(part.strip()) for part in raw.split(","))
        except ValueError as exc:
            raise ValueError(f"cell coordinate must be integer(s) like '3' or '3,7'; got {raw!r}") from exc
    raise ValueError(f"cell coordinate must be integer(s); got {raw!r}")


def _value_in(value: Any) -> CellValue:
    if isinstance(value, Blank):
        return value
    if value is None:
        raise ValueError("cell value None is not allowed: use NODATA (not measured) or NOTFOUND (measured, nothing there)")
    if isinstance(value, str) and value in (Blank.NODATA.value, Blank.NOTFOUND.value):
        return Blank(value)
    if isinstance(value, (int, float, str, bool)):
        return value
    raise ValueError(f"cell value must be a scalar or a blank; got {type(value).__name__}")


def _value_out(value: CellValue) -> Any:
    return value.value if isinstance(value, Blank) else value


def _check_resolution(value: Any) -> Union[int, float, str]:
    if value == UNDECLARED:
        return UNDECLARED
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("resolution must be a positive number or the sentinel UNDECLARED")
    if not value > 0 or value != value or value in (float("inf"), float("-inf")):
        raise ValueError("resolution must be a positive finite number")
    return value


# --------------------------------------------------------------------------
# FUNCTION 1
# --------------------------------------------------------------------------


def load_layer(data: Mapping[str, Any]) -> Layer:
    """dict -> Layer, or LayerDeclarationError naming EVERY missing required field."""

    if not isinstance(data, Mapping):
        raise LayerDeclarationError(REQUIRED_FIELDS, "input is not a mapping")
    _check_keys(data, REQUIRED_FIELDS + OPTIONAL_FIELDS, "layer")
    if "schema_version" in data and data["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported layer schema_version; expected {SCHEMA_VERSION!r}")
    missing = [f for f in REQUIRED_FIELDS if f not in data or data[f] is None
               or (isinstance(data[f], str) and not data[f].strip())]
    if missing:
        raise LayerDeclarationError(missing)
    discards = tuple(Discard.from_dict(d) for d in data.get("discards", []) or [])
    return Layer(
        measurand=data["measurand"],
        range=data["range"],
        instrument=data["instrument"],
        grade=_grade(data["grade"]),
        resolution=data["resolution"],
        name=str(data.get("name", "") or ""),
        discard_rule=data.get("discard_rule"),
        reason=data.get("reason"),
        cells=dict(data.get("cells", {}) or {}),
        discards=discards,
    )


def _grade(value: Any) -> Grade:
    try:
        return value if isinstance(value, Grade) else Grade(value)
    except ValueError as exc:
        raise ValueError(f"grade must be one of: {', '.join(g.value for g in Grade)}") from exc


def load_layer_file(path: Union[str, Path]) -> Layer:
    with open(path, encoding="utf-8") as fh:
        return load_layer(json.load(fh))


# --------------------------------------------------------------------------
# FUNCTION 2
# --------------------------------------------------------------------------


def can_join(a: Layer, b: Layer) -> JoinResult:
    """Compare declarations in JOIN_ORDER; instrument LAST and reported explicitly.

    Every field is compared and recorded even when an earlier field blocks, so
    the result is a full table, not just the first problem.
    """

    comparisons: Dict[str, str] = {}
    blocking: Optional[Tuple[JoinVerdict, str]] = None
    for name in JOIN_ORDER:
        va, vb = getattr(a, name), getattr(b, name)
        if name == "grade":
            va, vb = va.value, vb.value
        if va == UNDECLARED or vb == UNDECLARED:
            state = "undeclared"
        elif va == vb:
            state = "match"
        else:
            state = "differ"
        comparisons[name] = state
        if blocking is None and state != "match":
            blocking = (JoinVerdict.UNDECLARED if state == "undeclared" else JoinVerdict.INCOMMENSURABLE, name)

    resolution_match = (a.resolution == b.resolution) and a.resolution != UNDECLARED
    inst = comparisons["instrument"]
    inst_note = {
        "match": "instrument checked last: match",
        "differ": "instrument checked last: DIFFERS (datum offset)",
        "undeclared": "instrument checked last: UNDECLARED on at least one side",
    }[inst]

    if blocking is None:
        return JoinResult(
            JoinVerdict.COMMENSURABLE, None, comparisons, True, resolution_match,
            rule=f"measurand, range, grade agree; {inst_note}; "
                 f"resolution {'matches' if resolution_match else 'differs (project() before overlay)'}",
        )
    verdict, name_ = blocking
    if verdict is JoinVerdict.UNDECLARED:
        rule = f"UNDECLARED({name_}): the field is declared absent on at least one side; {inst_note}"
    else:
        rule = (f"INCOMMENSURABLE({name_}): {getattr(a, name_) if name_ != 'grade' else a.grade.value!r} "
                f"vs {getattr(b, name_) if name_ != 'grade' else b.grade.value!r}; {inst_note}")
    return JoinResult(verdict, name_, comparisons, True, resolution_match, rule=rule)


# --------------------------------------------------------------------------
# FUNCTION 3
# --------------------------------------------------------------------------


def project(layer: Layer, target_resolution: Union[int, float]) -> Layer:
    """Coarsen ONLY.  Never upsample.  Integer factor only.  Every drop is a Discard.

    Kept value per coarse cell, by declared precedence: the measured value of
    the lowest-coordinate surveyed sub-cell; else NOTFOUND if any sub-cell was
    measured and found nothing; else NODATA.  Everything not kept is a
    Discard carrying its rule.  Nothing is averaged or interpolated.
    """

    if layer.resolution == UNDECLARED:
        raise ProjectionError("cannot project: resolution is UNDECLARED")
    _check_resolution(target_resolution)
    if target_resolution <= layer.resolution:
        raise ProjectionError(
            f"refused: target resolution {target_resolution} is not coarser than {layer.resolution}; "
            "never upsample"
        )
    ratio = target_resolution / layer.resolution
    factor = int(round(ratio))
    if abs(ratio - factor) > 1e-9 or factor < 2:
        raise ProjectionError(
            f"refused: factor {ratio:g} is not an integer >= 2; a non-integer factor needs resampling, "
            "which is interpolation"
        )
    step = f"coarsen x{factor}: {layer.resolution} -> {target_resolution}"

    groups: Dict[Coord, List[Tuple[Coord, CellValue]]] = {}
    for coord, value in sorted(layer.cells.items()):
        coarse = tuple(c // factor for c in coord)
        groups.setdefault(coarse, []).append((coord, value))

    cells: Dict[Coord, CellValue] = {}
    discards: List[Discard] = list(layer.discards)
    for coarse, members in sorted(groups.items()):
        measured = [(c, v) for c, v in members if not isinstance(v, Blank)]
        notfound = [(c, v) for c, v in members if v is Blank.NOTFOUND]
        if measured:
            keep_coord, keep_val = measured[0]
            why = "kept: measured value of lowest-coordinate surveyed sub-cell"
        elif notfound:
            keep_coord, keep_val = notfound[0]
            why = "kept: NOTFOUND (region measured, nothing there)"
        else:
            keep_coord, keep_val = members[0]
            why = "kept: NODATA (no sub-cell measured)"
        cells[coarse] = keep_val
        for c, v in members:
            if c == keep_coord:
                continue
            discards.append(Discard(
                coarse_cell=coarse, source_cell=c, value=v,
                rule=f"{step}; {why}; dropped sub-cell {_coord_key(c)} value {_value_out(v)!r}",
            ))

    return Layer(
        measurand=layer.measurand,
        range=layer.range,
        instrument=layer.instrument,
        grade=Grade.MEASURED_DISCARDED,
        resolution=target_resolution,
        name=layer.name,
        discard_rule=f"{step}; source grade {layer.grade.value}; "
                     f"{len(discards) - len(layer.discards)} cell(s) dropped, each retrievable in discards",
        reason=layer.reason,
        cells=cells,
        discards=tuple(discards),
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p_load = sub.add_parser("load", help="load one layer JSON; refuse if any declaration is missing")
    p_load.add_argument("layer")
    p_load.add_argument("--json", action="store_true")
    p_join = sub.add_parser("join", help="can these two layers be combined?")
    p_join.add_argument("layer_a")
    p_join.add_argument("layer_b")
    p_join.add_argument("--json", action="store_true")
    p_proj = sub.add_parser("project", help="coarsen a layer; every drop recorded")
    p_proj.add_argument("layer")
    p_proj.add_argument("--to", type=float, required=True, help="target resolution (coarser)")
    p_proj.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.command == "load":
            layer = load_layer_file(args.layer)
            print(json.dumps(layer.to_dict(), indent=2, sort_keys=True) if args.json else layer.format())
        elif args.command == "join":
            result = can_join(load_layer_file(args.layer_a), load_layer_file(args.layer_b))
            print(json.dumps(result.to_dict(), indent=2, sort_keys=True) if args.json
                  else f"{result.verdict.value}" + (f"({result.field})" if result.field else "") + f": {result.rule}")
        else:
            target = int(args.to) if float(args.to).is_integer() else args.to
            layer = project(load_layer_file(args.layer), target)
            print(json.dumps(layer.to_dict(), indent=2, sort_keys=True) if args.json else layer.format())
    except (LayerDeclarationError, ProjectionError, ValueError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return 0


__all__ = [
    "JOIN_ORDER",
    "OPTIONAL_FIELDS",
    "REQUIRED_FIELDS",
    "SCHEMA_VERSION",
    "UNDECLARED",
    "Blank",
    "Discard",
    "Flag",
    "FlagCode",
    "Grade",
    "JoinResult",
    "JoinVerdict",
    "Layer",
    "LayerDeclarationError",
    "ProjectionError",
    "can_join",
    "load_layer",
    "load_layer_file",
    "project",
]


if __name__ == "__main__":
    sys.exit(main())
