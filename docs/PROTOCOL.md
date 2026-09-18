# MJ-Memory-Recall/0.1.0 — provisional engineering contract

This version is a falsifiable prototype. It does not formalize neural `r0` as
biology or as an MjQ/JP state. Changes to thresholds, mappings, coordinate
interpretation or accepted input fields require a new profile version.

## Inputs and state

The request has exactly `profile`, `namespace`, `as_of`, `frame`, `memories` and
`query`. The included `trajectory-recall.json` is an executable schema example.
Identifiers are bounded ASCII strings. Real values are finite decimal strings;
JSON numbers, NaN, Infinity and implicit conversions are rejected. Unknown cue,
position, command or query metadata uses `null` and a native missing variant.
An explicitly observed numeric zero remains a known value.

Each of 1–16 memories carries an immutable ID, namespace, bipolar nine-component
pattern (−0.9 or +0.9), entity, relation, context, observation and availability
times, an `OBSERVED` provenance claim, a receipt reference, optional playbook
selection ID and up to 99 events. Each event identifies an actor and step 0–8,
a two-component position or unknown, and one known command or unknown.
Duplicate actor/step pairs reject. The query carries the same metadata fields,
a nine-component incomplete/noisy cue in [−0.9,+0.9], previous command and up to
nine observed events. Its ID is distinct from every memory ID.

`as_of` equals the query's first observation time. Every memory satisfies
`observed_at <= available_at < as_of` and belongs to the request namespace.
Host claims of observation, identity and receipt provenance require independent
authentication; a string marked OBSERVED does not establish authenticity.

Frames explicitly bind ID, x/y origin, width and height. Playbook-backed memories
require the exact catalog frame, including decimal representation. There is no
silent scale conversion. Ordinary project memory can use another positive,
bounded frame. Every observed coordinate and curve point stays within it.

The pure recall state consists of the validated episode set, current cue,
aligned observation/episode events, optional original actor curves, candidate
scores, runner-up score and observed command-transition counts. Calling recall
does not mutate this state or train/persist a model. The optional store has a
separate versioned lifecycle described in KERNEL.md.

## Native transition and scoring rule

For each candidate, mean cue similarity over known components is
`base = mean(1 - abs(cue[i] - pattern[i]) / 1.8)`.
Unknown components contribute neither a term nor a denominator entry.

The expected play point at phase `t = step / 8` is the original quadratic Bezier
`(1-t)^2 start + 2(1-t)t control + t^2 end`. Remembered trace alignment requires
the exact actor and step; the play curve requires the exact actor ID. A position
score is `max(0, 1 - ((dx/width)^2 + (dy/height)^2)/0.04)`. When both commands are
known, an event score is `0.75 * position_score + 0.25 * exact_command_match`.
Without both command observations, position alone is used; absence is not a
command mismatch.

Trace and playbook evidence each require at least three aligned known positions.
An active evidence mean gets weight 2; the associative base gets weight 1.
`combined = (base + 2*active_trace + 2*active_playbook)/(1 + active_weights)`.
Inactive channels contribute no weight, rather than a false zero observation.
Eligibility requires compatible known metadata and either base ≥0.8, or base
≥0.5 plus trace/playbook ≥0.9. Retrieval requires at least three known cue
components, combined ≥0.8, and top-minus-runner-up ≥0.1. An absent runner is
compared with zero. Equal scores always hold, independently of input order.

The cue-only baseline uses the identical ≥3-known, ≥0.8-score and ≥0.1-margin
thresholds, with no metadata or trajectory gate. The trace-only ablation keeps
all query/episode values fixed and removes only the optional play selection.
This distinguishes the playbook contribution from the value of context and
remembered trajectories. Neither baseline is a substitute for the older
MJ-Bangel recurrent-network comparison; that original algorithm is preserved.

A candidate becomes a verified match only when all three query metadata fields
are known and equal. Partial context may support a candidate but stays
`CONTEXT_HOLD`. A separate, valid independent PASS may mark a verified result
`MATCH_FOR_REVIEW`; absence/HOLD does not, and DENY always remains DENY.
Computation success does not authorize a physical action or live trade.

## Engineered command mapping

| Source path kind | Bound Bangel token |
| --- | --- |
| BLOCK_TRACK, RUN_SUPPORT_BLOCK, PROTECTION_SET | require |
| RUN_TRACK, VERTICAL_STEM | derive |
| PULL_TRACK, CROSSING_ROUTE, SLANT_FLAT_DISTRIBUTION | for |
| MESH_READ, CLOUD_OR_FLAT_LEVERAGE, TIMED_ROUTE | measure |
| DROP_LAUNCH | let |
| RPO_ACCESS_ROUTE, RUSH_OR_FIT_TRACK, FIT_OR_PRESSURE_ENTRY, SCREEN_BLOCK_OR_RELEASE | if |
| HOOK_WALL_DROP, MAN_LEVERAGE, SCAN_RELEASE | match |
| DEEP_ZONE_DISTRIBUTION, SCREEN_RELEASE | emit |

This is the new plugin's operator binding, not a claim that the source playbook
used Bangel executable syntax. Unknown catalog kinds reject. The internal absent
curve placeholder is never scored as playbook evidence.

The transition forecast scans memories ordered by availability time then ID,
actors by ID and events by step. It counts only adjacent steps with two known
commands. Its bounded window retains the latest 128 pairs in that deterministic
ordering. Tokens `let, measure, derive, require, if, for, match, emit, return`
map to logical command nodes 1–9. A forecast needs at least three observations
of the previous command and a unique most frequent successor. Laplace-smoothed
probability is `(winning_count+1)/(total+9)`; it is diagnostic, not calibrated
confidence. Unknown or tied forecasts expose no selected command/node. These
logical command nodes and spatial projections are distinct engineered views.

## Outputs and uncertainty

Outputs include candidate and match availability separately, known-feature count,
base/trace/playbook/combined scores and counts, margin, baseline candidate,
forecast, preserved missing variants, independent review status, request/source/JP
hashes and execution receipt root. No output may silently promote a recalled
entity to observed metadata. The candidate ID is null when no candidate is
available; diagnostic score records can still contain the leading failed option.

The API rejects oversized, duplicate-field, malformed or unsupported input. Native
functions return typed failures for invalid geometry and retrieval bounds.
Runtime limits additionally bound instructions, events, allocation, output,
receipt size and execution time. More data must be explicitly partitioned by the
host; it is never silently truncated into a different candidate population.
Only the documented command-history window is bounded by selection.

## Falsification and acceptance

Freeze input definitions, scoring thresholds, seed and ground-truth labels before
running comparisons. Report verified recall, false matches, coverage, abstentions
and candidate-only recall separately. Compare on identical cases and track the
trace-only ablation. Include degraded cues, unrelated queries, shared geometry,
unknown/mismatched context and denied review. Repeated source geometry is a
required ambiguity challenge, not evidence of repeated independent plays.

The proposed playbook benefit is falsified for a tested workload if it fails to
increase verified recall at no higher false-match count than trace-only recall,
or if any gain disappears when comparison arms use equal information and
operating thresholds. Source-selected far-path fixtures establish a functional
mechanism only. A significant or general improvement requires a predeclared,
independent real-workload evaluation with uncertainty estimates and precision /
recall operating curves. This prototype makes no such claim.
