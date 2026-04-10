export type ConsoleNavItem = {
  title: string;
  href: string;
  group: "overview" | "workspace" | "system";
};

export type ConsoleNavSection = {
  id: string;
  title: string;
  items: ConsoleNavItem[];
};

export type ConsolePageMeta = {
  title: string;
  description: string;
  group: ConsoleNavItem["group"];
};

export const consoleNavSections: ConsoleNavSection[] = [
  {
    id: "overview",
    title: "概览",
    items: [{ title: "概览页", href: "/overview", group: "overview" }]
  },
  {
    id: "marketplace",
    title: "智能广场",
    items: [
      { title: "模型广场", href: "/model-square", group: "overview" },
      { title: "体验中心", href: "/experience", group: "overview" }
    ]
  },
  {
    id: "inference",
    title: "模型推理",
    items: [
      { title: "在线推理", href: "/endpoint", group: "workspace" },
      { title: "批量推理", href: "/batch-inference", group: "workspace" }
    ]
  },
  {
    id: "customization",
    title: "模型定制",
    items: [
      { title: "模型精调", href: "/model/finetune", group: "workspace" },
      { title: "模型评测", href: "/model/eval", group: "workspace" }
    ]
  },
  {
    id: "data",
    title: "数据管理",
    items: [
      { title: "数据集", href: "/dataset", group: "workspace" },
      { title: "湖资产", href: "/lake-assets", group: "workspace" },
      { title: "Files", href: "/files", group: "workspace" },
      { title: "RustFS", href: "/data", group: "workspace" }
    ]
  },
  {
    id: "system",
    title: "系统管理",
    items: [{ title: "项目配置", href: "/project", group: "system" }]
  }
];

export const consolePageMeta: Record<string, ConsolePageMeta> = {
  overview: { title: "概览页", description: "查看当前项目、核心指标和服务状态。", group: "overview" },
  "model-square": { title: "模型广场", description: "Provider 接入、模型同步和模型资产管理。", group: "overview" },
  experience: { title: "体验中心", description: "试玩工作台，适合做模型和工具链验证。", group: "overview" },
  endpoint: { title: "在线推理", description: "管理在线推理接入点和实时调用。", group: "workspace" },
  "batch-inference": { title: "批量推理", description: "离线任务、接入点和结果管理。", group: "workspace" },
  "model-finetune": { title: "模型精调", description: "训练任务和精调流程管理。", group: "workspace" },
  "model-warehouse": { title: "模型广场", description: "兼容旧路由，实际跳转到模型广场。", group: "overview" },
  "model-eval": { title: "模型评测", description: "评测任务与评测管理入口。", group: "workspace" },
  "model-eval-leaderboards": {
    title: "排行榜",
    description: "按 Eval Spec / Suite Version 组织和管理模型排行榜。",
    group: "workspace"
  },
  "model-eval-create": { title: "创建评测任务", description: "按 Benchmark 与 Version 创建真实评测任务。", group: "workspace" },
  "model-eval-detail": { title: "评测任务详情", description: "查看评测任务指标、样本级结果和产物位置。", group: "workspace" },
  "model-eval-specs-create": {
    title: "创建评测类型",
    description: "创建 Eval Spec 并定义初始版本。",
    group: "workspace"
  },
  "model-eval-suites-create": {
    title: "创建评测套件",
    description: "创建 Eval Suite 并编排多个评测项。",
    group: "workspace"
  },
  "model-eval-benchmarks": {
    title: "评测管理",
    description: "兼容旧路由，实际归属到模型评测下的评测管理标签。",
    group: "workspace"
  },
  dataset: { title: "数据集", description: "数据集、版本和共享管理。", group: "workspace" },
  "lake-assets": {
    title: "湖资产",
    description: "统一查看和管理数据湖 raw 层资产，支持搜索、筛选与删除。",
    group: "workspace"
  },
  files: {
    title: "Files",
    description: "原始文件系统视图，业务侧按目录管理，底层统一落在 S3 对象存储。",
    group: "workspace"
  },
  data: {
    title: "RustFS",
    description: "当前项目的 RustFS 浏览器，可直接查看 files、lake 与其他对象前缀的真实目录结构。",
    group: "workspace"
  },
  "dataset-create": { title: "创建数据集", description: "创建数据集和版本上传流程。", group: "workspace" },
  "dataset-detail": { title: "数据集详情", description: "查看数据集元数据与版本列表。", group: "workspace" },
  project: { title: "项目配置", description: "项目配额和授权管理。", group: "system" },
};
