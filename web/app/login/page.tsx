import type { Metadata } from "next";
import AuthForm from "@/components/AuthForm";

export const metadata: Metadata = { title: "Sign in · DaVINCI Silicon" };

export default function Page() {
  return <AuthForm mode="login" />;
}
