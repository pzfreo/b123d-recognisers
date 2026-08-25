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
not counted separately. Free-axis occurrences appear only in `section_passages`.

The package capability manifest is format 2. Each recogniser declares whether it is a physical
authority, compatibility projection, or derived API, and each counted family names its
authoritative aggregate output. Consumers must explicitly support format 2 before accepting the
0.4 package range. The existing `passages` family identifier and historical `introduced_in` value
do not change; all five new records use schema version 1.
