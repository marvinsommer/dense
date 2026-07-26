# DENSE on agentic coding work — t5 benchmark

Companion to [`CAVEMAN_BENCHSET.md`](CAVEMAN_BENCHSET.md), which
measures the same skill on chat-shaped prompts. This one measures it on a long agentic
tool-loop task where the deliverable is code rather than prose.

**Headline: the savings are real but much smaller — −19% here against −82% on chat prompts.**
Compression still helps when there is barely any prose to compress; it just helps less.

- Date: **2026-07-26**
- Model: **claude-opus-5**
- Design: 4 control + 4 DENSE, one pass per cell, run concurrently
- Total spend: **$34.19**
- Raw data: `agentic/results/t5cli_results_20260726_211753.json`
- Runner: `agentic/run_t5_cli.py` · task harness: `agentic/t5-dbengine/` (built by `agentic/t5_src.js`)

## Results

```
run         out_tok  turns  wall_s  db_loc  gate
none-1       50,217     65     604     978  PASS
none-2       66,413     99     783     971  PASS
none-3       62,620    101     821     799  PASS
none-4       50,421     87     640     907  PASS
dense-1      44,514     87     557     839  PASS
dense-2      49,076     66     585    1006  PASS
dense-3      48,584     93     565     949  PASS
dense-4      43,553     64     512     728  PASS
```

| arm | out_tok | sd | turns | wall_s | db.js LOC | spend $ | gate |
|---|---:|---:|---:|---:|---:|---:|---:|
| none | 57,418 | 8,342 | 88.0 | 712 | 914 | 18.78 | 4/4 |
| dense | 46,432 | 2,804 | 77.5 | 555 | 880 | 15.41 | 4/4 |

**dense − none = −10,986 tokens (−19.1%), t = −2.50, 95% CI −22,295 … +323**

Three secondary observations, all consistent with the primary effect (and not independent of
it, so they corroborate rather than confirm):

- **12% fewer turns, 22% less wall time.** The saving comes from less deliberation and fewer
  iterations, not from shipping a smaller engine.
- **Final artifact size is unchanged** — 880 vs 914 lines of `db.js`, well inside noise. DENSE
  did not cut the deliverable; it cut the process of arriving at it.
- **Variance collapses: sd 8,342 → 2,804.** The uncompressed arm is 3× noisier. The chat
  benchmark showed the same pattern (per-cell spread 605 → 73 tokens). Predictability may be
  worth as much as the mean saving.

## The task

`t5-dbengine` asks for an in-memory document database engine built against a **progressively
revealed** specification. `gate.js` prints the next unmet requirement in full only once every
previous one still passes, so the model cannot see requirement *k+1* until *k* is green. 21
requirements escalate from `insert/get` through secondary indexes, transactions with rollback,
schema validation, TTL with a logical clock, keyset pagination, a query planner with
plan-choice assertions, and compaction — each putting pressure on design choices made earlier.
R21 requires the model to write its own regression suite with at least 80 assertions.

The harness is compiled to an opaque loader (base64-embedded source) so the requirement list
cannot be read ahead; the prompt instructs the model to treat it as a black box.

Scoring is binary per run: `node gate.js` prints `COMPLETE: all 21 requirements met` or names
the requirement it stopped at. This was re-run independently after the benchmark rather than
taken from the model's self-report.

## Task character: file edits, planned up front, almost no prose

This task is the opposite of a chat prompt, and the numbers say so. Character counts of
everything the model emitted across the 8 clean runs:

| arm | prose chars | tool-payload chars | of which Write/Edit | prose share of output |
|---|---:|---:|---:|---:|
| none | 3,543 | 354,587 | 329,541 (92.9%) | **0.99%** |
| dense | 1,509 | 291,859 | 238,690 (81.8%) | **0.51%** |

Tool calls, 4 runs per arm:

| arm | Edit | Bash | Read | Write |
|---|---:|---:|---:|---:|
| none | 205 | 109 | 24 | 10 |
| dense | 168 | 116 | 14 | 8 |

Three things follow:

**It is file-edit dominated.** 82–93% of everything the model emitted through tools is file
content. Prose is ~1% or less — two orders of magnitude below a chat answer, where prose *is*
the deliverable.

**It is planned, not exploratory.** `Write` fires only ~2 times per run while `Edit` fires
~42–51 times: the model composes the engine and the test suite in a couple of large planned
writes, then converges by patching them. `Read` is rare (3–6 per run) — it works from its own
plan and its memory of what it wrote rather than re-reading the file. The ~27–29 `Bash` calls
per run are gate verification.

**So the savings cannot be narration.** With prose at ~1%, DENSE's −19% has to come out of
code, patch size, and hidden deliberation. What is visible: file-edit payload fell **27.6%**
and `Edit` calls fell **18%**, while the final artifact stayed the same size. The model reached
an equivalent engine with materially less patching.


### Why this task

Chosen after measuring six candidate designs (`t1`–`t6`) for output volume:

| task | mechanism | turns | out_tok |
|---|---|---:|---:|
| t1-staged | 36 hidden conformance stages, one failure revealed at a time | 9 | 5,329 |
| t2-fullreveal | same 36 stages, all failures revealed at once | 9 | 4,465 |
| t3-security | 36 staged security cases | 16 | 2,099 |
| t4-chain | 12 progressively revealed requirements | 41 | 9,246 |
| t5-dbengine | 21 progressively revealed requirements + self-written suite | 62 | 41,092 |
| t6-visible | same 21 requirements, whole spec available up front | 23 | 45,886 |

Two findings shaped the choice. **Hiding test failures does not force iteration** — Opus 5
one-shot the 36-stage evaluator on its first verify run, so t1 and t2 came out the same.
And **turns and tokens are close to independent** — t3 had more turns than t1 but a quarter
the tokens. Output volume tracks the size of the artifact demanded, not the loop structure.
t5 was selected for the agentic arm because it combines large volume with many turns.

## Methodology

Each run is a **separate `claude` CLI process**, not an Agent subagent:

```
claude -p "<task>" --output-format json --model claude-opus-5 \
       --allowed-tools Read Write Edit Glob Grep Bash TodoWrite \
       [--append-system-prompt "<dense SKILL.md>"]      # dense arm only
```

with `cwd` set to that run's own copy of the pristine `t5-dbengine/` template. The control arm
gets Claude Code's ordinary agent system prompt and nothing else; the dense arm gets the same
plus the skill appended — which mirrors how a skill is actually deployed.

Output tokens are `usage.output_tokens` from the CLI's JSON result: provider-reported, not
estimated. Note this is the **billed** figure and includes reasoning tokens, which are not
persisted in transcripts — on the earlier subagent runs, visible content (prose plus every
tool-call payload) accounted for only 42–48% of billed output.

### Isolation — the part that previously went wrong

A global `~/.claude/CLAUDE.md` loads into every Claude invocation. On this machine it said
"always use the dense skill". The runner therefore quarantines it (rename to
`CLAUDE.md.benchbak`, restored via `finally` + `atexit` + SIGINT/SIGTERM), uses an isolated
`HOME` containing credentials only, and refuses to start if a CLAUDE.md, skills dir, settings
or plugins appear there.

Setting `HOME` and `CLAUDE_CONFIG_DIR` alone is **not sufficient** — verified by planting a
marker file: Claude Code still loads user memory from the real home, and loads both.

Verification that the control arm was clean, run against the actual transcripts afterwards:

```
control-arm scan          caveman  dense_body  claudemd
  none-1                        0           0         0
  none-2                        1*          0         0     *= ".../caveman-bench/.benchhome/" path string
  none-3                        0           0         0
  none-4                        0           0         0
```

## Superseded results — do not cite

An earlier version of this benchmark used **Agent subagents spawned from a session that had
the dense skill invoked**. The skill body propagated into the control arm: exactly **1
injection in every control run and 2 in every dense run** (grep for `smallest correct
response` across all 16 transcripts). Those runs compared *DENSE ×1 against DENSE ×2*, a dose
comparison, not presence versus absence.

| benchmark | reported | status |
|---|---|---|
| t5 subagent | none 42,173 / dense 49,474 → **+17.3%** | **void** — sign reverses to −19.1% with a clean control |
| t6 subagent | none 36,876 / dense 37,698 → **+2.2%** | **void** — no baseline |
| t6 code chars | −11.8%, t = −3.09 | **re-label** — measures DENSE ×2 vs ×1, not skill vs none |

What survives from those runs, because it does not depend on arm labels: absolute token
volumes, the task-design findings above, the prose/code split (visible prose was 0.21% of
billed output on t6), the 2.3× within-arm spread, and 16/16 gate passes.

The lesson generalises: **on any machine with a global CLAUDE.md or an active skill, a
"no-skill" control is dirty unless you prove otherwise.** Prove it by probing the control arm
before spending, and by grepping the run transcripts afterwards.

## Caveats

- **n = 4 per arm.** The effect is marginal at conventional thresholds (t = −2.50, CI upper
  bound +323). Read it as "a substantial reduction, marginally resolved", not as a settled
  −19%. Roughly 8–10 runs per arm would be needed to tighten it.
- **No correctness signal.** Both arms went 4/4, and the earlier subagent runs went 16/16.
  A suite everything passes cannot detect a correctness cost — it only rules out a
  catastrophic one. To measure correctness properly the task needs to sit off ceiling.
- **One model, one task, one pass per cell.** Nothing here speaks to Sonnet, to other agentic
  domains, or to multi-file work beyond this single ~900-line engine.
- **Billed output includes reasoning tokens** that cannot be inspected. Where exactly the 19%
  was saved — visible code, tool payloads, or hidden deliberation — is not resolved by this
  data.
- **DENSE was appended to the system prompt**, not loaded through the skill mechanism. Close
  to real deployment, not identical to it.
- The task rewards a design that generalises early. A skill instructing "smallest correct
  implementation" could plausibly be penalised by a progressively revealed spec; the data
  neither shows nor excludes this.

## Reproducing

```bash
cd benchmarks/agentic

# rebuild the task harness from source (optional — t5-dbengine/ is already built)
node -e 'const fs=require("fs"),s=fs.readFileSync("t5_src.js","utf8");
         fs.writeFileSync("t5-dbengine/gate.js",
           "const M=Buffer.from(\""+Buffer.from(s).toString("base64")+"\",\"base64\").toString(\"utf8\");\n"+
           "const Module=require(\"module\");const m=new Module(__filename,null);\n"+
           "m.filename=__filename;m.paths=Module._nodeModulePaths(__dirname);m._compile(M,__filename);")'

# run the benchmark (quarantines ~/.claude/CLAUDE.md for the duration)
python3 run_t5_cli.py --per-arm 4 --model claude-opus-5 --concurrency 4

# verify the control arm was clean
BH=../chat/.benchhome
for i in 1 2 3 4; do
  f=$(ls -t $BH/.claude/projects/*runs-none-$i/*.jsonl | head -1)
  echo "none-$i dense=$(grep -c 'smallest correct response' $f) claudemd=$(grep -c 'Always use the' $f)"
done
```

Requires the `claude` CLI authenticated (OAuth is fine), Node, and Python 3. `run_t5_cli.py`
imports `quarantine_user_memory` and `ensure_bench_home` from `chat/run_cli.py`.

| file | what it is |
|---|---|
| `agentic/run_t5_cli.py` | benchmark runner |
| `agentic/t5_src.js` | readable source of the 21-requirement gate |
| `agentic/t5-dbengine/` | pristine task template (`gate.js` compiled, `db.js` stub) |
| `agentic/results/` | per-run metrics from the 8 clean runs |
