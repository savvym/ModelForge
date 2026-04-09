import { redirect } from "next/navigation";

export default async function ModelEvalBenchmarksRedirectPage({
  searchParams
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const params = new URLSearchParams();
  params.set("tab", "benchmarks");
  if (resolvedSearchParams.q?.trim()) {
    params.set("q", resolvedSearchParams.q.trim());
  }
  redirect(`/model/eval?${params.toString()}`);
}
