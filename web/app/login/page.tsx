import type { Metadata } from "next";
import AuthForm from "@/components/AuthForm";
import SiteHeader from "@/components/SiteHeader";

export const metadata: Metadata = { title: "Sign in · DaVINCI Silicon" };

export default function LoginPage() {
  return (
    <>
      <SiteHeader crumbs={[{ label: "sign in" }]} />
      <AuthForm mode="login" />
    </>
  );
}
