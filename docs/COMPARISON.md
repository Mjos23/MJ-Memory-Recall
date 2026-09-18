# Controlled native recall comparison

This is a deterministic diagnostic study of 32 explicitly synthetic fixtures, with two candidate memory episodes per query. It is not a production accuracy estimate, a biological result, or a claim of statistical significance.

The first 20 queries use the exact 20 fieldbook selections and cover all 10 offense and 10 defense profile slots. The remaining cases test misleading cues, exact geometric collisions, missing or mismatched context, and out-of-set cues. Source curves retain their original schematic coordinates. Three source actors are sampled at phases 1/2, 3/4 and 1; noisy cases add a fixed-seed displacement of two or three canvas units, remove two cue values and reverse two cue signs.

Far-path distractors are selected deterministically from same-side catalog geometry before calling the model. This deliberately tests discriminable paths. Exact-collision cases separately test refusal when geometry cannot distinguish memories. The dataset is small, constructed, and partly favorable to the overlay; results do not establish generalization across the ecosystem.

All classifications and scores run in native Bangel. The cue-only baseline is emitted by the same native retrieval call. Trace-only ablation repeats the identical query, events, context, cue patterns and traces, changing only each memory's selection_id to null. The full-versus-trace contrast isolates access to the playbook. All arms use the same fixed 0.1 winner margin, 0.8 acceptance score, and minimum of three known cue features. Full and trace-only also use entity, relationship and context gates that the cue-only baseline lacks; their difference from cue-only is not solely a playbook effect.

No thresholds were tuned on these results. Seed: `20260914`. Synthetic labels remain outside production requests. `OBSERVED` in fixture requests only simulates the trusted host's observation role; it is not authenticated provenance, real game-film evidence, or permission to train. The comparison performs no persistent store writes, kernel updates, or downstream actions.

A positive case has one expected verified memory match. Negative cases have no acceptable verified return, including context holds and unresolved collisions. False matches below include any wrong memory **or unqualified return** in those negative cases. Recall divides correct positive returns by all positive cases; coverage divides returns by all 32 cases. Missing context is not counted as recovered evidence.

| Arm | Correct positive returns | False or unqualified returns | Recall | Coverage | Holds |
|---|---:|---:|---:|---:|---:|
| Cue only | 4/22 | 6 | 18.18% | 31.25% | 22 |
| Cue + trace | 8/22 | 2 | 36.36% | 31.25% | 22 |
| Cue + trace + playbook | 22/22 | 0 | 100.00% | 68.75% | 10 |

| Fixture group | Cases | Cue correct / false | Trace correct / false | Full correct / false |
|---|---:|---:|---:|---:|
| clean_cue | 4 | 4 / 0 | 4 / 0 | 4 / 0 |
| context_mismatch | 2 | 0 / 2 | 0 / 0 | 0 / 0 |
| context_unknown | 2 | 0 / 2 | 0 / 0 | 0 / 0 |
| geometry_collision | 4 | 0 / 0 | 0 / 0 | 0 / 0 |
| misleading_cue | 2 | 0 / 2 | 0 / 2 | 2 / 0 |
| noisy_partial_cue | 4 | 0 / 0 | 0 / 0 | 4 / 0 |
| out_of_set | 2 | 0 / 0 | 0 / 0 | 0 / 0 |
| playbook_cue_tie | 8 | 0 / 0 | 0 / 0 | 8 / 0 |
| trace_cue_tie | 4 | 0 / 0 | 4 / 0 | 4 / 0 |

The following hashes bind the generated inputs and outputs to the evaluated source. Re-run the checked-in tool against these sources to reproduce the report; the optional JSON output includes every request, expected label, native decision, receipt root and per-request source hash.

| Material | SHA-256 |
|---|---|
| engine.py | `9c76b080492b71447f4f37227a06cda5c6e84a56d3ba5e9c466bf937564c10b5` |
| recall.bangel | `b3b5782def4988a376fa8471fa3ccc2d630e4a5d392ed37533544ddfeb0c3598` |
| catalog_index.json | `90c61ce7ab708221ba7ebac2dadc5d4e4ef2ef508c610e8324cc4b5f047fe9d7` |
| comparison_tool | `2fd4dd7931c0826f61300ad5d29405239da9c1846cf1c4a8686121dc7d93cf25` |
| input_set | `d21f6803cd01a1bea3a98e9194cae6f3459300e29ced7200a680b23a094d868e` |
| results | `99201c87e76628e804fef5b8d698be76949803ab4150f190b0410e7db0c3a71b` |

| Fixture | Expected verified return | Cue | Trace | Full | Input SHA-256 |
|---|---|---|---|---|---|
| fb-01 | target | target | target | target | `eeada9c179db4157b56767d3fc94a510c462f244c6c0f2a07d33b1a870e35784` |
| fb-02 | target | target | target | target | `eeec124a6c3f4f7f94df6d65db4b65673d8692d91eef81511bf8ddb1151ad764` |
| fb-03 | target | target | target | target | `279779518aca74c518019b8a620ae7d1ecefd5855f13306db5508b5e00a12f2e` |
| fb-04 | target | target | target | target | `c7c63fde35ea5b3cf45cfd85e7f037990e12ca8c7e2f655b8c51959ba7f0566b` |
| fb-05 | target | hold | hold | target | `7c8f9eff5adc2dc32cfbe25fcf45588bf2073fc955248557e91360014738e85f` |
| fb-06 | target | hold | hold | target | `7829fd2304394c270c36d89c1a301db37dc020e8e102e46c4da62ef4a9ba7fe8` |
| fb-07 | target | hold | hold | target | `c92ca7a57a4585f1617fe2fed97b0d4f1550d3228e04728f5fdd27d1b0989dca` |
| fb-08 | target | hold | hold | target | `9a813e4259c2033e97bace36920f177f9e11846b7e6087661203a35fcf9c9c41` |
| fb-09 | target | hold | hold | target | `3b8f4815b3a6a35c4b989359bf32ff856996f22bda93abfe70a94f04f9fbeb75` |
| fb-10 | target | hold | hold | target | `b728e7678316f1397eabe8afa06f3ab8c8954ef3cd1caa9fe629319c9cc1445a` |
| fb-11 | target | hold | hold | target | `9270dc79e038773debb324056412c54dd06febb32b3a0ff7dfe46f3ec888cc5b` |
| fb-12 | target | hold | hold | target | `143571ac4fcd374d9252d7bf810198ffeab705cef82481bd25632043ef0c4483` |
| fb-13 | target | hold | target | target | `4b4da5b7142bd1653c8ed10c08e487a4da8c84dfce35ce677f507bc895ecd81f` |
| fb-14 | target | hold | target | target | `b1287b90e8f3d1744496d8b3cdee20f5e927ea171a8c5af4cf521d0737455cc4` |
| fb-15 | target | hold | target | target | `afa6e3bfadec9b6e77b4b5988af4240cbe0e155f34947dff377ea02c42718fe4` |
| fb-16 | target | hold | target | target | `2896faf46bd9ba468163f7b0e5f3421cad211cad445ec4792f959d6734f0c150` |
| fb-17 | target | hold | hold | target | `0161e4d48e718a2235ff63bea0567d060c2c0d384386ea74e0cedb9bc8018680` |
| fb-18 | target | hold | hold | target | `d1cc5664da4bdabe4232eabeb179703450e7f905889ff88d20608dc935df7a8f` |
| fb-19 | target | hold | hold | target | `89028f55ec70e50a1d833a35d6ab1cd287d9ee144de7382457955a064c64b297` |
| fb-20 | target | hold | hold | target | `d07498cceabc706117524bdfd438448da7c854b95544f6ee0e225830d325aad1` |
| misleading-offense | target | distractor | distractor | target | `52e3dd2a51f8e58c2e6ed76047d05be08b4305f4a04f475ae28a9a9761e38e2d` |
| misleading-defense | target | distractor | distractor | target | `37fccae004dc44cbe21bfde7f4968443537930b62ff10b06f6f8d0e8f5fc0c5c` |
| collision-offense-1 | hold | hold | hold | hold | `932a2d2932617f6c9f983468de309a621cb4b418a478ed4c72b954b11426a957` |
| collision-offense-2 | hold | hold | hold | hold | `8164c1cc12c3460999560e25cee6545911f08d5fd8d2a70bc618e06ecd5da3da` |
| collision-defense-1 | hold | hold | hold | hold | `ddcb7aa4703cdd957649f8252c6807ec1ffd61780072cc33f5118b5cf763f98a` |
| collision-defense-2 | hold | hold | hold | hold | `f4281fd9adf48ab7cae4b96971f7d7595adcdca755371c41150b0e9dbab7085f` |
| context-unknown-offense | hold | target | hold | hold | `44be2abc63a26816f38a82bc315bac3ab216739fe86c98f1ce7ec4f2a1dd865f` |
| context-unknown-defense | hold | target | hold | hold | `f7560f0449d250b679e710d9146709abe38181e01ae1bb7a2fa4135bf082ee87` |
| context-mismatch-offense | hold | target | hold | hold | `016f32897156a9224f08c5c0a10e9a779f3b5296220d0e478350292f4d85b0c4` |
| context-mismatch-defense | hold | target | hold | hold | `7b99fa2abea06caa6cb4d8f6bdcda0ea1a716f2f7c850f9d9f9d0ddb99c72adf` |
| out-of-set-offense | hold | hold | hold | hold | `12cb0ae77403b46e992ea94e9a18009cf82b0df7f1ed3de78c257f5f830b1005` |
| out-of-set-defense | hold | hold | hold | hold | `a2ff62a46fc07c085ae15eb82843c5d789e090cb2eaee9dfc691a69e3451496b` |

```bash
PYTHONPATH=language/python/src:plugins/mj_memory_recall/src python3 -B plugins/mj_memory_recall/tools/compare_recall.py --output comparison.json
```

The recall improvement in this fixture set is conditional on informative playbook geometry and the declared command binding. A larger blinded corpus, realistic distractors, source-independent trajectories, and equal-recall or equal-coverage comparisons remain necessary before making a deployment-performance claim.
