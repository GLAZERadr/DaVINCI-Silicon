import type { Metadata } from "next";
import Board from "@/components/Board";
import { board, runList } from "@/lib/evidence";

export const metadata: Metadata = { title: "Evidence · DaVINCI Silicon" };

// The board opens on the repair story when the bundle has one.
export default function EvidencePage() {
  const runs = runList();
  const featured = runs.find((r) => r.seedBug) ?? runs[0];
  return <Board data={board(featured.id)} runs={runs} />;
}
