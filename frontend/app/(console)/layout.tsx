import { Suspense } from "react";

import { ConsoleShell } from "@/components/console/console-shell";
import { getProjects } from "@/features/project/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

async function ConsoleShellWithData({ children }: { children: React.ReactNode }) {
  const [projects, currentProjectId] = await Promise.all([
    getProjects().catch(() => []),
    getCurrentProjectIdFromCookie()
  ]);

  return (
    <ConsoleShell currentProjectId={currentProjectId} projects={projects}>
      {children}
    </ConsoleShell>
  );
}

function ShellFallback({ children }: { children: React.ReactNode }) {
  return (
    <ConsoleShell currentProjectId={null} projects={[]}>
      {children}
    </ConsoleShell>
  );
}

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<ShellFallback>{children}</ShellFallback>}>
      <ConsoleShellWithData>{children}</ConsoleShellWithData>
    </Suspense>
  );
}
