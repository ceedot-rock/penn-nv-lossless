## What changed

<!-- One or two sentences: what results or drivers changed, and why. -->

## Checks

- [ ] Every changed row decodes and SHA-256-verifies against the original (`sha` column reads `OK`)
- [ ] `results.tsv` / `results-arsenal.tsv` headers unchanged: `tag method orig comp ratio enc_s dec_s sha note`
- [ ] README totals table updated and equal to the per-method sums in the TSVs
- [ ] Drivers still parse: `bash -n drivers/*.sh`, `python3 -m py_compile drivers/arsenal_driver.py`
- [ ] No codec source or upstream-licensed code added to this repo
