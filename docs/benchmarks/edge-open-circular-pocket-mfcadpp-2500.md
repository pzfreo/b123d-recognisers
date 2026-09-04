# Edge-open circular pocket validation

## Result

The complete published MFCAD++ test split was scanned directly with
`recognise_edge_open_circular_pockets`: 2,500 models completed, 19 occurrences were found in 19
models, and no model raised an error. The four principal-axis residuals that motivated #487 are
included in those 19 occurrences.

Reading the labels only after geometric candidate construction gives 76 / 76 defining faces and
95 / 95 constituent faces labelled class 16, Circular end pocket. Each record owns four physical
wall supports plus its proved floor. No label is read by the recognizer.

The hit models are: 2046, 11872, 12062, 12229, 13831, 13874, 14079, 14669, 15484, 16210, 17988,
18365, 20275, 21745, 21793, 22620, 23015, 24389 and 25037.

## Interpretation

This is a bounded, high-purity recovery rather than a complete solution to Circular end pocket.
It demonstrates that a truthful open curved profile transfers beyond the four motivating examples
without fabricating the absent end or leaking into another MFCAD++ class. Taxonomy v13 maps the
new physical family to class 16 for subsequent effectiveness reports. MFInstSeg was neither run
nor inspected for this development increment.
