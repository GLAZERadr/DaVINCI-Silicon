# S6 / S10: timing, area and power on SKY130 (2 Nov 2026)

Two checks, both on the open SKY130 PDK, both run by tools (never by the model), both labelled *measured*.

| | S6 pre-layout | S10 post-layout |
| --- | --- | --- |
| Script | `verify/sta.py` (`verify/sta/synth.tcl`, `verify/sta/sta.tcl`) | `verify/layout.py` (`verify/layout/config.json`) |
| Make | `make sta RUN=<id>`, `make sta-ref` | `make layout RUN=<id>`, `make layout-ref` |
| Output | `runs/<id>/sta/` (`sta.json`, synth/STA logs, netlist) | `runs/<id>/layout/` (`summary.json`, `flow.log`, full LibreLane run with GDS under `runs/flow/`) |
| Label | "Pre-layout estimate · SKY130 hd typical corner · no wire parasitics · default activity" | "Post-layout, multi-corner (ss/tt/ff) STA and power from the open-source OpenLane 2 flow on SKY130." |
| Tools | Yosys 0.62 + OpenSTA 2.7.0 | LibreLane v3.0.17 Classic flow: Yosys, OpenROAD (place, CTS, route), OpenRCX, OpenSTA, Magic 8.3.623, KLayout 0.30.7, Netgen 1.5.316 |

Both use the image `ghcr.io/librelane/librelane:3.0.17` (arm64 + amd64, 7.5 GB unpacked) and the SKY130 PDK at the open_pdks revision LibreLane 3.0.17 pins (`8afc8346a57fe1ab7934ba5a6056ea8b43078e71`), fetched with `ciel` (sky130_fd_sc_hd, sky130_fd_io, sky130_fd_pr, 1.6 GB in `~/.ciel`):

```bash
docker pull ghcr.io/librelane/librelane:3.0.17
pip install ciel && ciel fetch --pdk sky130 -l sky130_fd_sc_hd -l sky130_fd_io -l sky130_fd_pr 8afc8346a57fe1ab7934ba5a6056ea8b43078e71
```

Isolation: the RTL first passes `agent.pipeline.validate`; tools run in a container with no network, capped CPU/memory/pids, read-only root, no capabilities, uid 1000, the PDK mounted read-only. S10 is a separate heavy job: run it once per design, not per repair attempt.

## What the numbers mean

- **S6**: one liberty corner (tt, 25 °C, 1.80 V), ideal clock, I/O delays 0 ns, no output load, no wires, OpenSTA default switching activity. Area is the sum of liberty cell areas. Max frequency = clock period minus worst setup slack. Clock-network power is 0 because there is no clock tree yet.
- **S10**: placed and routed with clock tree; parasitics extracted by OpenRCX; STA at 9 corners (ss/tt/ff × min/nom/max RC); the board shows the three nominal-RC corners, `summary.json` keeps the RC extremes. The flow's generic SDC applies 2 ns I/O delay, 0.25 ns clock uncertainty, 5 % derate, 33 fF output load, so its max-frequency figure is lower than S6's and the two are not comparable. Power per corner from OpenSTA with the SPEF and default activity. DRC (Magic, KLayout), LVS (Netgen) and the GDS come from the same flow.
- Neither is foundry-certified or commercial signoff.

## Stored results (2 Nov 2026, clock 10 ns)

S6 (`runs/<id>/sta/sta.json`):

| RTL | Area µm² | Cells / FFs | Setup WS | Hold WS | fmax est. | Power |
| --- | --- | --- | --- | --- | --- | --- |
| reference | 6507.5 | 440 / 151 | 7.436 ns | 0.062 ns | 390.0 MHz | 1.031 mW |
| live01 attempt 1 (model) | 6543.8 | 454 / 151 | 6.757 ns | 0.057 ns | 308.4 MHz | 1.048 mW |
| live02-m1 attempt 2 (model) | 6505.0 | 436 / 151 | 7.241 ns | 0.057 ns | 362.5 MHz | 1.088 mW |

S10 (`runs/<id>/layout/summary.json`), setup WS / fmax / power per corner:

| RTL | ss (100 °C 1.60 V) | tt (25 °C 1.80 V) | ff (−40 °C 1.95 V) | Die µm² | DRC / LVS / GDS |
| --- | --- | --- | --- | --- | --- |
| reference | 1.075 ns / 112.0 MHz / 1.991 mW | 4.680 / 188.0 / 2.501 | 5.764 / 236.1 / 2.904 | 21172 | clean / clean / yes |
| live01 attempt 1 | 1.526 / 118.0 / 1.973 | 5.161 / 206.6 / 2.477 | 6.153 / 259.9 / 2.874 | 20766 | clean / clean / yes |
| live02-m1 attempt 2 | **−0.172** / 98.3 / 1.955 | 4.385 / 178.1 / 2.456 | 5.638 / 229.2 / 2.852 | 21123 | clean / clean / yes |

Hold met at every corner for all three. Max-slew violations remain at the ss corner for all three designs (reference 139, live01 106, live02-m1 141 pins) and at tt for the reference (11); the flow finishes and reports them, the board shows them. live02-m1's repaired RTL misses 100 MHz at the ss corner (3 setup violations); the reference and live01 meet it.

## Board

`web/components/PhysicalPanel.tsx` renders "Pre-layout estimate (SKY130)" and "Post-layout (OpenLane 2, SKY130)" boxes on a run's Evidence Board, reference vs final RTL, only when the summaries exist. `scripts/export_evidence.py` copies only `sta/sta.json` and `layout/summary.json` per run and for the reference (no netlists, GDS or logs).
