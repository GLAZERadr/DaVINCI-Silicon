import type { Metadata } from "next";
import AccountView from "@/components/AccountView";
import SiteHeader from "@/components/SiteHeader";

export const metadata: Metadata = { title: "Your account · DaVINCI Silicon" };

export default function AccountPage() {
  return (
    <>
      <SiteHeader crumbs={[{ label: "account" }]} />
      <AccountView />
    </>
  );
}
