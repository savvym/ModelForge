"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { startTransition, useEffect, useState } from "react";
import {
  Bot,
  Boxes,
  ClipboardCheck,
  CircleHelp,
  Database,
  HardDrive,
  FolderCog,
  Gauge,
  LayoutDashboard,
  Library,
  type LucideIcon,
  PanelLeftClose,
  PanelLeftOpen,
  Rocket,
  Search,
  Sparkles,
  SquareArrowOutUpRight,
  UserCircle2,
  WandSparkles
} from "lucide-react";
import { CURRENT_PROJECT_COOKIE } from "@/features/project/constants";
import type { ProjectSummary } from "@/types/api";
import { cn } from "@/lib/utils";
import { consoleNavSections } from "@/lib/console-navigation";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger
} from "@/components/ui/select";

export function ConsoleShell({
  children,
  projects,
  currentProjectId
}: {
  children: React.ReactNode;
  projects: ProjectSummary[];
  currentProjectId: string | null;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [isNavCollapsed, setIsNavCollapsed] = useState(false);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(currentProjectId);
  const isFilesPage = pathname === "/files" || pathname.startsWith("/files/");
  const isCustomWorkbenchPage =
    pathname === "/experience" ||
    pathname === "/dataset-create" ||
    /^\/dataset\/[^/]+$/.test(pathname) ||
    /^\/dataset\/[^/]+\/new-version$/.test(pathname);

  const activeProject =
    projects.find((project) => project.id === selectedProjectId) ??
    projects.find((project) => project.is_default) ??
    projects[0] ??
    null;

  useEffect(() => {
    setSelectedProjectId(currentProjectId);
  }, [currentProjectId]);

  useEffect(() => {
    if (!activeProject) {
      return;
    }
    if (selectedProjectId && activeProject.id === selectedProjectId) {
      return;
    }
    document.cookie = `${CURRENT_PROJECT_COOKIE}=${encodeURIComponent(activeProject.id)}; Path=/; Max-Age=${60 * 60 * 24 * 365}; SameSite=Lax`;
  }, [activeProject, selectedProjectId]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const prefetchConsoleRoutes = () => {
      startTransition(() => {
        for (const href of navPrefetchTargets) {
          if (href !== pathname) {
            router.prefetch(href);
          }
        }
      });
    };

    const browserWindow = window as Window &
      typeof globalThis & {
        requestIdleCallback?: (
          callback: IdleRequestCallback,
          options?: IdleRequestOptions
        ) => number;
        cancelIdleCallback?: (handle: number) => void;
      };

    if (
      typeof browserWindow.requestIdleCallback === "function" &&
      typeof browserWindow.cancelIdleCallback === "function"
    ) {
      const idleId = browserWindow.requestIdleCallback(() => {
        prefetchConsoleRoutes();
      }, { timeout: 1200 });
      return () => browserWindow.cancelIdleCallback?.(idleId);
    }

    const timeoutId = browserWindow.setTimeout(() => {
      prefetchConsoleRoutes();
    }, 120);
    return () => browserWindow.clearTimeout(timeoutId);
  }, [pathname, router]);

  function handleProjectChange(projectId: string) {
    document.cookie = `${CURRENT_PROJECT_COOKIE}=${encodeURIComponent(projectId)}; Path=/; Max-Age=${60 * 60 * 24 * 365}; SameSite=Lax`;
    setSelectedProjectId(projectId);
    router.refresh();
  }

  return (
    <div
      className={cn(
        "console-shell grid h-dvh min-h-0 grid-cols-1 grid-rows-[46px_minmax(0,1fr)] overflow-hidden",
        isNavCollapsed ? "md:grid-cols-[72px_minmax(0,1fr)]" : "md:grid-cols-[232px_minmax(0,1fr)]"
      )}
    >
      <div className="col-span-full flex items-center gap-3 border-b border-slate-800/80 bg-[rgba(9,13,19,0.94)] px-3 backdrop-blur-xl">
        <div className="flex min-w-0 items-center gap-1.5">
          <button
            aria-label={isNavCollapsed ? "展开导航栏" : "收起导航栏"}
            className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-transparent text-slate-500 transition-colors hover:border-slate-700/80 hover:bg-slate-800/45 hover:text-slate-100"
            onClick={() => setIsNavCollapsed((current) => !current)}
            title={isNavCollapsed ? "展开导航栏" : "收起导航栏"}
            type="button"
          >
            {isNavCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>
          <ConsoleNavLink
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-transparent bg-transparent text-teal-300/80 transition-colors hover:border-slate-700/80 hover:bg-slate-800/40 hover:text-teal-200"
            href="/overview"
            title="返回概览"
          >
            <Boxes className="h-4 w-4" />
          </ConsoleNavLink>

          {projects.length ? (
            <div className="header-project-group min-w-0 rounded-xl border border-transparent bg-transparent transition-colors hover:border-slate-700/80 hover:bg-slate-800/40 focus-within:border-slate-700/80 focus-within:bg-slate-800/40">
              <Select
                onValueChange={handleProjectChange}
                value={activeProject?.id ?? undefined}
              >
                <SelectTrigger className="h-8 w-auto min-w-[124px] max-w-[280px] justify-start gap-1 rounded-xl !border-transparent !bg-transparent pl-2 pr-1.5 text-sm text-slate-100 shadow-none hover:!border-transparent hover:!bg-transparent focus:!border-transparent focus:ring-0 data-[state=open]:!border-transparent data-[state=open]:!bg-transparent [&>span]:flex-none [&>span]:max-w-[220px]">
                  <span className="truncate text-left text-sm font-medium text-slate-200">
                    {activeProject?.name ?? "default"}
                  </span>
                </SelectTrigger>
                <SelectContent align="start">
                  {projects.map((project) => (
                    <SelectItem key={project.id} value={project.id}>
                      {project.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <div className="rounded-xl border border-transparent bg-transparent px-2 text-sm font-medium text-slate-200">
              {activeProject?.name ?? "default"}
            </div>
          )}
        </div>

        <div className="hidden min-w-0 flex-1 md:block">
          <div className="relative mx-auto max-w-3xl">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
            <Input
              className="h-8 rounded-full border-slate-700 bg-[#0f141b] pl-9 text-sm"
              placeholder="Search data, files, and models..."
              readOnly
              value=""
            />
          </div>
        </div>

        <div className="ml-auto flex items-center gap-1.5">
          <HeaderIconButton icon={CircleHelp} label="帮助" />
          <HeaderIconButton icon={SquareArrowOutUpRight} label="打开新窗口" />
          <HeaderIconButton icon={UserCircle2} label="账户" />
        </div>
      </div>

      <aside className="row-start-2 flex min-h-0 flex-col overflow-hidden bg-transparent">
        <div
          className={cn(
            "min-h-0 flex-1 overflow-x-visible overflow-y-auto px-2",
            isNavCollapsed ? "py-2" : "py-3"
          )}
        >
          {isNavCollapsed ? (
            <nav className="space-y-3 py-1">
              {consoleNavSections.map((section, index) => (
                <div
                  className={cn("space-y-1", index > 0 && "border-t border-slate-900/70 pt-3")}
                  key={section.id}
                >
                  {section.items.map((item) => {
                    const active = isNavItemActive(pathname, item.href);
                    const Icon = iconByHref[item.href] ?? LayoutDashboard;

                    return (
                      <ConsoleNavLink
                        aria-label={item.title}
                        className={cn(
                          "group relative flex h-8 items-center justify-center rounded-md text-slate-300 transition-colors hover:bg-slate-800/70 hover:text-white",
                          active && "bg-slate-800/90 text-white"
                        )}
                        href={item.href}
                        key={item.href}
                        title={item.title}
                      >
                        <Icon className={cn("h-4 w-4 shrink-0", active && "text-sky-300")} />
                        <span className="pointer-events-none absolute left-full top-1/2 z-20 ml-2 hidden -translate-y-1/2 whitespace-nowrap rounded-md border border-slate-700 bg-[#111923] px-2 py-1 text-xs font-medium text-slate-200 shadow-lg group-hover:block">
                          {item.title}
                        </span>
                      </ConsoleNavLink>
                    );
                  })}
                </div>
              ))}
            </nav>
          ) : (
            <nav className="space-y-4">
              {consoleNavSections.map((section) => (
                <div key={section.id}>
                  <div className="px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                    {section.title}
                  </div>

                  <div className="mt-1 space-y-0.5">
                    {section.items.map((item) => {
                      const active = isNavItemActive(pathname, item.href);
                      const Icon = iconByHref[item.href] ?? LayoutDashboard;

                      return (
                        <ConsoleNavLink
                          key={item.href}
                          href={item.href}
                          className={cn(
                            "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] text-slate-200 transition-colors hover:bg-slate-800/75 hover:text-white",
                            active && "bg-[linear-gradient(180deg,rgba(25,37,53,0.98),rgba(17,26,37,0.98))] font-medium text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]"
                          )}
                        >
                          <Icon className={cn("h-4 w-4 shrink-0 text-slate-400", active && "text-sky-300")} />
                          <span className="truncate">{item.title}</span>
                        </ConsoleNavLink>
                      );
                    })}
                  </div>
                </div>
              ))}
            </nav>
          )}
        </div>
      </aside>

      <main className="row-start-2 min-h-0 bg-transparent">
        <div className="flex h-full min-h-0 flex-col">
          <div
            className={cn(
              "min-h-0 flex-1 bg-transparent",
              isFilesPage ? "overflow-hidden pb-0 pl-3 pr-0 pt-2.5" : "overflow-hidden pb-0 pl-4 pr-0 pt-3"
            )}
          >
            {isFilesPage || isCustomWorkbenchPage ? (
              children
            ) : (
              <div className="console-workbench h-full min-h-0">
                <div className="console-workbench__scroll h-full min-h-0 overflow-y-auto px-5 py-4 pb-12">
                  {children}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

const iconByHref: Record<string, LucideIcon> = {
  "/overview": Gauge,
  "/model-square": Bot,
  "/experience": Sparkles,
  "/endpoint": Rocket,
  "/batch-inference": Boxes,
  "/model/finetune": WandSparkles,
  "/model/eval": ClipboardCheck,
  "/model/eval-benchmarks": ClipboardCheck,
  "/model/eval-collections": Library,
  "/dataset": Database,
  "/lake-assets": Database,
  "/files": HardDrive,
  "/data": Database,
  "/knowledge": Library,
  "/project": FolderCog
} as const;

const navPrefetchTargets = Array.from(
  new Set(["/overview", ...consoleNavSections.flatMap((section) => section.items.map((item) => item.href))])
);

function HeaderIconButton({
  icon: Icon,
  label
}: {
  icon: LucideIcon;
  label: string;
}) {
  return (
    <button
      aria-label={label}
      className="inline-flex h-7 w-7 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-slate-800 hover:text-slate-100"
      title={label}
      type="button"
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}

function ConsoleNavLink({
  href,
  children,
  ...props
}: React.ComponentProps<typeof Link>) {
  const router = useRouter();

  function handlePrefetch() {
    startTransition(() => {
      router.prefetch(href.toString());
    });
  }

  return (
    <Link
      {...props}
      href={href}
      onFocus={handlePrefetch}
      onMouseEnter={handlePrefetch}
      prefetch
    >
      {children}
    </Link>
  );
}

function isNavItemActive(pathname: string, href: string) {
  if (pathname === href || pathname.startsWith(`${href}/`)) {
    return true;
  }
  if (
    href === "/model/eval" &&
    (pathname.startsWith("/model/eval-benchmarks") ||
      pathname.startsWith("/model/eval-leaderboards"))
  ) {
    return true;
  }
  return false;
}
