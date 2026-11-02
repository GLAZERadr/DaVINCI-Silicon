"""Learn content for students: one model call per requirement, stored in the repo.

For each requirement the model writes a plain-words explanation and one
question about a single output signal at a single cycle of that requirement's
directed test, plus the answer. The Run Console's Learn view shows the
question before the answer and keeps the RTL fix hidden until the answer is
revealed. No model call happens at view time: the view reads these files.

The model sees the requirement, the interface and the golden model's expected
values for the directed test (from the reference trace, measured). It never
sees RTL and is told not to give code. Everything it writes is AI
interpretation · not verified. The generator then checks the model's stated
value against the golden model at the cycle it chose and stores that check,
labelled measured, next to the text.

usage:
  python -m agent.learn --provider meta            # all requirements, live
  python -m agent.learn --provider fake            # offline stand-in, $0
  python -m agent.learn --provider meta --req REQ-06
writes learn/<block>/REQ-xx.json
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from agent import llm

ROOT = llm.ROOT
REQS = ROOT / "spec" / "requirements.json"
INTERFACE = ROOT / "spec" / "interface.json"
REF_TRACE = ROOT / "evidence" / "reference" / "trace" / "trace.json"
OUT = ROOT / "learn"
AI_LABEL = "AI interpretation · not verified"
RANDOM = "test_random_regression"
MAX_OUTPUT_TOKENS = 8000
OUTPUTS = ["dout", "count", "full", "empty", "almost_full", "overflow", "underflow"]


def _obj(props: dict) -> dict:
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}


S = {"type": "string"}
SCHEMA = _obj({
    "explanation": S,                                   # the requirement in plain words
    "question": S,                                      # asks for one signal at one cycle, and why
    "answer": S,                                        # the value and the reason
    "signal": {"type": "string", "enum": OUTPUTS},
    "cycle": {"type": "integer"},
    "expected_value": {"type": "integer"},             # the value the answer gives, for the check
})

PROMPT = """You are writing a short lesson for a student who is learning digital design.
Students often copy code without understanding it. Your job is to make them think, not to hand them a fix.

Requirement {rid} of a synchronous FIFO ({params}):
"{text}"

Ports: {ports}

Below is the directed test for this requirement ({test}), one line per rising clock edge:
inputs as sampled at the edge, then the outputs the golden model expects just after it.
CONTEXT {context}

Write:
- explanation: the requirement in plain words, 2 to 4 sentences, no jargon a first-year student would not know.
- question: ask what ONE output signal should be at ONE cycle of this test, and why. Pick the cycle where the
  requirement matters most (a design that breaks this requirement would show it there). Name the cycle number.
- answer: the value and the reasoning in 2 to 4 sentences, using what happened in the cycles before.
- signal, cycle: the output and cycle number the question asks about.
- expected_value: the value your answer gives, as an integer.

Do not write Verilog or any code. Do not describe how to change a design. Only explain behaviour."""


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def directed_test(req: dict) -> str | None:
    return next((t for t in req["tests"] if t != RANDOM), None)


def context(trace_test: dict) -> dict:
    """Compact, machine-readable view of the golden model over the directed test."""
    return {"test": trace_test["name"],
            "cycles": [{"k": c["k"], "in": c["in"], "exp": c["exp"]} for c in trace_test["cycles"]]}


def messages(req: dict, spec: dict, iface: dict, ctx: dict) -> list:
    ports = ", ".join(f"{p['name']} ({p['dir']})" for p in iface["ports"])
    params = ", ".join(f"{k}={v}" for k, v in spec["params"].items())
    return [{"role": "user", "content": PROMPT.format(rid=req["id"], text=req["text"], params=params, ports=ports,
                                                      test=ctx["test"], context=json.dumps(ctx, separators=(",", ":")))}]


def generate(req: dict, provider: str, spec: dict, iface: dict, ref: dict) -> dict:
    test = directed_test(req)
    tt = next((t for t in ref["tests"] if t["name"] == test), None)
    if tt is None:
        raise SystemExit(f"{req['id']}: no reference trace for {test}; run `make trace-ref` first")
    msgs = messages(req, spec, iface, context(tt))
    opts = {"max_tokens": MAX_OUTPUT_TOKENS,
            "response_format": {"type": "json_schema", "json_schema": {"name": "learn", "strict": True, "schema": SCHEMA}}}
    reply = llm.call(msgs, provider=provider, step="learn", run_id=f"learn-{req['id']}", **opts)
    try:
        content = json.loads(reply.text)
        missing = [k for k in SCHEMA["required"] if k not in content]
        if missing:
            raise ValueError(f"missing {missing}")
    except (json.JSONDecodeError, ValueError) as e:
        raise llm.LLMError(f"learn {req['id']}: unusable reply ({e}): {reply.text[:300]}") from None

    # Measured cross-check: the golden model's value at the cycle the model chose.
    cyc = next((c for c in tt["cycles"] if c["k"] == content["cycle"]), None)
    golden = cyc["exp"].get(content["signal"]) if cyc else None
    check = {"label": "measured · golden model on the reference trace",
             "reference_trace_sha256": ref.get("trace_sha256"),
             "cycle_in_test": cyc is not None,
             "golden_value": golden,
             "answer_matches_golden": golden is not None and golden == content["expected_value"]}
    return {
        "id": req["id"], "block": spec["block"], "requirement": req["text"], "test": test,
        "label": AI_LABEL, "content": content, "check": check,
        "provider": reply.provider, "model": reply.model,
        "tokens_in": reply.tokens_in, "tokens_out": reply.tokens_out, "cost_usd": reply.cost_usd,
        "request_sha256": reply.request_sha256, "response_sha256": reply.response_sha256,
        "requirements_sha256": _sha(REQS.read_bytes()),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", default="meta", choices=llm.PROVIDERS)
    ap.add_argument("--req", action="append", help="only these requirement ids (repeatable)")
    a = ap.parse_args(argv)
    if a.provider == "replay":
        ap.error("replay is for pipeline runs; use meta, baseten or fake")
    spec = json.loads(REQS.read_text())
    iface = json.loads(INTERFACE.read_text())
    ref = json.loads(REF_TRACE.read_text())
    reqs = [r for r in spec["requirements"] if not a.req or r["id"] in a.req]
    out = OUT / spec["block"]
    out.mkdir(parents=True, exist_ok=True)
    total = 0.0
    for r in reqs:
        try:
            rec = generate(r, a.provider, spec, iface, ref)
        except (llm.BudgetError, llm.LLMError) as e:
            print(f"{r['id']}: aborted: {e}", file=sys.stderr)
            return 1
        (out / f"{r['id']}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n")
        total += rec["cost_usd"]
        ck = rec["check"]
        print(f"{r['id']}: {rec['model']} · {rec['content']['signal']} @ cycle {rec['content']['cycle']} · "
              f"golden {ck['golden_value']} · {'matches' if ck['answer_matches_golden'] else 'DOES NOT MATCH'} · ${rec['cost_usd']:.4f}")
    print(f"{len(reqs)} calls, ${total:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
