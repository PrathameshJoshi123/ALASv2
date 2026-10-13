"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { Bot, Loader2, Send, X, Maximize2, Minimize2 } from "lucide-react";
import toast from "react-hot-toast";
import { marked } from "marked";
import DOMPurify from "dompurify";
import { apiClient } from "@/services/api";

interface QAItem {
  id: string;
  question: string;
  answer: string;
  answerHtml: string;
  isPending: boolean;
  isError: boolean;
}

interface JuristChatDrawerProps {
  contractId: string;
  isOpen: boolean;
  onClose: () => void;
}

export function JuristChatDrawer({ contractId, isOpen, onClose }: JuristChatDrawerProps) {
  const [qaInput, setQaInput] = useState("");
  const [qaLoading, setQaLoading] = useState(false);
  const [qaHistory, setQaHistory] = useState<QAItem[]>([]);
  const [isFullView, setIsFullView] = useState(false);

  const qaThreadRef = useRef<HTMLDivElement | null>(null);
  const qaInputRef = useRef<HTMLTextAreaElement | null>(null);

  const renderMarkdownToHtml = useCallback(async (content: string) => {
    try {
      marked.setOptions({
        gfm: true,
        breaks: true,
      });

      const rendered = marked.parse(content);
      const renderedHtml = typeof rendered === "string" ? rendered : await rendered;
      return DOMPurify.sanitize(renderedHtml);
    } catch (err) {
      const escaped = DOMPurify.sanitize(content, { ALLOWED_TAGS: [] });
      return `<p>${escaped}</p>`;
    }
  }, []);

  // Fetch saved chat history from backend database on drawer open
  useEffect(() => {
    if (!isOpen || !contractId) return;

    let isMounted = true;
    apiClient
      .getContractQAHistory(contractId)
      .then(async (res) => {
        if (!isMounted || !res?.history || !Array.isArray(res.history)) return;

        const parsedItems: QAItem[] = await Promise.all(
          res.history.map(async (msg: any) => {
            let answerText = msg.answer || "";
            if (msg.citations && Array.isArray(msg.citations) && msg.citations.length > 0) {
              answerText += "\n\n---\n**Citations / References:**\n";
              msg.citations.forEach((c: any, idx: number) => {
                const pages = c.page_start
                  ? ` (Page ${c.page_start}${c.page_end && c.page_end !== c.page_start ? `-${c.page_end}` : ""})`
                  : "";
                const quote = c.content ? `\n> "${c.content}"` : "";
                answerText += `\n${idx + 1}. **Chunk ${c.chunk_id || idx + 1}**${pages}${quote}`;
              });
            }
            const answerHtml = await renderMarkdownToHtml(answerText);
            return {
              id: msg.id || `${Date.now()}-${Math.random().toString(36).slice(2)}`,
              question: msg.question,
              answer: answerText,
              answerHtml,
              isPending: false,
              isError: false,
            };
          }),
        );

        if (parsedItems.length > 0) {
          setQaHistory(parsedItems);
        }
      })
      .catch(() => {});

    return () => {
      isMounted = false;
    };
  }, [isOpen, contractId, renderMarkdownToHtml]);

  const handleClearThread = async () => {
    if (!contractId) return;
    try {
      await apiClient.clearContractQAHistory(contractId);
      setQaHistory([]);
      toast.success("Chat history cleared from database.");
    } catch {
      setQaHistory([]);
    }
  };


  const handleAskQuestion = async (overridePrompt?: string) => {
    const question = (overridePrompt || qaInput).trim();
    if (!contractId || !question || qaLoading) return;

    const pendingId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;

    setQaInput("");
    setQaHistory((prev) => [
      ...prev,
      {
        id: pendingId,
        question,
        answer: "",
        answerHtml: "",
        isPending: true,
        isError: false,
      },
    ]);

    setQaLoading(true);

    try {
      const response = await apiClient.askContractQuestion(contractId, question);
      let answerText =
        response?.answer || response?.detail || response?.error || "No answer returned.";

      if (
        response?.citations &&
        Array.isArray(response.citations) &&
        response.citations.length > 0
      ) {
        answerText += "\n\n---\n**Citations / References:**\n";
        response.citations.forEach((c: any, idx: number) => {
          const pages = c.page_start
            ? ` (Page ${c.page_start}${c.page_end && c.page_end !== c.page_start ? `-${c.page_end}` : ""})`
            : "";
          const quote = c.content ? `\n> "${c.content}"` : "";
          answerText += `\n${idx + 1}. **Chunk ${c.chunk_id || idx + 1}**${pages}${quote}`;
        });
      }

      const answerHtml = await renderMarkdownToHtml(answerText);

      setQaHistory((prev) =>
        prev.map((item) =>
          item.id === pendingId
            ? {
                ...item,
                answer: answerText,
                answerHtml,
                isPending: false,
                isError: false,
              }
            : item,
        ),
      );
    } catch (error: any) {
      const serverDetail = error?.response?.data?.detail;
      toast.error(serverDetail || "Failed to get AI answer.");
      const errorText = serverDetail
        ? `**Error:** ${serverDetail}`
        : "Request failed. Please check your connection and try again.";
      const errorHtml = await renderMarkdownToHtml(errorText);

      setQaHistory((prev) =>
        prev.map((item) =>
          item.id === pendingId
            ? {
                ...item,
                answer: errorText,
                answerHtml: errorHtml,
                isPending: false,
                isError: true,
              }
            : item,
        ),
      );
    } finally {
      setQaLoading(false);
    }
  };

  useEffect(() => {
    if (!isOpen || !qaThreadRef.current) return;

    qaThreadRef.current.scrollTo({
      top: qaThreadRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [qaHistory, qaLoading, isOpen]);

  const quickPrompts = [
    "Summarize top negotiation priorities and statutory risks.",
    "Are non-compete and restraint of trade clauses valid under Section 27 ICA?",
    "What are the main liability caps, liquidated damages, and indemnities?",
  ];

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop when in Full View Modal mode */}
      {isFullView && (
        <div
          onClick={() => setIsFullView(false)}
          className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200"
        />
      )}

      <div
        className={
          isFullView
            ? "fixed inset-4 sm:inset-10 lg:inset-16 z-50 bg-gradient-to-b from-[#F4F7FB] to-[#EEF3FB] shadow-2xl rounded-2xl border border-slate-300 flex flex-col animate-in zoom-in-95 duration-200 overflow-hidden"
            : "fixed inset-y-0 right-0 z-50 w-full max-w-[440px] bg-gradient-to-b from-[#F4F7FB] to-[#EEF3FB] shadow-[-10px_0_30px_rgba(0,0,0,0.15)] border-l border-slate-200/80 flex flex-col animate-in slide-in-from-right duration-300"
        }
      >
        {/* Header */}
        <div className="px-6 pt-5 pb-4 border-b border-slate-200/70 bg-white/80 backdrop-blur-xl shrink-0">
          <div className="flex items-center gap-4">
            <div className="w-11 h-11 rounded-xl bg-[#0B1437] flex items-center justify-center shrink-0 shadow-[0_8px_20px_rgba(11,20,55,0.2)]">
              <Bot className="w-5 h-5 text-blue-400" strokeWidth={2.5} />
            </div>
            <div>
              <h3 className="font-extrabold text-[17px] text-slate-900 tracking-tight leading-none mb-1">
                Jurist AI Assistant
              </h3>
              <span className="text-[10px] font-bold tracking-[0.15em] text-[#3B5FE5] uppercase inline-flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                Autonomous LangGraph RAG
              </span>
            </div>
            <div className="ml-auto flex items-center gap-2">
              {qaHistory.length > 0 && (
                <span className="px-2.5 py-1 rounded-full bg-slate-100 border border-slate-200 text-[10px] font-semibold text-slate-500">
                  {qaHistory.length} turns
                </span>
              )}
              {/* Full View Big Modal Toggle */}
              <button
                type="button"
                onClick={() => setIsFullView(!isFullView)}
                title={isFullView ? "Exit Full View" : "Open in Full View Modal"}
                className="w-9 h-9 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-600 flex items-center justify-center transition-colors"
              >
                {isFullView ? (
                  <Minimize2 className="w-4 h-4" />
                ) : (
                  <Maximize2 className="w-4 h-4" />
                )}
              </button>
              <button
                onClick={onClose}
                className="w-9 h-9 rounded-full bg-slate-200/60 hover:bg-slate-200 text-slate-600 flex items-center justify-center transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Main Body */}
        <div className="px-5 pt-4 pb-5 flex-1 min-h-0 flex flex-col gap-3">
          <div className="flex items-center justify-between px-1">
            <span className="text-[11px] font-bold tracking-[0.14em] uppercase text-slate-500">
              Contract Q&A Thread
            </span>
            {qaHistory.length > 0 && (
              <button
                type="button"
                onClick={handleClearThread}
                className="text-[10px] font-semibold text-slate-400 hover:text-slate-600 transition-colors"
              >
                Clear Thread
              </button>
            )}
          </div>


        <div
          ref={qaThreadRef}
          className={`flex-1 min-h-0 px-1 overflow-y-auto ${qaHistory.length > 0 ? "space-y-5" : ""}`}
        >
          {qaHistory.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center px-4 py-8">
              <div className="w-12 h-12 rounded-2xl bg-white shadow-sm border border-slate-200 flex items-center justify-center mb-3">
                <Bot className="w-6 h-6 text-[#3B5FE5]" />
              </div>
              <h4 className="text-[15px] font-bold text-slate-800 mb-1">
                Ask Jurist AI Anything
              </h4>
              <p className="text-[12px] text-slate-500 mb-6 max-w-[260px] leading-relaxed">
                Query contract clauses, check specific obligations, or ask grounded legal questions directly.
              </p>
              <div className="flex flex-col gap-2 w-full max-w-[320px]">
                {quickPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => handleAskQuestion(prompt)}
                    className="w-full px-4 py-3 rounded-xl bg-white border border-slate-200 hover:border-[#3B5FE5]/30 hover:bg-blue-50/50 text-[11px] font-medium text-slate-600 transition-all text-left shadow-sm flex items-center justify-between group"
                  >
                    <span className="truncate pr-2">{prompt}</span>
                    <div className="w-5 h-5 rounded-md bg-slate-100 flex items-center justify-center group-hover:bg-[#3B5FE5] group-hover:text-white transition-colors shrink-0">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-5 pb-2">
              {qaHistory.map((item) => (
                <React.Fragment key={item.id}>
                  {/* User Question */}
                  <div className="flex justify-end pl-8">
                    <div className="bg-[#0B1437] text-white rounded-2xl rounded-tr-sm px-4 py-3 shadow-sm border border-[#1C2B62]">
                      <p className="text-[13px] leading-relaxed whitespace-pre-wrap">
                        {item.question}
                      </p>
                    </div>
                  </div>

                  {/* AI Response */}
                  <div className="flex justify-start pr-2">
                    <div className="flex gap-2.5 w-full">
                      <div className="w-7 h-7 rounded-full bg-white border border-slate-200 flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
                        <Bot className="w-4 h-4 text-[#3B5FE5]" />
                      </div>
                      <div className="flex-1 min-w-0">
                        {item.isPending ? (
                          <div className="flex items-center gap-2 text-[13px] text-slate-500 h-8">
                            <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
                            <span>Retrieving contract context & analyzing...</span>
                          </div>
                        ) : (
                          <div
                            className={`contract-markdown markdown-body max-w-none text-[13px] leading-relaxed bg-white rounded-2xl rounded-tl-sm px-4 py-3.5 border border-slate-200 shadow-sm ${item.isError ? "text-red-600" : "text-slate-700"}`}
                            dangerouslySetInnerHTML={{
                              __html: item.answerHtml,
                            }}
                          />
                        )}
                      </div>
                    </div>
                  </div>
                </React.Fragment>
              ))}
            </div>
          )}
        </div>

        {/* Composer */}
        <div className="shrink-0 flex flex-col gap-2 mt-2">
          {qaHistory.length > 0 && (
            <div className="flex flex-wrap gap-1.5 px-1">
              {quickPrompts.slice(0, 2).map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => handleAskQuestion(prompt)}
                  className="px-2.5 py-1 rounded-full bg-white border border-slate-200 hover:border-[#3B5FE5]/30 hover:bg-blue-50/50 text-[10px] font-medium text-slate-600 transition-colors shadow-sm truncate max-w-[200px]"
                >
                  {prompt}
                </button>
              ))}
            </div>
          )}

          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden focus-within:ring-2 focus-within:ring-[#3B5FE5] transition-all">
            <textarea
              ref={qaInputRef}
              placeholder="Ask a question about this contract document..."
              value={qaInput}
              onChange={(e) => setQaInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleAskQuestion();
                }
              }}
              className="w-full h-[90px] resize-none outline-none text-[13px] text-slate-800 placeholder:text-slate-400 font-medium leading-[1.6] bg-transparent p-4 custom-scrollbar"
            />
            <div className="flex items-center justify-between px-4 pb-3">
              <span className="text-[10px] text-slate-400 font-medium">
                Enter to send, Shift+Enter for newline
              </span>
              <button
                type="button"
                disabled={!qaInput.trim() || qaLoading}
                onClick={() => handleAskQuestion()}
                className="w-8 h-8 rounded-xl bg-[#0B1437] hover:bg-[#152458] disabled:opacity-40 text-white flex items-center justify-center transition-all shadow-sm"
              >
                {qaLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-3.5 h-3.5" />
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
      </div>
    </>
  );
}


