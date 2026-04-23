"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import {
  Bot,
  Braces,
  Check,
  Compass,
  Copy,
  ChevronsUpDown,
  LibraryBig,
  Server,
  Sparkles,
  SquarePen,
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
import type { ModelDeploymentSummary, RegistryModelSummary } from "@/types/api";
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
  if (
    model.provider_name?.startsWith("infer-agent /") ||
    model.vendor?.startsWith("infer-agent /")
  ) {
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
  modelOptions: ExperienceModelOption[];
  messagesLength: number;
  onResetConversation: () => void;
  onSelectModel: (value: string) => void;
  onSubmitPrompt: (value: string) => void;
  selectedModelId: string;
  status: ReturnType<typeof useChat<ExperienceUIMessage>>["status"];
  stop: () => void;
};

type ExperienceModelOption = {
  id: string;
  name: string;
  providerName: string;
  source: "registry" | "deployment";
  targetId: string;
};

type ExperienceModelSource = ExperienceModelOption["source"];

function isReadyDeployment(deployment: ModelDeploymentSummary) {
  return (deployment.phase ?? deployment.status) === "ready" && Boolean(deployment.endpoint_url);
}

export function ExperienceChatConsole({
  deployments,
  models,
}: {
  deployments: ModelDeploymentSummary[];
  models: RegistryModelSummary[];
}) {
  const chatModels = useMemo(() => models.filter(isLanguageModel), [models]);
  const deploymentModels = useMemo(
    () => deployments.filter(isReadyDeployment),
    [deployments]
  );
  const modelOptions = useMemo<ExperienceModelOption[]>(
    () => [
      ...chatModels.map((model) => ({
        id: `registry:${model.id}`,
        name: model.name,
        providerName: model.provider_name ?? "未绑定 Provider",
        source: "registry" as const,
        targetId: model.id,
      })),
      ...deploymentModels.map((deployment) => ({
        id: `deployment:${deployment.id}`,
        name: deployment.served_model_name ?? deployment.model_name ?? deployment.name,
        providerName: deployment.machine_name ?? "我的部署",
        source: "deployment" as const,
        targetId: deployment.id,
      })),
    ],
    [chatModels, deploymentModels]
  );
  const [selectedModelId, setSelectedModelId] = useState(modelOptions[0]?.id ?? "");
  const [uiError, setUiError] = useState<string | null>(null);
  const reasoningDepth: ExperienceReasoningDepth = "高";
  const requestOptionsRef = useRef({
    modelId: "",
    targetId: "",
    targetType: "registry" as ExperienceModelOption["source"],
    reasoningDepth: "高" as ExperienceReasoningDepth,
  });

  const selectedOptionId = useMemo(() => {
    if (!modelOptions.length) {
      return "";
    }
    return modelOptions.some((model) => model.id === selectedModelId)
      ? selectedModelId
      : modelOptions[0].id;
  }, [modelOptions, selectedModelId]);

  const selectedModel = useMemo(
    () => modelOptions.find((model) => model.id === selectedOptionId) ?? null,
    [modelOptions, selectedOptionId]
  );

  requestOptionsRef.current = {
    modelId: selectedModel?.targetId ?? "",
    targetId: selectedModel?.targetId ?? "",
    targetType: selectedModel?.source ?? "registry",
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
      setUiError("当前没有可用的语言模型，请先在模型广场接入模型，或在我的部署中启动模型。");
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
    <div className="flex h-full min-h-0 min-w-0 overflow-hidden">
      <section className="flex min-h-0 min-w-0 flex-1 flex-col bg-background">
        {!selectedModel ? (
          <div className="flex flex-1 items-center justify-center px-6 py-10">
            <div className="space-y-4 rounded-lg border border-dashed border-border bg-card/80 px-8 py-10 text-center">
              <div className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-lg border border-border bg-card/80 text-foreground">
                <Bot className="h-5 w-5" />
              </div>
              <div className="text-lg font-semibold text-foreground">
                当前没有可用的语言模型
              </div>
              <div className="text-sm leading-6 text-muted-foreground">
                请先前往模型广场接入模型，或在我的部署中启动至少一个可对话模型。
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
            <div className="flex min-h-0 flex-1 overflow-hidden">
              <Conversation className="h-full min-h-0 w-full">
                <ConversationContent
                  className="mx-auto w-full max-w-[820px] gap-6 px-4 pb-8 pt-8 md:px-8"
                  scrollClassName="console-scrollbar-subtle"
                >
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
                                ? "flex flex-col gap-3"
                                : "whitespace-pre-wrap text-[15px] leading-7"
                            }
                          >
                            {message.role === "assistant" ? (
                              <>
                                {reasoning ? (
                                  <Reasoning
                                    className="mb-3"
                                    isStreaming={isReasoningStreaming}
                                  >
                                    <ReasoningTrigger />
                                    <ReasoningContent className="text-[13px] leading-6 text-muted-foreground [&_blockquote]:text-muted-foreground [&_code]:bg-muted/40 [&_pre]:border-border [&_pre]:bg-card/80">
                                      {reasoning}
                                    </ReasoningContent>
                                  </Reasoning>
                                ) : message.metadata?.reasoningDepth &&
                                  message.metadata.reasoningDepth !== "关闭" ? (
                                  <div className="text-xs text-muted-foreground">
                                    当前模型未返回可展示的思考摘要。
                                  </div>
                                ) : null}

                                {text ? (
                                  <MessageResponse>{text}</MessageResponse>
                                ) : isLastMessage && isPending ? (
                                  <div className="text-sm text-muted-foreground">
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
                                  className="inline-flex items-center gap-1 rounded-full border border-transparent px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-border hover:bg-muted/40 hover:text-foreground"
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
                      className="min-h-0 flex-1 px-0 pb-12 pt-2"
                      title="从一个简洁的问题开始"
                    >
                      <div className="flex w-full max-w-[720px] flex-col items-center gap-6">
                        <div className="flex flex-col items-center gap-2">
                          <div className="flex size-10 items-center justify-center rounded-full bg-muted/45 text-muted-foreground">
                            <Bot className="size-4" />
                          </div>
                          <div className="text-xl font-semibold text-foreground">
                            从一个简洁的问题开始
                          </div>
                          <div className="text-sm leading-6 text-muted-foreground">
                            选择一个场景，或直接输入问题。
                          </div>
                        </div>

                        <div className="grid w-full gap-2 sm:grid-cols-2">
                          {starterPrompts.map((item) => (
                            <button
                              className="group rounded-2xl border border-border/65 bg-background/70 px-4 py-3.5 text-left shadow-sm transition-colors hover:border-border hover:bg-muted/35"
                              key={item.title}
                              onClick={() => submitPrompt(item.prompt)}
                              type="button"
                            >
                              <div className="flex items-center gap-3">
                                <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted/45 text-muted-foreground transition-colors group-hover:bg-background group-hover:text-foreground">
                                  <item.icon className="size-4" />
                                </div>
                                <div className="flex min-w-0 flex-col gap-1">
                                  <div className="text-sm font-medium text-foreground">
                                    {item.title}
                                  </div>
                                  <div className="text-xs leading-5 text-muted-foreground">
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

            <div className="bg-gradient-to-t from-background via-background/95 to-transparent px-4 pb-5 pt-8 backdrop-blur-sm md:px-8">
              <div className="mx-auto flex w-full max-w-[760px] flex-col gap-2.5">
                <PromptInputProvider>
                  <ExperienceComposer
                    modelOptions={modelOptions}
                    messagesLength={messages.length}
                    onResetConversation={resetConversation}
                    onSelectModel={setSelectedModelId}
                    onSubmitPrompt={submitPrompt}
                    selectedModelId={selectedOptionId}
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
  modelOptions,
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
  const [activeModelSource, setActiveModelSource] =
    useState<ExperienceModelSource>("registry");
  const selectedModel = modelOptions.find((model) => model.id === selectedModelId);
  const registryOptions = useMemo(
    () => modelOptions.filter((model) => model.source === "registry"),
    [modelOptions]
  );
  const deploymentOptions = useMemo(
    () => modelOptions.filter((model) => model.source === "deployment"),
    [modelOptions]
  );
  const activeOptions =
    activeModelSource === "registry" ? registryOptions : deploymentOptions;
  const modelSourceTabs = [
    {
      count: registryOptions.length,
      icon: LibraryBig,
      label: "模型广场",
      value: "registry" as const,
    },
    {
      count: deploymentOptions.length,
      icon: Server,
      label: "我的部署",
      value: "deployment" as const,
    },
  ];
  const activeSourceLabel =
    modelSourceTabs.find((item) => item.value === activeModelSource)?.label ?? "模型";

  function handleModelSelectorOpenChange(nextOpen: boolean) {
    setIsModelSelectorOpen(nextOpen);
    if (nextOpen && selectedModel) {
      setActiveModelSource(selectedModel.source);
    }
  }

  function handleSelectModel(nextModelId: string) {
    setIsModelSelectorOpen(false);
    if (nextModelId === selectedModelId) {
      return;
    }

    onSelectModel(nextModelId);
    onResetConversation();
  }

  const isGenerating = status === "submitted" || status === "streaming";

  return (
    <PromptInput
      className="experience-composer w-full"
      inputGroupClassName="rounded-3xl border-border/70 bg-card/95 shadow-[0_18px_55px_-36px_hsl(var(--foreground)/0.9)] ring-1 ring-border/30 transition-all focus-within:border-ring/70 focus-within:ring-ring/20"
      onSubmit={({ text }) => onSubmitPrompt(text)}
    >
      <PromptInputBody>
        <PromptInputTextarea
          className="min-h-[92px] px-5 pb-2 pt-5 text-[15px] leading-7 placeholder:text-muted-foreground/75"
          disabled={isGenerating}
          placeholder="输入问题，支持多轮追问"
        />
      </PromptInputBody>

      <PromptInputFooter className="items-center gap-2 px-3 pb-3 pt-2 sm:px-4">
        <PromptInputTools className="min-w-0 flex-1 flex-wrap gap-2">
          <ModelSelector
            onOpenChange={handleModelSelectorOpenChange}
            open={isModelSelectorOpen}
          >
            <ModelSelectorTrigger
              className={cn(
                buttonVariants({ size: "sm", variant: "secondary" }),
                "h-9 max-w-full justify-between gap-2 rounded-full border border-border/70 bg-muted/35 px-3 text-foreground shadow-none hover:bg-muted/55 sm:max-w-[420px]"
              )}
            >
              <span
                className={cn(
                  "h-2 w-2 shrink-0 rounded-full",
                  selectedModel?.source === "deployment"
                    ? "bg-emerald-500"
                    : "bg-primary"
                )}
              />
              <span className="min-w-0 truncate text-left">
                {selectedModel ? selectedModel.name : "选择一个语言模型"}
              </span>
              <span className="hidden shrink-0 text-xs font-normal text-muted-foreground sm:inline">
                {selectedModel ? selectedModel.providerName : activeSourceLabel}
              </span>
              <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            </ModelSelectorTrigger>

            <ModelSelectorContent
              className="max-w-[760px]"
              title="选择一个语言模型"
            >
              <ModelSelectorInput placeholder="搜索模型或 Provider" />
              <div className="grid min-h-[340px] grid-cols-1 border-t border-border sm:grid-cols-[176px_minmax(0,1fr)]">
                <div className="space-y-1 border-b border-border bg-muted/20 p-2 sm:border-b-0 sm:border-r">
                  {modelSourceTabs.map((item) => {
                    const isActive = item.value === activeModelSource;
                    return (
                      <button
                        className={cn(
                          "flex w-full items-center gap-2 rounded-md px-3 py-2.5 text-left text-sm transition-colors",
                          isActive
                            ? "bg-background text-foreground shadow-sm"
                            : "text-muted-foreground hover:bg-background/70 hover:text-foreground"
                        )}
                        key={item.value}
                        onClick={() => setActiveModelSource(item.value)}
                        type="button"
                      >
                        <item.icon className="h-4 w-4 shrink-0" />
                        <span className="min-w-0 flex-1 truncate">{item.label}</span>
                        <span className="text-xs tabular-nums text-muted-foreground">
                          {item.count}
                        </span>
                      </button>
                    );
                  })}
                </div>

                <ModelSelectorList className="max-h-[420px]">
                  <ModelSelectorEmpty>
                    {activeModelSource === "registry"
                      ? "模型广场暂无匹配模型。"
                      : "我的部署暂无匹配模型。"}
                  </ModelSelectorEmpty>
                  <ModelSelectorGroup heading={activeSourceLabel}>
                    {activeOptions.map((model) => {
                      const isSelected = model.id === selectedModelId;
                      return (
                        <ModelSelectorItem
                          className="mx-2 rounded-lg px-3 py-3"
                          key={model.id}
                          onSelect={() => handleSelectModel(model.id)}
                          value={`${model.name} ${model.providerName}`}
                        >
                          <div className="flex min-w-0 flex-1 flex-col gap-1">
                            <ModelSelectorName className="text-sm font-medium text-foreground">
                              {model.name}
                            </ModelSelectorName>
                            <div className="text-xs text-muted-foreground">
                              {model.providerName}
                            </div>
                          </div>
                          {isSelected ? <Check className="h-4 w-4 text-primary" /> : null}
                        </ModelSelectorItem>
                      );
                    })}
                  </ModelSelectorGroup>
                </ModelSelectorList>
              </div>
            </ModelSelectorContent>
          </ModelSelector>

          {messagesLength ? (
            <PromptInputButton
              className="rounded-full px-3 text-muted-foreground hover:bg-muted/60 hover:text-foreground"
              onClick={onResetConversation}
              size="sm"
              variant="ghost"
            >
              <SquarePen className="h-3.5 w-3.5" />
              新对话
            </PromptInputButton>
          ) : (
            <span />
          )}
        </PromptInputTools>

        <PromptInputSubmit
          className="h-10 w-10 rounded-full shadow-sm"
          disabled={!value.trim() && !isGenerating}
          onStop={stop}
          status={status}
        />
      </PromptInputFooter>
    </PromptInput>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm text-destructive">
      {message}
    </div>
  );
}

function FooterNote() {
  return (
    <div className="text-center text-xs text-muted-foreground">
      试用体验内容均由人工智能模型生成，不代表平台立场。
    </div>
  );
}
