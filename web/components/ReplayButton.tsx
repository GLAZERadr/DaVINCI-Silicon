"use client";

import { useState } from "react";

// With NEXT_PUBLIC_DAVINCI_API set, asks the API to replay the run ($0: recorded
// model output, real simulation) and reports the measured result. Without it,
// the static board jumps to the recorded replay in "Reproduce it".
const API = process.env.NEXT_PUBLIC_DAVINCI_API;

export default function ReplayButton({ runId }: { runId: string }) {
  const [state, setState] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function replay() {
    if (!API) {
      document.getElementById("reproduce")?.scrollIntoView({ behavior: "smooth" });
      setState("Showing the recorded replay. Run the command there to replay it yourself.");
      return;
    }
    setBusy(true);
    setState("Queued…");
    try {
      const res = await fetch(`${API}/runs/${encodeURIComponent(runId)}/replay`, { method: "POST" });
      if (!res.ok) throw new Error(`API answered ${res.status}`);
      const { run_id } = await res.json();
      for (let i = 0; i < 150; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const r = await (await fetch(`${API}/runs/${encodeURIComponent(run_id)}`)).json();
        if (r.status && r.attempts) {
          const reproduced = r.replay_check?.reproduced ? "reproduced" : "did not reproduce";
          setState(`Replay ${run_id}: ${r.status} (measured), ${reproduced} the recorded run.`);
          return;
        }
        if (r.state === "done" && r.status === "error") throw new Error(`replay failed: ${r.error ?? "see API logs"}`);
        setState(r.state === "running" ? "Simulating…" : "Queued…");
      }
      setState("Still running; check the API.");
    } catch (e) {
      setState(`Replay not run: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <button type="button" className="btn" onClick={replay} disabled={busy}>
        {busy ? "Replaying…" : "Replay this run"}
      </button>
      {state && <p className="replay-status" role="status">{state}</p>}
    </div>
  );
}
