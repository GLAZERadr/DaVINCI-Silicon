"""Model client for DaVINCI: one call() for every provider, with a cost ledger,
a hard budget guard and a response cache used for replay.

Providers
  meta     Meta Model API, muse-spark-1.3 (OpenAI-compatible)
  baseten  Muse Spark Open on Baseten (OpenAI-compatible)
  replay   returns the responses recorded by an earlier run, in order; $0
  fake     deterministic offline stand-in for development; $0

Every call, including failed and refused ones, is appended to
runs/_ledger.jsonl. Live calls are refused when the price for the provider is
not set or when spend would pass DAVINCI_BUDGET_USD.
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
LEDGER = RUNS / "_ledger.jsonl"
CACHE = RUNS / "_cache"

LIVE = {
    "meta": {
        "base": "https://api.meta.ai/v1",
        "model": "muse-spark-1.3",
        "key": "META_API_KEY",
        "price": ("PRICE_IN_META", "PRICE_OUT_META"),
        "max_tokens_field": "max_completion_tokens",
    },
    "baseten": {
        "base": "https://inference.baseten.co/v1",
        "model": "meta-models/muse-spark-open-1026",
        "key": "BASETEN_API_KEY",
        "price": ("PRICE_IN_BASETEN", "PRICE_OUT_BASETEN"),
        "max_tokens_field": "max_tokens",
    },
}
PROVIDERS = [*LIVE, "replay", "fake"]


class BudgetError(RuntimeError):
    pass


class LLMError(RuntimeError):
    pass


@dataclass
class Reply:
    text: str
    provider: str
    model: str
    request_sha256: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    seconds: float = 0.0
    extra: dict = field(default_factory=dict)


def load_env(path: Path = ROOT / ".env"):
    """Minimal .env reader; real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env(ROOT / ".env.local")
load_env()


def request_hash(messages: list, opts: dict) -> str:
    body = json.dumps({"messages": messages, "opts": opts}, sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()


def prices(provider: str):
    """USD per 1M tokens (in, out), or None if not configured."""
    k_in, k_out = LIVE[provider]["price"]
    try:
        return float(os.environ[k_in]), float(os.environ[k_out])
    except (KeyError, ValueError):
        return None


def spent_usd() -> float:
    if not LEDGER.exists():
        return 0.0
    total = 0.0
    for line in LEDGER.read_text().splitlines():
        try:
            total += float(json.loads(line).get("cost_usd") or 0)
        except ValueError:
            continue
    return total


def budget_usd() -> float:
    return float(os.environ.get("DAVINCI_BUDGET_USD", "120"))


def _ledger(entry: dict):
    RUNS.mkdir(exist_ok=True)
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **entry}
    with LEDGER.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def _guard(provider: str, max_tokens: int, messages: list):
    p = prices(provider)
    if p is None:
        k_in, k_out = LIVE[provider]["price"]
        raise BudgetError(f"{k_in}/{k_out} not set: refusing a live {provider} call the budget guard cannot price")
    # Worst case: ~4 chars per input token, every output token used.
    est_in = sum(len(m["content"]) if isinstance(m["content"], str) else 4000 for m in messages) / 4
    worst = (est_in * p[0] + max_tokens * p[1]) / 1e6
    spent, cap = spent_usd(), budget_usd()
    if spent + worst > cap:
        raise BudgetError(f"budget guard: spent ${spent:.2f} + worst case ${worst:.2f} > cap ${cap:.2f}")


def _post(url: str, key: str, body: dict, timeout: int) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise LLMError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:1000]}") from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise LLMError(f"network error: {e}") from None


def _live(provider: str, messages: list, opts: dict) -> Reply:
    cfg = LIVE[provider]
    key = os.environ.get(cfg["key"])
    if not key:
        raise LLMError(f"{cfg['key']} not set")
    model = os.environ.get(f"DAVINCI_MODEL_{provider.upper()}", cfg["model"])
    max_tokens = int(opts.get("max_tokens", 8000))
    _guard(provider, max_tokens, messages)
    body = {"model": model, "messages": messages, cfg["max_tokens_field"]: max_tokens}
    if opts.get("reasoning_effort") and provider == "meta":
        body["reasoning_effort"] = opts["reasoning_effort"]
    t0 = time.time()
    data = _post(f"{cfg['base']}/chat/completions", key, body, int(opts.get("timeout", 300)))
    usage = data.get("usage") or {}
    t_in, t_out = int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))
    p_in, p_out = prices(provider)
    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError):
        raise LLMError(f"unexpected response shape: {json.dumps(data)[:500]}") from None
    return Reply(text=text, provider=provider, model=data.get("model", model), request_sha256="",
                 tokens_in=t_in, tokens_out=t_out, cost_usd=round((t_in * p_in + t_out * p_out) / 1e6, 6),
                 seconds=round(time.time() - t0, 2),
                 extra={"finish_reason": data["choices"][0].get("finish_reason")})


def _fake(messages: list, step: str) -> Reply:
    """Offline stand-in: answers with the reference RTL. Lets the whole loop,
    including repair, be exercised without spending credit."""
    rtl = (ROOT / "rtl" / "sync_fifo.v").read_text()
    if step == "repair":
        text = ("DIAGNOSIS: (fake provider) the write enable ignores a same-cycle read when full; "
                "allow the write when rd_en is high.\n\n```verilog\n" + rtl + "```\n")
    else:
        text = "```verilog\n" + rtl + "```\n"
    return Reply(text=text, provider="fake", model="fake-reference", request_sha256="")


class Replayer:
    """Serves the responses an earlier run recorded, in call order. A request
    whose hash differs from the recorded one is still answered (the prompt
    drifted) but flagged so the evidence shows it."""

    def __init__(self, source_run: str):
        calls = RUNS / source_run / "calls.jsonl"
        if not calls.exists():
            raise LLMError(f"nothing to replay: {calls} not found")
        self.source = source_run
        self.calls = [json.loads(l) for l in calls.read_text().splitlines() if l.strip()]
        self.i = 0

    def next(self, h: str) -> Reply:
        while self.i < len(self.calls) and not self.calls[self.i].get("ok"):
            self.i += 1  # failed calls returned nothing to replay
        if self.i >= len(self.calls):
            raise LLMError(f"replay of {self.source} exhausted after {self.i} calls")
        rec = self.calls[self.i]
        self.i += 1
        f = CACHE / f"{rec['request_sha256']}.json"
        if not f.exists():
            raise LLMError(f"replay of {self.source}: cached response {f.name} missing")
        cached = json.loads(f.read_text())
        return Reply(text=cached["text"], provider="replay", model=f"replay:{cached['model']}",
                     request_sha256="", extra={"replayed_from": self.source,
                                               "request_matches": rec["request_sha256"] == h})


def call(messages: list, *, provider: str, step: str, run_id: str,
         replayer: "Replayer | None" = None, **opts) -> Reply:
    """One model call. Raises BudgetError / LLMError; both are ledgered."""
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider!r}; choose from {PROVIDERS}")
    h = request_hash(messages, {k: v for k, v in opts.items() if k != "timeout"})
    base = {"run_id": run_id, "step": step, "provider": provider, "request_sha256": h}
    try:
        if provider in LIVE:
            reply = _live(provider, messages, opts)
        elif provider == "replay":
            if replayer is None:
                raise LLMError("replay provider needs a Replayer")
            reply = replayer.next(h)
        else:
            reply = _fake(messages, step)
    except BudgetError as e:
        _ledger({**base, "status": "refused_budget", "error": str(e), "cost_usd": 0})
        raise
    except LLMError as e:
        _ledger({**base, "status": "error", "error": str(e)[:500], "cost_usd": 0})
        raise
    reply.request_sha256 = h
    if provider != "replay":
        CACHE.mkdir(parents=True, exist_ok=True)
        (CACHE / f"{h}.json").write_text(json.dumps(
            {"messages": messages, "opts": opts, "text": reply.text, "model": reply.model}, indent=1))
    _ledger({**base, "status": "ok", "model": reply.model, "tokens_in": reply.tokens_in,
             "tokens_out": reply.tokens_out, "cost_usd": reply.cost_usd, "seconds": reply.seconds})
    return reply


def reply_dict(r: Reply) -> dict:
    d = asdict(r)
    d.pop("text")
    return d
