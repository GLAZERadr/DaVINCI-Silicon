import { planFiles, planText } from "@/lib/evidence";

// Static files at export time: /plans/<run id>.md | .json | .csv | .hjson.
export const dynamic = "force-static";

export function generateStaticParams() {
  return planFiles().map((file) => ({ file }));
}

export async function GET(_req: Request, { params }: { params: Promise<{ file: string }> }) {
  const { file } = await params;
  const ext = file.split(".").pop()!;
  const type = { json: "application/json", csv: "text/csv", hjson: "text/plain", md: "text/markdown" }[ext] ?? "text/plain";
  return new Response(planText(file), { headers: { "content-type": `${type}; charset=utf-8` } });
}
