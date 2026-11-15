"""
de_weld.py -- separate the axes a single evaluative term welds together.
CC0, stdlib only, Python >= 3.8.

A term such as "safe" or "efficient" can carry a description, a judgement of
quality, a moral judgement and a harm estimate in one word. This module
records the term in the sentence it is used in, split into one claim per
axis, and keeps every slot, void where unknown. It decides nothing about the
term's meaning: the axis claims are declared by the caller. What it computes
from them is the class, the cross-axis pairs and the flag, each with the rule
that produced it.

Shape
-----
    INPUT  term + the sentence it is used in
           + declared axis claims (claim, scope, evidence, status)
           + declared couplings between claims, residue, judgment use
      |
      | 1 CLASSIFY  from the declared axes, never from a word list:
      |      descriptive claim only + context carries a valuation -> VALUE_ASSOCIATED
      |      descriptive claim only                                -> DESCRIPTIVE
      |      evaluative claim(s) only                              -> THIN
      |      descriptive AND evaluative claims                     -> THICK
      |      no claim with content                                 -> UNCLASSIFIED
      | 2 SPLIT     axes: descriptive | moral | quality | abundance |
      |             aesthetic | harm | other (name void until given)
      | 3 PER AXIS  claim, scope (who, where, when, use), evidence, status
      | 4 CROSS     every pair of axis claims: INDEPENDENT / COUPLED /
      |             CONFLICTING as declared, UNDECLARED otherwise
      | 5 RESIDUE   unresolved and contested at a date -> what would settle it:
      |             SCIENCE / ENGINEERING / AUDIT (a set; empty = not stated)
      | 6 FLAG      THIN term used in a judgment -> UNGROUNDED_EVALUATION
      v
    OUTPUT DeWeld record, to_dict / from_dict, all slots kept

Refusals that are deliberate
----------------------------
    a word list deciding the class          -> none here; the term string
                                               reaches no classification
    an undeclared pair of axes              -> UNDECLARED, never INDEPENDENT
    a void claim on a declared axis         -> kept as void, not dropped;
                                               counts as no content
    descriptive claim without evidence      -> recorded; descriptive_evidence
                                               reads VOID, separate from the flag
    other axis with no name                 -> kept with name None (void)
    a flag on a non-THIN term               -> none; only the stated rule fires
"""
from __future__ import annotations

import itertools
import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Tuple

from branch_set import _check_keys

SCHEMA_VERSION = "1.0"


class Axis(str, Enum):
    DESCRIPTIVE = "descriptive"
    MORAL = "moral"
    QUALITY = "quality"
    ABUNDANCE = "abundance"
    AESTHETIC = "aesthetic"
    HARM = "harm"
    OTHER = "other"


EVALUATIVE_AXES = frozenset(a.value for a in Axis if a != Axis.DESCRIPTIVE)


class TermClass(str, Enum):
    THIN = "thin"
    THICK = "thick"
    DESCRIPTIVE = "descriptive"
    VALUE_ASSOCIATED = "value_associated"
    UNCLASSIFIED = "unclassified"


class Status(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    PROPOSED = "PROPOSED"


class Relation(str, Enum):
    INDEPENDENT = "independent"
    COUPLED = "coupled"
    CONFLICTING = "conflicting"
    UNDECLARED = "undeclared"


class Need(str, Enum):
    SCIENCE = "science"
    ENGINEERING = "engineering"
    AUDIT = "audit"


class Flag(str, Enum):
    UNGROUNDED_EVALUATION = "ungrounded_evaluation"


def _opt_str(value: Any, name: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string or None")
    return value if value.strip() else None


def _required(value: Any, name: str) -> str:
    v = _opt_str(value, name)
    if v is None:
        raise ValueError(f"{name} is required")
    return v


@dataclass(frozen=True)
class Scope:
    who: Optional[str] = None
    where: Optional[str] = None
    when: Optional[str] = None
    use: Optional[str] = None

    def __post_init__(self) -> None:
        for name in ("who", "where", "when", "use"):
            object.__setattr__(self, name, _opt_str(getattr(self, name), name))

    def void_fields(self) -> Tuple[str, ...]:
        return tuple(n for n in ("who", "where", "when", "use") if getattr(self, n) is None)

    def to_dict(self) -> Dict[str, Any]:
        return {"who": self.who, "where": self.where, "when": self.when, "use": self.use}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Scope":
        _check_keys(data, ("who", "where", "when", "use"), "scope")
        return cls(**{k: data.get(k) for k in ("who", "where", "when", "use")})


@dataclass(frozen=True)
class AxisClaim:
    axis: Axis
    claim: Optional[str] = None
    scope: Scope = field(default_factory=Scope)
    evidence: Optional[str] = None
    status: Optional[Status] = None
    other_name: Optional[str] = None  # used only when axis is OTHER; void until given

    def __post_init__(self) -> None:
        object.__setattr__(self, "axis", Axis(self.axis))
        object.__setattr__(self, "claim", _opt_str(self.claim, "claim"))
        object.__setattr__(self, "evidence", _opt_str(self.evidence, "evidence"))
        if self.status is not None:
            object.__setattr__(self, "status", Status(self.status))
        if not isinstance(self.scope, Scope):
            raise TypeError("scope must be a Scope")
        name = _opt_str(self.other_name, "other_name")
        if name is not None and self.axis != Axis.OTHER:
            raise ValueError("other_name is only for the OTHER axis")
        object.__setattr__(self, "other_name", name)

    @property
    def has_content(self) -> bool:
        return self.claim is not None

    def label(self) -> str:
        if self.axis == Axis.OTHER:
            return f"other:{self.other_name}" if self.other_name else "other:(void)"
        return self.axis.value

    def to_dict(self) -> Dict[str, Any]:
        return {"axis": self.axis.value, "claim": self.claim, "scope": self.scope.to_dict(),
                "evidence": self.evidence,
                "status": self.status.value if self.status else None,
                "other_name": self.other_name}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AxisClaim":
        _check_keys(data, ("axis", "claim", "scope", "evidence", "status", "other_name"),
                    "axis claim")
        return cls(axis=Axis(data["axis"]), claim=data.get("claim"),
                   scope=Scope.from_dict(data.get("scope") or {}),
                   evidence=data.get("evidence"), status=data.get("status"),
                   other_name=data.get("other_name"))


@dataclass(frozen=True)
class Coupling:
    """A declared relation between two axis claims, by index into the record's axes."""
    a: int
    b: int
    relation: Relation
    note: Optional[str] = None

    def __post_init__(self) -> None:
        if not (isinstance(self.a, int) and isinstance(self.b, int)) or self.a == self.b:
            raise ValueError("a coupling joins two different axis indices")
        lo, hi = sorted((self.a, self.b))
        object.__setattr__(self, "a", lo)
        object.__setattr__(self, "b", hi)
        object.__setattr__(self, "relation", Relation(self.relation))
        if self.relation == Relation.UNDECLARED:
            raise ValueError("UNDECLARED is computed for missing pairs; do not declare it")
        object.__setattr__(self, "note", _opt_str(self.note, "note"))

    def to_dict(self) -> Dict[str, Any]:
        return {"a": self.a, "b": self.b, "relation": self.relation.value, "note": self.note}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Coupling":
        _check_keys(data, ("a", "b", "relation", "note"), "coupling")
        return cls(a=data["a"], b=data["b"], relation=Relation(data["relation"]),
                   note=data.get("note"))


@dataclass(frozen=True)
class Residue:
    question: str
    contested_as_of: Optional[str] = None   # a date, as given
    needs: Tuple[Need, ...] = ()             # empty = not stated, kept apart from a stated need

    def __post_init__(self) -> None:
        object.__setattr__(self, "question", _required(self.question, "question"))
        object.__setattr__(self, "contested_as_of", _opt_str(self.contested_as_of, "contested_as_of"))
        object.__setattr__(self, "needs", tuple(sorted({Need(n) for n in self.needs},
                                                       key=lambda n: n.value)))

    def to_dict(self) -> Dict[str, Any]:
        return {"question": self.question, "contested_as_of": self.contested_as_of,
                "needs": [n.value for n in self.needs]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Residue":
        _check_keys(data, ("question", "contested_as_of", "needs"), "residue")
        return cls(question=data["question"], contested_as_of=data.get("contested_as_of"),
                   needs=tuple(data.get("needs") or ()))


@dataclass(frozen=True)
class Input:
    """Everything the caller declares about one use of one term."""
    term: str
    sentence: Optional[str]
    axes: Tuple[AxisClaim, ...] = ()
    couplings: Tuple[Coupling, ...] = ()
    residue: Tuple[Residue, ...] = ()
    used_in_judgment: Optional[bool] = None  # None = not stated
    context_valuation: Optional[str] = None  # a valuation the sentence attaches, not the term
    provenance: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "term", _required(self.term, "term"))
        object.__setattr__(self, "sentence", _opt_str(self.sentence, "sentence"))
        object.__setattr__(self, "axes", tuple(self.axes))
        object.__setattr__(self, "couplings", tuple(self.couplings))
        object.__setattr__(self, "residue", tuple(self.residue))
        object.__setattr__(self, "context_valuation",
                           _opt_str(self.context_valuation, "context_valuation"))
        object.__setattr__(self, "provenance", _opt_str(self.provenance, "provenance"))
        if self.used_in_judgment is not None and not isinstance(self.used_in_judgment, bool):
            raise TypeError("used_in_judgment must be True, False or None")
        n = len(self.axes)
        seen = set()
        for c in self.couplings:
            if c.b >= n:
                raise ValueError(f"coupling refers to axis {c.b}; only {n} axes declared")
            if (c.a, c.b) in seen:
                raise ValueError(f"pair ({c.a}, {c.b}) declared twice")
            seen.add((c.a, c.b))

    def to_dict(self) -> Dict[str, Any]:
        return {"term": self.term, "sentence": self.sentence,
                "axes": [a.to_dict() for a in self.axes],
                "couplings": [c.to_dict() for c in self.couplings],
                "residue": [r.to_dict() for r in self.residue],
                "used_in_judgment": self.used_in_judgment,
                "context_valuation": self.context_valuation, "provenance": self.provenance}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Input":
        _check_keys(data, ("term", "sentence", "axes", "couplings", "residue",
                           "used_in_judgment", "context_valuation", "provenance"), "input")
        return cls(term=data["term"], sentence=data.get("sentence"),
                   axes=tuple(AxisClaim.from_dict(a) for a in data.get("axes") or ()),
                   couplings=tuple(Coupling.from_dict(c) for c in data.get("couplings") or ()),
                   residue=tuple(Residue.from_dict(r) for r in data.get("residue") or ()),
                   used_in_judgment=data.get("used_in_judgment"),
                   context_valuation=data.get("context_valuation"),
                   provenance=data.get("provenance"))


# ---- the six steps -------------------------------------------------------------

def classify(inp: Input) -> Tuple[TermClass, str]:
    """Class from the declared axes only. The term string is not read."""
    desc = any(a.axis == Axis.DESCRIPTIVE and a.has_content for a in inp.axes)
    ev = any(a.axis.value in EVALUATIVE_AXES and a.has_content for a in inp.axes)
    if desc and ev:
        return TermClass.THICK, "descriptive claim AND evaluative claim(s) declared"
    if ev:
        return TermClass.THIN, "evaluative claim(s) declared, no descriptive claim"
    if desc and inp.context_valuation is not None:
        return (TermClass.VALUE_ASSOCIATED,
                "descriptive claim only; the sentence attaches a valuation (context_valuation)")
    if desc:
        return TermClass.DESCRIPTIVE, "descriptive claim only, no valuation declared"
    return TermClass.UNCLASSIFIED, "no axis claim with content declared"


def cross_axis(inp: Input) -> Tuple[Dict[str, Any], ...]:
    """Every pair of declared axes; a pair not declared reads UNDECLARED."""
    declared = {(c.a, c.b): c for c in inp.couplings}
    out = []
    for i, j in itertools.combinations(range(len(inp.axes)), 2):
        c = declared.get((i, j))
        out.append({"a": i, "b": j, "a_axis": inp.axes[i].label(), "b_axis": inp.axes[j].label(),
                    "relation": (c.relation if c else Relation.UNDECLARED).value,
                    "note": c.note if c else None})
    return tuple(out)


def flags(inp: Input, term_class: TermClass) -> Tuple[Tuple[Flag, ...], str]:
    if term_class == TermClass.THIN and inp.used_in_judgment is True:
        return ((Flag.UNGROUNDED_EVALUATION,),
                "THIN term used in a judgment: no descriptive axis claim declared")
    if term_class == TermClass.THIN and inp.used_in_judgment is None:
        return ((), "THIN term; whether it is used in a judgment is not stated, so no flag")
    return ((), f"{term_class.value}: the ungrounded-evaluation rule applies to THIN terms only")


def descriptive_evidence(inp: Input) -> str:
    claims = [a for a in inp.axes if a.axis == Axis.DESCRIPTIVE and a.has_content]
    if not claims:
        return "NO_DESCRIPTIVE_CLAIM"
    return "PRESENT" if any(a.evidence is not None for a in claims) else "VOID"


@dataclass(frozen=True)
class DeWeld:
    input: Input
    term_class: TermClass
    class_rule: str
    cross: Tuple[Dict[str, Any], ...]
    flags: Tuple[Flag, ...]
    flag_rule: str
    descriptive_evidence: str
    void_slots: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, "input": self.input.to_dict(),
                "term_class": self.term_class.value, "class_rule": self.class_rule,
                "cross_axis": list(self.cross), "flags": [f.value for f in self.flags],
                "flag_rule": self.flag_rule, "descriptive_evidence": self.descriptive_evidence,
                "void_slots": list(self.void_slots)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DeWeld":
        _check_keys(data, ("schema_version", "input", "term_class", "class_rule", "cross_axis",
                           "flags", "flag_rule", "descriptive_evidence", "void_slots"), "de-weld record")
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        rec = de_weld(Input.from_dict(data["input"]))
        stored = dict(data)
        if rec.to_dict() != stored:
            raise ValueError("stored derived fields do not match a re-derivation from the input")
        return rec


def _void_slots(inp: Input) -> Tuple[str, ...]:
    out = []
    if inp.sentence is None:
        out.append("sentence")
    if inp.used_in_judgment is None:
        out.append("used_in_judgment")
    for i, a in enumerate(inp.axes):
        pre = f"axes[{i}]({a.label()})"
        for name in ("claim", "evidence", "status"):
            if getattr(a, name) is None:
                out.append(f"{pre}.{name}")
        out.extend(f"{pre}.scope.{s}" for s in a.scope.void_fields())
        if a.axis == Axis.OTHER and a.other_name is None:
            out.append(f"{pre}.other_name")
    for i, r in enumerate(inp.residue):
        if r.contested_as_of is None:
            out.append(f"residue[{i}].contested_as_of")
        if not r.needs:
            out.append(f"residue[{i}].needs")
    return tuple(out)


def de_weld(inp: Input) -> DeWeld:
    tc, rule = classify(inp)
    fl, frule = flags(inp, tc)
    return DeWeld(input=inp, term_class=tc, class_rule=rule, cross=cross_axis(inp),
                  flags=fl, flag_rule=frule, descriptive_evidence=descriptive_evidence(inp),
                  void_slots=_void_slots(inp))


def render(rec: DeWeld) -> str:
    i = rec.input
    lines = [f"term: {i.term!r}   sentence: {i.sentence!r}",
             f"class: {rec.term_class.value}   ({rec.class_rule})"]
    for k, a in enumerate(i.axes):
        lines.append(f"  [{k}] {a.label():12s} claim={a.claim!r} evidence={a.evidence!r} "
                     f"status={a.status.value if a.status else None} scope={a.scope.to_dict()}")
    for c in rec.cross:
        lines.append(f"  cross {c['a']}-{c['b']} {c['a_axis']}/{c['b_axis']}: {c['relation']}")
    for r in i.residue:
        lines.append(f"  residue: {r.question} (as of {r.contested_as_of}; needs "
                     f"{[n.value for n in r.needs] or 'not stated'})")
    lines.append(f"flags: {[f.value for f in rec.flags]}   ({rec.flag_rule})")
    lines.append(f"descriptive evidence: {rec.descriptive_evidence}")
    lines.append(f"void slots ({len(rec.void_slots)}): {', '.join(rec.void_slots) or 'none'}")
    return "\n".join(lines)


def main(argv) -> int:
    if "--selftest" in argv:
        print("de_weld.py has no selftest; run: python3 -m unittest tests.test_de_weld -v")
        return 2
    # Run through the imported module, not __main__: the seeds import `de_weld`,
    # and two copies of the enums would otherwise meet (see the test that runs
    # this file as a script).
    import de_weld as M
    if argv and argv[0] == "seeds":
        import de_weld_seeds
        for inp in de_weld_seeds.SEEDS:
            print(M.render(M.de_weld(inp)))
            print()
        return 0
    if len(argv) == 1 and not argv[0].startswith("-"):
        with open(argv[0], encoding="utf-8") as fh:
            data = json.load(fh)
        items = data if isinstance(data, list) else [data]
        print(json.dumps([M.de_weld(M.Input.from_dict(d)).to_dict() for d in items], indent=1))
        return 0
    print(__doc__)
    print("usage: python3 de_weld.py seeds | INPUT.json")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
