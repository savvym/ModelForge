import { GitCommitHorizontal } from "lucide-react";
import type { LakeRepoCommitSummary } from "@/types/api";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyContent } from "@/components/ui/empty";

export function RepoCommitList({ commits }: { commits: LakeRepoCommitSummary[] }) {
  if (commits.length === 0) {
    return (
      <Empty className="border border-dashed border-border/60 bg-card/60">
        <EmptyHeader>
          <EmptyTitle>还没有 commit</EmptyTitle>
          <EmptyDescription>从「上传文件」开始第一次提交。</EmptyDescription>
        </EmptyHeader>
        <EmptyContent />
      </Empty>
    );
  }
  return (
    <ol className="overflow-hidden rounded-lg border border-border/70 bg-card/60 divide-y divide-border/60">
      {commits.map((commit) => (
        <li key={commit.sha} className="flex items-start gap-3 px-4 py-3">
          <GitCommitHorizontal className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <div className="truncate text-sm text-foreground">{commit.message || commit.sha.slice(0, 7)}</div>
            <div className="text-xs text-muted-foreground">
              <span className="font-mono">{commit.sha.slice(0, 7)}</span>
              {commit.author_name ? ` · ${commit.author_name}` : ""}
              {commit.committed_at ? ` · ${new Date(commit.committed_at).toLocaleString("zh-CN")}` : ""}
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}
