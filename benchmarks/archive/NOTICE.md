# Third-party attribution

## caveman

The following files originate from [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman),
licensed **MIT**, and are redistributed here so the comparison is reproducible and auditable:

| file here | upstream path | modified |
|---|---|---|
| `chat/prompts.json` | `benchmarks/prompts.json` | no |
| `chat/run_upstream.py` | `benchmarks/run.py` | no (renamed only) |
| `chat/skills/caveman.md` | `skills/caveman/SKILL.md` | no |

`chat/run_cli.py` is a derivative work of upstream `benchmarks/run.py`, rewritten to drive the
Claude Code CLI instead of the Anthropic API, to support N arms instead of 2, and to isolate
the control arm. The prompt set and the median-output-token statistic are unchanged, so the
numbers remain comparable to upstream's.

Retrieved 2026-07-26.

The MIT License requires that its copyright notice and permission notice be included with any
copy or substantial portion of the software. Upstream's licence is therefore reproduced
verbatim at [`chat/LICENSE.caveman`](chat/LICENSE.caveman):

> MIT License
>
> Copyright (c) 2026 Julius Brussee

That file covers `chat/prompts.json`, `chat/run_upstream.py`, `chat/skills/caveman.md` and the
derived `chat/run_cli.py`. The repository's own [`LICENSE`](../../LICENSE) (Copyright (c) 2026
Marvin Sommer) covers everything else.

If the caveman authors would prefer these files be fetched at runtime rather than vendored,
`chat/run_cli.py` can be changed to download them and the copies removed.

## DENSE

`chat/skills/dense.md` is a copy of this repository's own `SYSTEM.md`, duplicated so the
benchmark runner is self-contained. If the two drift, `../../SYSTEM.md` is authoritative.
