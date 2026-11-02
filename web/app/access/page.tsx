import type { Metadata } from "next";
import AccessRequest from "@/components/AccessRequest";
import SiteHeader from "@/components/SiteHeader";

export const metadata: Metadata = { title: "Request access · DaVINCI Silicon" };

export default function AccessPage() {
  return (
    <>
      <SiteHeader crumbs={[{ label: "request access" }]} />
      <AccessRequest />
    </>
  );
}
