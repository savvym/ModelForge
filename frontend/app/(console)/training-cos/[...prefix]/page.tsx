import { renderBrowser } from "../page";

export default async function TrainingCosPrefixPage({
  params
}: {
  params: Promise<{ prefix: string[] }>;
}) {
  const { prefix } = await params;
  const decoded = prefix.map((segment) => decodeURIComponent(segment)).join("/");
  const normalized = decoded ? `${decoded.replace(/^\/+|\/+$/g, "")}/` : "";
  return renderBrowser(normalized);
}
