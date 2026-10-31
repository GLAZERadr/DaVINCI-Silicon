import { traceFiles, traceText } from "@/lib/evidence";

// Static files at export time: /traces/<run id>__<attempt>.json (verify/trace.py output).
export const dynamic = "force-static";

export function generateStaticParams() {
  return traceFiles().map((file) => ({ file }));
}

export async function GET(_req: Request, { params }: { params: Promise<{ file: string }> }) {
  const { file } = await params;
  return new Response(traceText(file), { headers: { "content-type": "application/json; charset=utf-8" } });
}
