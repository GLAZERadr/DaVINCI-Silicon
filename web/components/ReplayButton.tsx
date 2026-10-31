"use client";

import Link from "next/link";
import { useState } from "react";
import { apiBase } from "@/lib/api";

// With an API configured (NEXT_PUBLIC_DAVINCI_API or Connection settings), asks it
// to replay the run ($0: recorded model output, real simulation) and reports the
// measured result. Without one, the static board jumps to the recorded replay.

export default function ReplayButton({ runId }: { runId: string }) {
  const [state, setState] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  async function replay() {
    const API = apiBase();
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
          setDone(run_id);
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
      <button type="button" className="btn btn-sm" onClick={replay} disabled={busy}>
        {busy ? "Replaying…" : "Replay this run"}
      </button>
      {state && <p className="replay-status" role="status">{state}{done && <> <Link href={`/console/?run=${encodeURIComponent(done)}`}>Open in Run Console</Link></>}</p>}
    </div>
  );
}
