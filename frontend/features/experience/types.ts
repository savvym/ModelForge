import type { UIMessage } from "ai";

export type ExperienceReasoningDepth = "高" | "中" | "关闭";

export type ExperienceMessageMetadata = {
  latencyMs?: number;
  inputTokens?: number | null;
  outputTokens?: number | null;
  totalTokens?: number | null;
  requestId?: string | null;
  modelName?: string;
  providerName?: string;
  reasoningDepth?: ExperienceReasoningDepth;
};

export type ExperienceUIMessage = UIMessage<ExperienceMessageMetadata>;
