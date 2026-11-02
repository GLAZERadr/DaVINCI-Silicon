"""Area indicator from Yosys: generic cell and flip-flop counts of a design.

Runs `synth -top sync_fifo; stat` on one RTL file and records the total cell
count, the flip-flop count (the DFF/latch cell types in `stat`), the Yosys
version, the full log and the RTL sha256. These are generic Yosys cells with no
standard-cell library: a size indicator, not silicon area. There is no timing
or power flow here; both are recorded as "not measured", never estimated.

usage: python verify/area.py <rtl.v> --out <dir>    # synthesise (inside the sandbox for model RTL)
       python verify/area.py --run runs/<id>        # host: final RTL of a stored run, in Docker
       python verify/area.py --reference            # host: reference RTL, local Yosys (Docker if none)
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOP = "sync_fifo"
LABEL = "generic Yosys cells, no standard-cell library: a size indicator, not silicon area"
NOT_MEASURED = "not measured (no STA or power flow)"
# Flip-flop cell types after `synth`: fine-grained $_DFF*_ / $_SDFF*_ / $_ALDFF*_ cells, or
# coarse $dff/$adff/$sdff/... if any survive. Latches ($_DLATCH*, $_SR_) are counted apart.
FLOP = re.compile(r"^\$_(DFF|DFFE|SDFF|SDFFE|SDFFCE|DFFSR|DFFSRE|ALDFF|ALDFFE)_|^\$(a|ad|al|s|sd)?dff(e|sr|sre|ce)?$")
LATCH = re.compile(r"^\$_(DLATCH|DLATCHSR|SR)_|^\$(dlatch|dlatchsr|sr)$")


def area_hash() -> str:
    return hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest()


def parse_stat(stat: dict) -> dict:
    """Numbers from `stat -json` for the top module."""
    mods = stat.get("modules", {})
    top = mods.get(f"\\{TOP}") or mods.get(TOP) or (next(iter(mods.values())) if len(mods) == 1 else None)
    if top is None:
        raise ValueError(f"no module {TOP} in stat output")
    by_type = {k: int(v) for k, v in (top.get("num_cells_by_type") or {}).items()}
    flops = {k: n for k, n in by_type.items() if FLOP.match(k)}
    latches = {k: n for k, n in by_type.items() if LATCH.match(k)}
    return {"cells": int(top["num_cells"]), "flops": sum(flops.values()), "flop_types": flops,
            "latches": sum(latches.values()),
            "cells_by_type": dict(sorted(by_type.items())), "wires": top.get("num_wires"),
            "wire_bits": top.get("num_wire_bits")}


def yosys_version(yosys: str) -> str:
    p = subprocess.run([yosys, "-V"], capture_output=True, text=True, timeout=30)
    return (p.stdout or p.stderr).strip()


def run(rtl: Path, out: Path, yosys: str = "yosys") -> dict:
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    report = {"label": "measured", "kind": LABEL, "top": TOP,
              "rtl_sha256": hashlib.sha256(rtl.read_bytes()).hexdigest(), "area_sha256": area_hash(),
              "script": f"read_verilog <rtl>; synth -top {TOP}; stat",
              "timing": NOT_MEASURED, "power": NOT_MEASURED}
    log, stat_json = out / "yosys.log", out / "stat.json"
    stat_json.unlink(missing_ok=True)
    try:
        report["yosys"] = yosys_version(yosys)
        script = f"read_verilog {rtl}; synth -top {TOP}; stat; tee -q -o {stat_json} stat -json"
        p = subprocess.run([yosys, "-q", "-l", str(log), "-p", script], capture_output=True, text=True,
                           timeout=110)
        if p.returncode != 0 or not stat_json.exists():
            raise RuntimeError(f"yosys exit {p.returncode}: {(p.stderr or p.stdout)[-1500:]}")
        report |= parse_stat(json.loads(stat_json.read_text())) | {"status": "ok"}
    except Exception as e:  # a design that does not synthesise gets no numbers, recorded as such
        report |= {"status": "synth_error", "error": str(e)[-1500:]}
    report["seconds"] = round(time.time() - t0, 2)
    (out / "area.json").write_text(json.dumps(report, indent=2))
    return report


def final_rtl(run_dir: Path) -> Path:
    """RTL of the last attempt that was simulated."""
    r = json.loads((run_dir / "run.json").read_text())
    for a in reversed(r["attempts"]):
        m = a.get("measured") or {}
        if m.get("status") in ("pass", "fail"):
            return run_dir / f"attempt_{a['n']}" / "sync_fifo.v"
    raise SystemExit(f"{run_dir}: no simulated attempt")


def in_docker(rtl: Path, out: Path) -> dict:
    sys.path.insert(0, str(ROOT))
    from agent.pipeline import DOCKER_LIMITS, SANDBOX_IMAGE, SIM_TIMEOUT_S

    out.mkdir(parents=True, exist_ok=True)
    for old in ("area.json", "stat.json", "yosys.log"):  # never read back a previous run's result
        (out / old).unlink(missing_ok=True)
    cmd = ["docker", "run", "--rm", *DOCKER_LIMITS, "--entrypoint", "timeout",
           "-v", f"{rtl.resolve()}:/work/in/dut.v:ro", "-v", f"{out.resolve()}:/work/out",
           SANDBOX_IMAGE, "120", "python", "verify/area.py", "/work/in/dut.v", "--out", "/work/out"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=SIM_TIMEOUT_S)
    f = out / "area.json"
    if not f.exists():
        raise SystemExit(f"sandbox wrote no area.json (exit {p.returncode}): {p.stderr[-1000:]}")
    report = json.loads(f.read_text())
    if report.get("area_sha256") != area_hash():
        raise SystemExit("ABORT: the sandbox ran a different verify/area.py; rebuild with `make image`")
    if report.get("rtl_sha256") != hashlib.sha256(rtl.read_bytes()).hexdigest():
        raise SystemExit("ABORT: the sandbox synthesised different RTL")
    report["sandbox"] = SANDBOX_IMAGE
    f.write_text(json.dumps(report, indent=2))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rtl", type=Path, nargs="?")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--run", type=Path, help="stored run: synthesise its final RTL inside Docker")
    ap.add_argument("--reference", action="store_true", help="reference RTL, local Yosys (Docker if not installed)")
    a = ap.parse_args()
    if a.run:
        r = in_docker(final_rtl(a.run), a.run / "area")
    elif a.reference:
        rtl, out = ROOT / "rtl" / "sync_fifo.v", ROOT / "runs" / "reference" / "area"
        r = run(rtl, out) if shutil.which("yosys") else in_docker(rtl, out)
    elif a.rtl:
        r = run(a.rtl, a.out or ROOT / "runs" / "area")
    else:
        ap.error("give an RTL file, --run or --reference")
    print(json.dumps({k: r.get(k) for k in ("status", "cells", "flops", "flop_types", "yosys", "error")}, indent=1))
    sys.exit(0 if r.get("status") == "ok" else 1)


if __name__ == "__main__":
    main()
