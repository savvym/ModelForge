function normalizeSegment(value: string | null | undefined) {
  const normalized = (value ?? "").trim().replace(/^\/+|\/+$/g, "");
  return normalized || null;
}

export function getObjectStoreRootNamespace() {
  return (
    normalizeSegment(process.env.NEXT_PUBLIC_OBJECT_STORE_ROOT_PREFIX) ??
    (process.env.NODE_ENV === "production" ? "nta-prod" : "nta-dev")
  );
}

export function buildObjectStoreRootPrefix() {
  return `${getObjectStoreRootNamespace()}/`;
}

export function buildProjectPrefix(projectId: string) {
  return `${buildObjectStoreRootPrefix()}projects/${projectId}/`;
}

export function buildProjectDomainPrefix(projectId: string, domain: string) {
  const normalizedDomain = normalizeSegment(domain);
  if (!normalizedDomain) {
    throw new Error("对象存储域不能为空");
  }
  return `${buildProjectPrefix(projectId)}${normalizedDomain}/`;
}

export function buildBenchmarkVersionPrefix(
  projectId: string,
  benchmarkName: string,
  versionId: string
) {
  const normalizedBenchmarkName = normalizeSegment(benchmarkName);
  const normalizedVersionId = normalizeSegment(versionId);
  if (!normalizedBenchmarkName || !normalizedVersionId) {
    throw new Error("Benchmark 版本路径参数不完整");
  }
  return `${buildProjectDomainPrefix(projectId, "benchmarks")}${normalizedBenchmarkName}/versions/${normalizedVersionId}/`;
}
