"""S6 pre-layout timing and power on the open SKY130 PDK.

Synthesises a FIFO RTL with Yosys onto sky130_fd_sc_hd (typical corner
liberty), then runs OpenSTA on the netlist: worst setup and hold slack at a
stated clock, a maximum-frequency estimate (period minus worst setup slack),
cell area from the liberty cell areas, and report_power with OpenSTA's default
switching activity.

This is a pre-layout estimate: ideal clock, no wire parasitics, default
activity, one corner. It is not layout and not signoff.

Both tools run inside a container with no network, capped CPU/memory/pids, a
read-only root, no capabilities and a non-root user: model-written RTL is
untrusted. The RTL must also pass the same pre-simulation check as the loop
(agent.pipeline.validate) before it is synthesised.

usage: python verify/sta.py --reference            # rtl/sync_fifo.v -> runs/reference/sta
       python verify/sta.py --run runs/<id>        # final simulated RTL of a stored run -> runs/<id>/sta
       python verify/sta.py <rtl.v> --out <dir>
env:   DAVINCI_STA_IMAGE (default ghcr.io/librelane/librelane:3.0.17)
       DAVINCI_PDK_ROOT  (default ~/.ciel, as fetched by `ciel fetch --pdk sky130 <hash>`)
       DAVINCI_STA_PERIOD_NS (default 10, i.e. 100 MHz)
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "verify"))

IMAGE = os.environ.get("DAVINCI_STA_IMAGE", "ghcr.io/librelane/librelane:3.0.17")
PDK_ROOT = Path(os.environ.get("DAVINCI_PDK_ROOT", Path.home() / ".ciel"))
# open_pdks revision pinned by LibreLane 3.0.17 (librelane/pdk_hashes.yaml).
PDK_HASH = "8afc8346a57fe1ab7934ba5a6056ea8b43078e71"
LIB_NAME = "sky130_fd_sc_hd__tt_025C_1v80.lib"
PERIOD_NS = float(os.environ.get("DAVINCI_STA_PERIOD_NS", "10"))
CFG = ROOT / "verify" / "sta"
LABEL = "Pre-layout estimate · SKY130 hd typical corner · no wire parasitics · default activity"
# Same isolation as the simulation sandbox (agent.pipeline.DOCKER_LIMITS), with
# more memory and /tmp for synthesis.
LIMITS = ["--network", "none", "--cpus", "1", "--memory", "2g", "--pids-limit", "256",
          "--read-only", "--tmpfs", "/tmp:size=256m", "--cap-drop", "ALL",
          "--security-opt", "no-new-privileges", "--user", "1000:1000", "-e", "HOME=/tmp"]
TIMEOUT_S = 600


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def liberty() -> Path:
    lib = PDK_ROOT / "ciel" / "sky130" / "versions" / PDK_HASH / "sky130A" / "libs.ref" / "sky130_fd_sc_hd" / "lib" / LIB_NAME
    if not lib.exists():
        raise SystemExit(f"no liberty at {lib}: fetch the PDK with `ciel fetch --pdk sky130 {PDK_HASH}`")
    return lib


def pdk_cfg() -> Path:
    """The PDK's synthesis cell lists (no_synth.cells, drc_exclude.cells) for sky130_fd_sc_hd."""
    return PDK_ROOT / "ciel" / "sky130" / "versions" / PDK_HASH / "sky130A" / "libs.tech" / "openlane" / "sky130_fd_sc_hd"


def image_id() -> str | None:
    p = subprocess.run(["docker", "image", "inspect", "-f", "{{index .RepoDigests 0}}", IMAGE],
                       capture_output=True, text=True)
    return p.stdout.strip() or None


def final_rtl(run_dir: Path) -> tuple[Path, int]:
    """RTL of the last attempt that was simulated (the run's final design)."""
    r = json.loads((run_dir / "run.json").read_text())
    for a in reversed(r["attempts"]):
        if (a.get("measured") or {}).get("status") in ("pass", "fail"):
            return run_dir / f"attempt_{a['n']}" / "sync_fifo.v", a["n"]
    raise SystemExit(f"{run_dir}: no simulated attempt")


def docker(rtl: Path, lib: Path, out: Path, script: list[str]) -> subprocess.CompletedProcess:
    cmd = ["docker", "run", "--rm", *LIMITS, "-e", f"PERIOD_NS={PERIOD_NS:g}", "-e", "LIB=/work/lib/lib.lib",
           "-v", f"{rtl.resolve()}:/work/in/dut.v:ro", "-v", f"{lib}:/work/lib/lib.lib:ro",
           "-v", f"{CFG}:/work/cfg:ro", "-v", f"{pdk_cfg()}:/work/pdkcfg:ro", "-v", f"{out.resolve()}:/work/out",
           "--entrypoint", "timeout", IMAGE, str(TIMEOUT_S - 30), *script]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S)


def num(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


def parse_sta(log: str) -> dict:
    sec = lambda a, b: log.split(f"DAVINCI {a}", 1)[1].split(f"DAVINCI {b}", 1)[0] if f"DAVINCI {a}" in log else ""
    setup = num(r"worst slack\s+(?:max\s+)?(-?[\d.]+)", sec("setup", "hold"))
    hold = num(r"worst slack\s+(?:min\s+)?(-?[\d.]+)", sec("hold", "tns"))
    tns = num(r"tns\s+(?:max\s+)?(-?[\d.]+)", sec("tns", "end"))
    power = {}
    for group in ("Sequential", "Combinational", "Clock", "Macro", "Pad", "Total"):
        m = re.search(rf"^{group}\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)", log, re.M)
        if m:
            power[group.lower()] = {k: float(v) for k, v in zip(("internal_w", "switching_w", "leakage_w", "total_w"),
                                                              m.groups())}
    return {"setup_ws_ns": setup, "hold_ws_ns": hold, "setup_tns_ns": tns, "power": power}


def run(rtl: Path, out: Path, source: dict) -> dict:
    from agent.pipeline import validate

    out.mkdir(parents=True, exist_ok=True)
    for f in out.iterdir():
        if f.is_file():
            f.unlink()
    lib = liberty()
    report = {"label": LABEL, "kind": "measured", "source": source, "rtl_sha256": sha256_file(rtl),
              "clock": {"port": "clk", "period_ns": PERIOD_NS, "target_mhz": round(1000 / PERIOD_NS, 3)},
              "constraints": "ideal clock (no clock tree, so clock-network power is 0); input and output delay 0 ns; no output load; no wire parasitics; "
                             "OpenSTA default switching activity (no simulation activity)",
              "pdk": {"family": "sky130", "variant": "sky130A", "open_pdks": PDK_HASH, "library": "sky130_fd_sc_hd",
                      "liberty": LIB_NAME, "liberty_sha256": sha256_file(lib),
                      "corner": "tt, 25 °C, 1.80 V"},
              "image": {"tag": IMAGE, "digest": image_id()},
              "sta_script_sha256": sha256_file(CFG / "sta.tcl"), "synth_script_sha256": sha256_file(CFG / "synth.tcl")}
    reason = validate(rtl.read_text())
    if reason:
        report |= {"status": "rejected", "reason": reason}
        (out / "sta.json").write_text(json.dumps(report, indent=2))
        return report

    t0 = time.time()
    v = docker(rtl, lib, out, ["sh", "-c", "yosys -V; echo OpenSTA $(sta -version)"])
    vers = v.stdout.strip().splitlines()
    report["tools"] = {"yosys": vers[0] if vers else None, "opensta": vers[1] if len(vers) > 1 else None}

    s = docker(rtl, lib, out, ["yosys", "-q", "-l", "/work/out/synth.log", "-c", "/work/cfg/synth.tcl"])
    if s.returncode != 0 or not (out / "netlist.v").exists():
        report |= {"status": "synth_failed", "reason": (s.stdout + s.stderr)[-1500:]}
        (out / "sta.json").write_text(json.dumps(report, indent=2))
        return report
    stat = json.loads((out / "stat.json").read_text())
    mod = stat.get("modules", {}).get("\\sync_fifo") or next(iter(stat.get("modules", {}).values()), {})
    cells = mod.get("cells") or mod.get("num_cells_by_type") or {}
    area = mod.get("area")
    if area is None:
        area = num(r"Chip area for module .*?:\s+([\d.]+)", (out / "stat.txt").read_text())
    by_type = mod.get("num_cells_by_type") or {}
    flops = sum(n for c, n in by_type.items() if re.search(r"__(dfx|dfr|dfs|dfb|edf|sdf)", c))
    report["synthesis"] = {"cells": mod.get("num_cells"), "flip_flops": flops, "area_um2": area,
                           "area_source": "sum of liberty cell areas (yosys stat -liberty)",
                           "cells_by_type": by_type}

    t = docker(rtl, lib, out, ["sta", "-no_init", "-no_splash", "-exit", "/work/cfg/sta.tcl"])
    (out / "sta.log").write_text(t.stdout + t.stderr)
    if t.returncode != 0:
        report |= {"status": "sta_failed", "reason": (t.stdout + t.stderr)[-1500:]}
        (out / "sta.json").write_text(json.dumps(report, indent=2))
        return report
    p = parse_sta(t.stdout)
    ws = p["setup_ws_ns"]
    report["timing"] = {"setup_ws_ns": ws, "hold_ws_ns": p["hold_ws_ns"], "setup_tns_ns": p["setup_tns_ns"],
                        "met": ws is not None and ws >= 0 and (p["hold_ws_ns"] or 0) >= 0,
                        "min_period_ns": round(PERIOD_NS - ws, 4) if ws is not None else None,
                        "fmax_mhz": round(1000 / (PERIOD_NS - ws), 1) if ws is not None and PERIOD_NS - ws > 0 else None,
                        "fmax_note": "estimate: clock period minus worst setup slack (pre-layout, ideal clock)"}
    report["power"] = {"total_w": p["power"].get("total", {}).get("total_w"), "groups": p["power"],
                       "activity": "OpenSTA default (inputs 0.1 toggle density, clock from create_clock)"}
    report["status"] = "ok" if ws is not None and report["power"]["total_w"] is not None else "parse_failed"
    report["seconds"] = round(time.time() - t0, 1)
    (out / "sta.json").write_text(json.dumps(report, indent=2))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rtl", type=Path, nargs="?")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--run", type=Path, help="stored run: its final simulated RTL")
    ap.add_argument("--reference", action="store_true", help="reference RTL rtl/sync_fifo.v")
    a = ap.parse_args()
    if a.run:
        rtl, n = final_rtl(a.run)
        r = run(rtl, a.run / "sta", {"run_id": a.run.name, "attempt": n, "rtl": "model"})
    elif a.reference:
        r = run(ROOT / "rtl" / "sync_fifo.v", ROOT / "runs" / "reference" / "sta",
                {"run_id": "reference", "rtl": "reference (hand-written)"})
    elif a.rtl:
        r = run(a.rtl, a.out or ROOT / "runs" / "sta", {"rtl": str(a.rtl)})
    else:
        ap.error("give an RTL file, --run or --reference")
    print(json.dumps({k: r.get(k) for k in ("status", "reason", "synthesis", "timing", "power")}, indent=1)[:3000])
    sys.exit(0 if r.get("status") == "ok" else 1)


if __name__ == "__main__":
    main()
