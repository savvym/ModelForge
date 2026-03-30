"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  Braces,
  Cable,
  Check,
  Compass,
  Copy,
  ChevronsUpDown,
  ImagePlus,
  Sparkles,
  SquarePen,
  Video,
  WandSparkles,
} from "lucide-react";
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import {
  Message,
  MessageContent,
  MessageResponse,
  MessageToolbar,
} from "@/components/ai-elements/message";
import {
  Reasoning,
  ReasoningContent,
  ReasoningTrigger,
} from "@/components/ai-elements/reasoning";
import {
  PromptInput,
  PromptInputBody,
  PromptInputButton,
  PromptInputFooter,
  PromptInputProvider,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
  usePromptInputController,
} from "@/components/ai-elements/prompt-input";
import {
  ModelSelector,
  ModelSelectorContent,
  ModelSelectorEmpty,
  ModelSelectorGroup,
  ModelSelectorInput,
  ModelSelectorItem,
  ModelSelectorList,
  ModelSelectorName,
  ModelSelectorTrigger
} from "@/components/ai-elements/model-selector";
import { buttonVariants } from "@/components/ui/button";
import type {
  ExperienceReasoningDepth,
  ExperienceUIMessage,
} from "@/features/experience/types";
import { cn } from "@/lib/utils";
import type { RegistryModelSummary } from "@/types/api";
import { z } from "zod";

const starterPrompts = [
  {
    title: "产品介绍",
    prompt: "帮我写一段适合官网首屏的产品介绍，语气专业但不要太硬。",
    description: "生成一段简洁、可直接改写的文案。",
    icon: Sparkles,
  },
  {
    title: "总结会议纪要",
    prompt: "请把下面这段会议记录整理成结论、待办和风险三部分。",
    description: "把散乱信息整理成清晰结构。",
    icon: SquarePen,
  },
  {
    title: "解释代码逻辑",
    prompt: "请解释这段代码的核心流程，并指出最容易出错的部分。",
    description: "适合调试、Review 和交接。",
    icon: Braces,
  },
  {
    title: "拆解执行方案",
    prompt: "请根据这个目标拆成执行步骤、风险点和验收标准。",
    description: "把模糊目标拆成明确动作。",
    icon: Compass,
  },
];

const sideModes = [
  { icon: Bot, label: "语言模型", active: true },
  { icon: ImagePlus, label: "图像理解" },
  { icon: Video, label: "视频理解" },
  { icon: Cable, label: "MCP" },
  { icon: WandSparkles, label: "创作助手" },
];

const experienceMessageMetadataSchema = z.object({
  latencyMs: z.number().optional(),
  inputTokens: z.number().nullable().optional(),
  outputTokens: z.number().nullable().optional(),
  totalTokens: z.number().nullable().optional(),
  requestId: z.string().nullable().optional(),
  modelName: z.string().optional(),
  providerName: z.string().optional(),
  reasoningDepth: z.enum(["高", "中", "关闭"]).optional(),
});

function isLanguageModel(model: RegistryModelSummary) {
  if (model.status !== "active" || !model.provider_id) {
    return false;
  }

  const category = (model.category || "").toLowerCase();
  return ![
    "向量模型",
    "vector-model",
    "embedding-model",
    "embeddings-model",
    "video-model",
    "视频生成",
    "image-model",
    "图片生成",
    "voice-model",
    "audio-model",
    "语音模型",
  ].includes(category);
}

function formatTokens(value?: number | null) {
  if (typeof value !== "number") {
    return "--";
  }
  return value.toLocaleString("zh-CN");
}

function getMessageText(message: ExperienceUIMessage) {
  return message.parts
    .filter(
      (
        part
      ): part is Extract<ExperienceUIMessage["parts"][number], { type: "text" }> =>
        part.type === "text"
    )
    .map((part) => part.text)
    .join("");
}

function getReasoningText(message: ExperienceUIMessage) {
  return message.parts
    .filter(
      (
        part
      ): part is Extract<
        ExperienceUIMessage["parts"][number],
        { type: "reasoning" }
      > => part.type === "reasoning"
    )
    .map((part) => part.text)
    .join("\n\n");
}

type ComposerProps = {
  chatModels: RegistryModelSummary[];
  messagesLength: number;
  onResetConversation: () => void;
  onSelectModel: (value: string) => void;
  onSubmitPrompt: (value: string) => void;
  selectedModelId: string;
  status: ReturnType<typeof useChat<ExperienceUIMessage>>["status"];
  stop: () => void;
};

export function ExperienceChatConsole({
  models,
}: {
  models: RegistryModelSummary[];
}) {
  const chatModels = useMemo(() => models.filter(isLanguageModel), [models]);
  const [selectedModelId, setSelectedModelId] = useState(chatModels[0]?.id ?? "");
  const [uiError, setUiError] = useState<string | null>(null);
  const reasoningDepth: ExperienceReasoningDepth = "高";
  const requestOptionsRef = useRef({
    modelId: "",
    reasoningDepth: "高" as ExperienceReasoningDepth,
  });

  const selectedModel = useMemo(
    () => chatModels.find((model) => model.id === selectedModelId) ?? chatModels[0] ?? null,
    [chatModels, selectedModelId]
  );

  requestOptionsRef.current = {
    modelId: selectedModel?.id ?? "",
    reasoningDepth,
  };

  const transport = useMemo(
    () =>
      new DefaultChatTransport<ExperienceUIMessage>({
        api: "/experience/chat",
        prepareSendMessagesRequest: async ({
          body,
          id,
          messageId,
          messages,
          trigger,
        }) => ({
          body: {
            ...body,
            id,
            messageId,
            messages,
            trigger,
            ...requestOptionsRef.current,
          },
        }),
      }),
    []
  );

  const { clearError, error, messages, sendMessage, setMessages, status, stop } =
    useChat<ExperienceUIMessage>({
      messageMetadataSchema: experienceMessageMetadataSchema,
      transport,
    });

  const isPending = status === "submitted" || status === "streaming";
  const errorMessage = uiError ?? error?.message ?? null;

  useEffect(() => {
    if (!chatModels.length) {
      setSelectedModelId("");
      return;
    }

    setSelectedModelId((current) =>
      current && chatModels.some((model) => model.id === current)
        ? current
        : chatModels[0].id
    );
  }, [chatModels]);

  function resetConversation() {
    stop();
    setMessages([]);
    setUiError(null);
    clearError();
  }

  function copyText(content: string) {
    void navigator.clipboard.writeText(content);
  }

  function submitPrompt(rawPrompt: string) {
    if (!selectedModel) {
      setUiError("当前没有可用的语言模型，请先在模型广场中接入并启用模型。");
      return;
    }

    const prompt = rawPrompt.trim();
    if (!prompt) {
      return;
    }

    setUiError(null);
    clearError();
    void sendMessage({ text: prompt });
  }

  return (
    <div className="grid h-full min-h-0 grid-cols-[56px_minmax(0,1fr)] overflow-hidden">
      <aside className="border-r border-slate-800 bg-[#0f141b] px-2 py-6">
        <div className="flex flex-col items-center gap-3">
          {sideModes.map((mode) => (
            <button
              className={cn(
                "inline-flex h-9 w-9 items-center justify-center rounded-xl border transition-colors",
                mode.active
                  ? "border-slate-700 bg-[rgba(30,41,59,0.9)] text-slate-100"
                  : "border-transparent text-slate-500 hover:bg-slate-800 hover:text-slate-200"
              )}
              key={mode.label}
              title={mode.label}
              type="button"
            >
              <mode.icon className="h-4 w-4" />
            </button>
          ))}
        </div>
      </aside>

      <section className="flex min-h-0 flex-col bg-[linear-gradient(180deg,rgba(8,12,18,0.18),rgba(8,12,18,0.05)_28%,rgba(8,12,18,0)_100%)]">
        {!selectedModel ? (
          <div className="flex flex-1 items-center justify-center px-6 py-10">
            <div className="space-y-4 rounded-2xl border border-dashed border-slate-700 bg-[rgba(15,20,28,0.72)] px-8 py-10 text-center">
              <div className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-slate-800 bg-[#0f141b] text-slate-200">
                <Bot className="h-5 w-5" />
              </div>
              <div className="text-lg font-semibold text-slate-100">
                当前没有可用的语言模型
              </div>
              <div className="text-sm leading-6 text-slate-400">
                请先前往模型广场接入并启用至少一个可对话模型。
              </div>
              <Link
                className={cn(buttonVariants(), "rounded-full")}
                href="/model-square"
              >
                前往模型广场
              </Link>
            </div>
          </div>
        ) : (
          <>
            <div className="min-h-0 flex flex-1 overflow-hidden">
              <Conversation className="h-full min-h-0 w-full">
                <ConversationContent className="mx-auto w-full max-w-[880px] gap-6 px-6 py-6 md:px-8">
                  {messages.length ? (
                    messages.map((message, index) => {
                      const text = getMessageText(message);
                      const reasoning = getReasoningText(message);
                      const isLastMessage = index === messages.length - 1;
                      const isReasoningStreaming =
                        isLastMessage &&
                        isPending &&
                        message.parts.at(-1)?.type === "reasoning";

                      return (
                        <Message from={message.role} key={message.id}>
                          <MessageContent
                            className={
                              message.role === "assistant"
                                ? "space-y-3"
                                : "whitespace-pre-wrap text-[15px] leading-7"
                            }
                          >
                            {message.role === "assistant" ? (
                              <>
                                {reasoning ? (
                                  <Reasoning
                                    className="mb-4 w-full"
                                    isStreaming={isReasoningStreaming}
                                    open
                                  >
                                    <ReasoningTrigger className="pointer-events-none hover:text-slate-400" />
                                    <ReasoningContent className="text-[13px] leading-6 text-slate-400 [&_blockquote]:text-slate-400 [&_code]:bg-[rgba(255,255,255,0.04)] [&_pre]:border-white/8 [&_pre]:bg-[rgba(8,12,19,0.72)]">
                                      {reasoning}
                                    </ReasoningContent>
                                  </Reasoning>
                                ) : message.metadata?.reasoningDepth &&
                                  message.metadata.reasoningDepth !== "关闭" ? (
                                  <div className="text-xs text-slate-600">
                                    当前模型未返回可展示的思考摘要。
                                  </div>
                                ) : null}

                                {text ? (
                                  <MessageResponse>{text}</MessageResponse>
                                ) : isLastMessage && isPending ? (
                                  <div className="text-sm text-slate-500">
                                    正在生成回答...
                                  </div>
                                ) : null}
                              </>
                            ) : (
                              text
                            )}
                          </MessageContent>

                          {message.role === "assistant" ? (
                            <MessageToolbar>
                              <div className="truncate">
                                {[
                                  message.metadata?.latencyMs
                                    ? `${(message.metadata.latencyMs / 1000).toFixed(2)} s`
                                    : null,
                                  typeof message.metadata?.totalTokens === "number"
                                    ? `${formatTokens(message.metadata.totalTokens)} tokens`
                                    : null,
                                ]
                                  .filter(Boolean)
                                  .join(" · ") || "已完成"}
                              </div>
                              {text ? (
                                <button
                                  className="inline-flex items-center gap-1 rounded-full border border-transparent px-2.5 py-1 text-xs text-slate-400 transition-colors hover:border-slate-800 hover:bg-[rgba(255,255,255,0.04)] hover:text-slate-100"
                                  onClick={() => copyText(text)}
                                  type="button"
                                >
                                  <Copy className="h-3.5 w-3.5" />
                                  复制
                                </button>
                              ) : (
                                <span />
                              )}
                            </MessageToolbar>
                          ) : null}
                        </Message>
                      );
                    })
                  ) : (
                    <ConversationEmptyState
                      description="保留模型切换，把界面收成更轻的对话区。"
                      icon={
                        <div className="rounded-full border border-slate-800/80 bg-[rgba(255,255,255,0.03)] p-3">
                          <Bot className="h-5 w-5" />
                        </div>
                      }
                      title="从一个简洁的问题开始"
                    >
                      <div className="space-y-5">
                        <div className="space-y-2">
                          <div className="text-lg font-medium text-slate-100">
                            从一个简洁的问题开始
                          </div>
                          <div className="text-sm leading-6 text-slate-500">
                            体验中心现在使用更轻的消息流和输入区，减少视觉噪音。
                          </div>
                        </div>

                        <div className="grid gap-2 sm:grid-cols-2">
                          {starterPrompts.map((item) => (
                            <button
                              className="rounded-2xl border border-slate-800/80 bg-[rgba(255,255,255,0.02)] px-4 py-3 text-left transition-colors hover:bg-[rgba(255,255,255,0.04)]"
                              key={item.title}
                              onClick={() => submitPrompt(item.prompt)}
                              type="button"
                            >
                              <div className="flex items-start gap-3">
                                <div className="mt-0.5 text-slate-400">
                                  <item.icon className="h-4 w-4" />
                                </div>
                                <div className="space-y-1">
                                  <div className="text-sm font-medium text-slate-100">
                                    {item.title}
                                  </div>
                                  <div className="text-xs leading-5 text-slate-500">
                                    {item.description}
                                  </div>
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    </ConversationEmptyState>
                  )}
                </ConversationContent>
                <ConversationScrollButton />
              </Conversation>
            </div>

            <div className="border-t border-slate-900/80 bg-[linear-gradient(180deg,rgba(10,14,21,0.72),rgba(10,14,21,0.96))] px-6 py-4 backdrop-blur-xl">
              <div className="mx-auto w-full max-w-[880px] space-y-3">
                <PromptInputProvider>
                  <ExperienceComposer
                    chatModels={chatModels}
                    messagesLength={messages.length}
                    onResetConversation={resetConversation}
                    onSelectModel={setSelectedModelId}
                    onSubmitPrompt={submitPrompt}
                    selectedModelId={selectedModel?.id ?? ""}
                    status={status}
                    stop={stop}
                  />
                </PromptInputProvider>

                {errorMessage ? <ErrorBanner message={errorMessage} /> : null}
                <FooterNote />
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}

function ExperienceComposer({
  chatModels,
  messagesLength,
  onResetConversation,
  onSelectModel,
  onSubmitPrompt,
  selectedModelId,
  status,
  stop,
}: ComposerProps) {
  const { value } = usePromptInputController();
  const [isModelSelectorOpen, setIsModelSelectorOpen] = useState(false);
  const selectedModel = chatModels.find((model) => model.id === selectedModelId);

  function handleSelectModel(nextModelId: string) {
    setIsModelSelectorOpen(false);
    if (nextModelId === selectedModelId) {
      return;
    }

    onSelectModel(nextModelId);
    onResetConversation();
  }

  return (
    <PromptInput
      className="w-full"
      onSubmit={({ text }) => onSubmitPrompt(text)}
    >
      <PromptInputBody>
        <PromptInputTextarea
          className="px-4 pb-0 pt-4"
          disabled={status === "submitted" || status === "streaming"}
          placeholder="输入问题，支持多轮追问。"
        />
      </PromptInputBody>

      <PromptInputFooter className="flex-wrap gap-2">
        <PromptInputTools className="flex-1 flex-wrap gap-2">
          <ModelSelector
            onOpenChange={setIsModelSelectorOpen}
            open={isModelSelectorOpen}
          >
            <ModelSelectorTrigger
              className={cn(
                buttonVariants({ size: "sm", variant: "secondary" }),
                "max-w-[320px] justify-between gap-2 rounded-full border-white/10 bg-[rgba(255,255,255,0.04)] px-3 text-slate-100 hover:bg-[rgba(255,255,255,0.08)]"
              )}
            >
              <span className="min-w-0 truncate text-left">
                {selectedModel
                  ? `${selectedModel.name} · ${selectedModel.provider_name ?? "未绑定 Provider"}`
                  : "选择一个语言模型"}
              </span>
              <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-slate-500" />
            </ModelSelectorTrigger>

            <ModelSelectorContent
              className="max-w-[560px]"
              title="选择一个语言模型"
            >
              <ModelSelectorInput placeholder="搜索模型或 Provider" />
              <ModelSelectorList>
                <ModelSelectorEmpty>没有找到匹配模型。</ModelSelectorEmpty>
                <ModelSelectorGroup heading="可用模型">
                  {chatModels.map((model) => {
                    const isSelected = model.id === selectedModelId;
                    return (
                      <ModelSelectorItem
                        className="mx-2 rounded-2xl px-3 py-3"
                        key={model.id}
                        onSelect={() => handleSelectModel(model.id)}
                        value={`${model.name} ${model.provider_name ?? ""}`}
                      >
                        <div className="flex min-w-0 flex-1 flex-col gap-1">
                          <ModelSelectorName className="text-sm font-medium text-slate-100">
                            {model.name}
                          </ModelSelectorName>
                          <div className="text-xs text-slate-500">
                            {model.provider_name ?? "未绑定 Provider"}
                          </div>
                        </div>
                        {isSelected ? <Check className="h-4 w-4 text-[#8fffcf]" /> : null}
                      </ModelSelectorItem>
                    );
                  })}
                </ModelSelectorGroup>
              </ModelSelectorList>
            </ModelSelectorContent>
          </ModelSelector>

          {messagesLength ? (
            <PromptInputButton
              onClick={onResetConversation}
              size="sm"
              variant="ghost"
            >
              新对话
            </PromptInputButton>
          ) : (
            <span className="hidden text-xs text-slate-500 sm:inline">
              Enter 发送，Shift + Enter 换行
            </span>
          )}
        </PromptInputTools>

        <PromptInputSubmit
          className="h-9 w-9 rounded-full"
          disabled={!value.trim() && status !== "submitted" && status !== "streaming"}
          onStop={stop}
          status={status}
        />
      </PromptInputFooter>
    </PromptInput>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-red-200/30 bg-[rgba(120,30,52,0.18)] px-4 py-3 text-sm text-red-200">
      {message}
    </div>
  );
}

function FooterNote() {
  return (
    <div className="text-center text-xs text-slate-600">
      试用体验内容均由人工智能模型生成，不代表平台立场。
    </div>
  );
}
