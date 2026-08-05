#!/usr/bin/env python3
"""Rerun the t5 agentic benchmark with genuine arm isolation.

The earlier t5/t6 runs used Agent subagents spawned from a session that had the dense skill
invoked, so the skill body propagated into the CONTROL arm too (1 injection in every control
run, 2 in every dense run). This runner avoids that entirely: each run is a separate `claude`
CLI process with the user's CLAUDE.md quarantined, an isolated HOME, and the skill supplied
only via --append-system-prompt on the dense arm.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "chat"))
from run_cli import quarantine_user_memory, ensure_bench_home  # noqa: E402

ROOT = Path(__file__).parent
TEMPLATE = ROOT / "t5-dbengine"
RUNS = ROOT / "runs"
DENSE = (ROOT.parent / "chat" / "skills" / "dense.md").read_text()

TASK = """Build an in-memory document database engine in `db.js`.

You are not given the specification up front. Run `node gate.js`: it prints the next
requirement your engine does not yet meet, in full, together with the concrete assertion
that failed. Implement it, run `node gate.js` again, and it will either show you what is
still wrong with the current requirement or reveal the next one. There are 21 requirements.
Each is revealed only once every previous one still passes, so earlier behaviour must keep
working as the engine grows — later requirements will put real pressure on the design you
chose early.

Rules:
- Do not edit, decode, replace, delete or bypass `gate.js`. Treat it as a black box.
- You may create and modify `db.js` and anything under `tests/`. Nothing else.
- Node standard library only. No dependencies, no package.json.
- Keep going until `node gate.js` prints `COMPLETE: all 21 requirements met`. Do not stop
  early, do not ask questions, and do not report partial success — iterate until it completes.

When done, reply with only: the final requirement number reached, and the number of times you ran gate.js.
"""

TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash", "TodoWrite"]


def stage(arm, i):
    d = RUNS / f"{arm}-{i}"
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(TEMPLATE, d)
    return d


def run_one(job, model, timeout):
    arm, i = job
    d = stage(arm, i)
    env = dict(os.environ)
    env["HOME"] = str(ensure_bench_home())
    env.pop("ANTHROPIC_API_KEY", None)
    cmd = ["claude", "-p", TASK, "--output-format", "json", "--model", model,
           "--allowed-tools", *TOOLS]
    if arm == "dense":
        cmd += ["--append-system-prompt", DENSE]
    started = time.time()
    rec = {"run": f"{arm}-{i}", "arm": arm, "dir": str(d)}
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env=env, cwd=str(d))
        data = json.loads(p.stdout)
        u = data.get("usage", {})
        rec.update(out_tok=u.get("output_tokens", 0), num_turns=data.get("num_turns", 0),
                   cost=data.get("total_cost_usd", 0.0), is_error=data.get("is_error", False),
                   session=data.get("session_id", ""))
    except Exception as e:  # noqa: BLE001
        rec.update(out_tok=0, num_turns=0, cost=0.0, is_error=True, error=f"{type(e).__name__}: {e}")
    rec["wall_s"] = round(time.time() - started)
    g = subprocess.run(["node", "gate.js"], capture_output=True, text=True, cwd=str(d))
    rec["gate"] = "PASS" if g.stdout.startswith("COMPLETE") else "fail"
    rec["db_loc"] = len((d / "db.js").read_text().splitlines()) if (d / "db.js").exists() else 0
    suite = d / "tests" / "suite.js"
    rec["suite_loc"] = len(suite.read_text().splitlines()) if suite.exists() else 0
    print(f"  done {rec['run']:9} out={rec['out_tok']:>6} turns={rec['num_turns']:>3} "
          f"wall={rec['wall_s']:>4}s gate={rec['gate']}", file=sys.stderr)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-arm", type=int, default=4)
    ap.add_argument("--model", default="claude-opus-5")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args()

    RUNS.mkdir(exist_ok=True)
    jobs = [(a, i) for a in ("none", "dense") for i in range(1, args.per_arm + 1)]
    print(f"{len(jobs)} runs ({args.per_arm}/arm), model={args.model}", file=sys.stderr)

    with quarantine_user_memory():
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            recs = list(ex.map(lambda j: run_one(j, args.model, args.timeout), jobs))

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = ROOT / "results" / f"t5cli_results_{ts}.json"
    out.write_text(json.dumps({"metadata": {"model": args.model, "per_arm": args.per_arm,
                                            "date": datetime.now(timezone.utc).isoformat(),
                                            "transport": "claude CLI, CLAUDE.md quarantined"},
                               "runs": recs}, indent=2))
    print(f"\nsaved: {out}", file=sys.stderr)
    print(f"{'run':10} {'out_tok':>8} {'turns':>6} {'wall_s':>7} {'db_loc':>7} {'gate':>5}")
    for r in recs:
        print(f"{r['run']:10} {r['out_tok']:8} {r['num_turns']:6} {r['wall_s']:7} "
              f"{r['db_loc']:7} {r['gate']:>5}")


if __name__ == "__main__":
    main()
