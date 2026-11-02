"""S10 post-layout, multi-corner timing and power with the open-source OpenLane 2
flow (LibreLane) on SKY130.

Runs the LibreLane Classic flow once on a FIFO RTL (the reference, or a stored
run's final RTL): synthesis, floorplan, placement, CTS, routing, parasitic
extraction (OpenRCX), multi-corner STA and power with the extracted parasitics,
GDS stream-out, DRC (Magic, KLayout) and LVS (Netgen). It is a separate heavy
job, not part of the per-run simulation sandbox, and runs once per design, not
per repair attempt.

The container has no network, capped CPU/memory/pids, a read-only root, no
capabilities and a non-root user; the PDK is mounted read-only. The RTL must
pass agent.pipeline.validate first (model-written RTL is untrusted).

Writes runs/<id>/layout/: src/dut.v, config.json, flow.log, the full LibreLane
run under runs/flow/ (reports, GDS; gitignored) and summary.json (small; the
only file the evidence export copies).

usage: python verify/layout.py --reference          # rtl/sync_fifo.v -> runs/reference/layout
       python verify/layout.py --run runs/<id>      # final simulated RTL of a stored run
       python verify/layout.py --summarise <layout dir>   # rebuild summary.json from a finished flow
env:   DAVINCI_LAYOUT_IMAGE (default ghcr.io/librelane/librelane:3.0.17), DAVINCI_PDK_ROOT (default ~/.ciel)
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "verify"))
from sta import PDK_HASH, PDK_ROOT, final_rtl, sha256_file  # noqa: E402

IMAGE = os.environ.get("DAVINCI_LAYOUT_IMAGE", "ghcr.io/librelane/librelane:3.0.17")
CONFIG = ROOT / "verify" / "layout" / "config.json"
LABEL = "Post-layout, multi-corner (ss/tt/ff) STA and power from the open-source OpenLane 2 flow on SKY130."
# The three nominal-RC process corners shown; the other RC extremes are kept in summary.json.
SHOWN = {"nom_ss_100C_1v60": "ss", "nom_tt_025C_1v80": "tt", "nom_ff_n40C_1v95": "ff"}
LIMITS = ["--network", "none", "--cpus", "4", "--memory", "3g", "--pids-limit", "1024",
          "--read-only", "--tmpfs", "/tmp:size=2g", "--cap-drop", "ALL",
          "--security-opt", "no-new-privileges", "--user", "1000:1000", "-e", "HOME=/tmp"]
TIMEOUT_S = 3600


def pdk_dir() -> Path:
    d = PDK_ROOT / "ciel" / "sky130" / "versions" / PDK_HASH
    if not (d / "sky130A").exists():
        raise SystemExit(f"no PDK at {d}: `ciel fetch --pdk sky130 {PDK_HASH}`")
    return d


def docker(design: Path, args: list[str], timeout: int) -> subprocess.CompletedProcess:
    cmd = ["docker", "run", "--rm", *LIMITS, "-v", f"{pdk_dir()}:/pdk:ro", "-v", f"{design.resolve()}:/work/design",
           "-w", "/work/design", "--entrypoint", "timeout", IMAGE, str(timeout - 60), *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def tool_versions(design: Path) -> dict:
    p = docker(design, ["sh", "-c", "librelane --version | head -1; echo; openroad -version; yosys -V; "
                                    "magic --version; klayout -v; netgen -batch quit 2>&1 | grep -i netgen | head -1"], 300)
    lines = [l.strip() for l in p.stdout.splitlines() if l.strip()]
    pick = lambda pat: next((l for l in lines if re.search(pat, l, re.I)), None)
    return {"librelane": pick(r"^LibreLane"), "openroad": next((l for l in lines if re.fullmatch(r"[0-9a-f]{7,40}", l)), None),
            "yosys": (pick(r"^Yosys") or "").split(" (")[0] or None, "magic": pick(r"^\d+\.\d+\.\d+$"),
            "klayout": pick(r"^KLayout"), "netgen": pick(r"netgen")}


def image_digest() -> str | None:
    p = subprocess.run(["docker", "image", "inspect", "-f", "{{index .RepoDigests 0}}", IMAGE], capture_output=True, text=True)
    return p.stdout.strip() or None


def power_total(rpt: Path) -> dict | None:
    if not rpt.exists():
        return None
    m = re.search(r"^Total\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)", rpt.read_text(), re.M)
    return dict(zip(("internal_w", "switching_w", "leakage_w", "total_w"), map(float, m.groups()))) if m else None


def summarise(design: Path, source: dict, extra: dict | None = None) -> dict:
    flow = design / "runs" / "flow"
    cfg = json.loads((design / "config.json").read_text())
    period = float(cfg["CLOCK_PERIOD"])
    s = {"label": LABEL, "kind": "measured", "source": source, "rtl_sha256": sha256_file(design / "src" / "dut.v"),
         "clock": {"port": cfg["CLOCK_PORT"], "period_ns": period, "target_mhz": round(1000 / period, 3)},
         "flow": {"name": "LibreLane (OpenLane 2 lineage)", "version": None, "flow": "Classic", "config": cfg},
         "pdk": {"family": "sky130", "variant": "sky130A", "library": "sky130_fd_sc_hd", "open_pdks": PDK_HASH},
         "image": {"tag": IMAGE, "digest": image_digest()}, **(extra or {})}
    if s.get("tools", {}).get("librelane"):
        s["flow"]["version"] = s["tools"]["librelane"].replace("LibreLane ", "")
    metrics_f = flow / "final" / "metrics.json"
    steps = sorted(d.name for d in flow.iterdir() if d.is_dir() and re.match(r"^\d+-", d.name)) if flow.exists() else []
    s["last_step"] = steps[-1] if steps else None
    if not metrics_f.exists():
        s["status"] = "failed"
        s["stopped_at"] = s["last_step"]
        return s
    m = json.loads(metrics_f.read_text())
    sta_dir = next((flow / d for d in reversed(steps) if d.endswith("openroad-stapostpnr")), None)
    sdc = {}
    if sta_dir:
        log = sta_dir / "nom_tt_025C_1v80" / "sta.log"
        for k, v in re.findall(r"\[INFO\] Setting ([a-z ]+?) to: ([\d.%]+)", log.read_text() if log.exists() else ""):
            sdc[k.replace(" ", "_")] = v if v.endswith("%") else round(float(v), 4)
    s["constraints"] = {"sdc": "LibreLane generic fallback SDC (base.sdc)", **sdc}
    corners = []
    for key in sorted(k for k in m if k.startswith("timing__setup__ws__corner:")):
        c = key.split(":", 1)[1]
        ws = m[key]
        p = power_total(sta_dir / c / "power.rpt") if sta_dir else None
        corners.append({"corner": c, "process": SHOWN.get(c), "shown": c in SHOWN,
                        "setup_ws_ns": round(ws, 4), "hold_ws_ns": round(m.get(f"timing__hold__ws__corner:{c}"), 4),
                        "setup_violations": m.get(f"timing__setup_vio__count__corner:{c}"),
                        "hold_violations": m.get(f"timing__hold_vio__count__corner:{c}"),
                        "max_slew_violations": m.get(f"design__max_slew_violation__count__corner:{c}"),
                        "max_cap_violations": m.get(f"design__max_cap_violation__count__corner:{c}"),
                        "fmax_mhz": round(1000 / (period - ws), 1) if period - ws > 0 else None,
                        "power_total_w": p["total_w"] if p else None, "power": p})
    order = list(SHOWN)
    s["corners"] = sorted([c for c in corners if c["shown"]], key=lambda c: order.index(c["corner"]))
    s["corners_rc_extremes"] = [c for c in corners if not c["shown"]]
    s["fmax_note"] = "clock period minus worst setup slack at that corner, under the flow's SDC (I/O delays, uncertainty, derate)"
    s["power_note"] = "OpenSTA report_power per corner with SPEF from OpenRCX and default switching activity"
    s["area"] = {"die_um2": m.get("design__die__area"), "core_um2": m.get("design__core__area"),
                 "instances": m.get("design__instance__count"), "utilization": m.get("design__instance__utilization")}
    s["checks"] = {"magic_drc_errors": m.get("magic__drc_error__count"), "klayout_drc_errors": m.get("klayout__drc_error__count"),
                   "lvs_errors": m.get("design__lvs_error__count"), "xor_differences": m.get("design__xor_difference__count"),
                   "route_drc_errors": m.get("route__drc_errors"), "antenna_violating_nets": m.get("antenna__violating__nets"),
                   "max_slew_violations": m.get("design__max_slew_violation__count"),
                   "max_cap_violations": m.get("design__max_cap_violation__count"),
                   "setup_violations": m.get("timing__setup_vio__count"), "hold_violations": m.get("timing__hold_vio__count")}
    gds = flow / "final" / "gds" / "sync_fifo.gds"
    s["gds"] = gds.exists()
    if gds.exists():
        s["gds_sha256"] = sha256_file(gds)
        s["gds_bytes"] = gds.stat().st_size
    s["status"] = "ok"
    return s


def run(rtl: Path, design: Path, source: dict) -> dict:
    from agent.pipeline import validate

    if (design / "runs").exists():
        shutil.rmtree(design / "runs")
    (design / "src").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(rtl, design / "src" / "dut.v")
    shutil.copyfile(CONFIG, design / "config.json")
    reason = validate(rtl.read_text())
    if reason:
        s = {"label": LABEL, "kind": "measured", "source": source, "status": "rejected", "reason": reason}
        (design / "summary.json").write_text(json.dumps(s, indent=2))
        return s
    tools = tool_versions(design)
    t0 = time.time()
    try:
        p = docker(design, ["librelane", "--manual-pdk", "--pdk-root", "/pdk", "--pdk", "sky130A", "--scl", "sky130_fd_sc_hd",
                            "--run-tag", "flow", "--overwrite", "/work/design/config.json"], TIMEOUT_S)
        (design / "flow.log").write_text(p.stdout + p.stderr)
        code = p.returncode
    except subprocess.TimeoutExpired:
        code = "timeout"
    s = summarise(design, source, {"tools": tools, "exit": code, "seconds": round(time.time() - t0, 1)})
    if code != 0 and s["status"] == "ok":
        s["status"] = "failed"
        s["stopped_at"] = s.get("last_step")
    (design / "summary.json").write_text(json.dumps(s, indent=2))
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, help="stored run: its final simulated RTL")
    ap.add_argument("--reference", action="store_true", help="reference RTL rtl/sync_fifo.v")
    ap.add_argument("--summarise", type=Path, help="rebuild summary.json of a finished layout dir")
    a = ap.parse_args()
    if a.run:
        rtl, n = final_rtl(a.run)
        s = run(rtl, a.run / "layout", {"run_id": a.run.name, "attempt": n, "rtl": "model"})
    elif a.reference:
        s = run(ROOT / "rtl" / "sync_fifo.v", ROOT / "runs" / "reference" / "layout",
                {"run_id": "reference", "rtl": "reference (hand-written)"})
    elif a.summarise:
        old = json.loads((a.summarise / "summary.json").read_text()) if (a.summarise / "summary.json").exists() else {}
        s = summarise(a.summarise, old.get("source", {}), {k: old[k] for k in ("tools", "exit", "seconds") if k in old})
        (a.summarise / "summary.json").write_text(json.dumps(s, indent=2))
    else:
        ap.error("give --run, --reference or --summarise")
    print(json.dumps({k: s.get(k) for k in ("status", "stopped_at", "reason", "corners", "checks", "gds", "area")}, indent=1)[:4000])
    sys.exit(0 if s.get("status") == "ok" else 1)


if __name__ == "__main__":
    main()
