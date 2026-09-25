# MJ Memory Recall

> Current rights: all rights reserved by MJ Physics Engineering / Michael Bangel. No new license is granted by this revision. Prior grants and third-party notices remain effective; see the root LICENSE and LICENSING.md.


Version **0.1.0** adds reusable episodic recall and a physics-football overlay to
the Bangel ecosystem. It can be installed independently or used by **MJ Neural
Net**. All recall scoring, spatial projection, command prediction, lifecycle
transitions and update decisions are ordinary `.bangel` source compiled by Elsa,
independently admitted as JP and executed by Joanna. Python supplies validated
transport, catalog loading and SQLite I/O.

The packaged catalog contains **1,080 selections** (360 offense, 720 defense),
**11,880 original actor paths**, **360 formations**, ten system profiles and
4,320 sequence links. Each source quadratic curve retains its start, control,
end, actor and responsibility group. The source fieldbook's twenty selections
are included. Hashes and coverage are in `src/mj_memory_recall/data/`.

## Install and use

From the Bangel repository, with Python 3.12 or later:

```sh
python -m pip install --no-build-isolation ./language/python ./plugins/mj_memory_recall
mj-memory-recall run plugins/mj_memory_recall/src/mj_memory_recall/examples/trajectory-recall.json --output recall-result.json
mj-memory-recall lower plugins/mj_memory_recall/src/mj_memory_recall/examples/trajectory-recall.json --output recall-sources
python -m unittest discover -s plugins/mj_memory_recall/tests -v
```

Use fresh output paths. `run` exits 0 for a reviewed advisory, 3 for a held
advisory and 2 for invalid input or execution failure. The example finds the
correct remembered trajectory but retains downstream HOLD until independent
review is supplied. `lower` exports portable Bangel modules and admitted JP.
The independently installed source package uses `python -m pip install .` after
installing the pinned `bangel-language==0.2.0rc1` dependency from the ecosystem
repository or the supplied wheel set; it does not depend on a monorepo import.

```python
from mj_memory_recall import recall, EpisodicStore, assess_update, project_selection
from mj_memory_recall.api import create_app

result = recall(request)  # closed MJ-Memory-Recall/0.1.0 JSON object
with EpisodicStore("project.sqlite", namespace=request["namespace"],
                   frame=request["frame"]) as store:
    store.append(request)
    recalled = store.recall(request["query"], as_of=request["as_of"])
app = create_app(review_provider=independent_host_reviewer)
```

The library can be called by any project or self-healing-kernel host that binds
its own namespace, coordinate frame and authenticated evidence. It opens no
server and installs no background process. `assess_update` provides a qualified
candidate comparison seam; the host remains responsible for generating the
candidate predictions, authenticating receipts and applying any approved update.

## Recall and playbook behavior

An associative cue scores stored nine-component patterns. A second stage
compares matching actors and time steps against remembered trajectories and
source playbook curves. Known entity, relationship and context conflicts exclude
a candidate; unknown context remains unknown. A margin test holds ambiguous
matches. Geometry alone cannot identify an entity: the catalog contains only
146 distinct complete geometric assignment sets across its 1,080 selections.

Curves project into the pictured bottom-up N1–N9 grid using nine samples at
`step/8`. Repeated nodes are retained. The frame is **schematic pixels**, not
measured yards: x=42, y=55, width=748, height=455, positive y downward. These
projections and command bindings are versioned engineering choices. They do not
turn the pictures into approved command sequences or reproduce hippocampal
cellular biology.

Linguistic prediction is a bounded first-order model over nine Bangel command
tokens. It counts adjacent observed command pairs, conditioned on the previous
command. It neither bridges missing steps nor treats a forecast as an observed
memory. The playbook overlay also compares observed command tokens with the
versioned operator assigned to each path kind. Read rules, interaction surfaces,
formations and sequence links remain available as source context. Their prose
and equation strings are never executed as arbitrary code.

The independent API exposes `GET /v1/profile`, `GET /v1/catalog`,
`POST /v1/recall` and `POST /v1/project`. Projection requests contain exactly
`{"profile":"MJ-Playbook-Projection/0.1.0","selection_id":"<catalog id>"}`.
Recall uses the example's closed schema. Requests are bounded to 64 KiB and
responses to 1 MiB. Review enters through a server callback or a separate local
argument, bound to the SHA-256 of the entire request; clients cannot grant their
own review through JSON. No review defaults to HOLD; DENY remains dominant.

## Provisional contract and evidence

[PROTOCOL.md](docs/PROTOCOL.md) defines inputs, state, transition/scoring rules,
outputs, uncertainty, bounds and falsification criteria. [KERNEL.md](docs/KERNEL.md)
defines persistence, the `QUIESCE → SEAL → CHECKPOINT → DETACH → RECLAIM` resource
lifecycle and qualified update assessment. [COMPARISON.md](docs/COMPARISON.md)
describes the controlled synthetic recall comparison and its limits.

Lowercase **`r0` remains a provisional marker**, not a biological state,
implemented MjQ state or uppercase MjQ/JP `R0`. The source-local Pink reserve
variable also spelled `r0` is separate. Teal, Purple and Blue references inherited
by MJ Neural Net retain their own namespaces and source qualifications.

Tests use explicitly synthetic observations. No real user memory was imported,
no coach profile was used as training evidence, and no actual kernel model was
installed. Recall improvement must be evaluated on held-out ecosystem workloads;
a diagnostic fixture result is not a general accuracy claim.
