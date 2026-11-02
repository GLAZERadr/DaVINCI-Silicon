"""Design breakdown before RTL (spec → microarchitecture), stretch item S1.

Between the approved requirements and the RTL step, the model proposes a
structured breakdown: the state it will hold (registers, counters, pointers,
memory) with widths, the pointer/counter scheme, FSM states if any, the
control vs datapath split, interface timing assumptions, and which REQ each
element serves. It is AI interpretation until a person approves it; the
approved breakdown is then passed into the RTL prompt (`agent.pipeline
--breakdown <bid>`). After the run, `check()` measures which elements appear in
the final RTL with the declared width, and which REQs have no element.

usage: python -m agent.breakdown --create [--requirements F] [--spec F] [--provider meta|fake]
       python -m agent.breakdown --approve <bid> --by "Name"
       python -m agent.breakdown --check runs/<id>          # writes breakdown_check.json into the run
"""
import argparse
import hashlib
import json
import re
import secrets
import time
from pathlib import Path

from agent import llm

ROOT, RUNS = llm.ROOT, llm.RUNS
BREAKDOWN_DIR = RUNS / "_breakdown"
AI_LABEL = "AI interpretation · not verified"
BID = re.compile(r"^b-[0-9]{8}-[0-9]{6}-[0-9a-f]{4}$")
MAX_OUTPUT_TOKENS = 24000
PARAMS = json.loads((ROOT / "spec" / "interface.json").read_text())["params"]


def _obj(props: dict) -> dict:
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}


S = {"type": "string"}
SL = {"type": "array", "items": S}
SCHEMA = _obj({
    "block": S,
    "summary": S,
    "elements": {"type": "array", "items": _obj({
        "name": S,
        "kind": {"type": "string", "enum": ["register", "counter", "pointer", "memory", "flag", "wire", "fsm_state"]},
        "width": S,
        "role": S,
        "reqs": SL})},
    "pointer_scheme": S,
    "fsm_states": {"type": "array", "items": _obj({"name": S, "meaning": S})},
    "control": SL,
    "datapath": SL,
    "timing_assumptions": SL,
})

SYSTEM = """You are a careful RTL architect. Before any RTL is written, you break a design down into the
state it must hold and the logic around it, so an engineer can review the plan first.
Answer only with the JSON object the schema asks for."""


def messages(spec: str, reqs: str) -> list:
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content":
                f"## Specification\n\n{spec}\n\n## Approved requirements\n\n```json\n{reqs}\n```\n\n"
                "Give the microarchitecture breakdown for this block:\n"
                "- elements: every register, counter, pointer, memory array, flag and important internal wire, "
                "with the exact signal name you would use in the RTL (ports keep their spec names), the width as a "
                "Verilog expression in the spec's parameters (e.g. `CW`, `WIDTH`, `1`), its role, and the REQ ids it serves;\n"
                "- pointer_scheme: how read/write pointers and the count advance and wrap;\n"
                "- fsm_states: the FSM states if the design needs one (empty list if not);\n"
                "- control and datapath: which logic is control and which is datapath;\n"
                "- timing_assumptions: when inputs are sampled and outputs change relative to the clock and reset."}]


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _json_reply(reply: "llm.Reply") -> dict:
    if reply.extra.get("finish_reason") == "length":
        raise llm.LLMError("breakdown: reply cut off at the output token limit")
    m = re.search(r"\{.*\}", reply.text, flags=re.S)
    try:
        return json.loads(m.group(0) if m else reply.text)
    except (json.JSONDecodeError, AttributeError):
        raise llm.LLMError(f"breakdown: model did not return JSON: {reply.text[:300]}") from None


def new_bid() -> str:
    return f"b-{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"


def create(spec_path: Path, req_path: Path, provider: str = "meta", bid: str | None = None) -> dict:
    bid = bid or new_bid()
    d = BREAKDOWN_DIR / bid
    d.mkdir(parents=True)
    spec, reqs = spec_path.read_text(), req_path.read_text()
    rec = {"breakdown_id": bid, "label": AI_LABEL, "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "provider": provider, "spec_file": _rel(spec_path), "spec_sha256": _sha(spec.encode()),
           "requirements_file": _rel(req_path), "requirements_sha256": _sha(reqs.encode()), "status": "running"}
    msgs = messages(spec, reqs)
    (d / "prompt.json").write_text(json.dumps(msgs, indent=1))
    opts = {"max_tokens": MAX_OUTPUT_TOKENS,
            "response_format": {"type": "json_schema", "json_schema": {"name": "breakdown", "strict": True, "schema": SCHEMA}}}
    try:
        reply = llm.call(msgs, provider=provider, step="breakdown", run_id=bid, **opts)
        (d / "response.md").write_text(reply.text)
        rec["call"] = llm.reply_dict(reply)
        rec["cost_usd"] = reply.cost_usd
        rec["breakdown"] = _json_reply(reply)
        rec["status"] = "awaiting_approval"
    except (llm.BudgetError, llm.LLMError) as e:
        rec.update(status="aborted", error=str(e)[:500])
    (d / "breakdown.json").write_text(json.dumps(rec, indent=2))
    return rec


def _rel(p: Path) -> str:
    p = p.resolve()
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else str(p)


def load(bid: str) -> dict:
    if not BID.match(bid):
        raise ValueError("bad breakdown id")
    f = BREAKDOWN_DIR / bid / "breakdown.json"
    if not f.exists():
        raise FileNotFoundError(bid)
    rec = json.loads(f.read_text())
    a = BREAKDOWN_DIR / bid / "approved.json"
    if a.exists():
        rec["approved"] = json.loads(a.read_text())
        rec["approved_sha256"] = _sha(a.read_bytes())
    rec["approvals"] = history(bid)
    return rec


def approval_kind(a: dict) -> str:
    """human or integration_test. Approvals written before "kind" existed are
    read from their wording (the integration tests said so in approved_by)."""
    if a.get("kind"):
        return a["kind"]
    return "integration_test" if re.search(r"integration test|not a human review", a.get("approved_by", ""), re.I) \
        else "human"


def content_sha(breakdown: dict) -> str:
    """Hash of the breakdown content itself, so a later approval can be matched to the one a run used."""
    return _sha(json.dumps(breakdown, sort_keys=True).encode())


def history(bid: str) -> list:
    """Every approval of this breakdown, oldest first (approvals.jsonl, append-only).
    A breakdown approved before the history existed has its approved.json as the only entry."""
    d = BREAKDOWN_DIR / bid
    f = d / "approvals.jsonl"
    if f.exists():
        return [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    a = d / "approved.json"
    if not a.exists():
        return []
    rec = json.loads(a.read_text())
    return [{**rec, "kind": approval_kind(rec), "approved_sha256": _sha(a.read_bytes()),
             "content_sha256": content_sha(rec["breakdown"])}]


def approve(bid: str, approved_by: str, kind: str = "human") -> dict:
    """Approval of the proposed breakdown, as is. A human may approve a breakdown
    whose current approval was only an integration test; the earlier approval
    stays in approvals.jsonl and runs that used it keep their own copy."""
    if kind not in ("human", "integration_test"):
        raise ValueError("kind must be human or integration_test")
    rec = load(bid)
    current = rec.get("approved")
    if current and not (approval_kind(current) == "integration_test" and kind == "human"):
        raise ValueError(f"breakdown {bid} is already approved by {current['approved_by']}")
    if rec["status"] != "awaiting_approval":
        raise ValueError(f"breakdown {bid} is {rec['status']}")
    if not approved_by.strip():
        raise ValueError("approved_by is required")
    if kind == "human" and re.search(r"\bclaude\b|integration test|not a human review", approved_by, re.I):
        raise ValueError("a human approval needs the name of the person approving")
    d = BREAKDOWN_DIR / bid
    past = history(bid)
    approved = {"breakdown_id": bid, "approved_by": approved_by.strip(), "kind": kind,
                "approved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "spec_sha256": rec["spec_sha256"], "requirements_sha256": rec["requirements_sha256"],
                "breakdown": rec["breakdown"]}
    if current:
        approved["supersedes"] = {"approved_by": current["approved_by"], "approved_at": current["approved_at"],
                                  "kind": approval_kind(current), "approved_sha256": rec["approved_sha256"]}
    text = json.dumps(approved, indent=2)
    entry = {**approved, "approved_sha256": _sha(text.encode()), "content_sha256": content_sha(rec["breakdown"])}
    # Write the history first: the earlier approval must be on record before approved.json changes.
    with (d / "approvals.jsonl").open("w") as f:
        for row in past + [entry]:
            f.write(json.dumps(row) + "\n")
    (d / "approved.json").write_text(text)
    return load(bid)


def later_reviews(run_dir: Path) -> list:
    """Human approvals of the breakdown a run used, made after the run started with
    the same breakdown content. They do not change what the run was given."""
    run = json.loads((run_dir / "run.json").read_text())
    used = run.get("breakdown") or {}
    copy = run_dir / "breakdown.json"
    if not used.get("breakdown_id") or not copy.exists() or not BID.match(used["breakdown_id"]):
        return []
    same = content_sha(json.loads(copy.read_text())["breakdown"])
    return [{k: h.get(k) for k in ("approved_by", "approved_at", "kind", "approved_sha256", "content_sha256")}
            for h in history(used["breakdown_id"])
            if approval_kind(h) == "human" and h.get("approved_sha256") != used.get("approved_sha256")
            and h.get("content_sha256") == same and h.get("approved_at", "") > run.get("started", "")]


def prompt_section(approved: dict) -> str:
    return ("## Approved design breakdown\n\nA person approved this breakdown before RTL. Follow it: use these "
            "signal names and widths unless a requirement makes that impossible.\n\n"
            f"```json\n{json.dumps(approved['breakdown'], indent=1)}\n```")


# ---- measured check: does the final RTL follow the breakdown? ---------------------------------------------

DECL = re.compile(r"\b(?:input|output|inout|reg|wire|integer|localparam|parameter)\b(?:\s+(?:wire|reg|signed))*\s*"
                  r"(\[[^\]]+\])?\s*([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)")


def _eval(expr: str, params: dict) -> int | None:
    """Evaluate a small width expression like `CW`, `WIDTH-1`, `$clog2(DEPTH+1)` with the RTL's parameters."""
    e = expr.strip()
    e = re.sub(r"\$clog2\(([^()]+)\)", lambda m: str(max(1, (int(_eval(m.group(1), params) or 1) - 1).bit_length())), e)
    for k, v in sorted(params.items(), key=lambda kv: -len(kv[0])):
        e = re.sub(rf"\b{k}\b", str(v), e)
    if not re.fullmatch(r"[\d\s+\-*/()]+", e):
        return None
    try:
        return int(eval(e, {"__builtins__": {}}, {}))  # digits and + - * / ( ) only, checked above
    except Exception:
        return None


def rtl_params(rtl: str) -> dict:
    found = dict(PARAMS)
    for name, val in re.findall(r"\bparameter\s+(?:integer\s+)?(\w+)\s*=\s*([^,;)\n/]+)", rtl):
        n = _eval(val, found)
        if n is not None:
            found[name] = n
    return found


def declarations(rtl: str) -> dict:
    """name → declared width (int) or None when the range is not a plain [hi:lo]."""
    code = re.sub(r"//.*", "", rtl)
    params = rtl_params(rtl)
    out = {}
    for rng, names in DECL.findall(code):
        width = 1
        if rng:
            m = re.fullmatch(r"\[\s*(.+?)\s*:\s*(.+?)\s*\]", rng)
            hi, lo = (_eval(m.group(1), params), _eval(m.group(2), params)) if m else (None, None)
            width = hi - lo + 1 if hi is not None and lo is not None else None
        for n in re.split(r"\s*,\s*", names):
            out.setdefault(n, width)
    return out


def check(approved: dict, rtl: str, req_ids: list[str]) -> dict:
    params = rtl_params(rtl)
    decl = declarations(rtl)
    rows = []
    for el in approved["breakdown"]["elements"]:
        name = el["name"]
        present = name in decl or bool(re.search(rf"\b{re.escape(name)}\b", re.sub(r"//.*", "", rtl)))
        want = _eval(el["width"], params)
        got = decl.get(name)
        width = ("not checked" if not present or want is None or got is None or el["kind"] in ("fsm_state",)
                 else "match" if want == got else "differs")
        rows.append({"name": name, "kind": el["kind"], "width_planned": el["width"], "width_planned_bits": want,
                     "declared": name in decl, "present": present, "width_declared_bits": got, "width": width,
                     "reqs": el["reqs"]})
    served = {r for el in approved["breakdown"]["elements"] for r in el["reqs"]}
    return {"label": "measured", "breakdown_id": approved["breakdown_id"], "rtl_sha256": _sha(rtl.encode()),
            "params": params, "elements": rows,
            "present": sum(r["present"] for r in rows), "total": len(rows),
            "width_match": sum(r["width"] == "match" for r in rows),
            "width_differs": [r["name"] for r in rows if r["width"] == "differs"],
            "missing": [r["name"] for r in rows if not r["present"]],
            "reqs_without_element": [r for r in req_ids if r not in served]}


def check_run(run_dir: Path) -> dict | None:
    """Check a finished run that used a breakdown against its last simulated RTL."""
    run = json.loads((run_dir / "run.json").read_text())
    if not run.get("breakdown") or not (run_dir / "breakdown.json").exists():
        return None
    approved = json.loads((run_dir / "breakdown.json").read_text())
    sim = [a for a in run["attempts"] if (a.get("measured") or {}).get("status") in ("pass", "fail")]
    if not sim:
        return None
    rtl = (run_dir / f"attempt_{sim[-1]['n']}" / "sync_fifo.v").read_text()
    reqs = json.loads((ROOT / run["requirements_file"]).read_text() if not Path(run["requirements_file"]).is_absolute()
                      else Path(run["requirements_file"]).read_text())
    out = check(approved, rtl, [r["id"] for r in reqs["requirements"]]) | {"attempt": sim[-1]["n"]}
    (run_dir / "breakdown_check.json").write_text(json.dumps(out, indent=2))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--create", action="store_true")
    ap.add_argument("--spec", type=Path, default=ROOT / "spec" / "fifo_spec.md")
    ap.add_argument("--requirements", type=Path, default=ROOT / "spec" / "requirements.json")
    ap.add_argument("--provider", default="meta", choices=llm.PROVIDERS)
    ap.add_argument("--bid", help="use this breakdown id (API)")
    ap.add_argument("--approve", metavar="BID")
    ap.add_argument("--by", default="", help="name of the person approving")
    ap.add_argument("--integration-test", action="store_true",
                    help="record the approval as an integration test, not a human review")
    ap.add_argument("--check", type=Path, metavar="RUN_DIR")
    a = ap.parse_args(argv)
    if a.create:
        rec = create(a.spec, a.requirements, a.provider, a.bid)
        b = rec.get("breakdown") or {}
        print(f"{rec['breakdown_id']}: {rec['status']} · {len(b.get('elements', []))} elements · ${rec.get('cost_usd') or 0:.4f}")
        return 0 if rec["status"] == "awaiting_approval" else 1
    if a.approve:
        rec = approve(a.approve, a.by, "integration_test" if a.integration_test else "human")
        ap_ = rec["approved"]
        print(f"{a.approve}: approved by {ap_['approved_by']} ({ap_['kind']})"
              + (f"; replaces {ap_['supersedes']['approved_by']} ({ap_['supersedes']['kind']})" if ap_.get("supersedes") else ""))
        return 0
    if a.check:
        out = check_run(a.check)
        print(json.dumps({k: out[k] for k in ("present", "total", "width_match", "width_differs", "missing",
                                              "reqs_without_element")} if out else "run used no breakdown"))
        return 0
    ap.error("give --create, --approve or --check")


if __name__ == "__main__":
    raise SystemExit(main())
