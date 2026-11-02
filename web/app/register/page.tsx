import type { Metadata } from "next";
import AuthForm from "@/components/AuthForm";
import SiteHeader from "@/components/SiteHeader";

export const metadata: Metadata = { title: "Create account · DaVINCI Silicon" };

export default function RegisterPage() {
  return (
    <>
      <SiteHeader crumbs={[{ label: "create account" }]} />
      <AuthForm mode="register" />
    </>
  );
}
