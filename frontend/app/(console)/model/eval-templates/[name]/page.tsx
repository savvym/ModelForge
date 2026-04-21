import { redirect } from "next/navigation";

export default async function EvalTemplateDetailPage({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  redirect(`/model/eval-templates/${encodeURIComponent(name)}/edit`);
}
