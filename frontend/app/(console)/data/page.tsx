import { ObjectStoreConsole } from "@/features/object-store/components/object-store-console";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function DataPage({
  searchParams
}: {
  searchParams: Promise<{ bucket?: string; prefix?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const projectId = await getCurrentProjectIdFromCookie();
  const rootPrefix = projectId ? `projects/${projectId}/lake/` : undefined;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ObjectStoreConsole
        initialBucket={resolvedSearchParams.bucket}
        initialPrefix={resolvedSearchParams.prefix ?? rootPrefix}
        mode="data"
        rootPrefix={rootPrefix}
      />
    </div>
  );
}
