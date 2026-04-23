import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getBronzeAsset } from "@/features/lake/api";
import { BronzeAssetDetailPanel } from "@/features/lake/components/bronze-asset-detail";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function LakeAssetDetailPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const [{ id }, projectId] = await Promise.all([params, getCurrentProjectIdFromCookie()]);
  const asset = await getBronzeAsset(id, projectId).catch(() => null);

  if (!asset) {
    return (
      <Card className="border-border bg-card/80">
        <CardHeader>
          <CardTitle>Bronze 资产不存在</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 text-sm text-muted-foreground">
          <p>当前资产可能已被删除，或你访问的 ID 不存在。</p>
          <Link className="text-foreground underline-offset-4 hover:underline" href="/lake-assets">
            返回数据湖
          </Link>
        </CardContent>
      </Card>
    );
  }

  return <BronzeAssetDetailPanel asset={asset} />;
}
