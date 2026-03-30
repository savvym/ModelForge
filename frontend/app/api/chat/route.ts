import {
  createUIMessageStream,
  createUIMessageStreamResponse,
  type UIMessage,
} from "ai";
import { CURRENT_PROJECT_COOKIE, CURRENT_PROJECT_HEADER } from "@/features/project/constants";

const API_BASE_URL =
  process.env.API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://127.0.0.1:8081/api/v1";

type ExperienceChatRouteRequest = {
  messages?: UIMessage[];
  modelId?: string;
  reasoningDepth?: "高" | "中" | "关闭";
  networkEnabled?: boolean;
  mcpEnabled?: boolean;
  canvasEnabled?: boolean;
};

export const runtime = "nodejs";

function extractMessageText(message: UIMessage) {
  return message.parts
    .filter((part): part is Extract<(typeof message.parts)[number], { type: "text" }> => part.type === "text")
    .map((part) => part.text)
    .join("")
    .trim();
}

type BackendChatStreamEvent =
  | {
      type: "start";
      model_name?: string;
      provider_name?: string;
      api_format?: string;
      reasoning_depth?: "高" | "中" | "关闭" | string | null;
    }
  | {
      type: "reasoning_delta";
      delta: string;
    }
  | {
      type: "text_delta";
      delta: string;
    }
  | {
      type: "done";
      latency_ms?: number;
      request_id?: string | null;
      input_tokens?: number | null;
      output_tokens?: number | null;
      total_tokens?: number | null;
      reasoning_available?: boolean;
      streaming_mode?: string;
    }
  | {
      type: "error";
      message: string;
    };

async function* iterateSsePayloads(stream: ReadableStream<Uint8Array>) {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      buffer += decoder.decode();
      break;
    }
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const chunk = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      const dataLines = chunk
        .split(/\r?\n/)
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart());

      if (dataLines.length) {
        const rawPayload = dataLines.join("\n");
        if (rawPayload !== "[DONE]") {
          yield JSON.parse(rawPayload) as BackendChatStreamEvent;
        }
      }

      boundary = buffer.indexOf("\n\n");
    }
  }
}

export async function POST(request: Request) {
  const body = (await request.json()) as ExperienceChatRouteRequest;
  const modelId = body.modelId?.trim();
  const messages = Array.isArray(body.messages) ? body.messages : [];

  if (!modelId) {
    return new Response("Model id is required.", { status: 400 });
  }

  const serializedMessages = messages
    .map((message) => ({
      role: message.role,
      content: extractMessageText(message),
    }))
    .filter((message) => message.content);

  if (!serializedMessages.length) {
    return new Response("Messages are required.", { status: 400 });
  }

  const cookieHeader = request.headers.get("cookie") ?? "";
  const projectId = cookieHeader
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${CURRENT_PROJECT_COOKIE}=`))
    ?.split("=")[1];

  const backendResponse = await fetch(`${API_BASE_URL}/models/${modelId}/chat/stream`, {
    method: "POST",
    cache: "no-store",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
      ...(projectId ? { [CURRENT_PROJECT_HEADER]: decodeURIComponent(projectId) } : {}),
    },
    body: JSON.stringify({
      messages: serializedMessages,
      reasoning_depth: body.reasoningDepth,
    }),
  });

  if (!backendResponse.ok) {
    return new Response(
      (await backendResponse.text()) || "Failed to fetch the chat response.",
      { status: backendResponse.status }
    );
  }

  return createUIMessageStreamResponse({
    stream: createUIMessageStream({
      originalMessages: messages,
      async execute({ writer }) {
        let started = false;
        let textStarted = false;
        let reasoningStarted = false;
        const textPartId = `assistant-text-${Date.now()}`;
        const reasoningPartId = `assistant-reasoning-${Date.now()}`;

        const responseStream = backendResponse.body;
        if (!responseStream) {
          throw new Error("Backend chat stream is empty.");
        }

        for await (const event of iterateSsePayloads(responseStream)) {
          if (event.type === "start") {
            started = true;
            writer.write({
              type: "start",
              messageMetadata: {
                modelName: event.model_name,
                providerName: event.provider_name,
                reasoningDepth:
                  (event.reasoning_depth as "高" | "中" | "关闭" | undefined) ?? body.reasoningDepth ?? "关闭",
              },
            });
            continue;
          }

          if (!started) {
            started = true;
            writer.write({
              type: "start",
              messageMetadata: {
                reasoningDepth: body.reasoningDepth ?? "关闭",
              },
            });
          }

          if (event.type === "reasoning_delta") {
            if (!reasoningStarted) {
              reasoningStarted = true;
              writer.write({
                type: "reasoning-start",
                id: reasoningPartId,
              });
            }
            writer.write({
              type: "reasoning-delta",
              id: reasoningPartId,
              delta: event.delta,
            });
            continue;
          }

          if (event.type === "text_delta") {
            if (!textStarted) {
              textStarted = true;
              writer.write({
                type: "text-start",
                id: textPartId,
              });
            }
            writer.write({
              type: "text-delta",
              id: textPartId,
              delta: event.delta,
            });
            continue;
          }

          if (event.type === "error") {
            writer.write({
              type: "error",
              errorText: event.message,
            });
            break;
          }

          if (event.type === "done") {
            if (reasoningStarted) {
              writer.write({
                type: "reasoning-end",
                id: reasoningPartId,
              });
            }
            if (textStarted) {
              writer.write({
                type: "text-end",
                id: textPartId,
              });
            }
            writer.write({
              type: "finish",
              finishReason: "stop",
              messageMetadata: {
                latencyMs: event.latency_ms,
                inputTokens: event.input_tokens ?? null,
                outputTokens: event.output_tokens ?? null,
                totalTokens: event.total_tokens ?? null,
                requestId: event.request_id ?? null,
              },
            });
            return;
          }
        }

        if (reasoningStarted) {
          writer.write({
            type: "reasoning-end",
            id: reasoningPartId,
          });
        }
        if (textStarted) {
          writer.write({
            type: "text-end",
            id: textPartId,
          });
        }
        writer.write({
          type: "finish",
          finishReason: "stop",
        });
      },
      onError(error) {
        if (error instanceof Error) {
          return error.message;
        }
        return "Chat request failed.";
      },
    }),
  });
}
