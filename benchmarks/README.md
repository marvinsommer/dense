# Benchmarks

The current benchmark measures DENSE as static global system context in Claude Code.

| write-up | task shape | DENSE result |
|---|---|---:|
| [`DEEPSWE.md`](DEEPSWE.md) | 20 DeepSWE v1.1 coding tasks, 4 replicates per condition | **−27.6% pure agent time**; **−34.3% input tokens** |

The 14.00 vs 14.50 task-pass result is inside replicate noise. Read the benchmark as evidence
of process-efficiency savings, not as proof of an accuracy change. Its caveats and grading method
are in [`DEEPSWE.md`](DEEPSWE.md).

Earlier benchmark write-ups, runners, raw results, charts, and attribution files are preserved
under [`archive/`](archive/).