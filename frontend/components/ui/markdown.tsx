"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import { cn } from "@/lib/utils";

export interface MarkdownProps {
  content?: string | null;
  className?: string;
  inline?: boolean;
}

/**
 * Normalizes legal markdown prose so that packed section headers, numbered items,
 * and inline sub-bullet points are given clean paragraph line breaks.
 */
export function formatLegalMarkdown(raw: string): string {
  if (!raw || typeof raw !== "string") return "";
  let s = raw.trim();

  // 1. Separate clause title from first numbered item:
  // e.g. "**TERM AND EXTENSION** 1." -> "**TERM AND EXTENSION**\n\n1."
  s = s.replace(/(\*\*[A-Z\s0-9,&'-]{3,}\*\*)\s+(\d+\.)/g, "$1\n\n$2");

  // 2. Separate packed numbered sections:
  // e.g. "herein. 2. **Extension" -> "herein.\n\n2. **Extension"
  s = s.replace(/([.!?]|\*\*)\s+(\d+\.\s+\*\*)/g, "$1\n\n$2");
  s = s.replace(/([.!?])\s+(\d+\.\s+)/g, "$1\n\n$2");

  // 3. Separate packed inline bullet points:
  // e.g. "Mechanism**: - **Automatic Renewal**:" -> "Mechanism**:\n   - **Automatic Renewal**:"
  s = s.replace(/([.:!?])\s+-\s+(\*\*)/g, "$1\n   - $2");
  s = s.replace(/([.:!?])\s+-\s+([A-Za-z0-9])/g, "$1\n   - $2");

  // 4. Separate packed sub-clauses or capital headings at the end:
  // e.g. "other Party. **SAVINGS CLAUSE**:" -> "other Party.\n\n**SAVINGS CLAUSE**:"
  s = s.replace(/([.!?])\s+(\*\*[A-Z\s0-9,&'-]{4,}\*\*:?)/g, "$1\n\n$2");

  return s;
}

/**
 * Universal Markdown Renderer for ALAS
 * Renders legal prose, citations, statutory analysis, and AI reasoning
 * adhering to institutional typography without raw markdown artifacts (**bold**, etc.).
 */
export function Markdown({ content, className, inline = false }: MarkdownProps) {
  if (!content || typeof content !== "string") {
    return null;
  }

  const processedContent = inline ? content : formatLegalMarkdown(content);

  return (
    <div
      className={cn(
        "legal-markdown leading-relaxed text-foreground/90",
        inline
          ? "inline [&>p]:inline [&>p]:m-0 [&_*]:inline"
          : "text-xs space-y-2 [&_p]:leading-relaxed [&_p:last-child]:mb-0 [&_strong]:font-semibold [&_strong]:text-foreground [&_em]:italic [&_ul]:list-disc [&_ul]:pl-4 [&_ul]:my-1.5 [&_ol]:list-decimal [&_ol]:pl-4 [&_ol]:my-1.5 [&_li]:my-0.5 [&_blockquote]:border-l-2 [&_blockquote]:border-primary/40 [&_blockquote]:pl-2.5 [&_blockquote]:italic [&_code]:font-mono [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-[11px]",
        className,
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        components={{
          a: ({ node, ...props }) => (
            <a
              {...props}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#2563EB] hover:underline font-medium inline-flex items-center gap-0.5"
            />
          ),
          p: ({ node, ...props }) =>
            inline ? (
              <span {...props} />
            ) : (
              <p className="mb-2 last:mb-0 leading-relaxed" {...props} />
            ),
        }}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
}

// Export both Markdown and LegalMarkdown aliases for backwards compatibility
export { Markdown as LegalMarkdown };
export default Markdown;

