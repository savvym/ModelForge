"use client";

import { cjk } from "@streamdown/cjk";
import { code } from "@streamdown/code";
import { math } from "@streamdown/math";
import { mermaid } from "@streamdown/mermaid";
import type { UIMessage } from "ai";
import type { ComponentProps, HTMLAttributes } from "react";
import { memo, useMemo } from "react";
import { parseMarkdownIntoBlocks, Streamdown } from "streamdown";
import { AiCodeBlock } from "@/components/ai-elements/code-block";
import { cn } from "@/lib/utils";

const streamdownPlugins = { cjk, code, math, mermaid };

export type MessageProps = HTMLAttributes<HTMLDivElement> & {
  from: UIMessage["role"];
};

export function Message({ className, from, ...props }: MessageProps) {
  return (
    <div
      className={cn(
        "group flex w-full max-w-[95%] flex-col gap-2",
        from === "user" ? "is-user ml-auto justify-end" : "is-assistant",
        className
      )}
      {...props}
    />
  );
}

export type MessageContentProps = HTMLAttributes<HTMLDivElement>;

export function MessageContent({
  children,
  className,
  ...props
}: MessageContentProps) {
  return (
    <div
      className={cn(
        "flex w-fit min-w-0 max-w-full flex-col gap-2 overflow-hidden text-sm",
        "group-[.is-user]:ml-auto group-[.is-user]:max-w-[80%] group-[.is-user]:rounded-[20px] group-[.is-user]:bg-[rgba(255,255,255,0.05)] group-[.is-user]:px-4 group-[.is-user]:py-3 group-[.is-user]:text-slate-100",
        "group-[.is-assistant]:text-slate-100",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export type MessageResponseProps = ComponentProps<typeof Streamdown>;

type ParsedCodeFence = {
  code: string;
  isIncomplete: boolean;
  language?: string;
};

function parseCodeFence(block: string): ParsedCodeFence | null {
  const completeMatch = block.match(/^```([^\n`]*)\n([\s\S]*?)\n```$/);
  if (completeMatch) {
    return {
      code: completeMatch[2],
      isIncomplete: false,
      language: completeMatch[1] || undefined,
    };
  }

  const incompleteMatch = block.match(/^```([^\n`]*)\n([\s\S]*)$/);
  if (incompleteMatch) {
    return {
      code: incompleteMatch[2],
      isIncomplete: true,
      language: incompleteMatch[1] || undefined,
    };
  }

  return null;
}

export const MessageResponse = memo(
  ({ children, className, isAnimating, ...props }: MessageResponseProps) => {
    const content = typeof children === "string" ? children : "";
    const blocks = useMemo(() => parseMarkdownIntoBlocks(content), [content]);
    const proseClassName = cn(
      "max-w-none text-[15px] leading-8 text-slate-100",
      "[&>*:first-child]:mt-0 [&>*:last-child]:mb-0",
      "[&_a]:text-sky-300 [&_a]:underline [&_a]:underline-offset-4",
      "[&_blockquote]:border-l-2 [&_blockquote]:border-slate-700 [&_blockquote]:pl-4 [&_blockquote]:text-slate-400",
      "[&_code]:rounded-md [&_code]:bg-[rgba(255,255,255,0.06)] [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:text-[0.92em]",
      "[&_table]:w-full [&_table]:border-collapse [&_table]:overflow-hidden",
      "[&_td]:border-t [&_td]:border-slate-800/80 [&_td]:px-3 [&_td]:py-2 [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_th]:text-slate-400",
      className
    );

    return (
      <div className="space-y-4">
        {blocks.map((block, index) => {
          const codeFence = parseCodeFence(block);
          if (codeFence) {
            return (
              <AiCodeBlock
                code={codeFence.code}
                isIncomplete={codeFence.isIncomplete}
                key={`code-${index}`}
                language={codeFence.language}
              />
            );
          }

          if (!block.trim()) {
            return null;
          }

          return (
            <Streamdown
              className={proseClassName}
              isAnimating={isAnimating}
              key={`markdown-${index}`}
              mode={isAnimating ? "streaming" : "static"}
              plugins={streamdownPlugins}
              {...props}
            >
              {block}
            </Streamdown>
          );
        })}
      </div>
    );
  },
  (prevProps, nextProps) =>
    prevProps.children === nextProps.children &&
    prevProps.isAnimating === nextProps.isAnimating
);

MessageResponse.displayName = "MessageResponse";

export type MessageToolbarProps = ComponentProps<"div">;

export function MessageToolbar({
  children,
  className,
  ...props
}: MessageToolbarProps) {
  return (
    <div
      className={cn(
        "mt-4 flex w-full items-center justify-between gap-4 text-xs text-slate-500",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
