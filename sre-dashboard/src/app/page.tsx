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
  const [activeTab, setActiveTab] = useState<"overview" | "incidents" | "rag" | "simulator">("overview");
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
        borderColor: "#00f2fe",
        backgroundColor: "rgba(0, 242, 254, 0.05)",
        fill: true,
        tension: 0.4,
        borderWidth: 2,
        pointRadius: 3,
      },
      {
        label: "Replica Lag (sec)",
        data: [1.2, 1.5, 3.4, 8.9, 12.4, 4.2, 2.1],
        borderColor: "#9d4edd",
        backgroundColor: "rgba(157, 78, 221, 0.05)",
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
        backgroundColor: "rgba(59, 130, 246, 0.4)",
        borderColor: "#3b82f6",
        borderWidth: 1,
        borderRadius: 4,
      },
    ],
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
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-[#00f2fe] to-[#9d4edd] flex items-center justify-center shadow-[0_0_15px_rgba(0,242,254,0.3)] shrink-0">
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
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`flex items-center gap-3 py-3 px-3 rounded-lg text-sm transition-all duration-300 w-full ${
                  activeTab === item.id
                    ? "bg-gradient-to-r from-[rgba(0,242,254,0.1)] to-[rgba(157,78,221,0.05)] text-[#00f2fe] border-l-2 border-[#00f2fe]"
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
              <span className="text-[#00f2fe]">{settings.llm_provider}</span>
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
        <header className="dashboard-header flex items-center justify-between px-6 py-4 border-b border-[rgba(255,255,255,0.06)] bg-[#0a0e1a]/40 backdrop-blur-xl z-10 shrink-0">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-semibold text-white tracking-wide">
              {activeTab === "overview" && "Operational Overview"}
              {activeTab === "incidents" && "Operational Memory Alert Feed"}
              {activeTab === "rag" && "Cross-Vertical RAG Studio"}
              {activeTab === "simulator" && "Playbook Ingestion & Webhook Simulator"}
            </h1>
          </div>

          {/* BACKEND API STATUS BAR */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 bg-[#0e1628] border border-[rgba(255,255,255,0.06)] rounded-full px-3 py-1 text-xs">
              <span className="text-[#94a3b8]">API backend:</span>
              <span className="font-mono text-white select-all">{apiBase}</span>
            </div>

            <div className="flex items-center gap-2 bg-[#0e1628] border border-[rgba(255,255,255,0.06)] rounded-full px-3 py-1 text-xs">
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
                      <span className="px-3 py-1 rounded-full text-xs font-semibold tracking-wider text-[#00f2fe] bg-[rgba(0,242,254,0.1)] uppercase">
                        SRE Intelligent Platform
                      </span>
                      <h2 className="text-4xl md:text-6xl font-bold tracking-tight text-white mt-4 leading-tight">
                        Visualizing System <br />
                        <span className="bg-clip-text text-transparent bg-gradient-to-r from-[#00f2fe] to-[#9d4edd]">
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
                  <div className="h-full w-full bg-[#0a101f] p-6 flex flex-col gap-6 overflow-hidden rounded-2xl border border-white/5 relative">
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
                        <span className="text-2xl font-bold text-[#00f2fe] mt-2">{metrics.queriesCount}</span>
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
                            ? "bg-[rgba(0,242,254,0.1)] text-[#00f2fe] border border-[rgba(0,242,254,0.2)]"
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
                            ? "bg-[rgba(157,78,221,0.1)] text-[#9d4edd] border border-[rgba(157,78,221,0.2)]"
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
                      className="w-full accent-[#00f2fe]"
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
                    <Upload className="h-10 w-10 text-[#00f2fe] mb-3" />
                    {simFile ? (
                      <div className="text-center">
                        <span className="text-sm font-semibold text-white block truncate max-w-xs">{simFile.name}</span>
                        <span className="text-[11px] text-[#00f2fe] mt-1 block">
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
                    <Terminal className="h-4 w-4 text-[#00f2fe]" />
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
        </section>
      </main>
    </div>
  );
}
