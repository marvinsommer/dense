# Dense as global context on Claude CLI: methodology and results

## 1. Methodology

### 1.1 What is being tested

A compact instruction ("dense") that tells the model to prefer the smallest
correct response and implementation. The question is whether delivering it as
**global context — part of the system prompt on every request — changes solve
rate, token consumption, or wall-clock** relative to an unmodified agent.

Two conditions:

| condition    | delivery                                                                                                                                     |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **baseline** | no instruction, stock agent                                                                                                                  |
| **dense**    | instruction appended to the system prompt via `--append-system-prompt`, wrapped in `<override>…</override>`, 1798 bytes (sha256 `29a361ac…`) |

The full instruction, verbatim:

```text
<override>
# DENSE

Use the smallest correct response and implementation. Preserve correctness,
safety, security, accessibility, and required validation.

## Output

- First sentence: result.
- Then one compact evidence or validation line.
- Then only a correctness-critical caveat or next action; stop.
- Default: ≤3 sentences and ≤60 words.
- Delete preambles, restatements, process narration, praise, apologies, and recaps.

## Acceptance and scope

- Before acting, define the allowed change set in one line.
- Maintain a private acceptance ledger: requested behavior, each distinct mode or
  input class the behavior must handle (each sign, direction, boundary, and empty
  case), explicit exclusions, required tests, and unresolved questions.
- Preserve every ledger item across turns; add new requirements without dropping old ones.
- Reuse existing architecture and interfaces.
- New storage, schemas, dependencies, migrations, security models, backend
  routes, protocol changes, and cross-tab state are out of scope unless explicit.
- If a proposal exceeds scope, omit it and state the boundary briefly.
- Ask one focused question only when the boundary blocks correctness.
- Validate trust boundaries. Verification is always in scope: exercise every
  ledgered mode at least once, including the non-default sign or direction.
  A green pre-existing suite is not evidence for new behavior.

## Decisions

- Need it? If no, delete it.
- One line? Use one.
- When one path serves several modes, re-check every precondition and early
  return against each mode.
- Preserve unrelated changes. Never claim success without fresh output.

## Thinking and updates

- Think telegraphically.
- Commentary: concise status only while work continues or when a material result appears.
</override>
```

The dense text is injected as a **static system-prompt suffix**, not as a
retrievable skill and not as a user-turn preamble. This matters for cost: the
system prompt is a stable prefix, so it is written to the prompt cache once per
session and read thereafter. Cache reads are 98%+ of all input tokens in both
conditions, so the instruction's own cost is negligible and any token difference
comes from behaviour, not from carrying the text.

### 1.2 Agent and harness

- **Model**: Opus 5 (`claude-opus-5`), `--effort high`, default service tier.
- **Agent**: Claude Code CLI in headless mode —
  `claude --print --output-format stream-json --verbose --dangerously-skip-permissions`.
- **CLI versions**: 2.1.220, 2.1.221, 2.1.222 (see §3.4 — this is a disclosed
  confound, spread across both conditions).
- **Isolation**: each task run gets its own Docker container from the task's
  pinned image, its own git workspace, and its own `CLAUDE_CONFIG_DIR`. Nothing
  is shared between concurrent runs except the host daemon.
- **Container resources**: 2 CPUs, 8192 MB memory, 20480 MB storage per task,
  5400 s agent timeout, 1800 s verifier timeout.
- **Concurrency**: 4- or 5-wide, batches strictly sequential.
- **The agent must route every command through `docker exec`** into its assigned
  container. A run that executes anything on the host is flagged
  (`docker_routing_ok: false`) and discarded rather than scored.

### 1.3 Task set

A pinned 20-task subset of **DeepSWE v1.1** (`datacurve-ai/deep-swe`, revision
`a40d7298`), drawn from the 113-task official inventory:

| property           | value                                                                 |
| ------------------ | --------------------------------------------------------------------- |
| selection          | canonical-full, fixed membership from `deep_swe/canonical_tasks.json` |
| difficulty         | 5 easy, 5 medium-easy, 5 medium-hard, 5 hard                          |
| languages          | Go, Python, TypeScript, Rust, JavaScript                              |
| official pass rate | 0.22 – 0.91, mean 0.569                                               |

Each task is a feature request against a real repository at a pinned commit.
Reward is binary, from the task's own `test.sh` run in a fresh container.

### 1.4 Grading

Two stages, both from a pristine task image with the model patch applied:

1. **`implementation`** — agent-authored test files stripped from the patch.
   **This stage produces the reported score.**
2. **`self-check`** — the full patch including the agent's own tests.
   Diagnostic only.

Stage 1 exists because an agent-written test can collide with the grader's
hidden `test.patch`. Measured case: an agent declared `TestEmbedString` in
`interp/interp_embed_test.go` while the grader declares the same symbol in
`interp/embed_test.go`; the package stopped compiling and _every_ test failed,
including the pre-existing suite, scoring 0. The identical implementation scored
1 with that file withheld.

All eight runs are graded under this same two-stage grader. Three arms
originally ran under a single-stage grader and were regraded so the comparison
is uniform; that regrade moved one baseline arm 15 → 16 and one dense arm
14 → 15.

### 1.5 Replicates

**4 replicates per condition, 20 tasks each — 160 agent runs.** Replicates
exist because the suite is not deterministic (§3.3); single runs of either
condition are not interpretable.

### 1.6 Timing definitions

Three different numbers, kept separate because they answer different questions:

- **Wall-clock (as run)** — manifest start to finish. Includes queueing behind
  sequential batches, and includes any stall from an infrastructure failure.
  Useful for "how long did this actually take me", not for comparing conditions.
- **Pure agent time (per task)** — span from the first to the last stream event
  of the task's _successful_ attempt. Retries overwrite their predecessor's
  stream log, so **auth retries, contract-gate re-runs and stalls are excluded
  by construction**. Verified: capping inter-event gaps at 180 s changed no
  arm's total, i.e. no successful attempt contains a stall.
- **Pure agent time (per run)** — sum of the above over 20 tasks. This is
  compute actually spent, independent of how wide the run was.

Per-task pure agent time is the normalized figure used for comparison.

---

## 2. Results

### 2.1 Headline

| measure                        | baseline (n=4) | dense (n=4)  | delta                     |
| ------------------------------ | -------------- | ------------ | ------------------------- |
| **pass**                       | 16.25 ± 0.96   | 15.75 ± 1.50 | −0.5 tasks (inside noise) |
| **pure agent time / task**     | 27.81 min      | 20.13 min    | **−27.6%**                |
| **input tokens / task**        | 11.93M         | 7.77M        | **−34.9%**                |
| **output tokens / task**       | 82.2k          | 60.4k        | **−26.5%**                |
| **rounds / task**              | 91.8           | 71.4         | **−22.2%**                |
| **est. price / task**          | $9.79 ± 0.71   | $6.73 ± 0.26 | **−31.3%**                |
| **est. price / run (×20)**     | $195.92        | $134.57      | **−31.3%**                |
| **est. price / task _passed_** | $12.05         | $8.55        | **−29.0%**                |

**Price is an estimate, not an invoice.** These runs executed on a Max
subscription, so no per-token charge was actually incurred. The figure is the
Claude Code CLI's own `total_cost_usd` from each run's terminal `result` event —
i.e. what the same token volume would have cost at first-party API list prices
for `claude-opus-5`. It is reported because it is the only cost signal that
scales with the behaviour under test; treat it as a relative measure between the
two conditions, not as money spent.

Per-task price is right-skewed in both conditions — pooled across all 80 runs
per condition, baseline spans $3.69–$26.98 and dense $2.21–$16.00, because a
few long tasks dominate. The medians ($8.78 baseline, $6.16 dense, **−29.8%**)
track the means closely, so the saving is not an artefact of the tail.

### 2.2 Per-arm detail

| arm               | condition               | CLI     | pass      | pure agent time (sum) | avg / task    | median / task | wall-clock as run |
| ----------------- | ----------------------- | ------- | --------- | --------------------- | ------------- | ------------- | ----------------- |
| r01               | skill offered (control) | 2.1.220 | 17        | 525.4 min             | 26.27 min     | 23.06 min     | 258 min           |
| r02               | baseline                | 2.1.220 | 17        | 553.5 min             | 27.68 min     | 25.99 min     | 332 min           |
| r03               | baseline                | 2.1.222 | 15        | 559.8 min             | 27.99 min     | 25.63 min     | 435 min ⚠         |
| r04               | baseline                | 2.1.222 | 16        | 585.8 min             | 29.29 min     | 29.84 min     | 310 min ⚠         |
| v3-r1             | dense                   | 2.1.220 | 17        | 397.9 min             | 19.90 min     | 16.83 min     | 146 min           |
| v3-r2             | dense                   | 2.1.221 | 15        | 392.1 min             | 19.61 min     | 17.22 min     | 1206 min ⚠        |
| v3-r3             | dense                   | 2.1.221 | 14        | 399.5 min             | 19.97 min     | 16.71 min     | 188 min           |
| v3-r4             | dense                   | 2.1.222 | 17        | 420.5 min             | 21.02 min     | 16.84 min     | 250 min ⚠         |
| **baseline mean** |                         |         | **16.25** | **556.1 min**         | **27.81 min** |               |                   |
| **dense mean**    |                         |         | **15.75** | **402.5 min**         | **20.13 min** |               |                   |

⚠ = wall-clock inflated by an infrastructure stall or a contract-gate stop, not
by agent work. r03 lost ~3.7 h to an OAuth expiry; v3-r2 lost ~17 h to an
overnight stall. **The pure-agent-time columns are unaffected** — those arms'
per-task figures sit within 2% of their condition's mean, which is the point of
measuring it that way.

### 2.3 Tokens per task

| arm               | input      | cached     | output    | rounds   |
| ----------------- | ---------- | ---------- | --------- | -------- |
| r01               | 11.60M     | 11.44M     | 80.1k     | 90.0     |
| r02               | 11.35M     | 11.19M     | 80.1k     | 90.2     |
| r03               | 11.91M     | 11.73M     | 82.3k     | 91.5     |
| r04               | 13.05M     | 12.82M     | 86.6k     | 96.3     |
| v3-r1             | 8.07M      | 7.94M      | 61.9k     | 72.2     |
| v3-r2             | 7.42M      | 7.29M      | 59.5k     | 70.6     |
| v3-r3             | 7.64M      | 7.50M      | 60.7k     | 72.6     |
| v3-r4             | 8.33M      | 8.19M      | 62.2k     | 73.0     |
| **baseline mean** | **11.93M** | **11.75M** | **82.2k** | **91.8** |
| **dense mean**    | **7.77M**  | **7.64M**  | **60.4k** | **71.4** |

Cached tokens are approximately 98.4% of input in both conditions. The saving is fewer and
shorter turns, not a cheaper prompt.

### 2.4 Effect size against replicate spread

| measure                | baseline         | dense            | ranges                       |
| ---------------------- | ---------------- | ---------------- | ---------------------------- |
| pure agent time / task | 27.81 ± 1.24 min | 20.13 ± 0.62 min | disjoint                     |
| input / task           | 11.93M ± 0.75M   | 7.77M ± 0.41M    | disjoint                     |
| output / task          | 82.2k ± 3.1k     | 60.4k ± 1.2k     | disjoint                     |
| rounds / task          | 91.8 ± 3.0       | 71.4 ± 1.1       | disjoint                     |
| **pass**               | **16.25 ± 0.96** | **15.75 ± 1.50** | **almost fully overlapping** |

Every efficiency measure separates by 6–7 replicate standard deviations. The
pass difference is 0.4 standard deviations — smaller than the spread _within_
the baseline condition, which itself ranges 15 to 17.

---

### 2.5 Per-task results

`official` is the task pass rate across 22,887 scored trials in the public
DeepSWE v1.1 inventory, shown for calibration.

| task                                                | lang       | band        | official | r01  | r02  | r03  | r04  | v3-r1 | v3-r2 | v3-r3 | v3-r4 | base | dense |
| --------------------------------------------------- | ---------- | ----------- | -------- | ---- | ---- | ---- | ---- | ----- | ----- | ----- | ----- | ---- | ----- |
| abs-stepped-slices                                  | go         | medium-easy | 0.72     | FAIL | PASS | FAIL | PASS | PASS  | FAIL  | FAIL  | PASS  | 2/4  | 2/4   |
| actionlint-action-pinning-lint                      | go         | easy        | 0.83     | PASS | PASS | PASS | PASS | PASS  | PASS  | PASS  | PASS  | 4/4  | 4/4   |
| awilix-async-container-initialization               | typescript | medium-hard | 0.33     | FAIL | FAIL | FAIL | FAIL | FAIL  | FAIL  | FAIL  | FAIL  | 0/4  | 0/4   |
| bandit-incremental-cache-control                    | python     | medium-hard | 0.52     | PASS | PASS | PASS | PASS | PASS  | PASS  | PASS  | PASS  | 4/4  | 4/4   |
| boa-hierarchical-evaluation-cancellation            | rust       | medium-hard | 0.48     | PASS | PASS | PASS | PASS | PASS  | PASS  | PASS  | PASS  | 4/4  | 4/4   |
| csstree-shorthand-expansion-compression             | javascript | medium-hard | 0.28     | FAIL | PASS | FAIL | FAIL | FAIL  | FAIL  | FAIL  | FAIL  | 1/4  | 0/4   |
| dasel-html-document-format                          | go         | hard        | 0.49     | PASS | PASS | PASS | PASS | PASS  | PASS  | PASS  | PASS  | 4/4  | 4/4   |
| dynamodb-toolbox-conditional-attribute-requirements | typescript | medium-easy | 0.74     | PASS | PASS | PASS | PASS | PASS  | PASS  | PASS  | PASS  | 4/4  | 4/4   |
| fd-deterministic-multi-key-sorting                  | rust       | medium-easy | 0.58     | PASS | PASS | FAIL | FAIL | FAIL  | FAIL  | PASS  | FAIL  | 2/4  | 1/4   |
| happy-dom-abort-pending-body-reads                  | typescript | easy        | 0.91     | PASS | PASS | PASS | PASS | PASS  | PASS  | PASS  | PASS  | 4/4  | 4/4   |
| katex-multicolumn-array-spans                       | javascript | hard        | 0.30     | PASS | PASS | PASS | PASS | PASS  | PASS  | FAIL  | PASS  | 4/4  | 3/4   |
| langchain-request-coalescing                        | python     | hard        | 0.41     | PASS | FAIL | PASS | PASS | PASS  | PASS  | FAIL  | PASS  | 3/4  | 3/4   |
| narwhals-rolling-window-suite                       | python     | easy        | 0.89     | PASS | PASS | PASS | PASS | PASS  | PASS  | PASS  | PASS  | 4/4  | 4/4   |
| numba-stencil-boundary-modes                        | python     | medium-easy | 0.65     | PASS | PASS | PASS | PASS | PASS  | PASS  | PASS  | PASS  | 4/4  | 4/4   |
| pest-character-class-coalescing                     | rust       | hard        | 0.22     | PASS | PASS | PASS | PASS | PASS  | PASS  | PASS  | PASS  | 4/4  | 4/4   |
| quill-shared-toolbar-focus                          | typescript | hard        | 0.25     | PASS | FAIL | FAIL | FAIL | PASS  | FAIL  | FAIL  | PASS  | 1/4  | 2/4   |
| testem-per-launcher-reports                         | javascript | medium-easy | 0.70     | PASS | PASS | PASS | PASS | PASS  | PASS  | PASS  | PASS  | 4/4  | 4/4   |
| wasmi-trap-coredumps                                | rust       | easy        | 0.68     | PASS | PASS | PASS | PASS | PASS  | PASS  | PASS  | PASS  | 4/4  | 4/4   |
| yaegi-go-embed-directives                           | go         | medium-hard | 0.62     | PASS | PASS | PASS | PASS | PASS  | PASS  | PASS  | PASS  | 4/4  | 4/4   |
| yjs-map-conflict-detection                          | javascript | easy        | 0.77     | PASS | PASS | PASS | PASS | PASS  | PASS  | PASS  | PASS  | 4/4  | 4/4   |

### 2.6 Per-task cost (condition means, n=4)

| task                                                | base input | dense input | base output | dense output | base rounds | dense rounds |
| --------------------------------------------------- | ---------- | ----------- | ----------- | ------------ | ----------- | ------------ |
| abs-stepped-slices                                  | 5.01M      | 2.17M       | 55k         | 32k          | 67.3        | 41.0         |
| actionlint-action-pinning-lint                      | 14.38M     | 8.97M       | 80k         | 62k          | 105.0       | 77.3         |
| awilix-async-container-initialization               | 7.13M      | 4.33M       | 73k         | 54k          | 68.8        | 51.8         |
| bandit-incremental-cache-control                    | 11.62M     | 6.52M       | 82k         | 54k          | 100.0       | 69.5         |
| boa-hierarchical-evaluation-cancellation            | 15.01M     | 11.85M      | 84k         | 72k          | 105.0       | 88.3         |
| csstree-shorthand-expansion-compression             | 6.51M      | 2.07M       | 86k         | 55k          | 59.8        | 28.0         |
| dasel-html-document-format                          | 5.38M      | 2.94M       | 64k         | 42k          | 58.5        | 43.5         |
| dynamodb-toolbox-conditional-attribute-requirements | 29.51M     | 19.54M      | 118k        | 85k          | 166.8       | 137.5        |
| fd-deterministic-multi-key-sorting                  | 8.31M      | 5.75M       | 58k         | 46k          | 71.5        | 56.0         |
| happy-dom-abort-pending-body-reads                  | 16.12M     | 9.07M       | 77k         | 59k          | 121.5       | 79.0         |
| katex-multicolumn-array-spans                       | 8.92M      | 7.01M       | 77k         | 62k          | 78.0        | 73.3         |
| langchain-request-coalescing                        | 9.39M      | 3.71M       | 99.5k       | 55.1k       | 75.5        | 45.8         |
| narwhals-rolling-window-suite                       | 18.13M     | 12.55M      | 102k        | 75k          | 131.0       | 110.8        |
| numba-stencil-boundary-modes                        | 9.77M      | 7.01M       | 71k         | 54k          | 83.0        | 69.5         |
| pest-character-class-coalescing                     | 8.24M      | 6.08M       | 66k         | 49k          | 77.8        | 69.8         |
| quill-shared-toolbar-focus                          | 14.55M     | 7.97M       | 105k        | 77k          | 93.5        | 64.8         |
| testem-per-launcher-reports                         | 7.25M      | 4.20M       | 51k         | 38k          | 80.5        | 61.8         |
| wasmi-trap-coredumps                                | 19.38M     | 16.55M      | 92k         | 77k          | 112.0       | 108.3        |
| yaegi-go-embed-directives                           | 12.10M     | 7.44M       | 86k         | 64k          | 96.0        | 76.5         |
| yjs-map-conflict-detection                          | 11.97M     | 9.69M       | 118k        | 96k          | 83.5        | 76.3         |

---

## 3. Threats to validity

### 3.1 The suite cannot resolve the accuracy question

Of 20 tasks, **13 pass in all 8 runs and 1 fail in all 8**. Only 6 tasks ever
flip, and they flip in both directions (one favours dense, three favour baseline,
two split evenly). No task passes 4/4 under one condition and fails 4/4 under
the other. With 14 of 20 tasks carrying no signal, the measurement floor is
roughly ±1.3 tasks and the effect being looked for is below it.

### 3.2 Efficiency is measured on a floor of successful runs only

Pure agent time excludes failed attempts by construction. That is correct for
"how much work does a solve take" and wrong for "what does a run cost end to
end". Seven jobs across all runs failed for non-model reasons (5 OAuth expiry,
1 host-command contract violation, 1 provider content filter); all were re-run
and none was scored, but their compute is not in the totals.

### 3.3 Non-determinism is not controlled

Temperature is not pinned and the corpus tasks have genuine ambiguity. The 6
flipping tasks are the visible consequence.

### 3.4 CLI version is a confound

Runs span three CLI builds. Coverage is uneven — 2.1.221 appears only in the
dense condition:

| CLI     | baseline arms | dense arms   |
| ------- | ------------- | ------------ |
| 2.1.220 | r01, r02      | v3-r1        |
| 2.1.221 | —             | v3-r2, v3-r3 |
| 2.1.222 | r03, r04      | v3-r4        |

Within the dense condition, per-task agent time varies by 1.4 min across the
three builds while the baseline gap is 7.7 min, so a build effect large enough
to explain the headline result is not plausible — but it is not excluded either.
