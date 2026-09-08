# PREMISE TRACEABILITY

CC0. Working register. Opened 2026-09-08.

## PURPOSE

Organize assumptions by:
  (a) what was assumed
  (b) why it was adopted at the time
  (c) what it IMPORTS
  (d) what now depends on it
  (e) whether the dependency has ever been walked back

The register is the object. Individual rows are replaceable.
Physics is the first worked example, not the subject.

## WHY THIS DOES NOT EXIST ALREADY

Metrology has traceability chains: every measurement must link back to
a defined standard. That machinery covers MAGNITUDES only. There is no
equivalent for PREMISES. Each link in a premise chain is locally valid
and locally validated, and no role spans the chain.

## FILES

  register-physics.md  rows A1-A10, foundational assumptions, plus the
                       dependency edge list
  self-audit.md        rows S1-S6, the register's own assumptions
  boundary-grqm.md     rows B1-B7, the GR/QM collision decomposed into
                       separate imports
  chain-audit-b5.md    rows L1-L7, one forced sequence with each link
                       graded by epistemic origin
  downstream.md        rows D1-D4, fields outside physics building on
                       these links
  instruments.md       methods that fell out of the work
  GRADES.md            the epistemic grade legend, reusable across
                       domains
  sweep-reversibility.md
                       what reversibility claims were checked across which
                       fields, and where the term changes meaning between
                       them
  information-decoupling.md
                       why specialization scopes get declared in some fields
                       and not others, and what that costs downstream
  scope-declaration-spec.md
                       the four required fields for any transported claim,
                       plus the grade enum and what each grade means

## COLUMN DEFINITIONS

  ADOPTED_FOR    the reason at the time. Usually tractability.
  IMPORTS        what rides in with it, unstated.
  DEPENDS_ON_IT  what breaks or needs rebuilding if it fails.
  WALKED_BACK    NO / PARTIAL / YES — has the dependency been traced
                 forward from this assumption to everything resting
                 on it.
  STATUS         LIVE        still in use, still unexamined
                 NAMED       field acknowledges it as an assumption
                 CONTESTED   active dispute in the literature
                 SUPERSEDED  replaced, downstream not rebuilt

Never merge NOT MEASURED with NOT FOUND.
Never merge NAMED with WALKED_BACK — acknowledging an assumption is
not tracing it.

## HOW TO READ THE CROSS-REFERENCES

Pick one import. Follow its CROSS field. The consequence of importing
it is stated in every row it touches, so a reader can trace:

  "importing B5 means assuming reversibility is structural; cross with
   A3 shows the same premise forced the entropy arrow; therefore a
   revision of B5 does not just address black hole information, it
   reopens the arrow of time."

That is the intended use. This is not a list of complaints. It is a
dependency surface for tracing what one revision would cost and what
it would free.

## RULES FOR ADDING ROWS

  1. A row requires a source. No asserted assumptions.
  2. NAMED is not WALKED_BACK. Keep the columns separate.
  3. A null is a result: "no dependency trace exists" is a finding and
     gets recorded as one.
  4. Do not resolve a circularity by choosing a direction. Record it
     as a circularity.
  5. Rows are never deleted. Superseded rows keep their content and
     change STATUS.

## RECURSION STOP

self-audit.md runs this instrument on the register itself. That audit
is itself an instrument and has its own assumptions. It is not run on
itself. That is a DECLARED BOUNDARY, not a completed check — the next
layer is UNMEASURED, not clean.
