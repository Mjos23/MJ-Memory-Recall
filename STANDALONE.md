# Standalone repository — MJ-Memory-Recall 0.1.0

This private repository contains the original verified 0.1.0 source snapshot,
its existing MIT license and the matching offline Python wheels. All 174
files from the recovered source directory are unchanged. `REPOSITORY-IMPORT.json`
records their hashes and the archive identity. The archive's
`CLONE-PROVENANCE.json` remains historical, including its pre-publication status.

## Install independently

Use Python 3.12 or later from this repository's root:

```sh
python -m venv .venv
.venv/bin/python -m pip install --no-index --find-links wheels mj-memory-recall==0.1.0
.venv/bin/python -B -m unittest discover -s tests -v
```

On Windows, replace `.venv/bin/python` with `.venv\Scripts\python.exe`.
The supplied dependency wheels avoid sibling-repository imports and package-index
substitution. The CI workflow checks installed files against the preserved source
and runs the complete original regression suite on Linux/Python 3.12.

See [README.md](README.md) for native sources, API contracts and examples.
The current stack terminology is Bangel–Joanna–JP; historical names are retained
inside unchanged source documentation. Lowercase r0 remains provisional.
Review defaults to HOLD, and retrieved candidates do not grant execution authority.
Existing evidence files describe their original runs; the Actions tab contains
fresh checks for this repository import.

## Predictive and Layer 5 integration

The independently versioned predictive and decision development integration is
reviewable in [Bangel PR #10](https://github.com/Mjos23/bangel-language/pull/10).
It preserves these 0.1.0 module identities while adding canonical predictive
adapters, native decision arbitration, supervision, filtering and recovery.
See its [contract](https://github.com/Mjos23/bangel-language/blob/mj-neural-l5-integration/docs/MJ-NEURAL-L5-CONTRACT.md)
and [verification report](https://github.com/Mjos23/bangel-language/blob/mj-neural-l5-integration/docs/MJ-L5-VERIFICATION.md).
The new integration remains a development PR; it is not silently incorporated
into this preserved 0.1.0 package. Synthetic evidence does not establish
real-workload or biological performance.
