"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, RefreshCcw, Search, Trash2 } from "lucide-react";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import {
  ConsoleListHeader,
  consoleListSearchInputClassName,
  ConsoleListTableSurface,
  ConsoleListToolbar,
  ConsoleListToolbarCluster
} from "@/components/console/list-surface";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { CURRENT_PROJECT_COOKIE } from "@/features/project/constants";
import { createProject, deleteProject } from "@/features/project/api";
import type { ProjectCreateInput, ProjectSummary } from "@/types/api";
import { cn } from "@/lib/utils";

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    hour12: false
  });
}

function canDeleteProject(project: ProjectSummary) {
  return !project.is_default && project.resource_count === 0;
}

export function ProjectManagementConsole({
  initialProjects,
  currentProjectId
}: {
  initialProjects: ProjectSummary[];
  currentProjectId: string | null;
}) {
  const router = useRouter();
  const [projects, setProjects] = useState(initialProjects);
  const [keyword, setKeyword] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProjectSummary | null>(null);
  const [form, setForm] = useState<ProjectCreateInput>({
    code: "",
    name: "",
    description: ""
  });

  const filteredProjects = useMemo(() => {
    const normalized = keyword.trim().toLowerCase();
    if (!normalized) {
      return projects;
    }

    return projects.filter((project) =>
      [project.code, project.name, project.description ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(normalized)
    );
  }, [keyword, projects]);

  async function handleCreateProject() {
    setPending(true);
    setError(null);
    try {
      const created = await createProject(form);
      setProjects((current) =>
        [...current, created].sort((left, right) =>
          new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
        )
      );
      setCreateOpen(false);
      setForm({ code: "", name: "", description: "" });
      router.refresh();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "创建项目失败。");
    } finally {
      setPending(false);
    }
  }

  async function handleDeleteProject() {
    if (!deleteTarget) {
      return;
    }

    setPending(true);
    setError(null);
    try {
      await deleteProject(deleteTarget.id);
      setProjects((current) => current.filter((project) => project.id !== deleteTarget.id));
      if (currentProjectId === deleteTarget.id) {
        const defaultProject = projects.find((project) => project.is_default);
        if (defaultProject) {
          document.cookie = `${CURRENT_PROJECT_COOKIE}=${encodeURIComponent(defaultProject.id)}; Path=/; Max-Age=${60 * 60 * 24 * 365}; SameSite=Lax`;
        }
      }
      setDeleteTarget(null);
      router.refresh();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "删除项目失败。");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-4">
      <ConsoleListHeader title="项目配置" />

      <ConsoleListToolbar className="justify-start">
        <div className="relative min-w-[260px] flex-1 max-w-[420px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            className={consoleListSearchInputClassName}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="Find project"
            value={keyword}
          />
        </div>

        <ConsoleListToolbarCluster>
          <Button onClick={() => router.refresh()} size="sm" type="button" variant="outline">
            <RefreshCcw className="mr-2 h-4 w-4" />
            刷新
          </Button>
          <Button onClick={() => setCreateOpen(true)} size="sm" type="button">
            <Plus className="mr-2 h-4 w-4" />
            新建项目
          </Button>
        </ConsoleListToolbarCluster>
      </ConsoleListToolbar>

      {error ? (
        <div className="rounded-lg border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      <ConsoleListTableSurface>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader className="bg-transparent">
              <TableRow className="hover:bg-transparent">
                <TableHead className="min-w-[180px]">项目名称</TableHead>
                <TableHead className="min-w-[180px]">显示名称</TableHead>
                <TableHead className="min-w-[220px]">备注</TableHead>
                <TableHead className="min-w-[120px]">资源数量</TableHead>
                <TableHead className="min-w-[120px]">授权数</TableHead>
                <TableHead className="min-w-[180px]">创建时间</TableHead>
                <TableHead className="min-w-[180px]">更新时间</TableHead>
                <TableHead className="min-w-[160px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredProjects.length ? (
                filteredProjects.map((project) => {
                  const isCurrent = currentProjectId === project.id;
                  const deletable = canDeleteProject(project);
                  return (
                    <TableRow key={project.id}>
                      <TableCell className="font-medium text-foreground">
                        <div className="flex items-center gap-2">
                          <span>{project.code}</span>
                          {isCurrent ? (
                            <span className="rounded-full border border-border bg-muted/60 px-2 py-0.5 text-[11px] uppercase tracking-[0.12em] text-foreground">
                              当前
                            </span>
                          ) : null}
                        </div>
                      </TableCell>
                      <TableCell>{project.name}</TableCell>
                      <TableCell className="text-muted-foreground">{project.description || "-"}</TableCell>
                      <TableCell>{project.resource_count}</TableCell>
                      <TableCell>{project.member_count}</TableCell>
                      <TableCell>{formatDateTime(project.created_at)}</TableCell>
                      <TableCell>{formatDateTime(project.updated_at)}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-3 text-[13px]">
                          {!isCurrent ? (
                            <button
                              className="text-foreground transition-colors hover:text-primary"
                              onClick={() => {
                                document.cookie = `${CURRENT_PROJECT_COOKIE}=${encodeURIComponent(project.id)}; Path=/; Max-Age=${60 * 60 * 24 * 365}; SameSite=Lax`;
                                router.refresh();
                              }}
                              type="button"
                            >
                              切换
                            </button>
                          ) : null}
                          <button
                            className={cn(
                              "inline-flex items-center gap-1 transition-colors",
                              deletable
                                ? "text-destructive hover:text-destructive"
                                : "cursor-not-allowed text-foreground"
                            )}
                            disabled={!deletable}
                            onClick={() => setDeleteTarget(project)}
                            title={
                              project.is_default
                                ? "default 项目不能删除"
                                : project.resource_count > 0
                                  ? "请先清理项目下资源后再删除"
                                  : "删除项目"
                            }
                            type="button"
                          >
                            <Trash2 className="h-4 w-4" />
                            删除
                          </button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })
              ) : (
                <TableRow>
                  <TableCell className="py-12 text-center text-sm text-muted-foreground" colSpan={8}>
                    暂无符合条件的项目。
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </ConsoleListTableSurface>

      <Sheet onOpenChange={setCreateOpen} open={createOpen}>
        <SheetContent className="w-full gap-0 overflow-hidden border-l border-border bg-card px-0 py-0 text-foreground shadow-[-30px_0_70px_rgba(2,6,23,0.6)] sm:max-w-xl [&>button]:right-4 [&>button]:top-4 [&>button]:rounded-md [&>button]:text-muted-foreground [&>button]:hover:bg-card/80 [&>button]:hover:text-foreground">
          <SheetHeader className="gap-3 border-b border-border bg-card px-6 pb-5 pt-6 pr-12 sm:px-7">
            <div className="inline-flex w-fit items-center rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.18em] text-primary/90">
              Project Scope
            </div>
            <SheetTitle className="text-[22px] font-semibold tracking-[0.01em] text-foreground">
              新建项目
            </SheetTitle>
            <SheetDescription className="max-w-[32rem] text-sm leading-6 text-muted-foreground">
              创建后，数据集、模型、评测任务和文件资产都会在项目维度隔离。
            </SheetDescription>
          </SheetHeader>

          <div className="space-y-5 px-6 py-6 sm:px-7">
            <div className="grid gap-3 rounded-[22px] border border-border bg-card/80 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
              <div className="text-[12px] uppercase tracking-[0.16em] text-muted-foreground">
                Naming
              </div>
              <div className="text-sm leading-6 text-foreground">
                项目编码用于系统内识别和路径分组，建议保持简短、稳定、可读。
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-foreground" htmlFor="project-code">
                项目名称
              </Label>
              <Input
                id="project-code"
                onChange={(event) =>
                  setForm((current) => ({ ...current, code: event.target.value }))
                }
                placeholder="例如：team-alpha"
                value={form.code}
              />
              <div className="text-xs text-muted-foreground">仅支持小写字母、数字和连字符。</div>
            </div>

            <div className="space-y-2">
              <Label className="text-foreground" htmlFor="project-name">
                显示名称
              </Label>
              <Input
                id="project-name"
                onChange={(event) =>
                  setForm((current) => ({ ...current, name: event.target.value }))
                }
                placeholder="例如：Alpha 项目"
                value={form.name}
              />
            </div>

            <div className="space-y-2">
              <Label className="text-foreground" htmlFor="project-description">
                备注
              </Label>
              <Textarea
                id="project-description"
                onChange={(event) =>
                  setForm((current) => ({ ...current, description: event.target.value }))
                }
                placeholder="填写项目说明或隔离范围"
                rows={4}
                value={form.description ?? ""}
              />
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-border pt-5">
              <Button
                className="h-9 rounded-full border-border px-4 text-foreground hover:border-border hover:bg-card/80"
                onClick={() => setCreateOpen(false)}
                type="button"
                variant="outline"
              >
                取消
              </Button>
              <Button
                className="h-9 rounded-full px-4"
                disabled={pending || !form.code.trim() || !form.name.trim()}
                onClick={handleCreateProject}
                type="button"
              >
                {pending ? "创建中..." : "新建项目"}
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>

      <AlertDialog onOpenChange={(open) => !open && setDeleteTarget(null)} open={!!deleteTarget}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除项目</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget
                ? `确认删除项目 ${deleteTarget.name}（${deleteTarget.code}）？此操作不会自动迁移项目资源。`
                : ""}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleDeleteProject}
            >
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
