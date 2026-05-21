import { renderTrainingCosBrowser } from "@/features/training-cos/components/browser-page";

export default async function TrainingCosPrefixPage({
  params
}: {
  params: Promise<{ prefix: string[] }>;
}) {
  const { prefix } = await params;
  const decoded = prefix.map((segment) => decodeURIComponent(segment)).join("/");
  const normalized = decoded ? `${decoded.replace(/^\/+|\/+$/g, "")}/` : "";
  return renderTrainingCosBrowser(normalized);
}
