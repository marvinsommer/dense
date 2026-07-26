# Benchmarks

Two independent measurements of DENSE against a **verified clean control**, run 2026-07-26 on
`claude-opus-5` through the Claude Code CLI.

| benchmark | task shape | prose share of output | DENSE effect | n |
|---|---|---:|---:|---:|
| [`chat/`](chat/CAVEMANBENCHMARK.md) | single-turn Q&A (caveman's 10-prompt suite) | ~100% | **−82%** | 3 trials × 10 prompts |
| [`agentic/`](agentic/AGENTICBENCHMARK.md) | long tool loop, ~900-line code deliverable | 0.2% visible prose | **−19%** | 4 runs/arm |

**The effect is strongly task-shaped.** A compression skill can only remove ceremony the model
was going to write. Chat answers are almost entirely ceremony; a database engine is almost
entirely not. The −47% to −63% in this repo's README sits between these two poles, which is
where a mixed task set should land.

Secondary results worth noting:

- On caveman's own suite, DENSE (−82%) beat caveman (−62%) **on all 10 prompts**, and the
  harness reproduced caveman's published −65% claim to within 3 points through a different
  transport — some evidence the adaptation is faithful.
- **Variance collapses under compression.** Control-arm spread was 3–8× that of the DENSE arm
  in both benchmarks (chat: 605 vs 73 tokens per cell; agentic: sd 8,342 vs 2,804).
  Predictability may be worth as much as the mean saving.
- The agentic saving is **process, not product**: 12% fewer turns and 22% less wall time, with
  final artifact size unchanged (880 vs 914 lines).

## Read this before trusting any control arm

Both benchmarks were initially measured **wrong, in the same way**, and the agentic result came
out with the **opposite sign** (+17.3%, DENSE looking worse) before the flaw was found.

Two independent paths put DENSE into the *control* group:

1. A global `~/.claude/CLAUDE.md` saying "always use the dense skill" loads into **every**
   Claude invocation, including `claude -p` subprocesses.
2. A skill invoked in a parent session propagates into every Agent subagent it spawns.

Setting an isolated `HOME` **and** `CLAUDE_CONFIG_DIR` does not fix path 1 — verified with a
planted marker file, Claude Code loads user memory from the real home regardless. The runners
here quarantine the file, probe the control arm before spending anything, and grep the run
transcripts afterwards. Anyone reproducing this on a machine with a global CLAUDE.md or an
active skill should assume their control is dirty until they have proven otherwise.

Superseded figures are listed and marked void in
[`agentic/AGENTICBENCHMARK.md`](agentic/AGENTICBENCHMARK.md#superseded-results--do-not-cite).

## What these benchmarks do not show

- **Neither measures correctness of the compressed prose.** The chat suite counts tokens and
  nothing else — an 82% cut on "review this PR for security issues" is indistinguishable, by
  that benchmark, from an 82% cut that dropped the SQL-injection finding.
- The agentic benchmark **does** gate on execution (21 hidden requirements), but both arms
  scored 4/4, so it rules out a catastrophic correctness cost without providing a correctness
  *signal*. The task would need to sit off ceiling for that.
- Small n. The agentic effect is marginal at conventional thresholds (t = −2.50, 95% CI
  −22,295 … +323). Read −19% as a well-supported direction with a loosely pinned magnitude.
- One model, one machine, one pass per cell in the agentic arm.

## Layout

```
chat/
  CAVEMANBENCHMARK.md   full write-up: results, method, deviations from upstream, limitations
  run_cli.py            runner (CLAUDE.md quarantine, isolated HOME, preflight probe)
  run_upstream.py       upstream benchmarks/run.py, unmodified, for diffing
  prompts.json          upstream's 10 prompts, unmodified
  skills/               system prompts used per arm
  results/              every one of the 90 calls, including full response text

agentic/
  AGENTICBENCHMARK.md   full write-up
  run_t5_cli.py         runner
  t5_src.js             readable source of the 21-requirement progressive-reveal gate
  t5-dbengine/          pristine task template (gate.js compiled opaque, db.js stub)
  results/              per-run metrics
```

Reproduction commands are in each write-up. Both need the `claude` CLI authenticated (OAuth is
fine); the agentic runner also needs Node.

The 16 earlier subagent runs with the contaminated control are **not** included here — they are
documented but should not be cited.

## Attribution

`chat/prompts.json`, `chat/run_upstream.py` and `chat/skills/caveman.md` are from
[JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) (MIT). `chat/run_cli.py` is
adapted from that project's `benchmarks/run.py`. See [NOTICE.md](NOTICE.md).
