import type { Metadata } from "next";
import SiteHeader from "@/components/SiteHeader";
import SpecIntake from "@/components/SpecIntake";

export const metadata: Metadata = { title: "Spec intake · DaVINCI Silicon" };

export default function SpecPage() {
  return (
    <>
      <SiteHeader active="spec" />
      <SpecIntake />
    </>
  );
}
