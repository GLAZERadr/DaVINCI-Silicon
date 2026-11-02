import type { Metadata } from "next";
import NewRun from "@/components/NewRun";
import SiteHeader from "@/components/SiteHeader";
import { mutants, runList } from "@/lib/evidence";

export const metadata: Metadata = { title: "New run · DaVINCI Silicon" };

export default function NewRunPage() {
  return (
    <>
      <SiteHeader active="new" />
      <NewRun mutants={mutants()} recorded={runList().map((r) => r.id)} />
    </>
  );
}
