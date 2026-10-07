# Security Policy

This repository is benchmark evidence: TSV tables and benchmark drivers.
There is no server, no dependency install, and no codec source here, so the
attack surface is small — but integrity of the numbers is the security
property: a forged or silently altered row would misrepresent results.

## Reporting a vulnerability

Please do not open a public issue for security problems.

- Email: corey@slidphilabs.com with the subject line `penn-nv-lossless security`
- Or use GitHub's private vulnerability reporting on this repository
  (Security tab, "Report a vulnerability")

Include the affected file(s), steps or inputs to reproduce, and what you
expected versus what happened.

You can expect an acknowledgement within 3 business days. We will keep you
updated while we investigate and credit you in the changelog unless you prefer
to stay anonymous.

## In scope

- Tampered or misattributed rows in `results/*.tsv` (bytes that do not
  reproduce from the documented drivers, or a `sha: OK` row whose decode
  does not actually verify)
- A driver change that silently skips candidates or mislabels a method,
  corrupting the exact-selection claim
- Anything in CI that could let bad data land as passing

## Out of scope

- The corpora behind the Zenodo DOIs (we do not control them)
- The measured codecs themselves — report issues to their own repositories
- Social engineering, spam, or denial-of-service against mirrors of this repo
