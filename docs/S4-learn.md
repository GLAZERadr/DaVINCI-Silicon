# S4 Learn view for students

Run Console → **Learn mode** toggle (top of the left column). For a failing directed test it shows:

1. the requirement verbatim (frozen spec) and in plain words (AI interpretation · not verified),
2. the measured waveform of this attempt, opened at the first mismatch,
3. a question about one output at one cycle; the answer appears only on "Show the answer".

While the answer is hidden, the Diff / RTL / Prompt tabs, the AI diagnosis and the seeded-bug description are locked for that attempt.

Content: `learn/<block>/REQ-xx.json`, one model call per requirement by `agent/learn.py` (strict JSON schema; the model sees the requirement, the ports and the golden model's values for the directed test from `evidence/reference/trace/trace.json`, never RTL). Each file stores model, cost, request hash and the label. The generator also stores a measured check: the golden model's value at the cycle the question names, and whether the answer's value agrees. No model call at view time.

The committed files were made with `--provider fake` (text starts "(fake provider)"). Regenerate live:

```bash
python -m agent.learn --provider meta          # 10 calls, one per REQ
```
