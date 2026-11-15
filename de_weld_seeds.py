"""
de_weld_seeds.py -- five seed cases for de_weld.py. CC0, stdlib only.

CONSTRUCTED. These are model-authored readings, every one PROPOSED, offered
as worked examples of the record shape, not as findings about the words.
The sentences are invented to give each term a use; none is quoted from a
source. The splits are one reader's: a different reader may declare
different axes, and that disagreement is the instrument's input, not an
error in it. Nothing here cites evidence; evidence slots are void
throughout, which is why descriptive_evidence reads VOID or
NO_DESCRIPTIVE_CLAIM on every seed.
"""
from de_weld import Axis, AxisClaim, Coupling, Input, Need, Relation, Residue, Scope

P = "PROPOSED"
SRC = "CONSTRUCTED seed, model-authored reading (Claude), 2026-11-15"

SEEDS = (
    Input(
        term="good weapon",
        sentence="That is a good weapon.",
        axes=(
            AxisClaim(Axis.QUALITY, "performs its function reliably and with effect",
                      Scope(use="as a weapon"), status=P),
            AxisClaim(Axis.DESCRIPTIVE, "has the properties its design function requires",
                      Scope(use="as a weapon"), status=P),
            AxisClaim(Axis.HARM, "its function is to injure or destroy",
                      Scope(use="as a weapon"), status=P),
            AxisClaim(Axis.MORAL, None, status=P),
        ),
        couplings=(
            Coupling(0, 1, Relation.COUPLED, "functional quality rests on the described properties"),
            Coupling(0, 2, Relation.COUPLED, "better at its function = more capable of harm"),
            Coupling(0, 3, Relation.CONFLICTING,
                     "'good' at the function can be read as morally good; the sentence states no moral claim"),
        ),
        residue=(Residue("whether the sentence carries a moral judgement or only a functional one",
                         "2026-11-15", ()),),
        used_in_judgment=True,
        provenance=SRC,
    ),
    Input(
        term="artist",
        sentence="She is a real artist.",
        axes=(
            AxisClaim(Axis.DESCRIPTIVE, "makes art as a practice", Scope(who="she"), status=P),
            AxisClaim(Axis.QUALITY, "makes it at a high standard ('real')", Scope(who="she"),
                      status=P),
            AxisClaim(Axis.AESTHETIC, None, status=P),
        ),
        couplings=(Coupling(0, 1, Relation.COUPLED, "the honorific rides on the occupation word"),),
        residue=(Residue("what standard 'real' measures against, and whose", "2026-11-15",
                         (Need.AUDIT,)),),
        used_in_judgment=True,
        provenance=SRC,
    ),
    Input(
        term="efficient",
        sentence="The new engine is efficient.",
        axes=(
            AxisClaim(Axis.DESCRIPTIVE, "a ratio of useful output to input is high",
                      Scope(use="engine operation"), status=P),
            AxisClaim(Axis.ABUNDANCE, "uses less of a resource per unit of work",
                      Scope(use="engine operation"), status=P),
            AxisClaim(Axis.QUALITY, "is a better engine", status=P),
        ),
        couplings=(Coupling(0, 1, Relation.COUPLED, "the ratio is what 'less per unit' means"),),
        residue=(Residue("which ratio, over which boundary (fuel only? manufacture? end of life?), "
                         "against which comparison engine", "2026-11-15",
                         (Need.ENGINEERING, Need.AUDIT)),),
        used_in_judgment=True,
        provenance=SRC,
    ),
    Input(
        term="neutral",
        sentence="The report is neutral.",
        axes=(
            AxisClaim(Axis.QUALITY, "is fair; takes no side", status=P),
            AxisClaim(Axis.MORAL, "is free of bias, which is presented as a virtue", status=P),
        ),
        couplings=(Coupling(0, 1, Relation.COUPLED),),
        residue=(Residue("neutral relative to which positions, measured how", "2026-11-15",
                         (Need.AUDIT,)),),
        used_in_judgment=True,
        provenance=SRC,
    ),
    Input(
        term="safe",
        sentence="The bridge is safe.",
        axes=(
            AxisClaim(Axis.DESCRIPTIVE, "its capacity exceeds the expected load by a margin",
                      Scope(where="this bridge"), status=P),
            AxisClaim(Axis.HARM, "the chance of failure causing injury is low",
                      Scope(where="this bridge"), status=P),
            AxisClaim(Axis.MORAL, "the remaining risk is acceptable to impose on users", status=P),
        ),
        couplings=(
            Coupling(0, 1, Relation.COUPLED, "margin is the reason given for low chance of harm"),
            Coupling(1, 2, Relation.COUPLED, "'low' becomes 'acceptable' only under a threshold"),
        ),
        residue=(Residue("what margin, for which loads (traffic, flood, ice), over what period, and "
                         "who sets the acceptable-risk threshold", "2026-11-15",
                         (Need.SCIENCE, Need.ENGINEERING, Need.AUDIT)),),
        used_in_judgment=True,
        provenance=SRC,
    ),
)
