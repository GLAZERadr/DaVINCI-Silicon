// Formal checks (S5 bounded, S9 unbounded) from verify/formal.py: measured
// SymbiYosys results on the run's final RTL and on the reference RTL. A
// bounded result is never shown as a proof. Renders only when data exists.
import type { Json } from "@/lib/evidence";

type Prop = { id: string; text: string; result: string; bounded: string; bmc: Json; prove: Json[] };

function Result({ p, depth }: { p: Prop | undefined; depth: number }) {
  if (!p) return <span className="mark-neutral">○ Not run</span>;
  if (p.result === "proved") {
    const engine = p.prove[p.prove.length - 1]?.engine ?? "";
    return <span className="mark-pass" title={engine}>✓ Proved (unbounded)</span>;
  }
  if (p.result === "bounded") return <span className="mark-neutral">○ Bounded only · holds {depth} cycles</span>;
  if (p.result === "failed") {
    const step = p.bmc?.cex_step;
    return <span className="mark-fail">✕ Failed{step != null ? ` at step ${step}` : ""} · counterexample stored</span>;
  }
  return <span className="mark-neutral">○ No result</span>;
}

export default function FormalPanel({ run, reference }: { run: Json | null; reference: Json | null }) {
  const main = run ?? reference;
  if (!main) return null;
  const depth: number = main.depth;
  const props: Prop[] = main.properties;
  const byId = (rep: Json | null, id: string) => (rep?.properties as Prop[] | undefined)?.find((p) => p.id === id);
  const muts = reference?.mutants;
  const tools = main.tools ?? {};
  return (
    <section className="box" aria-labelledby="formal">
      <div className="box-header">
        <h2 id="formal">Formal checks (SymbiYosys)</h2>
        <span className="meta-text">
          Bounded formal: {main.bmc_holding} of {props.length} properties hold for {depth} cycles
          {" · "}{main.proved} proved (unbounded) · <span className="tag-measured">measured</span>
        </span>
      </div>
      <p className="box-lede">
        Hand-written properties on the ports only (frozen, never shown to the model), checked inside the
        sandbox: bounded model check to depth {depth}, then an unbounded attempt (k-induction, then abc pdr).
        A property is marked proved only when the prover returned PASS. Reset is assumed in the first cycle;
        all other inputs are free. Data ordering is covered by simulation, not by these properties.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Property</th>
              {run && <th>Final RTL (attempt {run.attempt ?? "?"})</th>}
              {reference && <th>Reference RTL</th>}
            </tr>
          </thead>
          <tbody>
            {props.map((p) => (
              <tr key={p.id}>
                <td><span className="mono">{p.id.split("_")[0]}</span> {p.text}</td>
                {run && <td><Result p={byId(run, p.id)} depth={depth} /></td>}
                {reference && <td><Result p={byId(reference, p.id)} depth={depth} /></td>}
              </tr>
            ))}
            {muts && (
              <tr>
                <td>Planted bugs these properties catch <span className="meta-text">hand-written mutants of the reference RTL</span></td>
                <td colSpan={(run ? 1 : 0) + 1}>
                  <span className={muts.caught > 0 ? "mark-pass" : "mark-neutral"}>{muts.caught > 0 ? "✓" : "○"} {muts.caught}/{muts.injected} caught</span>{" "}
                  <span className="meta-text">
                    {(muts.mutants as Json[]).filter((m) => m.result === "caught")
                      .map((m) => `${m.id} (${(m.failed_properties as string[]).map((f) => f.split("_")[0]).join(", ")})`).join(" · ")}
                    {muts.caught < muts.injected && ` · not caught by these properties: ${(muts.mutants as Json[])
                      .filter((m) => m.result === "not caught").map((m) => m.id).join(", ")} (flags and data no property states)`}
                  </span>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="box-footer">
        <span className="meta-text">{[tools.yosys?.split(" (")[0], tools.sby, tools.z3, "yosys-abc"].filter(Boolean).join(" · ")}</span>
        <span className="meta-text mono">props {String(main.props_sha256 ?? "").slice(0, 12)}</span>
      </div>
    </section>
  );
}
