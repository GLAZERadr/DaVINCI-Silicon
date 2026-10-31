import Board from "@/components/Board";
import { board, runList } from "@/lib/evidence";

// The landing page shows the repair story when the bundle has one.
export default function Home() {
  const runs = runList();
  const featured = runs.find((r) => r.seedBug) ?? runs[0];
  return <Board data={board(featured.id)} runs={runs} />;
}
