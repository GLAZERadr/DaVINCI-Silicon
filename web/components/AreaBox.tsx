import type { Area } from "@/lib/evidence";

// S2: size indicator from Yosys (verify/area.py). Rendered only when a stored area.json exists.
// Timing and power live in the SKY130 boxes (S6/S10) when those were measured for this run.
export default function AreaBox({ area, physical = false }: { area: Area; physical?: boolean }) {
  const { final, reference } = area;
  const versions = [...new Set([final.yosys, reference?.yosys].filter(Boolean))].join(" · ");
  return (
    <section className="box" aria-labelledby="area">
      <div className="box-header">
        <h2 id="area">Area (Yosys)</h2>
        <span className="tag-measured">measured</span>
      </div>
      <p className="box-lede">{final.kind}. <span className="mono">synth -top sync_fifo; stat</span> on the final RTL (in the sandbox) and on the hand-written reference.</p>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Design</th><th>Cells</th><th>Flip-flops</th></tr></thead>
          <tbody>
            <tr><td>Final RTL <span className="meta-text mono">{area.runId}</span></td><td>{final.cells}</td><td>{final.flops}</td></tr>
            {reference && <tr><td>Reference RTL <span className="meta-text">hand-written</span></td><td>{reference.cells}</td><td>{reference.flops}</td></tr>}
            {physical ? (
              <tr><td>Timing and power</td><td colSpan={2}><span className="meta-text">measured on SKY130, in the pre-layout and post-layout boxes below</span></td></tr>
            ) : (
              <>
                <tr><td>Timing</td><td colSpan={2}><span className="mark-neutral">○ not measured</span> <span className="meta-text">no STA flow</span></td></tr>
                <tr><td>Power</td><td colSpan={2}><span className="mark-neutral">○ not measured</span> <span className="meta-text">no power flow</span></td></tr>
              </>
            )}
          </tbody>
        </table>
      </div>
      <p className="box-lede meta-text">Tool: <span className="mono">{versions}</span></p>
    </section>
  );
}
