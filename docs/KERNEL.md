# Memory persistence and kernel adapters

The `mj_memory_recall.store` and `mj_memory_recall.kernel` modules provide local
episodic storage, a resource-memory lifecycle and a candidate evaluation seam
for Bangel projects. They do not implement a bootable operating-system kernel,
install a model, modify a program profile or grant downstream action permission.

All lifecycle transitions, generation increments, access authorization, evidence
qualification and held-out loss decisions execute in
`src/mj_memory_recall/source/kernel.bangel` through Elsa, independent JP
admission and Joanna. Python validates the closed transport and performs SQLite
I/O, canonical serialization, hashing and receipt binding. The compiler,
runtime, general language profile and existing neural mathematics are unchanged.

## Source and interpretation

The recovered resource-memory protocol is F-017 in representation WP-04,
*Memory, Request Occultation, and Generational Handoff*: source SHA-256
`a5a05442c8b59e2b1be2e0a1bc71c5cf602efc6a97eb568628b80f45f602474c`.
The R15 Impetus amendment repeats the sequence:

`QUIESCE → SEAL → CHECKPOINT → DETACH → RECLAIM`

It requires no silent deletion or uncleared generation reuse. That is a
resource-memory protocol, not an associative recall algorithm. SQLite storage,
the initial `ACTIVE` state and explicit `ACTIVATE` operation are versioned
engineering adaptations. The store retains rows after reclaim; reclaim is a
logical generation boundary rather than a file deletion or an assertion of
physical memory release. F-015/F-016 preallocation and F-028 byte reconciliation
are not claimed as implemented by this adapter.

The playbook's domain retention qualification, sometimes described there with
R2/R3 terminology, is represented as an explicit evidence qualification. It is
not mapped into Joanna runtime R-states. Lowercase neural `r0` remains
provisional and distinct from those resource and domain concepts.

## EpisodicStore

```python
from mj_memory_recall.store import EpisodicStore

with EpisodicStore("project-memory.sqlite", namespace=request["namespace"],
                   frame=request["frame"]) as store:
    store.append(request)
    candidate_request = store.request_for(request["query"], as_of=request["as_of"])
    result = store.recall(request["query"], as_of=request["as_of"])
```

`append(request)` accepts the existing `MJ-Memory-Recall/0.1.0` request and
atomically appends its validated observed memories. Stored patterns, traces,
receipt references, timestamps and optional play selections retain their original
values. IDs are immutable within a namespace across every generation. A duplicate
anywhere in a batch rejects and rolls back the whole batch.

A namespace is explicitly chosen for each store connection. The exact frame
object, including its identifier, bounds and decimal representations, is bound
to that namespace for its lifetime. Neither another project namespace nor a
silently rescaled frame can enter its recall request. Namespace partitioning is
an application boundary, not a replacement for operating-system access control.

`snapshot(as_of)` returns an atomic view of the current generation, selecting
only memories with `available_at < as_of`. It includes its canonical SHA-256,
generation and native access-authorization receipt metadata. `request_for` and
`recall` additionally enforce `query.observed_at == as_of`, so later information
cannot backfill the first query observation. A snapshot may be empty;
`request_for` then rejects because the existing recall profile requires at least
one memory. More than 16 eligible memories rejects explicitly rather than
silently dropping a candidate. A generation can retain at most 256 records;
each serialized record is bounded to 65,536 bytes and a checkpoint to 16 MiB.

Each connection belongs to one calling thread. Separate connections use SQLite
transactions for atomic reads and writes. No background worker or server is
started. Opening the object creates only the explicitly chosen SQLite file;
examples and tests use synthetic fixtures, not persistent user memories.

## Lifecycle, checkpoint and recovery

| Current stage | Operation | Result |
| --- | --- | --- |
| `ACTIVE` | `advance("QUIESCE")` | Stop accepting append operations |
| `QUIESCE` | `advance("SEAL")` | Seal the generation for checkpointing |
| `SEAL` | `checkpoint()` | Atomically store the checkpoint and enter `CHECKPOINT` |
| `CHECKPOINT` | `advance("DETACH")` | Verify checkpoint; remove the generation from active snapshots |
| `DETACH` | `advance("RECLAIM")` | Verify checkpoint; mark logical reclaim complete |
| `RECLAIM` | `advance("ACTIVATE")` | Verify checkpoint; increment generation and activate an empty generation |

No stage can be skipped. A new generation cannot reuse an old record ID.
Old rows and checkpoint records remain in the database. Ordinary snapshots are
available before detach, but append is authorized only in `ACTIVE`.

```python
store.advance("QUIESCE")
store.advance("SEAL")
checkpoint = store.checkpoint()
# Retain checkpoint["checkpoint_sha256"] separately from the database.
store.advance("DETACH")
store.advance("RECLAIM")
store.advance("ACTIVATE")
verified = store.recover(checkpoint["checkpoint_sha256"])
```

`checkpoint()` returns a content-addressed `MJ-Memory-Checkpoint/0.1.0` payload,
its hash, and native transition receipt metadata. Hashes cover canonical JSON,
not mutable SQLite page layout. On restart, the active generation's records,
frame, lifecycle record and associated checkpoint are checked.

`recover(expected_sha256)` verifies the checkpoint against the caller-retained
hash, namespace/frame and the exact retained generation rows. It returns verified
recovery material without reactivating an old generation or modifying files.
Restarting an active store directly preserves its recall behavior. This adapter
does not repair a corrupted database, import arbitrary recovery files, or claim
that internal checksums authenticate an adversary who can rewrite the database
and every trusted external hash. A separately retained checkpoint hash is needed
for an independent recovery integrity comparison.

## Candidate evaluation

```python
from mj_memory_recall.kernel import assess_update

decision = assess_update(update_request, review=independent_review)
assert decision["model_installed"] is False
```

The closed `MJ-Memory-Update/0.1.0` request has exactly:

| Field | Meaning |
| --- | --- |
| `profile`, `id`, `namespace`, `as_of` | Version, candidate request identity, domain and first evaluation observation |
| `baseline`, `candidate` | Model SHA-256 and protected descriptor hashes |
| `signals` | Up to 64 classified evidence records |
| `validation` | Up to 16 later held-out prediction records |

Each model descriptor has exactly `model_sha256`, `program_profile_sha256`,
`game_plan_sha256` and `film_evidence_sha256`. Values are lowercase 64-character
SHA-256 strings. Candidate model identity must differ from the baseline; the
three protected hashes must remain identical. Any proposed ProgramProfile,
GamePlan or FilmEvidence rewrite holds the update.

Each signal has exactly `id`, `receipt_ref`, `namespace`, `observed_at`,
`available_at`, `provenance`, `classified`, `compatible` and
`domain_retention_qualified`. The final three fields are explicit booleans.
Every supplied signal must be namespace-compatible, `OBSERVED`, classified,
compatible and qualified for domain retention. At least **30** such signals
are required. IDs and receipt references must be unique; one outcome, a coach
profile, film, an unclassified observation or a synthetic record cannot satisfy
the learning gate.

Each validation record has exactly `id`, `receipt_ref`, `namespace`,
`observed_at`, `available_at`, `provenance`, `target`, `prior_prediction` and
`candidate_prediction`. Numeric values are decimal strings: the target is 0 or
1, and predictions lie in [0,1]. At least **three** distinct, compatible observed
validation receipts are required. They must be disjoint from training signals,
observed strictly after every training signal became available, and themselves
available strictly before `as_of`.

Bangel computes binary Brier loss as the mean squared difference between each
prediction and observed target. Candidate loss must be **strictly lower** than
baseline loss. Ties, regressions, insufficient evidence, leakage, unqualified
retention and absent validation all retain the prior model. Losses are
unavailable when no valid held-out comparison exists.

Independent review is a separate in-process argument with exactly:

```json
{
  "profile": "MJ-Memory-Update-Review/0.1.0",
  "request_sha256": "<SHA-256 of the complete candidate request>",
  "verdict": "PASS"
}
```

`HOLD` and `DENY` are also valid verdicts. Missing review holds; invalid hash
binding rejects. Receipt references, classification and retention fields are
host evidence claims. The host must independently authenticate and qualify them;
a matching hash proves content identity, not issuer identity or the truth of
claimed observations. This adapter does not independently execute or train the
candidate model; it compares host-supplied held-out predictions tied to the
candidate hash. Any promotion decision still installs nothing and cannot
supplant a downstream control gate.

## Fresh verification scope

Six store tests exercise restart with actual recall, strict observation timing,
namespace/frame isolation, transactional rollback, lifecycle order, old-generation
retention, and tampered record/checkpoint rejection. Seven kernel tests exercise
native lifecycle checks, independently calculated Brier values, the 30-signal
minimum, domain qualifications, disjoint later validation, review binding and
denial, protected-profile immutability, loss ties/regressions, and maximum bounded
input (64 signals and 16 validation records). All thirteen passed through the
existing local Bangel toolchain. Cross-platform installed-package verification
belongs to the parent integration checkpoint.
