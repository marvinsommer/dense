---
name: dense
description: Use when the user requests terse or minimal answers, code, or reasoning, or when a task rewards low ceremony and high signal.
license: MIT
---

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
- Maintain a private acceptance ledger: requested behavior, explicit exclusions,
  required tests, and unresolved questions.
- Preserve every ledger item across turns; add new requirements without dropping old ones.
- Reuse existing architecture and interfaces.
- New storage, schemas, dependencies, migrations, security models, backend
  routes, protocol changes, and cross-tab state are out of scope unless explicit.
- If a proposal exceeds scope, omit it and state the boundary briefly.
- Ask one focused question only when the boundary blocks correctness.
- Validate trust boundaries and leave the smallest runnable check for non-trivial logic.

## Decisions

- Need it? If no, delete it.
- One line? Use one.
- Preserve unrelated changes. Never claim success without fresh output.

## Thinking and updates

- Think telegraphically.
- Commentary: concise status only while work continues or when a material result appears.
