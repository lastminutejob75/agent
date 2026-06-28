import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api.js";
import { fetchTenantRequestsBundleCached } from "../lib/tenantRequestsCache.js";
import { toUiStatus, classifyRequestType, shouldShowHandoffInRequestInbox, shouldShowCallInRequestInbox, callbackRequestStatusRaw, callbackRequestPriority, callbackRequestSummary, callbackRequestSourceLabel, isLiveTransferHandoff } from "../lib/requestUiStatus.js";

const REQUEST_STATUS_OVERRIDES_KEY = "uwi_request_status_overrides";
const SYNC_BADGE_WINDOW_MS = 2 * 60 * 1000;

const TONE_BY_TYPE = {
  transfer: { border: "#8B5CF6", badgeBg: "#F5F3FF", badgeText: "#6D28D9" },
  callback: { border: "#F59E0B", badgeBg: "#FFF7ED", badgeText: "#B45309" },
  message: { border: "#0EA5E9", badgeBg: "#F0F9FF", badgeText: "#0369A1" },
  renewal: { border: "#3B82F6", badgeBg: "#EFF6FF", badgeText: "#1D4ED8" },
  document: { border: "#10B981", badgeBg: "#ECFDF5", badgeText: "#047857" },
  question: { border: "#94A3B8", badgeBg: "#F8FAFC", badgeText: "#475569" },
};

const PRIORITY_TONE = {
  Urgence: { border: "#EF4444", badgeBg: "#FEF2F2", badgeText: "#B91C1C", wait: "#DC2626" },
  Standard: { border: "#F59E0B", badgeBg: "#FFFBEB", badgeText: "#B45309", wait: "#EA580C" },
  Faible: { border: "#94A3B8", badgeBg: "#F8FAFC", badgeText: "#64748B", wait: "#64748B" },
};


function readRequestStatusOverrides() {
  if (typeof window === "undefined") return {};
  try {
    const parsed = JSON.parse(window.localStorage.getItem(REQUEST_STATUS_OVERRIDES_KEY) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function isFreshlySynced(updatedAt) {
  const date = new Date(String(updatedAt || "").trim());
  if (Number.isNaN(date.getTime())) return false;
  return Date.now() - date.getTime() <= SYNC_BADGE_WINDOW_MS;
}

function formatDate(value) {
  const raw = String(value || "").trim();
  if (!raw) return "—";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  if (sameDay) return `Aujourd'hui ${date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`;
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return `Hier ${date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`;
  }
  return date.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" }) + " " + date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

function getWaitingTime(value) {
  const raw = String(value || "").trim();
  if (!raw) return "—";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return "—";
  const minutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000));
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  if (hours < 24) return `${hours}h${String(rem).padStart(2, "0")}`;
  const days = Math.floor(hours / 24);
  return `${days}j ${hours % 24}h`;
}

function minutesSince(value) {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return null;
  return Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000));
}

function formatDelayFromMinutes(minutes) {
  if (!Number.isFinite(minutes)) return "—";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return `${hours}h${String(rem).padStart(2, "0")}`;
}

function requestPriority(callOrHandoff) {
  const p = String(callOrHandoff.priority || callOrHandoff.handoff_priority || "").toLowerCase();
  const summary = String(callOrHandoff.summary || "").toLowerCase();
  if (p.includes("urgent") || summary.includes("urgence")) return "Urgence";
  if (p.includes("low") || p.includes("faible")) return "Faible";
  return "Standard";
}

export default function AppRequests() {
  const [searchParams] = useSearchParams();
  const [calls, setCalls] = useState([]);
  const [handoffs, setHandoffs] = useState([]);
  const [callbacks, setCallbacks] = useState([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("À traiter");
  const [typeFilter, setTypeFilter] = useState("Tous types");
  const [priorityFilter, setPriorityFilter] = useState("Toutes priorités");
  const [sortOrder, setSortOrder] = useState("desc");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [requestStatusOverrides, setRequestStatusOverrides] = useState(() => readRequestStatusOverrides());
  const listAnchorRef = useRef(null);

  useEffect(() => {
    const urlStatus = String(searchParams.get("status") || "").trim();
    const urlType = String(searchParams.get("type") || "").trim();
    const urlPriority = String(searchParams.get("priority") || "").trim();
    const urlQuery = String(searchParams.get("q") || "").trim();
    const urlSort = String(searchParams.get("sort") || "").trim().toLowerCase();

    if (["À traiter", "En cours", "Traitées", "Toutes"].includes(urlStatus)) setStatus(urlStatus);
    if (["Tous types", "Transfert humain", "Rappel", "Message", "Renouvellement", "Document", "Question"].includes(urlType)) setTypeFilter(urlType);
    if (["Toutes priorités", "Urgence", "Standard", "Faible"].includes(urlPriority)) setPriorityFilter(urlPriority);
    if (urlQuery) setQuery(urlQuery);
    if (urlSort === "asc" || urlSort === "desc") setSortOrder(urlSort);
  }, [searchParams]);

  useEffect(() => {
    const refresh = () => setRequestStatusOverrides(readRequestStatusOverrides());
    const onStorage = (event) => {
      if (!event.key || event.key === REQUEST_STATUS_OVERRIDES_KEY) refresh();
    };
    window.addEventListener("storage", onStorage);
    window.addEventListener("uwi:request-status-updated", refresh);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("uwi:request-status-updated", refresh);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const { callsRes, handoffsRes, callbacksRes } = await fetchTenantRequestsBundleCached(api, {
          callsQuery: "?limit=50&days=30&compact=1",
          handoffsQuery: "?limit=50",
          callbacksQuery: "?limit=50",
        });
        if (cancelled) return;
        setCalls(Array.isArray(callsRes?.calls) ? callsRes.calls : []);
        setHandoffs(Array.isArray(handoffsRes?.items) ? handoffsRes.items : []);
        setCallbacks(Array.isArray(callbacksRes?.items) ? callbacksRes.items : []);
      } catch (e) {
        if (!cancelled) setError(e?.message || "Erreur chargement des demandes");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const requests = useMemo(() => {
    const fromCalls = calls
      .filter((c) => c.followup_state === "callback" || c.status === "TRANSFERRED" || c.reason_category === "urgency")
      .filter((c) => shouldShowCallInRequestInbox(c, callbacks))
      .map((c) => {
        const t = classifyRequestType({ ...c, _source: "call" });
        const statusRaw = c.followup_state === "processed" ? "processed" : "callback_created";
        return {
          id: `call-${c.call_id || c.id}`,
          patientId: `patient-${String(c.patient_name || "patient").toLowerCase().replace(/\s+/g, "-")}`,
          patientName: c.patient_name || "Patient",
          initials: (String(c.patient_name || "PT").split(" ").slice(0, 2).map((x) => x[0] || "").join("").toUpperCase() || "PT"),
          type: t.type,
          typeKey: t.typeKey,
          priority: requestPriority(c),
          status: toUiStatus(statusRaw),
          status_raw: statusRaw,
          summary: c.summary || c.reason_label || "Demande transférée nécessitant une action humaine.",
          phone: c.customer_number || "—",
          createdAtLabel: formatDate(c.started_at || c.last_event_at),
          source: "Via appel",
          waitingTime: getWaitingTime(c.started_at || c.last_event_at),
          createdAt: c.started_at || c.last_event_at,
        };
      });

    const fromHandoffs = handoffs
      .filter((h) => shouldShowHandoffInRequestInbox(h, callbacks))
      .map((h) => {
        const t = classifyRequestType({ ...h, _source: "handoff" });
        const rawStatus = String(h.status || "").toLowerCase();
        return {
          id: `req-${String(h.id || "").padStart(3, "0")}`,
          patientId: `patient-${String(h.display_name || "patient").toLowerCase().replace(/\s+/g, "-")}`,
          patientName: h.display_name || "Patient",
          initials: (String(h.display_name || "PT").split(" ").slice(0, 2).map((x) => x[0] || "").join("").toUpperCase() || "PT"),
          type: t.type,
          typeKey: t.typeKey,
          priority: requestPriority(h),
          status: toUiStatus(rawStatus),
          status_raw: rawStatus,
          summary: h.summary || h.reason || "Demande transférée nécessitant une action humaine.",
          phone: h.patient_phone || "—",
          createdAtLabel: formatDate(h.created_at),
          source: isLiveTransferHandoff(h) ? "Transfert live" : "Appel vocal",
          waitingTime: getWaitingTime(h.created_at),
          createdAt: h.created_at,
          handoffId: h.id || null,
        };
      });

    const fromCallbacks = callbacks.map((c) => {
      const statusRaw = callbackRequestStatusRaw(c);
      const isMessage = String(c?.reason || "").toLowerCase() === "message";
      return {
        id: `callback-${c.id}`,
        patientId: `patient-${String(c.name || "patient").toLowerCase().replace(/\s+/g, "-")}`,
        patientName: c.name || "Patient",
        initials: (String(c.name || "PT").split(" ").slice(0, 2).map((x) => x[0] || "").join("").toUpperCase() || "PT"),
        type: isMessage ? "Message" : "Rappel",
        typeKey: isMessage ? "message" : "callback",
        priority: callbackRequestPriority(c),
        status: toUiStatus(statusRaw),
        status_raw: statusRaw,
        summary: callbackRequestSummary(c),
        phone: c.phone || "—",
        createdAtLabel: formatDate(c.created_at),
        source: callbackRequestSourceLabel(c),
        unknownPatient: Boolean(c.unmatched),
        waitingTime: getWaitingTime(c.created_at),
        createdAt: c.created_at,
        callbackId: c.id,
        handoffId: c.handoff_id || null,
        callId: c.call_id || null,
      };
    });

    return [...fromHandoffs, ...fromCalls, ...fromCallbacks]
      .map((item) => {
        const override = requestStatusOverrides[item.id];
        if (!override?.status_raw) return item;
        const raw = String(override.status_raw).toLowerCase();
        return {
          ...item,
          status_raw: raw,
          status: toUiStatus(raw),
          syncedRecently: isFreshlySynced(override.updated_at),
        };
      })
      .sort((a, b) => new Date(b.createdAt || 0).getTime() - new Date(a.createdAt || 0).getTime());
  }, [calls, handoffs, callbacks, requestStatusOverrides]);

  const kpis = useMemo(() => {
    const toProcess = requests.filter((r) => r.status === "À traiter").length;
    const urgent = requests.filter((r) => r.priority === "Urgence").length;
    const transfers = requests.filter((r) => r.type === "Transfert humain").length;
    const activeRequests = requests.filter((r) => {
      const raw = String(r.status_raw || "").toLowerCase();
      return raw !== "processed" && raw !== "cancelled";
    });
    const avgDelayForPriority = (priority) => {
      const values = activeRequests
        .filter((r) => r.priority === priority)
        .map((r) => minutesSince(r.createdAt))
        .filter((x) => Number.isFinite(x));
      if (!values.length) return "—";
      const avgMinutes = Math.round(values.reduce((sum, x) => sum + x, 0) / values.length);
      return formatDelayFromMinutes(avgMinutes);
    };
    return {
      toProcess,
      urgent,
      transfers,
      delayUrgent: avgDelayForPriority("Urgence"),
      delayStandard: avgDelayForPriority("Standard"),
      delayLow: avgDelayForPriority("Faible"),
    };
  }, [requests]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = requests.filter((r) => {
      const byStatus = status === "Toutes" || r.status === status;
      const byType = typeFilter === "Tous types" || r.type === typeFilter;
      const byPriority = priorityFilter === "Toutes priorités" || r.priority === priorityFilter;
      const byQuery = !q || [r.patientName, r.summary, r.phone, r.type].join(" ").toLowerCase().includes(q);
      return byStatus && byType && byPriority && byQuery;
    });
    return filtered.sort((a, b) => {
      const aTime = new Date(a.createdAt || 0).getTime();
      const bTime = new Date(b.createdAt || 0).getTime();
      return sortOrder === "desc" ? bTime - aTime : aTime - bTime;
    });
  }, [requests, query, status, typeFilter, priorityFilter, sortOrder]);

  function scrollToRequests() {
    window.requestAnimationFrame(() => {
      if (listAnchorRef.current) {
        listAnchorRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  }

  function focusToProcess() {
    setStatus("À traiter");
    setPriorityFilter("Toutes priorités");
    setTypeFilter("Tous types");
    scrollToRequests();
  }

  function focusUrgent() {
    setStatus("Toutes");
    setPriorityFilter("Urgence");
    setTypeFilter("Tous types");
    scrollToRequests();
  }

  function focusTransfers() {
    setStatus("Toutes");
    setPriorityFilter("Toutes priorités");
    setTypeFilter("Transfert humain");
    scrollToRequests();
  }

  function focusStandard() {
    setStatus("Toutes");
    setPriorityFilter("Standard");
    setTypeFilter("Tous types");
    scrollToRequests();
  }

  function focusLow() {
    setStatus("Toutes");
    setPriorityFilter("Faible");
    setTypeFilter("Tous types");
    scrollToRequests();
  }

  function resetFilters() {
    setQuery("");
    setStatus("À traiter");
    setTypeFilter("Tous types");
    setPriorityFilter("Toutes priorités");
    setSortOrder("desc");
  }

  return (
    <div className="uwi-requests-page" style={{ minHeight: "100%", background: "#F7FAFC", padding: 24 }}>
      <style>{`
        .uwi-requests-page,
        .uwi-requests-page * {
          box-sizing: border-box;
        }
        .uwi-requests-page {
          overflow-x: clip;
          max-width: 100%;
        }
        .uwi-requests-inner {
          max-width: 1220px;
          margin: 0 auto;
          width: 100%;
          min-width: 0;
        }
        .uwi-requests-page .uwi-requests-header { margin: 0; }
        .uwi-requests-page .uwi-requests-h1 { margin: 0; font-size: 38px; font-weight: 900; letter-spacing: -.03em; color: #0A1628; }
        .uwi-requests-page .uwi-requests-sub { margin: 8px 0 0; font-size: 15px; color: #475569; }
        .uwi-requests-page .uwi-requests-metrics { margin-top: 18px; display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 12px; }
        .uwi-requests-page .uwi-requests-metrics > * { min-width: 0; }
        .uwi-requests-page .uwi-requests-filters-row { display: grid; grid-template-columns: 1fr auto auto auto auto auto; gap: 10px; align-items: center; min-width: 0; }
        .uwi-requests-page .uwi-requests-filters-row > * { min-width: 0; max-width: 100%; }
        .uwi-requests-page .uwi-requests-search {
          width: 100%;
          min-width: 0;
          height: 42px;
          border-radius: 10px;
          border: 1px solid #DDE7F1;
          padding: 0 12px;
          font-size: 14px;
          font-weight: 600;
          color: #0A1628;
          outline: none;
        }
        .uwi-requests-page .uwi-requests-select {
          width: 100%;
          min-width: 0;
          max-width: 100%;
          height: 42px;
          border-radius: 10px;
          border: 1px solid #DDE7F1;
          background: #fff;
          color: #0A1628;
          font-weight: 700;
          padding: 0 10px;
        }
        .uwi-requests-page .uwi-requests-action-btn {
          width: 100%;
          min-width: 0;
          height: 42px;
          border-radius: 10px;
          font-weight: 700;
          padding: 0 12px;
          cursor: pointer;
          white-space: nowrap;
        }
        .uwi-requests-page .uwi-delay-metric-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; min-width: 0; }
        .uwi-requests-page .uwi-delay-metric-grid > button { min-width: 0; }
        .uwi-requests-page .uwi-requests-segment {
          display: flex;
          align-items: center;
          gap: 6px;
          border: 1px solid #E2EAF4;
          border-radius: 10px;
          background: #fff;
          padding: 4px;
          min-width: 0;
          max-width: 100%;
          overflow-x: auto;
          -webkit-overflow-scrolling: touch;
        }
        .uwi-requests-page .uwi-requests-segment button {
          flex: 0 0 auto;
          white-space: nowrap;
        }
        .uwi-requests-page .uwi-metric-btn {
          width: 100%;
          min-width: 0;
        }
        @media (max-width: 1024px) {
          .uwi-requests-page .uwi-requests-filters-row {
            grid-template-columns: 1fr 1fr !important;
          }
          .uwi-requests-page .uwi-requests-filters-row > :first-child,
          .uwi-requests-page .uwi-requests-filters-row > .uwi-requests-segment {
            grid-column: 1 / -1 !important;
          }
        }
        @media (max-width: 760px) {
          .uwi-requests-page { padding: 10px !important; }
          .uwi-requests-page .uwi-requests-header { display: none; }
          .uwi-requests-page .uwi-requests-metrics {
            grid-template-columns: repeat(2, minmax(0,1fr)) !important;
            gap: 8px !important;
            margin-top: 0 !important;
          }
          .uwi-requests-page .uwi-delay-metric { grid-column: 1 / -1 !important; }
          .uwi-requests-page .uwi-delay-metric-grid {
            grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
            gap: 6px !important;
          }
          .uwi-requests-page .uwi-delay-metric-grid > button { padding: 8px 6px !important; }
          .uwi-requests-page .uwi-delay-metric-grid > button > div:last-child {
            font-size: 18px !important;
          }
          .uwi-requests-page .uwi-requests-filters-row {
            grid-template-columns: 1fr !important;
            gap: 8px !important;
          }
          .uwi-requests-page .uwi-requests-filters-row > * {
            width: 100% !important;
            max-width: 100% !important;
          }
          .uwi-requests-page .uwi-requests-segment {
            display: grid !important;
            grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
            gap: 6px !important;
            overflow: visible !important;
            padding: 6px !important;
          }
          .uwi-requests-page .uwi-requests-segment button {
            width: 100% !important;
            flex: initial !important;
            padding: 10px 8px !important;
            font-size: 11px !important;
            white-space: normal !important;
            line-height: 1.2 !important;
            text-align: center !important;
          }
          .uwi-requests-page .uwi-requests-filters-card { padding: 10px !important; }
          .uwi-requests-page .uwi-metric-value { font-size: 26px !important; }
          .uwi-requests-page .uwi-metric-btn { padding: 12px !important; }
          .uwi-requests-page .uwi-delay-metric { padding: 12px !important; }
        }
      `}</style>
      <div className="uwi-requests-inner">
        <div className="uwi-requests-header">
          <h1 className="uwi-requests-h1">Demandes patients</h1>
          <p className="uwi-requests-sub">Demandes transférées par Clara nécessitant une action du cabinet.</p>
        </div>

        <div className="uwi-requests-metrics">
          <Metric title={String(kpis.toProcess)} subtitle="à traiter" onClick={focusToProcess} active={status === "À traiter" && priorityFilter === "Toutes priorités" && typeFilter === "Tous types"} />
          <Metric title={String(kpis.urgent)} subtitle="urgentes" danger onClick={focusUrgent} active={priorityFilter === "Urgence"} />
          <Metric title={String(kpis.transfers)} subtitle="transferts humains" info onClick={focusTransfers} active={typeFilter === "Transfert humain"} />
          <DelayMetric
            urgentDelay={kpis.delayUrgent}
            standardDelay={kpis.delayStandard}
            lowDelay={kpis.delayLow}
            onUrgentClick={focusUrgent}
            onStandardClick={focusStandard}
            onLowClick={focusLow}
            urgentActive={priorityFilter === "Urgence"}
            standardActive={priorityFilter === "Standard"}
            lowActive={priorityFilter === "Faible"}
          />
        </div>

        <div className="uwi-requests-filters-card" style={{ marginTop: 14, background: "#fff", border: "1px solid #E2EAF4", borderRadius: 16, padding: 14 }}>
          <div className="uwi-requests-filters-row">
            <input
              className="uwi-requests-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Rechercher un patient, un motif, un téléphone..."
            />
            <Segment value={status} onChange={setStatus} options={["À traiter", "En cours", "Traitées", "Toutes"]} />
            <SelectLike value={typeFilter} onChange={setTypeFilter} options={["Tous types", "Transfert humain", "Rappel", "Message", "Renouvellement", "Document", "Question"]} />
            <SelectLike value={priorityFilter} onChange={setPriorityFilter} options={["Toutes priorités", "Urgence", "Standard", "Faible"]} />
            <button
              type="button"
              className="uwi-requests-action-btn"
              onClick={() => setSortOrder((prev) => (prev === "desc" ? "asc" : "desc"))}
              style={{
                border: "1px solid #DDE7F1",
                background: "#fff",
                color: "#475569",
              }}
            >
              {sortOrder === "desc" ? "Plus récentes" : "Plus anciennes"}
            </button>
            <button
              type="button"
              className="uwi-requests-action-btn"
              onClick={resetFilters}
              style={{
                border: "1px solid #CBD5E1",
                background: "#F8FAFC",
                color: "#334155",
                fontWeight: 800,
              }}
            >
              Réinitialiser
            </button>
          </div>
        </div>

        <p style={{ margin: "14px 2px", fontSize: 13, color: "#64748B", fontWeight: 700 }}>Cliquez sur une demande pour ouvrir la fiche patient.</p>

        {error ? (
          <div style={{ marginBottom: 10, border: "1px solid #FECACA", background: "#FFF1F2", color: "#B91C1C", borderRadius: 10, padding: "10px 12px", fontSize: 13, fontWeight: 700 }}>
            {error}
          </div>
        ) : null}

        <div ref={listAnchorRef} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {!loading && rows.length === 0 ? (
            <div style={{ border: "1px solid #E2EAF4", borderRadius: 12, background: "#fff", padding: 16, color: "#64748B", fontWeight: 700 }}>
              Aucune demande pour ces filtres.
            </div>
          ) : null}

          {rows.map((request) => {
            const typeTone = TONE_BY_TYPE[request.typeKey] || TONE_BY_TYPE.question;
            const priorityTone = PRIORITY_TONE[request.priority] || PRIORITY_TONE.Standard;
            const rawStatus = String(request.status_raw || "").toLowerCase();
            const isCancelled = rawStatus === "cancelled";
            const isProcessed = rawStatus === "processed";
            const syncedRecently = !!request.syncedRecently;
            const leftBorder = isCancelled ? "#94A3B8" : isProcessed ? "#10B981" : request.priority === "Urgence" ? priorityTone.border : typeTone.border;
            const statusBadge = isCancelled
              ? { label: "Annulée", bg: "#F1F5F9", color: "#475569" }
              : isProcessed
                ? { label: "Traitée", bg: "#ECFDF5", color: "#047857" }
                : request.status === "En cours"
                  ? { label: "En cours", bg: "#FFF7ED", color: "#B45309" }
                  : { label: "À traiter", bg: "#FEF2F2", color: "#B91C1C" };
            const params = new URLSearchParams();
            params.set("requestId", request.id);
            if (request.phone) params.set("phone", request.phone);
            if (request.patientName) params.set("patientName", request.patientName);
            if (request.summary) params.set("summary", request.summary);
            params.set("type", request.type);
            params.set("status", statusBadge.label);
            params.set("source", request.source);
            params.set("createdAtLabel", request.createdAtLabel);
            return (
              <Link
                key={request.id}
                to={`/app/patient-dashboard?${params.toString()}`}
                style={{
                  textDecoration: "none",
                  color: "inherit",
                  display: "block",
                  border: "1px solid #E2EAF4",
                  borderLeft: `4px solid ${leftBorder}`,
                  background: syncedRecently ? "#FFFBEB" : isCancelled ? "#F8FAFC" : isProcessed ? "#F0FDF4" : "#fff",
                  borderRadius: 14,
                  padding: "14px 16px",
                  transition: "all .15s ease",
                }}
                className={`request-inbox-row${syncedRecently ? " request-inbox-row--synced" : ""}`}
              >
                <div className="request-row-grid" style={{ display: "grid", gridTemplateColumns: "56px 1fr 28px", alignItems: "center", gap: 12 }}>
                  <div className="request-row-avatar" style={{ width: 46, height: 46, borderRadius: "50%", display: "grid", placeItems: "center", fontWeight: 900, fontSize: 16, color: "#0A1628", background: "#ECFDF5", border: "1px solid #BBF7D0" }}>
                    {request.initials}
                  </div>
                  <div className="request-row-main" style={{ minWidth: 0 }}>
                    <div className="request-row-name" style={{ fontSize: 19, fontWeight: 900, color: "#0A1628", lineHeight: 1.25, wordBreak: "break-word" }}>
                      {request.patientName}
                    </div>
                    <div className="request-row-badges" style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                      <span style={{ borderRadius: 8, padding: "2px 8px", fontSize: 11, fontWeight: 800, background: typeTone.badgeBg, color: typeTone.badgeText }}>{request.type}</span>
                      <span style={{ borderRadius: 8, padding: "2px 8px", fontSize: 11, fontWeight: 800, background: priorityTone.badgeBg, color: priorityTone.badgeText }}>{request.priority}</span>
                      <span style={{ borderRadius: 8, padding: "2px 8px", fontSize: 11, fontWeight: 800, background: statusBadge.bg, color: statusBadge.color }}>{statusBadge.label}</span>
                      {request.unknownPatient ? (
                        <span
                          title="Appelant non enregistré au cabinet : message laissé, pas de transfert direct."
                          style={{ borderRadius: 8, padding: "2px 8px", fontSize: 11, fontWeight: 800, background: "#F1F5F9", color: "#475569", border: "1px solid #CBD5E1" }}
                        >
                          Inconnu
                        </span>
                      ) : null}
                      {syncedRecently ? (
                        <span style={{ borderRadius: 8, padding: "2px 8px", fontSize: 11, fontWeight: 900, background: "#FEF3C7", color: "#92400E" }}>
                          mis à jour
                        </span>
                      ) : null}
                    </div>
                    <div className="request-row-summary" style={{ marginTop: 4, fontSize: 14, color: "#334155", fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {request.summary}
                    </div>
                    <div className="request-row-meta" style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4, fontSize: 13, color: "#64748B", fontWeight: 700 }}>
                      <span style={{ color: "#0F766E", wordBreak: "break-all" }}>{request.phone}</span>
                      <span>{request.createdAtLabel}</span>
                      <span>{request.source}</span>
                      <span style={{ color: priorityTone.wait, fontWeight: 900 }}>Attente : {request.waitingTime}</span>
                    </div>
                  </div>
                  <div className="request-row-arrow" style={{ fontSize: 30, color: "#94A3B8", fontWeight: 300 }}>›</div>
                </div>
              </Link>
            );
          })}
        </div>
      </div>

      <style>{`
        .request-inbox-row:hover {
          transform: translateY(-1px);
          border-color: #CBD5E1 !important;
          box-shadow: 0 10px 20px rgba(15,23,42,.08);
        }
        .request-inbox-row--synced {
          animation: syncedFlash 900ms ease-out 1;
        }
        @keyframes syncedFlash {
          0% {
            box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.45);
            transform: translateY(-1px);
          }
          45% {
            box-shadow: 0 0 0 10px rgba(245, 158, 11, 0.18);
          }
          100% {
            box-shadow: 0 0 0 0 rgba(245, 158, 11, 0);
            transform: translateY(0);
          }
        }
        @media (max-width: 760px) {
          .request-inbox-row {
            padding: 12px !important;
          }
          .request-row-grid {
            grid-template-columns: 40px minmax(0, 1fr) !important;
            gap: 10px !important;
            align-items: flex-start !important;
          }
          .request-row-avatar {
            width: 40px !important;
            height: 40px !important;
            font-size: 13px !important;
          }
          .request-row-main {
            min-width: 0;
            overflow: hidden;
          }
          .request-row-name {
            font-size: 16px !important;
          }
          .request-row-badges {
            gap: 4px !important;
            margin-top: 4px !important;
          }
          .request-row-badges > span {
            font-size: 10px !important;
            padding: 2px 6px !important;
          }
          .request-row-summary {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: initial !important;
            display: block !important;
            font-size: 13px !important;
            line-height: 1.4 !important;
          }
          .request-row-meta {
            margin-top: 6px !important;
            font-size: 12px !important;
          }
          .request-row-arrow {
            display: none !important;
          }
        }
        .request-inbox-row:hover > div > div:last-child {
          transform: translateX(3px);
          color: #059669;
        }
        @media (min-width: 761px) {
          .request-row-meta {
            flex-direction: row !important;
            flex-wrap: wrap !important;
            align-items: center !important;
            gap: 8px !important;
          }
        }
      `}</style>
    </div>
  );
}

function Metric({ title, subtitle, danger = false, info = false, onClick, active = false }) {
  const color = danger ? "#DC2626" : info ? "#2563EB" : "#059669";
  return (
    <button
      type="button"
      className="uwi-metric-btn"
      onClick={onClick}
      style={{
        border: active ? "1px solid #93C5FD" : "1px solid #E2EAF4",
        borderRadius: 14,
        background: active ? "#F8FBFF" : "#fff",
        padding: 16,
        textAlign: "left",
        cursor: "pointer",
        transition: "all .15s ease",
      }}
    >
      <div className="uwi-metric-value" style={{ fontSize: 36, lineHeight: 1, fontWeight: 900, letterSpacing: "-.04em", color }}>{title}</div>
      <div style={{ marginTop: 4, fontSize: 13, fontWeight: 800, color: "#334155" }}>{subtitle}</div>
    </button>
  );
}

function DelayMetric({
  urgentDelay = "48 min",
  standardDelay = "3h12",
  lowDelay = "6h40",
  onUrgentClick,
  onStandardClick,
  onLowClick,
  urgentActive = false,
  standardActive = false,
  lowActive = false,
}) {
  return (
    <div className="uwi-delay-metric" style={{ border: "1px solid #E2EAF4", borderRadius: 14, background: "#fff", padding: 16 }}>
      <div style={{ fontSize: 13, fontWeight: 800, color: "#334155" }}>Délais de traitement</div>
      <div className="uwi-delay-metric-grid" style={{ marginTop: 8 }}>
        <button
          type="button"
          onClick={onUrgentClick}
          style={{
            border: urgentActive ? "1px solid #FCA5A5" : "1px solid #FEE2E2",
            borderRadius: 10,
            background: urgentActive ? "#FEF2F2" : "#fff",
            padding: 8,
            textAlign: "left",
            cursor: "pointer",
            transition: "all .15s ease",
          }}
        >
          <div style={{ fontSize: 12, color: "#64748B", fontWeight: 700 }}>Urgences</div>
          <div style={{ fontSize: 24, color: "#DC2626", fontWeight: 900 }}>{urgentDelay}</div>
        </button>
        <button
          type="button"
          onClick={onStandardClick}
          style={{
            border: standardActive ? "1px solid #FDBA74" : "1px solid #FFEDD5",
            borderRadius: 10,
            background: standardActive ? "#FFF7ED" : "#fff",
            padding: 8,
            textAlign: "left",
            cursor: "pointer",
            transition: "all .15s ease",
          }}
        >
          <div style={{ fontSize: 12, color: "#64748B", fontWeight: 700 }}>Standard</div>
          <div style={{ fontSize: 24, color: "#EA580C", fontWeight: 900 }}>{standardDelay}</div>
        </button>
        <button
          type="button"
          onClick={onLowClick}
          style={{
            border: lowActive ? "1px solid #CBD5E1" : "1px solid #E2E8F0",
            borderRadius: 10,
            background: lowActive ? "#F8FAFC" : "#fff",
            padding: 8,
            textAlign: "left",
            cursor: "pointer",
            transition: "all .15s ease",
          }}
        >
          <div style={{ fontSize: 12, color: "#64748B", fontWeight: 700 }}>Faible</div>
          <div style={{ fontSize: 24, color: "#64748B", fontWeight: 900 }}>{lowDelay}</div>
        </button>
      </div>
    </div>
  );
}

function Segment({ value, onChange, options }) {
  return (
    <div className="uwi-requests-segment" style={{ display: "flex", alignItems: "center", gap: 6, border: "1px solid #E2EAF4", borderRadius: 10, background: "#fff", padding: 4 }}>
      {options.map((option) => (
        <button
          key={option}
          type="button"
          onClick={() => onChange(option)}
          style={{
            border: "none",
            borderRadius: 8,
            padding: "7px 10px",
            background: value === option ? "#E8F7F7" : "transparent",
            color: value === option ? "#007C84" : "#475569",
            fontWeight: 800,
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          {option}
        </button>
      ))}
    </div>
  );
}

function SelectLike({ value, onChange, options }) {
  return (
    <select
      className="uwi-requests-select"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {options.map((opt) => (
        <option key={opt} value={opt}>
          {opt}
        </option>
      ))}
    </select>
  );
}
