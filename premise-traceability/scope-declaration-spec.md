# scope_declaration.py — SPEC
# stdlib only, phone-buildable, CC0
# joins: instrument-join-registry (shared declaration-block shape)

## THE BLOCK — four required fields on any transported claim

  measurand   what was actually measured, not what it is called
  range       the sector/domain where it holds
  instrument  what produced the number, INCLUDING the scaffold/harness
  grade       one of the enum below

## GRADE ENUM — five values, and the fifth is the new one

  MEASURED_PRESENT   tested, effect found          (weak-sector T violation)
  MEASURED_ABSENT    tested, effect not found      (neutron EDM limit)
  UNMEASURED         no instrument exists          (gravity, T symmetry)
  UNDERPOWERED       tested, test provably cannot  (aggregated Markov
                     resolve it                     dwell-time blindness)
  IMPOSED            adopted as a model constraint (microscopic
                     for tractability, not tested   reversibility in
                                                    reaction mechanisms)

  UNDERPOWERED and IMPOSED must NOT collapse into UNMEASURED.
  They are the two grades the selection effect predicts, and they
  co-occur where the premise is load-bearing.

## FUNCTION 1 — declaration_score(claim)

  returns: DECLARED | PARTIAL(missing_fields) | UNDECLARED
  no verdict on truth. A claim without a block is not wrong,
  it is UNTRACEABLE. Different thing.

## FUNCTION 2 — axis_compare(claim_a, claim_b)

  returns exactly one of:
    COMMENSURABLE     blocks share measurand + range + instrument
    INCOMMENSURABLE   blocks differ on a named field; field is returned
    UNDECLARED        one or both blocks absent/partial

  CRITICAL: UNDECLARED and INCOMMENSURABLE are SEPARATE returns.
  Collapsing them repeats the NOT-MEASURED / NOT-FOUND merge error.

## WORKED CASES — regression set, all four from this session

  Astra 99.9 vs Opus 30.2
    -> INCOMMENSURABLE(instrument): provider adapter vs standard harness
       secondary: range differs (task set)
  Opus 30.2 vs Sol 7.8
    -> COMMENSURABLE: same harness, same set
  chemistry microscopic reversibility
    -> grade IMPOSED, range UNDECLARED
       (justification travelled, range did not)
  "laws are time-symmetric"
    -> PARTIAL(range): true for EM/strong, false for weak,
       UNMEASURED for gravity — three grades under one word
  orthopedic surgeon at crash scene
    -> PARTIAL(range): credential is scope-shaped,
       range not carried with the authority

## OUT OF SCOPE — stated so it is not assumed

  Does NOT judge whether a claim is true.
  Does NOT infer a missing block's contents.
  Does NOT rank claims.
  Flags only.
