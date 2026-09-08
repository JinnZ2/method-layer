# REGISTER — PHYSICS ROWS

CC0. Columns and rules: see README.md.

## FIELD ALREADY NAMES PART OF THIS

  - Assumptions of Physics (Carcassi & Aidala, Michigan): the practice
    of deriving mathematics FROM stated physical principles stopped in
    modern times. Lagrangian mechanics and QM posit the mathematical
    structure with no justification of what is physically described or
    why those rules hold; physics is recovered afterwards by
    "interpreting" the mathematics.
  - "Theories without models: uncontrolled idealizations in particle
    physics" (Synthese 2024): a class of models built from
    NON-CONTROLLABLE idealizations, adopted for mathematical
    tractability, where the introduced error cannot be bounded.
    Distinct from approximation with known error.
  - Continuous formalism was extrapolated to the foundations while
    discreteness is observed at small scale — named explicitly in the
    literature as a hidden assumption.

---

A1  ABSOLUTE (NEWTONIAN) TIME
  ADOPTED_FOR    a single global parameter makes the equations solvable
  IMPORTS        a universal simultaneity; time as one-dimensional;
                 time as an external parameter rather than a dynamical
                 entity
  DEPENDS_ON_IT  quantum mechanics (Schrodinger evolution in t);
                 quantum field theory via the fixed Minkowski
                 background
  WALKED_BACK    NO
  STATUS         NAMED — surfaces as "the problem of time" only at the
                 point of collision with general relativity, where time
                 is local and dynamical. By then it is structural, not
                 visible as an assumption.

A2  TIME AS AN AXIS / FOURTH COORDINATE
  ADOPTED_FOR    manifold mathematics needed a fourth coordinate slot
  IMPORTS        axis properties time does not exhibit — you cannot
                 remain stationary in it, cannot reverse along it,
                 cannot survey it (only ever occupy a point)
  DEPENDS_ON_IT  all of spacetime geometry as currently written
  WALKED_BACK    NO
  STATUS         LIVE. The formalism itself already contradicts the
                 assignment: time enters the metric with OPPOSITE SIGN
                 to the three spatial dimensions, which is what makes
                 light cones and the causal/non-causal split exist.
                 Category assignment never re-examined.

A3  THE PAST HYPOTHESIS (low-entropy initial state)
  ADOPTED_FOR    the microscopic laws are time-symmetric (Newton,
                 Maxwell, Schrodinger, Einstein field equations), so the
                 thermodynamic arrow cannot come from them; it has to be
                 imported from a boundary condition
  IMPORTS        an unexplained initial condition of extraordinary
                 improbability — Penrose: one part in 10^(10^123) of
                 the relevant phase space
  DEPENDS_ON_IT  the second law's explanation; every arrow of time in
                 physics; the direction of causal reasoning
  WALKED_BACK    PARTIAL
  STATUS         CONTESTED and self-acknowledged. The field states
                 plainly that merely postulating it without explanation
                 is an open problem, and that without it there is no
                 explanation of the second law.

A4  MOLECULAR CHAOS (Stosszahlansatz)
  ADOPTED_FOR    required to derive entropy increase from reversible
                 kinetics (Boltzmann H-theorem, 1872)
  IMPORTS        a TIME-ASYMMETRIC assumption — into the derivation
                 whose purpose was to produce time asymmetry
  DEPENDS_ON_IT  statistical mechanics' account of irreversibility;
                 A3's supporting argument
  WALKED_BACK    NO
  STATUS         CONTESTED. Doubts about its applicability are stated
                 in the literature as not firmly laid to rest.
  NOTE           Circularity candidate: the asymmetry may have entered
                 at the step meant to derive it. Strongest single row.

A5  OBSERVER-INDEPENDENT ENTROPY
  ADOPTED_FOR    lets entropy be a state function of the system alone
  IMPORTS        a privileged coarse-graining — a choice of which
                 macro-variables count
  DEPENDS_ON_IT  A3; the claim that the arrow of time is objective
  WALKED_BACK    PARTIAL
  STATUS         CONTESTED. In coarse-graining schemes using
                 observer-relative macro-variables the low-entropy past
                 is PERSPECTIVAL: different subsystems or observers may
                 ascribe different entropies. A separate proposal
                 derives the observed asymmetry from assigning a-priori
                 probabilities differently to past and future events.

A6  CONTINUITY OF SPACE, TIME, AND QUANTITY
  ADOPTED_FOR    calculus. Differential equations require it.
  IMPORTS        arbitrary precision; infinite divisibility;
                 real-valued quantities with no granularity floor
  DEPENDS_ON_IT  every differential formulation in physics
  WALKED_BACK    NO
  STATUS         NAMED. Described in the literature as extrapolated to
                 the foundations without examination while discreteness
                 is observed at small scale; at Planck scale the
                 particle notion itself is said to lose meaning.

A7  POINT PARTICLES / IDEALIZED ISOLATED SYSTEMS
  ADOPTED_FOR    tractability; a state assignable to a smallest unit
  IMPORTS        locality; individuality; separability of a system from
                 its surroundings
  DEPENDS_ON_IT  scattering theory; the entire particle ontology of the
                 standard model
  WALKED_BACK    NO
  STATUS         NAMED. Cited as a hidden assumption: elementary
                 particles retain the corpuscle picture while having
                 lost most of its attributes (locality, individuality).

A8  PERTURBATIVE EXPANSION AS THE ROUTE TO PREDICTION
  ADOPTED_FOR    the only tractable method for interacting field theory
  IMPORTS        a series that in general does not converge and must be
                 read as an asymptotic expansion; individual terms not
                 in general finite; blindness to everything
                 non-analytic in the coupling constant
  DEPENDS_ON_IT  nearly all quantitative predictions in QFT; the very
                 statement that gravity is non-renormalizable is a
                 PERTURBATIVE statement
  WALKED_BACK    NO
  STATUS         LIVE and self-acknowledged: very few non-perturbative
                 results are known, so the seriousness of the omission
                 cannot even be estimated.
  NOTE           Gravity's incompatibility may be a property of the
                 METHOD rather than of gravity. A8 and the
                 non-renormalizability finding are not independent.

A9  POSIT-STRUCTURE-THEN-INTERPRET
  ADOPTED_FOR    it worked; deriving structure from physical principles
                 was harder and was abandoned
  IMPORTS        no stated account of what is physically described or
                 why the rules hold; physical meaning attached
                 afterwards by interpretation
  DEPENDS_ON_IT  Lagrangian mechanics; quantum mechanics as taught and
                 used
  WALKED_BACK    PARTIAL — this is what the Assumptions of Physics
                 programme is attempting to reverse
  STATUS         NAMED
  NOTE           META-ROW. This is the practice that lets rows A1-A8
                 accumulate unexamined. Ranking candidate for root of
                 the dependency graph.

A10 UNCONTROLLED IDEALIZATION AS ACCEPTABLE PRACTICE
  ADOPTED_FOR    mathematical tractability plus empirical relevance
  IMPORTS        an error term that cannot be bounded — distinct from
                 approximation with known error
  DEPENDS_ON_IT  a class of particle-physics models identified in the
                 literature as having no controlling theory
  WALKED_BACK    NO
  STATUS         NAMED (Synthese 2024)
  NOTE           Second meta-row. A9 says structure is posited; A10
                 says the error of doing so is unquantified.

---

## DEPENDENCY EDGES OBSERVED SO FAR

  A9  ---> A1, A2, A6, A7        practice enabling unexamined adoption
  A9  ---> A10                   same practice, error side
  A1  ---> A2                    one-dimensional time precedes axis slot
  A2  ---> A6                    coordinate treatment presumes continuity
  A4  ---> A3                    H-theorem argument supports Past Hyp.
  A5  ---> A3                    objectivity of entropy supports it
  A6  ---> A8                    continuity underwrites the expansion
  A7  ---> A8                    particle ontology underwrites it
  A8  ---> "gravity is non-renormalizable"

  Root candidates by in-degree: A9, then A6.
  PROVISIONAL — see self-audit.md S2. The ranking is computed from an
  edge list shown to be an incomplete relation type.

  Circularity candidate: A4 (asymmetry imported into the derivation of
  asymmetry).

---

## OPEN / NOT YET ENTERED

  - Locality and its status post-Bell. Needs its own pull rather than
    assertion.
  - Lorentz invariance at arbitrarily small length scales — appears in
    the perturbative literature as an assumption permitting virtual
    quanta of arbitrarily high energy. Candidate row A11.
  - Measurement / collapse. Deliberately not entered: the
    interpretation literature is large enough to swamp the register
    before the structure is stable.
  - Ergodicity, and the fluctuation-out-of-equilibrium account of A3
    (Boltzmann's own proposal; Feynman called it ridiculous).
  - Penrose's Weyl Curvature Hypothesis as a gravitational counterpart
    to A3 — also grounds the arrow in boundary conditions rather than
    time-asymmetric laws. Same structural move, different boundary.
  - CPT rather than T as the relevant symmetry: check whether this
    changes A4's status or only its statement.
