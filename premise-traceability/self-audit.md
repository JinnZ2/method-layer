# SELF-AUDIT — THE REGISTER'S OWN ASSUMPTIONS

CC0. Added 2026-09-08, on the question: what does the dependency list
itself assume.

Same treatment as the physics rows. These are not caveats. They are
rows, and they carry the same columns.

The register is not exempt from its own instrument. If it were, that
exemption would be assumption S0.

---

S1  ASSUMPTIONS ARE SEPARABLE INTO ROWS
  ADOPTED_FOR    a table is writable, editable, and diffable on a phone
  IMPORTS        that A1 and A2 are distinct items with a relation
                 between them, rather than one tangled commitment cut
                 in two places
  DEPENDS_ON_IT  every row; the entire edge list
  WALKED_BACK    NO
  STATUS         LIVE
  NOTE           If the object is a single commitment, the row
                 structure is already a PROJECTION of it — the same
                 projection step this register was built to expose.
                 Rendering a held structure as sequential rows is a
                 scope-in, not a neutral transcription.

S2  DEPENDENCY IS DIRECTIONAL
  ADOPTED_FOR    arrows are computable; in-degree gives a root
                 candidate
  IMPORTS        that the linked items can fail independently, and that
                 one is prior
  DEPENDS_ON_IT  the edge list; the root-candidate ranking (A9, then
                 A6)
  WALKED_BACK    PARTIAL — A4 already broke it and required a
                 circularity note instead of an edge
  STATUS         CONTESTED, internally. One counterexample is already
                 in the register.

S3  THE FIELD'S LITERATURE IS A VALID SOURCE FOR THE FIELD'S OWN
    UNEXAMINED PREMISES
  ADOPTED_FOR    Rule 1 — a row requires a source, no asserted
                 assumptions
  IMPORTS        that an unexamined assumption leaves a citable trace
  DEPENDS_ON_IT  every row in the register
  WALKED_BACK    NO
  STATUS         LIVE — and this is the register's hard ceiling.
  NOTE           An assumption nobody has noticed generates no
                 citation. So coverage of NAMED assumptions may be good
                 and coverage of genuinely invisible ones is
                 structurally ZERO. The register cannot distinguish
                 "no further assumptions exist" from "no further
                 assumptions have been written down." NOT FOUND and
                 NOT LOOKED FOR occupy the same cell.
                 MITIGATION AVAILABLE, NOT APPLIED: a second register
                 sourced from PRACTITIONER REPORT rather than
                 publication — what people inside the work know is
                 assumed but has never been worth writing.

S4  "ADOPTED FOR" IS RECOVERABLE
  ADOPTED_FOR    it makes the register explanatory rather than merely
                 descriptive
  IMPORTS        that a historical motive exists and was recorded; that
                 the adoption was experienced as a CHOICE
  DEPENDS_ON_IT  the ADOPTED_FOR column entirely
  WALKED_BACK    NO
  STATUS         LIVE
  NOTE           Most of these were never framed as choices. Where the
                 motive is reconstructed rather than documented, the
                 cell is an inference wearing a fact's formatting. The
                 column needs per-cell lineage — [obs] documented,
                 [inf] reconstructed. NOT YET APPLIED. Until it is,
                 treat ADOPTED_FOR as [inf] by default.

S5  ENGLISH PROSE AND A FIXED COLUMN SET CAN HOLD THE OBJECT
  ADOPTED_FOR    a plain-text file opens on any phone with no framework
                 context and no build step
  IMPORTS        five columns, sequential rows, one relation type
  DEPENDS_ON_IT  the artefact's transportability, which is the reason
                 it exists
  WALKED_BACK    NO
  STATUS         LIVE
  NOTE           The shape was chosen for the CHANNEL, not because the
                 object has that shape. Recorded so a later reader does
                 not mistake the format for a finding.

S6  THE REGISTER SITS OUTSIDE THE CHAIN IT DESCRIBES
  ADOPTED_FOR    nothing. Never adopted deliberately. Default position
                 of any instrument that does not audit itself.
  IMPORTS        ordering, discreteness, and identity-over-time — used
                 to write down a critique of ordering, discreteness,
                 and identity-over-time
  DEPENDS_ON_IT  the register's claim to be an audit rather than
                 another layer of the same thing
  WALKED_BACK    NO
  STATUS         LIVE
  NOTE           Same shape as A4. A4 imports time asymmetry into the
                 derivation of time asymmetry; S6 imports the premises
                 under audit into the audit. Do not resolve this by
                 declaring the register meta and therefore exempt —
                 that is the exemption move, and an exemption is a
                 finding, not a licence.

---

## WHAT THE SELF-AUDIT CHANGES UPSTREAM

  - Root-candidate ranking (A9, then A6) is downgraded from result to
    PROVISIONAL, because it is computed from an edge list that S2
    shows to be an incomplete relation type.
  - The ADOPTED_FOR column requires per-cell lineage before any row is
    cited elsewhere. Until then, treat ADOPTED_FOR as [inf] by default.
  - Register coverage should be stated as: NAMED assumptions, sourced
    from publication. NOT: assumptions of physics.

## RECURSION STOP

This audit is itself an instrument and has its own assumptions. It is
not run on itself here. That is a declared boundary, not a completed
check — the next layer is UNMEASURED, not clean.
