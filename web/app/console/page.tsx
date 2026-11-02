import type { Metadata } from "next";
import ConsoleIndex from "@/components/ConsoleIndex";
import SiteHeader from "@/components/SiteHeader";
import { defaultRequirements, runList, triage } from "@/lib/evidence";

export const metadata: Metadata = { title: "Run Console · DaVINCI Silicon" };

export default function ConsolePage() {
  return (
    <>
      <SiteHeader active="console" />
      <ConsoleIndex recorded={runList()} requirements={defaultRequirements()} triage={triage()} />
    </>
  );
}
