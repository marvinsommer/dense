<p align="center">
  <img src="img/dense-icon.svg" alt="DENSE" width="128">
</p>

# DENSE

A compact system prompt that makes a coding model write less — less prose, less code, less
ceremony — while preserving correctness and required validation. [`SYSTEM.md`](SYSTEM.md) is
the canonical prompt (MIT).

## Current result

The latest benchmark applies DENSE as global system context to Claude Code on 20 DeepSWE v1.1
tasks, with four replicates per condition and hidden grading.

| measure | baseline | DENSE | change |
|---|---:|---:|---:|
| pass rate (tasks / 20) | 16.25 | 15.75 | −0.5 tasks |
| pure agent time / task | 27.81 min | 20.13 min | **−27.6%** |
| input tokens / task | 11.93M | 7.77M | **−34.9%** |
| output tokens / task | 82.2k | 60.4k | **−26.5%** |
| rounds / task | 91.8 | 71.4 | **−22.2%** |
| estimated price / task | $9.79 | $6.73 | **−31.3%** |

The efficiency reductions are consistent across replicates. The pass difference is within run
noise, so this benchmark supports a process-efficiency result, not an accuracy claim.

See the full [DeepSWE methodology and results](benchmarks/DEEPSWE.md). Superseded benchmark
write-ups and their raw runners/data are preserved in the [archive](benchmarks/archive/).

## Quickstart

| CLI                                  | Strongest `SYSTEM.md` method                              |            Preserves built-in prompt? | Weaker file fallback                      |
| ------------------------------------ | --------------------------------------------------------- | ------------------------------------: | ----------------------------------------- |
| **Claude Code**                      | `claude --append-system-prompt-file SYSTEM.md`            |                                   Yes | Copy to `CLAUDE.md`                       |
| **Claude Code — replacement**        | `claude --system-prompt-file SYSTEM.md`                   |                                    No | Copy to `CLAUDE.md`                       |
| **GitHub Copilot CLI**               | **[HACKY WORKAROUND]** Use the Copilot SDK with `systemMessage`                  |                  Yes with append mode | **[RECOMMENDED]** Copy to `.github/copilot-instructions.md` |
| **GitHub Copilot CLI — replacement** | **[HACKY WORKAROUND]** Copilot SDK with `systemMessage.mode = "replace"`         |                                    No | **[RECOMMENDED]** Copy to `.github/copilot-instructions.md` |
| **OpenAI Codex CLI**                 | Load the contents into `developer_instructions`           |                                   Yes | Copy to `AGENTS.md`                       |
| **OpenAI Codex CLI — replacement**   | `codex -c 'model_instructions_file="/path/to/SYSTEM.md"'` |                                    No | Copy to `AGENTS.md`                       |
| **OpenCode — recommended**           | Add `"instructions": ["SYSTEM.md"]` to `opencode.json`    |                                   Yes | Copy to `AGENTS.md`                       |
| **OpenCode — replacement**           | Set the primary agent’s `"prompt": "{file:./SYSTEM.md}"`  | No—replaces that agent’s stock prompt | Copy to `AGENTS.md`                       |

## License

MIT. See [LICENSE](LICENSE).
