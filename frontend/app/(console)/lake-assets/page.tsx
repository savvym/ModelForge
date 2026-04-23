import { getBronzeAssets, getBronzeJobs } from "@/features/lake/api";
import { LakeAssetManager } from "@/features/lake/components/lake-asset-manager";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function LakeAssetsPage() {
  const projectId = await getCurrentProjectIdFromCookie();
  const [assets, jobs] = await Promise.all([
    getBronzeAssets(projectId).catch(() => []),
    getBronzeJobs(projectId).catch(() => [])
  ]);

  return <LakeAssetManager assets={assets} jobs={jobs} />;
}
