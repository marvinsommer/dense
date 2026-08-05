#!/usr/bin/env python3
"""Benchmark terseness skills via the Claude Code CLI instead of the raw Anthropic API.

Adapted from JuliusBrussee/caveman benchmarks/run.py. Same prompts, same median-output-token
metric, same table format. Differences from the original are documented in ADAPTATION.md.

  python3 run_cli.py --dry-run
  python3 run_cli.py --arms none dense caveman --trials 3 --model claude-opus-5
"""

import argparse
import atexit
import contextlib
import json
import os
import pwd
import shutil
import signal
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_VERSION = "2.0.0-cli"
SCRIPT_DIR = Path(__file__).parent
PROMPTS_PATH = SCRIPT_DIR / "prompts.json"
SKILLS_DIR = SCRIPT_DIR / "skills"
RESULTS_DIR = SCRIPT_DIR / "results"
BENCH_HOME = SCRIPT_DIR / ".benchhome"

NORMAL_SYSTEM = "You are a helpful assistant."

# Tools are disabled so the CLI produces one plain generation per prompt, matching the
# single-shot shape of the original API benchmark. Without this the model may run tools,
# which turns output tokens into a measure of agentic behaviour rather than verbosity.
NO_TOOLS = [
    "Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebFetch", "WebSearch",
    "Task", "TodoWrite", "NotebookEdit", "Skill", "Agent",
]


REAL_HOME = Path(pwd.getpwuid(os.getuid()).pw_dir)
USER_MEMORY = REAL_HOME / ".claude" / "CLAUDE.md"
MEMORY_BAK = REAL_HOME / ".claude" / "CLAUDE.md.benchbak"


@contextlib.contextmanager
def quarantine_user_memory():
    """Move ~/.claude/CLAUDE.md aside for the duration of the run.

    Claude Code loads user memory from the real home even when HOME and CLAUDE_CONFIG_DIR
    are overridden (verified empirically), so a control arm is only clean if the file is
    genuinely absent. Restored on normal exit, exception, SIGINT and SIGTERM.
    """
    if not USER_MEMORY.exists():
        yield False
        return

    def restore(*_):
        if MEMORY_BAK.exists() and not USER_MEMORY.exists():
            MEMORY_BAK.rename(USER_MEMORY)
            print(f"restored {USER_MEMORY}", file=sys.stderr)

    USER_MEMORY.rename(MEMORY_BAK)
    print(f"quarantined {USER_MEMORY} -> {MEMORY_BAK.name}", file=sys.stderr)
    atexit.register(restore)
    prev = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    for s in prev:
        signal.signal(s, lambda sig, frm: (restore(), sys.exit(130)))
    try:
        yield True
    finally:
        restore()
        for s, h in prev.items():
            signal.signal(s, h)


def preflight(model):
    """Prove the control arm sees no terseness instruction before spending on a full run."""
    probe = ("Quote verbatim any instruction you were given about how terse or minimal your "
             "responses should be. If you were given none, reply exactly: NONE")
    got = call_cli(model, NORMAL_SYSTEM, probe)["text"].lower()
    dirty = [w for w in ("dense", "terse", "minimal", "smallest correct") if w in got]
    # 'terse'/'minimal' appear in the probe itself, so only a skill name or body is damning.
    if "dense" in got or "smallest correct" in got:
        sys.exit(f"PREFLIGHT FAILED: control arm still sees a terseness instruction {dirty}\n"
                 f"  probe answer: {got[:200]}")
    print(f"preflight OK: control arm is clean ({got.strip()[:60]!r})", file=sys.stderr)


def load_prompts():
    with open(PROMPTS_PATH) as f:
        return json.load(f)["prompts"]


def system_for_arm(arm):
    if arm == "none":
        return NORMAL_SYSTEM
    path = SKILLS_DIR / f"{arm}.md"
    if not path.exists():
        sys.exit(f"ERROR: no skill file for arm '{arm}' at {path}")
    return path.read_text()


def ensure_bench_home():
    """Isolated HOME: credentials only, no CLAUDE.md, no skills, no settings, no hooks.

    Without this the user's global CLAUDE.md and skill directory leak into every arm,
    including the control — which would silently contaminate the baseline.
    """
    claude_dir = BENCH_HOME / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    src = Path.home() / ".claude" / ".credentials.json"
    dst = claude_dir / ".credentials.json"
    if src.exists() and not dst.exists():
        shutil.copy2(src, dst)
    for leak in ("CLAUDE.md", "skills", "settings.json", "plugins"):
        p = claude_dir / leak
        if p.exists():
            sys.exit(f"ERROR: {p} would contaminate the run; remove it")
    return BENCH_HOME


def call_cli(model, system, prompt, timeout=600, max_retries=2):
    env = dict(os.environ)
    env["HOME"] = str(ensure_bench_home())
    env.pop("ANTHROPIC_API_KEY", None)
    cmd = [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--model", model,
        "--system-prompt", system,
        "--disallowed-tools", *NO_TOOLS,
    ]
    for attempt in range(max_retries + 1):
        started = time.time()
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, env=env,
                cwd=str(SCRIPT_DIR),
            )
            data = json.loads(proc.stdout)
            if data.get("is_error"):
                raise RuntimeError(data.get("result", "cli reported is_error"))
            usage = data.get("usage", {})
            return {
                "output_tokens": usage.get("output_tokens", 0),
                "input_tokens": usage.get("input_tokens", 0),
                "cost_usd": data.get("total_cost_usd", 0.0),
                "num_turns": data.get("num_turns", 0),
                "wall_s": round(time.time() - started, 1),
                "text": data.get("result", ""),
                "chars": len(data.get("result", "") or ""),
            }
        except Exception as e:  # noqa: BLE001 - retry anything transient
            if attempt < max_retries:
                delay = [5, 15][min(attempt, 1)]
                print(f"    retry in {delay}s ({type(e).__name__}: {e})", file=sys.stderr)
                time.sleep(delay)
            else:
                raise


def run(model, prompts, arms, trials, concurrency=1):
    jobs = []
    for entry in prompts:
        for arm in arms:
            for t in range(trials):
                jobs.append((entry, arm, t))

    done = {"n": 0}
    total = len(jobs)

    def work(job):
        entry, arm, t = job
        out = call_cli(model, system_for_arm(arm), entry["prompt"])
        done["n"] += 1
        print(f"  [{done['n']}/{total}] {entry['id']} | {arm} | trial {t + 1} "
              f"| {out['output_tokens']} tok", file=sys.stderr)
        return (entry["id"], arm, out)

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        finished = list(ex.map(work, jobs))

    by_id = {e["id"]: {"id": e["id"], "category": e["category"], "prompt": e["prompt"],
                       **{a: [] for a in arms}} for e in prompts}
    for pid, arm, out in finished:
        by_id[pid][arm].append(out)
    return [by_id[e["id"]] for e in prompts]


def compute(results, arms):
    base = arms[0]
    rows, per_arm = [], {a: [] for a in arms}
    for e in results:
        r = {"id": e["id"], "category": e["category"]}
        med = {a: statistics.median([t["output_tokens"] for t in e[a]]) for a in arms}
        for a in arms:
            r[a] = int(med[a])
            per_arm[a].append(med[a])
            if a != base:
                r[f"{a}_saved_pct"] = round((1 - med[a] / med[base]) * 100) if med[base] else 0
        rows.append(r)
    summary = {a: {"mean_median_tokens": round(statistics.mean(per_arm[a]))} for a in arms}
    for a in arms:
        if a != base:
            sav = [(1 - per_arm[a][i] / per_arm[base][i]) * 100
                   for i in range(len(rows)) if per_arm[base][i]]
            summary[a]["avg_saved_pct"] = round(statistics.mean(sav))
            summary[a]["min_saved_pct"] = round(min(sav))
            summary[a]["max_saved_pct"] = round(max(sav))
    return rows, summary


LABELS = {
    "react-rerender": "Explain React re-render bug",
    "auth-middleware-fix": "Fix auth middleware token expiry",
    "postgres-pool": "Set up PostgreSQL connection pool",
    "git-rebase-merge": "Explain git rebase vs merge",
    "async-refactor": "Refactor callback to async/await",
    "microservices-monolith": "Architecture: microservices vs monolith",
    "pr-security-review": "Review PR for security issues",
    "docker-multi-stage": "Docker multi-stage build",
    "race-condition-debug": "Debug PostgreSQL race condition",
    "error-boundary": "Implement React error boundary",
}


def table(rows, summary, arms):
    base = arms[0]
    head = "| Task |" + "".join(f" {a} |" for a in arms) + \
           "".join(f" {a} saved |" for a in arms if a != base)
    sep = "|------|" + "---:|" * (len(arms) + len(arms) - 1)
    out = [head, sep]
    for r in rows:
        line = f"| {LABELS.get(r['id'], r['id'])} |"
        line += "".join(f" {r[a]} |" for a in arms)
        line += "".join(f" {r[f'{a}_saved_pct']}% |" for a in arms if a != base)
        out.append(line)
    line = "| **Average** |" + "".join(f" **{summary[a]['mean_median_tokens']}** |" for a in arms)
    line += "".join(f" **{summary[a]['avg_saved_pct']}%** |" for a in arms if a != base)
    out.append(line)
    out.append("")
    for a in arms:
        if a != base:
            s = summary[a]
            out.append(f"*{a}: range {s['min_saved_pct']}%–{s['max_saved_pct']}% across prompts.*")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--arms", nargs="+", default=["none", "dense", "caveman"],
                    help="first arm is the baseline")
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-quarantine", action="store_true",
                    help="skip moving ~/.claude/CLAUDE.md aside (control arm will be dirty)")
    args = ap.parse_args()

    prompts = load_prompts()
    if args.dry_run:
        print(f"model:   {args.model}")
        print(f"arms:    {args.arms} (baseline: {args.arms[0]})")
        print(f"trials:  {args.trials}")
        print(f"prompts: {len(prompts)}")
        print(f"total CLI calls: {len(prompts) * len(args.arms) * args.trials}")
        for a in args.arms:
            n = len(system_for_arm(a))
            print(f"  arm {a:9} system prompt {n} chars")
        return

    ensure_bench_home()
    print(f"{len(prompts)} prompts x {len(args.arms)} arms x {args.trials} trials "
          f"= {len(prompts) * len(args.arms) * args.trials} calls", file=sys.stderr)

    ctx = contextlib.nullcontext(False) if args.no_quarantine else quarantine_user_memory()
    with ctx:
        preflight(args.model)
        results = run(args.model, prompts, args.arms, args.trials, args.concurrency)
    rows, summary = compute(results, args.arms)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"cli_benchmark_{ts}.json"
    with open(path, "w") as f:
        json.dump({
            "metadata": {"script_version": SCRIPT_VERSION, "model": args.model,
                         "arms": args.arms, "trials": args.trials,
                         "date": datetime.now(timezone.utc).isoformat(),
                         "transport": "claude CLI --print, tools disabled, isolated HOME"},
            "summary": summary, "rows": rows, "raw": results,
        }, f, indent=2)
    print(f"\nsaved: {path}", file=sys.stderr)
    print(table(rows, summary, args.arms))


if __name__ == "__main__":
    main()
