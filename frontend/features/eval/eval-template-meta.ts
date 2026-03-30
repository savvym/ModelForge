export type TemplateTypeId =
  | "llm_categorical"
  | "llm_numeric"
  | "rule_string_match"
  | "rule_text_similarity"
  | "manual_categorical";

export type TemplateOutputType = "boolean" | "numeric" | "categorical";

export interface TemplateTypeMeta {
  id: TemplateTypeId;
  label: string;
  description: string;
  outputType: TemplateOutputType;
  supportsPresets: boolean;
  requiresModel: boolean;
}

export interface TemplatePresetMeta {
  id: string;
  label: string;
  description: string;
  prompt: string;
  passLabels?: string[];
  failLabels?: string[];
  scoreMin?: string;
  scoreMax?: string;
  passThreshold?: string;
}

export const TEMPLATE_TYPES: TemplateTypeMeta[] = [
  {
    id: "llm_categorical",
    label: "LLM 自动评测 - 分类型",
    description: "由 Judge LLM 输出分类标签，并按 Pass / Fail 分组计算结果。",
    outputType: "categorical",
    supportsPresets: true,
    requiresModel: true,
  },
  {
    id: "llm_numeric",
    label: "LLM 自动评测 - 数值型",
    description: "由 Judge LLM 给出数值分数，并结合分数范围与通过阈值完成判定。",
    outputType: "numeric",
    supportsPresets: true,
    requiresModel: true,
  },
  {
    id: "rule_string_match",
    label: "规则评测 - 字符串匹配",
    description: "对两个文本模板做完全匹配、包含、前后缀匹配等规则校验。",
    outputType: "boolean",
    supportsPresets: false,
    requiresModel: false,
  },
  {
    id: "rule_text_similarity",
    label: "规则评测 - 文本相似度",
    description: "对两个文本模板计算 BLEU、ROUGE、余弦相似度等指标，并通过阈值判断。",
    outputType: "boolean",
    supportsPresets: false,
    requiresModel: false,
  },
  {
    id: "manual_categorical",
    label: "人工评测 - 分类型",
    description: "由人工从预定义标签中进行标注，并按 Pass / Fail 分组沉淀结果。",
    outputType: "categorical",
    supportsPresets: false,
    requiresModel: false,
  },
];

export const OUTPUT_TYPE_LABELS: Record<string, string> = {
  numeric: "数值打分",
  boolean: "通过/不通过",
  categorical: "分类标签",
};

export const STRING_MATCH_OPERATORS = [
  { value: "equals", label: "相等" },
  { value: "not_equals", label: "不相等" },
  { value: "contains", label: "包含" },
  { value: "starts_with", label: "开头包含" },
  { value: "ends_with", label: "结尾包含" },
] as const;

export const TEXT_SIMILARITY_METRICS = [
  { value: "FUZZY_MATCH", label: "FUZZY_MATCH" },
  { value: "BLEU_4", label: "BLEU_4" },
  { value: "COSINE", label: "COSINE" },
  { value: "ROUGE_1", label: "ROUGE_1" },
  { value: "ROUGE_2", label: "ROUGE_2" },
  { value: "ROUGE_L", label: "ROUGE_L" },
  { value: "ACCURACY", label: "ACCURACY" },
] as const;

export const LLM_CATEGORICAL_PRESETS: TemplatePresetMeta[] = [
  {
    id: "rubric-check",
    label: "标准核查",
    description: "逐条检查评分标准是否满足，输出 Pass / Fail。",
    prompt:
      "You are a strict grader.\n" +
      "Review the response against every rubric item and decide whether it passes overall.\n" +
      "Use the provided rubric as the scoring standard.\n\n" +
      "Rubric:\n{{target}}\n\n" +
      "Question or context:\n{{input}}\n\n" +
      "Response:\n{{output}}",
    passLabels: ["Pass"],
    failLabels: ["Fail"],
  },
  {
    id: "relevance-check",
    label: "相关性判断",
    description: "判断回答是否和问题相关，输出 Relevant / Irrelevant。",
    prompt:
      "You are an expert evaluator.\n" +
      "Determine whether the response directly addresses the user request.\n\n" +
      "Question:\n{{input}}\n\n" +
      "Response:\n{{output}}",
    passLabels: ["Relevant"],
    failLabels: ["Irrelevant"],
  },
  {
    id: "sentiment-analysis",
    label: "情感分析",
    description: "识别文本情绪倾向，默认标签为积极 / 中性 / 消极。",
    prompt:
      "You are a sentiment analysis expert.\n" +
      "Classify the emotional tone of the text into one of the configured labels.\n\n" +
      "Text:\n{{output}}",
    passLabels: ["积极"],
    failLabels: ["中性", "消极"],
  },
  {
    id: "correctness-category",
    label: "正确性分类",
    description: "将回答分为 correct / partial / wrong 三类，并映射到 Pass / Fail。",
    prompt:
      "You are an expert evaluator.\n" +
      "Classify the correctness of the response against the reference answer.\n\n" +
      "Question:\n{{input}}\n\n" +
      "Reference answer:\n{{target}}\n\n" +
      "Response:\n{{output}}",
    passLabels: ["correct"],
    failLabels: ["partial", "wrong"],
  },
  {
    id: "custom",
    label: "自定义评分器",
    description: "从零开始编写分类评测 Prompt，并自行维护标签分组。",
    prompt:
      "1. Explain the evaluation standard you want the judge model to apply.\n" +
      "2. Make sure the final score label is one of the configured category labels.\n" +
      "3. Reference at least one runtime variable such as {{input}}, {{target}}, or {{output}}.",
    passLabels: ["Pass"],
    failLabels: ["Fail"],
  },
];

export const LLM_NUMERIC_PRESETS: TemplatePresetMeta[] = [
  {
    id: "quality-score-1-5",
    label: "质量评分 (1-5)",
    description: "对回答质量进行 1-5 分打分，适用于开放式问答。",
    prompt:
      "You are an expert evaluator.\n" +
      "Evaluate the response quality on a scale from 1 to 5.\n\n" +
      "Question:\n{{input}}\n\n" +
      "Response:\n{{output}}",
    scoreMin: "1",
    scoreMax: "5",
    passThreshold: "3",
  },
  {
    id: "semantic-similarity",
    label: "语义相似度",
    description: "比较回答和参考答案的语义一致性，并输出数值分数。",
    prompt:
      "You are an evaluation expert.\n" +
      "Score how semantically similar the response is to the reference answer.\n\n" +
      "Reference answer:\n{{target}}\n\n" +
      "Response:\n{{output}}",
    scoreMin: "0",
    scoreMax: "5",
    passThreshold: "3",
  },
  {
    id: "custom",
    label: "自定义评分器",
    description: "从零开始编写数值评分 Prompt，并自定义分数范围和阈值。",
    prompt:
      "1. Describe the grading standard clearly.\n" +
      "2. Ensure the score falls within the configured numeric range.\n" +
      "3. Reference at least one runtime variable such as {{input}}, {{target}}, or {{output}}.",
    scoreMin: "0",
    scoreMax: "5",
    passThreshold: "3",
  },
];

const PRESET_LABELS = new Map(
  [...LLM_CATEGORICAL_PRESETS, ...LLM_NUMERIC_PRESETS].map((preset) => [preset.id, preset.label]),
);

const TEMPLATE_TYPE_LABELS = new Map(TEMPLATE_TYPES.map((item) => [item.id, item.label]));

export function getTemplateTypeMeta(templateType: string | null | undefined) {
  return TEMPLATE_TYPES.find((item) => item.id === templateType);
}

export function getTemplateTypeLabel(templateType: string | null | undefined) {
  if (!templateType) return "未分类";
  return TEMPLATE_TYPE_LABELS.get(templateType as TemplateTypeId) ?? templateType;
}

export function getPresetLabel(presetId: string | null | undefined) {
  if (!presetId) return "--";
  return PRESET_LABELS.get(presetId) ?? presetId;
}

export function getPresetsForTemplateType(templateType: TemplateTypeId) {
  if (templateType === "llm_categorical") {
    return LLM_CATEGORICAL_PRESETS;
  }
  if (templateType === "llm_numeric") {
    return LLM_NUMERIC_PRESETS;
  }
  return [];
}

export function parseTagList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function stringifyTagList(values: string[]) {
  return values.join(", ");
}

export function defaultPassTags() {
  return "Pass";
}

export function defaultFailTags() {
  return "Fail";
}
