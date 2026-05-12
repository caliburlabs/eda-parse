# First real authority-tier runs

This folder preserves the first real frontier-model passes over the sealed
authority tasks in `benchmarks/timing_diagnosis/`.

Run batch:

- Date: 2026-05-12
- Model: Claude Opus 4.7 with high effort
- Scope: `authority_001`, `authority_002`, `authority_003`
- Final patched-grader result: all three answers grade PASS at 100%
- Approximate API spend reported during the run review: about `$3.50` total

Each task folder keeps:

- `answer.json` — the structured final answer emitted by the model
- `transcript.jsonl` — the tool-call / tool-result trace from the real run
- `runner.log` — retained only where the wrapper log carried useful retry
  behavior (`authority_001`)

Intentionally omitted:

- `stdout.txt`, because it duplicated `answer.json`
- empty `stderr.txt`
- temporary false-positive probe files created during grader calibration

These artifacts are evidence, not benchmark inputs. They document how the
subject agent behaved on the frozen tasks and should not be used by agents
while taking the benchmark.
