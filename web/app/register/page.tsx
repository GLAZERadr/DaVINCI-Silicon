import type { Metadata } from "next";
import AuthForm from "@/components/AuthForm";

export const metadata: Metadata = { title: "Create account · DaVINCI Silicon" };

export default function Page() {
  return <AuthForm mode="register" />;
}
