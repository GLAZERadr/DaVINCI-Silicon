import ModelAvatar from "./ModelAvatar";
import type { Json } from "@/lib/run";

// A design breakdown (S1): the model's proposal is AI interpretation (dashed);
// the "in final RTL" column is measured from the run's last simulated RTL.
export default function BreakdownView({ breakdown, model, approvedBy, check }:
  { breakdown: Json; model?: string; approvedBy?: string; check?: Json | null }) {
  const rows = new Map<string, Json>(((check?.elements ?? []) as Json[]).map((r) => [r.name, r]));
  return (
    <div className="bd">
      <div className="tl-comment bd-ai">
        <div className="tl-comment-head">
          <ModelAvatar model={model} />
          <strong>{model ?? "model"}</strong>
          <span className="tag-ai">AI interpretation · not verified</span>
          <span className="meta-text">{approvedBy ? `approved by ${approvedBy} before RTL` : "awaiting approval"}</span>
        </div>
        <p>{breakdown.summary}</p>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Element</th><th>Kind</th><th>Width</th><th>Role</th><th>REQs</th>{check ? <th>In final RTL · measured</th> : null}</tr></thead>
            <tbody>
              {(breakdown.elements as Json[]).map((el) => {
                const r = rows.get(el.name);
                return (
                  <tr key={el.name}>
                    <td className="mono">{el.name}</td>
                    <td>{el.kind}</td>
                    <td className="mono">{el.width}</td>
                    <td>{el.role}</td>
                    <td className="mono">{(el.reqs as string[]).join(", ") || "—"}</td>
                    {check ? (
                      <td>{!r ? <span className="mark-neutral">○ not checked</span>
                        : !r.present ? <span className="mark-fail">✕ not in RTL</span>
                        : r.width === "match" ? <span className="mark-pass">✓ present · {r.width_declared_bits} bit{r.width_declared_bits === 1 ? "" : "s"}</span>
                        : r.width === "differs" ? <span className="mark-fail">✕ width {r.width_declared_bits}, planned {r.width_planned_bits}</span>
                        : <span className="mark-pass">✓ present <span className="meta-text">(width not checked)</span></span>}</td>
                    ) : null}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <dl className="side-facts bd-facts">
          <dt>Pointers</dt><dd>{breakdown.pointer_scheme || "—"}</dd>
          <dt>FSM</dt><dd>{(breakdown.fsm_states as Json[]).length ? (breakdown.fsm_states as Json[]).map((s) => `${s.name}: ${s.meaning}`).join(" · ") : "none"}</dd>
          <dt>Control</dt><dd>{(breakdown.control as string[]).join(" · ") || "—"}</dd>
          <dt>Datapath</dt><dd>{(breakdown.datapath as string[]).join(" · ") || "—"}</dd>
          <dt>Timing</dt><dd>{(breakdown.timing_assumptions as string[]).join(" · ") || "—"}</dd>
        </dl>
      </div>
      {check ? (
        <p className={`measured ${check.missing.length || check.width_differs.length ? "fail" : "pass"}`}>
          <span className="label">Measured · final RTL (attempt {check.attempt})</span>
          {check.present}/{check.total} elements in the final RTL · {check.width_match} widths match
          {check.width_differs.length ? ` · width differs: ${check.width_differs.join(", ")}` : ""}
          {check.missing.length ? ` · missing: ${check.missing.join(", ")}` : ""}
          {" · "}requirements with no element: {check.reqs_without_element.join(", ") || "none"}
        </p>
      ) : null}
    </div>
  );
}
