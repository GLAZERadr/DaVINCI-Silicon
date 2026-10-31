import { planFiles, planText } from "@/lib/evidence";

// Static files at export time: /plans/<run id>.md and /plans/<run id>.json.
export const dynamic = "force-static";

export function generateStaticParams() {
  return planFiles().map((file) => ({ file }));
}

export async function GET(_req: Request, { params }: { params: Promise<{ file: string }> }) {
  const { file } = await params;
  const type = file.endsWith(".json") ? "application/json" : "text/markdown";
  return new Response(planText(file), { headers: { "content-type": `${type}; charset=utf-8` } });
}
