import type { Metadata } from "next";
import PlanView from "@/components/PlanView";
import SiteHeader from "@/components/SiteHeader";
import { planBundle } from "@/lib/evidence";

export const metadata: Metadata = { title: "Reference RTL · Verification plan · DaVINCI Silicon" };

export default function ReferencePlan() {
  const b = planBundle("reference")!;
  return (
    <>
      <SiteHeader active="evidence" crumbs={[{ label: "reference RTL" }, { label: "verification plan" }]} />
      <main className="board plan-page">
        <section className="title-block">
          <p className="eyebrow">Verification plan · hand-written reference RTL (rtl/sync_fifo.v)</p>
          <h1 className="display-title">The plan against the reference design. <span className="tone-2">The same frozen tests, planted bugs and sign-off criteria every generated RTL is held to.</span></h1>
        </section>
        <PlanView plan={b.plan} csv={b.csv} hjson={b.hjson} planId="reference" />
      </main>
    </>
  );
}
