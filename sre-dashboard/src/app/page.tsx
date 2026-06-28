"use client";

import { useState, useEffect, useRef } from "react";
import { ContainerScroll } from "@/components/ui/container-scroll-animation";
import { DateTime } from "luxon";
import Swal from "sweetalert2";
import { animate } from "animejs";
import { gsap } from "gsap";
import AOS from "aos";
import "aos/dist/aos.css";
import Lenis from "lenis";
import {
  useFloating,
  useHover,
  useInteractions,
  offset,
  flip,
  shift,
} from "@floating-ui/react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip as ChartTooltip,
  Legend,
  Filler,
} from "chart.js";
import { Line, Bar } from "react-chartjs-2";
import {
  Activity,
  AlertTriangle,
  Terminal,
  Search,
  Upload,
  RefreshCw,
  Settings,
  BookOpen,
  Layers,
} from "lucide-react";

// Register Chart.js elements
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  ChartTooltip,
  Legend,
  Filler
);

interface ActiveMemory {
  memory_id: string;
  memory_key: string;
  summary: string;
  score: number;
  reasons: string[];
  provenance: {
    occurred_at: string;
    severity: string;
    evidence_key: string;
    evidence_value: string;
    title: string | null;
    source_type: string;
  }[];
}

interface RAGResult {
  chunk_id: string;
  document_id: string;
  document_title: string;
  source_type: string;
  uri: string | null;
  chunk_index: number;
  content: string;
  section_title: string | null;
  heading_path: string | null;
  rrf_score: number;
  reason_codes: string[];
}

interface AskResponse {
  answer: string;
  citations: {
    citation_index: number;
    document_title: string;
    source_type: string;
    uri: string | null;
    content: string;
    rrf_score: number;
  }[];
}

export default function SreDashboard() {
  // Navigation & Config States
  const [activeTab, setActiveTab] = useState<"overview" | "incidents" | "rag" | "simulator" | "dbe">("overview");
  const [apiBase] = useState<string>("http://127.0.0.1:8000");
  const [apiStatus, setApiStatus] = useState<"online" | "offline" | "checking">("checking");
  const [settings, setSettings] = useState<{
    llm_provider: string;
    embedding_dimension: number;
    llm_model: string;
    embedding_provider: string;
    embedding_model: string;
    chunking_strategy: string;
    app_name: string;
    environment: string;
  }>({
    app_name: "Memory with Receipts RAG",
    environment: "local",
    llm_provider: "gemini",
    llm_model: "gemini-2.5-flash",
    embedding_provider: "gemini",
    embedding_model: "gemini-embedding-2",
    embedding_dimension: 768,
    chunking_strategy: "structure_aware",
  });

  // Overview Stats
  const [metrics, setMetrics] = useState({
    runbooksCount: 2,
    alertsCount: 0,
    queriesCount: 0,
  });

  // Incidents feed
  const [incidents, setIncidents] = useState<ActiveMemory[]>([]);
  const [expandedIncidentId, setExpandedIncidentId] = useState<string | null>(null);
  const [incidentsLoading, setIncidentsLoading] = useState(false);

  // RAG Query states
  const [searchQuery, setSearchQuery] = useState("");
  const [searchMode, setSearchMode] = useState<"search" | "ask">("search");
  const [selectedSourceType, setSelectedSourceType] = useState<"None" | "operational-memory" | "markdown">("None");
  const [topK, setTopK] = useState(5);
  const [ragLoading, setRagLoading] = useState(false);
  const [searchResult, setSearchResult] = useState<RAGResult[]>([]);
  const [askResult, setAskResult] = useState<AskResponse | null>(null);
  const [showCitations, setShowCitations] = useState(true);

  // Simulator states
  const [simFile, setSimFile] = useState<File | null>(null);
  const [simFileUploading, setSimFileUploading] = useState(false);
  const [simAlertName, setSimAlertName] = useState("PostgreSQLReplicationLagCritical");
  const [simSeverity, setSimSeverity] = useState("critical");
  const [simInstance, setSimInstance] = useState("db-replica-01.prod.internal:5432");
  const [simSummary, setSimSummary] = useState("PostgreSQL replication lag is extremely high");
  const [simDescription, setSimDescription] = useState("Replication lag on db-replica-01 has reached 12.4 GB, exceeding critical SLA of 1 GB.");
  const [simTeam, setSimTeam] = useState("sre-ops");
  const [consoleLog, setConsoleLog] = useState("");

  // DBE diagnostics states
  const [dbeLoading, setDbeLoading] = useState(false);
  const [dbeLogs, setDbeLogs] = useState<{ step_number: number; thought: string; action_tool: string | null; action_argument: string | null; observation: string | null }[]>([]);
  const [dbeRca, setDbeRca] = useState("");
  const [dbeSlackSent, setDbeSlackSent] = useState(false);
  const [dbeGchatSent, setDbeGchatSent] = useState(false);
  const [dbeError, setDbeError] = useState<string | null>(null);
  const [selectedDbeAlert, setSelectedDbeAlert] = useState("PostgreSQLReplicationLagCritical");
  const [dbeRunbookContext, setDbeRunbookContext] = useState<string[]>([]);
  const [dbeMemoryId, setDbeMemoryId] = useState<string | null>(null);
  const [dbeDocumentId, setDbeDocumentId] = useState<string | null>(null);

  // DBE Live Telemetry States
  const [metricsTab, setMetricsTab] = useState<"agent" | "metrics">("agent");
  const [liveMetrics, setLiveMetrics] = useState<{
    database_name: string;
    active_connections: number;
    idle_connections: number;
    total_connections: number;
    max_connections: number;
    lock_count: number;
    blocked_connections: number;
    cache_hit_ratio: number;
    db_size_bytes: number;
    xact_commit: number;
    xact_rollback: number;
    timestamp: string;
  } | null>(null);
  const [autoRefreshMetrics, setAutoRefreshMetrics] = useState(true);
  const [metricsHistory, setMetricsHistory] = useState<{
    timestamps: string[];
    connections: number[];
    locks: number[];
    commits: number[];
  }>({
    timestamps: [],
    connections: [],
    locks: [],
    commits: [],
  });

  const runDbeDiagnostics = async (alertName: string) => {
    if (!alertName) return;
    setDbeLoading(true);
    setDbeLogs([]);
    setDbeRca("");
    setDbeError(null);
    setDbeSlackSent(false);
    setDbeGchatSent(false);
    setDbeRunbookContext([]);
    setDbeMemoryId(null);
    setDbeDocumentId(null);

    try {
      const res = await fetch(`${apiBase}/v1/dbe/diagnose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: alertName, max_steps: 5 }),
      });

      const data = await res.json();
      if (res.ok) {
        setDbeLogs(data.steps || []);
        setDbeRca(data.rca_report || "");
        setDbeSlackSent(data.slack_sent);
        setDbeGchatSent(data.gchat_sent);
        setDbeRunbookContext(data.runbook_context_used || []);
        setDbeMemoryId(data.memory_id || null);
        setDbeDocumentId(data.document_id || null);
        if (!data.is_successful) {
          setDbeError(data.error_message || "Agent diagnostics timed out.");
        }
        Swal.fire({
          title: "Diagnosis Complete",
          text: "RCA report generated and notification channels alerted.",
          icon: "success",
          background: "#121b2d",
          color: "#f8fafc",
          confirmButtonColor: "#00f2fe",
        });
      } else {
        setDbeError(data.detail?.message || "Diagnostics failed.");
        Swal.fire("Diagnostics failed", data.detail?.message || "Internal server error", "error");
      }
    } catch (err) {
      console.error(err);
      setDbeError("FastAPI backend unreachable.");
      Swal.fire("Connection Error", "Unable to reach FastAPI backend", "error");
    } finally {
      setDbeLoading(false);
    }
  };

  const fetchLiveMetrics = async () => {
    try {
      const res = await fetch(`${apiBase}/v1/dbe/metrics`);
      if (res.ok) {
        const data = await res.json();
        setLiveMetrics(data);

        // Keep last 12 samples
        setMetricsHistory((prev) => {
          const time = DateTime.fromISO(data.timestamp).toFormat("HH:mm:ss");
          const nextTimestamps = [...prev.timestamps, time].slice(-12);
          const nextConnections = [...prev.connections, data.total_connections].slice(-12);
          const nextLocks = [...prev.locks, data.lock_count].slice(-12);
          const nextCommits = [...prev.commits, data.xact_commit].slice(-12);
          return {
            timestamps: nextTimestamps,
            connections: nextConnections,
            locks: nextLocks,
            commits: nextCommits,
          };
        });
      }
    } catch (err) {
      console.error("Failed to fetch live database metrics", err);
    }
  };

  // Metrics periodic sync
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (activeTab === "dbe" && metricsTab === "metrics") {
      fetchLiveMetrics();
      if (autoRefreshMetrics) {
        interval = setInterval(fetchLiveMetrics, 5000);
      }
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, metricsTab, autoRefreshMetrics]);

  // Refs for Animations
  const pageContainerRef = useRef<HTMLDivElement>(null);
  const tabContentRef = useRef<HTMLDivElement>(null);
  const sidebarRef = useRef<HTMLDivElement>(null);

  // Initialize Smooth Scrolling, GSAP, and AOS
  useEffect(() => {
    // 1. Lenis Smooth Scroll - attach to the main scrollable container, not window
    const mainEl = document.querySelector(".main-scroll-container") as HTMLElement | null;
    const lenis = new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      ...(mainEl ? { wrapper: mainEl, content: mainEl } : {}),
    });

    function raf(time: number) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }
    requestAnimationFrame(raf);

    // 2. AOS Initialize
    AOS.init({
      duration: 800,
      once: false,
      mirror: true,
    });

    // 3. GSAP Entry Animation
    if (pageContainerRef.current) {
      gsap.fromTo(
        sidebarRef.current,
        { x: -80, opacity: 0 },
        { x: 0, opacity: 1, duration: 0.8, ease: "power2.out" }
      );
      gsap.fromTo(
        ".dashboard-header",
        { y: -30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.8, delay: 0.2, ease: "power2.out" }
      );
      gsap.fromTo(
        ".dashboard-viewport",
        { opacity: 0, y: 15 },
        { opacity: 1, y: 0, duration: 0.8, delay: 0.4, ease: "power2.out" }
      );
    }

    return () => {
      lenis.destroy();
    };
  }, []);

  // Anime.js Tab Transition effect
  useEffect(() => {
    if (tabContentRef.current) {
      animate(tabContentRef.current, {
        opacity: [0, 1],
        translateY: [10, 0],
        duration: 450,
        ease: "outCubic",
      });
    }
  }, [activeTab]);


  // Poll server health on load and every 5 seconds
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${apiBase}/health`);
        if (res.ok) {
          setApiStatus("online");
          const data = await res.json();
          if (data.settings) {
            setSettings(data.settings);
          }
        } else {
          setApiStatus("offline");
        }
      } catch {
        setApiStatus("offline");
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 5000);
    return () => clearInterval(interval);
  }, [apiBase]);

  // Load Active Alerts for Overview and Incidents tabs
  useEffect(() => {
    if (apiStatus === "online") {
      fetchIncidents();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiStatus, apiBase]);

  const fetchIncidents = async () => {
    setIncidentsLoading(true);
    try {
      const res = await fetch(`${apiBase}/operational-memory/retrieval`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service_name: null,
          host_name: null,
          category: null,
          limit: 20,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        const memories: ActiveMemory[] = data.matched_memories || [];
        setIncidents(memories);
        setMetrics((m) => ({ ...m, alertsCount: memories.length }));
      }
    } catch (err) {
      console.error("Failed to fetch operational incidents", err);
    } finally {
      setIncidentsLoading(false);
    }
  };

  // Run Search or Ask
  const handleRagQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setRagLoading(true);
    setSearchResult([]);
    setAskResult(null);

    const payload: {
      query: string;
      top_k: number;
      source_type?: string;
    } = {
      query: searchQuery,
      top_k: topK,
    };

    if (selectedSourceType !== "None") {
      payload.source_type = selectedSourceType;
    }

    try {
      setMetrics((m) => ({ ...m, queriesCount: m.queriesCount + 1 }));
      if (searchMode === "search") {
        const res = await fetch(`${apiBase}/v1/search`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (res.ok) {
          const data = await res.json();
          setSearchResult(data.results || []);

          Swal.fire({
            title: "Search Successful",
            text: `Retrieved ${data.results?.length || 0} reference chunks.`,
            icon: "success",
            toast: true,
            position: "top-end",
            showConfirmButton: false,
            timer: 2500,
            background: "#121b2d",
            color: "#f8fafc",
          });
        } else {
          const errData = await res.json();
          Swal.fire("Search failed", errData.detail?.message || res.statusText, "error");
        }
      } else {
        const res = await fetch(`${apiBase}/v1/ask`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (res.ok) {
          const data = await res.json();
          setAskResult(data);

          Swal.fire({
            title: "Answer Generated",
            text: "RAG agent retrieved chunks and answered using LLM.",
            icon: "success",
            toast: true,
            position: "top-end",
            showConfirmButton: false,
            timer: 2500,
            background: "#121b2d",
            color: "#f8fafc",
          });
        } else {
          const errData = await res.json();
          Swal.fire("Ask failed", errData.detail?.message || res.statusText, "error");
        }
      }
    } catch (err) {
      console.error(err);
      Swal.fire("Query Error", "Unable to reach FastAPI backend RAG system", "error");
    } finally {
      setRagLoading(false);
    }
  };

  // Playbook File Upload Ingestion
  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!simFile) return;

    setSimFileUploading(true);
    const formData = new FormData();
    formData.append("file", simFile);

    try {
      const res = await fetch(`${apiBase}/v1/ingest/file`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      setConsoleLog(JSON.stringify(data, null, 2));

      if (res.ok) {
        setMetrics((m) => ({ ...m, runbooksCount: m.runbooksCount + 1 }));
        setSimFile(null);
        Swal.fire({
          title: "Runbook Ingested!",
          text: `Document processed successfully. Chunks generated and embedded.`,
          icon: "success",
          background: "#121b2d",
          color: "#f8fafc",
          confirmButtonColor: "#00f2fe",
        });
      } else {
        Swal.fire({
          title: "Ingestion failed",
          text: data.detail?.message || "File parsing error",
          icon: "error",
          background: "#121b2d",
          color: "#f8fafc",
        });
      }
    } catch (err) {
      console.error(err);
      Swal.fire("Ingestion Error", "FastAPI ingestion endpoint unreachable", "error");
    } finally {
      setSimFileUploading(false);
    }
  };

  // Fire Webhook alert simulation
  const handleFireAlert = async (e: React.FormEvent) => {
    e.preventDefault();

    // Only include fields that match the PrometheusWebhookPayload schema
    const alertPayload = {
      receiver: "sre-webhook-receiver",
      status: "firing",
      alerts: [
        {
          status: "firing",
          labels: {
            alertname: simAlertName,
            severity: simSeverity,
            instance: simInstance,
            team: simTeam,
          },
          annotations: {
            summary: simSummary,
            description: simDescription,
          },
          startsAt: DateTime.now().toISO(),
          endsAt: null,
          generatorURL: null,
        },
      ],
    };

    try {
      const res = await fetch(`${apiBase}/v1/ingest/webhook/prometheus`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(alertPayload),
      });

      const data = await res.json();
      setConsoleLog(JSON.stringify(data, null, 2));

      if (res.ok) {
        fetchIncidents();
        Swal.fire({
          title: "Webhook Fired!",
          text: `Prometheus webhook simulated alert: ${simAlertName}`,
          icon: "success",
          background: "#121b2d",
          color: "#f8fafc",
          confirmButtonColor: "#9d4edd",
        });
      } else {
        Swal.fire(
          "Webhook Simulation Failed",
          JSON.stringify(data.detail) || "Server error",
          "error"
        );
      }
    } catch (err) {
      console.error(err);
      Swal.fire("Simulation Error", "Prometheus webhook endpoint unreachable", "error");
    }
  };

  // Chart telemetry data configs
  const systemLoadData = {
    labels: ["12:00", "12:05", "12:10", "12:15", "12:20", "12:25", "12:30"],
    datasets: [
      {
        label: "Primary DB Load (%)",
        data: [42, 48, 55, 78, 92, 45, 38],
        borderColor: "#94a3b8",
        backgroundColor: "rgba(148, 163, 184, 0.08)",
        fill: true,
        tension: 0.4,
        borderWidth: 2,
        pointRadius: 3,
      },
      {
        label: "Replica Lag (sec)",
        data: [1.2, 1.5, 3.4, 8.9, 12.4, 4.2, 2.1],
        borderColor: "#cbd5e1",
        backgroundColor: "rgba(203, 213, 225, 0.08)",
        fill: true,
        tension: 0.4,
        borderWidth: 2,
        pointRadius: 3,
      },
    ],
  };

  const dbConnectionsData = {
    labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    datasets: [
      {
        label: "Avg Client Connections",
        data: [210, 230, 290, 310, 480, 190, 180],
        backgroundColor: "rgba(148, 163, 184, 0.15)",
        borderColor: "#94a3b8",
        borderWidth: 1,
        borderRadius: 4,
      },
    ],
  };

  const liveTelemetryChartData = {
    labels: metricsHistory.timestamps.length > 0 ? metricsHistory.timestamps : ["-"],
    datasets: [
      {
        label: "Database Connections",
        data: metricsHistory.connections.length > 0 ? metricsHistory.connections : [0],
        borderColor: "#94a3b8",
        backgroundColor: "rgba(148, 163, 184, 0.08)",
        fill: true,
        tension: 0.4,
        borderWidth: 2.5,
        pointRadius: 2,
      },
      {
        label: "Active Locks",
        data: metricsHistory.locks.length > 0 ? metricsHistory.locks : [0],
        borderColor: "#cbd5e1",
        backgroundColor: "rgba(203, 213, 225, 0.08)",
        fill: true,
        tension: 0.4,
        borderWidth: 2.5,
        pointRadius: 2,
      }
    ]
  };

  const transactionThroughputData = {
    labels: metricsHistory.timestamps.length > 0 ? metricsHistory.timestamps : ["-"],
    datasets: [
      {
        label: "Commits",
        data: metricsHistory.commits.length > 0 ? metricsHistory.commits : [0],
        borderColor: "#10b981",
        backgroundColor: "rgba(16, 185, 129, 0.05)",
        fill: true,
        tension: 0.4,
        borderWidth: 2,
        pointRadius: 2,
      }
    ]
  };

  // Floating UI citation hover config — wired to citation index state
  const [hoveredCitationIdx, setHoveredCitationIdx] = useState<number | null>(null);
  const { refs, floatingStyles, context } = useFloating({
    open: hoveredCitationIdx !== null,
    onOpenChange: (open) => {
      if (!open) setHoveredCitationIdx(null);
    },
    middleware: [offset(8), flip(), shift({ padding: 8 })],
    placement: "top-start",
  });
  const hover = useHover(context, { delay: 100, move: false });
  const { getReferenceProps, getFloatingProps } = useInteractions([hover]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#070a13]" ref={pageContainerRef}>
      {/* SIDEBAR NAVIGATION */}
      <aside
        ref={sidebarRef}
        className="w-20 md:w-64 border-r border-[rgba(255,255,255,0.06)] bg-[#0a0e1a]/80 backdrop-blur-xl flex flex-col items-center md:items-stretch justify-between py-6 px-4 z-20 shrink-0"
      >
        <div className="flex flex-col gap-8 w-full">
          {/* LOGO */}
          <div className="flex items-center gap-3 px-2">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-[#475569] to-[#94a3b8] border border-white/5 flex items-center justify-center shrink-0">
              <Activity className="h-5 w-5 text-white" />
            </div>
            <span className="hidden md:block font-bold text-lg bg-clip-text text-transparent bg-gradient-to-r from-[#f8fafc] to-[#94a3b8]">
              Aegis SRE
            </span>
          </div>

          {/* MENU LINKS */}
          <nav className="flex flex-col gap-2 w-full">
            {[
              { id: "overview" as const, icon: <Layers className="h-5 w-5 shrink-0" />, label: "Dashboard Overview" },
              { id: "incidents" as const, icon: <AlertTriangle className="h-5 w-5 shrink-0" />, label: "Active Incidents" },
              { id: "rag" as const, icon: <Search className="h-5 w-5 shrink-0" />, label: "Unified RAG Studio" },
              { id: "simulator" as const, icon: <Terminal className="h-5 w-5 shrink-0" />, label: "Ingestion Simulator" },
              { id: "dbe" as const, icon: <Terminal className="h-5 w-5 shrink-0" />, label: "DBE Diagnostics" },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`flex items-center gap-3 py-3 px-3 rounded-lg text-sm transition-all duration-300 w-full ${
                  activeTab === item.id
                    ? "bg-white/[0.04] text-white border-l-2 border-slate-400"
                    : "text-[#94a3b8] hover:bg-white/5 hover:text-white"
                }`}
              >
                {item.icon}
                <span className="hidden md:block font-medium">{item.label}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* BOTTOM UTILITY / SETTINGS */}
        <div className="w-full flex flex-col gap-4">
          <div className="hidden md:flex flex-col gap-1.5 p-3 rounded-lg bg-white/[0.03] border border-white/5 text-[0.8rem]">
            <div className="flex items-center justify-between text-[#94a3b8]">
              <span>RAG Provider</span>
              <span className="text-[#cbd5e1]">{settings.llm_provider}</span>
            </div>
            <div className="flex items-center justify-between text-[#94a3b8]">
              <span>Dim size</span>
              <span className="text-white">{settings.embedding_dimension}d</span>
            </div>
          </div>

          <div className="flex items-center justify-center md:justify-start gap-3 px-2 py-3 border-t border-white/5">
            <Settings className="h-5 w-5 text-[#94a3b8] cursor-pointer hover:text-white" />
            <span className="hidden md:block text-xs text-[#94a3b8]">v0.3-Beta</span>
          </div>
        </div>
      </aside>

      {/* MAIN CONTENT VIEWPORT */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        {/* HEADER BAR */}
        <header className="dashboard-header flex items-center justify-between px-6 py-4 border-b border-[rgba(255,255,255,0.06)] bg-[#131722]/40 backdrop-blur-xl z-10 shrink-0">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-semibold text-white tracking-wide">
              {activeTab === "overview" && "Operational Overview"}
              {activeTab === "incidents" && "Operational Memory Alert Feed"}
              {activeTab === "rag" && "Cross-Vertical RAG Studio"}
              {activeTab === "simulator" && "Playbook Ingestion & Webhook Simulator"}
              {activeTab === "dbe" && "DBE Diagnostic Agent Console"}
            </h1>
          </div>

          {/* BACKEND API STATUS BAR */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 bg-[#1b2230] border border-[rgba(255,255,255,0.06)] rounded-full px-3 py-1 text-xs">
              <span className="text-[#94a3b8]">API backend:</span>
              <span className="font-mono text-white select-all">{apiBase}</span>
            </div>

            <div className="flex items-center gap-2 bg-[#1b2230] border border-[rgba(255,255,255,0.06)] rounded-full px-3 py-1 text-xs">
              {apiStatus === "checking" && (
                <>
                  <RefreshCw className="h-3 w-3 text-amber-400 animate-spin" />
                  <span className="text-[#94a3b8]">Syncing...</span>
                </>
              )}
              {apiStatus === "online" && (
                <>
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </span>
                  <span className="text-emerald-400 font-medium">ONLINE</span>
                </>
              )}
              {apiStatus === "offline" && (
                <>
                  <span className="h-2 w-2 rounded-full bg-rose-500"></span>
                  <span className="text-rose-500 font-medium">OFFLINE</span>
                </>
              )}
            </div>
          </div>
        </header>

        {/* WORKSPACE TAB CONTENT VIEWPORT — scrollable */}
        <section
          ref={tabContentRef}
          className="dashboard-viewport flex-1 overflow-y-auto overflow-x-hidden p-6 z-0 main-scroll-container"
        >
          {/* TAB 1: OVERVIEW */}
          {activeTab === "overview" && (
            <div className="flex flex-col gap-8 w-full max-w-7xl mx-auto">

              {/* ACETERNITY 3D SCROLL ANIMATION CONTAINER */}
              <div data-aos="fade-up" className="relative w-full">
                <ContainerScroll
                  titleComponent={
                    <div className="max-w-2xl mx-auto text-center mb-6">
                      <span className="px-3 py-1 rounded-full text-xs font-semibold tracking-wider text-[#cbd5e1] bg-white/[0.04] border border-white/5 uppercase">
                        SRE Intelligent Platform
                      </span>
                      <h2 className="text-4xl md:text-6xl font-bold tracking-tight text-white mt-4 leading-tight">
                        Visualizing System <br />
                        <span className="bg-clip-text text-transparent bg-gradient-to-r from-[#f1f5f9] to-[#94a3b8]">
                          Operational Memory
                        </span>
                      </h2>
                      <p className="text-sm md:text-base text-[#94a3b8] mt-3">
                        Grounded RAG answers backed by verifiable database receipts. Streamlining root cause analysis with zero hallucinations.
                      </p>
                    </div>
                  }
                >
                  {/* Dashboard Mockup Inside 3D Scroll Container */}
                  <div className="h-full w-full bg-[#1b2230] p-6 flex flex-col gap-6 overflow-hidden rounded-2xl border border-white/5 relative">
                    <div className="flex justify-between items-center border-b border-white/5 pb-4">
                      <div className="flex gap-2">
                        <span className="w-3 h-3 rounded-full bg-rose-500"></span>
                        <span className="w-3 h-3 rounded-full bg-amber-500"></span>
                        <span className="w-3 h-3 rounded-full bg-emerald-500"></span>
                      </div>
                      <span className="text-xs text-[#94a3b8] font-mono">postgres-cluster-primary-aegis</span>
                    </div>

                    <div className="grid grid-cols-3 gap-4">
                      <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 flex flex-col justify-between">
                        <span className="text-xs text-[#94a3b8]">Runbooks Ingested</span>
                        <span className="text-2xl font-bold text-white mt-2">{metrics.runbooksCount}</span>
                      </div>
                      <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 flex flex-col justify-between">
                        <span className="text-xs text-[#94a3b8]">Active Critical Alerts</span>
                        <span className="text-2xl font-bold text-rose-400 mt-2">{metrics.alertsCount}</span>
                      </div>
                      <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 flex flex-col justify-between">
                        <span className="text-xs text-[#94a3b8]">Verifiable Queries</span>
                        <span className="text-2xl font-bold text-white mt-2">{metrics.queriesCount}</span>
                      </div>
                    </div>

                    <div className="flex-1 min-h-[150px] relative">
                      <Line
                        data={systemLoadData}
                        options={{
                          responsive: true,
                          maintainAspectRatio: false,
                          plugins: { legend: { display: false } },
                          scales: {
                            x: { grid: { display: false }, ticks: { color: "#475569" } },
                            y: { grid: { color: "rgba(255,255,255,0.03)" }, ticks: { color: "#475569" } },
                          },
                        }}
                      />
                    </div>
                  </div>
                </ContainerScroll>
              </div>

              {/* OVERVIEW METRICS SECTION */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Stats Card 1 */}
                <div
                  data-aos="fade-up"
                  data-aos-delay="100"
                  className="glass-panel p-6 flex flex-col justify-between min-h-[140px] relative overflow-hidden group"
                >
                  <div className="absolute top-0 right-0 p-6 opacity-5 group-hover:scale-110 transition-transform duration-300">
                    <BookOpen className="h-24 w-24 text-white" />
                  </div>
                  <div>
                    <span className="text-xs font-semibold tracking-wider text-[#94a3b8] uppercase">Runbook Knowledge Base</span>
                    <h2 className="text-4xl font-extrabold text-white mt-3 tracking-tight">{metrics.runbooksCount} Documents</h2>
                  </div>
                  <p className="text-xs text-[#94a3b8] mt-4">Loaded playbook markdown runbooks parsed to pgvector database</p>
                </div>

                {/* Stats Card 2 */}
                <div
                  data-aos="fade-up"
                  data-aos-delay="200"
                  className="glass-panel p-6 flex flex-col justify-between min-h-[140px] relative overflow-hidden group"
                >
                  <div className="absolute top-0 right-0 p-6 opacity-5 group-hover:scale-110 transition-transform duration-300">
                    <AlertTriangle className="h-24 w-24 text-white" />
                  </div>
                  <div>
                    <span className="text-xs font-semibold tracking-wider text-[#94a3b8] uppercase">Live Alarms Tracked</span>
                    <h2 className={`text-4xl font-extrabold mt-3 tracking-tight ${metrics.alertsCount > 0 ? "text-rose-400" : "text-emerald-400"}`}>
                      {metrics.alertsCount} Firing
                    </h2>
                  </div>
                  <p className="text-xs text-[#94a3b8] mt-4">Active operational memory events recorded from webhook alerts</p>
                </div>

                {/* Stats Card 3 */}
                <div
                  data-aos="fade-up"
                  data-aos-delay="300"
                  className="glass-panel p-6 flex flex-col justify-between min-h-[140px] relative overflow-hidden group"
                >
                  <div className="absolute top-0 right-0 p-6 opacity-5 group-hover:scale-110 transition-transform duration-300">
                    <Activity className="h-24 w-24 text-white" />
                  </div>
                  <div>
                    <span className="text-xs font-semibold tracking-wider text-[#94a3b8] uppercase">Telemetry RAG Queries</span>
                    <h2 className="text-4xl font-extrabold text-[#00f2fe] mt-3 tracking-tight">{metrics.queriesCount} Requests</h2>
                  </div>
                  <p className="text-xs text-[#94a3b8] mt-4">Verified query search requests completed this session</p>
                </div>
              </div>

              {/* GRAPHS AND HISTORICAL CHARTS */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Live load line graph */}
                <div data-aos="fade-up" className="glass-panel p-6">
                  <h3 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">Live Database CPU & Lag Indicators</h3>
                  <div className="h-72">
                    <Line
                      data={systemLoadData}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: {
                            labels: { color: "#f8fafc", font: { family: "Outfit" } },
                          },
                        },
                        scales: {
                          x: { grid: { display: false }, ticks: { color: "#94a3b8" } },
                          y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#94a3b8" } },
                        },
                      }}
                    />
                  </div>
                </div>

                {/* Bar Chart Client Connections */}
                <div data-aos="fade-up" data-aos-delay="100" className="glass-panel p-6">
                  <h3 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">Client Connection Counts (Weekly)</h3>
                  <div className="h-72">
                    <Bar
                      data={dbConnectionsData}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: { display: false },
                        },
                        scales: {
                          x: { grid: { display: false }, ticks: { color: "#94a3b8" } },
                          y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#94a3b8" } },
                        },
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: ACTIVE INCIDENTS */}
          {activeTab === "incidents" && (
            <div className="max-w-4xl mx-auto flex flex-col gap-6 animate-fade-in">
              <div className="flex justify-between items-center border-b border-white/5 pb-4">
                <div>
                  <h2 className="text-lg font-medium text-white">Active Alerts & Root Cause Logs</h2>
                  <p className="text-xs text-[#94a3b8] mt-1">Operational memories extracted from live monitoring systems and logs</p>
                </div>
                <button
                  onClick={fetchIncidents}
                  disabled={incidentsLoading}
                  className="glass-button text-xs py-1.5 px-3"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${incidentsLoading ? "animate-spin" : ""}`} />
                  Refresh Logs
                </button>
              </div>

              {incidentsLoading && incidents.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 gap-4">
                  <div className="h-10 w-10 border-2 border-t-transparent border-[#00f2fe] rounded-full animate-spin"></div>
                  <span className="text-sm text-[#94a3b8]">Querying Postgres vector storage...</span>
                </div>
              ) : incidents.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-center glass-panel">
                  <span className="text-3xl">🛡️</span>
                  <h3 className="text-md font-medium text-white mt-4">All Systems Nominal</h3>
                  <p className="text-xs text-[#94a3b8] mt-1">No active incidents found in postgres operational memory.</p>
                  {apiStatus === "offline" && (
                    <p className="text-xs text-rose-400 mt-2">⚠️ API backend is offline. Start FastAPI server to load live data.</p>
                  )}
                </div>
              ) : (
                <div className="flex flex-col gap-4">
                  {incidents.map((inc) => {
                    const isExpanded = expandedIncidentId === inc.memory_id;
                    const occurredAt = inc.provenance?.[0]?.occurred_at
                      ? DateTime.fromISO(inc.provenance[0].occurred_at).toRelative()
                      : "Unknown time";

                    return (
                      <div
                        key={inc.memory_id}
                        className={`glass-panel overflow-hidden transition-all duration-300 ${isExpanded ? "border-[#00f2fe] bg-white/5" : ""}`}
                      >
                        {/* Header bar */}
                        <div
                          onClick={() => setExpandedIncidentId(isExpanded ? null : inc.memory_id)}
                          className="p-5 flex items-center justify-between cursor-pointer hover:bg-white/[0.02]"
                        >
                          <div className="flex items-center gap-4">
                            <span className="h-2 w-2 rounded-full bg-rose-500 animate-pulse shrink-0"></span>
                            <div>
                              <h3 className="text-md font-semibold text-white">{inc.summary}</h3>
                              <div className="flex items-center gap-2 mt-1.5 text-xs text-[#94a3b8]">
                                <span className="bg-rose-500/10 text-rose-400 border border-rose-500/20 px-2 py-0.5 rounded text-[10px] font-mono uppercase">
                                  {inc.provenance?.[0]?.severity || "critical"}
                                </span>
                                <span>•</span>
                                <span>
                                  Instance: <code className="text-white">{inc.provenance?.[0]?.evidence_key || "Unknown"}</code>
                                </span>
                                <span>•</span>
                                <span>{occurredAt}</span>
                              </div>
                            </div>
                          </div>

                          <span className="text-xs text-[#94a3b8] shrink-0 ml-4">
                            {isExpanded ? "▲ Collapse details" : "▼ Expand timeline"}
                          </span>
                        </div>

                        {/* Collapsible body */}
                        {isExpanded && (
                          <div className="px-5 pb-5 border-t border-white/5 pt-4 flex flex-col gap-4 bg-black/10">
                            <div>
                              <h4 className="text-xs font-semibold text-white uppercase tracking-wider">Root Cause Reasoning / Context</h4>
                              <ul className="list-disc pl-4 mt-2 text-sm text-[#94a3b8] flex flex-col gap-1">
                                {inc.reasons.map((reason, idx) => (
                                  <li key={idx}>{reason}</li>
                                ))}
                              </ul>
                            </div>

                            {/* Provenance timeline logs */}
                            <div>
                              <h4 className="text-xs font-semibold text-white uppercase tracking-wider mb-3">Telemetry Log Timeline</h4>
                              <div className="relative border-l border-white/10 ml-2 pl-4 flex flex-col gap-4">
                                {inc.provenance.map((prov, idx) => (
                                  <div key={idx} className="relative">
                                    <span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-[#00f2fe] border-4 border-[#070a13] box-content"></span>

                                    <div className="text-xs text-[#94a3b8]">
                                      {DateTime.fromISO(prov.occurred_at).toFormat("yyyy-MM-dd HH:mm:ss ZZZZ")}
                                    </div>
                                    <div className="text-sm font-medium text-white mt-0.5">
                                      {prov.title || "Webhook Alert Callback"}
                                    </div>
                                    <div className="text-xs mt-1 bg-black/30 border border-white/5 p-2 rounded-md font-mono text-emerald-400 select-all">
                                      {prov.evidence_key}: {prov.evidence_value}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: RAG STUDIO */}
          {activeTab === "rag" && (
            <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-6 animate-fade-in">
              {/* Left query pane */}
              <div className="glass-panel p-6 flex flex-col gap-6 md:col-span-1 h-fit">
                <div>
                  <h2 className="text-md font-semibold text-white">Search Constraints</h2>
                  <p className="text-xs text-[#94a3b8] mt-1">Tune retrieval filters and similarity scope</p>
                </div>

                <form onSubmit={handleRagQuery} className="flex flex-col gap-4">
                  <div className="flex flex-col gap-1.5">
                    <label className="text-xs text-[#94a3b8] font-medium">Query Mode</label>
                    <div className="grid grid-cols-2 gap-2 bg-black/20 p-1 rounded-lg border border-white/5">
                      <button
                        type="button"
                        onClick={() => setSearchMode("search")}
                        className={`text-xs py-1.5 rounded-md font-medium transition-all ${
                          searchMode === "search"
                            ? "bg-white/[0.06] text-white border border-white/10"
                            : "text-[#94a3b8] hover:text-white"
                        }`}
                      >
                        Pure Search
                      </button>
                      <button
                        type="button"
                        onClick={() => setSearchMode("ask")}
                        className={`text-xs py-1.5 rounded-md font-medium transition-all ${
                          searchMode === "ask"
                            ? "bg-white/[0.06] text-white border border-white/10"
                            : "text-[#94a3b8] hover:text-white"
                        }`}
                      >
                        Generative Ask
                      </button>
                    </div>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label className="text-xs text-[#94a3b8] font-medium">Source Type Filter</label>
                    <select
                      className="glass-input text-xs"
                      value={selectedSourceType}
                      onChange={(e) => setSelectedSourceType(e.target.value as "None" | "operational-memory" | "markdown")}
                    >
                      <option value="None">All (Operational & Markdowns)</option>
                      <option value="operational-memory">Operational Memories Only</option>
                      <option value="markdown">Ingested Playbooks Only</option>
                    </select>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label className="text-xs text-[#94a3b8] font-medium">Top K Chunks ({topK})</label>
                    <input
                      type="range"
                      min="1"
                      max="10"
                      value={topK}
                      onChange={(e) => setTopK(parseInt(e.target.value))}
                      className="w-full accent-[#cbd5e1]"
                    />
                  </div>

                  <button type="submit" className="glass-button text-sm mt-2" disabled={ragLoading}>
                    {ragLoading ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin" />
                        Generating Answer...
                      </>
                    ) : (
                      <>
                        <Search className="h-4 w-4" />
                        Execute RAG Query
                      </>
                    )}
                  </button>
                </form>
              </div>

              {/* Right results pane */}
              <div className="md:col-span-2 flex flex-col gap-6">
                {/* Search Text Area Input */}
                <div className="glass-panel p-4 flex gap-3">
                  <input
                    type="text"
                    className="glass-input flex-1 text-sm py-2 px-4 bg-transparent border-0 focus:ring-0 focus:border-0"
                    placeholder="Ask Aegis RAG (e.g. 'How do I resolve PostgreSQL replication lag on db-replica-01?')"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !ragLoading) {
                        handleRagQuery(e);
                      }
                    }}
                  />
                </div>

                {/* Output Screen */}
                <div className="flex-1 min-h-[400px]">
                  {ragLoading ? (
                    <div className="glass-panel h-full flex flex-col items-center justify-center p-20 gap-4">
                      <div className="h-10 w-10 border-2 border-t-transparent border-[#9d4edd] rounded-full animate-spin"></div>
                      <span className="text-sm text-[#94a3b8] animate-pulse">Retrieving grounded facts and building prompt...</span>
                    </div>
                  ) : !searchResult.length && !askResult ? (
                    <div className="glass-panel h-full flex flex-col items-center justify-center p-20 text-center">
                      <span className="text-4xl">🤖</span>
                      <h3 className="text-md font-medium text-white mt-4">RAG Assistant Ready</h3>
                      <p className="text-xs text-[#94a3b8] mt-1 max-w-sm">
                        Submit a query to parse structural documentation chunks and match vector database indexes.
                      </p>
                    </div>
                  ) : searchMode === "search" ? (
                    // Search Result Chunks List
                    <div className="flex flex-col gap-4">
                      {searchResult.map((res) => (
                        <div key={res.chunk_id} className="glass-panel p-5 flex flex-col gap-3" data-aos="fade-up">
                          <div className="flex justify-between items-start gap-4">
                            <div className="flex items-center gap-2">
                              <span className="text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded font-mono">
                                Score: {res.rrf_score.toFixed(4)}
                              </span>
                              <span className="text-xs text-white font-medium">{res.document_title}</span>
                            </div>
                            <span className="text-xs text-[#94a3b8] bg-white/[0.03] px-2 py-0.5 rounded font-mono">
                              {res.source_type}
                            </span>
                          </div>

                          <p className="text-xs text-[#94a3b8] bg-black/20 p-3 rounded-lg border border-white/[0.03] font-mono leading-relaxed whitespace-pre-wrap select-text">
                            {res.content}
                          </p>

                          <div className="flex items-center justify-between text-[11px] text-[#94a3b8]">
                            <span>
                              Heading: <code className="text-white">{res.heading_path || "None"}</code>
                            </span>
                            <span>
                              URI: <code className="text-[#00f2fe] select-all">{res.uri || "None"}</code>
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    // Ask Answer Screen
                    askResult && (
                      <div className="glass-panel p-6 flex flex-col gap-6" data-aos="fade-up">
                        <div className="flex justify-between items-center border-b border-white/5 pb-4">
                          <div className="flex items-center gap-2">
                            <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
                            <span className="text-xs font-semibold text-white uppercase tracking-wider">Aegis Generative Answer</span>
                          </div>
                          <span className="text-xs text-[#94a3b8] font-mono">Verified Receipts Attached</span>
                        </div>

                        <div className="text-sm text-[#94a3b8] leading-relaxed whitespace-pre-wrap select-text">
                          {askResult.answer}
                        </div>

                        {/* Receipts Citation Section */}
                        <div className="border-t border-white/5 pt-4">
                          <div
                            onClick={() => setShowCitations(!showCitations)}
                            className="flex justify-between items-center cursor-pointer text-xs font-semibold text-white tracking-wider uppercase"
                          >
                            <span>📑 Verifiable Source Receipts ({askResult.citations.length})</span>
                            <span>{showCitations ? "▲ Hide Chunks" : "▼ Show Chunks"}</span>
                          </div>

                          {showCitations && (
                            <div className="grid grid-cols-1 gap-4 mt-4">
                              {askResult.citations.map((cit) => (
                                <div
                                  key={cit.citation_index}
                                  className="p-4 rounded-xl bg-black/20 border border-white/5 flex flex-col gap-2 relative"
                                  ref={cit.citation_index === 0 ? refs.setReference : undefined}
                                  {...(cit.citation_index === 0 ? getReferenceProps() : {})}
                                >
                                  <div className="flex justify-between items-center">
                                    <div className="flex items-center gap-2">
                                      <span className="h-5 w-5 bg-[rgba(0,242,254,0.1)] text-[#00f2fe] flex items-center justify-center rounded-md font-mono text-xs">
                                        {cit.citation_index}
                                      </span>
                                      <span className="text-xs text-white font-medium">{cit.document_title}</span>
                                    </div>
                                    <span className="text-[10px] bg-white/[0.03] text-[#94a3b8] px-2 py-0.5 rounded uppercase font-mono">
                                      {cit.source_type}
                                    </span>
                                  </div>

                                  <p className="text-xs text-[#94a3b8] italic bg-black/10 p-2.5 rounded border border-white/[0.02] select-text font-mono leading-normal">
                                    &ldquo;{cit.content}&rdquo;
                                  </p>

                                  <div className="flex justify-between items-center text-[10px] text-[#94a3b8]">
                                    <span>
                                      Score: <code className="text-white">{cit.rrf_score.toFixed(4)}</code>
                                    </span>
                                    <span>
                                      URI: <code className="text-[#00f2fe] select-all">{cit.uri || "None"}</code>
                                    </span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Floating UI popover for first citation */}
                        {hoveredCitationIdx === 0 && (
                          <div
                            ref={refs.setFloating}
                            style={floatingStyles}
                            {...getFloatingProps()}
                            className="z-50 bg-[#0e1628] border border-[rgba(0,242,254,0.2)] rounded-lg p-3 text-xs text-[#94a3b8] max-w-xs shadow-xl"
                          >
                            <div className="font-semibold text-[#00f2fe] mb-1">Citation Preview</div>
                            <p className="leading-relaxed line-clamp-3">{askResult.citations[0]?.content}</p>
                          </div>
                        )}
                      </div>
                    )
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: SIMULATOR & PLAYBOOK INGESTION */}
          {activeTab === "simulator" && (
            <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-6 animate-fade-in">
              {/* Playbook file uploader panel */}
              <div className="glass-panel p-6 flex flex-col gap-6" data-aos="fade-up">
                <div>
                  <h2 className="text-md font-semibold text-white">Ingest New Playbook</h2>
                  <p className="text-xs text-[#94a3b8] mt-1">Upload markdown `.md` troubleshooting playbooks directly into vector database</p>
                </div>

                <form onSubmit={handleFileUpload} className="flex flex-col gap-4">
                  <label className="flex flex-col items-center justify-center border border-dashed border-white/20 rounded-xl p-8 bg-black/20 hover:bg-white/[0.03] cursor-pointer transition-colors relative">
                    <Upload className="h-10 w-10 text-slate-400 mb-3" />
                    {simFile ? (
                      <div className="text-center">
                        <span className="text-sm font-semibold text-white block truncate max-w-xs">{simFile.name}</span>
                        <span className="text-[11px] text-slate-300 mt-1 block">
                          {(simFile.size / 1024).toFixed(1)} KB - Click to replace
                        </span>
                      </div>
                    ) : (
                      <div className="text-center">
                        <span className="text-sm font-medium text-white block">Click to select file</span>
                        <span className="text-[11px] text-[#94a3b8] mt-1 block">Supports markdown formatting playbooks</span>
                      </div>
                    )}
                    <input
                      type="file"
                      accept=".md,.txt"
                      className="hidden"
                      onChange={(e) => setSimFile(e.target.files?.[0] || null)}
                    />
                  </label>

                  <button
                    type="submit"
                    className="glass-button text-sm"
                    disabled={simFileUploading || !simFile}
                  >
                    {simFileUploading ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin" />
                        Embedding Playbook...
                      </>
                    ) : (
                      <>
                        <Upload className="h-4 w-4" />
                        Ingest Playbook Guide
                      </>
                    )}
                  </button>
                </form>
              </div>

              {/* Webhook Alarm simulator panel */}
              <div className="glass-panel p-6 flex flex-col gap-6" data-aos="fade-up" data-aos-delay="100">
                <div>
                  <h2 className="text-md font-semibold text-white">Prometheus Alarm Webhook</h2>
                  <p className="text-xs text-[#94a3b8] mt-1">Simulate monitors webhook callback to post new incident logs</p>
                </div>

                <form onSubmit={handleFireAlert} className="flex flex-col gap-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs text-[#94a3b8] font-medium">Alert Name</label>
                      <select
                        className="glass-input text-xs"
                        value={simAlertName}
                        onChange={(e) => {
                          const name = e.target.value;
                          setSimAlertName(name);
                          if (name === "PostgreSQLReplicationLagCritical") {
                            setSimSeverity("critical");
                            setSimSummary("PostgreSQL replication lag is extremely high");
                            setSimDescription("Replication lag on db-replica-01 has reached 12.4 GB, exceeding SLA of 1 GB.");
                          } else if (name === "PostgreSQLHighMemoryUsage") {
                            setSimSeverity("warning");
                            setSimSummary("Database RAM consumption exceeds 92%");
                            setSimDescription("PostgreSQL RSS size on db-replica-02 is elevated at 58 GB of 64 GB total.");
                          } else {
                            setSimSeverity("critical");
                            setSimSummary("PostgreSQL Max Connections Reached");
                            setSimDescription("Active client connections reached 98% of limit on db-primary (490/500).");
                          }
                        }}
                      >
                        <option value="PostgreSQLReplicationLagCritical">PostgreSQLReplicationLagCritical</option>
                        <option value="PostgreSQLHighMemoryUsage">PostgreSQLHighMemoryUsage</option>
                        <option value="PostgreSQLMaxConnectionsReached">PostgreSQLMaxConnectionsReached</option>
                      </select>
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs text-[#94a3b8] font-medium">Severity</label>
                      <select
                        className="glass-input text-xs"
                        value={simSeverity}
                        onChange={(e) => setSimSeverity(e.target.value)}
                      >
                        <option value="critical">Critical</option>
                        <option value="warning">Warning</option>
                        <option value="info">Info</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs text-[#94a3b8] font-medium">Host Instance</label>
                      <input
                        type="text"
                        className="glass-input text-xs"
                        value={simInstance}
                        onChange={(e) => setSimInstance(e.target.value)}
                      />
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs text-[#94a3b8] font-medium">Ops Team</label>
                      <input
                        type="text"
                        className="glass-input text-xs"
                        value={simTeam}
                        onChange={(e) => setSimTeam(e.target.value)}
                      />
                    </div>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label className="text-xs text-[#94a3b8] font-medium">Summary</label>
                    <input
                      type="text"
                      className="glass-input text-xs"
                      value={simSummary}
                      onChange={(e) => setSimSummary(e.target.value)}
                    />
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label className="text-xs text-[#94a3b8] font-medium">Description</label>
                    <textarea
                      className="glass-input text-xs"
                      rows={2}
                      value={simDescription}
                      onChange={(e) => setSimDescription(e.target.value)}
                      style={{ resize: "none" }}
                    />
                  </div>

                  <button type="submit" className="glass-button text-sm mt-1">
                    🔥 Fire Prometheus Webhook Event
                  </button>
                </form>
              </div>

              {/* Console log output viewer */}
              <div className="glass-panel p-6 md:col-span-2 flex flex-col gap-4" data-aos="fade-up">
                <div className="flex justify-between items-center border-b border-white/5 pb-3">
                  <div className="flex items-center gap-2">
                    <Terminal className="h-4 w-4 text-slate-400" />
                    <h2 className="text-xs font-semibold text-white uppercase tracking-wider">Webhook API Console Logs</h2>
                  </div>
                  <button
                    onClick={() => setConsoleLog("")}
                    className="text-[10px] text-[#94a3b8] hover:text-white uppercase font-bold"
                  >
                    Clear Console
                  </button>
                </div>

                <pre className="bg-black/40 border border-white/5 p-4 rounded-xl text-xs font-mono text-emerald-400 max-h-60 overflow-y-auto select-all leading-relaxed whitespace-pre">
                  {consoleLog || "Simulator webhook logs will render here in real-time JSON format..."}
                </pre>
              </div>
            </div>
          )}
          {/* TAB 5: DBE DIAGNOSTICS */}
          {activeTab === "dbe" && (
            <div className="max-w-5xl mx-auto flex flex-col gap-6 animate-fade-in">
              {/* DBE Sub-tab Selector */}
              <div className="flex justify-between items-center border-b border-white/5 pb-4">
                <div className="flex gap-4">
                  <button
                    onClick={() => setMetricsTab("agent")}
                    className={`text-sm font-semibold pb-2 border-b-2 transition-all ${
                      metricsTab === "agent"
                        ? "text-white border-slate-400"
                        : "text-[#94a3b8] border-transparent hover:text-white"
                    }`}
                  >
                    Diagnostic Agent Console
                  </button>
                  <button
                    onClick={() => setMetricsTab("metrics")}
                    className={`text-sm font-semibold pb-2 border-b-2 transition-all ${
                      metricsTab === "metrics"
                        ? "text-white border-slate-400"
                        : "text-[#94a3b8] border-transparent hover:text-white"
                    }`}
                  >
                    Live Database Telemetry
                  </button>
                </div>

                {metricsTab === "metrics" && (
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 text-xs text-[#94a3b8]">
                      <span>Auto Refresh:</span>
                      <button
                        onClick={() => setAutoRefreshMetrics(!autoRefreshMetrics)}
                        className={`px-3 py-1 rounded-full text-[10px] font-bold tracking-wider uppercase transition-all ${
                          autoRefreshMetrics
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : "bg-white/5 text-[#94a3b8] border border-white/5"
                        }`}
                      >
                        {autoRefreshMetrics ? "ON" : "OFF"}
                      </button>
                    </div>
                    <button
                      onClick={fetchLiveMetrics}
                      className="glass-button text-xs py-1.5 px-3"
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                      Force Sync
                    </button>
                  </div>
                )}
              </div>

              {/* Agent Console view */}
              {metricsTab === "agent" && (
                <div className="flex flex-col gap-6 animate-fade-in">
                  <div className="glass-panel p-6 flex flex-col gap-6">
                    <div>
                      <h2 className="text-md font-semibold text-white">DBE Diagnostic Agent</h2>
                      <p className="text-xs text-[#94a3b8] mt-1">Select an active incident or trigger query to launch ReAct agentic diagnostics</p>
                    </div>

                    <div className="flex gap-4 items-end">
                      <div className="flex-1 flex flex-col gap-1.5">
                        <label className="text-xs text-[#94a3b8] font-medium">Select Firing Incident / Alert Query</label>
                        <select
                          className="glass-input text-xs"
                          value={selectedDbeAlert}
                          onChange={(e) => setSelectedDbeAlert(e.target.value)}
                        >
                          {incidents.length > 0 ? (
                            incidents.map((inc) => (
                              <option key={inc.memory_id} value={inc.provenance?.[0]?.title || inc.summary}>
                                {inc.summary} ({inc.provenance?.[0]?.severity || "critical"})
                              </option>
                            ))
                          ) : (
                            <>
                              <option value="PostgreSQLReplicationLagCritical">PostgreSQLReplicationLagCritical (Simulation Alert)</option>
                              <option value="PostgreSQLMaxConnectionsReached">PostgreSQLMaxConnectionsReached (Simulation Alert)</option>
                              <option value="RDSCPUUtilizationHigh">RDSCPUUtilizationHigh (Simulation Alert)</option>
                            </>
                          )}
                        </select>
                      </div>

                      <button
                        onClick={() => runDbeDiagnostics(selectedDbeAlert)}
                        className="glass-button text-sm h-fit py-2.5 px-6"
                        disabled={dbeLoading}
                      >
                        {dbeLoading ? (
                          <span className="flex items-center gap-2">
                            <RefreshCw className="h-4 w-4 animate-spin" />
                            Running ReAct Diagnostics...
                          </span>
                        ) : (
                          "Run Diagnostics"
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Steps Console / Log output */}
                  {(dbeLoading || dbeLogs.length > 0) && (
                    <div className="glass-panel p-6 flex flex-col gap-4">
                      <div className="flex justify-between items-center border-b border-white/5 pb-3">
                        <div className="flex items-center gap-2">
                          <Terminal className="h-4 w-4 text-slate-400" />
                          <h2 className="text-xs font-semibold text-white uppercase tracking-wider">Diagnostic Execution Log</h2>
                        </div>
                        {dbeLoading && (
                          <span className="text-xs text-slate-400 animate-pulse">Agent is thinking and querying tools...</span>
                        )}
                      </div>

                      <div className="flex flex-col gap-4 max-h-[400px] overflow-y-auto pr-2">
                        {dbeLogs.map((log) => (
                          <div key={log.step_number} className="bg-black/30 border border-white/5 p-4 rounded-xl flex flex-col gap-2 font-mono text-xs">
                            <div className="flex justify-between text-[11px] text-white font-bold border-b border-white/5 pb-1">
                              <span>STEP {log.step_number}</span>
                              <span>{log.action_tool ? `Tool: ${log.action_tool}` : "Finalization"}</span>
                            </div>
                            <div className="text-white">
                              <span className="text-[#94a3b8] font-bold">Thought:</span> {log.thought}
                            </div>
                            {log.action_argument && (
                              <div className="text-slate-300 truncate">
                                <span className="text-[#94a3b8] font-bold">Arguments:</span> {log.action_argument}
                              </div>
                            )}
                            {log.observation && (
                              <div className="mt-2 bg-black/50 border border-white/5 p-3 rounded-lg text-emerald-400 select-all whitespace-pre overflow-x-auto">
                                <span className="text-[#94a3b8] font-bold block mb-1">Observation Output:</span>
                                {log.observation}
                              </div>
                            )}
                          </div>
                        ))}

                        {dbeLoading && dbeLogs.length === 0 && (
                          <div className="text-center py-6 text-xs text-[#94a3b8] font-mono animate-pulse">
                            Initiating diagnostics agent...
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Diagnosed RCA Report */}
                  {dbeRca && (
                    <div className="glass-panel p-6 flex flex-col gap-6">
                      <div className="flex justify-between items-center border-b border-white/5 pb-4">
                        <div className="flex items-center gap-2">
                          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500"></span>
                          <span className="text-xs font-semibold text-white uppercase tracking-wider">Root Cause Analysis (RCA) Report</span>
                        </div>
                        <div className="flex gap-2">
                          {dbeSlackSent && (
                            <span className="text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded font-mono">
                              Slack Notified
                            </span>
                          )}
                          {dbeGchatSent && (
                            <span className="text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded font-mono">
                              GChat Notified
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="text-sm text-[#94a3b8] leading-relaxed whitespace-pre-wrap select-text font-sans prose prose-invert max-w-none">
                        {dbeRca}
                      </div>
                    </div>
                  )}

                  {/* Referenced Runbooks & Ingestion Receipts Grid */}
                  {dbeRca && (dbeRunbookContext.length > 0 || dbeMemoryId || dbeDocumentId) && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6" data-aos="fade-up">
                      {/* Left: Referenced Runbook Knowledge */}
                      <div className="glass-panel p-6 flex flex-col gap-4">
                        <div className="border-b border-white/5 pb-3">
                          <h3 className="text-xs font-semibold text-white uppercase tracking-wider">Referenced Runbook Knowledge</h3>
                        </div>
                        {dbeRunbookContext.length > 0 ? (
                          <div className="flex flex-col gap-3 max-h-[300px] overflow-y-auto pr-1">
                            {dbeRunbookContext.map((chunk, idx) => (
                              <div key={idx} className="p-3 bg-black/10 rounded-lg border border-white/5 text-xs text-[#94a3b8] font-mono leading-relaxed select-text whitespace-pre-wrap">
                                {chunk}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="text-xs text-[#64748b] italic p-2">
                            No matching runbook playbook knowledge was referenced for this alert category.
                          </div>
                        )}
                      </div>

                      {/* Right: Operational Ingestion Receipts */}
                      <div className="glass-panel p-6 flex flex-col gap-4">
                        <div className="border-b border-white/5 pb-3">
                          <h3 className="text-xs font-semibold text-white uppercase tracking-wider">Ingestion Status / Receipts</h3>
                        </div>
                        <p className="text-xs text-[#94a3b8] leading-relaxed">
                          This root cause analysis (RCA) report and diagnostic sequence have been ingested back into the operational memory and document index.
                        </p>
                        
                        <div className="flex flex-col gap-4 mt-2">
                          {/* Memory ID Chip */}
                          <div className="flex flex-col gap-1.5">
                            <span className="text-[11px] font-semibold text-white uppercase tracking-wider">Operational Memory Receipt</span>
                            {dbeMemoryId ? (
                              <div className="flex items-center justify-between gap-2 p-2 bg-black/25 border border-white/5 rounded-lg">
                                <button
                                  onClick={() => {
                                    setActiveTab("rag");
                                    setSelectedSourceType("operational-memory");
                                    setSearchQuery(dbeMemoryId);
                                    setSearchMode("search");
                                  }}
                                  className="text-xs text-[#94a3b8] hover:text-white font-mono font-medium text-left truncate flex-1 hover:underline cursor-pointer"
                                  title="Click to lookup in Unified RAG Studio"
                                >
                                  {dbeMemoryId}
                                </button>
                                <button
                                  onClick={() => {
                                    navigator.clipboard.writeText(dbeMemoryId);
                                    Swal.fire({
                                      title: "Copied!",
                                      text: "Memory ID copied to clipboard",
                                      icon: "success",
                                      toast: true,
                                      position: "top-end",
                                      showConfirmButton: false,
                                      timer: 1500,
                                      background: "#1e2535",
                                      color: "#f1f5f9",
                                    });
                                  }}
                                  className="p-1 text-[#64748b] hover:text-[#94a3b8] rounded transition-colors"
                                  title="Copy Memory ID"
                                >
                                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                                  </svg>
                                </button>
                              </div>
                            ) : (
                              <span className="text-xs text-[#64748b] italic">Not ingested</span>
                            )}
                          </div>

                          {/* Document ID Chip */}
                          <div className="flex flex-col gap-1.5">
                            <span className="text-[11px] font-semibold text-white uppercase tracking-wider">Document Index Receipt</span>
                            {dbeDocumentId ? (
                              <div className="flex items-center justify-between gap-2 p-2 bg-black/25 border border-white/5 rounded-lg">
                                <button
                                  onClick={() => {
                                    setActiveTab("rag");
                                    setSelectedSourceType("markdown");
                                    setSearchQuery(dbeDocumentId);
                                    setSearchMode("search");
                                  }}
                                  className="text-xs text-[#94a3b8] hover:text-white font-mono font-medium text-left truncate flex-1 hover:underline cursor-pointer"
                                  title="Click to lookup in Unified RAG Studio"
                                >
                                  {dbeDocumentId}
                                </button>
                                <button
                                  onClick={() => {
                                    navigator.clipboard.writeText(dbeDocumentId);
                                    Swal.fire({
                                      title: "Copied!",
                                      text: "Document ID copied to clipboard",
                                      icon: "success",
                                      toast: true,
                                      position: "top-end",
                                      showConfirmButton: false,
                                      timer: 1500,
                                      background: "#1e2535",
                                      color: "#f1f5f9",
                                    });
                                  }}
                                  className="p-1 text-[#64748b] hover:text-[#94a3b8] rounded transition-colors"
                                  title="Copy Document ID"
                                >
                                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                                  </svg>
                                </button>
                              </div>
                            ) : (
                              <span className="text-xs text-[#64748b] italic">Not ingested</span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {dbeError && (
                    <div className="glass-panel p-5 bg-rose-500/5 border-rose-500/20 flex gap-3 text-xs text-rose-400">
                      <AlertTriangle className="h-4 w-4 shrink-0" />
                      <div>
                        <div className="font-bold">Diagnostics Execution Failure</div>
                        <div className="mt-1">{dbeError}</div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Live Telemetry monitor view */}
              {metricsTab === "metrics" && (
                <div className="flex flex-col gap-6 animate-fade-in">
                  {liveMetrics ? (
                    <>
                      {/* Overview status bar */}
                      <div className="glass-panel p-5 flex items-center justify-between bg-white/[0.01]">
                        <div className="flex items-center gap-3">
                          <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                          </span>
                          <div>
                            <span className="text-[10px] text-[#94a3b8] uppercase font-bold tracking-wider">Catalog Target</span>
                            <h3 className="text-sm font-semibold text-white font-mono">{liveMetrics.database_name}</h3>
                          </div>
                        </div>
                        <div className="flex items-center gap-6">
                          <div>
                            <span className="text-[10px] text-[#94a3b8] uppercase font-bold tracking-wider block text-right">Database Size</span>
                            <span className="text-sm font-bold text-white">{(liveMetrics.db_size_bytes / (1024 * 1024)).toFixed(2)} MB</span>
                          </div>
                          <div className="border-l border-white/5 pl-6">
                            <span className="text-[10px] text-[#94a3b8] uppercase font-bold tracking-wider block text-right">Last Sample</span>
                            <span className="text-xs font-mono text-[#00f2fe]">{DateTime.fromISO(liveMetrics.timestamp).toFormat("HH:mm:ss")}</span>
                          </div>
                        </div>
                      </div>

                      {/* Metrics Card Grid */}
                      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                        {/* 1. Connection Limits */}
                        <div className="glass-panel p-5 flex flex-col justify-between min-h-[120px] relative overflow-hidden group">
                          <div>
                            <span className="text-[10px] font-bold text-[#94a3b8] uppercase tracking-wider">Connections</span>
                            <div className="flex items-baseline gap-2 mt-2">
                              <span className="text-3xl font-extrabold text-white">{liveMetrics.total_connections}</span>
                              <span className="text-xs text-[#94a3b8]">/ {liveMetrics.max_connections} max</span>
                            </div>
                          </div>
                          <div className="mt-4">
                            <div className="flex justify-between text-[10px] text-[#94a3b8] mb-1">
                              <span>Connection pool usage</span>
                              <span>{Math.round((liveMetrics.total_connections / liveMetrics.max_connections) * 100)}%</span>
                            </div>
                            <div className="w-full h-1.5 bg-black/40 rounded-full overflow-hidden border border-white/5">
                              <div
                                className={`h-full rounded-full transition-all duration-500 ${
                                  (liveMetrics.total_connections / liveMetrics.max_connections) > 0.8
                                    ? "bg-rose-500"
                                    : (liveMetrics.total_connections / liveMetrics.max_connections) > 0.5
                                    ? "bg-amber-500"
                                    : "bg-emerald-500"
                                }`}
                                style={{ width: `${Math.min(100, (liveMetrics.total_connections / liveMetrics.max_connections) * 100)}%` }}
                              ></div>
                            </div>
                          </div>
                        </div>

                        {/* 2. Active vs Idle */}
                        <div className="glass-panel p-5 flex flex-col justify-between min-h-[120px]">
                          <div>
                            <span className="text-[10px] font-bold text-[#94a3b8] uppercase tracking-wider">Activity Distribution</span>
                            <div className="grid grid-cols-2 gap-4 mt-2">
                              <div>
                                <span className="text-xs text-[#94a3b8] block">Active Clients</span>
                                <span className="text-xl font-bold text-[#00f2fe]">{liveMetrics.active_connections}</span>
                              </div>
                              <div>
                                <span className="text-xs text-[#94a3b8] block">Idle Clients</span>
                                <span className="text-xl font-bold text-white">{liveMetrics.idle_connections}</span>
                              </div>
                            </div>
                          </div>
                          <p className="text-[10px] text-[#94a3b8] mt-3">Active vs Idle backends in pg_stat_activity</p>
                        </div>

                        {/* 3. Cache Hit Ratio */}
                        <div className="glass-panel p-5 flex flex-col justify-between min-h-[120px] relative overflow-hidden group">
                          <div>
                            <span className="text-[10px] font-bold text-[#94a3b8] uppercase tracking-wider">Cache Hit Rate</span>
                            <h2 className="text-3xl font-extrabold text-emerald-400 mt-2">{(liveMetrics.cache_hit_ratio * 100).toFixed(2)}%</h2>
                          </div>
                          <p className="text-[10px] text-[#94a3b8] mt-3">Shared buffer read efficiency of user tables</p>
                        </div>

                        {/* 4. Locks & Blocked Connections */}
                        <div className="glass-panel p-5 flex flex-col justify-between min-h-[120px]">
                          <div>
                            <span className="text-[10px] font-bold text-[#94a3b8] uppercase tracking-wider">Locks & Blocks</span>
                            <div className="grid grid-cols-2 gap-4 mt-2">
                              <div>
                                <span className="text-xs text-[#94a3b8] block">Active Locks</span>
                                <span className="text-xl font-bold text-[#9d4edd]">{liveMetrics.lock_count}</span>
                              </div>
                              <div>
                                <span className="text-xs text-[#94a3b8] block">Blocked Queries</span>
                                <span className={`text-xl font-bold ${liveMetrics.blocked_connections > 0 ? "text-rose-400 animate-pulse" : "text-white"}`}>
                                  {liveMetrics.blocked_connections}
                                </span>
                              </div>
                            </div>
                          </div>
                          <p className="text-[10px] text-[#94a3b8] mt-3">Active lock handles and waits on db resources</p>
                        </div>
                      </div>

                      {/* Charts section */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Live telemetry chart */}
                        <div className="glass-panel p-6">
                          <h3 className="text-xs font-semibold text-white uppercase tracking-wider mb-4">Connections & Locks Historical Stream</h3>
                          <div className="h-64">
                            <Line
                              data={liveTelemetryChartData}
                              options={{
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: {
                                  legend: {
                                    labels: { color: "#f8fafc", font: { family: "Outfit", size: 10 } },
                                  },
                                },
                                scales: {
                                  x: { grid: { display: false }, ticks: { color: "#94a3b8", font: { size: 9 } } },
                                  y: { grid: { color: "rgba(255,255,255,0.03)" }, ticks: { color: "#94a3b8", font: { size: 9 } } },
                                },
                              }}
                            />
                          </div>
                        </div>

                        {/* Transactions commits throughput chart */}
                        <div className="glass-panel p-6">
                          <h3 className="text-xs font-semibold text-white uppercase tracking-wider mb-4">Database Commits Trend</h3>
                          <div className="h-64">
                            <Line
                              data={transactionThroughputData}
                              options={{
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: {
                                  legend: {
                                    labels: { color: "#f8fafc", font: { family: "Outfit", size: 10 } },
                                  },
                                },
                                scales: {
                                  x: { grid: { display: false }, ticks: { color: "#94a3b8", font: { size: 9 } } },
                                  y: { grid: { color: "rgba(255,255,255,0.03)" }, ticks: { color: "#94a3b8", font: { size: 9 } } },
                                },
                              }}
                            />
                          </div>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="glass-panel flex flex-col items-center justify-center py-24 gap-4 text-center">
                      <div className="h-8 w-8 border-2 border-t-transparent border-[#00f2fe] rounded-full animate-spin"></div>
                      <span className="text-sm text-[#94a3b8]">Synchronizing with database engine...</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
