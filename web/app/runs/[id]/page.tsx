import type { Metadata } from "next";
import Board from "@/components/Board";
import { board, runList } from "@/lib/evidence";

export function generateStaticParams() {
  return runList().map((r) => ({ id: r.id }));
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  return { title: `${id} · DaVINCI Evidence Board` };
}

export default async function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <Board data={board(id)} runs={runList()} />;
}
