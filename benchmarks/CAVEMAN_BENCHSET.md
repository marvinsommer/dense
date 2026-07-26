# Caveman benchmark suite, run through the Claude Code CLI

Adaptation of [`JuliusBrussee/caveman`](https://github.com/JuliusBrussee/caveman/tree/main/benchmarks)
`benchmarks/run.py` to drive the **Claude Code CLI** instead of the raw Anthropic API, and to
compare **three** arms instead of two. Same 10 prompts, same median-output-token metric, same
table format.

- Date: **2026-07-26**
- Model: **claude-opus-5**
- Arms: `none` (baseline) / `dense` / `caveman`
- 10 prompts × 3 arms × 3 trials = **90 calls**, total spend **$3.13**
- Raw data: `chat/results/cli_benchmark_20260726_203116.json` (every call, including full text)
- Runner: `chat/run_cli.py`

## Results

| Task | none | dense | caveman | dense saved | caveman saved |
|------|---:|---:|---:|---:|---:|
| Explain React re-render bug | 1191 | 204 | 394 | 83% | 67% |
| Fix auth middleware token expiry | 2978 | 342 | 387 | 89% | 87% |
| Set up PostgreSQL connection pool | 3264 | 594 | 984 | 82% | 70% |
| Explain git rebase vs merge | 1322 | 225 | 595 | 83% | 55% |
| Refactor callback to async/await | 757 | 172 | 287 | 77% | 62% |
| Architecture: microservices vs monolith | 2103 | 420 | 1074 | 80% | 49% |
| Review PR for security issues | 1642 | 382 | 619 | 77% | 62% |
| Docker multi-stage build | 2390 | 340 | 1009 | 86% | 58% |
| Debug PostgreSQL race condition | 1677 | 260 | 664 | 84% | 60% |
| Implement React error boundary | 2190 | 441 | 1023 | 80% | 53% |
| **Average** | **1951** | **338** | **704** | **82%** | **62%** |

*dense: range 77%–89% across prompts. caveman: range 49%–87%.*

DENSE beats caveman on all 10 prompts, on caveman's own benchmark.

### Per-arm detail

| arm | mean out tok | median | spend $ | mean within-cell spread (3 trials) | chars/tok | mean chars |
|---|---:|---:|---:|---:|---:|---:|
| none | 1977 | 1845 | 1.75 | 605 (max 1634) | 2.09 | 4141 |
| dense | 336 | 338 | 0.53 | 73 (max 157) | 2.35 | 790 |
| caveman | 690 | 642 | 0.85 | 153 (max 297) | 2.33 | 1606 |

Two things worth noting in that table:

**Variance scales with verbosity.** The control arm's three trials on the same prompt differ
by 605 output tokens on average and by 1634 at worst — the uncompressed arm is far noisier
than either compressed arm. Any single-pass measurement of a baseline like this carries a
large error bar.

**The compression is density, not truncation.** Both skill arms produce *more* characters per
output token than the control (2.35 and 2.33 vs 2.09). If the savings came from answers being
cut off mid-thought, this ratio would not move in that direction. This is suggestive, not
conclusive — see Limitations.

## Method

Each call is one non-interactive CLI invocation with tools disabled, so it produces a single
plain generation (`num_turns: 1`) — matching the single-shot shape of the upstream API
benchmark:

```
claude -p "<prompt>" --output-format json --model <model> \
       --system-prompt "<arm system prompt>" \
       --disallowed-tools Bash Read Write Edit Glob Grep WebFetch WebSearch Task TodoWrite NotebookEdit Skill Agent
```

Output tokens come from `usage.output_tokens` in the CLI's JSON result — provider-reported,
not estimated. Per prompt and arm, the **median of 3 trials** is taken, then savings are
computed against the same prompt's `none` median, then averaged across prompts. This is the
upstream statistic, unchanged.

Arm system prompts follow upstream exactly: `none` is `"You are a helpful assistant."`, and a
skill arm's system prompt is the **entire SKILL.md file including frontmatter**. Skill prompt
sizes: `dense.md` 1,602 chars, `caveman.md` 5,017 chars — caveman's instructions are ~3.1×
larger, and that cost is paid on every turn in real use.

### Control-arm isolation — required, and not optional

A global `~/.claude/CLAUDE.md` is loaded into **every** CLI invocation and will silently
contaminate the control arm. On this machine that file said "always use the dense skill",
which would have made the baseline a DENSE run.

Setting an isolated `HOME` **and** `CLAUDE_CONFIG_DIR` is *not* sufficient — verified
empirically by planting a marker file: Claude Code loads user memory from the real home
regardless, and loads both files. The runner therefore:

1. **Quarantines** `~/.claude/CLAUDE.md` (renames to `CLAUDE.md.benchbak`) for the duration of
   the run, restoring it via `finally` + `atexit` + SIGINT/SIGTERM handlers.
2. Uses an isolated `HOME` (`.benchhome/`) containing credentials only — no CLAUDE.md, no
   skills, no settings, no hooks — and refuses to start if any of those appear there.
3. Runs a **preflight probe** before spending anything: it asks the control arm to quote any
   instruction it was given about terseness. The run aborts unless the answer is clean. On
   this run it answered `none`.

Skipping step 1 (`--no-quarantine`) produces a dirty control and numbers that mean nothing.

## Deviations from upstream `run.py`

| | upstream | here |
|---|---|---|
| transport | `anthropic` SDK, `messages.create` | `claude` CLI, `--print --output-format json` |
| temperature | `0` | **not controllable** — the CLI does not expose it |
| `max_tokens` | `4096` | CLI default (32000) |
| arms | 2 (normal, caveman) | N (baseline first; `none dense caveman` here) |
| system prompt | API `system` param | `--system-prompt` |
| scaffolding | none | Claude Code's tool definitions and env are in context in **all** arms |
| isolation | not needed | CLAUDE.md quarantine + isolated HOME + preflight |
| concurrency | serial | `--concurrency` (4 here) |

The missing temperature control adds variance relative to upstream; three trials and a median
mitigate but do not eliminate it. Removing the 4096-token cap **raises** measured savings
relative to upstream if any control answer would have been truncated — here the control mean
is 1,977 tokens with a maximum of 3,264, so the cap would rarely have bound, but it is a real
difference in what is being measured.

## Limitations

- **No correctness measurement anywhere in this suite.** It counts tokens and nothing else. An
  82% reduction on "review this PR for security issues" is indistinguishable, by this
  benchmark, from an 82% reduction that dropped the SQL-injection finding. The `chars/tok`
  evidence above argues against gross truncation but is not a quality check. Any claim built
  on these numbers needs execution-graded or rubric-graded validation added.
- **10 prompts, 3 trials, one model.** No confidence intervals are reported because the
  upstream statistic (median of 3, then mean across prompts) does not support them well.
- **Chat-shaped prompts only.** All 10 are single-turn questions whose entire deliverable is
  prose. This is the maximum-compressible-surface case. On agentic tool-loop tasks where the
  deliverable is code, the same DENSE skill measured ≈0% reduction (see [`AGENTIC_BENCH.md`](AGENTIC_BENCH.md), where
  visible prose was 0.21% of billed output). Do not generalise 82% to agentic work.
- **`num_turns: 1` by construction.** Tools are disabled, so this says nothing about
  multi-turn or tool-using behaviour.

## Reproducing

```bash
cd benchmarks/chat
python3 run_cli.py --dry-run
python3 run_cli.py --arms none dense caveman --trials 3 --model claude-opus-5 --concurrency 4
```

Requires the `claude` CLI authenticated (OAuth is fine) and `chat/skills/<arm>.md` for each
non-baseline arm. Upstream `run.py` is kept alongside as `chat/run_upstream.py` for diffing.
