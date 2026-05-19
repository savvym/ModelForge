"use client";

import { Copy, ExternalLink, GitBranch, GitCommitHorizontal } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { LakeRepoDetail } from "@/types/api";

export function RepoHeader({ repo }: { repo: LakeRepoDetail }) {
  function copyClone() {
    if (!repo.clone_url) return;
    navigator.clipboard.writeText(repo.clone_url).then(
      () => toast.success("克隆地址已复制"),
      () => toast.error("复制失败")
    );
  }

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
            数据湖 · {repo.gitea_org}
          </div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <span className="text-muted-foreground">{repo.gitea_org}</span>
            <span className="text-muted-foreground">/</span>
            <span>{repo.name}</span>
            <Badge variant="outline" className="ml-2 text-xs">
              {repo.visibility}
            </Badge>
          </h1>
          {repo.description ? (
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">{repo.description}</p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {repo.clone_url ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button size="sm" variant="outline" onClick={copyClone}>
                  <Copy className="mr-2 size-4" />
                  复制克隆地址
                </Button>
              </TooltipTrigger>
              <TooltipContent>{repo.clone_url}</TooltipContent>
            </Tooltip>
          ) : null}
          {repo.web_url ? (
            <a
              href={repo.web_url}
              target="_blank"
              rel="noreferrer"
              className={buttonVariants({ size: "sm", variant: "outline" })}
            >
              <ExternalLink className="mr-2 size-4" />
              Gitea 页面
            </a>
          ) : null}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <div className="inline-flex items-center gap-1.5">
          <GitBranch className="size-4" /> {repo.default_branch}
        </div>
        {repo.last_commit ? (
          <div className="inline-flex items-center gap-1.5">
            <GitCommitHorizontal className="size-4" />
            <span className="max-w-[480px] truncate">{repo.last_commit.message || repo.last_commit.sha.slice(0, 7)}</span>
            <span className="text-muted-foreground/70">
              · {repo.last_commit.author_name}
            </span>
          </div>
        ) : repo.empty ? (
          <Badge variant="outline" className="text-xs">空仓库</Badge>
        ) : null}
      </div>
    </section>
  );
}
