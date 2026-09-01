# E5 Double-D / ordinary-Hole reconciliation

Issue #304 removes one duplicate aggregate interpretation at a physical Double-D void. Direct
Hole and Double-D discovery remain independent. Terminal reconciliation rejects the Hole only
when its non-empty exact defining-node set is a proper subset of one completed Double-D
occurrence's complete four-wall set.

## Geometry and architecture contract

The Double-D occurrence says strictly more about the same constant through boundary: its defining
evidence retains the cylindrical sides and both planar flats, while the ordinary Hole proposal
retains only the cylindrical subset. No coordinate, diameter, axis, record equality, solid order
or tolerance establishes the relationship. Disjoint holes and equal-diameter holes on another
solid therefore remain accepted. The rejected Hole records the exact winning Double-D Candidate,
and Hole patterns derive only from the accepted Hole inventory.

ADRs 0002, 0003, 0004, 0005, 0007 and 0009 apply. Discovery remains sibling-blind and writer/direct
parity is unchanged; the rule consumes only completed Candidate sets and terminal frozen evidence
inside `_reconcile`. No public record schema, family output, tolerance, graph authority or
persistent identity changes. The bounded public explanation enum gains the corresponding reason;
ADRs 0003 and 0005 record the precedence and additive compatibility decision.

Authored evidence covers the reported geometry-dependent duplicate, direct-family preservation,
the exact rejected disposition and winner, public explanation projection, pattern suppression, a disjoint circular hole on the
same solid, and an equal-diameter circular hole on another solid. Existing Double-D transform,
scale, STEP, topology-order, multiple-occurrence and provenance tests remain authoritative.

## Exact MFCAD++-500 result

Both reports use taxonomy v8 and the canonical lexical selection hash
`323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`:

- parent `6ae44e0ab4db830ebe91890bca7e83072518d5bd`:
  [`effectiveness-mfcadpp-500-double-d-parent-6ae44e0.json`](effectiveness-mfcadpp-500-double-d-parent-6ae44e0.json),
  SHA-256 `01c6c1964192ecdef232c77db69eb2dcb35b53b086d973f2a72e20dfd17000fd`;
- implementation `22bf3e684cf7eb38f96423714df760e66c58b8eb`:
  [`effectiveness-mfcadpp-500-double-d-22bf3e6.json`](effectiveness-mfcadpp-500-double-d-22bf3e6.json),
  SHA-256 `a7835011a452588d6d550bf28f1e8c58fd45e791cc767bdf955b131d85764856`.

All 500 models load and evaluate. After removing package commit and per-run timing, the complete
reports are byte-equal: no selected model contains an accepted Double-D occurrence, so records,
accepted outputs, reconciliation, mapped scores, coverage, diagnostics and taxonomy mismatches do
not change. This is neutral development evidence, not proof that the fix is unused downstream;
the independently authored Draftwright blocker, reproduced locally as an authored regression, is
the positive consumer case.

Runtime is 341.30 seconds for the parent and 343.63 seconds for the implementation (1.0068x), with
median 0.6355 to 0.6400 seconds and p95 1.2490 to 1.2538 seconds. The difference is within the 1.10
package gate and consistent with one small terminal Candidate-set comparison.
