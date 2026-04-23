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
        "group flex w-full max-w-[92%] flex-col gap-2",
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
        "group-[.is-user]:ml-auto group-[.is-user]:max-w-[78%] group-[.is-user]:rounded-[22px] group-[.is-user]:rounded-br-md group-[.is-user]:bg-primary group-[.is-user]:px-4 group-[.is-user]:py-3 group-[.is-user]:text-primary-foreground group-[.is-user]:shadow-sm",
        "group-[.is-assistant]:text-foreground",
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
      "max-w-none text-[15px] leading-8 text-foreground",
      "[&>*:first-child]:mt-0 [&>*:last-child]:mb-0",
      "[&_a]:text-primary [&_a]:underline [&_a]:underline-offset-4",
      "[&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-4 [&_blockquote]:text-muted-foreground",
      "[&_code]:rounded-md [&_code]:bg-muted/40 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:text-[0.92em]",
      "[&_table]:w-full [&_table]:border-collapse [&_table]:overflow-hidden",
      "[&_td]:border-t [&_td]:border-border [&_td]:px-3 [&_td]:py-2 [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_th]:text-muted-foreground",
      className
    );

    return (
      <div className="flex flex-col gap-4">
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
        "mt-4 flex w-full items-center justify-between gap-4 text-xs text-muted-foreground",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
