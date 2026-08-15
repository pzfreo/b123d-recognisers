# Complete-grid hole-pattern scaling

Issue #9 measured the pre-fix implementation on square grids of identical
`HoleRecord` values. `_rect_grid` found the correct result, but the recogniser then
enumerated lower-priority bolt-circle and linear candidates that could never be
allocated:

| Holes | Pre-fix seconds |
| ---: | ---: |
| 25 | 0.019 |
| 49 | 0.186 |
| 100 | 2.634 |
| 196 | 37.130 |
| 400 | >400 (terminated) |

Run the post-fix benchmark from a locked development environment:

```console
uv run python tools/benchmark_pattern_scaling.py --iterations 5
```

The benchmark constructs records directly, so it measures pattern allocation rather
than OCCT boolean construction. It asserts that every run still returns exactly one
`RectGrid` containing every input hole. The regression test additionally replaces the
circle and linear enumerators with fail-fast sentinels, providing a deterministic
operation-bound guarantee rather than relying on a wall-clock CI threshold.

Post-fix medians from five iterations on Linux x86-64 (kernel 6.8.0), Python
3.10.21:

| Holes | Post-fix median seconds |
| ---: | ---: |
| 25 | 0.00125 |
| 49 | 0.00261 |
| 100 | 0.01315 |
| 196 | 0.05614 |
| 400 | 0.41131 |

The 196-hole case falls from 37.130 seconds to 0.05614 seconds (about 661×),
and the formerly non-terminating 400-hole case completes well below one second on
the measurement host. Wall-clock values are review evidence only; the sentinel test
is the stable CI guard.
