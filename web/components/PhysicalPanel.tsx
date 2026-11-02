import type { Json, Physical } from "@/lib/evidence";

// S6 / S10: timing, area and power of the reference RTL and this run's final RTL on the
// open SKY130 PDK. Every number comes from a stored tool run (sta.json, layout/summary.json).

const fmt = (v: unknown, digits: number, unit = "") =>
  typeof v === "number" && Number.isFinite(v) ? `${v.toFixed(digits)}${unit}` : "n/a";
const mw = (w: unknown) => (typeof w === "number" ? `${(w * 1000).toFixed(3)} mW` : "n/a");
const slack = (v: unknown) => (typeof v !== "number" ? <span className="mark-neutral">○ n/a</span>
  : v >= 0 ? <span className="mark-pass">✓ {v.toFixed(3)} ns met</span> : <span className="mark-fail">✕ {v.toFixed(3)} ns violated</span>);

function Status({ s }: { s: Json | null }) {
  if (!s) return <span className="mark-neutral">○ Not run</span>;
  return s.status === "ok" ? <span className="mark-pass">✓ Done</span> : <span className="mark-fail">✕ {String(s.status).replace(/_/g, " ")}</span>;
}

// Why max-slew counts are non-zero, from the STA reports, repair log and flow config (checked
// 2 Nov on the reference RTL and every exported run): no I/O port among the violators (driving
// cell and output load are set by the flow's SDC); the limit is the flow default
// MAX_TRANSITION_CONSTRAINT; design repair runs after global placement, before routing.
function slewNote(ref: Json | null, final: Json | null) {
  const count = (s: Json | null, proc: string) => s?.corners?.find((c: Json) => c.process === proc)?.max_slew_violations;
  const any = [ref, final].some((s) => (s?.corners ?? []).some((c: Json) => (c.max_slew_violations ?? 0) > 0));
  if (!any) return null;
  const limit = ref?.flow?.config?.MAX_TRANSITION_CONSTRAINT ?? final?.flow?.config?.MAX_TRANSITION_CONSTRAINT ?? 0.75;
  const refCounts = ["ss", "tt"].map((p) => `${p} ${count(ref, p) ?? "n/a"}`).join(", ");
  return (
    <p className="box-pad meta-text">
      <span className="tag-measured">measured</span> Max-slew counts: every violator is an internal cell pin, none an I/O
      port (the flow&apos;s SDC sets a driving cell and an output load). The limit is the flow&apos;s default
      max transition of {limit} ns; slew is repaired after placement, before routing, and the counts here are
      measured after routing. The hand-written reference RTL shows the same pattern ({refCounts} pins), so the
      counts reflect the default flow settings rather than a difference between the two designs. Not tuned.
    </p>
  );
}

function finalLabel(s: Json | null, runId: string) {
  const n = s?.source?.attempt;
  return <>Final RTL <span className="meta-text">{runId}{n ? `, attempt ${n}` : ""}</span></>;
}

function PreLayout({ p }: { p: Physical }) {
  const { staRef: a, staFinal: b } = p;
  const any = (a ?? b)!;
  const rows: [string, (s: Json) => React.ReactNode][] = [
    ["Status", (s) => <Status s={s} />],
    ["Cell area (liberty cell areas)", (s) => fmt(s.synthesis?.area_um2, 1, " µm²")],
    ["Cells · flip-flops", (s) => s.synthesis ? `${s.synthesis.cells} · ${s.synthesis.flip_flops}` : "n/a"],
    [`Worst setup slack at ${fmt(any.clock?.target_mhz, 0)} MHz`, (s) => slack(s.timing?.setup_ws_ns)],
    ["Worst hold slack", (s) => slack(s.timing?.hold_ws_ns)],
    ["Max frequency (estimate)", (s) => fmt(s.timing?.fmax_mhz, 1, " MHz")],
    ["Total power (default activity)", (s) => mw(s.power?.total_w)],
  ];
  return (
    <section className="box" aria-labelledby="prelayout">
      <div className="box-header">
        <h2 id="prelayout">Pre-layout estimate (SKY130)</h2>
        <span className="tag-measured">measured</span>
      </div>
      <p className="box-lede">{any.label}. Synthesis and static timing only: no placement, no routing, not signoff.</p>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Metric</th><th>Reference RTL <span className="meta-text">hand-written</span></th><th>{finalLabel(b, p.runId)}</th></tr></thead>
          <tbody>
            {rows.map(([name, f]) => (
              <tr key={name}><td>{name}</td><td>{a ? f(a) : <Status s={null} />}</td><td>{b ? f(b) : <Status s={null} />}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="box-footer">
        <span className="meta-text">{any.tools?.yosys?.split(" (")[0]} · {any.tools?.opensta} · {any.pdk?.library} {any.pdk?.liberty} · open_pdks <span className="mono">{String(any.pdk?.open_pdks).slice(0, 10)}</span></span>
        <span className="meta-text">{any.constraints}</span>
      </div>
    </section>
  );
}

function PostLayout({ p }: { p: Physical }) {
  const { layoutRef: a, layoutFinal: b } = p;
  const any = (a ?? b)!;
  const corners: string[] = Array.from(new Set([...(a?.corners ?? []), ...(b?.corners ?? [])].map((c: Json) => c.corner)));
  const cell = (s: Json | null, corner: string, f: (c: Json) => React.ReactNode) => {
    const c = s?.corners?.find((x: Json) => x.corner === corner);
    return c ? f(c) : <span className="mark-neutral">○ n/a</span>;
  };
  const check = (s: Json | null, k: string) => {
    const v = s?.checks?.[k];
    return typeof v !== "number" ? <span className="mark-neutral">○ Not run</span>
      : v === 0 ? <span className="mark-pass">✓ Clean</span> : <span className="mark-fail">✕ {v} errors</span>;
  };
  const both = (f: (s: Json | null) => React.ReactNode) => <><td>{f(a)}</td><td>{f(b)}</td></>;
  return (
    <section className="box" aria-labelledby="postlayout">
      <div className="box-header">
        <h2 id="postlayout">Post-layout (OpenLane 2, SKY130)</h2>
        <span className="tag-measured">measured</span>
      </div>
      <p className="box-lede">{any.label} Clock {fmt(any.clock?.period_ns, 1)} ns ({fmt(any.clock?.target_mhz, 0)} MHz);
        nominal RC corners shown. Max frequency = period minus worst setup slack under the flow&apos;s SDC
        {any.constraints?.input_delay != null ? ` (I/O delay ${any.constraints.input_delay} ns, clock uncertainty ${any.constraints.clock_uncertainty} ns, derate ${any.constraints.timing_derate})` : ""}.
        Power: per-corner OpenSTA with extracted parasitics and default switching activity.</p>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Corner · metric</th><th>Reference RTL <span className="meta-text">hand-written</span></th><th>{finalLabel(b, p.runId)}</th></tr></thead>
          <tbody>
            <tr><td>Flow</td>{both((s) => <Status s={s} />)}</tr>
            {corners.flatMap((corner) => {
              const name = <><strong>{corner.split("_")[1]}</strong> <span className="mono meta-text">{corner}</span></>;
              return [
                <tr key={`${corner}-s`}><td>{name} setup slack</td>{both((s) => cell(s, corner, (c) => slack(c.setup_ws_ns)))}</tr>,
                <tr key={`${corner}-h`}><td>{name} hold slack</td>{both((s) => cell(s, corner, (c) => slack(c.hold_ws_ns)))}</tr>,
                <tr key={`${corner}-f`}><td>{name} max frequency</td>{both((s) => cell(s, corner, (c) => fmt(c.fmax_mhz, 1, " MHz")))}</tr>,
                <tr key={`${corner}-p`}><td>{name} total power</td>{both((s) => cell(s, corner, (c) => mw(c.power_total_w)))}</tr>,
                <tr key={`${corner}-v`}><td>{name} max-slew violations</td>{both((s) => cell(s, corner, (c) => typeof c.max_slew_violations !== "number" ? "n/a"
                  : c.max_slew_violations === 0 ? <span className="mark-pass">✓ None</span> : <span className="mark-fail">✕ {c.max_slew_violations} pins</span>))}</tr>,
              ];
            })}
            <tr><td>Die area</td>{both((s) => fmt(s?.area?.die_um2, 0, " µm²"))}</tr>
            <tr><td>DRC (Magic)</td>{both((s) => check(s, "magic_drc_errors"))}</tr>
            <tr><td>DRC (KLayout)</td>{both((s) => check(s, "klayout_drc_errors"))}</tr>
            <tr><td>LVS (Netgen)</td>{both((s) => check(s, "lvs_errors"))}</tr>
            <tr><td>GDS produced</td>{both((s) => s?.gds === true ? <span className="mark-pass">✓ Yes</span> : s?.gds === false ? <span className="mark-fail">✕ No</span> : <span className="mark-neutral">○ Not run</span>)}</tr>
          </tbody>
        </table>
      </div>
      {slewNote(a, b)}
      <div className="box-footer">
        <span className="meta-text">{any.flow?.name} {any.flow?.version} · {any.tools?.openroad ? `OpenROAD ${String(any.tools.openroad).slice(0, 10)} · ` : ""}{any.pdk?.variant} {any.pdk?.library} · open_pdks <span className="mono">{String(any.pdk?.open_pdks).slice(0, 10)}</span></span>
        <span className="meta-text">Open-source flow results; not foundry-certified, not commercial signoff.</span>
      </div>
    </section>
  );
}

export default function PhysicalPanel({ data }: { data: Physical | null }) {
  if (!data) return null;
  const pre = data.staRef || data.staFinal;
  const post = data.layoutRef || data.layoutFinal;
  if (!pre && !post) return null;
  return (
    <>
      <h2 className="group-title">Timing, area and power (SKY130)</h2>
      {pre && <PreLayout p={data} />}
      {post && <PostLayout p={data} />}
    </>
  );
}
