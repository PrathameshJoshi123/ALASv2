"use client";

import React, { useEffect, useState, useRef } from "react";
import {
  Sparkles,
  Loader2,
  CheckCircle2,
  AlertCircle,
  FileText,
  Search,
  Scale,
  ShieldCheck,
  ChevronRight,
  Terminal,
  Activity,
  Layers,
  Shield,
  Gavel,
} from "lucide-react";
import { apiClient } from "@/services/api";

export interface DraftEvent {
  document_id: string;
  milestone: string;
  stage: number;
  total_stages: number;
  progress_percentage: number;
  message: string;
  details?: Record<string, any>;
  is_complete?: boolean;
  is_error?: boolean;
  timestamp: string;
}

interface DraftingStreamConsoleProps {
  contractId: string;
  taskId?: string | null;
  prompt?: string | null;
  onComplete: (resolvedDocId?: string) => void;
  onError?: (err: any) => void;
}

const STAGES = [
  { id: 1, label: "Blueprint & Intake", icon: FileText, desc: "Resolving contract type and parties" },
  { id: 2, label: "Structure Mapping", icon: Terminal, desc: "Extracting section hierarchy & blueprint" },
  { id: 3, label: "Kanoon & Statutory Research", icon: Search, desc: "Live statutory search & Kanoon citations" },
  { id: 4, label: "Autonomous Clause Drafting", icon: Scale, desc: "Synthesizing section-by-section clauses" },
  { id: 5, label: "Compliance Review & Audit", icon: ShieldCheck, desc: "Verifying Sec 27, 74, 28 ICA & arbitration rules" },
  { id: 6, label: "Final Assembly", icon: CheckCircle2, desc: "Formatting document & compiling report" },
];

export function DraftingStreamConsole({
  contractId,
  taskId,
  prompt,
  onComplete,
  onError,
}: DraftingStreamConsoleProps) {
  const [events, setEvents] = useState<DraftEvent[]>([]);
  const [currentProgress, setCurrentProgress] = useState(10);
  const [currentStage, setCurrentStage] = useState(1);
  const [latestMessage, setLatestMessage] = useState("Initializing deterministic drafting orchestrator...");
  const [isConnected, setIsConnected] = useState(false);
  const [isDone, setIsDone] = useState(false);

  const [activeMeta, setActiveMeta] = useState<{
    contract_type?: string;
    favor_party?: string;
    governing_law?: string;
    drafting_style?: string;
    parties?: string[];
  }>({});

  const terminalEndRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll terminal
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  const [activeDocId, setActiveDocId] = useState<string>(() => {
    return (contractId && contractId !== "undefined" && contractId !== "null") ? contractId : "";
  });

  useEffect(() => {
    if (contractId && contractId !== "undefined" && contractId !== "null") {
      setActiveDocId(contractId);
    }
  }, [contractId]);

  // If activeDocId is missing, resolve it dynamically via taskId
  useEffect(() => {
    if (!activeDocId && taskId) {
      let interval: NodeJS.Timeout | null = null;
      const lookup = async () => {
        try {
          const res = await apiClient.getProcessingStatus("undefined", taskId);
          if (res?.document_id) {
            setActiveDocId(res.document_id);
            if (interval) clearInterval(interval);
          }
        } catch (e) {
          // ignore
        }
      };
      lookup();
      interval = setInterval(lookup, 1500);
      return () => {
        if (interval) clearInterval(interval);
      };
    }
  }, [activeDocId, taskId]);

  useEffect(() => {
    if (!activeDocId) return;

    let eventSource: EventSource | null = null;
    let pollInterval: NodeJS.Timeout | null = null;
    let completed = false;

    const handleNewEvent = (evt: DraftEvent) => {
      setEvents((prev) => {
        // Prevent duplicate events based on timestamp and milestone
        if (prev.some((e) => e.timestamp === evt.timestamp && e.milestone === evt.milestone)) {
          return prev;
        }
        return [...prev, evt];
      });

      if (evt.progress_percentage !== undefined) {
        setCurrentProgress(evt.progress_percentage);
      }
      if (evt.stage !== undefined) {
        setCurrentStage(evt.stage);
      }
      if (evt.message) {
        setLatestMessage(evt.message);
      }

      if (evt.details) {
        setActiveMeta((prev) => ({
          ...prev,
          contract_type: evt.details?.contract_type || prev.contract_type,
          favor_party: evt.details?.favor_party || prev.favor_party,
          governing_law: evt.details?.governing_law || prev.governing_law,
          drafting_style: evt.details?.drafting_style || prev.drafting_style,
          parties: evt.details?.parties || prev.parties,
        }));
      }

      if (evt.is_complete && !completed) {
        completed = true;
        setIsDone(true);
        setCurrentProgress(100);
        setCurrentStage(6);
        setTimeout(() => {
          onComplete(activeDocId);
        }, 1200);
      }

      if (evt.is_error) {
        onError?.(evt.message);
      }
    };

    // 1. Establish SSE Connection
    try {
      const streamUrl = apiClient.getDraftStreamUrl(activeDocId);
      eventSource = new EventSource(streamUrl);

      eventSource.onopen = () => {
        setIsConnected(true);
      };

      eventSource.onmessage = (e) => {
        try {
          const parsed: DraftEvent = JSON.parse(e.data);
          handleNewEvent(parsed);
        } catch (err) {
          console.error("SSE Parse Error:", err);
        }
      };

      eventSource.onerror = (err) => {
        console.warn("SSE Connection error, falling back to polling", err);
        setIsConnected(false);
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }
      };
    } catch (sseErr) {
      console.warn("Could not initiate EventSource", sseErr);
      setIsConnected(false);
    }

    // 2. Auxiliary Polling Fallback (in case SSE fails or proxy drops connection)
    const pollEvents = async () => {
      try {
        const res = await apiClient.getDraftEvents(activeDocId);
        if (Array.isArray(res?.events)) {
          res.events.forEach((evt: DraftEvent) => handleNewEvent(evt));
        }
        if (res?.is_complete && !completed) {
          completed = true;
          setIsDone(true);
          setCurrentProgress(100);
          setCurrentStage(6);
          setTimeout(() => {
            onComplete(activeDocId);
          }, 1200);
        }
      } catch (pollErr) {
        // ignore
      }
    };

    // Check immediately and every 2.5 seconds
    pollEvents();
    pollInterval = setInterval(pollEvents, 2500);

    return () => {
      if (eventSource) {
        eventSource.close();
      }
      if (pollInterval) {
        clearInterval(pollInterval);
      }
    };
  }, [activeDocId, onComplete, onError]);

  return (
    <div className="flex w-full min-h-[600px] bg-slate-950 items-center justify-center p-4 lg:p-8 rounded-xl font-sans">
      <div className="w-full max-w-5xl bg-slate-900 border border-slate-800 rounded-xl p-6 lg:p-8 shadow-xl flex flex-col gap-6">
        {/* Header Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800 pb-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-blue-400">
              <Scale className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-100 tracking-tight flex items-center gap-2">
                Deterministic Contract Generation
                <span className="px-2 py-0.5 rounded bg-blue-500/10 border border-blue-500/20 text-blue-400 text-[10px] font-semibold uppercase tracking-wider">
                  LangGraph V2.4
                </span>
              </h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Autonomous legal orchestrator with Indian Kanoon precedent integration
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800/80 border border-slate-700 text-xs font-medium text-slate-300">
              <span
                className={`w-2 h-2 rounded-full ${
                  isDone
                    ? "bg-emerald-400"
                    : isConnected
                    ? "bg-emerald-400 animate-pulse"
                    : "bg-amber-400"
                }`}
              />
              <span>{isDone ? "Completed" : isConnected ? "Live Agent Stream" : "Syncing Updates"}</span>
            </div>
            <div className="text-xl font-bold text-blue-400 tracking-tight font-mono">
              {currentProgress}%
            </div>
          </div>
        </div>

        {/* Dynamic Progress Bar */}
        <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden relative">
          <div
            className="h-full bg-blue-500 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${currentProgress}%` }}
          />
        </div>

        {/* Active Blueprint & Configuration Context Bar */}
        {(activeMeta.contract_type || activeMeta.favor_party || activeMeta.governing_law || prompt) && (
          <div className="flex flex-wrap items-center gap-2 p-3 rounded-lg bg-slate-950/70 border border-slate-800/80 text-xs">
            <span className="text-slate-400 font-semibold uppercase tracking-wider text-[10px] flex items-center gap-1">
              <Layers className="w-3 h-3 text-blue-400" />
              Active Blueprint:
            </span>
            {activeMeta.contract_type && (
              <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20 font-medium text-[11px]">
                {activeMeta.contract_type}
              </span>
            )}
            {activeMeta.favor_party && (
              <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 font-medium text-[11px]">
                Posture: {activeMeta.favor_party}
              </span>
            )}
            {activeMeta.governing_law && (
              <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 font-medium text-[11px]">
                {activeMeta.governing_law}
              </span>
            )}
            {activeMeta.drafting_style && (
              <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 font-medium text-[11px]">
                Style: {activeMeta.drafting_style}
              </span>
            )}
            {activeMeta.parties && activeMeta.parties.length > 0 && (
              <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 font-medium text-[11px]">
                Parties: {activeMeta.parties.join(" & ")}
              </span>
            )}
          </div>
        )}

        {/* Milestone Steps Timeline */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2.5">
          {STAGES.map((s) => {
            const Icon = s.icon;
            const isCompleted = currentStage > s.id || isDone;
            const isCurrent = currentStage === s.id && !isDone;

            return (
              <div
                key={s.id}
                className={`p-3 rounded-lg border transition-all flex flex-col gap-1.5 ${
                  isCompleted
                    ? "bg-slate-800/40 border-blue-500/30 text-blue-200"
                    : isCurrent
                    ? "bg-blue-950/40 border-blue-500 text-white ring-1 ring-blue-500/30"
                    : "bg-slate-950/40 border-slate-800 text-slate-500"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div
                    className={`w-6 h-6 rounded flex items-center justify-center ${
                      isCompleted
                        ? "bg-blue-500/20 text-blue-300"
                        : isCurrent
                        ? "bg-blue-600 text-white animate-pulse"
                        : "bg-slate-800 text-slate-500"
                    }`}
                  >
                    {isCompleted ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <Icon className="w-3 h-3" />
                    )}
                  </div>
                  <span className="text-[10px] font-bold tracking-wider opacity-60 font-mono">
                    0{s.id}
                  </span>
                </div>
                <div>
                  <h4 className="text-[11px] font-bold tracking-tight line-clamp-1">{s.label}</h4>
                  <p className="text-[9px] opacity-70 line-clamp-1 mt-0.5">{s.desc}</p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Live Terminal / Agent Activity Log */}
        <div className="bg-slate-950 border border-slate-800 rounded-lg p-4 flex flex-col gap-2.5 font-mono">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2 px-1">
            <div className="flex items-center gap-2 text-xs text-slate-400 font-semibold">
              <Terminal className="w-3.5 h-3.5 text-blue-400" />
              <span>Real-Time Autonomous Agent Stream</span>
            </div>
            <div className="flex items-center gap-2 text-[11px] text-slate-500">
              <Activity className="w-3 h-3 text-emerald-400 animate-pulse" />
              <span>{events.length} events emitted</span>
            </div>
          </div>

          {/* Terminal log messages container */}
          <div className="h-[210px] overflow-y-auto pr-2 space-y-1.5 text-xs custom-scrollbar">
            {events.length === 0 ? (
              <div className="flex items-center gap-3 text-slate-500 py-6 justify-center">
                <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                <span>Connecting to LangGraph agent execution channel...</span>
              </div>
            ) : (
              events.map((evt, idx) => {
                const isKanoon = evt.milestone.includes("KANOON") || evt.milestone.includes("LEGAL");
                const isSection = evt.milestone.includes("SECTION");
                const isAudit = evt.milestone.includes("AUDIT") || evt.milestone.includes("COMPLIANCE");
                const isLast = idx === events.length - 1;

                return (
                  <div
                    key={idx}
                    className={`flex items-start gap-2.5 py-1 px-2 rounded transition-colors ${
                      isLast ? "bg-slate-900 border border-blue-500/30" : "hover:bg-slate-900/40"
                    }`}
                  >
                    <span className="text-[10px] text-slate-500 shrink-0 pt-0.5">
                      {new Date(evt.timestamp).toLocaleTimeString()}
                    </span>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase shrink-0 ${
                        isKanoon
                          ? "bg-amber-500/10 text-amber-300 border border-amber-500/20"
                          : isSection
                          ? "bg-blue-500/10 text-blue-300 border border-blue-500/20"
                          : isAudit
                          ? "bg-purple-500/10 text-purple-300 border border-purple-500/20"
                          : "bg-slate-800 text-slate-300"
                      }`}
                    >
                      {evt.milestone}
                    </span>
                    <p
                      className={`text-[11px] leading-relaxed break-words ${
                        isLast ? "text-slate-100 font-medium" : "text-slate-400"
                      }`}
                    >
                      {evt.message}
                    </p>
                  </div>
                );
              })
            )}
            <div ref={terminalEndRef} />
          </div>
        </div>
      </div>
    </div>
  );
}
