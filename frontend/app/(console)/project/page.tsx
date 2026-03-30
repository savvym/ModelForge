import { ProjectManagementConsole } from "@/features/project/components/project-management-console";
import { getProjects } from "@/features/project/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function ProjectPage() {
  const [projects, currentProjectId] = await Promise.all([
    getProjects().catch(() => []),
    getCurrentProjectIdFromCookie()
  ]);

  return (
    <ProjectManagementConsole
      currentProjectId={currentProjectId}
      initialProjects={projects}
    />
  );
}
