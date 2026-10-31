"""Spec image/PDF → requirements, for human approval.

Two model calls, both ledgered and both AI interpretation, never measured:
  extract  the model sees only the page images (not spec/requirements.json)
           and lists what the pages state, with where it read each item.
  map      a text-only call pairs each extracted item with the closest
           reference requirement, so approved items inherit that REQ's
           frozen tests; items with no match are shown as untested.

A human then approves (and may edit) the list. Only approved.json reaches the
RTL step, together with the interface-only part of spec/fifo_spec.md, so the
generated RTL really depends on what was extracted.

usage:
  python -m agent.extract spec/fixtures/sf16_datasheet.pdf [--provider meta]
  python -m agent.extract --approve <xid> --by "Name" [--edited list.json]
  python -m agent.pipeline --run-id x1 --requirements runs/_extract/<xid>/approved.json \\
      --spec runs/_extract/<xid>/interface_spec.md
"""
import argparse
import base64
import hashlib
import io
import json
import re
import secrets
import sys
import time
from pathlib import Path

from agent import llm

ROOT, RUNS = llm.ROOT, llm.RUNS
EXTRACT_DIR = RUNS / "_extract"
REFERENCE = ROOT / "spec" / "requirements.json"
SPEC = ROOT / "spec" / "fifo_spec.md"
AI_LABEL = "AI interpretation · not verified"
MAX_PAGES = 8
IMAGE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".webp": "image/webp", ".gif": "image/gif"}
XID = re.compile(r"^x-[0-9]{8}-[0-9]{6}-[0-9a-f]{4}$")


def _obj(props: dict) -> dict:
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}


S = {"type": "string"}
EXTRACT_SCHEMA = _obj({
    "block": S,
    "params": {"type": "array", "items": _obj({"name": S, "value": S, "source_location": S})},
    "ports": {"type": "array", "items": _obj({"name": S, "direction": {"type": "string", "enum": ["in", "out"]},
                                               "width": S, "description": S})},
    "requirements": {"type": "array", "items": _obj({
        "id": S, "text": S, "source_location": S,
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]}})},
    "unreadable": {"type": "array", "items": S},
})
MAP_SCHEMA = _obj({"mapping": {"type": "array", "items": _obj({
    "id": S, "maps_to": {"anyOf": [S, {"type": "null"}]}, "reason": S})}})

EXTRACT_PROMPT = """These pages describe a digital hardware block. Extract what they state.

- requirements: every behavioural rule the pages state, one testable statement each, ids EX-01, EX-02, ...
  Say only what the pages say. Do not add rules from general knowledge of such blocks.
  source_location names where you read it (e.g. "page 1, table 3.3, row 4" or "page 2, figure 4.1").
  confidence is low when the text is hard to read or you are inferring from a diagram.
- params and ports: as stated on the pages.
- unreadable: anything you could not read or that looks contradictory."""

MAP_PROMPT = """Pair each extracted requirement with the reference requirement it states, if any.
maps_to is the reference id, or null if no reference requirement says the same thing.
Several extracted items may map to one reference id. Give a one-line reason."""


def pages(path: Path) -> list[bytes]:
    """Page images as PNG bytes. PDFs are rendered locally (the chat endpoint
    takes images, not PDFs), at most MAX_PAGES pages."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(str(path))
        out = []
        for i in range(min(len(doc), MAX_PAGES)):
            buf = io.BytesIO()
            doc[i].render(scale=150 / 72).to_pil().save(buf, format="PNG")
            out.append(buf.getvalue())
        return out
    if suffix in IMAGE_MIME:
        from PIL import Image
        buf = io.BytesIO()
        Image.open(path).convert("RGB").save(buf, format="PNG")
        return [buf.getvalue()]
    raise ValueError(f"unsupported file type {suffix}; use PDF, PNG, JPEG, WebP or GIF")


def interface_spec() -> str:
    """The parts of fifo_spec.md the frozen testbench fixes (parameters, ports,
    RTL constraints), without the behavioural rules."""
    text = SPEC.read_text()
    keep = []
    for sec in re.split(r"(?m)^(?=## )", text):
        if sec.startswith(("## Parameters", "## Interface", "## Constraints")):
            keep.append(sec.strip().replace("as long as the timing below holds",
                                            "as long as the approved behaviour holds"))
    return ("# sync_fifo — interface\n\nPort names, widths and parameters are fixed by the test bench. "
            "Behaviour is given by the approved requirements.\n\n" + "\n\n".join(keep) + "\n")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _json_reply(reply: "llm.Reply", what: str) -> dict:
    text = reply.text.strip()
    m = re.search(r"\{.*\}", text, flags=re.S)
    try:
        return json.loads(m.group(0) if m else text)
    except (json.JSONDecodeError, AttributeError):
        raise llm.LLMError(f"{what}: model did not return JSON: {text[:300]}") from None


def new_xid() -> str:
    return f"x-{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"


def extract(path: Path, provider: str = "meta", xid: str | None = None) -> dict:
    xid = xid or new_xid()
    d = EXTRACT_DIR / xid
    (d / "pages").mkdir(parents=True)
    raw = path.read_bytes()
    (d / f"source{path.suffix.lower()}").write_bytes(raw)
    imgs = pages(path)
    for i, png in enumerate(imgs, 1):
        (d / "pages" / f"page_{i}.png").write_bytes(png)
    rec = {"extraction_id": xid, "label": AI_LABEL, "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "source": {"name": path.name, "sha256": _sha(raw), "pages": len(imgs),
                      "page_sha256": [_sha(p) for p in imgs]},
           "provider": provider, "calls": [], "status": "running"}

    def save():
        (d / "extracted.json").write_text(json.dumps(rec, indent=2))

    def call(step, messages, schema):
        opts = {"max_tokens": 8000,
                "response_format": {"type": "json_schema", "json_schema": {"name": step, "strict": True,
                                                                           "schema": schema}}}
        try:
            reply = llm.call(messages, provider=provider, step=step, run_id=xid, **opts)
        except (llm.BudgetError, llm.LLMError) as e:
            rec["calls"].append({"step": step, "ok": False, "error": str(e)[:500]})
            rec.update(status="aborted", error=f"{step}: {e}")
            save()
            raise
        (d / f"{step}_response.md").write_text(reply.text)
        rec["calls"].append({"step": step, "ok": True, **llm.reply_dict(reply)})
        return reply

    content = [{"type": "text", "text": EXTRACT_PROMPT}] + [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(p).decode()}}
        for p in imgs]
    # The prompt file keeps hashes instead of the base64 page data.
    (d / "extract_prompt.json").write_text(json.dumps(
        [{"type": "text", "text": EXTRACT_PROMPT}] + [{"type": "image", "page": i, "sha256": _sha(p)}
                                                       for i, p in enumerate(imgs, 1)], indent=1))
    try:
        got = _json_reply(call("extract", [{"role": "user", "content": content}], EXTRACT_SCHEMA), "extract")
        rec["extracted"] = got
        ref = json.loads(REFERENCE.read_text())["requirements"]
        mmsg = [{"role": "user", "content": f"{MAP_PROMPT}\n\n## Extracted\n\n```json\n"
                 f"{json.dumps([{k: r[k] for k in ('id', 'text')} for r in got['requirements']], indent=1)}\n```\n\n"
                 f"## Reference\n\n```json\n{json.dumps([{k: r[k] for k in ('id', 'text')} for r in ref], indent=1)}\n```"}]
        rec["mapping"] = _json_reply(call("map", mmsg, MAP_SCHEMA), "map")["mapping"]
    except (llm.BudgetError, llm.LLMError):
        return rec
    rec["comparison"] = compare(rec)
    rec["status"] = "awaiting_approval"
    rec["cost_usd"] = round(sum(c.get("cost_usd", 0) for c in rec["calls"]), 6)
    save()
    return rec


def compare(rec: dict) -> dict:
    """Side by side with spec/requirements.json, from the model's mapping
    (so this table is AI interpretation too)."""
    ref = json.loads(REFERENCE.read_text())["requirements"]
    maps = {m["id"]: m.get("maps_to") for m in rec.get("mapping", [])}
    rows = []
    for r in ref:
        hits = [e["id"] for e in rec["extracted"]["requirements"] if maps.get(e["id"]) == r["id"]]
        rows.append({"reference": r["id"], "reference_text": r["text"], "extracted": hits, "covered": bool(hits)})
    unmapped = [e["id"] for e in rec["extracted"]["requirements"] if not maps.get(e["id"])]
    return {"label": AI_LABEL, "reference_covered": sum(x["covered"] for x in rows), "reference_total": len(rows),
            "rows": rows, "extracted_without_reference": unmapped}


def load(xid: str) -> dict:
    if not XID.match(xid):
        raise ValueError("bad extraction id")
    f = EXTRACT_DIR / xid / "extracted.json"
    if not f.exists():
        raise FileNotFoundError(xid)
    rec = json.loads(f.read_text())
    a = EXTRACT_DIR / xid / "approved.json"
    if a.exists():
        rec["approved"] = json.loads(a.read_text())
        rec["approved_sha256"] = _sha(a.read_bytes())
    return rec


def approve(xid: str, approved_by: str, requirements: list | None = None) -> dict:
    """Human approval. `requirements` is the (possibly edited) list of
    {id, text[, maps_to]}; None approves the extracted list as is."""
    rec = load(xid)
    if rec["status"] != "awaiting_approval" or "approved" in rec:
        raise ValueError(f"extraction {xid} is {('already approved' if 'approved' in rec else rec['status'])}")
    if not approved_by.strip():
        raise ValueError("approved_by is required")
    maps = {m["id"]: m.get("maps_to") for m in rec.get("mapping", [])}
    items = requirements if requirements is not None else rec["extracted"]["requirements"]
    if not items:
        raise ValueError("nothing to approve")
    ref = {r["id"]: r for r in json.loads(REFERENCE.read_text())["requirements"]}
    reqs, ids = [], set()
    for it in items:
        if not str(it.get("id", "")).strip() or not str(it.get("text", "")).strip() or it["id"] in ids:
            raise ValueError(f"each requirement needs a unique id and text: {it}")
        ids.add(it["id"])
        maps_to = it.get("maps_to", maps.get(it["id"]))
        reqs.append({"id": it["id"], "text": it["text"], "maps_to": maps_to,
                     "tests": ref[maps_to]["tests"] if maps_to in ref else [],
                     "edited": requirements is not None and next(
                         (e["text"] != it["text"] for e in rec["extracted"]["requirements"] if e["id"] == it["id"]),
                         True)})
    approved = {
        "block": "sync_fifo",
        "params": json.loads(REFERENCE.read_text())["params"],
        "requirements": reqs,
        "extraction_id": xid,
        "source": rec["source"],
        "approved_by": approved_by.strip(),
        "approved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "untested": [r["id"] for r in reqs if not r["tests"]],
    }
    d = EXTRACT_DIR / xid
    (d / "approved.json").write_text(json.dumps(approved, indent=2))
    (d / "interface_spec.md").write_text(interface_spec())
    return load(xid)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", type=Path)
    ap.add_argument("--provider", default="meta", choices=[p for p in llm.PROVIDERS if p != "replay"])
    ap.add_argument("--xid", help="extraction id to use (default: generated)")
    ap.add_argument("--approve", metavar="XID")
    ap.add_argument("--by", help="who approves (required with --approve)")
    ap.add_argument("--edited", type=Path, help="JSON list of {id, text[, maps_to]} to approve instead")
    a = ap.parse_args(argv)
    if a.approve:
        edited = json.loads(a.edited.read_text()) if a.edited else None
        rec = approve(a.approve, a.by or "", edited)
        print(json.dumps({k: rec["approved"][k] for k in ("extraction_id", "approved_by", "untested")}
                         | {"approved_sha256": rec["approved_sha256"],
                            "requirements": EXTRACT_DIR / a.approve / "approved.json",
                            "spec": EXTRACT_DIR / a.approve / "interface_spec.md"}, indent=2, default=str))
        return 0
    if not a.file:
        ap.error("give a file to extract, or --approve XID")
    if a.xid and not XID.match(a.xid):
        ap.error("bad --xid")
    rec = extract(a.file, a.provider, a.xid)
    print(json.dumps({k: rec.get(k) for k in ("extraction_id", "status", "error", "cost_usd")}, indent=2))
    if rec["status"] == "awaiting_approval":
        for e in rec["extracted"]["requirements"]:
            m = next((x["maps_to"] for x in rec["mapping"] if x["id"] == e["id"]), None)
            print(f'  {e["id"]:6} → {m or "—":7} [{e["confidence"]}] {e["text"]}  ({e["source_location"]})')
        c = rec["comparison"]
        print(f'reference covered: {c["reference_covered"]}/{c["reference_total"]} ({AI_LABEL})')
    return 0 if rec["status"] == "awaiting_approval" else 1


if __name__ == "__main__":
    sys.exit(main())
