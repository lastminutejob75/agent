import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Trash2 } from "lucide-react";
import { adminApi } from "../../lib/adminApi.js";
import { getLeadsSummary, listAdminLeads } from "../../lib/adminLeadsApi.js";
import { applySearchParamsUpdates } from "../../lib/adminLeadsFilters.js";

const BRAND = {
  teal: "#009CA4",
  tealDark: "#007C84",
  navy: "#071A33",
  ink: "#0A1628",
  yellow: "#F5C842",
  bg: "#F4F8FA",
  border: "#DCE8EC",
  muted: "#667085",
  red: "#D92D20",
  orange: "#F79009",
  blue: "#2563EB",
  green: "#039855",
  purple: "#7C3AED",
  softTeal: "#E7F7F7",
};

const STATUS_LABEL = {
  new: "Nouveau",
  contacted: "Contacté",
  interested: "Intéressé",
  demo_scheduled: "Démo prévue",
  trial_offered: "Essai proposé",
  trial_started: "Essai gratuit",
  converted: "Converti",
  lost: "Perdu",
  later: "À relancer plus tard",
};

const PIPELINE = [
  { id: "all", label: "Tous" },
  { id: "new", label: "Nouveau" },
  { id: "to_contact", label: "À contacter" },
  { id: "contacted", label: "Contacté" },
  { id: "demo", label: "Démo prévue" },
  { id: "trial", label: "Essai gratuit" },
  { id: "converted", label: "Converti" },
  { id: "lost", label: "Perdu" },
];

const SEGMENT_LABELS = {
  Tous: "Tous",
  grand_account: "Grands comptes",
  high: "Priorité haute",
  solo_practitioner: "Praticiens seuls",
  without_assistant: "Sans secrétariat",
  standard: "Standard",
};

function segmentLabel(segment) {
  return SEGMENT_LABELS[segment] || String(segment || "Standard").replace(/_/g, " ");
}

function tone(kind, filled = false) {
  const map = {
    teal: [BRAND.teal, BRAND.softTeal],
    navy: [BRAND.navy, "#EAF0F6"],
    blue: [BRAND.blue, "#EAF1FF"],
    green: [BRAND.green, "#EAF8F0"],
    orange: [BRAND.orange, "#FFF4E5"],
    red: [BRAND.red, "#FEECEC"],
    purple: [BRAND.purple, "#F3E8FF"],
    yellow: ["#B7791F", "#FFF8D8"],
    gray: [BRAND.muted, "#F2F4F7"],
  };
  const [solid, soft] = map[kind] || map.gray;
  return filled
    ? { background: solid, color: "#fff", borderColor: solid }
    : { background: soft, color: solid, borderColor: `${solid}33` };
}

function statusTone(status) {
  if (status === "new") return "teal";
  if (status === "contacted" || status === "interested") return "blue";
  if (status === "demo_scheduled") return "purple";
  if (status === "trial_offered" || status === "trial_started") return "yellow";
  if (status === "converted") return "green";
  if (status === "lost") return "red";
  return "gray";
}

function priorityTone(priority) {
  if (priority === "high") return "red";
  if (priority === "medium") return "orange";
  return "gray";
}

function Pill({ children, variant = "gray", filled = false }) {
  return (
    <span
      style={{
        ...tone(variant, filled),
        display: "inline-flex",
        alignItems: "center",
        borderRadius: 999,
        border: "1px solid",
        padding: "2px 10px",
        fontSize: 11,
        fontWeight: 800,
        lineHeight: 1.3,
      }}
    >
      {children}
    </span>
  );
}

function sanitizeForDisplay(lead) {
  const status = String(lead.status || "new");
  const score = Number(lead.score || 0);
  const priority = String(lead.priority || (score >= 75 ? "high" : score >= 45 ? "medium" : "low"));
  const segment = String(lead.segment || "standard");
  const statusLabel = STATUS_LABEL[status] || status;
  const callsPerDay = lead.calls_per_day || lead.daily_call_volume || "unknown";
  return {
    ...lead,
    status,
    statusLabel: lead.status_label || statusLabel,
    score,
    priority,
    segment,
    callsPerDay,
    cabinet: lead.cabinet_name || lead.cabinet || "Cabinet sans nom",
    contact: lead.contact_name || lead.assistant_name || "Contact cabinet",
    role: lead.contact_role || "",
    profession: lead.profession || lead.medical_specialty_label || lead.medical_specialty || "Cabinet médical",
    city: lead.city || "",
    source: lead.source_detail || lead.source || "Inconnu",
    pain: lead.primary_pain_point || "Non renseigné",
    nextAction: lead.next_action || "À définir",
    nextActionAt: lead.follow_up_at || lead.last_interaction_at || lead.created_at || "—",
    hasAssistant:
      lead.assistant_name && String(lead.assistant_name).toLowerCase() !== "none"
        ? `Oui · ${lead.assistant_name}`
        : "Non",
    notes:
      typeof lead.notes === "string" && lead.notes.trim()
        ? [lead.notes.trim()]
        : Array.isArray(lead.notes)
          ? lead.notes
          : [],
  };
}

export default function AdminLeadsList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState(null);
  const [pipelineCounts, setPipelineCounts] = useState({});
  const [leads, setLeads] = useState([]);
  const [total, setTotal] = useState(0);
  const [selectedLeadId, setSelectedLeadId] = useState(searchParams.get("lead") || "");
  const [segment, setSegment] = useState(searchParams.get("segment") || "Tous");
  const [searchDraft, setSearchDraft] = useState(searchParams.get("search") || "");
  const [sort, setSort] = useState(searchParams.get("sort") || "created_desc");
  const [convertMode, setConvertMode] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [creatingLead, setCreatingLead] = useState(false);
  const [createError, setCreateError] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [importingCsv, setImportingCsv] = useState(false);
  const [importReport, setImportReport] = useState(null);
  const [deletingLeadId, setDeletingLeadId] = useState(null);
  const [isNarrow, setIsNarrow] = useState(() =>
    typeof window !== "undefined" ? window.innerWidth <= 820 : false,
  );
  const importInputRef = useRef(null);
  const [createForm, setCreateForm] = useState({
    cabinet_name: "",
    contact_name: "",
    email: "",
    phone: "",
    profession: "",
    city: "",
    calls_per_day: "unknown",
    pain_point: "",
    next_action: "",
    next_action_at: "",
    source: "manual",
    status: "new",
  });

  const stage = searchParams.get("status") || "all";
  const query = searchParams.get("search") || "";
  const page = Number(searchParams.get("page") || 1);
  const limit = Number(searchParams.get("limit") || 25);
  const followUpToday = searchParams.get("follow_up") === "today";
  const targetLeadId = searchParams.get("lead") || "";
  const totalPages = Math.max(1, Math.ceil(total / Math.max(1, limit)));

  useEffect(() => {
    setSearchDraft(query);
  }, [query]);

  useEffect(() => {
    if (searchDraft === query) return undefined;
    const timer = window.setTimeout(() => {
      setQuery({ search: searchDraft || null, page: 1 });
    }, 400);
    return () => window.clearTimeout(timer);
  }, [searchDraft, query]);

  useEffect(() => {
    function onResize() {
      setIsNarrow(window.innerWidth <= 820);
    }
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const [sumRes, listRes, targetLead] = await Promise.all([
          getLeadsSummary("30d").catch(() => null),
          listAdminLeads({
            status: stage,
            search: query,
            segment: segment === "Tous" ? undefined : segment.toLowerCase().replace(/\s+/g, "_"),
            sort,
            page,
            limit,
            followUpToday,
          }),
          targetLeadId ? adminApi.leadGet(targetLeadId).catch(() => null) : Promise.resolve(null),
        ]);
        if (cancelled) return;
        const mapped = (listRes.items || []).map(sanitizeForDisplay);
        if (targetLead && !mapped.some((item) => String(item.id) === String(targetLead.id))) {
          mapped.unshift(sanitizeForDisplay(targetLead));
        }
        setSummary(sumRes);
        setPipelineCounts(listRes.pipeline || {});
        setLeads(mapped);
        setTotal(listRes.total || 0);
        setSelectedLeadId((prev) => {
          if (targetLeadId && mapped.some((x) => String(x.id) === targetLeadId)) return targetLeadId;
          return prev && mapped.some((x) => String(x.id) === prev) ? prev : String(mapped[0]?.id || "");
        });
      } catch (e) {
        if (cancelled) return;
        setError(e?.message || "Impossible de charger les prospects");
        setLeads([]);
        setTotal(0);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [stage, query, segment, sort, page, limit, followUpToday, targetLeadId, refreshKey]);

  const selectedLead = useMemo(
    () => leads.find((l) => String(l.id) === String(selectedLeadId)) || leads[0] || null,
    [leads, selectedLeadId],
  );

  const displayedPipeline = useMemo(() => {
    const fallback = {
      all: leads.length,
      new: leads.filter((l) => l.status === "new").length,
      to_contact: leads.filter((l) => l.status === "new").length,
      contacted: leads.filter((l) => l.status === "contacted").length,
      demo: leads.filter((l) => l.status === "demo_scheduled").length,
      trial: leads.filter((l) => l.status === "trial_started" || l.status === "trial_offered").length,
      converted: leads.filter((l) => l.status === "converted").length,
      lost: leads.filter((l) => l.status === "lost").length,
    };
    return PIPELINE.map((p) => ({
      ...p,
      count:
        pipelineCounts[p.id] ??
        pipelineCounts[p.id === "demo" ? "demo_scheduled" : p.id === "trial" ? "trial_started" : p.id] ??
        fallback[p.id] ??
        0,
    }));
  }, [pipelineCounts, leads]);

  const stats = useMemo(() => {
    const avg = summary?.average_score ?? Math.round((leads.reduce((s, l) => s + Number(l.score || 0), 0) / Math.max(1, leads.length)));
    return {
      newCount: summary?.new_leads_count ?? displayedPipeline.find((x) => x.id === "new")?.count ?? 0,
      toContact: summary?.to_contact_count ?? displayedPipeline.find((x) => x.id === "to_contact")?.count ?? 0,
      demos: summary?.demo_scheduled_count ?? 0,
      trial: summary?.trial_leads_count ?? 0,
      high: summary?.high_priority_count ?? leads.filter((l) => l.priority === "high").length,
      avg,
    };
  }, [summary, leads, displayedPipeline]);

  async function quickStatusUpdate(lead, nextStatus) {
    try {
      await adminApi.leadSetStatus(lead.id, { status: nextStatus });
      setLeads((prev) => prev.map((x) => (String(x.id) === String(lead.id) ? sanitizeForDisplay({ ...x, status: nextStatus }) : x)));
      setRefreshKey((v) => v + 1);
    } catch (e) {
      setError(e?.message || "Erreur mise à jour statut");
    }
  }

  async function handleDeleteLead(lead) {
    const id = lead?.id;
    if (!id) return;
    const label = String(lead.cabinet || lead.contact || id || "").slice(0, 120);
    if (!window.confirm(`Supprimer définitivement ce prospect (« ${label} ») ? Cette action est irréversible.`)) return;
    setDeletingLeadId(id);
    setError("");
    try {
      await adminApi.leadDelete(id);
      if (String(selectedLeadId) === String(id)) setSelectedLeadId("");
      setRefreshKey((v) => v + 1);
    } catch (e) {
      setError(e?.message || "Échec de la suppression.");
    } finally {
      setDeletingLeadId(null);
    }
  }

  function normalizeDateTimeLocal(value) {
    const raw = String(value || "").trim();
    if (!raw) return "";
    if (raw.endsWith("Z") || raw.includes("+")) return raw;
    return `${raw}:00`;
  }

  async function handleCreateLead() {
    setCreateError("");
    if (!createForm.email.trim() && !createForm.phone.trim()) {
      setCreateError("Email ou téléphone requis.");
      return;
    }
    setCreatingLead(true);
    try {
      await adminApi.leadCreate({
        ...createForm,
        next_action_at: normalizeDateTimeLocal(createForm.next_action_at),
      });
      setShowCreateModal(false);
      setCreateForm({
        cabinet_name: "",
        contact_name: "",
        email: "",
        phone: "",
        profession: "",
        city: "",
        calls_per_day: "unknown",
        pain_point: "",
        next_action: "",
        next_action_at: "",
        source: "manual",
        status: "new",
      });
      setRefreshKey((v) => v + 1);
    } catch (e) {
      setCreateError(e?.message || "Impossible de créer le prospect");
    } finally {
      setCreatingLead(false);
    }
  }

  function setQuery(updates) {
    setSearchParams(applySearchParamsUpdates(searchParams, updates));
  }

  function normalizeLeadStatus(raw) {
    const value = String(raw || "").trim().toLowerCase();
    const aliases = {
      new: "new",
      nouveau: "new",
      to_contact: "to_contact",
      a_contacter: "to_contact",
      contacted: "contacted",
      contacte: "contacted",
      interested: "interested",
      interesse: "interested",
      demo: "demo_scheduled",
      demo_scheduled: "demo_scheduled",
      trial: "trial_started",
      trial_started: "trial_started",
      converted: "converted",
      converti: "converted",
      lost: "lost",
      perdu: "lost",
      later: "later",
      relance: "later",
    };
    return aliases[value] || "new";
  }

  function parseCsvLine(line, delimiter = ",") {
    const cells = [];
    let current = "";
    let inQuote = false;
    for (let i = 0; i < line.length; i += 1) {
      const ch = line[i];
      if (ch === "\"") {
        const next = line[i + 1];
        if (inQuote && next === "\"") {
          current += "\"";
          i += 1;
        } else {
          inQuote = !inQuote;
        }
      } else if (ch === delimiter && !inQuote) {
        cells.push(current.trim());
        current = "";
      } else {
        current += ch;
      }
    }
    cells.push(current.trim());
    return cells;
  }

  async function handleImportCsvFile(event) {
    const file = event?.target?.files?.[0];
    event.target.value = "";
    if (!file) return;
    setImportReport(null);
    setError("");
    setImportingCsv(true);
    try {
      const text = await file.text();
      const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
      if (lines.length < 2) throw new Error("CSV vide ou incomplet.");
      const commaCount = (lines[0].match(/,/g) || []).length;
      const semicolonCount = (lines[0].match(/;/g) || []).length;
      const delimiter = semicolonCount > commaCount ? ";" : ",";
      const headers = parseCsvLine(lines[0], delimiter).map((h) => h.toLowerCase().trim());
      const rows = lines.slice(1);
      let okCount = 0;
      let failCount = 0;
      const errors = [];
      for (let i = 0; i < rows.length; i += 1) {
        const cols = parseCsvLine(rows[i], delimiter);
        const row = {};
        headers.forEach((h, idx) => {
          row[h] = (cols[idx] || "").trim();
        });
        const payload = {
          cabinet_name: row.cabinet || row.cabinet_name || "",
          contact_name: row.contact || row.contact_name || "",
          email: row.email || "",
          phone: row.phone || row.telephone || "",
          profession: row.profession || row.specialty || "",
          city: row.city || row.ville || "",
          calls_per_day: row.calls_per_day || row.appels_jour || "unknown",
          pain_point: row.pain_point || row.douleur || "",
          next_action: row.next_action || "",
          next_action_at: normalizeDateTimeLocal(row.next_action_at || ""),
          source: row.source || "manual_import_csv",
          status: normalizeLeadStatus(row.status),
        };
        if (!payload.email && !payload.phone) {
          failCount += 1;
          errors.push(`Ligne ${i + 2}: email ou téléphone manquant`);
          continue;
        }
        try {
          await adminApi.leadCreate(payload);
          okCount += 1;
        } catch (err) {
          failCount += 1;
          errors.push(`Ligne ${i + 2}: ${err?.message || "échec import"}`);
        }
      }
      setImportReport({ okCount, failCount, errors: errors.slice(0, 5) });
      setRefreshKey((v) => v + 1);
    } catch (err) {
      setError(err?.message || "Import CSV impossible");
    } finally {
      setImportingCsv(false);
    }
  }

  function downloadCsvTemplate() {
    const header = [
      "cabinet",
      "contact",
      "email",
      "phone",
      "profession",
      "city",
      "calls_per_day",
      "status",
      "source",
      "pain_point",
      "next_action",
      "next_action_at",
    ].join(",");
    const row1 = [
      "Cabinet Demo Paris",
      "Dr Martin",
      "dr.martin@example.fr",
      "+33612345678",
      "Médecin généraliste",
      "Paris",
      "25-50",
      "new",
      "manual_import_csv",
      "Trop d'appels pendant les consultations",
      "Appel découverte",
      "2026-05-20T10:30",
    ].join(",");
    const row2 = [
      "Cabinet Smile",
      "Dr Haddad",
      "",
      "+33698765432",
      "Dentiste",
      "Lyon",
      "50-100",
      "demo",
      "manual_import_csv",
      "Besoin de filtrer les urgences",
      "Préparer démo",
      "",
    ].join(",");
    const csv = `${header}\n${row1}\n${row2}\n`;
    const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "modele-import-leads.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  return (
    <div style={{ minHeight: "100vh", background: BRAND.bg, color: BRAND.ink, fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif" }}>
      <div style={{ maxWidth: 1400, margin: "0 auto", padding: "18px 16px 24px" }}>
        <header style={{ marginBottom: 16, display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-start", justifyContent: "space-between" }}>
          <div>
            <div style={{ marginBottom: 6, display: "inline-flex", alignItems: "center", gap: 6, border: "1px solid #BFE9EC", borderRadius: 999, padding: "4px 10px", fontSize: 11, fontWeight: 800, color: BRAND.tealDark, background: "#fff" }}>
              ✦ Admin · Prospects
            </div>
            <h1 style={{ margin: 0, fontSize: 34, lineHeight: 1.1, fontWeight: 900, color: BRAND.navy, letterSpacing: "-0.04em" }}>
              Pipeline commercial
            </h1>
            <p style={{ margin: "6px 0 0", fontSize: 14, fontWeight: 600, color: BRAND.muted }}>
              Suivi des cabinets intéressés par UWi, de la prise de contact jusqu’à la conversion en client.
            </p>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            <input
              ref={importInputRef}
              type="file"
              accept=".csv,text/csv"
              onChange={handleImportCsvFile}
              style={{ display: "none" }}
            />
            <button
              onClick={() => importInputRef.current?.click()}
              disabled={importingCsv}
              style={{ borderRadius: 14, border: `1px solid ${BRAND.border}`, background: "#fff", padding: "10px 14px", fontWeight: 800, cursor: importingCsv ? "default" : "pointer", opacity: importingCsv ? 0.7 : 1 }}
            >
              {importingCsv ? "Import..." : "Importer CSV"}
            </button>
            <button
              onClick={downloadCsvTemplate}
              style={{ borderRadius: 14, border: `1px solid ${BRAND.border}`, background: "#fff", padding: "10px 14px", fontWeight: 800, cursor: "pointer" }}
            >
              Télécharger modèle CSV
            </button>
            <button
              onClick={() => setQuery({ follow_up: followUpToday ? null : "today", page: 1 })}
              style={{
                borderRadius: 14,
                border: `1px solid ${followUpToday ? BRAND.teal : BRAND.border}`,
                background: followUpToday ? BRAND.softTeal : "#fff",
                color: followUpToday ? BRAND.tealDark : BRAND.ink,
                padding: "10px 14px",
                fontWeight: 800,
                cursor: "pointer",
              }}
            >
              Relances du jour
            </button>
            <button
              onClick={() => setShowCreateModal(true)}
              style={{ borderRadius: 14, border: "none", background: BRAND.teal, color: "#fff", padding: "10px 16px", fontWeight: 900, cursor: "pointer" }}
            >
              + Ajouter un prospect
            </button>
          </div>
        </header>

        <section style={{ marginBottom: 12, borderRadius: 22, border: `1px solid ${BRAND.border}`, background: "#fff", padding: 12 }}>
          <div style={{ marginBottom: 10, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
            <div>
              <div style={{ fontWeight: 900, fontSize: 18, color: BRAND.navy }}>Pipeline</div>
              <div style={{ fontSize: 12, fontWeight: 700, color: BRAND.muted }}>Prospect → qualification → essai → client</div>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
              <Pill variant="teal">{total} résultat(s)</Pill>
              <Pill variant="gray">Score moyen {stats.avg}</Pill>
              {stats.high > 0 ? <Pill variant="red">{stats.high} priorité haute</Pill> : null}
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 8 }}>
            {displayedPipeline.map((item) => {
              const active = stage === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setQuery({ status: item.id === "all" ? null : item.id, page: 1 })}
                  style={{
                    borderRadius: 14,
                    border: `1px solid ${active ? BRAND.navy : BRAND.border}`,
                    padding: "10px 10px",
                    textAlign: "left",
                    background: active ? BRAND.navy : "#FBFDFD",
                    color: active ? "#fff" : BRAND.ink,
                    cursor: "pointer",
                  }}
                >
                  <div style={{ fontSize: 11, fontWeight: 800, opacity: 0.8 }}>{item.label}</div>
                  <div style={{ marginTop: 3, fontSize: 24, fontWeight: 900, letterSpacing: "-0.04em" }}>{item.count}</div>
                </button>
              );
            })}
          </div>
        </section>

        <section style={{ marginBottom: 12, borderRadius: 22, border: `1px solid ${BRAND.border}`, background: "#fff", padding: 12 }}>
          <div style={{ display: "grid", gap: 8, gridTemplateColumns: isNarrow ? "1fr" : "minmax(220px,1fr) minmax(220px,1fr) minmax(170px,200px)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, border: `1px solid ${BRAND.border}`, background: "#F8FBFC", borderRadius: 14, padding: "10px 12px" }}>
              <span style={{ color: "#98A2B3" }}>⌕</span>
              <input
                value={searchDraft}
                onChange={(e) => setSearchDraft(e.target.value)}
                placeholder="Rechercher cabinet, praticien, ville, douleur, source..."
                style={{ width: "100%", border: "none", outline: "none", background: "transparent", fontWeight: 700, color: BRAND.navy, fontSize: 13 }}
              />
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {["Tous", "grand_account", "high", "solo_practitioner", "without_assistant"].map((s) => (
                <button
                  key={s}
                  onClick={() => {
                    setSegment(s);
                    setQuery({ segment: s === "Tous" ? null : s, page: 1 });
                  }}
                  style={{
                    borderRadius: 12,
                    padding: "8px 10px",
                    border: "1px solid transparent",
                    background: segment === s ? BRAND.navy : "#F2F4F7",
                    color: segment === s ? "#fff" : BRAND.muted,
                    fontWeight: 800,
                    fontSize: 11,
                    cursor: "pointer",
                  }}
                >
                  {segmentLabel(s)}
                </button>
              ))}
            </div>
            <select
              value={sort}
              onChange={(e) => {
                const nextSort = e.target.value;
                setSort(nextSort);
                setQuery({ sort: nextSort, page: 1 });
              }}
              style={{ borderRadius: 12, border: `1px solid ${BRAND.border}`, background: "#fff", padding: "9px 10px", fontWeight: 800, color: BRAND.navy }}
            >
              <option value="score_desc">Score le plus élevé</option>
              <option value="next_action_asc">Prochaine action</option>
              <option value="calls_desc">Volume appels</option>
              <option value="created_desc">Créés récemment</option>
              <option value="name_asc">Nom A-Z</option>
            </select>
          </div>
          {(stage !== "all" || segment !== "Tous" || query || followUpToday) ? (
            <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", position: "sticky", top: 4, zIndex: 2, background: "#fff", paddingTop: 2 }}>
              {stage !== "all" ? <Pill variant="teal">Statut: {stage.replace(/_/g, " ")}</Pill> : null}
              {segment !== "Tous" ? <Pill variant="purple">Segment: {segmentLabel(segment)}</Pill> : null}
              {query ? <Pill variant="blue">Recherche: {query}</Pill> : null}
              {followUpToday ? <Pill variant="orange">Relances du jour</Pill> : null}
              <button
                onClick={() => {
                  setSegment("Tous");
                  setSort("created_desc");
                  setSearchDraft("");
                  setQuery({ status: null, search: null, segment: null, sort: "created_desc", follow_up: null, page: 1 });
                }}
                style={{ marginLeft: "auto", borderRadius: 999, border: `1px solid ${BRAND.border}`, background: "#fff", padding: "5px 10px", fontWeight: 800, fontSize: 11, cursor: "pointer" }}
              >
                Réinitialiser les filtres
              </button>
            </div>
          ) : null}
        </section>

        {error ? (
          <div style={{ marginBottom: 12, borderRadius: 14, border: `1px solid ${BRAND.red}66`, background: "#FEECEC", color: BRAND.red, padding: "10px 12px", fontWeight: 700 }}>
            {error}
          </div>
        ) : null}
        {importReport ? (
          <div style={{ marginBottom: 12, borderRadius: 14, border: `1px solid ${importReport.failCount ? BRAND.orange : BRAND.green}66`, background: importReport.failCount ? "#FFF4E5" : "#EAF8F0", color: BRAND.navy, padding: "10px 12px", fontWeight: 700 }}>
            Import CSV terminé : {importReport.okCount} créé(s), {importReport.failCount} en erreur.
            {importReport.errors?.length ? ` ${importReport.errors.join(" · ")}` : ""}
          </div>
        ) : null}
        <details style={{ marginBottom: 12, borderRadius: 12, border: `1px solid ${BRAND.border}`, background: "#fff", padding: "8px 10px", color: BRAND.muted, fontSize: 11, fontWeight: 700 }}>
          <summary style={{ cursor: "pointer", color: BRAND.navy }}>Format attendu pour l’import CSV</summary>
          <div style={{ marginTop: 8, lineHeight: 1.5 }}>
            Colonnes : `cabinet,contact,email,phone,profession,city,calls_per_day,status,source,pain_point,next_action,next_action_at`.
          </div>
        </details>

        {loading ? (
          <div style={{ padding: 22, color: BRAND.muted, fontWeight: 700 }}>Chargement des prospects…</div>
        ) : (
          <div style={{ display: "grid", gap: 16, alignItems: "start", gridTemplateColumns: isNarrow ? "minmax(0, 1fr)" : "minmax(0, 1fr) 430px" }}>
            <section style={{ display: "grid", gap: 7 }}>
              {leads.map((lead) => (
                <LeadCard
                  key={lead.id}
                  lead={lead}
                  selected={String(selectedLeadId) === String(lead.id)}
                  isNarrow={isNarrow}
                  onSelect={() => {
                    setSelectedLeadId(String(lead.id));
                    const next = new URLSearchParams(searchParams);
                    next.set("lead", String(lead.id));
                    setSearchParams(next, { replace: true });
                    setConvertMode(false);
                  }}
                />
              ))}
              {leads.length === 0 ? (
                <div style={{ borderRadius: 18, border: `1px dashed #BFD3DA`, background: "#fff", padding: 24, textAlign: "center", color: BRAND.muted, fontWeight: 700 }}>
                  Aucun prospect trouvé.
                </div>
              ) : null}
            </section>

            <div style={{ order: isNarrow ? -1 : 0 }}>
              {selectedLead ? (
                <DetailPanel
                  lead={selectedLead}
                  convertMode={convertMode}
                  setConvertMode={setConvertMode}
                  onStatusChange={quickStatusUpdate}
                  onDelete={handleDeleteLead}
                  deletingLeadId={deletingLeadId}
                  isNarrow={isNarrow}
                />
              ) : (
                <aside style={{ position: isNarrow ? "relative" : "sticky", top: 12, borderRadius: 20, border: `1px solid ${BRAND.border}`, background: "#fff", padding: 16 }}>
                  <div style={{ color: BRAND.muted, fontWeight: 700 }}>Sélectionnez un prospect.</div>
                </aside>
              )}
            </div>
          </div>
        )}
        {!loading && total > 0 ? (
          <nav
            aria-label="Pagination des prospects"
            style={{
              marginTop: 14,
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 10,
              borderRadius: 16,
              border: `1px solid ${BRAND.border}`,
              background: "#fff",
              padding: "10px 12px",
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 800, color: BRAND.muted }}>
              Page {page} sur {totalPages} · {total} prospect{total > 1 ? "s" : ""}
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setQuery({ page: Math.max(1, page - 1), lead: null })}
                style={{ ...paginationButtonStyle, opacity: page <= 1 ? 0.45 : 1 }}
              >
                Précédent
              </button>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setQuery({ page: Math.min(totalPages, page + 1), lead: null })}
                style={{ ...paginationButtonStyle, opacity: page >= totalPages ? 0.45 : 1 }}
              >
                Suivant
              </button>
            </div>
          </nav>
        ) : null}
      </div>
      {showCreateModal ? (
        <div
          onClick={() => setShowCreateModal(false)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(7,26,51,0.45)",
            zIndex: 70,
            display: "grid",
            placeItems: "center",
            padding: isNarrow ? 8 : 14,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: "100%",
              maxWidth: 660,
              maxHeight: isNarrow ? "92vh" : "86vh",
              overflowY: "auto",
              borderRadius: isNarrow ? 16 : 20,
              border: `1px solid ${BRAND.border}`,
              background: "#fff",
              padding: isNarrow ? 10 : 14,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 10 }}>
              <div style={{ fontSize: 20, fontWeight: 900, color: BRAND.navy }}>Nouveau prospect</div>
              <button onClick={() => setShowCreateModal(false)} style={{ border: "none", background: "transparent", fontSize: 22, cursor: "pointer", color: BRAND.muted }}>×</button>
            </div>
            <div style={{ display: "grid", gap: 8, gridTemplateColumns: isNarrow ? "1fr" : "1fr 1fr" }}>
              <input value={createForm.cabinet_name} onChange={(e) => setCreateForm((p) => ({ ...p, cabinet_name: e.target.value }))} placeholder="Nom du cabinet" style={inputStyle} />
              <input value={createForm.contact_name} onChange={(e) => setCreateForm((p) => ({ ...p, contact_name: e.target.value }))} placeholder="Nom du contact" style={inputStyle} />
              <input value={createForm.email} onChange={(e) => setCreateForm((p) => ({ ...p, email: e.target.value }))} placeholder="Email" style={inputStyle} />
              <input value={createForm.phone} onChange={(e) => setCreateForm((p) => ({ ...p, phone: e.target.value }))} placeholder="Téléphone" style={inputStyle} />
              <input value={createForm.profession} onChange={(e) => setCreateForm((p) => ({ ...p, profession: e.target.value }))} placeholder="Profession" style={inputStyle} />
              <input value={createForm.city} onChange={(e) => setCreateForm((p) => ({ ...p, city: e.target.value }))} placeholder="Ville" style={inputStyle} />
              <select value={createForm.calls_per_day} onChange={(e) => setCreateForm((p) => ({ ...p, calls_per_day: e.target.value }))} style={inputStyle}>
                <option value="unknown">Volume appels</option>
                <option value="<10">&lt;10</option>
                <option value="10-25">10-25</option>
                <option value="25-50">25-50</option>
                <option value="50-100">50-100</option>
                <option value="100+">100+</option>
              </select>
              <select value={createForm.status} onChange={(e) => setCreateForm((p) => ({ ...p, status: e.target.value }))} style={inputStyle}>
                <option value="new">Nouveau</option>
                <option value="interested">Intéressé</option>
                <option value="demo_scheduled">Démo prévue</option>
                <option value="trial_started">Essai gratuit</option>
                <option value="later">À relancer plus tard</option>
              </select>
              <input value={createForm.next_action} onChange={(e) => setCreateForm((p) => ({ ...p, next_action: e.target.value }))} placeholder="Prochaine action" style={inputStyle} />
              <input type="datetime-local" value={createForm.next_action_at} onChange={(e) => setCreateForm((p) => ({ ...p, next_action_at: e.target.value }))} style={inputStyle} />
              <textarea value={createForm.pain_point} onChange={(e) => setCreateForm((p) => ({ ...p, pain_point: e.target.value }))} placeholder="Douleur / contexte" style={{ ...inputStyle, gridColumn: "1 / -1", minHeight: 84, resize: "vertical" }} />
            </div>
            {createError ? <div style={{ marginTop: 10, color: BRAND.red, fontWeight: 700, fontSize: 13 }}>{createError}</div> : null}
            <div
              style={{
                marginTop: 12,
                display: "flex",
                justifyContent: "flex-end",
                gap: 8,
                position: "sticky",
                bottom: 0,
                background: "#fff",
                paddingTop: 8,
              }}
            >
              <button onClick={() => setShowCreateModal(false)} style={{ borderRadius: 12, border: `1px solid ${BRAND.border}`, background: "#fff", padding: "9px 12px", fontWeight: 800, cursor: "pointer" }}>Annuler</button>
              <button onClick={handleCreateLead} disabled={creatingLead} style={{ borderRadius: 12, border: "none", background: BRAND.teal, color: "#fff", padding: "9px 12px", fontWeight: 900, cursor: creatingLead ? "default" : "pointer", opacity: creatingLead ? 0.65 : 1 }}>
                {creatingLead ? "Création..." : "Créer le prospect"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function LeadCard({ lead, selected, isNarrow, onSelect }) {
  const priorityLabel = lead.priority === "high" ? "Haute" : lead.priority === "medium" ? "Moyenne" : "Basse";
  const contextLabel = lead.nextAction && lead.nextAction !== "À définir" ? lead.nextAction : lead.source;
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
      style={{
        position: "relative",
        width: "100%",
        minWidth: 0,
        overflow: "hidden",
        display: "grid",
        gridTemplateColumns: isNarrow ? "minmax(0, 1fr) auto" : "minmax(190px, 1.4fr) minmax(170px, 1fr) auto",
        gridTemplateAreas: isNarrow ? '"identity score" "meta meta"' : '"identity meta score"',
        alignItems: "center",
        gap: isNarrow ? 8 : 12,
        borderRadius: 14,
        border: `${selected ? 2 : 1}px solid ${selected ? BRAND.teal : BRAND.border}`,
        borderLeft: `${selected ? 6 : 1}px solid ${selected ? BRAND.teal : BRAND.border}`,
        background: selected ? "#ECFAFA" : "#fff",
        padding: selected ? "10px 12px 10px 10px" : "11px 13px",
        textAlign: "left",
        cursor: "pointer",
        boxShadow: selected ? "0 5px 16px rgba(0,156,164,0.12)" : "0 1px 3px rgba(10,22,40,0.04)",
        fontFamily: "inherit",
      }}
    >
      <div style={{ minWidth: 0, gridArea: "identity" }}>
        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 14, lineHeight: 1.2, fontWeight: 900, color: BRAND.navy }}>
            {lead.cabinet}
          </span>
          {selected ? <Pill variant="teal" filled>SÉLECTIONNÉ</Pill> : null}
        </div>
        <div style={{ marginTop: 3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 11, fontWeight: 700, color: BRAND.muted }}>
          {lead.contact} · {lead.profession}
        </div>
      </div>

      <div style={{ minWidth: 0, gridArea: "meta", display: "grid", gap: 5 }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
          {!isNarrow ? <Pill variant={statusTone(lead.status)}>{lead.statusLabel}</Pill> : null}
          <Pill variant={priorityTone(lead.priority)}>Priorité {priorityLabel.toLowerCase()}</Pill>
        </div>
        <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 11, fontWeight: 700, color: BRAND.muted }}>
          {lead.nextAction && lead.nextAction !== "À définir" ? "À faire" : "Source"} · <span style={{ color: BRAND.navy }}>{contextLabel}</span>
        </div>
      </div>

      <div style={{ gridArea: "score", display: "flex", alignItems: "center", gap: 8 }}>
        {isNarrow ? <Pill variant={statusTone(lead.status)}>{lead.statusLabel}</Pill> : null}
        <div style={{ minWidth: 38, textAlign: "right" }}>
          <div style={{ fontSize: 9, fontWeight: 800, color: "#98A2B3", textTransform: "uppercase" }}>Score</div>
          <div style={{ fontSize: 19, lineHeight: 1, fontWeight: 900, color: BRAND.navy }}>{lead.score}</div>
        </div>
        <span aria-hidden="true" style={{ color: selected ? BRAND.tealDark : "#98A2B3", fontSize: 18, fontWeight: 900 }}>›</span>
      </div>
    </button>
  );
}

function DetailPanel({ lead, convertMode, setConvertMode, onStatusChange, onDelete, deletingLeadId, isNarrow = false }) {
  const plan = lead.callsPerDay === "100+" ? "Growth" : lead.callsPerDay === "50-100" ? "Starter" : "Essai gratuit";
  const transitions = {
    new: ["contacted", "interested", "later", "lost"],
    contacted: ["interested", "demo_scheduled", "later", "lost"],
    interested: ["demo_scheduled", "trial_offered", "later", "lost"],
    demo_scheduled: ["trial_started", "converted", "lost"],
    trial_offered: ["trial_started", "converted", "lost"],
    trial_started: ["converted", "later", "lost"],
    later: ["contacted", "interested", "demo_scheduled", "lost"],
  };
  const nextStatuses = transitions[lead.status] || [];
  const statusLabel = {
    new: "Nouveau",
    contacted: "Contacté",
    interested: "Intéressé",
    demo_scheduled: "Démo prévue",
    trial_offered: "Essai proposé",
    trial_started: "Essai gratuit",
    converted: "Converti",
    lost: "Perdu",
    later: "À relancer plus tard",
  };
  return (
    <aside style={{ position: isNarrow ? "relative" : "sticky", top: 12, alignSelf: "start" }}>
      <section style={{ overflow: "hidden", borderRadius: isNarrow ? 18 : 22, border: `1px solid ${BRAND.border}`, background: "#fff", boxShadow: "0 8px 24px rgba(7,26,51,0.08)" }}>
        <div style={{ borderBottom: `1px solid ${BRAND.border}`, padding: isNarrow ? 14 : 18 }}>
          <div style={{ marginBottom: 10, fontSize: 10, fontWeight: 900, letterSpacing: "0.12em", color: BRAND.tealDark }}>
            PROSPECT SÉLECTIONNÉ
          </div>
          <div style={{ fontSize: isNarrow ? 22 : 26, lineHeight: 1.1, fontWeight: 900, letterSpacing: "-0.035em", color: BRAND.navy }}>{lead.cabinet}</div>
          <div style={{ marginTop: 4, fontSize: 13, fontWeight: 700, color: BRAND.muted }}>
            {lead.contact} · {lead.profession}{lead.role ? ` · ${lead.role}` : ""}
          </div>
          <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", gap: 6 }}>
            <Pill variant={statusTone(lead.status)}>{lead.statusLabel}</Pill>
            <Pill variant={priorityTone(lead.priority)}>
              {lead.priority === "high" ? "Priorité haute" : lead.priority === "medium" ? "Priorité moyenne" : "Priorité basse"}
            </Pill>
            <Pill variant="gray">Score {lead.score}</Pill>
          </div>
        </div>

        <div style={{ padding: isNarrow ? 14 : 18 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 6 }}>
            <button onClick={() => onStatusChange(lead, "contacted")} style={actionButton}>☎<span>Appeler</span></button>
            <a href={`mailto:${lead.email || ""}`} style={{ ...actionButton, textDecoration: "none" }}>✉<span>Email</span></a>
            <button onClick={() => onStatusChange(lead, "later")} style={actionButton}>↻<span>Relance</span></button>
            <button onClick={() => onStatusChange(lead, "demo_scheduled")} style={actionButton}>▶<span>Démo</span></button>
          </div>

          <Link
            to={`/admin/tenants/new?fromLead=${encodeURIComponent(lead.id)}`}
            onClick={() => setConvertMode(true)}
            style={{ marginTop: 10, display: "flex", alignItems: "center", justifyContent: "space-between", borderRadius: 14, background: BRAND.teal, color: "#fff", textDecoration: "none", padding: "13px 15px", fontSize: 14, fontWeight: 900, boxShadow: "0 6px 16px rgba(0,156,164,0.2)" }}
          >
            <span>Convertir en client</span>
            <span style={{ fontSize: 20 }}>→</span>
          </Link>

          <div style={{ marginTop: 14, display: "grid", gap: 8, gridTemplateColumns: isNarrow ? "1fr" : "1fr 1fr" }}>
            <Info label="Téléphone" value={lead.callback_phone || lead.phone || "—"} />
            <Info label="Email" value={lead.email || "—"} />
            <Info label="Ville" value={lead.city || "—"} />
            <Info label="Prochaine action" value={lead.nextAction || "À définir"} />
          </div>
          <div style={detailTextBlock}>
            <div style={detailTitle}>Besoin principal</div>
            <p style={detailBody}>{lead.pain}</p>
          </div>

          <details style={detailsStyle}>
            <summary style={summaryStyle}>Changer le statut</summary>
            <div style={{ paddingTop: 10, display: "flex", flexWrap: "wrap", gap: 6 }}>
              {nextStatuses.length ? nextStatuses.map((status) => (
                <button key={status} type="button" onClick={() => onStatusChange(lead, status)} style={statusButton}>
                  {statusLabel[status] || status}
                </button>
              )) : <span style={mutedDetailText}>Aucune transition disponible.</span>}
            </div>
          </details>

          <details style={detailsStyle}>
            <summary style={summaryStyle}>Informations secondaires</summary>
            <div style={{ paddingTop: 10, display: "grid", gap: 8, gridTemplateColumns: "1fr 1fr" }}>
              <Info label="Source" value={lead.source} />
              <Info label="Segment" value={segmentLabel(lead.segment)} />
              <Info label="Appels / jour" value={lead.callsPerDay} />
              <Info label="Secrétariat" value={lead.hasAssistant} />
            </div>
            <div style={detailTextBlock}>
              <div style={detailTitle}>Point de vigilance</div>
              <p style={detailBody}>{lead.objection || "À qualifier lors du prochain échange."}</p>
            </div>
          </details>

          <details style={detailsStyle}>
            <summary style={summaryStyle}>Préparation du cabinet</summary>
            <div style={{ paddingTop: 10 }}>
              <div style={mutedDetailText}>
                Plan suggéré : <strong style={{ color: BRAND.navy }}>{plan}</strong>. Les coordonnées seront préremplies lors de la conversion.
              </div>
              {convertMode ? (
                <div style={{ marginTop: 8, borderRadius: 10, background: BRAND.softTeal, padding: 10, fontSize: 12, fontWeight: 800, color: BRAND.tealDark }}>
                  Préparation de la conversion activée.
                </div>
              ) : null}
            </div>
          </details>

          <details style={{ ...detailsStyle, borderColor: `${BRAND.red}44` }}>
            <summary style={{ ...summaryStyle, color: BRAND.red }}>Suppression irréversible</summary>
            <div style={{ paddingTop: 10 }}>
              <p style={{ ...mutedDetailText, margin: "0 0 10px" }}>Supprime définitivement ce prospect.</p>
              <button
                type="button"
                disabled={deletingLeadId === lead.id}
                onClick={() => onDelete?.(lead)}
                style={{ width: "100%", borderRadius: 12, border: `1px solid ${BRAND.red}`, background: "#fff", color: BRAND.red, padding: "9px 12px", fontWeight: 900, cursor: deletingLeadId === lead.id ? "wait" : "pointer", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8 }}
              >
                <Trash2 size={16} strokeWidth={2} />
                {deletingLeadId === lead.id ? "Suppression…" : "Supprimer définitivement"}
              </button>
            </div>
          </details>
        </div>
      </section>
    </aside>
  );
}

const actionButton = {
  minWidth: 0,
  minHeight: 58,
  borderRadius: 12,
  border: `1px solid ${BRAND.border}`,
  background: "#F8FBFC",
  color: BRAND.navy,
  textDecoration: "none",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  gap: 3,
  fontWeight: 900,
  fontSize: 11,
  padding: "7px 4px",
  cursor: "pointer",
};

const detailsStyle = {
  marginTop: 10,
  borderRadius: 12,
  border: `1px solid ${BRAND.border}`,
  background: "#fff",
  padding: "10px 11px",
};

const summaryStyle = {
  cursor: "pointer",
  color: BRAND.navy,
  fontSize: 12,
  fontWeight: 900,
};

const statusButton = {
  borderRadius: 999,
  border: `1px solid ${BRAND.border}`,
  background: "#F8FBFC",
  padding: "5px 9px",
  fontSize: 11,
  fontWeight: 800,
  color: BRAND.navy,
  cursor: "pointer",
};

const mutedDetailText = {
  fontSize: 12,
  lineHeight: 1.45,
  fontWeight: 700,
  color: BRAND.muted,
};

const inputStyle = {
  borderRadius: 12,
  border: `1px solid ${BRAND.border}`,
  background: "#fff",
  padding: "10px 11px",
  fontWeight: 700,
  color: BRAND.navy,
  outline: "none",
};

const paginationButtonStyle = {
  borderRadius: 10,
  border: `1px solid ${BRAND.border}`,
  background: "#fff",
  color: BRAND.navy,
  padding: "8px 12px",
  fontWeight: 800,
  cursor: "pointer",
};

function Info({ label, value }) {
  return (
    <div style={{ borderRadius: 10, border: "1px solid #E4ECEF", background: "#FBFDFD", padding: 10 }}>
      <div style={{ fontSize: 9, fontWeight: 800, color: "#98A2B3", textTransform: "uppercase" }}>{label}</div>
      <div style={{ marginTop: 3, fontSize: 12, fontWeight: 900, color: BRAND.navy }}>{value}</div>
    </div>
  );
}

const detailTextBlock = {
  marginTop: 8,
  borderRadius: 12,
  border: "1px solid #E4ECEF",
  background: "#FBFDFD",
  padding: 10,
};
const detailTitle = {
  fontSize: 10,
  fontWeight: 800,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  color: "#98A2B3",
};
const detailBody = {
  margin: "6px 0 0",
  fontSize: 13,
  lineHeight: 1.5,
  fontWeight: 700,
  color: BRAND.navy,
};
