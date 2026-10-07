# Contributing to penn-nv-lossless

This repository holds benchmark evidence, not codec source: per-file results
tables (`results/`) and the drivers that produced them (`drivers/`). The corpus
itself (the 76 Penn NV-diamond files, 273,190,871 bytes) is referenced via the
Zenodo DOIs in the README and is not stored here.

## Ground rules

- Every row in `results/*.tsv` must come from a real run: every compressed
  output decoded and SHA-256-verified against the original, `sha` column `OK`.
- Exact selection only: the per-file winner is the smallest **actual**
  compressed bytes. No estimates, no skipped candidates.
- The README totals table must equal the per-method sums of the TSVs.
  CI (`audited-checks`) checks this, along with header stability and row
  integrity, on every pull request.
- Do not add codec source to this repo. Some codecs measured here are AGPL-3.0
  upstream; this repo ships no codec code and that must stay true.

## Quick checks

```sh
bash -n drivers/run_all.sh drivers/bench_one_q.sh   # shell drivers parse
python3 -m py_compile drivers/arsenal_driver.py     # python driver compiles
```

CI additionally validates TSV integrity (headers, `comp/orig == ratio`,
`sha == OK` on every row, full 5+4 method coverage of all 76 files) and
README-vs-TSV totals.

## Adding a method or re-running

1. Add the encode/decode cell to `drivers/bench_one_q.sh` (or extend
   `drivers/arsenal_driver.py` for a lab-codec run) — same exact-selection
   semantics: decode + SHA-256 verify, record real wall times.
2. Re-run with `drivers/run_all.sh`. It is safe to re-run: it skips files
   that already have rows.
3. Update the README results table and method list from the new totals.
4. Open a pull request using the template.

## Licensing

This repo is MIT. By contributing you agree your contribution may be
distributed under MIT, and you confirm you are not introducing code whose
license conflicts with that (e.g. no AGPL codec source).
