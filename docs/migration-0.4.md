# Migrating passage attribution to 0.4

Version 0.4 adds `SectionPassage` as the sole attributed `PASSAGES` record. It represents
principal and free-axis constant-section passages with a canonical frame, run interval, complete
section, and explicit open ends.

Writer-free `recognise_passages(part, ledger=None)` remains the compatibility API for legacy
principal-axis `Passage` values. Its values, ordering, and `to_dict()` contract are unchanged.
Passing any non-`None` `ClaimLedger` or `EvidenceWriter` now raises `PassageCompatibilityError`
before geometry discovery or ledger mutation. Attributed callers must migrate to:

```python
records = recognise_section_passages(part, ledger=ledger)
```

`RecognitionResult.section_passages` is the physical, counted result. The existing
`RecognitionResult.passages` field remains a post-reconciliation compatibility projection of
accepted, exactly representable principal line sections; it owns no Candidate or evidence and is
not counted separately. It is a stable subsequence of the standalone legacy result, not a promise
that every historical legacy record has a rich equivalent. A legacy-only record whose claimed
walls do not form a truthful constant section remains visible from writer-free
`recognise_passages`, but is absent from the aggregate, reconciliation and census. Free-axis
occurrences appear only in `section_passages`.

This intentionally narrows aggregate compatibility before 1.0. On the checked-in
`10060.step` regression, standalone legacy output remains the two-element `(X, Z)` sequence. The
partial-span X false positive has no rich occurrence, while the truthful Z occurrence remains the
sole aggregate projection in its original relative order. Consequently `feature_census` reports
one Passage instead of the historical two; all other census keys and the exact Slot, Pocket and
Prismatic Pocket dispositions remain unchanged on that part.

The package capability manifest is format 2. Each recogniser declares whether it is a physical
authority, compatibility projection, or derived API, and each counted family names its
authoritative aggregate output. Consumers must explicitly support format 2 before accepting the
0.4 package range. The existing `passages` family identifier and historical `introduced_in` value
do not change; all five new records use schema version 1.
