import { redirect } from "next/navigation";

export default async function ModelWarehousePage({
  searchParams
}: {
  searchParams: Promise<{ panel?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const target =
    resolvedSearchParams.panel === "provider"
      ? "/model-square/provider/new"
      : resolvedSearchParams.panel === "model"
        ? "/model-square/model/new"
        : "/model-square";

  redirect(target);
}
