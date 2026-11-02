"""S3 demo: was the reference model right? Measured against the reference RTL.

Drives N input vectors (fixed seed) into the hand-written sat_gain reference
RTL in Icarus, records what the RTL outputs, then compares two Python models
with the simulator's answers:
  - the naive float model (blocks/sat_gain/candidate/float_model.py):
    round-to-nearest, wraps instead of saturating;
  - the bit-accurate model (blocks/sat_gain/tests/golden_model.py).
The RTL outputs are measured (simulator); the counts are computed from them.

usage: python verify/model_demo.py [--n 1000] [--seed 2026] [--out runs/blocks/sat_gain/model_demo]
"""
import argparse
import hashlib
import importlib.util
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_block import ROOT, load, run, suite_hash  # noqa: E402

BLOCK = "sat_gain"
CORNERS = [(127, 127), (-128, -128), (-1, 1), (1, 127)]  # the spec's corner-case table


def _module(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def bits(code: int) -> str:
    return format(code & 0xFF, "08b")


def q17(code: int) -> str:
    s = code - 256 if code & 0x80 else code
    return f"{s}/128"


def vectors(n: int, seed: int) -> list:
    rng = random.Random(seed)
    head = CORNERS[:n]
    return [list(v) for v in head] + [[rng.randint(-128, 127), rng.randint(-128, 127)] for _ in range(n - len(head))]


def compare(captured: list, model, name: str, with_sat: bool) -> dict:
    mism = []
    for i, c in enumerate(captured):
        exp_y, exp_sat = model(c["x"], c["g"])
        exp_y &= 0xFF
        if exp_y != c["y"] or (with_sat and exp_sat != c["sat"]):
            mism.append((i, c, exp_y, exp_sat))
    res = {"model": name, "compared": "y and sat" if with_sat else "y only (the float model has no sat output)",
           "vectors": len(captured), "disagree": len(mism), "agree": len(captured) - len(mism)}
    if mism:
        i, c, ey, es = mism[0]
        res["first_mismatch"] = {
            "vector": i, "x": f"{c['x'] & 0xFF:#04x}", "g": f"{c['g'] & 0xFF:#04x}",
            "x_value": q17(c["x"] & 0xFF), "g_value": q17(c["g"] & 0xFF),
            "model_expected": {"y": f"{ey:#04x}", "y_bits": bits(ey), "y_value": q17(ey)},
            "rtl_got": {"y": f"{c['y']:#04x}", "y_bits": bits(c["y"]), "y_value": q17(c["y"]), "sat": c["sat"]},
        }
        kinds = {"saturation": 0, "rounding": 0}
        for _, c, ey, _ in mism:
            kinds["saturation" if c["sat"] else "rounding"] += 1
        res["disagreements_by_cause"] = kinds
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--rtl", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "blocks" / BLOCK / "model_demo")
    a = ap.parse_args()
    block = load(BLOCK)
    rtl = (a.rtl or ROOT / block["reference_rtl"]).resolve()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    vec = vectors(a.n, a.seed)
    (out / "vectors.json").write_text(json.dumps(vec))
    cap = out / "captured.json"
    cap.unlink(missing_ok=True)
    v = run(block, rtl, out / "sim", test_module="capture_vectors", test_dir=ROOT / "blocks" / BLOCK / "demo",
            extra_env={"DAVINCI_VECTORS": str(out / "vectors.json"), "DAVINCI_CAPTURE": str(cap)})
    if v["status"] != "pass" or not cap.exists():
        raise SystemExit(f"capture simulation failed: {v.get('status')} {v.get('error', '')}")
    captured = json.loads(cap.read_text())

    golden = _module(block["golden_model"], "sat_gain_golden")
    flt = _module(f"{block['candidate_tests']['dir']}/float_model.py", "sat_gain_float")
    result = {
        "label": "measured: reference RTL outputs from Icarus; counts computed from them",
        "block": BLOCK,
        "rtl": str(rtl.relative_to(ROOT)) if rtl.is_relative_to(ROOT) else str(rtl),
        "rtl_sha256": hashlib.sha256(rtl.read_bytes()).hexdigest(),
        "suite_sha256": suite_hash(block),
        "simulator": v["simulator"],
        "vectors": {"n": len(vec), "seed": a.seed, "corner_cases_first": len(CORNERS[:a.n]),
                    "sha256": hashlib.sha256(json.dumps(vec).encode()).hexdigest()},
        "float_model": compare(captured, lambda x, g: (flt.float_gain(x, g), None), "float (round-to-nearest, wraps)",
                               with_sat=False),
        "bit_accurate_model": compare(captured, golden.sat_gain, "bit-accurate (integer, truncate, saturate)",
                                      with_sat=True),
        "model_sha256": {"float": hashlib.sha256((ROOT / block["candidate_tests"]["dir"] / "float_model.py")
                                                 .read_bytes()).hexdigest(),
                         "bit_accurate": hashlib.sha256((ROOT / block["golden_model"]).read_bytes()).hexdigest()},
        "message": "The reference model itself was wrong; DaVINCI shows it before you blame the design.",
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (out / "model_demo.json").write_text(json.dumps(result, indent=2))
    f, b = result["float_model"], result["bit_accurate_model"]
    print(f"reference RTL simulated on {len(vec)} vectors (seed {a.seed})")
    print(f"float model:        disagrees on {f['disagree']} of {f['vectors']}")
    if "first_mismatch" in f:
        m = f["first_mismatch"]
        print(f"  first mismatch: vector {m['vector']} x={m['x']} ({m['x_value']}) g={m['g']} ({m['g_value']}): "
              f"model {m['model_expected']['y']} {m['model_expected']['y_bits']} vs RTL {m['rtl_got']['y']} "
              f"{m['rtl_got']['y_bits']}; by cause {f['disagreements_by_cause']}")
    print(f"bit-accurate model: disagrees on {b['disagree']} of {b['vectors']}")
    sys.exit(0 if b["disagree"] == 0 else 1)


if __name__ == "__main__":
    main()
