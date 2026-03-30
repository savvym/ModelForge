import { getLakeAssets, getLakeBatches } from "@/features/lake/api";
import { LakeAssetManager } from "@/features/lake/components/lake-asset-manager";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function LakeAssetsPage() {
  const projectId = await getCurrentProjectIdFromCookie();
  const [assets, batches] = await Promise.all([
    getLakeAssets({ stage: "raw", projectId }).catch(() => []),
    getLakeBatches(projectId).catch(() => [])
  ]);

  return <LakeAssetManager assets={assets} batches={batches} />;
}
