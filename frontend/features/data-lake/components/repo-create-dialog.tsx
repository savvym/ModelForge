"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { createRepo } from "@/features/data-lake/api";

const NAME_RE = /^[a-z0-9][a-z0-9._-]{0,62}[a-z0-9]$|^[a-z0-9]$/;

export function RepoCreateDialog() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = name.trim().toLowerCase();
    if (!NAME_RE.test(normalized)) {
      toast.error("仓库名只能包含小写字母、数字、点、下划线和连字符，且首尾必须是字母或数字。");
      return;
    }
    setSubmitting(true);
    try {
      const repo = await createRepo({
        name: normalized,
        display_name: displayName.trim() || normalized,
        description: description.trim() || null
      });
      toast.success(`仓库「${repo.display_name}」已创建`);
      setOpen(false);
      setName("");
      setDisplayName("");
      setDescription("");
      router.refresh();
      router.push(`/data-lake/${repo.id}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "创建失败";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">新建仓库</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[480px]">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>新建数据湖仓库</DialogTitle>
            <DialogDescription>
              仓库会创建在当前项目下，底层托管在 Gitea，支持 md、图片和大文件 LFS。
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="repo-name">仓库名</Label>
              <Input
                id="repo-name"
                placeholder="my-dataset"
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
              />
              <p className="text-xs text-muted-foreground">
                只能小写字母、数字、点 .、下划线 _、连字符 -，2-64 字符。
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="repo-display-name">显示名称（可选）</Label>
              <Input
                id="repo-display-name"
                placeholder="My Dataset"
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="repo-description">描述（可选）</Label>
              <Textarea
                id="repo-description"
                placeholder="这个仓库是做什么的？"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)} disabled={submitting}>
              取消
            </Button>
            <Button type="submit" disabled={submitting || !name.trim()}>
              {submitting ? "创建中…" : "创建仓库"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
