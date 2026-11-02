// Build-time reader for learn/<block>/REQ-xx.json (agent/learn.py). The Learn view
// shows these stored files; it never calls a model at view time.
import fs from "node:fs";
import path from "node:path";
import type { LearnItem } from "@/components/LearnView";

const ROOT = path.resolve(process.cwd(), "..", "learn");

export function learnItems(block = "sync_fifo"): Record<string, LearnItem> {
  const dir = path.join(ROOT, block);
  if (!fs.existsSync(dir)) return {};
  const out: Record<string, LearnItem> = {};
  for (const f of fs.readdirSync(dir).filter((n) => /^REQ-\d+\.json$/.test(n)).sort()) {
    const d = JSON.parse(fs.readFileSync(path.join(dir, f), "utf8"));
    out[d.id] = {
      id: d.id, requirement: d.requirement, test: d.test, label: d.label, provider: d.provider, model: d.model,
      costUsd: d.cost_usd, requestSha: d.request_sha256, content: d.content, check: d.check,
    };
  }
  return out;
}
