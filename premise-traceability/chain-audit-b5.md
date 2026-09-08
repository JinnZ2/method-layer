# CHAIN AUDIT — B5 REVERSIBILITY
# The forced sequence, each link graded by epistemic origin.

CC0. Added 2026-09-08.

Design brief: take the strongest consequence node. State the forced
sequence — because it had to be done THIS way, then THIS has to be done
that way, which means THIS follows. Then grade each link by what it
actually is.

WHY B5: highest cross-reference count in boundary-grqm.md. One import,
two failures, in two literatures that do not cite each other.

Grade definitions: see GRADES.md.

---

## THE FORCED SEQUENCE

L1  The microscopic equations are time-symmetric.
    Newton, Maxwell, Schrodinger, Einstein field equations.
    GRADE  [INST] for the tested regimes, [INF-I] as stated.
    The symmetry is a property OF THE WRITTEN EQUATIONS — that part is
    checkable by inspection, not measurement. The claim that NATURE is
    symmetric is informed by the equations' success over their tested
    range. Note the field's own correction: the relevant symmetry is
    CPT, not T alone. So the clean statement "the laws are
    time-symmetric" is already the coarse version.
    EXPOSURE: the range where reversibility has been directly tested is
    not the range over which it is asserted.

L2  BECAUSE L1, no arrow of time can come from the laws.
    GRADE  [FP] — a valid deduction, and deduction from L1 is all it
    is. Nothing measured enters here.
    This link is sound. It is also the pivot: everything after it is
    downstream of a deduction, not of an observation.

L3  BECAUSE L2, the arrow must be imported from elsewhere.
    GRADE  [CONV] — "elsewhere" was not derived. A boundary condition
    was SELECTED as the place to put it, because a boundary condition
    is the one slot available in the formalism that is not a law. The
    choice of slot was structural convenience.
    THIS IS THE LINK WHERE THE IMPORT HAPPENS. It grades as convention.

L4  BECAUSE L3, the universe began in a low-entropy state.
    GRADE  [INF] — inferred by running the second law backwards. Not
    measured. The improbability is stated as one part in 10^(10^123) of
    relevant phase space.
    The field states plainly that postulating it without further
    explanation is an open problem, and that WITHOUT IT there is no
    explanation of the second law.
    EXPOSURE: L4 is load-bearing for the second law, and L4's only
    support is the second law. The loop does not close.

L5  BECAUSE L4 needs mechanism, entropy increase is derived from
    reversible kinetics.
    GRADE  [INF] with an embedded [CONV] — the H-theorem requires the
    molecular chaos assumption, doubts about which the literature
    states have not been firmly laid to rest.
    AND THAT ASSUMPTION IS ITSELF TIME-ASYMMETRIC.
    CIRCULARITY: asymmetry enters at the step whose purpose was to
    derive asymmetry. This is A4.

L6  BECAUSE L1, information cannot be destroyed — unitarity.
    GRADE  [FP] — structural requirement of the quantum formalism.
    Note: this is the SAME parent as L2. L1 forks here.

L7  BECAUSE L6, black hole information loss is a crisis.
    GRADE  [INF] — the crisis exists only because L6 was imported as
    structural. If reversibility were graded [INF-I] rather than [FP],
    an irreversible process at extreme curvature would be a finding
    about the boundary of L1's tested range, not a paradox.
    GR's side: everything except mass, charge and momentum is erased.
    That is a prediction of the classical theory, also [INF] — no black
    hole interior has been instrumented.

---

## THE STRUCTURE THIS EXPOSES

  L1 [INF-I]
   |
   +--> L2 [FP] --> L3 [CONV] --> L4 [INF] --> L5 [INF + CONV, circular]
   |
   +--> L6 [FP] --> L7 [INF]

  ONE PARENT. TWO BRANCHES. Neither branch's literature cites the
  other's, and BOTH terminate in an unresolved item that is graded
  inference.

  Read down either branch: there is no [INST] link after L1. Everything
  downstream of the fork is deduction, convention, and inference. The
  only instrumented link is the one whose claimed range exceeds its
  tested range.

## CONSEQUENCE OF THE GRADING

  1. The arrow of time and the information paradox are NOT two
     problems. They are two branches off one ungraded import.
  2. The import is at L3, and L3 is convention. That is the cheapest
     place to intervene and the least examined.
  3. L1's grade is the whole structure's exposure. If reversibility is
     [INF-I] — good over its tested range, asserted beyond it — then
     both branch-terminal problems dissolve into a single question:
     WHERE DOES L1 STOP HOLDING. That question is answerable by
     instrument in principle. Neither branch asks it, because L6 and L2
     both promoted L1 to [FP] on the way past.
  4. THE PROMOTION IS THE ERROR, not any individual link. An [INF-I]
     link was read as [FP] by two separate downstream literatures, and
     nothing in either field's method records the promotion.

## WHAT WOULD FALSIFY THIS READ

  - Any direct instrumented test of microscopic reversibility at
    energies or curvatures approaching the regimes where the two
    branches terminate. If one exists, L1 upgrades and the read fails.
    STATUS: NOT CHECKED. Do not treat as absent.
  - A citation link between the arrow-of-time literature and the black
    hole information literature that treats them as one premise. If
    common treatment exists, item 1 above is not a finding.
    STATUS: NOT CHECKED.
  - A derivation of L3's slot choice from something other than
    formalism structure.

  Both NOT CHECKED items are NOT MEASURED, not NOT FOUND.

## INHERITED

  S1-S6 apply. Additionally: the grade assignments are the author's,
  not the field's. No published paper labels L3 a convention. The
  grading is therefore [INF] at the meta level, and a reader should
  re-derive it rather than cite it.

---

# CORRECTION 2026-09-08 — L1 IS FALSIFIED
# Appended after the chain above was written. The chain's parent
# premise does not survive contact with the measurement record.
# The chain above is LEFT UNCHANGED. This correction is appended
# rather than merged, so the promotion error stays visible.

## WHAT WAS MEASURED

  T violation has been DIRECTLY OBSERVED. BaBar, 2012, 468 million B
  meson pairs from Y(4S) decays: non-zero values for T-violating
  parameters. The measurement used entanglement between neutral B
  mesons; a true test of time reversal symmetry with unstable particles
  had previously been considered impossible.

  Earlier: T violation was seen in neutral kaons at CPLEAR, but that
  measurement could not distinguish T violation from CP violation, and
  its interpretation drew criticism. BaBar is the direct result.

## CONSEQUENCE FOR L1

  L1 as written — "the microscopic equations are time-symmetric" — IS
  FALSE AS STATED.

  L1 REGRADES to [INST], and its CONTENT INVERTS:
    T is violated in the weak sector, measured.
    CPT is conserved to the limit of measurement; CPT tests have been
    consistent with zero.

  The CPT-not-T correction noted in the original L1 is therefore not a
  technicality. It is the whole content of the link.

## DOES THE SCOPE HOLD — NO

  The violation is confined to ONE OF FOUR INTERACTIONS.

    WEAK              T VIOLATED, measured (BaBar; CPLEAR indirect).
                      Weak interaction is maximally antisymmetric under
                      P and C.
    ELECTROMAGNETIC   T symmetric. Measured absent to tight limits.
    STRONG            T symmetric. Measured absent to tight limits.
    GRAVITY           NO T TEST EXISTS.

  Bound on the symmetric sectors: no neutron electric dipole moment has
  been found. Best limit (0.0 +/- 1.1) x 10^-26 e.cm, after roughly six
  orders of magnitude of experimental improvement. A permanent EDM
  would violate both P and T. So T violation outside the weak sector is
  MEASURED ABSENT, not unmeasured. That distinction is load-bearing.

  THREE DIFFERENT GRADES NOW SIT UNDER ONE WORD:
    measured-broken     (weak)
    measured-intact     (electromagnetic, strong)
    UNMEASURED          (gravity)
  Any argument using "reversibility" without naming its sector is
  equivocating across three grades.

## GAPS THIS OPENS

  G-a  THE VIOLATION IS IN THE WRONG SECTOR TO DO THE DOWNSTREAM WORK.
       Thermodynamic irreversibility occurs in systems governed by
       electromagnetism, where T holds to the EDM limit above. So L2's
       deduction ("no arrow can come from the laws") SURVIVES FOR THE
       RELEVANT SECTOR while its stated premise is false globally.
       The chain is not rescued by the falsification and is not
       destroyed by it. It is MIS-SCOPED, which is a third thing.
       OPEN: has anyone attempted to derive a thermodynamic arrow from
       weak-sector T violation, and what bounded the attempt?
       STATUS: NOT CHECKED.

  G-b  AN UNEXAMINED SUBSTITUTION.
       The literature notes that assuming CPT symmetry, T violation is
       equivalent to CP violation, and that the two are "often used
       interchangeably." That substitution is licensed BY A THEOREM,
       and the theorem is a premise. Register row candidate.
       OPEN: what is the measured bound on CPT itself, and what
       depends on the substitution that would not survive its
       loosening?
       STATUS: NOT CHECKED.

  G-c  GRAVITY HAS NO T TEST — AND THAT IS WHERE THE SECOND BRANCH
       LIVES.
       B5's branch L6-L7 (unitarity, black hole information loss) sits
       entirely in the gravitational sector. The sector with no
       reversibility measurement in it is the sector whose
       reversibility crisis is being argued about.
       This is the finding. Everything else in this correction is
       scope bookkeeping.
       OPEN: is there any proposed instrument, even in principle, for
       T symmetry in a gravitational regime?
       STATUS: NOT CHECKED.

  G-d  HISTORICAL PRECEDENT FOR INSTRUMENTING A HELD ASSUMPTION.
       Before 1964, no T violation had been found even in systems
       exhibiting MAXIMAL parity violation, so a non-zero neutron EDM
       was regarded as highly unlikely. Ramsey emphasised the need to
       check T invariance experimentally regardless. The check was
       right and the expectation was wrong.
       Filed as a worked case: "regarded as highly unlikely" is not a
       measurement, and the field has been here before on this exact
       premise.

## WHAT DID NOT CHANGE

  L3 is still [CONV]. L4 is still [INF]. The falsification of L1 does
  not touch them, because they were never supported by L1 — only
  triggered by it. A premise can be false and its downstream chain
  still stand on convention.

## THE PROMOTION ERROR, RESTATED WITH TEETH

  The original chain audit called the promotion of L1 from [INF-I] to
  [FP] an error of grading. It is worse than that. L1 was FALSIFIED IN
  ONE SUB-FIELD IN 2012 while two downstream literatures continued
  building on the unfalsified version, because the falsification is
  sector-scoped and the premise was being used unscoped.

  GENERALISED: an equivocation across sectors is how a falsified
  premise keeps working. The word survived; the scope did not travel
  with it.
  This belongs in instruments.md as a check: FOR ANY PREMISE, LIST THE
  SECTORS/REGIMES SEPARATELY AND GRADE EACH. Never grade the word.
