"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { startTransition, useEffect, useState } from "react";
import {
  Bot,
  Boxes,
  ClipboardCheck,
  Database,
  HardDrive,
  FolderCog,
  Gauge,
  LayoutDashboard,
  type LucideIcon,
  PanelLeftClose,
  PanelLeftOpen,
  Rocket,
  Search,
  Sparkles,
  WandSparkles
} from "lucide-react";
import { CURRENT_PROJECT_COOKIE } from "@/features/project/constants";
import type { ProjectSummary } from "@/types/api";
import { cn } from "@/lib/utils";
import { consoleNavSections } from "@/lib/console-navigation";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger
} from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

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
  const isStorageBrowserPage =
    pathname === "/files" ||
    pathname.startsWith("/files/") ||
    pathname === "/data" ||
    pathname.startsWith("/data/");
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
        "console-shell grid h-dvh min-h-0 grid-cols-1 grid-rows-[52px_minmax(0,1fr)] overflow-hidden bg-background text-foreground",
        isNavCollapsed ? "md:grid-cols-[72px_minmax(0,1fr)]" : "md:grid-cols-[232px_minmax(0,1fr)]"
      )}
    >
      <div className="col-span-full flex items-center gap-3 border-b border-border/80 bg-background/95 px-3 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="flex min-w-0 items-center gap-1.5">
          <Button
            aria-label={isNavCollapsed ? "展开导航栏" : "收起导航栏"}
            className="size-8 rounded-md text-muted-foreground"
            onClick={() => setIsNavCollapsed((current) => !current)}
            size="icon"
            title={isNavCollapsed ? "展开导航栏" : "收起导航栏"}
            type="button"
            variant="ghost"
          >
            {isNavCollapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
          </Button>
          <ConsoleNavLink
            className={cn(
              buttonVariants({ size: "icon", variant: "ghost" }),
              "size-8 rounded-md text-primary/80 hover:text-primary"
            )}
            href="/overview"
            title="返回概览"
          >
            <Boxes />
          </ConsoleNavLink>

          {projects.length ? (
            <div className="min-w-0 rounded-lg border border-transparent transition-colors hover:bg-muted/60 focus-within:bg-muted/60">
              <Select
                onValueChange={handleProjectChange}
                value={activeProject?.id ?? undefined}
              >
                <SelectTrigger className="h-8 w-auto min-w-[124px] max-w-[280px] justify-start gap-1 border-transparent bg-transparent pl-2 pr-1.5 text-sm shadow-none hover:bg-muted/70 focus:ring-0 focus:ring-offset-0 data-[state=open]:bg-muted/70 [&>span]:flex-none [&>span]:max-w-[220px]">
                  <span className="truncate text-left text-sm font-medium text-foreground">
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
            <div className="rounded-lg px-2 text-sm font-medium text-foreground">
              {activeProject?.name ?? "default"}
            </div>
          )}
        </div>

        <div className="hidden min-w-0 flex-1 md:block">
          <div className="relative mx-auto max-w-3xl">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="h-8 rounded-md bg-background/70 pl-9 text-sm shadow-none"
              placeholder="Search data, files, and models..."
              readOnly
              value=""
            />
          </div>
        </div>

        <div className="ml-auto flex items-center gap-1.5">
          <ThemeToggle />
          <Button
            aria-label="账户"
            className="size-8 rounded-md text-muted-foreground"
            size="icon"
            type="button"
            variant="ghost"
          >
            <Avatar className="size-4">
              <AvatarFallback className="text-[9px] font-medium">MF</AvatarFallback>
            </Avatar>
          </Button>
        </div>
      </div>

      <aside className="row-start-2 flex min-h-0 flex-col overflow-hidden bg-transparent">
        <ScrollArea className="min-h-0 flex-1">
          <div className={cn("px-2", isNavCollapsed ? "py-2" : "py-3")}>
            {isNavCollapsed ? (
              <nav className="flex flex-col gap-3 py-1">
                {consoleNavSections.map((section, index) => (
                  <div
                    className={cn("flex flex-col gap-1", index > 0 && "border-t border-border/60 pt-3")}
                    key={section.id}
                  >
                    {section.items.map((item) => {
                      const active = isNavItemActive(pathname, item.href);
                      const Icon = iconByHref[item.href] ?? LayoutDashboard;

                      return (
                        <Tooltip key={item.href}>
                          <TooltipTrigger asChild>
                            <ConsoleNavLink
                              aria-label={item.title}
                              className={cn(
                                buttonVariants({ size: "icon", variant: active ? "secondary" : "ghost" }),
                                "size-8 rounded-md text-muted-foreground",
                                active && "text-foreground"
                              )}
                              href={item.href}
                            >
                              <Icon className={cn(active && "text-primary")} />
                            </ConsoleNavLink>
                          </TooltipTrigger>
                          <TooltipContent side="right">{item.title}</TooltipContent>
                        </Tooltip>
                      );
                    })}
                  </div>
                ))}
              </nav>
            ) : (
              <nav className="flex flex-col gap-4">
                {consoleNavSections.map((section) => (
                  <div className="flex flex-col gap-1" key={section.id}>
                    <div className="px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                      {section.title}
                    </div>

                    <div className="flex flex-col gap-0.5">
                      {section.items.map((item) => {
                        const active = isNavItemActive(pathname, item.href);
                        const Icon = iconByHref[item.href] ?? LayoutDashboard;

                        return (
                          <ConsoleNavLink
                            key={item.href}
                            href={item.href}
                            className={cn(
                              buttonVariants({ size: "sm", variant: active ? "secondary" : "ghost" }),
                              "h-9 justify-start rounded-md px-2.5 text-sm",
                              active && "text-foreground"
                            )}
                          >
                            <Icon className={cn("text-muted-foreground", active && "text-primary")} />
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
        </ScrollArea>
      </aside>

      <main className="row-start-2 min-h-0 min-w-0 bg-transparent">
        <div className="flex h-full min-h-0 min-w-0 flex-col">
          <div
            className={cn(
              "min-h-0 min-w-0 flex-1 bg-transparent",
              isStorageBrowserPage
                ? "overflow-hidden pb-0 pl-3 pr-0 pt-2.5"
                : "overflow-hidden pb-0 pl-4 pr-0 pt-3"
            )}
          >
            {isStorageBrowserPage || isCustomWorkbenchPage ? (
              <div className="min-h-0 min-w-0">{children}</div>
            ) : (
              <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-lg border border-border/70 bg-card/70 shadow-sm backdrop-blur">
                <ScrollArea className="console-workbench__scroll h-full min-h-0">
                  <div className="px-5 py-4 pb-12">
                    {children}
                  </div>
                </ScrollArea>
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
  "/model/my-models": Database,
  "/model/finetune": WandSparkles,
  "/model/eval": ClipboardCheck,
  "/model/eval-benchmarks": ClipboardCheck,
  "/model/probes": Search,
  "/dataset": Database,
  "/lake-assets": Database,
  "/files": HardDrive,
  "/data": HardDrive,
  "/project": FolderCog
} as const;

const navPrefetchTargets = Array.from(
  new Set(["/overview", ...consoleNavSections.flatMap((section) => section.items.map((item) => item.href))])
);

function HeaderIconButton({
  icon: Icon,
  label,
  children
}: {
  icon?: LucideIcon;
  label: string;
  children?: React.ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          aria-label={label}
          className="size-8 rounded-md text-muted-foreground"
          size="icon"
          type="button"
          variant="ghost"
        >
          {children ?? (Icon ? <Icon /> : null)}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
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
