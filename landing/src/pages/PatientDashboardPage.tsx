import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useOutletContext, useSearchParams } from "react-router-dom";
import { agendaSlotMotif, formatAgendaSlotHour, parseAgendaSlotStart } from "../lib/agendaSlotParse.js";
import { api } from "../lib/api.js";
import { normalizePhoneBusinessKey } from "../lib/phoneNormalize";
import { patientDashboardFileHasValidatedIdentity } from "../lib/callsService.js";

/** Clé téléphone métier (= backend `normalize_phone_number`). */
function normalizePhone(value: string) {
  return normalizePhoneBusinessKey(value);
}

/** Pour rapprocher le libellé « patient » d’un créneau Google avec la fiche. */
function normalizeAgendaPatientName(value: string) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ");
}

function formatCabinetMetaDate(value: unknown) {
  const raw = String(value || "").trim();
  if (!raw) return "—";
  const d = new Date(raw.includes("T") ? raw.replace(" ", "T") : raw);
  return Number.isNaN(d.getTime()) ? raw.slice(0, 10) || "—" : d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

type SidebarPatientRow = {
  /** Téléphone normalisé comme clé (aligné tenant API). */
  phone: string;
  displayPhone: string;
  name: string;
  initials: string;
  dateLabel: string;
  gradient: string;
  hasValidated: boolean;
  statusBucket: "new" | "active" | "inactive";
};

type ModalType = "profile" | "addNote" | "addDocument" | "history" | "deletePatient" | null;
type ViewType = "overview" | "appointments" | "history";
type RequestContext = {
  id: string;
  phone: string;
  patientName: string;
  summary: string;
  type: string;
  status: string;
  source: string;
  createdAtLabel: string;
};

type PatientNote = {
  id: number;
  text: string;
  author: string;
  created_at: string;
};

type PatientDocument = {
  id: number;
  original_name: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
};

const SIDEBAR_GRADIENTS = [
  "from-[#008EA1] to-[#004866]",
  "from-[#00A686] to-[#007C73]",
  "from-[#7256F4] to-[#5338C9]",
  "from-[#0BA37F] to-[#007B64]",
  "from-[#FF9A2E] to-[#F36F21]",
  "from-[#009CA4] to-[#006E78]",
  "from-[#8068E8] to-[#5942C9]",
];

function sidebarGradient(seed: string) {
  if (!seed) return SIDEBAR_GRADIENTS[0];
  let h = 0;
  for (let i = 0; i < seed.length; i += 1) h = (h + seed.charCodeAt(i)) | 0;
  return SIDEBAR_GRADIENTS[Math.abs(h) % SIDEBAR_GRADIENTS.length];
}

function cabinetRowTimeLabel(value: string) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return "";
  const diff = Date.now() - date.getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "Aujourd'hui";
  if (days === 1) return "Hier";
  if (days < 7) return `Il y a ${days} j`;
  return date.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function deriveCabinetRowBucket(row: Record<string, unknown>): "new" | "active" | "inactive" {
  const now = Date.now();
  const updatedAt = new Date(String(row.updated_at || 0)).getTime();
  const createdAt = new Date(String(row.created_at || 0)).getTime();
  const daysSinceUpdate = Number.isFinite(updatedAt) ? (now - updatedAt) / 86400000 : 0;
  const daysSinceCreation = Number.isFinite(createdAt) ? (now - createdAt) / 86400000 : 999;
  if (daysSinceCreation < 14 && !patientDashboardFileHasValidatedIdentity(row)) return "new";
  if (daysSinceUpdate > 60 && Number.isFinite(updatedAt)) return "inactive";
  return "active";
}

function formatDisplayFrenchPhone(raw: string): string {
  const trimmed = String(raw || "").trim();
  if (!trimmed) return "—";
  if (trimmed.startsWith("+33") && trimmed.length === 12) {
    return `0${trimmed.slice(3, 4)} ${trimmed.slice(4, 6)} ${trimmed.slice(6, 8)} ${trimmed.slice(8, 10)} ${trimmed.slice(10)}`;
  }
  return trimmed;
}

function cabinetRowToSidebar(row: Record<string, unknown>): SidebarPatientRow | null {
  const phone = normalizePhone(String(row.phone || ""));
  if (!phone) return null;
  const displayName =
    String(row.display_name || row.validated_name || row.raw_name || "").trim() || "Patient";
  const updatedIso = String(row.updated_at || row.created_at || "");
  return {
    phone,
    displayPhone: formatDisplayFrenchPhone(phone.startsWith("+") ? phone : phone),
    name: displayName,
    initials: initialsFromFullName(displayName),
    dateLabel: cabinetRowTimeLabel(updatedIso),
    gradient: sidebarGradient(phone),
    hasValidated: patientDashboardFileHasValidatedIdentity(row),
    statusBucket: deriveCabinetRowBucket(row),
  };
}

function initialsFromFullName(name: string) {
  const parts = String(name || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  const a = parts[0][0];
  const b = parts[parts.length - 1][0];
  return `${a}${b}`.toUpperCase();
}

const viewTabs: Array<{ id: ViewType; label: string; icon: string }> = [
  { id: "overview", label: "Vue d'ensemble", icon: "▤" },
  { id: "appointments", label: "Rendez-vous", icon: "▣" },
  { id: "history", label: "Historique", icon: "◷" },
];

const REQUEST_STATUS_OVERRIDES_KEY = "uwi_request_status_overrides";

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

/** Si le patient ouvert (?phone=) n’est pas dans les résultats API, on injecte une ligne pour le garder cliquable. */
function injectSelectedPatientRow(
  rows: SidebarPatientRow[],
  phoneKey: string,
  hero: { name: string; phone: string; initials: string } | null,
): SidebarPatientRow[] {
  const key = phoneKey ? normalizePhone(phoneKey) : "";
  if (!key || !hero) return rows;
  if (rows.some((r) => r.phone === key)) return rows;
  const canonical = normalizePhone(hero.phone) || key;
  return [
    {
      phone: canonical,
      displayPhone: formatDisplayFrenchPhone(canonical),
      name: hero.name,
      initials: hero.initials,
      dateLabel: "—",
      gradient: sidebarGradient(canonical),
      hasValidated: true,
      statusBucket: "active",
    },
    ...rows,
  ];
}

function frenchAppointmentDateParts(d: Date): { day: string; monthYear: string; dow: string } {
  return {
    day: String(d.getDate()),
    monthYear: d.toLocaleDateString("fr-FR", { month: "long", year: "numeric" }),
    dow: `${d.toLocaleDateString("fr-FR", { weekday: "short" }).replace(".", "").toUpperCase()}.`,
  };
}

function agendaPatientSourceLabel(slot: Record<string, unknown>): string {
  const src = String(slot.source || "").toUpperCase();
  if (src === "UWI") return "Pris par Clara (UWi)";
  if (src === "PAGE_PUBLIQUE") return "Page publique";
  if (src === "EXTERNAL") return "Agenda cabinet";
  return src ? src : "—";
}

/** Libellé de statut pour liste / vignette RDV patient */
function patientAgendaRowStatus(slot: Record<string, unknown>, start: Date): string {
  const joined = `${slot.booking_status || ""} ${slot.status || ""}`.toLowerCase();
  if (joined.includes("cancel") || joined.includes("annul")) return "Annulé";
  if (start.getTime() >= Date.now()) {
    if (joined.includes("pending")) return "À confirmer";
    if (joined.includes("confirm")) return "Confirmé";
    return "Prévu";
  }
  return "Passé";
}

function formatBytes(value: number) {
  const size = Number(value || 0);
  if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} Mo`;
  return `${Math.max(1, Math.round(size / 1024))} Ko`;
}

function normalizeRequestKind(requestId: string) {
  if (requestId.startsWith("req-")) {
    const raw = requestId.slice(4).replace(/^0+/, "") || "0";
    return { kind: "handoff" as const, rawId: raw };
  }
  if (requestId.startsWith("call-")) {
    return { kind: "call" as const, rawId: requestId.slice(5) };
  }
  return { kind: "unknown" as const, rawId: requestId };
}

function toStatusLabel(statusRaw: "processed" | "cancelled") {
  return statusRaw === "cancelled" ? "Annulée" : "Traitée";
}

function isTerminalLabel(label: string) {
  const normalized = String(label || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
  return normalized.includes("annule") || normalized.includes("traite");
}

function persistRequestStatusOverride(requestId: string, statusRaw: "processed" | "cancelled") {
  if (typeof window === "undefined") return;
  let current: Record<string, { status_raw: string; updated_at: string }> = {};
  try {
    const parsed = JSON.parse(window.localStorage.getItem(REQUEST_STATUS_OVERRIDES_KEY) || "{}");
    if (parsed && typeof parsed === "object") current = parsed;
  } catch {
    current = {};
  }
  current[requestId] = {
    status_raw: statusRaw,
    updated_at: new Date().toISOString(),
  };
  window.localStorage.setItem(REQUEST_STATUS_OVERRIDES_KEY, JSON.stringify(current));
  window.dispatchEvent(new Event("uwi:request-status-updated"));
}

function Toast({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div className="fixed right-6 top-5 z-50 rounded-2xl bg-[#0A1628] px-4 py-3 text-sm font-bold text-white shadow-2xl">
      {message}
    </div>
  );
}

function HeaderAction({
  children,
  variant = "blue",
  onClick,
}: {
  children: React.ReactNode;
  variant?: "blue" | "green" | "purple" | "gray";
  onClick: () => void;
}) {
  const variants = {
    blue: "border-[#8DD8E3] text-[#007E8C] hover:bg-[#E8F8FA]",
    green: "border-[#8DE4AB] text-[#13A146] hover:bg-[#EEFFF4]",
    purple: "border-[#C7A4FF] text-[#7B3DFF] hover:bg-[#F7F0FF]",
    gray: "border-[#DDE7F1] text-[#475569] hover:bg-[#F8FAFC]",
  };

  return (
    <button
      onClick={onClick}
      className={cx(
        "inline-flex h-12 items-center justify-center gap-2 rounded-xl border bg-white px-5 text-sm font-extrabold transition active:scale-[0.98]",
        variants[variant],
      )}
    >
      {children}
    </button>
  );
}

function OutlineTag({ children, tone = "blue" }: { children: React.ReactNode; tone?: "blue" | "red" }) {
  const tones = {
    blue: "border-[#75D3DF] text-[#008EA1]",
    red: "border-[#FF8989] text-[#EE3434]",
  };
  return <span className={cx("rounded-lg border bg-white px-4 py-2 text-sm font-extrabold", tones[tone])}>{children}</span>;
}

function PrimaryCTA({
  children,
  variant = "dark",
  onClick,
}: {
  children: React.ReactNode;
  variant?: "dark" | "note" | "document";
  onClick: () => void;
}) {
  const variants = {
    dark: "bg-gradient-to-br from-[#06355D] to-[#002D4E] text-white shadow-[0_12px_30px_rgba(3,49,82,.20)] hover:brightness-110",
    note: "border border-[#FF9C4B] bg-white text-[#F26C00] hover:bg-[#FFF7EF]",
    document: "border border-[#6AD58B] bg-white text-[#0EA348] hover:bg-[#F0FFF5]",
  };

  return (
    <button
      onClick={onClick}
      className={cx(
        "flex h-16 items-center justify-center gap-3 rounded-2xl px-6 text-base font-black transition active:scale-[0.98]",
        variants[variant],
      )}
    >
      {children}
    </button>
  );
}

function Modal({
  title,
  children,
  onClose,
  width = "max-w-3xl",
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  width?: string;
}) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-[#0A1628]/35 p-6 backdrop-blur-sm" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className={cx("max-h-[88vh] w-full overflow-auto rounded-[28px] bg-white p-7 shadow-2xl", width)}>
        <div className="mb-6 flex items-center justify-between gap-4">
          <h2 className="text-2xl font-black tracking-tight text-[#0A1628]">{title}</h2>
          <button onClick={onClose} className="grid h-10 w-10 place-items-center rounded-xl border border-[#DDE7F1] text-xl font-black hover:bg-[#F8FAFC]">
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export default function PatientDashboardPage() {
  const outlet = useOutletContext() as { me?: { tenant_name?: string } } | undefined;
  const meTenantName = outlet?.me?.tenant_name?.trim();

  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("Tous");
  const [activeView, setActiveView] = useState<ViewType>("overview");
  const [toast, setToast] = useState("");
  const [modal, setModal] = useState<ModalType>(null);
  const [note, setNote] = useState("");
  const [patientNotes, setPatientNotes] = useState<PatientNote[]>([]);
  const [notesLoading, setNotesLoading] = useState(false);
  const [notesSaving, setNotesSaving] = useState(false);
  const [noteDeletingId, setNoteDeletingId] = useState<number | null>(null);
  const [documents, setDocuments] = useState<PatientDocument[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentsUploading, setDocumentsUploading] = useState(false);
  const [documentDeletingId, setDocumentDeletingId] = useState<number | null>(null);
  const [documentSendingId, setDocumentSendingId] = useState<number | null>(null);
  const [previewDoc, setPreviewDoc] = useState<PatientDocument | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [patientEmail, setPatientEmail] = useState("");
  const [editingEmail, setEditingEmail] = useState(false);
  const [emailDraft, setEmailDraft] = useState("");
  const [emailSaving, setEmailSaving] = useState(false);
  const [requestStatus, setRequestStatus] = useState("");
  const [requestActionLoading, setRequestActionLoading] = useState<"" | "processed" | "cancelled">("");
  const [tenantPatientNotFound, setTenantPatientNotFound] = useState(false);
  /** Profil réel (API) pour l’en-tête quand on ouvre /patient-dashboard?phone=… ou un numéro reconnu en base. */
  const [urlPatientHero, setUrlPatientHero] = useState<{ name: string; phone: string; initials: string } | null>(null);
  const [tenantSidebarRows, setTenantSidebarRows] = useState<SidebarPatientRow[]>([]);
  const [tenantListLoading, setTenantListLoading] = useState(true);
  const toastTimerRef = useRef<number | null>(null);
  const sidebarBootstrapDoneRef = useRef(false);
  const [tenantAgendaRawSlots, setTenantAgendaRawSlots] = useState<Array<Record<string, unknown>>>([]);
  const [patientAgendaLoading, setPatientAgendaLoading] = useState(false);
  /** Recherche serveur GET /patients?q= ; null si la recherche API n’est pas utilisée (< 2 caractères). */
  const [patientSearchRows, setPatientSearchRows] = useState<SidebarPatientRow[] | null>(null);
  const [patientSearchLoading, setPatientSearchLoading] = useState(false);
  /** Recharge GET /patients/{phone} (ex. après POST création ou mise à jour nom). */
  const [patientFetchNonce, setPatientFetchNonce] = useState(0);
  /** Ligne brute API `cabinet_clients` pour le modal profil / métadonnées. */
  const [patientCabinetRow, setPatientCabinetRow] = useState<Record<string, unknown> | null>(null);
  const [createFicheName, setCreateFicheName] = useState("");
  const [createFicheSaving, setCreateFicheSaving] = useState(false);
  const [profileNameDraft, setProfileNameDraft] = useState("");
  const [profileSaveSaving, setProfileSaveSaving] = useState(false);
  const [deletePreviewLoading, setDeletePreviewLoading] = useState(false);
  const [deletePreview, setDeletePreview] = useState<null | {
    confirmation_token: string;
    expires_at: string;
    summary: {
      phone: string;
      display_name: string;
      notes_count: number;
      documents_count: number;
      documents?: Array<{ id: number; original_name: string }>;
    };
  }>(null);
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [deleteSaving, setDeleteSaving] = useState(false);

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    };
  }, []);

  const requestContext = useMemo<RequestContext | null>(() => {
    const requestId = (searchParams.get("requestId") || "").trim();
    if (!requestId) return null;
    return {
      id: requestId,
      phone: (searchParams.get("phone") || "").trim(),
      patientName: (searchParams.get("patientName") || "").trim(),
      summary: (searchParams.get("summary") || "Demande transférée par Clara nécessitant une action humaine.").trim(),
      type: (searchParams.get("type") || "Transfert humain").trim(),
      status: (searchParams.get("status") || "À traiter").trim(),
      source: (searchParams.get("source") || "Via transfert").trim(),
      createdAtLabel: (searchParams.get("createdAtLabel") || "Maintenant").trim(),
    };
  }, [searchParams]);

  useEffect(() => {
    if (!tenantPatientNotFound) return;
    const hint = String(requestContext?.patientName || "").trim();
    if (hint) setCreateFicheName((prev) => (prev.trim() ? prev : hint));
  }, [tenantPatientNotFound, requestContext?.patientName]);

  const phoneFromDashboardUrl = useMemo(() => (searchParams.get("phone") || "").trim(), [searchParams]);
  const isDirectPhoneView = Boolean(phoneFromDashboardUrl);
  const tenantPatientPhone = useMemo(() => normalizePhone(phoneFromDashboardUrl), [phoneFromDashboardUrl]);

  /** Corrige ?phone= après décodage URL (notamment « + » → espace) ou variants 06 / espaces. */
  useEffect(() => {
    const raw = (searchParams.get("phone") || "").trim();
    const canonical = normalizePhone(raw);
    if (!canonical || canonical === raw) return;
    const np = new URLSearchParams(searchParams);
    np.set("phone", canonical);
    setSearchParams(np, { replace: true });
  }, [searchParams, setSearchParams]);

  const loadTenantSidebarPatients = useCallback(async () => {
    try {
      const res = await api.tenantGetPatients("?limit=500");
      const items = Array.isArray(res?.items) ? res.items : [];
      const mapped = items
        .map((item: Record<string, unknown>) => cabinetRowToSidebar(item))
        .filter((item): item is SidebarPatientRow => Boolean(item));
      setTenantSidebarRows(mapped);
    } catch {
      setTenantSidebarRows([]);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    setTenantListLoading(true);
    loadTenantSidebarPatients().finally(() => {
      if (!cancelled) setTenantListLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [loadTenantSidebarPatients]);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setPatientSearchRows(null);
      setPatientSearchLoading(false);
      return undefined;
    }
    setPatientSearchLoading(true);
    setPatientSearchRows(null);
    let cancelled = false;
    const timer = window.setTimeout(() => {
      api
        .tenantGetPatients(`?q=${encodeURIComponent(q)}&limit=100`)
        .then((res) => {
          if (cancelled) return;
          const items = Array.isArray(res?.items) ? res.items : [];
          const mapped = items
            .map((item: Record<string, unknown>) => cabinetRowToSidebar(item))
            .filter((row): row is SidebarPatientRow => Boolean(row));
          setPatientSearchRows(mapped);
        })
        .catch(() => {
          if (!cancelled) setPatientSearchRows([]);
        })
        .finally(() => {
          if (!cancelled) setPatientSearchLoading(false);
        });
    }, 320);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query]);

  useEffect(() => {
    const pnorm = normalizePhone(phoneFromDashboardUrl);
    if (!pnorm) return undefined;
    const t = window.setTimeout(() => {
      loadTenantSidebarPatients();
    }, 450);
    return () => window.clearTimeout(t);
  }, [phoneFromDashboardUrl, loadTenantSidebarPatients]);

  useEffect(() => {
    if (tenantListLoading) return;
    if (normalizePhone(searchParams.get("phone") || "")) return;
    if ((searchParams.get("requestId") || "").trim()) return;
    if (!tenantSidebarRows.length) return;
    if (sidebarBootstrapDoneRef.current) return;
    sidebarBootstrapDoneRef.current = true;
    const first = normalizePhone(tenantSidebarRows[0]?.phone || "");
    if (!first) return;
    const np = new URLSearchParams(searchParams);
    np.set("phone", first);
    setSearchParams(np, { replace: true });
  }, [tenantListLoading, tenantSidebarRows, searchParams, setSearchParams]);

  const effectiveSidebarRows = useMemo(() => {
    let rows = injectSelectedPatientRow([...tenantSidebarRows], tenantPatientPhone, urlPatientHero);
    /** GET /patients/{phone} en 404 mais numéro connu dans l’URL : garder une ligne liste + en-tête cohérents. */
    if (
      tenantPatientNotFound &&
      tenantPatientPhone &&
      !rows.some((r) => r.phone === tenantPatientPhone)
    ) {
      rows = [
        {
          phone: tenantPatientPhone,
          displayPhone: formatDisplayFrenchPhone(tenantPatientPhone),
          name: "Patient — nom à compléter",
          initials: "?",
          dateLabel: "—",
          gradient: sidebarGradient(tenantPatientPhone),
          hasValidated: false,
          statusBucket: "new",
        },
        ...rows,
      ];
    }
    return rows;
  }, [tenantSidebarRows, tenantPatientPhone, urlPatientHero, tenantPatientNotFound]);

  const effectiveSearchSidebarRows = useMemo((): SidebarPatientRow[] | null => {
    if (patientSearchRows === null) return null;
    return injectSelectedPatientRow([...patientSearchRows], tenantPatientPhone, urlPatientHero);
  }, [patientSearchRows, tenantPatientPhone, urlPatientHero]);

  const sidebarHeroFallback = useMemo(
    () => effectiveSidebarRows.find((r) => r.phone === tenantPatientPhone) || null,
    [effectiveSidebarRows, tenantPatientPhone],
  );

  const sidebarCounts = useMemo(
    () => ({
      total: effectiveSidebarRows.length,
      aTraiter: effectiveSidebarRows.filter((r) => !r.hasValidated).length,
      nouveaux: effectiveSidebarRows.filter((r) => r.statusBucket === "new").length,
    }),
    [effectiveSidebarRows],
  );

  const filteredSidebarRows = useMemo(() => {
    const qTrim = query.trim();
    const qLower = qTrim.toLowerCase();

    const rowMatchesQuery = (row: SidebarPatientRow) => {
      const hay = `${row.name} ${row.displayPhone} ${row.phone}`.toLowerCase();
      if (hay.includes(qLower)) return true;
      const needle = normalizePhone(qTrim);
      return Boolean(needle && row.phone === needle);
    };

    let out: SidebarPatientRow[];
    if (qTrim.length >= 2) {
      const locally = effectiveSidebarRows.filter(rowMatchesQuery);
      if (patientSearchLoading || patientSearchRows === null) {
        out = locally;
      } else {
        const fromApi = effectiveSearchSidebarRows ?? [];
        out = fromApi.length > 0 ? fromApi : locally;
      }
    } else {
      out = effectiveSidebarRows;
      if (qTrim.length === 1) {
        out = out.filter((row) =>
          `${row.name} ${row.displayPhone} ${row.phone}`.toLowerCase().includes(qLower),
        );
      }
    }

    if (filter === "À traiter") out = out.filter((row) => !row.hasValidated);
    if (filter === "Nouveaux") out = out.filter((row) => row.statusBucket === "new");
    return out;
  }, [
    effectiveSidebarRows,
    effectiveSearchSidebarRows,
    patientSearchLoading,
    patientSearchRows,
    query,
    filter,
  ]);

  const sidebarSearchPending = Boolean(query.trim().length >= 2 && patientSearchLoading);

  useEffect(() => {
    if (!phoneFromDashboardUrl) setUrlPatientHero(null);
  }, [phoneFromDashboardUrl]);

  const displayHero = useMemo(() => {
    const teal = "from-[#009CA4] to-[#004C69]";
    const slate = "from-slate-400 to-slate-600";
    const loadingGrad = "from-slate-300 to-slate-500";
    if (tenantPatientNotFound) {
      if (sidebarHeroFallback && sidebarHeroFallback.phone === tenantPatientPhone) {
        return {
          name: sidebarHeroFallback.name,
          phone: formatDisplayFrenchPhone(tenantPatientPhone || phoneFromDashboardUrl),
          initials: sidebarHeroFallback.initials,
          gradient: sidebarHeroFallback.gradient,
        };
      }
      if (isDirectPhoneView) {
        return {
          name: "Aucune fiche pour ce numéro",
          phone: formatDisplayFrenchPhone(tenantPatientPhone || phoneFromDashboardUrl),
          initials: "?",
          gradient: slate,
        };
      }
      return {
        name: "Patient",
        phone: "—",
        initials: "?",
        gradient: slate,
      };
    }
    if (urlPatientHero) {
      return {
        ...urlPatientHero,
        phone: formatDisplayFrenchPhone(normalizePhone(urlPatientHero.phone) || urlPatientHero.phone),
        gradient: teal,
      };
    }
    if (documentsLoading && tenantPatientPhone) {
      return {
        name: "Chargement…",
        phone: formatDisplayFrenchPhone(tenantPatientPhone),
        initials: "…",
        gradient: loadingGrad,
      };
    }
    if (sidebarHeroFallback) {
      return {
        name: sidebarHeroFallback.name,
        phone: sidebarHeroFallback.displayPhone,
        initials: sidebarHeroFallback.initials,
        gradient: sidebarHeroFallback.gradient,
      };
    }
    return {
      name: "Patient",
      phone: "—",
      initials: "?",
      gradient: slate,
    };
  }, [
    tenantPatientNotFound,
    isDirectPhoneView,
    phoneFromDashboardUrl,
    tenantPatientPhone,
    urlPatientHero,
    documentsLoading,
    sidebarHeroFallback,
  ]);

  useEffect(() => {
    setRequestStatus(requestContext?.status || "");
    setRequestActionLoading("");
  }, [requestContext?.id, requestContext?.status]);

  useEffect(() => {
    let cancelled = false;
    if (!tenantPatientPhone) {
      setDocuments([]);
      setUrlPatientHero(null);
      setTenantPatientNotFound(false);
      return () => {
        cancelled = true;
      };
    }
    setDocumentsLoading(true);
    api.tenantGetPatient(tenantPatientPhone)
      .then((res) => {
        if (cancelled) return;
        setTenantPatientNotFound(false);
        const p = res?.patient as Record<string, unknown> | undefined;
        setPatientCabinetRow(p ?? null);
        if (p) {
          const name =
            String(p.display_name || p.validated_name || p.raw_name || "Patient").trim() || "Patient";
          const tel = String(p.phone || tenantPatientPhone).trim();
          setUrlPatientHero({ name, phone: tel, initials: initialsFromFullName(name) });
        } else {
          setUrlPatientHero(null);
        }
        const list = Array.isArray(res?.documents) ? res.documents : [];
        setPatientEmail(String(p?.email || ""));
        setDocuments(
          list.map((item: any) => ({
            id: Number(item.id),
            original_name: String(item.original_name || ""),
            mime_type: String(item.mime_type || ""),
            size_bytes: Number(item.size_bytes || 0),
            created_at: String(item.created_at || ""),
          })),
        );
      })
      .catch((e: unknown) => {
        const status =
          typeof e === "object" && e !== null && "status" in e ? (e as { status?: number }).status : undefined;
        if (!cancelled) setDocuments([]);
        if (!cancelled) setPatientEmail("");
        if (!cancelled) setUrlPatientHero(null);
        if (!cancelled) setPatientCabinetRow(null);
        if (!cancelled) setTenantPatientNotFound(status === 404);
      })
      .finally(() => {
        if (!cancelled) setDocumentsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tenantPatientPhone, patientFetchNonce]);

  useEffect(() => {
    if (!editingEmail) setEmailDraft(patientEmail || "");
  }, [patientEmail, editingEmail]);

  useEffect(() => {
    let cancelled = false;
    if (!tenantPatientPhone) {
      setPatientNotes([]);
      return () => {
        cancelled = true;
      };
    }
    setNotesLoading(true);
    api.tenantGetPatientNotes(tenantPatientPhone, "?limit=100")
      .then((res) => {
        if (cancelled) return;
        const items = Array.isArray(res?.items) ? res.items : [];
        setPatientNotes(
          items.map((item: any) => ({
            id: Number(item.id),
            text: String(item.text || ""),
            author: String(item.author || "Cabinet"),
            created_at: String(item.created_at || ""),
          })),
        );
      })
      .catch(() => {
        if (!cancelled) setPatientNotes([]);
      })
      .finally(() => {
        if (!cancelled) setNotesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tenantPatientPhone, patientFetchNonce]);

  useEffect(() => {
    let cancelled = false;
    if (!tenantPatientPhone) {
      setTenantAgendaRawSlots([]);
      setPatientAgendaLoading(false);
      return () => {
        cancelled = true;
      };
    }
    setPatientAgendaLoading(true);
    api
      .tenantGetAgenda("?upcoming_days=60&compact=1")
      .then((res) => {
        if (cancelled) return;
        const slots = Array.isArray(res?.slots) ? res.slots : [];
        setTenantAgendaRawSlots(slots as Array<Record<string, unknown>>);
      })
      .catch(() => {
        if (!cancelled) setTenantAgendaRawSlots([]);
      })
      .finally(() => {
        if (!cancelled) setPatientAgendaLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tenantPatientPhone]);

  const patientAgendaSlots = useMemo(() => {
    if (!tenantPatientPhone) return [];
    const needle = normalizePhone(tenantPatientPhone);
    const heroKey = normalizeAgendaPatientName(String(urlPatientHero?.name || ""));
    const genericPatientName = normalizeAgendaPatientName("Patient");
    const heroIsPlaceholder =
      !heroKey ||
      heroKey === genericPatientName ||
      heroKey.includes("nom a completer") ||
      heroKey.includes("nom à compléter") ||
      (heroKey.startsWith("patient ") && heroKey.includes("complet"));

    return tenantAgendaRawSlots.filter((raw) => {
      const row = raw as Record<string, unknown>;
      const pn = normalizePhone(String(row.patient_phone || ""));
      if (needle && pn && pn === needle) return true;

      const slotNameKey = normalizeAgendaPatientName(String(row.patient || ""));
      if (
        slotNameKey.length >= 2 &&
        !heroIsPlaceholder &&
        heroKey.length >= 2 &&
        heroKey === slotNameKey
      )
        return true;

      if (!pn && heroKey && slotNameKey.length >= 2 && heroKey === slotNameKey) return true;
      return false;
    });
  }, [tenantAgendaRawSlots, tenantPatientPhone, urlPatientHero?.name]);

  const patientAgendaParsed = useMemo(() => {
    const rows: Array<{ slot: Record<string, unknown>; start: Date }> = [];
    for (const slot of patientAgendaSlots) {
      const start = parseAgendaSlotStart(slot);
      if (start) rows.push({ slot, start });
    }
    rows.sort((a, b) => a.start.getTime() - b.start.getTime());
    return rows;
  }, [patientAgendaSlots]);

  const upcomingPatientAppointments = useMemo(() => {
    const now = Date.now();
    return patientAgendaParsed.filter((x) => x.start.getTime() >= now);
  }, [patientAgendaParsed]);

  useEffect(() => {
    if (modal === "profile" && urlPatientHero?.name) setProfileNameDraft(urlPatientHero.name);
  }, [modal, urlPatientHero?.name]);

  const createPatientFichePractice = useCallback(
    async (validatedName: string) => {
      const name = validatedName.trim();
      const debugCtx = { phone: tenantPatientPhone, nameLen: name.length };
      console.info("[fiche.create] start", debugCtx);
      if (!tenantPatientPhone) {
        console.warn("[fiche.create] abort: no phone", debugCtx);
        notify("Aucun numéro patient — rouvrez la fiche depuis la liste Patients.", { sticky: true });
        return false;
      }
      if (name.length < 2) {
        console.warn("[fiche.create] abort: name too short", debugCtx);
        notify("Saisissez le prénom et le nom (au moins 2 caractères) puis recliquez sur « Créer la fiche ».", { sticky: true });
        return false;
      }
      try {
        const res = await api.tenantRegisterPatient({
          patient_phone: tenantPatientPhone,
          validated_name: name,
          raw_name: name,
        });
        console.info("[fiche.create] success", { ...debugCtx, register_mode: res?.register_mode });
        const profile = res?.patient as Record<string, unknown> | undefined;
        if (profile) {
          const disp =
            String(profile.display_name || profile.validated_name || profile.raw_name || name).trim() || name;
          const tel = String(profile.phone || tenantPatientPhone).trim();
          setUrlPatientHero({ name: disp, phone: tel, initials: initialsFromFullName(disp) });
          setPatientCabinetRow(profile);
          setPatientEmail(String(profile.email || ""));
        }
        setTenantPatientNotFound(false);
        notify(res?.register_mode === "updated" ? "Fiche mise à jour" : "Fiche patient enregistrée");
        setPatientFetchNonce((n) => n + 1);
        await loadTenantSidebarPatients();
        return true;
      } catch (e) {
        console.error("[fiche.create] failure", debugCtx, e);
        notify((e as Error)?.message || "Impossible d’enregistrer la fiche", { sticky: true });
        return false;
      }
    },
    [tenantPatientPhone, loadTenantSidebarPatients],
  );

  const saveNewPatientBanner = async () => {
    setCreateFicheSaving(true);
    try {
      const ok = await createPatientFichePractice(createFicheName);
      if (ok) setCreateFicheName("");
    } finally {
      setCreateFicheSaving(false);
    }
  };

  const saveProfileFromModal = async () => {
    setProfileSaveSaving(true);
    try {
      const ok = await createPatientFichePractice(profileNameDraft);
      if (ok) setModal(null);
    } finally {
      setProfileSaveSaving(false);
    }
  };

  const openDeletePatientModal = async () => {
    if (!tenantPatientPhone) return;
    setDeletePreviewLoading(true);
    setDeletePreview(null);
    setDeleteConfirmText("");
    setModal("deletePatient");
    try {
      const res = await api.tenantPreparePatientDelete(tenantPatientPhone);
      setDeletePreview({
        confirmation_token: String(res?.confirmation_token || ""),
        expires_at: String(res?.expires_at || ""),
        summary: {
          phone: String(res?.summary?.phone || tenantPatientPhone),
          display_name: String(res?.summary?.display_name || displayHero.name || "Patient"),
          notes_count: Number(res?.summary?.notes_count || 0),
          documents_count: Number(res?.summary?.documents_count || 0),
          documents: Array.isArray(res?.summary?.documents) ? res.summary.documents : [],
        },
      });
    } catch (e) {
      notify((e as Error)?.message || "Impossible de préparer la suppression", { sticky: true });
      setModal(null);
    } finally {
      setDeletePreviewLoading(false);
    }
  };

  const confirmDeletePatient = async () => {
    if (!tenantPatientPhone || !deletePreview) return;
    if (deleteConfirmText.trim().toUpperCase() !== "SUPPRIMER") {
      notify("Tapez exactement SUPPRIMER pour continuer.", { sticky: true });
      return;
    }
    const doubleCheck = window.confirm(
      `Confirmer la suppression définitive de la fiche "${deletePreview.summary.display_name}" (${formatDisplayFrenchPhone(deletePreview.summary.phone)}) ?\n\nCette action est irréversible.`,
    );
    if (!doubleCheck) return;
    setDeleteSaving(true);
    try {
      const res = await api.tenantConfirmPatientDelete(tenantPatientPhone, {
        confirmation_token: deletePreview.confirmation_token,
        confirmation_phrase: deleteConfirmText.trim(),
      });
      if (!res?.ok) throw new Error("Suppression non confirmée");
      notify("Fiche patient supprimée définitivement");
      setModal(null);
      setDeletePreview(null);
      setDeleteConfirmText("");
      await loadTenantSidebarPatients();
      const np = new URLSearchParams(searchParams);
      np.delete("phone");
      setSearchParams(np, { replace: true });
    } catch (e) {
      notify((e as Error)?.message || "Erreur suppression fiche", { sticky: true });
    } finally {
      setDeleteSaving(false);
    }
  };

  const notify = (message: string, opts?: { sticky?: boolean }) => {
    setToast(message);
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    /* Toast "sticky" (erreur/validation) = 6 s pour laisser le temps de lire avant qu'il disparaisse. */
    const ms = opts?.sticky ? 6000 : 1800;
    toastTimerRef.current = window.setTimeout(() => setToast(""), ms);
  };

  const saveNote = async () => {
    if (!note.trim()) {
      notify("Ajoute une note avant d'enregistrer");
      return false;
    }
    if (!tenantPatientPhone) {
      notify("Aucun patient sélectionné");
      return false;
    }
    setNotesSaving(true);
    try {
      const res = await api.tenantCreatePatientNote(tenantPatientPhone, { text: note.trim(), author: "Praticien" });
      const created = res?.item;
      if (created) {
        setPatientNotes((prev) => [
          {
            id: Number(created.id),
            text: String(created.text || ""),
            author: String(created.author || "Praticien"),
            created_at: String(created.created_at || ""),
          },
          ...prev,
        ]);
      }
      setNote("");
      notify("Note ajoutée au contexte patient");
      return true;
    } catch (e) {
      notify((e as Error)?.message || "Erreur ajout note");
      return false;
    } finally {
      setNotesSaving(false);
    }
  };

  const removeNote = async (noteId: number) => {
    if (!tenantPatientPhone || !noteId) return;
    setNoteDeletingId(noteId);
    try {
      await api.tenantDeletePatientNote(tenantPatientPhone, noteId);
      setPatientNotes((prev) => prev.filter((item) => item.id !== noteId));
      notify("Note supprimée");
    } catch (e) {
      notify((e as Error)?.message || "Erreur suppression note");
    } finally {
      setNoteDeletingId(null);
    }
  };

  const uploadDocument = async (file?: File | null) => {
    if (!file) return;
    if (!tenantPatientPhone) {
      notify("Aucun patient sélectionné");
      return;
    }
    setDocumentsUploading(true);
    try {
      const res = await api.tenantUploadPatientDocument(tenantPatientPhone, file);
      const created = res?.document;
      if (created) {
        setDocuments((prev) => [
          {
            id: Number(created.id),
            original_name: String(created.original_name || file.name),
            mime_type: String(created.mime_type || file.type || "application/octet-stream"),
            size_bytes: Number(created.size_bytes || file.size || 0),
            created_at: String(created.created_at || ""),
          },
          ...prev,
        ]);
      }
      notify("Document ajouté");
    } catch (e) {
      notify((e as Error)?.message || "Erreur upload document");
    } finally {
      setDocumentsUploading(false);
    }
  };

  const downloadDocument = async (doc: PatientDocument) => {
    if (!tenantPatientPhone) return;
    try {
      const url = api.tenantDownloadPatientDocument(tenantPatientPhone, doc.id);
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("Téléchargement échoué");
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = doc.original_name || "document";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (e) {
      notify((e as Error)?.message || "Erreur téléchargement");
    }
  };

  const openPreview = async (doc: PatientDocument) => {
    if (!tenantPatientPhone) return;
    const canPreview = doc.mime_type.includes("pdf") || doc.mime_type.startsWith("image/");
    if (!canPreview) {
      await downloadDocument(doc);
      return;
    }
    try {
      const url = api.tenantDownloadPatientDocument(tenantPatientPhone, doc.id);
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("Impossible de charger le document");
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      setPreviewDoc(doc);
      setPreviewUrl(objectUrl);
    } catch (e) {
      notify((e as Error)?.message || "Erreur prévisualisation");
    }
  };

  const closePreview = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewDoc(null);
    setPreviewUrl("");
  };

  const deleteDocument = async (docId: number) => {
    if (!tenantPatientPhone || !docId) return;
    setDocumentDeletingId(docId);
    try {
      await api.tenantDeletePatientDocument(tenantPatientPhone, docId);
      setDocuments((prev) => prev.filter((doc) => doc.id !== docId));
      notify("Document supprimé");
    } catch (e) {
      notify((e as Error)?.message || "Erreur suppression document");
    } finally {
      setDocumentDeletingId(null);
    }
  };

  const sendDocument = async (docId: number) => {
    if (!tenantPatientPhone || !docId) return;
    if (!patientEmail) {
      notify("Ajoute d'abord l'email du patient");
      return;
    }
    setDocumentSendingId(docId);
    try {
      await api.tenantSendPatientDocument(tenantPatientPhone, docId);
      notify(`Document envoyé à ${patientEmail}`);
    } catch (e) {
      notify((e as Error)?.message || "Erreur envoi email");
    } finally {
      setDocumentSendingId(null);
    }
  };

  const saveEmail = async () => {
    if (!tenantPatientPhone) {
      notify("Aucun patient sélectionné", { sticky: true });
      return;
    }
    const next = emailDraft.trim();
    /* Validation côté front : alignée sur la validation backend pour éviter les 422 silencieux. */
    if (next && (!next.includes("@") || next.includes(" ") || !next.split("@")[1]?.includes("."))) {
      notify("Email invalide (format attendu : prenom@domaine.fr)", { sticky: true });
      return;
    }
    setEmailSaving(true);
    console.info("[patient.email] PATCH start", { phone: tenantPatientPhone, hasEmail: !!next });
    try {
      const res = await api.tenantUpdatePatient(tenantPatientPhone, { email: next });
      console.info("[patient.email] PATCH ok", res);
      /* On reflète la valeur renvoyée par le backend pour éviter d'afficher localement une valeur non persistée. */
      const persisted = String(res?.patient?.email ?? next);
      setPatientEmail(persisted);
      setEmailDraft(persisted);
      setEditingEmail(false);
      notify(persisted ? `Email enregistré : ${persisted}` : "Email supprimé");
    } catch (e) {
      console.error("[patient.email] PATCH failure", e);
      const msg = (e as Error)?.message || "Erreur mise à jour email";
      notify(msg, { sticky: true });
    } finally {
      setEmailSaving(false);
    }
  };

  const updateRequestStatus = async (nextStatus: "processed" | "cancelled") => {
    if (!requestContext?.id) return;
    const info = normalizeRequestKind(requestContext.id);
    if (info.kind === "call" && nextStatus === "cancelled") {
      notify("Annulation indisponible pour ce type de demande");
      return;
    }
    setRequestActionLoading(nextStatus);
    try {
      if (info.kind === "handoff") {
        await api.tenantUpdateHandoff(info.rawId, { status: nextStatus });
      } else if (info.kind === "call") {
        await api.tenantUpdateCallFollowup(info.rawId, { followup_state: "processed" });
      } else {
        throw new Error("Demande introuvable");
      }
      const nextLabel = toStatusLabel(nextStatus);
      setRequestStatus(nextLabel);
      persistRequestStatusOverride(requestContext.id, nextStatus);
      const next = new URLSearchParams(searchParams);
      next.set("status", nextLabel);
      setSearchParams(next, { replace: true });
      notify(nextStatus === "cancelled" ? "Demande annulée" : "Demande marquée traitée");
    } catch (e) {
      notify((e as Error)?.message || "Erreur de mise à jour");
    } finally {
      setRequestActionLoading("");
    }
  };

  return (
    <div className="min-h-screen bg-[#F7FAFC] text-[#0A1628]">
      <Toast message={toast} />

      <div className="grid min-h-screen grid-cols-1 xl:grid-cols-[330px_minmax(0,1fr)]">
        <aside className="border-b border-[#E5EDF5] bg-white px-4 py-5 sm:px-6 sm:py-7 xl:border-b-0 xl:border-r xl:px-6 xl:py-8">
          <div className="mb-5 flex items-center justify-between">
            <h2 className="text-2xl font-black">Patients</h2>
            <span className="rounded-xl bg-[#EEF6FA] px-3 py-1.5 text-sm font-black text-[#1C4B6B]">{sidebarCounts.total}</span>
          </div>

          <div className="relative mb-5">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-lg text-[#8D9AAF]">⌕</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Rechercher (nom ou téléphone, 2+ caractères)…"
              className="h-12 w-full rounded-xl border border-[#DDE7F1] bg-white pl-11 pr-4 text-sm outline-none transition placeholder:text-[#9AA8BB] focus:border-[#009CA4] focus:ring-4 focus:ring-[#009CA4]/10"
            />
            {!tenantListLoading && tenantSidebarRows.length >= 500 ? (
              <p className="mt-2 text-xs font-semibold leading-relaxed text-[#8D9AAF]">
                Affichage des 500 fiches les plus récentes. Pour retrouver un patient hors de cette liste, tapez au moins 2 caractères (nom ou numéro).
              </p>
            ) : null}
          </div>

          <div className="mb-6 flex flex-wrap gap-2">
            {[["Tous", String(sidebarCounts.total)], ["À traiter", String(sidebarCounts.aTraiter)], ["Nouveaux", String(sidebarCounts.nouveaux)]].map(([label, count]) => (
              <button
                key={label}
                onClick={() => setFilter(label)}
                className={cx(
                  "rounded-lg border px-3.5 py-2 text-xs font-black transition",
                  filter === label
                    ? "border-[#009CA4] bg-white text-[#008EA1] shadow-sm"
                    : label === "À traiter"
                      ? "border-[#FFE4D1] bg-[#FFF7F1] text-[#EF6C00]"
                      : "border-[#E2EAF4] bg-[#F9FCFF] text-[#1A72C5]",
                )}
              >
                {label} <span className="ml-1">{count}</span>
              </button>
            ))}
          </div>

          <div className="overflow-hidden rounded-3xl border border-[#E5EDF5] bg-white shadow-sm">
            {tenantListLoading ? (
              <div className="p-10 text-center text-sm font-semibold text-[#64748B]">Chargement de la liste…</div>
            ) : sidebarSearchPending ? (
              <div className="p-10 text-center text-sm font-semibold text-[#64748B]">Recherche dans toutes les fiches…</div>
            ) : filteredSidebarRows.length === 0 ? (
              <div className="p-10 text-center text-sm font-semibold text-[#64748B]">Aucun patient ne correspond aux filtres.</div>
            ) : (
              filteredSidebarRows.map((patient) => {
                const selected = patient.phone === tenantPatientPhone;
                return (
                  <button
                    key={patient.phone}
                    type="button"
                    onClick={() => {
                      const np = new URLSearchParams(searchParams);
                      np.set("phone", patient.phone);
                      setSearchParams(np, { replace: true });
                    }}
                    className={cx(
                      "flex w-full items-center gap-4 border-b border-[#EEF3F8] p-4 text-left transition last:border-b-0",
                      selected ? "bg-[#EAF8FC] ring-1 ring-inset ring-[#BFEAF0]" : "hover:bg-[#F8FBFD]",
                    )}
                  >
                    <div className={cx("grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-gradient-to-br text-lg font-black text-white shadow-sm", patient.gradient)}>
                      {patient.initials}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-black">{patient.name}</div>
                      <div className="mt-1 text-sm text-[#53647F]">{patient.displayPhone}</div>
                    </div>
                    <div className="text-xs font-semibold text-[#53647F]">{patient.dateLabel || "—"}</div>
                  </button>
                );
              })
            )}

            <button
              type="button"
              onClick={() => navigate("/app/patients")}
              className="flex h-16 w-full items-center justify-center gap-3 text-sm font-black text-[#007E8C] hover:bg-[#F8FBFD]"
            >
              Voir tous les patients <span className="text-xl">›</span>
            </button>
          </div>
        </aside>

        <main className="overflow-y-auto px-3 py-4 sm:px-5 sm:py-5 lg:px-8 lg:py-6">
          {tenantPatientNotFound ? (
            <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-950 shadow-sm">
              <p className="m-0">
                <span className="font-black">Aucune fiche patient trouvée pour ce numéro sur le dashboard.</span> Retournez à la liste{" "}
                <button
                  type="button"
                  onClick={() => navigate("/app/patients")}
                  className="font-black text-amber-800 underline underline-offset-2 hover:text-amber-900"
                >
                  Patients
                </button>{" "}
                ou depuis l&apos;{" "}
                <button
                  type="button"
                  onClick={() => navigate("/app/agenda")}
                  className="font-black text-amber-800 underline underline-offset-2 hover:text-amber-900"
                >
                  agenda
                </button>
                . Vous pouvez aussi créer la fiche ici :
              </p>
              {tenantPatientPhone ? (
                <div className="mt-4 flex max-w-xl flex-col gap-2 sm:flex-row sm:items-end">
                  <label className="min-w-0 flex-1 text-sm font-semibold">
                    <span className="mb-1 block text-xs uppercase tracking-wide text-amber-900/75">Nom sur la fiche</span>
                    <input
                      type="text"
                      value={createFicheName}
                      onChange={(e) => setCreateFicheName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !createFicheSaving) {
                          e.preventDefault();
                          void saveNewPatientBanner();
                        }
                      }}
                      placeholder="Prénom et nom"
                      className="box-border w-full rounded-xl border border-amber-200 bg-white px-3 py-2.5 font-semibold text-amber-950 outline-none placeholder:text-amber-800/45 focus:border-amber-500 focus:ring-2 focus:ring-amber-300/40"
                    />
                  </label>
                  <button
                    type="button"
                    disabled={createFicheSaving}
                    onClick={() => void saveNewPatientBanner()}
                    className="shrink-0 rounded-xl bg-amber-900 px-5 py-2.5 font-black text-white shadow-sm hover:bg-amber-950 disabled:opacity-60"
                  >
                    {createFicheSaving ? "Enregistrement…" : "Créer la fiche"}
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}
          <section className="rounded-[28px] border border-[#E2EAF4] bg-white p-4 shadow-[0_18px_45px_rgba(10,22,40,0.06)] sm:p-6 lg:p-7">
            <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between xl:gap-8">
              <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:gap-5 lg:gap-6">
                <div className={cx("grid h-20 w-20 shrink-0 place-items-center rounded-3xl bg-gradient-to-br text-3xl font-black text-white shadow-[8px_10px_0_rgba(0,156,164,0.12)] sm:h-28 sm:w-28 sm:text-4xl xl:h-32 xl:w-32 xl:text-5xl", displayHero.gradient)}>
                  {displayHero.initials}
                </div>

                <div className="min-w-0">
                  <div className="mb-3 flex flex-wrap items-center gap-3">
                    <h1 className="text-2xl font-black tracking-tight sm:text-3xl xl:text-4xl">{displayHero.name}</h1>
                    <span className="rounded-lg bg-[#E6FAED] px-3 py-2 text-sm font-black text-[#0BA64B]">● Actif</span>
                  </div>

                  <div className="mb-5 flex flex-wrap gap-x-8 gap-y-2 text-sm font-semibold text-[#52637C]">
                    <span>☎ {displayHero.phone}</span>
                    {tenantPatientNotFound ? (
                      <span className="inline-flex items-center gap-2 opacity-75">
                        <span>✉</span>
                        Créez d&apos;abord la fiche ci-dessus pour ajouter un email.
                      </span>
                    ) : editingEmail ? (
                      <span className="inline-flex items-center gap-2">
                        <span>✉</span>
                        <input
                          value={emailDraft}
                          onChange={(event) => setEmailDraft(event.target.value)}
                          placeholder="email@cabinet.fr"
                          className="h-8 rounded-lg border border-[#DDE7F1] px-2 text-sm font-semibold text-[#0A1628] outline-none focus:border-[#009CA4]"
                        />
                        <button type="button" onClick={saveEmail} disabled={emailSaving} className="rounded-lg bg-[#009CA4] px-2 py-1 text-xs font-black text-white disabled:opacity-60">
                          {emailSaving ? "..." : "OK"}
                        </button>
                        <button type="button" onClick={() => setEditingEmail(false)} className="rounded-lg border border-[#DDE7F1] px-2 py-1 text-xs font-black text-[#475569]">
                          Annuler
                        </button>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-2">
                        <span>✉ {patientEmail || "Aucun email"}</span>
                        <button type="button" onClick={() => setEditingEmail(true)} className="rounded-lg border border-[#DDE7F1] px-2 py-1 text-xs font-black text-[#475569] hover:bg-[#F8FAFC]">
                          {patientEmail ? "Modifier" : "Ajouter"}
                        </button>
                      </span>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-3">
                    <OutlineTag>Patient régulier</OutlineTag>
                    <OutlineTag>Préférence matin</OutlineTag>
                    <OutlineTag>SMS préféré</OutlineTag>
                    <OutlineTag tone="red">Risque no-show</OutlineTag>
                  </div>
                </div>
              </div>

              <div className="flex w-full shrink-0 flex-wrap gap-2 sm:gap-3 xl:w-auto xl:justify-end">
                <HeaderAction
                  onClick={() => {
                    const t = normalizePhone(displayHero.phone);
                    if (t) window.location.href = `tel:${t}`;
                    else notify("Numéro absent pour passer un appel.");
                  }}
                >
                  ☎ Appeler
                </HeaderAction>
                <HeaderAction variant="green" onClick={() => notify("WhatsApp ouvert")}>☘ WhatsApp</HeaderAction>
                <HeaderAction variant="purple" onClick={() => notify("SMS ouvert")}>▣ SMS</HeaderAction>
                <HeaderAction variant="gray" onClick={() => notify("Menu patient ouvert")}>•••</HeaderAction>
              </div>
            </div>
          </section>

          <section className="mt-5 rounded-[26px] border border-[#E2EAF4] bg-white shadow-sm">
            <div className="flex overflow-x-auto border-b border-[#EEF3F8]">
              {viewTabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveView(tab.id)}
                  className={cx(
                    "relative flex h-14 shrink-0 items-center gap-2 whitespace-nowrap px-4 text-sm font-black transition sm:h-16 sm:gap-3 sm:px-6 lg:px-8",
                    activeView === tab.id ? "text-[#008EA1]" : "text-[#42536E] hover:bg-[#F8FBFD]",
                  )}
                >
                  <span className="text-xl">{tab.icon}</span>
                  {tab.label}
                  {activeView === tab.id && <span className="absolute bottom-0 left-0 right-0 h-1 bg-[#009CA4]" />}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-1 gap-4 p-5 sm:grid-cols-2 lg:grid-cols-4">
              <PrimaryCTA onClick={() => setModal("profile")}>✎ Voir le profil détaillé</PrimaryCTA>
              <PrimaryCTA variant="note" onClick={() => setModal("addNote")}>✎ Ajouter une note</PrimaryCTA>
              <PrimaryCTA variant="document" onClick={() => setModal("addDocument")}>▤ Ajouter un document</PrimaryCTA>
              <button
                type="button"
                onClick={() => void openDeletePatientModal()}
                className="rounded-2xl border border-red-200 bg-red-50 px-4 py-4 text-left text-sm font-black text-red-700 transition hover:bg-red-100"
              >
                🗑 Supprimer la fiche patient
              </button>
            </div>
          </section>

          {requestContext && (
            <section className="mt-6 rounded-[28px] border border-[#FFD9B8] bg-[#FFF7F0] p-6 shadow-sm">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-2xl font-black text-[#0A1628]">Demande à traiter</h2>
                  <p className="mt-1 text-sm font-semibold text-[#6B5A4A]">
                    Demande transférée car elle nécessite une action humaine
                  </p>
                </div>
                <button
                  onClick={() => {
                    const next = new URLSearchParams(searchParams);
                    [
                      "requestId",
                      "phone",
                      "patientName",
                      "summary",
                      "type",
                      "status",
                      "source",
                      "createdAtLabel",
                    ].forEach((key) => next.delete(key));
                    setSearchParams(next, { replace: true });
                  }}
                  className="rounded-xl border border-[#F2C59F] bg-white px-4 py-2 text-xs font-black text-[#9A5A1C] hover:bg-[#FFF4EA]"
                >
                  Masquer
                </button>
              </div>

              <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
                <div className="rounded-xl border border-[#F4E1CF] bg-white p-3">
                  <div className="text-xs font-bold text-[#8B735D]">Type de demande</div>
                  <div className="mt-1 font-black text-[#0A1628]">{requestContext.type}</div>
                </div>
                <div className="rounded-xl border border-[#F4E1CF] bg-white p-3">
                  <div className="text-xs font-bold text-[#8B735D]">Statut</div>
                  <div className="mt-1 font-black text-[#0A1628]">{requestStatus || requestContext.status}</div>
                </div>
                <div className="rounded-xl border border-[#F4E1CF] bg-white p-3">
                  <div className="text-xs font-bold text-[#8B735D]">Date/heure de transfert</div>
                  <div className="mt-1 font-black text-[#0A1628]">{requestContext.createdAtLabel}</div>
                </div>
                <div className="rounded-xl border border-[#F4E1CF] bg-white p-3">
                  <div className="text-xs font-bold text-[#8B735D]">Source</div>
                  <div className="mt-1 font-black text-[#0A1628]">{requestContext.source}</div>
                </div>
              </div>

              <div className="mt-3 rounded-xl border border-[#F4E1CF] bg-white p-4">
                <div className="text-xs font-bold uppercase tracking-wide text-[#8B735D]">Résumé généré par Clara</div>
                <p className="mt-2 text-sm leading-7 text-[#334155]">{requestContext.summary}</p>
              </div>

              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <button onClick={() => notify("Action: Rappeler le patient")} className="rounded-xl bg-[#009CA4] px-4 py-3 text-sm font-black text-white hover:bg-[#00838A]">Rappeler le patient</button>
                <button onClick={() => notify("Action: Assigner au médecin")} className="rounded-xl border border-[#DDE7F1] bg-white px-4 py-3 text-sm font-black text-[#0A1628] hover:bg-[#F8FAFC]">Assigner au médecin</button>
                <button onClick={() => notify("Action: Planifier un créneau")} className="rounded-xl border border-[#DDE7F1] bg-white px-4 py-3 text-sm font-black text-[#0A1628] hover:bg-[#F8FAFC]">Planifier un créneau</button>
                <button onClick={() => setModal("addNote")} className="rounded-xl border border-[#DDE7F1] bg-white px-4 py-3 text-sm font-black text-[#0A1628] hover:bg-[#F8FAFC]">Ajouter une note</button>
                <button
                  onClick={() => updateRequestStatus("processed")}
                  disabled={!!requestActionLoading || isTerminalLabel(requestStatus || requestContext.status)}
                  className={cx(
                    "rounded-xl border border-[#A7F3D0] bg-[#ECFDF5] px-4 py-3 text-sm font-black text-[#047857] lg:col-span-2",
                    !!requestActionLoading || isTerminalLabel(requestStatus || requestContext.status) ? "cursor-not-allowed opacity-60" : "hover:bg-[#DDFBEF]",
                  )}
                >
                  {requestActionLoading === "processed" ? "Traitement..." : "Marquer comme traitée"}
                </button>
                <button
                  onClick={() => updateRequestStatus("cancelled")}
                  disabled={!!requestActionLoading || isTerminalLabel(requestStatus || requestContext.status)}
                  className={cx(
                    "rounded-xl border border-[#CBD5E1] bg-[#F8FAFC] px-4 py-3 text-sm font-black text-[#475569] lg:col-span-3",
                    !!requestActionLoading || isTerminalLabel(requestStatus || requestContext.status) ? "cursor-not-allowed opacity-60" : "hover:bg-[#F1F5F9]",
                  )}
                >
                  {requestActionLoading === "cancelled" ? "Annulation..." : "Annuler la demande"}
                </button>
              </div>
            </section>
          )}

          {activeView === "overview" && (
            <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[1.25fr_0.85fr]">
              <div className="space-y-6">
                <section className="rounded-[28px] border border-[#E2EAF4] bg-white p-6 shadow-sm">
                  <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                    <h2 className="flex flex-wrap items-center gap-3 text-xl font-black">
                      ▣ Rendez-vous à venir
                      {!patientAgendaLoading && upcomingPatientAppointments.length > 0 ? (
                        <span className="rounded-full bg-[#E8F7F7] px-2.5 py-1 text-xs font-black text-[#008EA1]">
                          {upcomingPatientAppointments.length}
                        </span>
                      ) : null}
                    </h2>
                    <button onClick={() => setModal("history")} className="rounded-xl border border-[#91D9E3] px-4 py-2 text-sm font-black text-[#008EA1] hover:bg-[#E9FAFC]">
                      ◴ Voir l'historique complet
                    </button>
                  </div>

                  {patientAgendaLoading ? (
                    <p className="m-0 text-sm font-semibold text-[#61708B]">Chargement de l’agenda…</p>
                  ) : !tenantPatientPhone ? (
                    <p className="m-0 text-sm font-semibold text-[#61708B]">Sélectionnez un patient pour voir ses prochains rendez-vous.</p>
                  ) : upcomingPatientAppointments.length === 0 ? (
                    <p className="m-0 text-sm font-semibold text-[#61708B]">
                      Aucun rendez-vous à venir pour ce numéro (prochains 60 jours). Les créneaux réservés avec ce téléphone sur l’agenda apparaîtront ici.
                    </p>
                  ) : (
                    <>
                    {(() => {
                      const { slot, start } = upcomingPatientAppointments[0];
                      const parts = frenchAppointmentDateParts(start);
                      const statusLb = patientAgendaRowStatus(slot, start);
                      const tone =
                        statusLb === "Annulé"
                          ? "rounded-lg bg-[#FFF1F1] px-3 py-2 text-sm font-black text-[#B91C1C]"
                          : statusLb === "À confirmer"
                            ? "rounded-lg bg-[#FFF7ED] px-3 py-2 text-sm font-black text-[#C2410C]"
                            : "rounded-lg bg-[#E6FAED] px-3 py-2 text-sm font-black text-[#0BA64B]";
                      return (
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-7">
                    <div className="grid h-24 w-20 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-[#009CA4] to-[#004C69] text-center text-white shadow-[8px_8px_0_rgba(0,156,164,0.12)] sm:h-28 sm:w-24">
                      <div>
                        <div className="text-3xl font-black sm:text-4xl">{parts.day}</div>
                        <div className="mt-1 text-sm sm:text-base">{parts.monthYear}</div>
                        <div className="mt-1 text-sm font-black sm:text-base">{parts.dow}</div>
                      </div>
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="mb-4 flex flex-wrap items-center gap-3 sm:gap-6">
                        <div className="text-3xl font-black sm:text-4xl">{formatAgendaSlotHour(start)} <span className="text-sm font-semibold text-[#64748B] sm:text-base">(20 min)</span></div>
                        <div className="h-8 w-px bg-[#D9E3EF]" />
                        <div className="text-xl font-black">{meTenantName || "Cabinet"}</div>
                        <span className={`rounded-lg px-3 py-2 text-sm font-black ${tone}`}>{statusLb}</span>
                      </div>

                      <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
                        <div><div className="mb-1 text-xs font-bold text-[#7D8CA5]">Motif</div><div className="font-black">{agendaSlotMotif(slot) || "—"}</div></div>
                        <div><div className="mb-1 text-xs font-bold text-[#7D8CA5]">Source</div><div className="font-black">{agendaPatientSourceLabel(slot)}</div></div>
                        <div><div className="mb-1 text-xs font-bold text-[#7D8CA5]">Préférence</div><div className="font-black">—</div></div>
                        <div><div className="mb-1 text-xs font-bold text-[#7D8CA5]">Canal</div><div className="font-black">Téléphone</div></div>
                      </div>

                      <div className="mt-5 flex flex-wrap gap-3">
                        <button type="button" onClick={() => notify("Déplacement du RDV : ouvrir l’agenda")} className="rounded-xl border border-[#72CDE0] px-4 py-2 text-sm font-black text-[#008EA1] hover:bg-[#E9FAFC]">▣ Déplacer le RDV</button>
                        <button type="button" onClick={() => notify("Annulation du RDV : ouvrir l’agenda")} className="rounded-xl border border-[#FF9B9B] px-4 py-2 text-sm font-black text-[#FF3030] hover:bg-[#FFF1F1]">♲ Annuler le RDV</button>
                        <button type="button" onClick={() => navigate("/app/agenda")} className="rounded-xl border border-[#B6C3D7] px-4 py-2 text-sm font-black text-[#53647F] hover:bg-[#F8FAFC]">▣ Voir l&apos;agenda</button>
                      </div>
                    </div>
                  </div>
                      );
                    })()}
                  {upcomingPatientAppointments.length > 1 ? (
                    <div className="mt-6 border-t border-[#E2EAF4] pt-5">
                      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                        <h3 className="text-sm font-black uppercase tracking-wide text-[#475569]">
                          Autres rendez-vous à venir ({upcomingPatientAppointments.length - 1})
                        </h3>
                        <button
                          type="button"
                          onClick={() => setActiveView("appointments")}
                          className="rounded-xl border border-[#91D9E3] px-3 py-1.5 text-xs font-black text-[#008EA1] hover:bg-[#E9FAFC]"
                        >
                          Tous en détail
                        </button>
                      </div>
                      <ul className="m-0 list-none space-y-3 p-0">
                        {upcomingPatientAppointments.slice(1).map(({ slot: sRow, start: dt }) => {
                          const rk = `${String(sRow.event_id || sRow.appointment_id || "")}-${dt.toISOString()}`;
                          const dLabel = dt.toLocaleDateString("fr-FR", {
                            weekday: "short",
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          });
                          const st = patientAgendaRowStatus(sRow, dt);
                          return (
                            <li
                              key={rk}
                              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#EEF3F8] bg-[#F8FBFD] px-4 py-3 text-sm"
                            >
                              <div className="min-w-0 flex-1">
                                <div className="font-black text-[#0A1628]">
                                  {formatAgendaSlotHour(dt)} · {dLabel.replace(/\.$/, ".")}
                                </div>
                                <div className="mt-1 font-semibold text-[#475569]">{agendaSlotMotif(sRow) || "Consultation"}</div>
                              </div>
                              <span className="rounded-lg bg-white px-3 py-1.5 text-xs font-black text-[#007E8C]">{st}</span>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ) : null}
                  </>
                  )}
                </section>

                <section className="rounded-[28px] bg-gradient-to-br from-[#062E53] via-[#023E63] to-[#007B88] p-6 text-white shadow-[0_20px_45px_rgba(0,66,90,0.22)]">
                  <h2 className="mb-5 text-2xl font-black">☆ Contexte patient</h2>
                  <div className="grid grid-cols-2 gap-6">
                    <div>
                      <div className="mb-4 flex items-center justify-between">
                        <div className="text-sm font-black uppercase tracking-wide text-[#11D6DB]">● Résumé Clara</div>
                        <div className="text-sm italic text-white/60">Généré par IA</div>
                      </div>

                      <p className="text-[17px] leading-8 text-white/95">
                        {displayHero.name} contacte principalement le cabinet par téléphone. Les notes et documents ci-dessous sont
                        synchronisés avec votre espace cabinet lorsque le numéro ou la fiche correspondent en base.
                      </p>

                      <p className="mt-5 text-sm italic text-white/65">Mis à jour · Aujourd'hui à 14:32</p>
                    </div>

                    <div className="border-l border-white/25 pl-6">
                      <h3 className="mb-4 text-xl font-black text-white">✎ Notes de l'équipe</h3>

                      <div className="space-y-4">
                        {notesLoading ? (
                          <div className="text-sm text-white/70">Chargement des notes...</div>
                        ) : patientNotes.length === 0 ? (
                          <div className="text-sm text-white/70">Aucune note pour ce patient.</div>
                        ) : (
                          patientNotes.slice(0, 4).map((item) => (
                            <div key={item.id} className="border-b border-white/20 pb-4">
                              <div className="text-base font-semibold">♡ {item.text}</div>
                              <div className="mt-1 flex items-center justify-between text-sm text-white/60">
                                <span>{item.author} · {new Date(item.created_at).toLocaleDateString("fr-FR")}</span>
                                <button
                                  type="button"
                                  onClick={() => removeNote(item.id)}
                                  disabled={noteDeletingId === item.id}
                                  className="rounded border border-white/25 px-2 py-0.5 text-xs font-bold text-white/80 hover:bg-white/10 disabled:opacity-50"
                                >
                                  {noteDeletingId === item.id ? "..." : "Supprimer"}
                                </button>
                              </div>
                            </div>
                          ))
                        )}
                      </div>

                      <textarea
                        value={note}
                        onChange={(event) => setNote(event.target.value)}
                        placeholder="Ajouter une note..."
                        className="mt-4 h-16 w-full resize-none rounded-xl border border-white/20 bg-white px-4 py-3 text-[#0A1628] outline-none focus:ring-4 focus:ring-[#00C4CC]/25"
                      />
                      <button onClick={saveNote} disabled={notesSaving} className="mt-3 rounded-xl bg-[#00A5AE] px-7 py-3 text-sm font-black text-white shadow-lg hover:bg-[#00949C] disabled:opacity-60">
                        {notesSaving ? "Enregistrement..." : "Enregistrer"}
                      </button>
                    </div>
                  </div>
                </section>
              </div>

              <aside className="space-y-6">
                <section className="rounded-[28px] border border-[#E2EAF4] bg-white p-7 shadow-sm">
                  <div className="mb-5 flex items-center justify-between">
                    <h2 className="text-2xl font-black"><span className="text-[#FF8A00]">ϟ</span> À traiter <span className="ml-2 rounded-full bg-[#FFF1E8] px-2 py-1 text-sm text-[#FF6B00]">2</span></h2>
                    <button onClick={() => notify("Actions à traiter ouvertes")} className="text-sm font-black text-[#008EA1]">Voir tout ›</button>
                  </div>

                  <div className="space-y-4">
                    <button onClick={() => notify("Rappel automatique à confirmer")} className="flex w-full items-center gap-4 rounded-2xl border border-[#EEF3F8] p-4 text-left hover:bg-[#F8FBFD]">
                      <div className="grid h-12 w-12 place-items-center rounded-xl bg-[#FFF5F5] text-xl">🗓</div>
                      <div className="flex-1"><div className="font-black">Confirmer rappel automatique</div><div className="mt-1 text-sm text-[#61708B]">Échéance : 17/05/2026</div></div>
                      <span className="rounded-lg bg-[#FFF1EA] px-3 py-2 text-xs font-black text-[#FF4B3E]">À faire</span>
                    </button>

                    <button onClick={() => notify("Document demandé ouvert")} className="flex w-full items-center gap-4 rounded-2xl border border-[#EEF3F8] p-4 text-left hover:bg-[#F8FBFD]">
                      <div className="grid h-12 w-12 place-items-center rounded-xl bg-[#F1F5FF] text-xl">🔒</div>
                      <div className="flex-1"><div className="font-black">Document demandé</div><div className="mt-1 text-sm text-[#61708B]">Échéance : 18/05/2026</div></div>
                      <span className="rounded-lg bg-[#FFF2E3] px-3 py-2 text-xs font-black text-[#EF6C00]">En attente</span>
                    </button>
                  </div>
                </section>
              </aside>
            </div>
          )}

          {activeView === "appointments" && (
            <section className="mt-6 rounded-[28px] border border-[#E2EAF4] bg-white p-4 shadow-sm sm:p-6 lg:p-8">
              <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-black">Rendez-vous du patient</h2>
                  {tenantPatientPhone && !patientAgendaLoading ? (
                    <p className="mt-2 text-sm font-bold text-[#008EA1]">
                      {upcomingPatientAppointments.length} rendez-vous à venir (fenêtre 60 jours)
                    </p>
                  ) : null}
                </div>
                <button
                  type="button"
                  onClick={() => setActiveView("overview")}
                  className="rounded-xl border border-[#B6C3D7] px-4 py-2 text-sm font-black text-[#53647F] hover:bg-[#F8FAFC]"
                >
                  ◂ Retour vue d’ensemble
                </button>
              </div>
              <p className="mb-4 text-sm font-semibold text-[#61708B]">
                Liste de tous les créneaux à venir rattachés au numéro de ce patient dans l&apos;agenda du cabinet.
              </p>
              {!tenantPatientPhone ? (
                <p className="text-sm font-semibold text-[#61708B]">Sélectionnez un patient.</p>
              ) : patientAgendaLoading ? (
                <p className="text-sm font-semibold text-[#61708B]">Chargement…</p>
              ) : upcomingPatientAppointments.length === 0 ? (
                <p className="text-sm font-semibold text-[#61708B]">
                  Aucun rendez-vous à venir avec ce téléphone. Vérifiez que chaque RDV comporte bien le numéro en contact dans l&apos;agenda ou Google&nbsp;Calendar.
                </p>
              ) : (
              <div className="space-y-3 sm:space-y-4">
                {upcomingPatientAppointments.map(({ slot, start }) => {
                  const rowKey = `${String(slot.event_id || slot.appointment_id || "")}-${start.toISOString()}`;
                  const dateStr = start.toLocaleDateString("fr-FR", {
                    day: "2-digit",
                    month: "2-digit",
                    year: "numeric",
                  });
                  return (
                  <div key={rowKey} className="grid grid-cols-2 gap-2 rounded-2xl border border-[#EEF3F8] p-4 text-sm sm:grid-cols-[120px_90px_1fr_160px] sm:items-center sm:gap-3">
                    <b className="col-span-1">{dateStr}</b>
                    <b className="col-span-1">{formatAgendaSlotHour(start)}</b>
                    <span className="col-span-2 sm:col-span-1">{agendaSlotMotif(slot) || "Consultation"}</span>
                    <span className="col-span-2 rounded-lg bg-[#F2F8FA] px-3 py-2 text-center font-black text-[#007E8C] sm:col-span-1">{patientAgendaRowStatus(slot, start)}</span>
                  </div>
                  );
                })}
              </div>
              )}
            </section>
          )}

          {activeView === "history" && (
            <section className="mt-6 rounded-[28px] border border-[#E2EAF4] bg-white p-4 shadow-sm sm:p-6 lg:p-8">
              <h2 className="mb-5 text-2xl font-black">Historique des interactions</h2>
              <HistoryList />
            </section>
          )}
        </main>
      </div>

      {modal === "profile" && (
        <Modal title="Profil patient" onClose={() => setModal(null)} width="max-w-2xl">
          {tenantPatientNotFound ? (
            <p className="m-0 text-sm leading-7 text-[#475569]">
              Créez d&apos;abord la fiche avec le formulaire en haut de page (nom puis « Créer la fiche »), puis vous pourrez modifier les détails ici.
            </p>
          ) : urlPatientHero ? (
            <>
              <div className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-2">
                <label className="sm:col-span-2 rounded-2xl bg-[#F8FBFD] p-4">
                  <div className="mb-1 text-xs font-bold text-[#7D8CA5]">Nom affiché</div>
                  <input
                    value={profileNameDraft}
                    onChange={(e) => setProfileNameDraft(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-[#DDE7F1] bg-white px-3 py-2 font-black text-[#0A1628] outline-none focus:border-[#009CA4]"
                  />
                </label>
                <div className="rounded-2xl bg-[#F8FBFD] p-4">
                  <div className="mb-1 text-xs font-bold text-[#7D8CA5]">Téléphone</div>
                  <div className="font-black">{formatDisplayFrenchPhone(normalizePhone(urlPatientHero.phone))}</div>
                </div>
                <div className="rounded-2xl bg-[#F8FBFD] p-4">
                  <div className="mb-1 text-xs font-bold text-[#7D8CA5]">Fiche créée</div>
                  <div className="font-black">{formatCabinetMetaDate(patientCabinetRow?.created_at)}</div>
                </div>
                <div className="rounded-2xl bg-[#F8FBFD] p-4">
                  <div className="mb-1 text-xs font-bold text-[#7D8CA5]">Dernière mise à jour</div>
                  <div className="font-black">{formatCabinetMetaDate(patientCabinetRow?.updated_at)}</div>
                </div>
              </div>
              <div className="mt-6 flex gap-3">
                <button
                  type="button"
                  disabled={profileSaveSaving}
                  onClick={() => void saveProfileFromModal()}
                  className="flex-1 rounded-xl bg-[#009CA4] px-4 py-3 font-black text-white hover:bg-[#00838A] disabled:opacity-60"
                >
                  {profileSaveSaving ? "Enregistrement…" : "Enregistrer le nom"}
                </button>
                <button
                  type="button"
                  onClick={() => void openDeletePatientModal()}
                  className="flex-1 rounded-xl border border-red-300 px-4 py-3 font-black text-red-600"
                >
                  Supprimer
                </button>
              </div>
            </>
          ) : (
            <p className="m-0 text-sm font-semibold text-[#61708B]">Chargement du profil…</p>
          )}
        </Modal>
      )}

      {modal === "addNote" && (
        <Modal title="Ajouter une note" onClose={() => setModal(null)} width="max-w-xl">
          <textarea
            autoFocus
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Ex. Préfère les rendez-vous le matin, ne pas appeler après 18h..."
            className="h-40 w-full resize-none rounded-2xl border border-[#DDE7F1] p-4 outline-none focus:border-[#009CA4] focus:ring-4 focus:ring-[#009CA4]/10"
          />
          <button
            onClick={async () => {
              const ok = await saveNote();
              if (ok) setModal(null);
            }}
            disabled={notesSaving}
            className="mt-4 w-full rounded-xl bg-[#009CA4] px-4 py-3 font-black text-white disabled:opacity-60"
          >
            {notesSaving ? "Enregistrement..." : "Enregistrer la note"}
          </button>
        </Modal>
      )}

      {modal === "addDocument" && (
        <Modal title="Ajouter un document" onClose={() => setModal(null)} width="max-w-xl">
          <div className="rounded-3xl border-2 border-dashed border-[#BFE6EC] bg-[#F7FCFD] p-8 text-center">
            <div className="mb-3 text-4xl">▤</div>
            <div className="text-lg font-black">Déposer un document</div>
            <p className="mt-2 text-sm text-[#61708B]">Justificatif, courrier ou document administratif lié à la demande.</p>
            <label className="mt-5 inline-flex cursor-pointer rounded-xl border border-[#009CA4] bg-white px-5 py-3 font-black text-[#008EA1]">
              {documentsUploading ? "Envoi..." : "Choisir un fichier"}
              <input
                type="file"
                disabled={documentsUploading}
                accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,.xls,.xlsx,.txt"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  uploadDocument(file);
                  event.target.value = "";
                }}
                className="hidden"
              />
            </label>
          </div>

          <div className="mt-5">
            <h4 className="mb-2 text-sm font-black text-[#334155]">Documents patient</h4>
            {documentsLoading ? (
              <div className="rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] px-4 py-3 text-sm text-[#64748B]">Chargement...</div>
            ) : documents.length === 0 ? (
              <div className="rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] px-4 py-3 text-sm text-[#64748B]">Aucun document pour ce patient.</div>
            ) : (
              <div className="max-h-64 space-y-2 overflow-auto pr-1">
                {documents.map((doc) => {
                  const canPreview = doc.mime_type.includes("pdf") || doc.mime_type.startsWith("image/");
                  return (
                    <div key={doc.id} className="flex items-center justify-between gap-3 rounded-xl border border-[#E2E8F0] bg-white px-3 py-2">
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-bold text-[#0A1628]">{doc.original_name}</div>
                        <div className="text-xs text-[#64748B]">{formatBytes(doc.size_bytes)} · {doc.created_at ? new Date(doc.created_at).toLocaleDateString("fr-FR") : "maintenant"}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        {canPreview ? (
                          <button type="button" onClick={() => openPreview(doc)} className="rounded-lg border border-[#DDE7F1] px-2 py-1 text-xs font-black text-[#0A1628] hover:bg-[#F8FAFC]">Voir</button>
                        ) : null}
                        <button type="button" onClick={() => downloadDocument(doc)} className="rounded-lg border border-[#DDE7F1] px-2 py-1 text-xs font-black text-[#0A1628] hover:bg-[#F8FAFC]">Télécharger</button>
                        <button
                          type="button"
                          onClick={() => sendDocument(doc.id)}
                          disabled={documentSendingId === doc.id || !patientEmail}
                          className="rounded-lg border border-[#86EFAC] px-2 py-1 text-xs font-black text-[#15803D] hover:bg-[#F0FDF4] disabled:opacity-50"
                          title={patientEmail ? `Envoyer à ${patientEmail}` : "Ajoute un email patient"}
                        >
                          {documentSendingId === doc.id ? "..." : "Envoyer"}
                        </button>
                        <button
                          type="button"
                          onClick={() => deleteDocument(doc.id)}
                          disabled={documentDeletingId === doc.id}
                          className="rounded-lg border border-[#FCA5A5] px-2 py-1 text-xs font-black text-[#B91C1C] hover:bg-[#FEF2F2] disabled:opacity-50"
                        >
                          {documentDeletingId === doc.id ? "..." : "Supprimer"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </Modal>
      )}

      {modal === "history" && (
        <Modal title="Historique complet" onClose={() => setModal(null)} width="max-w-4xl">
          <HistoryList extended />
        </Modal>
      )}

      {modal === "deletePatient" && (
        <Modal title="Supprimer la fiche patient" onClose={() => setModal(null)} width="max-w-2xl">
          {deletePreviewLoading ? (
            <p className="text-sm font-semibold text-[#61708B]">Préparation de la suppression…</p>
          ) : !deletePreview ? (
            <p className="text-sm font-semibold text-[#61708B]">Impossible de charger le récapitulatif de suppression.</p>
          ) : (
            <div className="space-y-4">
              <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">
                <p className="m-0 font-black">Action irréversible.</p>
                <p className="mt-2 mb-0">
                  Cette opération supprime définitivement la fiche patient, ses notes et ses documents associés.
                </p>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="rounded-2xl bg-[#F8FBFD] p-4">
                  <div className="text-xs font-bold text-[#7D8CA5]">Patient</div>
                  <div className="mt-1 font-black">{deletePreview.summary.display_name}</div>
                </div>
                <div className="rounded-2xl bg-[#F8FBFD] p-4">
                  <div className="text-xs font-bold text-[#7D8CA5]">Téléphone</div>
                  <div className="mt-1 font-black">{formatDisplayFrenchPhone(deletePreview.summary.phone)}</div>
                </div>
                <div className="rounded-2xl bg-[#F8FBFD] p-4">
                  <div className="text-xs font-bold text-[#7D8CA5]">Notes supprimées</div>
                  <div className="mt-1 font-black">{deletePreview.summary.notes_count}</div>
                </div>
                <div className="rounded-2xl bg-[#F8FBFD] p-4">
                  <div className="text-xs font-bold text-[#7D8CA5]">Documents supprimés</div>
                  <div className="mt-1 font-black">{deletePreview.summary.documents_count}</div>
                </div>
              </div>
              <label className="block text-sm font-semibold text-[#334155]">
                Tapez <span className="font-black">SUPPRIMER</span> pour confirmer :
                <input
                  value={deleteConfirmText}
                  onChange={(e) => setDeleteConfirmText(e.target.value)}
                  className="mt-2 w-full rounded-xl border border-[#DDE7F1] bg-white px-3 py-2 font-black text-[#0A1628] outline-none focus:border-[#EF4444]"
                  placeholder="SUPPRIMER"
                />
              </label>
              <div className="mt-2 flex gap-3">
                <button
                  type="button"
                  onClick={() => setModal(null)}
                  className="flex-1 rounded-xl border border-[#DDE7F1] px-4 py-3 font-black text-[#334155]"
                >
                  Annuler
                </button>
                <button
                  type="button"
                  disabled={deleteSaving || deleteConfirmText.trim().toUpperCase() !== "SUPPRIMER"}
                  onClick={() => void confirmDeletePatient()}
                  className="flex-1 rounded-xl bg-red-600 px-4 py-3 font-black text-white disabled:opacity-60"
                >
                  {deleteSaving ? "Suppression…" : "Confirmer la suppression définitive"}
                </button>
              </div>
            </div>
          )}
        </Modal>
      )}

      {previewDoc && previewUrl && (
        <Modal title={previewDoc.original_name} onClose={closePreview} width="max-w-4xl">
          <div className="mb-3 flex justify-end">
            <button
              type="button"
              onClick={() => sendDocument(previewDoc.id)}
              disabled={documentSendingId === previewDoc.id || !patientEmail}
              className="rounded-lg border border-[#86EFAC] px-3 py-1.5 text-xs font-black text-[#15803D] hover:bg-[#F0FDF4] disabled:opacity-50"
            >
              {documentSendingId === previewDoc.id ? "Envoi..." : "Envoyer par email"}
            </button>
          </div>
          {previewDoc.mime_type.includes("pdf") ? (
            <iframe src={previewUrl} title={previewDoc.original_name} className="h-[70vh] w-full rounded-xl border border-[#E2E8F0]" />
          ) : previewDoc.mime_type.startsWith("image/") ? (
            <img src={previewUrl} alt={previewDoc.original_name} className="max-h-[70vh] w-full rounded-xl border border-[#E2E8F0] object-contain" />
          ) : (
            <div className="rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] px-4 py-3 text-sm text-[#64748B]">
              Aperçu indisponible pour ce type de fichier.
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}

function HistoryList({ extended = false }: { extended?: boolean }) {
  const rows: Array<[string, string, string, string, string, "green" | "orange"]> = [
    ["17/05/2026", "09:36", "Appel sortant", "Rappel de rendez-vous pour le 21 mai 2026 à 10:30.", "Traité automatiquement", "green"],
    ["15/05/2026", "14:22", "SMS sortant", "Rappel automatique de rendez-vous.", "Traité automatiquement", "green"],
    ["12/05/2026", "08:47", "Appel entrant", "Demande de report au 26/05 à 09:30.", "Action humaine requise", "orange"],
    ["10/05/2026", "11:05", "Document reçu", "Justificatif d'assurance ajouté au dossier.", "Traité automatiquement", "green"],
  ];

  return (
    <div className="space-y-0 overflow-hidden rounded-2xl border border-[#EEF3F8] bg-white">
      {rows.slice(0, extended ? rows.length : 3).map(([date, hour, type, result, status, tone]) => (
        <div
          key={`${date}-${hour}`}
          className="grid grid-cols-[16px_1fr] gap-2 border-b border-[#EEF3F8] p-4 last:border-b-0 sm:grid-cols-[16px_110px_150px_1fr_180px] sm:items-center sm:gap-4"
        >
          <span className={cx("h-3 w-3 rounded-full", tone === "green" ? "bg-[#18C765]" : "bg-[#FF9E18]")} />
          <div className="text-sm text-[#61708B] sm:col-span-1"><b>{date}</b><br />{hour}</div>
          <div className="col-span-2 -mt-1 font-black sm:col-span-1 sm:mt-0">{type}</div>
          <div className="col-span-2 text-sm text-[#53647F] sm:col-span-1">{result}</div>
          <span className={cx("col-span-2 rounded-lg px-3 py-2 text-center text-xs font-black sm:col-span-1", tone === "green" ? "bg-[#E8FAF0] text-[#0B9445]" : "bg-[#FFF1DE] text-[#D96B00]")}>{status}</span>
        </div>
      ))}
    </div>
  );
}
