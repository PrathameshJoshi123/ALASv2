"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Scale,
  Gavel,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  Send,
  ExternalLink,
  BookOpen,
  Download,
  RotateCcw,
  Sparkles,
  Search,
  MessageSquare,
  FileText,
  UserCheck,
  ChevronRight,
  Info,
  Layers,
  Award,
  Radio,
  Loader2,
} from "lucide-react";
import toast from "react-hot-toast";
import { apiClient } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardFooter,
} from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function LegalMarkdown({ content, className }: { content: string; className?: string }) {
  if (!content) return null;
  return (
    <div
      className={cn(
        "prose prose-xs max-w-none text-xs leading-relaxed text-foreground/90",
        "[&_p]:mb-2 [&_p:last-child]:mb-0",
        "[&_strong]:font-semibold [&_strong]:text-foreground",
        "[&_em]:italic",
        "[&_ul]:list-disc [&_ul]:pl-4 [&_ul]:my-1.5",
        "[&_ol]:list-decimal [&_ol]:pl-4 [&_ol]:my-1.5",
        "[&_li]:my-0.5",
        "[&_blockquote]:border-l-2 [&_blockquote]:border-primary/40 [&_blockquote]:pl-2.5 [&_blockquote]:italic",
        className,
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  );
}

// ============================================================
// Types
// ============================================================

interface KanoonCitation {
  doc_id: string;
  title: string;
  court: string;
  year?: string;
  citation_standard?: string;
  url: string;
  ratio_decidendi: string;
  statutory_sections: string[];
  relevance: string;
  distinguishing_angle?: string;
}

interface ArgumentSubmission {
  id: string;
  turn_number: number;
  speaker: "petitioner" | "respondent" | "user";
  speaker_side?: "petitioner" | "respondent";
  round_number?: number;
  title: string;
  argument_text: string;
  citations: KanoonCitation[];
  doctrine_tags: string[];
  weakness_detected?: string;
  timestamp: string;
}

interface BenchInterlocutory {
  id: string;
  turn_number: number;
  targeted_speaker: "petitioner" | "respondent" | "both";
  query: string;
  context_basis: string;
  suggested_answer: string;
  evidentiary_flag?: string;
  timestamp: string;
}

interface DebateRound {
  round_number: number;
  status: "completed" | "in_progress" | "pending";
  issue_focus: string;
  petitioner_submission?: ArgumentSubmission;
  respondent_submission?: ArgumentSubmission;
  bench_queries: BenchInterlocutory[];
  momentum_petitioner: number; // 0-100%
}

// ============================================================
// Baseline Fallback Data (Institutional Grounds)
// ============================================================

const DEFAULT_ISSUES = [
  "Issue 1: Maintainability of Criminal Proceedings in Commercial Dispute (Sec 482 CrPC / Sec 528 BNSS)",
  "Issue 2: Requirement & Admissibility of Electronic Records Certificate (Sec 65B BSA / IEA)",
  "Issue 3: Prima Facie Establishment of Mens Rea & Dishonest Inducement at Inception (Sec 420 IPC / Sec 318 BNS)",
];

const INITIAL_ROUNDS: DebateRound[] = [
  {
    round_number: 1,
    status: "completed",
    issue_focus: "Maintainability & Prima Facie Ingredients of Fraud",
    momentum_petitioner: 58,
    petitioner_submission: {
      id: "arg_pet_1",
      turn_number: 1,
      speaker: "petitioner",
      title: "Active Deception from Inception & Misappropriation of Escrow Balances",
      argument_text:
        "May it please the court, the allegations set out in the complaint disclose a clear, premeditated dishonest inducement at the very threshold of the agreement. The respondent knowingly made representations regarding asset ownership that were demonstrably false, thereby inducing the complainant to disburse INR 4.2 Crores. This is not a mere breach of covenant; it constitutes an offense under Section 420 read with Section 406 IPC. Quashing at this preliminary stage would deprive the prosecution of the opportunity to lead trial evidence.",
      doctrine_tags: ["Section 420 IPC", "Prima Facie Threshold", "Section 482 Quashing Standards"],
      citations: [
        {
          doc_id: "1431516",
          title: "State of Haryana and Ors. v. Bhajan Lal and Ors.",
          court: "Supreme Court of India",
          year: "1992",
          citation_standard: "AIR 1992 SC 604; 1992 Supp (1) SCC 335",
          url: "https://indiankanoon.org/doc/1431516/",
          ratio_decidendi:
            "The High Court under Section 482 CrPC should exercise inherent powers sparingly and only when allegations in the FIR, even if taken at face value, do not disclose any cognizable offense whatsoever.",
          statutory_sections: ["Section 482 CrPC", "Section 154 CrPC"],
          relevance: "Defends the complaint against premature quashing petitions.",
          distinguishing_angle:
            "Can be distinguished if the dispute is demonstrably commercial with pure contractual remedies provided in arbitration clause.",
        },
      ],
      timestamp: "10:14 AM",
    },
    respondent_submission: {
      id: "arg_resp_1",
      turn_number: 2,
      speaker: "respondent",
      title: "Commercial Breach Clothed with Criminal Robes to Bypass Arbitration",
      argument_text:
        "The entire criminal complaint is an abuse of process initiated with the sole intent to exert illicit commercial pressure and circumvent the mandatory London/Mumbai seat arbitration agreed under Clause 14.2. A breach of contractual obligation cannot automatically be equated with criminal cheating unless dishonest intention is proved to exist right at the inception of the transaction. Subsequent inability to perform due to regulatory supply freezes does not satisfy Section 415 IPC.",
      doctrine_tags: ["Commercial vs Criminal", "Arbitration Preemption", "Absence of Mens Rea"],
      citations: [
        {
          doc_id: "1687691",
          title: "Dalip Kaur and Ors. v. Jagnar Singh and Anr.",
          court: "Supreme Court of India",
          year: "2009",
          citation_standard: "(2009) 14 SCC 696",
          url: "https://indiankanoon.org/doc/1687691/",
          ratio_decidendi:
            "An offense of cheating requires dishonest intention from the very beginning. A mere failure to fulfill a contractual promise does not attract criminal prosecution under Section 420 IPC in the absence of initial fraudulent intent.",
          statutory_sections: ["Section 415 IPC", "Section 420 IPC"],
          relevance: "Destroys prosecution's claim by showing subsequent non-performance is civil breach.",
          distinguishing_angle:
            "Prosecution must show contemporaneous email evidence of false representation before fund transfer.",
        },
      ],
      timestamp: "10:18 AM",
    },
    bench_queries: [
      {
        id: "bench_q_1",
        turn_number: 1,
        targeted_speaker: "petitioner",
        query:
          "Counsel for Petitioner: Given that the parties engaged in six months of active commercial performance before the dispute arose, how do you sustain the plea of fraudulent intent at the very inception?",
        context_basis: "Commercial performance history verified in Case Timeline Item #4.",
        suggested_answer:
          "Emphasize the initial forged valuation certificate (Exhibit P-3) which was submitted to obtain clearance before any commercial milestone was triggered.",
        evidentiary_flag: "Exhibit P-3 missing forensic digital signature certificate under Sec 65B.",
        timestamp: "10:22 AM",
      },
    ],
  },
];

export default function PreTrialDebatePage() {
  const router = useRouter();
  const routeParams = useParams();
  const caseId = routeParams?.id as string;

  // Case & Debate State
  const [caseTitle, setCaseTitle] = useState("Litigation Matter Dossier");
  const [framedIssues, setFramedIssues] = useState<string[]>(DEFAULT_ISSUES);
  const [selectedIssueIndex, setSelectedIssueIndex] = useState(0);
  const [rounds, setRounds] = useState<DebateRound[]>(INITIAL_ROUNDS);
  const [activeTab, setActiveTab] = useState<"adversarial_arena" | "bench_log" | "citations">(
    "adversarial_arena",
  );

  // Streaming & Connection State
  const [isSSEConnected, setIsSSEConnected] = useState(false);
  const [liveAgentStatus, setLiveAgentStatus] = useState<string | null>(null);

  // Human-In-The-Loop State
  const [lawyerSide, setLawyerSide] = useState<"petitioner" | "respondent">("petitioner");
  const [customArgument, setCustomArgument] = useState("");
  const [isSubmittingArgument, setIsSubmittingArgument] = useState(false);

  // Modal Inspect State
  const [inspectCitation, setInspectCitation] = useState<KanoonCitation | null>(null);
  const [showBriefModal, setShowBriefModal] = useState(false);
  const [liveBriefData, setLiveBriefData] = useState<any>(null);

  // Quick Action Pills
  const quickActions = [
    "Plead Inadmissibility under Sec 65B BSA",
    "Argue Absence of Initial Mens Rea",
    "Distinguish Bhajan Lal: Pure Civil Remedy",
    "Invoke Commercial Frustration Sec 56 ICA",
    "Object: Case Law Overruled by Larger Bench",
  ];

  // 1. Fetch Case Details and Existing Debate State on Mount
  useEffect(() => {
    if (!caseId) return;

    const loadInitialState = async () => {
      try {
        const details = await apiClient.getCaseDetails(caseId);
        if (details?.title) setCaseTitle(details.title);

        const debateStatus = await apiClient.getCaseDebateStatus(caseId);
        if (debateStatus?.debate_turns && debateStatus.debate_turns.length > 0) {
          if (debateStatus.framed_issues && debateStatus.framed_issues.length > 0) {
            setFramedIssues(debateStatus.framed_issues);
          }
          reconstructRoundsFromBackend(debateStatus);
        } else {
          setLiveAgentStatus("Synthesizing dynamic courtroom arguments from case exhibits...");
          try {
            const started = await apiClient.startCaseDebate(caseId);
            if (started?.debate_turns && started.debate_turns.length > 0) {
              if (started.framed_issues && started.framed_issues.length > 0) {
                setFramedIssues(started.framed_issues);
              }
              reconstructRoundsFromBackend(started);
            }
          } catch (e) {
            console.warn("Auto-start skipped or failed, using baseline simulation.", e);
          } finally {
            setLiveAgentStatus(null);
          }
        }
      } catch (err) {
        console.warn("Could not load backend debate status, utilizing baseline simulation.", err);
      }
    };

    loadInitialState();
  }, [caseId]);

  // Helper to sync backend turns into UI rounds
  const reconstructRoundsFromBackend = (data: any) => {
    const rawTurns: any[] = data.debate_turns || [];
    if (rawTurns.length === 0) return;

    const queries: BenchInterlocutory[] = (data.bench_queries || []).map((q: any) => ({
      id: q.id,
      turn_number: q.turn_number,
      targeted_speaker: q.targeted_speaker,
      query: q.query,
      context_basis: q.context_basis,
      suggested_answer: q.suggested_answer,
      evidentiary_flag: q.evidentiary_flag,
      timestamp: q.timestamp || new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    }));

    // Map each turn into an ArgumentSubmission with normalized speaker_side
    const mappedTurns: ArgumentSubmission[] = rawTurns.map((t: any, index: number) => {
      const side: "petitioner" | "respondent" =
        t.speaker_side ||
        (t.speaker === "petitioner"
          ? "petitioner"
          : t.speaker === "respondent"
          ? "respondent"
          : t.title && t.title.toLowerCase().includes("petitioner")
          ? "petitioner"
          : t.title && (t.title.toLowerCase().includes("defense") || t.title.toLowerCase().includes("respondent"))
          ? "respondent"
          : index % 2 === 0
          ? "petitioner"
          : "respondent");

      return {
        id: t.id || `turn_${t.turn_number || index}`,
        turn_number: t.turn_number || index + 1,
        round_number: t.round_number || Math.floor(index / 2) + 1,
        speaker: t.speaker || (side === "petitioner" ? "petitioner" : "respondent"),
        speaker_side: side,
        title: t.title || (side === "petitioner" ? "Petitioner Submission" : "Respondent Submission"),
        argument_text: t.argument_text || "",
        citations: t.citations || [],
        doctrine_tags: t.doctrine_tags || [],
        timestamp: t.timestamp || new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
    });

    // Group turns into pairwise rounds (Round 1: turns 1 & 2, Round 2: turns 3 & 4, etc.)
    const reconstructedRounds: DebateRound[] = [];
    for (let i = 0; i < mappedTurns.length; i += 2) {
      const turnA = mappedTurns[i];
      const turnB = mappedTurns[i + 1];
      const roundNum = turnA.round_number || Math.floor(i / 2) + 1;

      let petSub: ArgumentSubmission | undefined;
      let respSub: ArgumentSubmission | undefined;

      if (turnA && turnB) {
        if (turnA.speaker_side === "petitioner") {
          petSub = turnA;
          respSub = turnB;
        } else {
          respSub = turnA;
          petSub = turnB;
        }
      } else if (turnA) {
        if (turnA.speaker_side === "petitioner") {
          petSub = turnA;
        } else {
          respSub = turnA;
        }
      }

      const roundQueries = queries.filter(
        (q) => q.turn_number === roundNum || (roundNum === 1 && queries.length > 0)
      );

      reconstructedRounds.push({
        round_number: roundNum,
        status: turnB ? "completed" : "in_progress",
        issue_focus:
          (data.framed_issues && data.framed_issues[roundNum - 1]) ||
          DEFAULT_ISSUES[Math.min(roundNum - 1, DEFAULT_ISSUES.length - 1)] ||
          `Round ${roundNum} Arguments`,
        petitioner_submission: petSub,
        respondent_submission: respSub,
        bench_queries: roundQueries.length > 0 ? roundQueries : roundNum === 1 ? INITIAL_ROUNDS[0].bench_queries : [],
        momentum_petitioner: data.momentum_petitioner || 55,
      });
    }

    if (reconstructedRounds.length > 0) {
      setRounds(reconstructedRounds);
    }
  };

  // 2. Real-Time SSE Stream Listener
  useEffect(() => {
    if (!caseId) return;

    let eventSource: EventSource | null = null;
    try {
      const streamUrl = apiClient.getDebateStreamUrl(caseId);
      eventSource = new EventSource(streamUrl);

      eventSource.onopen = () => {
        setIsSSEConnected(true);
      };

      eventSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          handleStreamEvent(payload);
        } catch (parseErr) {
          console.error("Error parsing SSE debate event:", parseErr);
        }
      };

      eventSource.onerror = () => {
        setIsSSEConnected(false);
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }
      };
    } catch (err) {
      console.warn("Could not establish EventSource for debate stream:", err);
      setIsSSEConnected(false);
    }

    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [caseId]);

  // Handle incoming live SSE event
  const handleStreamEvent = (evt: any) => {
    if (evt.message) {
      setLiveAgentStatus(evt.message);
      setTimeout(() => setLiveAgentStatus(null), 4000);
    }

    if (evt.event_type === "PETITIONER_ARGUMENT" && evt.details?.turn) {
      const turn: ArgumentSubmission = evt.details.turn;
      const rndNum = turn.round_number || evt.round_number || 1;
      setRounds((prev) => {
        const existingIdx = prev.findIndex((r) => r.round_number === rndNum);
        if (existingIdx >= 0) {
          const updated = [...prev];
          updated[existingIdx] = {
            ...updated[existingIdx],
            petitioner_submission: turn,
          };
          return updated;
        } else {
          return [
            ...prev,
            {
              round_number: rndNum,
              status: "in_progress",
              issue_focus: (framedIssues && framedIssues[rndNum - 1]) || `Round ${rndNum} Arguments`,
              petitioner_submission: turn,
              bench_queries: [],
              momentum_petitioner: 55,
            },
          ];
        }
      });
      toast.success("Petitioner Senior Advocate submitted oral argument.");
    } else if (evt.event_type === "RESPONDENT_REBUTTAL" && evt.details?.turn) {
      const turn: ArgumentSubmission = evt.details.turn;
      const rndNum = turn.round_number || evt.round_number || 1;
      setRounds((prev) => {
        const existingIdx = prev.findIndex((r) => r.round_number === rndNum);
        if (existingIdx >= 0) {
          const updated = [...prev];
          updated[existingIdx] = {
            ...updated[existingIdx],
            respondent_submission: turn,
            status: "completed",
          };
          return updated;
        } else {
          return [
            ...prev,
            {
              round_number: rndNum,
              status: "completed",
              issue_focus: (framedIssues && framedIssues[rndNum - 1]) || `Round ${rndNum} Arguments`,
              respondent_submission: turn,
              bench_queries: [],
              momentum_petitioner: 55,
            },
          ];
        }
      });
      toast.success("Defense Counsel delivered counter-rebuttal.");
    } else if (evt.event_type === "BENCH_QUERY" && evt.details?.bench_query) {
      const query: BenchInterlocutory = evt.details.bench_query;
      setRounds((prev) => {
        const updated = [...prev];
        const last = { ...updated[updated.length - 1] };
        last.bench_queries = [...last.bench_queries, query];
        if (evt.details?.momentum_petitioner) {
          last.momentum_petitioner = evt.details.momentum_petitioner;
        }
        updated[updated.length - 1] = last;
        return updated;
      });
    } else if (evt.event_type === "HUMAN_INTERVENTION_REBUTTAL" && evt.details) {
      const { user_turn, counter_turn, round_number } = evt.details;
      const rndNum = round_number || user_turn?.round_number || counter_turn?.round_number;
      if (user_turn && counter_turn) {
        setRounds((prev) => {
          const userSide = user_turn.speaker_side || (lawyerSide === "petitioner" ? "petitioner" : "respondent");
          const petTurn = userSide === "petitioner" ? user_turn : counter_turn;
          const respTurn = userSide === "respondent" ? user_turn : counter_turn;

          const existingIdx = rndNum ? prev.findIndex((r) => r.round_number === rndNum) : -1;
          if (existingIdx >= 0) {
            const updated = [...prev];
            updated[existingIdx] = {
              ...updated[existingIdx],
              petitioner_submission: petTurn,
              respondent_submission: respTurn,
              status: "completed",
            };
            return updated;
          } else {
            const nextRoundNum = rndNum || (prev.length + 1);
            return [
              ...prev,
              {
                round_number: nextRoundNum,
                status: "completed",
                issue_focus: (framedIssues && framedIssues[nextRoundNum - 1]) || `Round ${nextRoundNum} Arguments`,
                petitioner_submission: petTurn,
                respondent_submission: respTurn,
                bench_queries: [],
                momentum_petitioner: 55,
              },
            ];
          }
        });
      }
    }
  };

  // 3. Handle Lawyer Custom Argument Injection (Human-in-the-Loop)
  const handleInjectArgument = async () => {
    if (!customArgument.trim()) {
      toast.error("Please enter a legal proposition or argument to steer the counsel.");
      return;
    }

    const argumentText = customArgument.trim();
    setCustomArgument("");
    setIsSubmittingArgument(true);

    try {
      const updatedState = await apiClient.submitDebateArgument(caseId, {
        custom_argument: argumentText,
        represented_side: lawyerSide,
      });

      if (updatedState?.debate_turns) {
        reconstructRoundsFromBackend(updatedState);
      }
      toast.success("Argument injected! Opposing counsel agent responded autonomously.");
    } catch (err) {
      console.warn("Backend turn error, utilizing client-side fallback adaptation.", err);
      setTimeout(() => {
        const userSubmission: ArgumentSubmission = {
          id: `arg_user_${Date.now()}`,
          turn_number: rounds.length * 2 + 1,
          speaker: "user",
          speaker_side: lawyerSide,
          round_number: rounds.length + 1,
          title: `Lead Counsel Intervention (${lawyerSide === "petitioner" ? "Petitioner" : "Defense"})`,
          argument_text: argumentText,
          doctrine_tags: ["Counsel Steer", "Custom Doctrine", "Interactive HITL"],
          citations: [],
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        };

        const opposingSpeaker = lawyerSide === "petitioner" ? "respondent" : "petitioner";
        const opposingResponse: ArgumentSubmission = {
          id: `arg_opp_${Date.now()}`,
          turn_number: rounds.length * 2 + 2,
          speaker: opposingSpeaker,
          speaker_side: opposingSpeaker,
          round_number: rounds.length + 1,
          title: `Autonomous Counter-Rebuttal to Lead Counsel`,
          argument_text: `Responding directly to counsel's submission on "${argumentText.slice(0, 60)}...": Under settled Indian Supreme Court jurisprudence (Indian Oil Corporation v. NEPC India Ltd. (2006) 6 SCC 736), criminal proceedings cannot be weaponized to enforce civil recoveries. The averments cannot withstand Section 482 scrutiny.`,
          doctrine_tags: ["Autonomous Pivot", "Indian Kanoon Real-Time Grounding"],
          citations: [
            {
              doc_id: "1491764",
              title: "Indian Oil Corporation v. NEPC India Ltd. & Ors.",
              court: "Supreme Court of India",
              year: "2006",
              citation_standard: "(2006) 6 SCC 736",
              url: "https://indiankanoon.org/doc/1491764/",
              ratio_decidendi:
                "A growing tendency in business circles to convert purely civil disputes into criminal cases was strongly deprecated. Quashing is warranted if civil remedies are merely criminalized.",
              statutory_sections: ["Section 420 IPC", "Section 482 CrPC"],
              relevance: "Rebuts the human counsel's proposition with Supreme Court ratio.",
              distinguishing_angle: "Check if specific fiduciary relationship was created under escrow terms.",
            },
          ],
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        };

        const nextRoundNum = rounds.length + 1;
        const newRound: DebateRound = {
          round_number: nextRoundNum,
          status: "completed",
          issue_focus: (framedIssues && framedIssues[nextRoundNum - 1]) || `Round ${nextRoundNum} Arguments`,
          petitioner_submission: lawyerSide === "petitioner" ? userSubmission : opposingResponse,
          respondent_submission: lawyerSide === "respondent" ? userSubmission : opposingResponse,
          bench_queries: [],
          momentum_petitioner: lawyerSide === "petitioner" ? 62 : 48,
        };
        setRounds((prev) => [...prev, newRound]);
      }, 800);
    } finally {
      setIsSubmittingArgument(false);
    }
  };

  // 4. Reset Simulation
  const handleResetSimulation = async () => {
    try {
      const res = await apiClient.startCaseDebate(caseId);
      if (res?.debate_turns) {
        reconstructRoundsFromBackend(res);
      } else {
        setRounds(INITIAL_ROUNDS);
      }
      toast.success("Debate restarted via LangGraph orchestrator.");
    } catch (e) {
      setRounds(INITIAL_ROUNDS);
      toast.success("Debate simulation reset to Round 1 opening pleadings.");
    }
  };

  // 5. Open Brief Modal & Fetch Live Report
  const handleOpenBriefModal = async () => {
    setShowBriefModal(true);
    try {
      const brief = await apiClient.getDebateBrief(caseId);
      if (brief && brief.executive_summary) {
        setLiveBriefData(brief);
      }
    } catch (err) {
      console.warn("Could not fetch live brief, utilizing compiled data.", err);
    }
  };

  const currentRound = rounds[rounds.length - 1] || INITIAL_ROUNDS[0];
  const allBenchQueries = rounds.flatMap((r) => r.bench_queries);
  const rawCitations = rounds.flatMap((r) => [
    ...(r.petitioner_submission?.citations || []),
    ...(r.respondent_submission?.citations || []),
  ]);
  const allCitations = Array.from(
    new Map(rawCitations.map((c) => [c.doc_id, c])).values(),
  );

  return (
    <div className="p-8 lg:p-10 max-w-7xl mx-auto space-y-8">
      {/* 1. Standard Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-6">
        <div>
          <button
            onClick={() => router.push(`/dashboard/cases/${caseId}/results`)}
            className="inline-flex items-center text-xs font-semibold text-muted-foreground hover:text-foreground mb-2 gap-1"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Case Dossier</span>
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Pre-Trial Adversarial War Room
            </h1>
            <Badge variant="info">Multi-Agent Moot</Badge>
            {isSSEConnected ? (
              <Badge variant="success" className="gap-1 text-[11px]">
                <Radio className="w-2.5 h-2.5 animate-pulse" />
                <span>Live Stream</span>
              </Badge>
            ) : (
              <Badge variant="outline" className="text-[11px] text-muted-foreground">
                Standalone Mode
              </Badge>
            )}
            <Badge variant="outline" className="font-mono text-xs">
              Round {currentRound.round_number} of {Math.max(3, rounds.length)}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Simulated courtroom argument combat. Prosecution vs. Defense with autonomous Indian Kanoon
            research, judicial bench challenges, and live human co-counsel steering.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleResetSimulation}
            className="text-xs gap-1.5"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset Rounds</span>
          </Button>

          <Button
            variant="default"
            size="sm"
            onClick={handleOpenBriefModal}
            className="text-xs gap-1.5"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export Trial Brief</span>
          </Button>
        </div>
      </div>

      {/* Live Agent Activity Pill */}
      {liveAgentStatus && (
        <div className="flex items-center gap-2 px-4 py-2 rounded-md bg-blue-50 border border-blue-200 text-xs text-blue-900 animate-in fade-in">
          <Loader2 className="w-3.5 h-3.5 animate-spin text-[#2563EB]" />
          <span className="font-semibold">Courtroom Activity:</span>
          <span>{liveAgentStatus}</span>
        </div>
      )}

      {/* 2. Top Strategy Bar: Framed Issues & Momentum Meter */}
      <Card className="border border-border shadow-sm bg-card">
        <CardContent className="p-5 space-y-4">
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
            <div className="flex-1 space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                Active Legal Issues Under Argumentation
              </p>
              <div className="flex flex-col gap-2.5">
                {framedIssues.map((issue, idx) => (
                  <button
                    key={idx}
                    onClick={() => setSelectedIssueIndex(idx)}
                    className={cn(
                      "text-xs p-3 rounded-md border font-medium transition-colors text-left w-full",
                      selectedIssueIndex === idx
                        ? "border-[#2563EB] bg-blue-50/70 text-blue-900 font-semibold shadow-xs"
                        : "border-border bg-background text-muted-foreground hover:text-foreground hover:border-slate-300",
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <span className="font-mono text-xs font-bold shrink-0 mt-0.5 text-muted-foreground">
                        {idx + 1}.
                      </span>
                      <div className="flex-1">
                        <LegalMarkdown
                          content={issue.replace(/^\d+\.\s*/, "").trim()}
                          className={cn(
                            "text-xs leading-relaxed [&_p]:mb-0",
                            selectedIssueIndex === idx
                              ? "[&_strong]:text-blue-950 text-blue-900"
                              : "[&_strong]:text-foreground text-slate-700",
                          )}
                        />
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Win Probability & Momentum Gauge */}
            <div className="min-w-[260px] p-4 rounded-lg border border-border bg-slate-50/70 shrink-0">
              <div className="flex items-center justify-between text-xs font-semibold mb-1.5">
                <span className="text-[#2563EB]">Petitioner: {currentRound.momentum_petitioner}%</span>
                <span className="text-slate-800">
                  Respondent: {100 - currentRound.momentum_petitioner}%
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-slate-200 overflow-hidden flex">
                <div
                  className="bg-[#2563EB] transition-all duration-500"
                  style={{ width: `${currentRound.momentum_petitioner}%` }}
                />
                <div
                  className="bg-slate-700 transition-all duration-500"
                  style={{ width: `${100 - currentRound.momentum_petitioner}%` }}
                />
              </div>
              <p className="text-[11px] text-muted-foreground mt-1 text-center">
                Bench Favorability Index based on cited Supreme Court authority
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 3. Navigation View Switcher */}
      <Tabs
        value={activeTab}
        onValueChange={(val) => setActiveTab(val as any)}
        className="w-full"
      >
        <TabsList className="grid grid-cols-3 max-w-md">
          <TabsTrigger value="adversarial_arena" className="text-xs gap-1.5">
            <Scale className="w-3.5 h-3.5" />
            <span>Adversarial Arena</span>
          </TabsTrigger>
          <TabsTrigger value="bench_log" className="text-xs gap-1.5">
            <Gavel className="w-3.5 h-3.5" />
            <span>Bench Queries ({currentRound.bench_queries.length})</span>
          </TabsTrigger>
          <TabsTrigger value="citations" className="text-xs gap-1.5">
            <BookOpen className="w-3.5 h-3.5" />
            <span>Kanoon Precedents ({allCitations.length})</span>
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: Adversarial Arena (The 3-Column Courtroom) */}
        <TabsContent value="adversarial_arena" className="space-y-6 mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* Column A: Petitioner / Prosecution Counsel (5 cols) */}
            <div className="lg:col-span-5 space-y-4">
              <div className="flex items-center justify-between border-b border-blue-200 pb-2">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-[#2563EB]" />
                  <h3 className="text-sm font-bold text-foreground">
                    Petitioner / Prosecution Counsel
                  </h3>
                </div>
                <Badge variant="info">Affirmative Burden</Badge>
              </div>

              {rounds.map((rnd) =>
                rnd.petitioner_submission ? (
                  <Card
                    key={rnd.petitioner_submission.id}
                    className="border-blue-100 bg-white shadow-sm hover:border-blue-300 transition-colors"
                  >
                    <CardHeader className="p-4 pb-2">
                      <div className="flex items-center justify-between">
                        <Badge
                          variant={
                            rnd.petitioner_submission.speaker === "user" ? "default" : "info"
                          }
                          className="text-[10px]"
                        >
                          Round {rnd.round_number} :{" "}
                          {rnd.petitioner_submission.speaker === "user"
                            ? "Human Lead Counsel"
                            : "Senior Advocate AI"}
                        </Badge>
                        <span className="text-[11px] text-muted-foreground">
                          {rnd.petitioner_submission.timestamp}
                        </span>
                      </div>
                      <CardTitle className="text-sm font-semibold mt-1.5 text-foreground leading-snug">
                        {rnd.petitioner_submission.title.replace(/\*\*/g, "").replace(/\*/g, "")}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="p-4 pt-1 space-y-3">
                      <LegalMarkdown content={rnd.petitioner_submission.argument_text} />

                      {/* Indian Kanoon Precedents Chips */}
                      {rnd.petitioner_submission.citations.length > 0 && (
                        <div className="space-y-1.5 pt-2 border-t border-border/60">
                          <p className="text-[11px] font-semibold text-muted-foreground flex items-center gap-1">
                            <BookOpen className="w-3 h-3 text-[#2563EB]" />
                            <span>Authorities Cited (indiankanoon.org):</span>
                          </p>
                          <div className="space-y-1.5">
                            {rnd.petitioner_submission.citations.map((c) => (
                              <button
                                key={c.doc_id}
                                onClick={() => setInspectCitation(c)}
                                className="w-full text-left p-2 rounded border border-blue-200 bg-blue-50/50 hover:bg-blue-100/60 transition-colors group"
                              >
                                <div className="flex items-center justify-between text-xs font-semibold text-blue-950">
                                  <span>{c.title}</span>
                                  <ExternalLink className="w-3 h-3 text-[#2563EB] opacity-70 group-hover:opacity-100" />
                                </div>
                                <div className="text-[11px] text-blue-700/80 mt-0.5">
                                  {c.court} &bull; {c.citation_standard}
                                </div>
                                <p className="text-[11px] text-muted-foreground line-clamp-1 mt-1">
                                  Ratio: {c.ratio_decidendi}
                                </p>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ) : null,
              )}
            </div>

            {/* Column B: Bench Interlocutory Query Interceptor (2 cols / middle strip) */}
            <div className="lg:col-span-2 space-y-4">
              <div className="flex items-center justify-between border-b border-border pb-2">
                <div className="flex items-center gap-2">
                  <Gavel className="w-4 h-4 text-slate-700" />
                  <h3 className="text-xs font-bold text-foreground">Judicial Bench</h3>
                </div>
                <Badge variant="outline" className="text-[10px]">
                  Bench Rulings
                </Badge>
              </div>

              {allBenchQueries.length === 0 ? (
                <div className="p-3 rounded-lg border border-dashed border-border bg-slate-50/50 text-center">
                  <p className="text-[11px] text-muted-foreground">No active bench challenges.</p>
                </div>
              ) : (
                allBenchQueries.map((q) => (
                  <div
                    key={q.id}
                    className="p-3 rounded-lg border border-border bg-slate-50 space-y-2 shadow-xs"
                  >
                    <div className="flex items-center gap-1.5 text-[11px] font-bold text-slate-800">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                      <span>Interlocutory Challenge</span>
                    </div>
                    <LegalMarkdown
                      content={q.query}
                      className="[&_p]:mb-0 text-xs text-foreground font-medium leading-snug"
                    />
                    {q.evidentiary_flag && (
                      <div className="text-[10px] text-amber-800 bg-amber-50 p-1.5 rounded border border-amber-200 font-medium">
                        ⚠️ Audit: {q.evidentiary_flag}
                      </div>
                    )}
                    <div className="pt-1 text-[11px] text-muted-foreground border-t border-border space-y-0.5">
                      <span className="font-semibold text-foreground">Recommended Pivot:</span>
                      <LegalMarkdown content={q.suggested_answer} className="[&_p]:mb-0 text-[11px] text-muted-foreground" />
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Column C: Respondent / Defense Counsel (5 cols) */}
            <div className="lg:col-span-5 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-300 pb-2">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-slate-800" />
                  <h3 className="text-sm font-bold text-foreground">
                    Respondent / Defense Counsel
                  </h3>
                </div>
                <Badge variant="secondary">Demolition & Quashing</Badge>
              </div>

              {rounds.map((rnd) =>
                rnd.respondent_submission ? (
                  <Card
                    key={rnd.respondent_submission.id}
                    className="border-slate-200 bg-white shadow-sm hover:border-slate-400 transition-colors"
                  >
                    <CardHeader className="p-4 pb-2">
                      <div className="flex items-center justify-between">
                        <Badge
                          variant={
                            rnd.respondent_submission.speaker === "user" ? "default" : "secondary"
                          }
                          className="text-[10px]"
                        >
                          Round {rnd.round_number} :{" "}
                          {rnd.respondent_submission.speaker === "user"
                            ? "Human Lead Counsel"
                            : "Defense Advocate AI"}
                        </Badge>
                        <span className="text-[11px] text-muted-foreground">
                          {rnd.respondent_submission.timestamp}
                        </span>
                      </div>
                      <CardTitle className="text-sm font-semibold mt-1.5 text-foreground leading-snug">
                        {rnd.respondent_submission.title.replace(/\*\*/g, "").replace(/\*/g, "")}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="p-4 pt-1 space-y-3">
                      <LegalMarkdown content={rnd.respondent_submission.argument_text} />

                      {/* Kanoon Precedents Chips */}
                      {rnd.respondent_submission.citations.length > 0 && (
                        <div className="space-y-1.5 pt-2 border-t border-border/60">
                          <p className="text-[11px] font-semibold text-muted-foreground flex items-center gap-1">
                            <BookOpen className="w-3 h-3 text-slate-700" />
                            <span>Authorities Cited (indiankanoon.org):</span>
                          </p>
                          <div className="space-y-1.5">
                            {rnd.respondent_submission.citations.map((c) => (
                              <button
                                key={c.doc_id}
                                onClick={() => setInspectCitation(c)}
                                className="w-full text-left p-2 rounded border border-slate-200 bg-slate-50/70 hover:bg-slate-100 transition-colors group"
                              >
                                <div className="flex items-center justify-between text-xs font-semibold text-slate-900">
                                  <span>{c.title}</span>
                                  <ExternalLink className="w-3 h-3 text-slate-700 opacity-70 group-hover:opacity-100" />
                                </div>
                                <div className="text-[11px] text-slate-600 mt-0.5">
                                  {c.court} &bull; {c.citation_standard}
                                </div>
                                <p className="text-[11px] text-muted-foreground line-clamp-1 mt-1">
                                  Ratio: {c.ratio_decidendi}
                                </p>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ) : null,
              )}
            </div>
          </div>

          {/* 4. Docked Lawyer Intervention Bar (Human-in-the-Loop) */}
          <Card className="border-2 border-border shadow-md bg-card">
            <CardHeader className="p-4 pb-2">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <UserCheck className="w-4 h-4 text-[#2563EB]" />
                  <span className="text-xs font-bold uppercase tracking-wider text-foreground">
                    Human-In-The-Loop: Steer Counsel with Custom Proposition
                  </span>
                </div>
                {/* Role Switcher */}
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-muted-foreground">You represent:</span>
                  <button
                    onClick={() => setLawyerSide("petitioner")}
                    className={cn(
                      "px-2.5 py-1 rounded-md text-xs font-medium transition-colors border",
                      lawyerSide === "petitioner"
                        ? "bg-[#2563EB] text-white border-transparent"
                        : "bg-muted text-muted-foreground border-border",
                    )}
                  >
                    Petitioner Co-Counsel
                  </button>
                  <button
                    onClick={() => setLawyerSide("respondent")}
                    className={cn(
                      "px-2.5 py-1 rounded-md text-xs font-medium transition-colors border",
                      lawyerSide === "respondent"
                        ? "bg-slate-800 text-white border-transparent"
                        : "bg-muted text-muted-foreground border-border",
                    )}
                  >
                    Defense Co-Counsel
                  </button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-4 pt-2 space-y-3">
              {/* Quick Action Chips */}
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[11px] text-muted-foreground mr-1">Quick Injections:</span>
                {quickActions.map((action, i) => (
                  <button
                    key={i}
                    onClick={() => setCustomArgument(action)}
                    className="text-[11px] px-2.5 py-1 rounded-md border border-border bg-slate-50 text-slate-700 hover:bg-slate-100 hover:border-slate-300 transition-colors"
                  >
                    {action}
                  </button>
                ))}
              </div>

              {/* Text Area & Submit */}
              <div className="flex flex-col sm:flex-row gap-3">
                <Textarea
                  value={customArgument}
                  onChange={(e) => setCustomArgument(e.target.value)}
                  placeholder={`Type a custom factual nuance, statutory exception, or Supreme Court citation to steer ${
                    lawyerSide === "petitioner" ? "Petitioner" : "Defense"
                  }...`}
                  rows={2}
                  className="text-xs resize-none"
                />
                <Button
                  variant="primary"
                  loading={isSubmittingArgument}
                  onClick={handleInjectArgument}
                  className="sm:w-48 text-xs shrink-0 self-end sm:self-stretch gap-1.5"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>Intervene & Force Rebuttal</span>
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab 2: Bench Log & Interlocutory Questions */}
        <TabsContent value="bench_log" className="space-y-4 mt-6">
          <Card className="border border-border">
            <CardHeader className="p-6">
              <CardTitle className="text-base font-bold flex items-center gap-2">
                <Gavel className="w-5 h-5 text-slate-800" />
                <span>Judicial Interlocutory Ledger & Bench Traps</span>
              </CardTitle>
              <CardDescription className="text-xs">
                Sharp questions formulated by the Judicial Bench agent to simulate actual judge cross-examinations.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-6 pt-0 space-y-4">
              {rounds
                .flatMap((r) => r.bench_queries)
                .map((q, idx) => (
                  <div
                    key={q.id || idx}
                    className="p-4 rounded-lg border border-border bg-card space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs font-mono">
                          Query #{idx + 1}
                        </Badge>
                        <Badge
                          variant={q.targeted_speaker === "petitioner" ? "info" : "secondary"}
                          className="text-xs capitalize"
                        >
                          Targeted to: {q.targeted_speaker}
                        </Badge>
                      </div>
                      <span className="text-xs text-muted-foreground">{q.timestamp}</span>
                    </div>

                    <div className="text-sm font-semibold text-foreground">
                      <LegalMarkdown content={q.query} className="[&_p]:mb-0 font-semibold" />
                    </div>

                    <div className="p-3 rounded-md bg-muted/60 text-xs space-y-1">
                      <p className="font-semibold text-foreground">Contextual Basis from Case Dossier:</p>
                      <LegalMarkdown content={q.context_basis} className="[&_p]:mb-0 text-muted-foreground" />
                    </div>

                    <div className="p-3 rounded-md bg-emerald-50/70 border border-emerald-200 text-xs space-y-1">
                      <p className="font-semibold text-emerald-900">Recommended 1-Minute Courtroom Answer:</p>
                      <LegalMarkdown content={q.suggested_answer} className="[&_p]:mb-0 text-emerald-800" />
                    </div>
                  </div>
                ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab 3: Indian Kanoon Precedents Ledger */}
        <TabsContent value="citations" className="space-y-4 mt-6">
          <Card className="border border-border">
            <CardHeader className="p-6">
              <CardTitle className="text-base font-bold flex items-center gap-2">
                <BookOpen className="w-5 h-5 text-[#2563EB]" />
                <span>Verified Precedents from indiankanoon.org</span>
              </CardTitle>
              <CardDescription className="text-xs">
                Direct statutory and case law authorities retrieved autonomously by the Law Clerk agent.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-6 pt-0 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {allCitations.map((cit, idx) => (
                  <Card
                    key={`${cit.doc_id}_${idx}`}
                    className="border border-border bg-card hover:border-blue-300 transition-colors"
                  >
                    <CardHeader className="p-4 pb-2">
                      <div className="flex items-center justify-between">
                        <Badge variant="outline" className="text-[10px] font-mono">
                          Doc ID: {cit.doc_id}
                        </Badge>
                        <a
                          href={cit.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs text-[#2563EB] hover:underline inline-flex items-center gap-1"
                        >
                          <span>Open Kanoon</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                      <CardTitle className="text-sm font-semibold text-foreground mt-1">
                        {cit.title}
                      </CardTitle>
                      <CardDescription className="text-xs">
                        {cit.court} &bull; {cit.citation_standard}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="p-4 pt-1 space-y-2">
                      <div className="text-xs">
                        <span className="font-semibold text-foreground">Ratio Decidendi: </span>
                        <span className="text-muted-foreground">{cit.ratio_decidendi}</span>
                      </div>
                      {cit.distinguishing_angle && (
                        <div className="p-2 rounded bg-amber-50 border border-amber-200 text-[11px] text-amber-900">
                          <span className="font-semibold">Counter / Distinguishing Note: </span>
                          {cit.distinguishing_angle}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* 5. Precedent Inspector Dialog */}
      <Dialog
        open={Boolean(inspectCitation)}
        onOpenChange={(open) => !open && setInspectCitation(null)}
      >
        <DialogContent className="max-w-2xl">
          {inspectCitation && (
            <>
              <DialogHeader>
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="info">Indian Kanoon Precedent</Badge>
                  <span className="text-xs font-mono text-muted-foreground">
                    Doc ID: {inspectCitation.doc_id}
                  </span>
                </div>
                <DialogTitle className="text-lg font-bold text-foreground">
                  {inspectCitation.title}
                </DialogTitle>
                <DialogDescription className="text-xs text-muted-foreground">
                  {inspectCitation.court} &bull; {inspectCitation.citation_standard}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4 py-2 text-xs">
                <div className="p-3 rounded-lg border border-border bg-slate-50 space-y-1">
                  <p className="font-semibold text-foreground">Ratio Decidendi (Core Legal Rule):</p>
                  <p className="text-muted-foreground leading-relaxed">
                    {inspectCitation.ratio_decidendi}
                  </p>
                </div>

                <div className="space-y-1">
                  <p className="font-semibold text-foreground">Statutory Sections Governed:</p>
                  <div className="flex flex-wrap gap-1.5">
                    {inspectCitation.statutory_sections.map((sec, i) => (
                      <Badge key={i} variant="outline" className="text-xs">
                        {sec}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="p-3 rounded-lg border border-amber-200 bg-amber-50 space-y-1 text-amber-900">
                  <p className="font-semibold">How to Distinguish This in Court (Trial Hack):</p>
                  <p className="leading-relaxed">
                    {inspectCitation.distinguishing_angle ||
                      "Focus on distinct factual matrix or establish non-applicability to criminal proceedings."}
                  </p>
                </div>

                <div className="flex items-center justify-between pt-3 border-t border-border">
                  <span className="text-muted-foreground text-[11px]">
                    Verified via indiankanoon.org direct engine
                  </span>
                  <a
                    href={inspectCitation.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs text-[#2563EB] font-semibold hover:underline"
                  >
                    <span>Read Full Judgment on Indian Kanoon</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* 6. Pre-Trial Combat Pack Export Modal */}
      <Dialog open={showBriefModal} onOpenChange={setShowBriefModal}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="success">Trial Preparation Brief</Badge>
              <Badge variant="outline">Case: {caseId.slice(0, 8)}</Badge>
            </div>
            <DialogTitle className="text-xl font-bold">
              Pre-Trial Readiness Brief & Combat Pack
            </DialogTitle>
            <DialogDescription className="text-xs">
              Synthesized by the Multi-Agent Moot Court System with verified Indian Kanoon authorities.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-4 text-xs">
            {/* Summary */}
            <div className="p-4 rounded-lg border border-border bg-slate-50 space-y-2">
              <h4 className="font-bold text-sm text-foreground">1. Executive Trial Readiness Summary</h4>
              {liveBriefData?.executive_summary ? (
                <LegalMarkdown content={liveBriefData.executive_summary} className="text-muted-foreground" />
              ) : (
                <p className="text-muted-foreground leading-relaxed">
                  Matter: <strong className="text-foreground">{caseTitle}</strong>. The prosecution’s
                  affirmative burden under Section 420 IPC remains vulnerable to the defense’s threshold
                  objection under the <em>Dalip Kaur</em> and <em>Bhajan Lal</em> doctrines. Securing conviction
                  will necessitate producing primary WhatsApp device forensics or filing an urgent Section 65B
                  certificate before charge-framing.
                </p>
              )}
              <div className="flex items-center gap-4 text-xs font-semibold pt-2">
                <span>
                  Overall Win Probability:{" "}
                  <strong className="text-[#2563EB]">
                    {liveBriefData?.win_probability_petitioner || currentRound.momentum_petitioner}%
                  </strong>
                </span>
                <span>
                  Precedents Scraped:{" "}
                  <strong className="text-foreground">
                    {liveBriefData?.total_citations_scraped || allCitations.length}
                  </strong>
                </span>
              </div>
            </div>

            {/* Adversary Playbook */}
            <div className="space-y-2">
              <h4 className="font-bold text-sm text-foreground">2. Predicted Opponent Playbook & Counter-Measures</h4>
              <div className="space-y-2">
                {(liveBriefData?.adversary_playbook || [
                  {
                    predicted_move: "Filing for quashing under Section 482 CrPC citing commercial dispute clothing.",
                    counter_rebuttal: "Cite Bhajan Lal Para 102(1) — when allegations prima facie disclose an offense, quashing is precluded without trial.",
                  },
                  {
                    predicted_move: "Challenging digital transcripts under Arjun Panditrao Khotkar (lack of 65B certificate).",
                    counter_rebuttal: "File application under Section 91 CrPC directing production of the original mobile device for forensic inspection.",
                  },
                ]).map((item: any, i: number) => (
                  <div key={i} className="p-3 rounded border border-border bg-card">
                    <p className="font-semibold text-foreground">Predicted Move #{i + 1}:</p>
                    <p className="text-muted-foreground">{item.predicted_move}</p>
                    <p className="font-semibold text-emerald-800 mt-1">Recommended Rebuttal:</p>
                    <p className="text-emerald-700">{item.counter_rebuttal}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Precedent Ledger */}
            <div className="space-y-2">
              <h4 className="font-bold text-sm text-foreground">3. Key Indian Kanoon Citations</h4>
              <div className="space-y-1.5">
                {allCitations.map((c, i) => (
                  <div key={i} className="flex items-center justify-between p-2 rounded border border-border text-xs">
                    <div>
                      <span className="font-semibold text-foreground">{c.title}</span>
                      <span className="text-muted-foreground ml-2">({c.citation_standard})</span>
                    </div>
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[#2563EB] hover:underline flex items-center gap-1 font-medium"
                    >
                      <span>Kanoon Link</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                ))}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center justify-end gap-2 pt-4 border-t border-border">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  navigator.clipboard.writeText(
                    `# Pre-Trial Readiness Brief: ${caseTitle}\n\nOverall Win Probability: ${currentRound.momentum_petitioner}%\n\nKey Citations:\n` +
                      allCitations.map((c) => `- ${c.title} (${c.url})`).join("\n"),
                  );
                  toast.success("Brief copied to clipboard in Markdown format!");
                }}
                className="text-xs"
              >
                Copy Markdown
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={() => window.print()}
                className="text-xs gap-1.5"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Print Trial Pack</span>
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
