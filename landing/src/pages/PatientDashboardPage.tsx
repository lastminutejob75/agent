import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { agendaSlotMotif, formatAgendaSlotHour, parseAgendaSlotStart } from "../lib/agendaSlotParse.js";
import { api } from "../lib/api.js";
import { buildTenantRequestRows, filterOpenPatientRequests } from "../lib/requestUiStatus.js";
import { buildAbsenceNoteText, normalizePatientInsightTags } from "../lib/patientInsightTags.js";
import {
  agendaOriginLabel,
  agendaSlotDurationMinutes,
  contactTypeLabel,
  timePreferenceLabel,
} from "../lib/agendaPatientMeta.js";
import {
  appointmentActionId,
  appointmentLocalId,
  agendaCancelPayload,
  agendaReschedulePayload,
  buildAgendaViewUrl,
  canCancelAgendaSlot,
  canOpenReschedulePatientAppt,
  canRescheduleAgendaSlot,
  isAgendaSlotPast,
} from "../lib/agendaAppointmentActions.js";
import AgendaReschedulePanel from "../components/agenda/AgendaReschedulePanel.jsx";
import CreateCabinetBookingModal from "../components/agenda/CreateCabinetBookingModal.jsx";
import CreatePatientFromCallModal from "../components/calls/CreatePatientFromCallModal.jsx";
import { buildCabinetBookingStartIso, formatLongDateFR, formatTimeChoiceFR } from "../lib/cabinetBooking.js";
import PatientDashboardMobile from "./PatientDashboardMobile";
import { normalizePhoneBusinessKey } from "../lib/phoneNormalize";
import { validatePatientPhone, validateContactEmail, isValidContactEmail } from "../lib/contactValidation.js";
import { patientDashboardFileHasValidatedIdentity } from "../lib/callsService.js";
import {
  formatBirthDateWithAge,
  formatPhysicianWithCity,
} from "../lib/patientProfileMeta.js";
import PatientDuplicateBanner from "../components/patients/PatientDuplicateBanner.jsx";
import PatientQuestionnaireCard from "../components/patients/PatientQuestionnaireCard.jsx";
import PatientAdminQuestionnaireCard from "../components/patients/PatientAdminQuestionnaireCard.jsx";
import PatientMedicalQuestionnaireCard from "../components/patients/PatientMedicalQuestionnaireCard.jsx";
import PatientContextSummary from "../components/patients/PatientContextSummary.jsx";
import FicheConsultationUWI from "../components/consultations/FicheConsultationUWI.jsx";
import {
  checkPatientDuplicates,
  formatPatientDuplicateConflict,
  hasBlockingPatientDuplicate,
  parsePatientDuplicateError,
} from "../lib/patientDuplicateCheck.js";
import {
  fetchTenantCallbacksCached,
  fetchTenantHandoffsCached,
  fetchTenantRequestsBundleCached,
} from "../lib/tenantRequestsCache.js";
import {
  fetchTenantPatientsListCached,
  getCachedTenantPatientsList,
  invalidateTenantPatientsListCache,
} from "../lib/patientsListCache.js";
import {
  computePatientCreateFieldErrors,
  isPatientCreateSubmitBlocked,
  usePatientCreateDuplicateCheck,
  validatePatientCreateFormForSubmit,
} from "../lib/patientCreateForm.js";

const TENANT_PATIENTS_LIST_QUERY = "?limit=80&compact=1";

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

function mapPatientPastAppointments(raw: unknown): Array<{ start: Date; key: string }> {
  if (!Array.isArray(raw)) return [];
  const out: Array<{ start: Date; key: string }> = [];
  for (const row of raw) {
    const iso = String((row as { start_iso?: string })?.start_iso || "").trim();
    if (!iso) continue;
    const start = new Date(iso);
    if (Number.isNaN(start.getTime())) continue;
    out.push({ start, key: iso });
  }
  return out;
}

function formatCabinetMetaDate(value: unknown) {
  const raw = String(value || "").trim();
  if (!raw) return "—";
  const d = new Date(raw.includes("T") ? raw.replace(" ", "T") : raw);
  return Number.isNaN(d.getTime()) ? raw.slice(0, 10) || "—" : d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function formatBirthDateDisplay(value: unknown) {
  const raw = String(value || "").trim().slice(0, 10);
  if (!raw) return "Non renseignée";
  const d = new Date(`${raw}T12:00:00`);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
}

function computeAgeFromBirthDate(value: unknown): number | null {
  const raw = String(value || "").trim().slice(0, 10);
  if (!raw) return null;
  const birth = new Date(`${raw}T12:00:00`);
  if (Number.isNaN(birth.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - birth.getFullYear();
  const monthDelta = now.getMonth() - birth.getMonth();
  if (monthDelta < 0 || (monthDelta === 0 && now.getDate() < birth.getDate())) age -= 1;
  return age >= 0 ? age : null;
}

function parseOptionalIntInput(value: string): number | undefined {
  const raw = String(value || "").trim().replace(",", ".");
  if (!raw) return undefined;
  const num = Number(raw);
  if (!Number.isFinite(num)) return undefined;
  return Math.round(num);
}

function parseOptionalFloatInput(value: string): number | undefined {
  const raw = String(value || "").trim().replace(",", ".");
  if (!raw) return undefined;
  const num = Number(raw);
  if (!Number.isFinite(num)) return undefined;
  return num;
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

type ModalType =
  | "createPatientManual"
  | "createConsultation"
  | "profile"
  | "addNote"
  | "addDocument"
  | "history"
  | "deletePatient"
  | "cancelAppt"
  | "rescheduleAppt"
  | "sendSingleMessage"
  | "sendBulkMessage"
  | null;
type ApptActionTarget = { slot: Record<string, unknown>; start: Date };
type PatientBookingConfirm = {
  patientName: string;
  bookingDate: string;
  bookingTime: string;
  motif: string;
};
type ViewType = "overview" | "appointments" | "history" | "documents";
type MessageChannel = "sms" | "email";
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

type ConsultationOpenDraft = {
  consultationId?: string;
  appointmentId: string;
  date: string;
  motif: string;
  sourceConsultationId?: string;
  prefill?: {
    mode_consultation?: "rapide" | "complete";
    anamnese?: string;
    etat_general?: string;
    examen_physique?: string;
    constantes?: Record<string, unknown>;
    impression_clinique?: string;
    cim10?: string;
    examens_complementaires?: string[];
    prescription?: string;
    orientation?: string;
    suivi_consignes?: string;
    ia_resume?: string;
    ia_contexte_patient?: string;
    note_praticien?: string;
  };
};

type PatientInsightTag = { key: string; label: string; tone: "blue" | "red" };

type PatientHistoryItem = {
  id: string;
  date_label: string;
  time_label: string;
  type_label: string;
  summary: string;
  status_label: string;
  tone: "green" | "orange" | "red";
};

type PatientConsultationRow = {
  id: string;
  consultationId: number;
  dateLabel: string;
  motif: string;
  impression: string;
  prochainRdv: string;
  source: Record<string, unknown>;
};

function mapPatientConsultationRow(row: unknown): PatientConsultationRow | null {
  if (!row || typeof row !== "object") return null;
  const consultationId = Number((row as { id?: unknown })?.id);
  if (!Number.isFinite(consultationId) || consultationId <= 0) return null;
  const id = String(consultationId);
  const dateRaw = String((row as { date_consultation?: unknown })?.date_consultation || "").trim().slice(0, 10);
  const dateLabel = formatCabinetMetaDate(dateRaw);
  const motifRaw = String((row as { motif?: unknown })?.motif || "").trim();
  const impressionRaw = String((row as { impression_clinique?: unknown })?.impression_clinique || "").trim();
  const suiviRaw = String((row as { suivi_prochain_rdv?: unknown })?.suivi_prochain_rdv || "").trim().slice(0, 10);
  return {
    id,
    consultationId,
    dateLabel,
    motif: motifRaw || "Consultation",
    impression: impressionRaw,
    prochainRdv: suiviRaw ? formatCabinetMetaDate(suiviRaw) : "",
    source: row as Record<string, unknown>,
  };
}

function buildConsultationPrefillFromSource(source: Record<string, unknown>) {
  const vitals = source.vitals && typeof source.vitals === "object"
    ? (source.vitals as Record<string, unknown>)
    : {};
  const examens = Array.isArray(source.examens_demandes)
    ? source.examens_demandes
        .map((item) => String(item || "").trim())
        .filter(Boolean)
    : [];
  return {
    mode_consultation: source.mode_consultation === "complete" ? "complete" : "rapide",
    anamnese: String(source.anamnese || ""),
    etat_general: String(source.etat_general || ""),
    examen_physique: String(source.examen_physique || ""),
    constantes: vitals,
    impression_clinique: String(source.impression_clinique || ""),
    cim10: String(source.cim10 || ""),
    examens_complementaires: examens,
    prescription: String(source.prescription || ""),
    orientation: String(source.orientation || ""),
    suivi_consignes: String(source.suivi_consignes || ""),
    ia_resume: String(source.ia_resume || ""),
    ia_contexte_patient: String(source.ia_contexte_patient || ""),
    note_praticien: String(source.note_praticien || ""),
  };
}

function mapPatientHistoryItems(raw: unknown): PatientHistoryItem[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((row) => {
      const toneRaw = String((row as { tone?: string })?.tone || "green");
      const tone: PatientHistoryItem["tone"] =
        toneRaw === "orange" ? "orange" : toneRaw === "red" ? "red" : "green";
      return {
        id: String((row as { id?: string })?.id || ""),
        date_label: String((row as { date_label?: string })?.date_label || "—"),
        time_label: String((row as { time_label?: string })?.time_label || "—"),
        type_label: String((row as { type_label?: string })?.type_label || "Événement"),
        summary: String((row as { summary?: string })?.summary || ""),
        status_label: String((row as { status_label?: string })?.status_label || "—"),
        tone,
      };
    })
    .filter((item) => item.id);
}

const SIDEBAR_GRADIENTS = [
  "from-[#008EA1] to-[#004866]",
  "from-[#00A686] to-[#007C73]",
  "from-[#7256F4] to-[#5338C9]",
  "from-[#0BA37F] to-[#007B64]",
  "from-[#FF9A2E] to-[#F36F21]",
  "from-[#009CA4] to-[#006E78]",
  "from-[#8068E8] to-[#5942C9]",
];

const CONSULTATION_DRAFT_EMPTY: ConsultationOpenDraft = {
  consultationId: "",
  appointmentId: "",
  date: new Date().toISOString().slice(0, 10),
  motif: "Consultation",
  sourceConsultationId: "",
  prefill: undefined,
};

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
  const normalized = normalizePhone(String(raw || "").trim());
  if (!normalized) return "—";
  if (normalized.startsWith("+33") && normalized.length === 12) {
    const local = `0${normalized.slice(3)}`;
    return `${local.slice(0, 2)} ${local.slice(2, 4)} ${local.slice(4, 6)} ${local.slice(6, 8)} ${local.slice(8, 10)}`;
  }
  const digits = normalized.replace(/\D/g, "");
  if (digits.length >= 10) {
    const local = digits.slice(-10);
    return `${local.slice(0, 2)} ${local.slice(2, 4)} ${local.slice(4, 6)} ${local.slice(6, 8)} ${local.slice(8, 10)}`;
  }
  return String(raw || "").trim() || "—";
}

function patientStatusMeta(bucket: "new" | "active" | "inactive") {
  if (bucket === "new") {
    return { label: "Nouveau", dot: "#2563EB", bg: "#EFF6FF", text: "#1D4ED8" };
  }
  if (bucket === "inactive") {
    return { label: "Inactif", dot: "#94A3B8", bg: "#F1F5F9", text: "#64748B" };
  }
  return { label: "Actif", dot: "#0BA64B", bg: "#E6FAED", text: "#0BA64B" };
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

const PATIENT_DETAIL_CACHE_MS = 90000;

type PatientDetailBundle = {
  patientCabinetRow: Record<string, unknown> | null;
  urlPatientHero: { name: string; phone: string; initials: string } | null;
  patientEmail: string;
  documents: PatientDocument[];
  patientNotes: PatientNote[];
  patientInsightTags: PatientInsightTag[];
  patientPastAppointments: Array<{ start: Date; key: string }>;
  tenantPatientNotFound: boolean;
};

function emptyPatientDetailBundle(
  overrides: Partial<PatientDetailBundle> = {},
): PatientDetailBundle {
  return {
    tenantPatientNotFound: false,
    patientCabinetRow: null,
    urlPatientHero: null,
    patientEmail: "",
    documents: [],
    patientNotes: [],
    patientInsightTags: [],
    patientPastAppointments: [],
    ...overrides,
  };
}

function isPatientDetailCacheValid(
  cached:
    | {
        nonce: number;
        ts: number;
        hasNotes: boolean;
      }
    | undefined,
  patientFetchNonce: number,
  activeView: ViewType,
) {
  return Boolean(
    cached
      && cached.nonce === patientFetchNonce
      && Date.now() - cached.ts < PATIENT_DETAIL_CACHE_MS
      && (activeView !== "overview" || cached.hasNotes),
  );
}

function mapPatientDocuments(list: unknown[]) {
  return list.map((item: any) => ({
    id: Number(item.id),
    original_name: String(item.original_name || ""),
    mime_type: String(item.mime_type || ""),
    size_bytes: Number(item.size_bytes || 0),
    created_at: String(item.created_at || ""),
  }));
}

function mapPatientNotes(items: unknown[]) {
  return items.map((item: any) => ({
    id: Number(item.id),
    text: String(item.text || ""),
    author: String(item.author || "Cabinet"),
    created_at: String(item.created_at || ""),
  }));
}

const PATIENT_NOTE_PREVIEW_LIMIT = 180;

function previewPatientNoteText(text: string) {
  const raw = String(text || "");
  if (raw.length <= PATIENT_NOTE_PREVIEW_LIMIT) return raw;
  return `${raw.slice(0, PATIENT_NOTE_PREVIEW_LIMIT).trimEnd()}...`;
}

function buildPatientHeroFromProfile(p: Record<string, unknown> | undefined, fallbackPhone: string) {
  if (!p) return null;
  const name = String(p.display_name || p.validated_name || p.raw_name || "Patient").trim() || "Patient";
  const tel = String(p.phone || fallbackPhone).trim();
  return { name, phone: tel, initials: initialsFromFullName(name) };
}

const viewTabs: Array<{ id: ViewType; label: string; shortLabel: string }> = [
  { id: "overview", label: "Vue d'ensemble", shortLabel: "Aperçu" },
  { id: "appointments", label: "Rendez-vous", shortLabel: "RDV" },
  { id: "documents", label: "Documents", shortLabel: "Docs" },
  { id: "history", label: "Historique", shortLabel: "Historique" },
];

const REQUEST_STATUS_OVERRIDES_KEY = "uwi_request_status_overrides";

function readRequestStatusOverrides() {
  if (typeof window === "undefined") return {};
  try {
    const parsed = JSON.parse(window.localStorage.getItem(REQUEST_STATUS_OVERRIDES_KEY) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function requestTypeIcon(typeKey: string) {
  if (typeKey === "document") return "🔒";
  if (typeKey === "renewal") return "💊";
  if (typeKey === "transfer") return "✉";
  if (typeKey === "question") return "❓";
  return "🗓";
}

function requestStatusBadge(status: string) {
  if (status === "En cours") {
    return { label: "En attente", bg: "#FFF2E3", color: "#EF6C00" };
  }
  return { label: "À faire", bg: "#FFF1EA", color: "#FF4B3E" };
}

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

type ManualPatientCreateForm = {
  firstName: string;
  lastName: string;
  phone: string;
  email: string;
  birthDate: string;
  treatingPhysicianName: string;
  treatingPhysicianCity: string;
  initialNote: string;
  agendaMotif: string;
  rawCalendarName: string;
  callId: string;
};

const MANUAL_PATIENT_CREATE_EMPTY: ManualPatientCreateForm = {
  firstName: "",
  lastName: "",
  phone: "",
  email: "",
  birthDate: "",
  treatingPhysicianName: "",
  treatingPhysicianCity: "",
  initialNote: "",
  agendaMotif: "",
  rawCalendarName: "",
  callId: "",
};

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

/** Libellé de statut pour liste / vignette RDV patient */
function patientAgendaRowStatus(slot: Record<string, unknown>, start: Date): string {
  const joined = `${slot.booking_status || ""} ${slot.status || ""}`.toLowerCase();
  if (joined.includes("cancel") || joined.includes("annul")) return "Annulé";
  if (start.getTime() >= Date.now()) {
    if (joined.includes("pending")) return "À confirmer";
    if (joined.includes("confirm")) return "Confirmé";
    return "Confirmé";
  }
  return "Passé";
}

function formatBytes(value: number) {
  const size = Number(value || 0);
  if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} Mo`;
  return `${Math.max(1, Math.round(size / 1024))} Ko`;
}

function normalizeRequestKind(requestId: string) {
  if (requestId.startsWith("callback-")) {
    return { kind: "callback" as const, rawId: requestId.slice("callback-".length) };
  }
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

function HeroSvgIcon({ name }: { name: "phone" | "mail" | "whatsapp" | "sms" | "more" | "overview" | "calendar" | "history" | "documents" | "consult" }) {
  const common = "h-[18px] w-[18px] shrink-0";
  if (name === "phone") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M6.6 3.5h2.4l1.2 4.8-1.8 1.1a12.5 12.5 0 0 0 5.2 5.2l1.1-1.8 4.8 1.2v2.4c0 .9-.7 1.6-1.6 1.7C10.8 18.3 5.7 13.2 3.9 5.2 3.8 4.3 4.5 3.5 5.4 3.5Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      </svg>
    );
  }
  if (name === "mail") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <rect x="3.5" y="6" width="17" height="12" rx="2.2" stroke="currentColor" strokeWidth="1.8" />
        <path d="M4.5 7.5 12 13l7.5-5.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  }
  if (name === "whatsapp") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M12 3a8.5 8.5 0 0 0-7.3 12.8L3.5 21l5.4-1.1A8.5 8.5 0 1 0 12 3Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
        <path d="M9.2 9.4c.2-.5.5-.5.8-.5h.7c.2 0 .4.1.5.4l.5 1.2c.1.2.1.4 0 .6l-.4.5c-.1.2-.1.4 0 .6.4.8 1.2 1.6 2 2 .2.1.4.1.6 0l.5-.4c.2-.1.4-.1.6 0l1.2.5c.3.1.4.3.4.5v.7c0 .3-.1.6-.5.8-.4.3-1 .6-1.7.6-.9 0-2-.4-3.1-1.3-1.3-1.1-2.4-2.8-2.5-3.6-.1-.5.1-1 .4-1.3Z" fill="currentColor" />
      </svg>
    );
  }
  if (name === "sms") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M5 5.5h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H9l-4 3v-3H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      </svg>
    );
  }
  if (name === "more") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="6" cy="12" r="1.6" fill="currentColor" />
        <circle cx="12" cy="12" r="1.6" fill="currentColor" />
        <circle cx="18" cy="12" r="1.6" fill="currentColor" />
      </svg>
    );
  }
  if (name === "overview") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <rect x="4" y="4" width="7" height="7" rx="1.8" stroke="currentColor" strokeWidth="1.8" />
        <rect x="13" y="4" width="7" height="7" rx="1.8" stroke="currentColor" strokeWidth="1.8" />
        <rect x="4" y="13" width="7" height="7" rx="1.8" stroke="currentColor" strokeWidth="1.8" />
        <rect x="13" y="13" width="7" height="7" rx="1.8" stroke="currentColor" strokeWidth="1.8" />
      </svg>
    );
  }
  if (name === "calendar") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <rect x="4" y="5.5" width="16" height="14" rx="2.2" stroke="currentColor" strokeWidth="1.8" />
        <path d="M8 4v3M16 4v3M4 10h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  }
  if (name === "documents") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M8 4.5h8l4 4.5V19a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6.5a2 2 0 0 1 2-2Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
        <path d="M16 4.5V9h4M10 12h6M10 15.5h4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  }
  if (name === "consult") {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="8" cy="9" r="3" stroke="currentColor" strokeWidth="1.8" />
        <path d="M11 11.5c1.7.8 3 2.6 3 4.7v1.8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        <path d="M15.5 14.5h4.5M17.7 12.3v4.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        <path d="M3 20h9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg className={common} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth="1.8" />
      <path d="M12 7.5v5l3 2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function PatientStatusPill({ bucket }: { bucket: "new" | "active" | "inactive" }) {
  const meta = patientStatusMeta(bucket);
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-black sm:text-sm"
      style={{ backgroundColor: meta.bg, color: meta.text }}
    >
      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: meta.dot }} />
      {meta.label}
    </span>
  );
}

function ContactMetaCard({
  icon,
  label,
  value,
  action,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-2.5 rounded-2xl border border-[#E8EEF5] bg-[#F8FBFD] px-3 py-2.5 sm:flex-row sm:items-start sm:gap-3 sm:px-4 sm:py-3">
      <div className="flex min-w-0 items-start gap-2.5 sm:gap-3">
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-white text-[#007E8C] shadow-sm ring-1 ring-[#E2EAF4] sm:mt-0.5 sm:h-9 sm:w-9">
          {icon}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#94A3B8] sm:text-[11px]">{label}</div>
          <div className="mt-0.5 break-words text-[13px] font-bold leading-snug text-[#0A1628] sm:text-[15px]">{value}</div>
        </div>
      </div>
      {action ? <div className="shrink-0 sm:ml-auto sm:self-center">{action}</div> : null}
    </div>
  );
}

function PatientQuickActions({
  notify,
  onOpenProfile,
  onCreateBooking,
  onCreateConsultation,
  createBookingDisabled,
}: {
  notify: (message: string, opts?: { sticky?: boolean }) => void;
  onOpenProfile: () => void;
  onCreateBooking: () => void;
  onCreateConsultation: () => void;
  createBookingDisabled?: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <HeaderAction
        variant="primary"
        compact
        icon={<HeroSvgIcon name="consult" />}
        onClick={onCreateConsultation}
      >
        Créer une consultation
      </HeaderAction>
      <HeaderAction
        variant="secondary"
        compact
        icon={<HeroSvgIcon name="calendar" />}
        onClick={() => {
          if (createBookingDisabled) {
            notify("Numéro patient requis pour créer un rendez-vous.");
            return;
          }
          onCreateBooking();
        }}
      >
        Créer un RDV
      </HeaderAction>
      <HeaderAction variant="ghost" compact icon={<HeroSvgIcon name="more" />} onClick={onOpenProfile}>
        Profil
      </HeaderAction>
    </div>
  );
}

function PatientProfileHeaderMeta({
  birthDate,
  treatingPhysician,
  treatingPhysicianCity,
  onOpenProfile,
}: {
  birthDate: unknown;
  treatingPhysician: unknown;
  treatingPhysicianCity: unknown;
  onOpenProfile: () => void;
}) {
  const physician = formatPhysicianWithCity(treatingPhysician, treatingPhysicianCity);
  const birthLabel = formatBirthDateWithAge(birthDate, formatBirthDateDisplay);
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-[#E8EEF5] bg-[#F8FBFD] p-3.5 sm:flex-row sm:items-center sm:justify-between sm:gap-5 sm:p-4">
      <div className="grid min-w-0 flex-1 grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4">
        <div className="min-w-0">
          <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#94A3B8] sm:text-[11px]">
            Date de naissance
          </div>
          <div className="mt-0.5 text-sm font-black text-[#0A1628] sm:text-[15px]">{birthLabel}</div>
        </div>
        <div className="min-w-0">
          <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#94A3B8] sm:text-[11px]">
            Médecin traitant
          </div>
          <div className="mt-0.5 break-words text-sm font-black text-[#0A1628] sm:text-[15px]">
            {physician || "Non renseigné"}
          </div>
        </div>
      </div>
      <button
        type="button"
        onClick={onOpenProfile}
        className="inline-flex h-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#06355D] to-[#002D4E] px-4 text-sm font-black text-white shadow-[0_10px_24px_rgba(3,49,82,0.18)] transition hover:brightness-110 active:scale-[0.98] sm:h-12 sm:px-5"
      >
        Voir le profil détaillé
      </button>
    </div>
  );
}

function PatientProfileTextArea({
  label,
  value,
  onChange,
  placeholder,
  rows = 3,
  className = "",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
  className?: string;
}) {
  return (
    <label className={cx("block rounded-2xl bg-white p-4", className)}>
      <div className="mb-1 text-xs font-bold text-[#7D8CA5]">{label}</div>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        maxLength={6000}
        placeholder={placeholder}
        className="mt-1 w-full resize-y rounded-xl border border-[#DDE7F1] bg-white px-3 py-2 text-sm font-semibold leading-6 text-[#0A1628] outline-none focus:border-[#009CA4] focus:ring-4 focus:ring-[#009CA4]/10"
      />
    </label>
  );
}

function PatientMedicalContextPreview({
  patient,
  compact = false,
}: {
  patient: Record<string, unknown> | null;
  compact?: boolean;
}) {
  const read = (key: string) => String(patient?.[key] || "").trim();
  const allergy = read("allergies");
  const treatment = read("traitements");
  const attention = read("points_attention");
  const risks = read("facteurs_risque");
  const summary = read("synthese_medicale");
  const last = read("dernier_contexte_consultation");
  const hasContext = Boolean(allergy || treatment || attention || risks || summary || last);
  const rows = [
    { label: "Allergies", value: allergy || "Non renseignées", tone: allergy ? "red" : "muted" },
    { label: "Traitements", value: treatment || "Aucun traitement renseigné", tone: treatment ? "teal" : "muted" },
    { label: "Points d'attention", value: attention || risks || "Aucun point d'attention renseigné", tone: attention || risks ? "amber" : "muted" },
  ];
  const toneClass = {
    red: "border-red-200 bg-red-50 text-red-950",
    amber: "border-amber-200 bg-amber-50 text-amber-950",
    teal: "border-[#BFE9EC] bg-[#F0FAFB] text-[#0A4F55]",
    muted: "border-[#E2EAF4] bg-white text-[#334155]",
  };
  return (
    <section className={cx(
      "overflow-hidden rounded-[28px] border border-[#DDE7F1] bg-white shadow-[0_16px_40px_rgba(15,23,42,0.08)]",
      compact ? "p-4" : "p-5",
    )}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-black uppercase tracking-[0.18em] text-[#009CA4]">Contexte médical</p>
          <h2 className={cx("font-black tracking-[-0.02em] text-[#0A1628]", compact ? "text-xl" : "text-2xl")}>
            Ce qu'il faut savoir avant la consultation
          </h2>
          <p className="mt-1 max-w-2xl text-sm font-semibold leading-6 text-[#64748B]">
            Résumé stable, alertes et derniers éléments récupérés depuis les fiches de consultation.
          </p>
        </div>
        <span className={cx(
          "rounded-full px-3 py-1.5 text-xs font-black",
          hasContext ? "bg-[#E9FAFC] text-[#007E8C]" : "bg-[#F1F5F9] text-[#64748B]",
        )}>
          {hasContext ? "Contexte renseigné" : "À compléter"}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
        {rows.map((row) => (
          <div key={row.label} className={cx("rounded-2xl border px-4 py-3", toneClass[row.tone as keyof typeof toneClass])}>
            <div className="text-[10px] font-black uppercase tracking-[0.14em] opacity-70">{row.label}</div>
            <div className="mt-1.5 text-sm font-black leading-6">{row.value}</div>
          </div>
        ))}
      </div>
      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
        <div className="rounded-2xl border border-[#E2EAF4] bg-[#F8FBFD] px-4 py-3">
          <div className="text-[10px] font-black uppercase tracking-[0.14em] text-[#64748B]">Synthèse médicale</div>
          <p className="mt-2 text-sm font-semibold leading-7 text-[#0A1628]">
            {summary || "Aucune synthèse médicale stable pour l'instant."}
          </p>
        </div>
        <div className="rounded-2xl border border-[#E2EAF4] bg-[#F8FBFD] px-4 py-3">
          <div className="text-[10px] font-black uppercase tracking-[0.14em] text-[#64748B]">Dernier contexte</div>
          <p className="mt-2 text-sm font-semibold leading-7 text-[#0A1628]">
            {last || "Aucune consultation enregistrée n'a encore enrichi ce contexte."}
          </p>
        </div>
      </div>
    </section>
  );
}

function HeaderAction({
  children,
  icon,
  variant = "primary",
  compact = false,
  onClick,
}: {
  children: React.ReactNode;
  icon?: React.ReactNode;
  variant?: "primary" | "secondary" | "ghost";
  compact?: boolean;
  onClick: () => void;
}) {
  const variants = {
    primary: "border-[#009CA4] bg-[#009CA4] text-white shadow-[0_8px_20px_rgba(0,156,164,0.22)] hover:bg-[#008891]",
    secondary: "border-[#DDE7F1] bg-white text-[#0A1628] hover:bg-[#F8FBFD]",
    ghost: "border-[#E2EAF4] bg-[#F8FBFD] text-[#52637C] hover:bg-white",
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-xl border text-sm font-extrabold transition active:scale-[0.98]",
        compact ? "h-11 px-3 sm:px-4" : "h-11 px-4 sm:h-12 sm:px-5",
        variants[variant],
      )}
    >
      {icon}
      <span className={compact ? "text-xs sm:text-sm" : ""}>{children}</span>
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

function PatientDocumentsList({
  documents,
  loading,
  patientEmail,
  documentSendingId,
  documentDeletingId,
  onPreview,
  onDownload,
  onSend,
  onDelete,
  onAddDocument,
}: {
  documents: PatientDocument[];
  loading: boolean;
  patientEmail: string;
  documentSendingId: number | null;
  documentDeletingId: number | null;
  onPreview: (doc: PatientDocument) => void;
  onDownload: (doc: PatientDocument) => void;
  onSend: (docId: number) => void;
  onDelete: (docId: number) => void;
  onAddDocument?: () => void;
}) {
  if (loading) {
    return (
      <div className="rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] px-4 py-3 text-sm text-[#64748B]">
        Chargement des documents…
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-[#DDE7F1] bg-[#F8FAFC] px-4 py-8 text-center">
        <div className="text-3xl">▤</div>
        <p className="mt-3 text-sm font-semibold text-[#61708B]">Aucun document pour ce patient.</p>
        {onAddDocument ? (
          <button
            type="button"
            onClick={onAddDocument}
            className="mt-4 rounded-xl border border-[#6AD58B] bg-white px-4 py-2.5 text-sm font-black text-[#0EA348] hover:bg-[#F0FFF5]"
          >
            ▤ Ajouter un document
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {documents.map((doc) => {
        const canPreview = doc.mime_type.includes("pdf") || doc.mime_type.startsWith("image/");
        return (
          <div key={doc.id} className="flex items-center justify-between gap-3 rounded-xl border border-[#E2E8F0] bg-white px-3 py-3 sm:px-4">
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-bold text-[#0A1628]">{doc.original_name}</div>
              <div className="text-xs text-[#64748B]">
                {formatBytes(doc.size_bytes)} · {doc.created_at ? new Date(doc.created_at).toLocaleDateString("fr-FR") : "récemment"}
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
              {canPreview ? (
                <button type="button" onClick={() => onPreview(doc)} className="rounded-lg border border-[#75D3DF] bg-[#E9FAFC] px-2.5 py-1 text-xs font-black text-[#008EA1] hover:bg-[#DDF6FA]">
                  Consulter
                </button>
              ) : null}
              <button type="button" onClick={() => onDownload(doc)} className="rounded-lg border border-[#DDE7F1] px-2.5 py-1 text-xs font-black text-[#0A1628] hover:bg-[#F8FAFC]">
                Télécharger
              </button>
              <button
                type="button"
                onClick={() => onSend(doc.id)}
                disabled={documentSendingId === doc.id || !patientEmail}
                className="rounded-lg border border-[#86EFAC] px-2.5 py-1 text-xs font-black text-[#15803D] hover:bg-[#F0FDF4] disabled:opacity-50"
                title={patientEmail ? `Envoyer à ${patientEmail}` : "Ajoutez un email patient"}
              >
                {documentSendingId === doc.id ? "..." : "Envoyer"}
              </button>
              <button
                type="button"
                onClick={() => onDelete(doc.id)}
                disabled={documentDeletingId === doc.id}
                className="rounded-lg border border-[#FCA5A5] px-2.5 py-1 text-xs font-black text-[#B91C1C] hover:bg-[#FEF2F2] disabled:opacity-50"
              >
                {documentDeletingId === doc.id ? "..." : "Supprimer"}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PrimaryCTA({
  children,
  variant = "dark",
  onClick,
}: {
  children: React.ReactNode;
  variant?: "dark" | "note" | "document" | "consult";
  onClick: () => void;
}) {
  const variants = {
    dark: "bg-gradient-to-br from-[#06355D] to-[#002D4E] text-white shadow-[0_12px_30px_rgba(3,49,82,.20)] hover:brightness-110",
    note: "border border-[#FF9C4B] bg-white text-[#F26C00] hover:bg-[#FFF7EF]",
    document: "border border-[#6AD58B] bg-white text-[#0EA348] hover:bg-[#F0FFF5]",
    consult: "border border-[#75D3DF] bg-white text-[#008EA1] hover:bg-[#E9FAFC]",
  };

  return (
    <button
      onClick={onClick}
      className={cx(
        "flex h-14 items-center justify-center gap-2.5 rounded-2xl px-4 text-sm font-black transition active:scale-[0.98] sm:h-16 sm:gap-3 sm:px-6 sm:text-base",
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
  title: React.ReactNode;
  children: React.ReactNode;
  onClose: () => void;
  width?: string;
}) {
  return (
    <div className="fixed inset-0 z-[100] flex items-end justify-center bg-[#0A1628]/35 p-3 backdrop-blur-sm sm:items-center sm:p-6" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className={cx("max-h-[90vh] w-full overflow-auto rounded-[28px] bg-white p-5 shadow-2xl sm:p-7", width)}>
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
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("Tous");
  const [activeView, setActiveView] = useState<ViewType>("overview");
  const [toast, setToast] = useState("");
  const [modal, setModal] = useState<ModalType>(null);
  const [note, setNote] = useState("");
  const [noteRecording, setNoteRecording] = useState(false);
  const [noteTranscribing, setNoteTranscribing] = useState(false);
  const noteRecorderRef = useRef<MediaRecorder | null>(null);
  const noteChunksRef = useRef<BlobPart[]>([]);
  const noteStreamRef = useRef<MediaStream | null>(null);
  const [patientNotes, setPatientNotes] = useState<PatientNote[]>([]);
  const [notesLoading, setNotesLoading] = useState(false);
  const [notesSaving, setNotesSaving] = useState(false);
  const [absenceNoteSavingKey, setAbsenceNoteSavingKey] = useState("");
  const [noteDeletingId, setNoteDeletingId] = useState<number | null>(null);
  const [noteUpdatingId, setNoteUpdatingId] = useState<number | null>(null);
  const [noteEditingId, setNoteEditingId] = useState<number | null>(null);
  const [noteEditDraft, setNoteEditDraft] = useState("");
  const [noteExpandedIds, setNoteExpandedIds] = useState<Record<number, boolean>>({});
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
  const [emailDuplicateConflicts, setEmailDuplicateConflicts] = useState<Array<Record<string, unknown>>>([]);
  const [editingPhone, setEditingPhone] = useState(false);
  const [phoneDraft, setPhoneDraft] = useState("");
  const [phoneSaving, setPhoneSaving] = useState(false);
  const [phoneDuplicateConflicts, setPhoneDuplicateConflicts] = useState<Array<Record<string, unknown>>>([]);
  const [requestStatus, setRequestStatus] = useState("");
  const [requestActionLoading, setRequestActionLoading] = useState<"" | "processed" | "cancelled">("");
  const [tenantPatientNotFound, setTenantPatientNotFound] = useState(false);
  /** Profil réel (API) pour l’en-tête quand on ouvre /patient-dashboard?phone=… ou un numéro reconnu en base. */
  const [urlPatientHero, setUrlPatientHero] = useState<{ name: string; phone: string; initials: string } | null>(null);
  const [tenantSidebarRows, setTenantSidebarRows] = useState<SidebarPatientRow[]>(() => {
    const cached = getCachedTenantPatientsList(TENANT_PATIENTS_LIST_QUERY);
    if (!cached?.items?.length) return [];
    return cached.items
      .map((item: Record<string, unknown>) => cabinetRowToSidebar(item))
      .filter((item): item is SidebarPatientRow => Boolean(item));
  });
  const [tenantListLoading, setTenantListLoading] = useState(
    () => !getCachedTenantPatientsList(TENANT_PATIENTS_LIST_QUERY)?.items?.length,
  );
  const [tenantListError, setTenantListError] = useState<string | null>(null);
  const toastTimerRef = useRef<number | null>(null);
  const patientDetailCacheRef = useRef(new Map<string, {
    nonce: number;
    ts: number;
    hasNotes: boolean;
    patientCabinetRow: Record<string, unknown> | null;
    urlPatientHero: { name: string; phone: string; initials: string } | null;
    patientEmail: string;
    documents: PatientDocument[];
    patientNotes: PatientNote[];
    patientInsightTags: PatientInsightTag[];
    patientPastAppointments: Array<{ start: Date; key: string }>;
    tenantPatientNotFound: boolean;
  }>());
  const [tenantAgendaRawSlots, setTenantAgendaRawSlots] = useState<Array<Record<string, unknown>>>([]);
  const [patientAgendaLoading, setPatientAgendaLoading] = useState(false);
  /** Fenêtre agenda déjà chargée (14j overview, 60j onglet rendez-vous). */
  const [agendaDaysLoaded, setAgendaDaysLoaded] = useState(0);
  const [agendaRefreshNonce, setAgendaRefreshNonce] = useState(0);
  const [createPatientBookingOpen, setCreatePatientBookingOpen] = useState(false);
  const [patientBookingConfirm, setPatientBookingConfirm] = useState<PatientBookingConfirm | null>(null);
  const [apptActionTarget, setApptActionTarget] = useState<ApptActionTarget | null>(null);
  const [apptActionLoading, setApptActionLoading] = useState(false);
  /** Recherche serveur GET /patients?q= ; null si la recherche API n’est pas utilisée (< 2 caractères). */
  const [patientSearchRows, setPatientSearchRows] = useState<SidebarPatientRow[] | null>(null);
  const [patientSearchLoading, setPatientSearchLoading] = useState(false);
  const [patientListOpen, setPatientListOpen] = useState(false);
  /** Recharge GET /patients/{phone} (ex. après POST création ou mise à jour nom). */
  const [patientFetchNonce, setPatientFetchNonce] = useState(0);
  const [summaryRefreshNonce, setSummaryRefreshNonce] = useState(0);
  /** Ligne brute API `cabinet_clients` pour le modal profil / métadonnées. */
  const [patientCabinetRow, setPatientCabinetRow] = useState<Record<string, unknown> | null>(null);
  const [patientInsightTags, setPatientInsightTags] = useState<PatientInsightTag[]>([]);
  const [patientPastAppointments, setPatientPastAppointments] = useState<Array<{ start: Date; key: string }>>([]);
  const [patientHistory, setPatientHistory] = useState<PatientHistoryItem[]>([]);
  const [patientHistoryLoading, setPatientHistoryLoading] = useState(false);
  const [patientConsultations, setPatientConsultations] = useState<PatientConsultationRow[]>([]);
  const [patientConsultationsLoading, setPatientConsultationsLoading] = useState(false);
  const [lastSavedConsultationId, setLastSavedConsultationId] = useState<number | null>(null);
  const [manualPatientCreateForm, setManualPatientCreateForm] = useState<ManualPatientCreateForm>(
    MANUAL_PATIENT_CREATE_EMPTY,
  );
  const [manualPatientCreateSaving, setManualPatientCreateSaving] = useState(false);
  const [manualPatientCreateConflicts, setManualPatientCreateConflicts] = useState<Array<Record<string, unknown>>>([]);
  const [consultationInitialDraft, setConsultationInitialDraft] = useState<ConsultationOpenDraft>(CONSULTATION_DRAFT_EMPTY);
  const [consultationSaving, setConsultationSaving] = useState(false);
  const [consultationDeletingId, setConsultationDeletingId] = useState<number | null>(null);
  const [createFicheName, setCreateFicheName] = useState("");
  const [createFicheSaving, setCreateFicheSaving] = useState(false);
  const [profileNameDraft, setProfileNameDraft] = useState("");
  const [profileBirthDateDraft, setProfileBirthDateDraft] = useState("");
  const [profilePhysicianDraft, setProfilePhysicianDraft] = useState("");
  const [profilePhysicianCityDraft, setProfilePhysicianCityDraft] = useState("");
  const [profileMedicalAntecedentsDraft, setProfileMedicalAntecedentsDraft] = useState("");
  const [profileSurgicalAntecedentsDraft, setProfileSurgicalAntecedentsDraft] = useState("");
  const [profileAllergiesDraft, setProfileAllergiesDraft] = useState("");
  const [profileTreatmentsDraft, setProfileTreatmentsDraft] = useState("");
  const [profileRiskFactorsDraft, setProfileRiskFactorsDraft] = useState("");
  const [profileAttentionPointsDraft, setProfileAttentionPointsDraft] = useState("");
  const [profileMedicalSummaryDraft, setProfileMedicalSummaryDraft] = useState("");
  const [profileLastConsultationContextDraft, setProfileLastConsultationContextDraft] = useState("");
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
  const [tenantHandoffs, setTenantHandoffs] = useState<Array<Record<string, unknown>>>([]);
  const [tenantCallbacks, setTenantCallbacks] = useState<Array<Record<string, unknown>>>([]);
  const [tenantCalls, setTenantCalls] = useState<Array<Record<string, unknown>>>([]);
  const [requestsLoading, setRequestsLoading] = useState(false);
  const [requestStatusOverrides, setRequestStatusOverrides] = useState<Record<string, { status_raw?: string }>>(
    () => readRequestStatusOverrides(),
  );
  const [selectedPatientPhones, setSelectedPatientPhones] = useState<string[]>([]);
  const [singleMessageChannel, setSingleMessageChannel] = useState<MessageChannel>("sms");
  const [singleMessageSubject, setSingleMessageSubject] = useState("Message de votre cabinet");
  const [singleMessageBody, setSingleMessageBody] = useState("");
  const [singleMessageSending, setSingleMessageSending] = useState(false);
  const [bulkMessageChannel, setBulkMessageChannel] = useState<MessageChannel>("sms");
  const [bulkMessageSubject, setBulkMessageSubject] = useState("Message de votre cabinet");
  const [bulkMessageBody, setBulkMessageBody] = useState("");
  const [bulkMessageSendToAll, setBulkMessageSendToAll] = useState(false);
  const [bulkMessageSending, setBulkMessageSending] = useState(false);
  const [bulkModalQuery, setBulkModalQuery] = useState("");
  const consultationAutoOpenRef = useRef(false);
  const consultationDossierRef = useRef<HTMLElement | null>(null);

  const manualPatientCreateFieldErrors = useMemo(
    () => computePatientCreateFieldErrors(manualPatientCreateForm),
    [manualPatientCreateForm],
  );
  const manualPatientCreateSubmitBlocked = useMemo(
    () => isPatientCreateSubmitBlocked(manualPatientCreateFieldErrors, manualPatientCreateConflicts),
    [manualPatientCreateFieldErrors, manualPatientCreateConflicts],
  );
  const handleManualPatientCreateConflicts = useCallback((conflicts: Array<Record<string, unknown>>) => {
    setManualPatientCreateConflicts(conflicts);
  }, []);

  usePatientCreateDuplicateCheck({
    enabled: modal === "createPatientManual",
    phone: manualPatientCreateForm.phone,
    email: manualPatientCreateForm.email,
    onConflicts: handleManualPatientCreateConflicts,
  });

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    };
  }, []);

  useEffect(() => {
    if (noteEditingId === null) return;
    if (!patientNotes.some((item) => item.id === noteEditingId)) {
      setNoteEditingId(null);
      setNoteEditDraft("");
    }
  }, [noteEditingId, patientNotes]);

  const notify = useCallback((message: string, opts?: { sticky?: boolean }) => {
    setToast(message);
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    /* Toast "sticky" (erreur/validation) = 6 s pour laisser le temps de lire avant qu'il disparaisse. */
    const ms = opts?.sticky ? 6000 : 1800;
    toastTimerRef.current = window.setTimeout(() => setToast(""), ms);
  }, []);

  const confirmImportantAction = useCallback((message: string) => {
    if (typeof window === "undefined") return true;
    return window.confirm(message);
  }, []);

  const globalLoadingLabel = useMemo(() => {
    if (consultationSaving) return "Enregistrement de la fiche consultation…";
    if (manualPatientCreateSaving) return "Création de la fiche patient…";
    if (singleMessageSending) return "Envoi du message individuel…";
    if (bulkMessageSending) return "Envoi groupé en cours…";
    if (profileSaveSaving) return "Enregistrement du profil patient…";
    if (createFicheSaving) return "Création de la fiche patient…";
    if (notesSaving) return "Enregistrement de la note…";
    if (noteUpdatingId) return "Modification de la note…";
    if (absenceNoteSavingKey) return "Enregistrement de l'absence…";
    if (emailSaving) return "Enregistrement de l'email…";
    if (phoneSaving) return "Enregistrement du numéro…";
    if (documentsUploading) return "Ajout du document…";
    if (documentsLoading) return "Chargement des documents…";
    if (notesLoading) return "Chargement des notes…";
    if (patientAgendaLoading) return "Chargement des rendez-vous…";
    if (patientHistoryLoading) return "Chargement de l'historique…";
    if (tenantListLoading) return "Chargement des patients…";
    if (patientSearchLoading) return "Recherche de patients…";
    if (requestsLoading) return "Chargement des demandes…";
    if (deletePreviewLoading) return "Préparation de la suppression…";
    if (deleteSaving) return "Suppression de la fiche en cours…";
    if (apptActionLoading) return "Traitement du rendez-vous…";
    if (requestActionLoading) return "Mise à jour de la demande…";
    return "";
  }, [
    consultationSaving,
    manualPatientCreateSaving,
    singleMessageSending,
    bulkMessageSending,
    profileSaveSaving,
    createFicheSaving,
    notesSaving,
    noteUpdatingId,
    absenceNoteSavingKey,
    emailSaving,
    phoneSaving,
    documentsUploading,
    documentsLoading,
    notesLoading,
    patientAgendaLoading,
    patientHistoryLoading,
    tenantListLoading,
    patientSearchLoading,
    requestsLoading,
    deletePreviewLoading,
    deleteSaving,
    apptActionLoading,
    requestActionLoading,
  ]);

  const requestContextFromUrl = useMemo<RequestContext | null>(() => {
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

  const requestIdFromUrl = (searchParams.get("requestId") || "").trim();
  const phoneFromDashboardUrl = useMemo(() => (searchParams.get("phone") || "").trim(), [searchParams]);
  const isDirectPhoneView = Boolean(phoneFromDashboardUrl);
  const tenantPatientPhone = useMemo(() => normalizePhone(phoneFromDashboardUrl), [phoneFromDashboardUrl]);
  const [patientProfileReady, setPatientProfileReady] = useState(false);

  useEffect(() => {
    setPatientProfileReady(false);
    setTenantAgendaRawSlots([]);
    setAgendaDaysLoaded(0);
    setPatientAgendaLoading(false);
  }, [tenantPatientPhone]);

  useEffect(() => {
    const refresh = () => setRequestStatusOverrides(readRequestStatusOverrides());
    const onStorage = (event: StorageEvent) => {
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
    if (!tenantPatientPhone && !requestIdFromUrl) {
      setRequestsLoading(false);
      return undefined;
    }
    if (!requestIdFromUrl && !patientProfileReady) {
      return undefined;
    }
    let cancelled = false;
    setRequestsLoading(true);
    const deferMs = requestIdFromUrl ? 0 : 2000;
    const tid = window.setTimeout(() => {
      fetchTenantRequestsBundleCached(api, {
        callsQuery: requestIdFromUrl
          ? "?limit=50&days=30&compact=1"
          : "?limit=25&days=14&compact=1",
        handoffsQuery: requestIdFromUrl ? "?limit=50" : "?limit=20",
        callbacksQuery: requestIdFromUrl ? "?limit=50" : "?limit=20",
      })
      .then(({ callsRes, handoffsRes, callbacksRes }) => {
        if (cancelled) return;
        setTenantHandoffs(Array.isArray(handoffsRes?.items) ? handoffsRes.items : []);
        setTenantCalls(Array.isArray(callsRes?.calls) ? callsRes.calls : []);
        setTenantCallbacks(Array.isArray(callbacksRes?.items) ? callbacksRes.items : []);
      })
      .finally(() => {
        if (!cancelled) setRequestsLoading(false);
      });
    }, deferMs);
    return () => {
      cancelled = true;
      window.clearTimeout(tid);
    };
  }, [tenantPatientPhone, requestIdFromUrl, patientProfileReady]);

  const tenantRequestRows = useMemo(
    () => buildTenantRequestRows(tenantCalls, tenantHandoffs, tenantCallbacks, requestStatusOverrides),
    [tenantCalls, tenantHandoffs, tenantCallbacks, requestStatusOverrides],
  );

  const patientOpenRequests = useMemo(
    () => filterOpenPatientRequests(tenantRequestRows, tenantPatientPhone, normalizePhone),
    [tenantRequestRows, tenantPatientPhone],
  );

  const activeRequestDetail = useMemo(() => {
    if (!requestIdFromUrl) return null;
    const fromApi = tenantRequestRows.find((row) => row.id === requestIdFromUrl);
    if (fromApi) return fromApi;
    if (!requestContextFromUrl) return null;
    return {
      id: requestContextFromUrl.id,
      patientName: requestContextFromUrl.patientName || "Patient",
      type: requestContextFromUrl.type,
      typeKey: "transfer",
      priority: "Standard",
      status: requestContextFromUrl.status,
      status_raw: requestContextFromUrl.status.toLowerCase().includes("cours") ? "callback_scheduled" : "callback_created",
      summary: requestContextFromUrl.summary,
      phone: requestContextFromUrl.phone,
      createdAtLabel: requestContextFromUrl.createdAtLabel,
      createdAt: "",
      source: requestContextFromUrl.source,
    };
  }, [requestIdFromUrl, tenantRequestRows, requestContextFromUrl]);

  const otherOpenRequests = useMemo(
    () => patientOpenRequests.filter((row) => row.id !== activeRequestDetail?.id),
    [patientOpenRequests, activeRequestDetail?.id],
  );

  const openPatientRequest = useCallback((req: {
    id: string;
    phone?: string;
    patientName?: string;
    summary?: string;
    type?: string;
    status?: string;
    source?: string;
    createdAtLabel?: string;
  }) => {
    const np = new URLSearchParams(searchParams);
    np.set("requestId", req.id);
    if (req.phone || tenantPatientPhone) np.set("phone", req.phone || tenantPatientPhone);
    if (req.patientName) np.set("patientName", req.patientName);
    if (req.summary) np.set("summary", req.summary);
    if (req.type) np.set("type", req.type);
    np.set("status", req.status === "En cours" ? "En cours" : "À traiter");
    if (req.source) np.set("source", req.source);
    if (req.createdAtLabel) np.set("createdAtLabel", req.createdAtLabel);
    setSearchParams(np, { replace: true });
  }, [searchParams, setSearchParams, tenantPatientPhone]);

  const clearActiveRequest = useCallback(() => {
    const next = new URLSearchParams(searchParams);
    [
      "requestId",
      "patientName",
      "summary",
      "type",
      "status",
      "source",
      "createdAtLabel",
    ].forEach((key) => next.delete(key));
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  const requestContext = requestContextFromUrl;

  useEffect(() => {
    if (!tenantPatientNotFound) return;
    const hint = String(requestContext?.patientName || "").trim();
    if (hint) setCreateFicheName((prev) => (prev.trim() ? prev : hint));
  }, [tenantPatientNotFound, requestContext?.patientName]);

  useEffect(() => {
    setPatientListOpen(!tenantPatientPhone);
  }, [tenantPatientPhone]);

  /** Corrige ?phone= après décodage URL (notamment « + » → espace) ou variants 06 / espaces. */
  useEffect(() => {
    const raw = (searchParams.get("phone") || "").trim();
    const canonical = normalizePhone(raw);
    if (!canonical || canonical === raw) return;
    const np = new URLSearchParams(searchParams);
    np.set("phone", canonical);
    setSearchParams(np, { replace: true });
  }, [searchParams, setSearchParams]);

  const loadTenantSidebarPatients = useCallback(async (opts?: { force?: boolean }) => {
    try {
      setTenantListError(null);
      if (opts?.force) invalidateTenantPatientsListCache();
      const { items } = await fetchTenantPatientsListCached(api, {
        query: TENANT_PATIENTS_LIST_QUERY,
        force: Boolean(opts?.force),
      });
      const mapped = items
        .map((item: Record<string, unknown>) => cabinetRowToSidebar(item))
        .filter((item): item is SidebarPatientRow => Boolean(item));
      setTenantSidebarRows(mapped);
    } catch (e) {
      if (!opts?.force) {
        const cached = getCachedTenantPatientsList(TENANT_PATIENTS_LIST_QUERY);
        if (cached?.items?.length) return;
      }
      setTenantSidebarRows([]);
      setTenantListError((e as Error)?.message || "Impossible de charger la liste des fiches patients.");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const cached = getCachedTenantPatientsList(TENANT_PATIENTS_LIST_QUERY);
    if (cached?.items?.length) {
      const mapped = cached.items
        .map((item: Record<string, unknown>) => cabinetRowToSidebar(item))
        .filter((item): item is SidebarPatientRow => Boolean(item));
      setTenantSidebarRows(mapped);
      setTenantListLoading(false);
    } else if (!phoneFromDashboardUrl) {
      setTenantListLoading(true);
    } else {
      setTenantListLoading(false);
    }
    const deferMs = phoneFromDashboardUrl ? 350 : 0;
    const tid = window.setTimeout(() => {
      loadTenantSidebarPatients({ force: !cached?.items?.length }).finally(() => {
        if (!cancelled) setTenantListLoading(false);
      });
    }, deferMs);
    return () => {
      cancelled = true;
      window.clearTimeout(tid);
    };
  }, [loadTenantSidebarPatients, phoneFromDashboardUrl]);

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
  const visibleSelectablePhones = useMemo(
    () => filteredSidebarRows.map((row) => row.phone).filter(Boolean),
    [filteredSidebarRows],
  );
  const selectedVisibleCount = useMemo(
    () => visibleSelectablePhones.filter((phone) => selectedPatientPhones.includes(phone)).length,
    [visibleSelectablePhones, selectedPatientPhones],
  );
  const allVisibleSelected = visibleSelectablePhones.length > 0 && selectedVisibleCount === visibleSelectablePhones.length;
  const selectedSidebarRows = useMemo(() => {
    const selectedSet = new Set(selectedPatientPhones);
    return effectiveSidebarRows.filter((row) => selectedSet.has(row.phone));
  }, [effectiveSidebarRows, selectedPatientPhones]);
  const selectedPatientsPreviewLabel = useMemo(() => {
    if (!selectedSidebarRows.length) return "";
    const names = selectedSidebarRows.map((row) => row.name);
    if (names.length <= 3) return names.join(", ");
    return `${names.slice(0, 3).join(", ")} +${names.length - 3}`;
  }, [selectedSidebarRows]);
  const bulkModalRows = useMemo(() => {
    const q = bulkModalQuery.trim().toLowerCase();
    let rows = effectiveSidebarRows;
    if (q) {
      rows = rows.filter((row) => {
        const hay = `${row.name} ${row.displayPhone} ${row.phone}`.toLowerCase();
        if (hay.includes(q)) return true;
        const needle = normalizePhone(bulkModalQuery);
        return Boolean(needle && row.phone === needle);
      });
    }
    const selectedSet = new Set(selectedPatientPhones);
    return [...rows].sort((a, b) => {
      const aSel = selectedSet.has(a.phone) ? 1 : 0;
      const bSel = selectedSet.has(b.phone) ? 1 : 0;
      if (aSel !== bSel) return bSel - aSel;
      return a.name.localeCompare(b.name, "fr");
    });
  }, [effectiveSidebarRows, bulkModalQuery, selectedPatientPhones]);
  const modalSelectablePhones = useMemo(
    () => bulkModalRows.map((row) => row.phone).filter(Boolean),
    [bulkModalRows],
  );
  const allModalSelected =
    modalSelectablePhones.length > 0 &&
    modalSelectablePhones.every((phone) => selectedPatientPhones.includes(phone));

  useEffect(() => {
    const allowed = new Set(effectiveSidebarRows.map((row) => row.phone).filter(Boolean));
    setSelectedPatientPhones((prev) => prev.filter((phone) => allowed.has(phone)));
  }, [effectiveSidebarRows]);

  const toggleSelectedPatientPhone = useCallback((phone: string) => {
    setSelectedPatientPhones((prev) =>
      prev.includes(phone) ? prev.filter((p) => p !== phone) : [...prev, phone],
    );
  }, []);

  const toggleSelectAllVisiblePatients = useCallback(() => {
    setSelectedPatientPhones((prev) => {
      if (!visibleSelectablePhones.length) return prev;
      const visibleSet = new Set(visibleSelectablePhones);
      if (allVisibleSelected) {
        return prev.filter((phone) => !visibleSet.has(phone));
      }
      const merged = [...prev];
      for (const phone of visibleSelectablePhones) {
        if (!merged.includes(phone)) merged.push(phone);
      }
      return merged;
    });
  }, [allVisibleSelected, visibleSelectablePhones]);
  const toggleSelectAllModalPatients = useCallback(() => {
    setSelectedPatientPhones((prev) => {
      if (!modalSelectablePhones.length) return prev;
      const modalSet = new Set(modalSelectablePhones);
      if (allModalSelected) {
        return prev.filter((phone) => !modalSet.has(phone));
      }
      const merged = [...prev];
      for (const phone of modalSelectablePhones) {
        if (!merged.includes(phone)) merged.push(phone);
      }
      return merged;
    });
  }, [allModalSelected, modalSelectablePhones]);

  const clearSelectedPatients = useCallback(() => {
    setSelectedPatientPhones([]);
  }, []);

  useEffect(() => {
    if (!phoneFromDashboardUrl) setUrlPatientHero(null);
  }, [phoneFromDashboardUrl]);

  const displayHero = useMemo(() => {
    const teal = "from-[#009CA4] to-[#004C69]";
    const slate = "from-slate-400 to-slate-600";
    const loadingGrad = "from-slate-300 to-slate-500";
    const resolveStatus = (): "new" | "active" | "inactive" => {
      if (sidebarHeroFallback && sidebarHeroFallback.phone === tenantPatientPhone) {
        return sidebarHeroFallback.statusBucket;
      }
      if (patientCabinetRow) return deriveCabinetRowBucket(patientCabinetRow);
      return "active";
    };
    const statusBucket = resolveStatus();
    if (tenantPatientNotFound) {
      if (sidebarHeroFallback && sidebarHeroFallback.phone === tenantPatientPhone) {
        return {
          name: sidebarHeroFallback.name,
          phone: formatDisplayFrenchPhone(tenantPatientPhone || phoneFromDashboardUrl),
          initials: sidebarHeroFallback.initials,
          gradient: sidebarHeroFallback.gradient,
          statusBucket,
        };
      }
      if (isDirectPhoneView) {
        return {
          name: "Aucune fiche pour ce numéro",
          phone: formatDisplayFrenchPhone(tenantPatientPhone || phoneFromDashboardUrl),
          initials: "?",
          gradient: slate,
          statusBucket: "new" as const,
        };
      }
      return {
        name: "Patient",
        phone: "—",
        initials: "?",
        gradient: slate,
        statusBucket: "active" as const,
      };
    }
    if (urlPatientHero) {
      return {
        ...urlPatientHero,
        phone: formatDisplayFrenchPhone(normalizePhone(urlPatientHero.phone) || urlPatientHero.phone),
        gradient: teal,
        statusBucket,
      };
    }
    if (sidebarHeroFallback) {
      return {
        name: sidebarHeroFallback.name,
        phone: sidebarHeroFallback.displayPhone,
        initials: sidebarHeroFallback.initials,
        gradient: sidebarHeroFallback.gradient,
        statusBucket,
      };
    }
    if (tenantPatientPhone && !urlPatientHero && !patientCabinetRow && !tenantPatientNotFound) {
      return {
        name: "Chargement…",
        phone: formatDisplayFrenchPhone(tenantPatientPhone),
        initials: "…",
        gradient: loadingGrad,
        statusBucket: "active" as const,
      };
    }
    return {
      name: "Patient",
      phone: "—",
      initials: "?",
      gradient: slate,
      statusBucket: "active" as const,
    };
  }, [
    tenantPatientNotFound,
    isDirectPhoneView,
    phoneFromDashboardUrl,
    tenantPatientPhone,
    urlPatientHero,
    patientCabinetRow,
    sidebarHeroFallback,
  ]);

  useEffect(() => {
    setRequestStatus(requestContext?.status || "");
    setRequestActionLoading("");
  }, [requestContext?.id, requestContext?.status]);

  const applyPatientDetailBundle = useCallback((bundle: PatientDetailBundle) => {
    setTenantPatientNotFound(bundle.tenantPatientNotFound);
    setPatientCabinetRow(bundle.patientCabinetRow);
    setUrlPatientHero(bundle.urlPatientHero);
    setPatientEmail(bundle.patientEmail);
    setDocuments(bundle.documents);
    setPatientNotes(bundle.patientNotes);
    setPatientInsightTags(bundle.patientInsightTags);
    setPatientPastAppointments(bundle.patientPastAppointments);
  }, []);

  const syncPatientEmailDraft = useCallback((email: string) => {
    setEditingEmail(false);
    setEmailDraft(email);
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!tenantPatientPhone) {
      applyPatientDetailBundle(emptyPatientDetailBundle());
      syncPatientEmailDraft("");
      setPatientHistory([]);
      setDocumentsLoading(false);
      setNotesLoading(false);
      return () => {
        cancelled = true;
      };
    }

    const cached = patientDetailCacheRef.current.get(tenantPatientPhone);
    const cacheValid = isPatientDetailCacheValid(cached, patientFetchNonce, activeView);

    if (cacheValid && cached) {
      applyPatientDetailBundle(cached);
      syncPatientEmailDraft(cached.patientEmail || "");
      setDocumentsLoading(false);
      setNotesLoading(false);
      return () => {
        cancelled = true;
      };
    }

    /* Changement de fiche : purge immédiate pour ne pas afficher l'email / notes de la fiche précédente. */
    applyPatientDetailBundle(emptyPatientDetailBundle());
    syncPatientEmailDraft("");
    setPatientHistory([]);
    setDocumentsLoading(false);
    setNotesLoading(activeView === "overview");
    setNoteDeletingId(null);
    setNoteUpdatingId(null);
    setNoteEditingId(null);
    setNoteEditDraft("");
    setNoteExpandedIds({});

    const notesPromise = activeView === "overview"
      ? api.tenantGetPatientNotes(tenantPatientPhone, "?limit=40").catch(() => ({ items: [] }))
      : Promise.resolve({ items: [] as unknown[] });

    api.tenantGetPatient(tenantPatientPhone, { lightweight: true, includeDocuments: false })
      .then(async (res) => {
        if (cancelled) return;
        const p = res?.patient as Record<string, unknown> | undefined;
        const notesRes = await notesPromise;
        if (cancelled) return;
        const bundle: PatientDetailBundle = {
          tenantPatientNotFound: false,
          patientCabinetRow: p ?? null,
          urlPatientHero: buildPatientHeroFromProfile(p, tenantPatientPhone),
          patientEmail: String(p?.email || ""),
          documents: cached?.documents?.length ? cached.documents : [],
          patientNotes: activeView === "overview"
            ? mapPatientNotes(Array.isArray(notesRes?.items) ? notesRes.items : [])
            : (cached?.patientNotes || []),
          patientInsightTags: normalizePatientInsightTags(res?.insights?.tags),
          patientPastAppointments: mapPatientPastAppointments(res?.insights?.recent_past_appointments),
        };
        applyPatientDetailBundle(bundle);
        syncPatientEmailDraft(bundle.patientEmail);
        patientDetailCacheRef.current.set(tenantPatientPhone, {
          ...bundle,
          nonce: patientFetchNonce,
          ts: Date.now(),
          hasNotes: activeView === "overview",
        });
      })
      .catch(async (e: unknown) => {
        if (cancelled) return;
        const status =
          typeof e === "object" && e !== null && "status" in e ? (e as { status?: number }).status : undefined;
        const notesRes = await notesPromise.catch(() => ({ items: [] as unknown[] }));
        if (cancelled) return;
        const bundle = emptyPatientDetailBundle({
          tenantPatientNotFound: status === 404,
          patientNotes: activeView === "overview"
            ? mapPatientNotes(Array.isArray(notesRes?.items) ? notesRes.items : [])
            : [],
        });
        applyPatientDetailBundle(bundle);
        syncPatientEmailDraft("");
        if (status !== 404) return;
        patientDetailCacheRef.current.set(tenantPatientPhone, {
          ...bundle,
          nonce: patientFetchNonce,
          ts: Date.now(),
          hasNotes: activeView === "overview",
        });
      })
      .finally(() => {
        if (!cancelled) {
          setDocumentsLoading(false);
          setNotesLoading(false);
          setPatientProfileReady(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [
    tenantPatientPhone,
    patientFetchNonce,
    activeView,
    applyPatientDetailBundle,
    syncPatientEmailDraft,
    location.pathname,
    location.search,
    location.state,
    navigate,
  ]);

  useEffect(() => {
    if (!tenantPatientPhone) {
      setDocuments([]);
      setDocumentsLoading(false);
      return undefined;
    }
    const needDocs = activeView === "overview" || activeView === "documents";
    if (!needDocs) return undefined;

    const cached = patientDetailCacheRef.current.get(tenantPatientPhone);
    if (cached?.documents?.length && isPatientDetailCacheValid(cached, patientFetchNonce, activeView)) {
      setDocuments(cached.documents);
      setDocumentsLoading(false);
      return undefined;
    }

    let cancelled = false;
    setDocumentsLoading(true);
    const deferMs = activeView === "documents" ? 0 : 700;
    const tid = window.setTimeout(() => {
      api.tenantGetPatientDocuments(tenantPatientPhone)
        .then((res) => {
          if (cancelled) return;
          const docs = mapPatientDocuments(Array.isArray(res?.items) ? res.items : []);
          setDocuments(docs);
          const entry = patientDetailCacheRef.current.get(tenantPatientPhone);
          if (entry) {
            patientDetailCacheRef.current.set(tenantPatientPhone, { ...entry, documents: docs });
          }
        })
        .catch(() => {
          if (!cancelled) setDocuments([]);
        })
        .finally(() => {
          if (!cancelled) setDocumentsLoading(false);
        });
    }, deferMs);
    return () => {
      cancelled = true;
      window.clearTimeout(tid);
    };
  }, [tenantPatientPhone, activeView, patientFetchNonce]);

  useEffect(() => {
    if (!tenantPatientPhone) return;
    setApptActionTarget(null);
    setModal((current) => (current === "cancelAppt" || current === "rescheduleAppt" ? null : current));
    setPreviewDoc(null);
    setPreviewUrl("");
  }, [tenantPatientPhone]);

  useEffect(() => {
    if (!editingEmail) setEmailDraft(patientEmail || "");
  }, [patientEmail, editingEmail, tenantPatientPhone]);

  useEffect(() => {
    if (!editingPhone) setPhoneDraft(tenantPatientPhone || "");
  }, [tenantPatientPhone, editingPhone]);

  useEffect(() => {
    if (!editingEmail || !tenantPatientPhone) {
      setEmailDuplicateConflicts([]);
      return;
    }
    const email = emailDraft.trim();
    if (!email || !isValidContactEmail(email)) {
      setEmailDuplicateConflicts([]);
      return;
    }
    let cancelled = false;
    const ctrl = new AbortController();
    const tid = window.setTimeout(() => {
      checkPatientDuplicates({
        email,
        excludePhone: tenantPatientPhone,
        signal: ctrl.signal,
      })
        .then((res) => {
          if (!cancelled) {
            setEmailDuplicateConflicts(Array.isArray(res?.conflicts) ? res.conflicts : []);
          }
        })
        .catch(() => {
          if (!cancelled) setEmailDuplicateConflicts([]);
        });
    }, 320);
    return () => {
      cancelled = true;
      window.clearTimeout(tid);
      ctrl.abort();
    };
  }, [editingEmail, emailDraft, tenantPatientPhone]);

  useEffect(() => {
    if (!editingPhone || !tenantPatientPhone) {
      setPhoneDuplicateConflicts([]);
      return;
    }
    const phone = phoneDraft.trim();
    if (!phone) {
      setPhoneDuplicateConflicts([]);
      return;
    }
    const phoneCheck = validatePatientPhone(phone);
    if (!phoneCheck.ok) {
      setPhoneDuplicateConflicts([]);
      return;
    }
    let cancelled = false;
    const ctrl = new AbortController();
    const tid = window.setTimeout(() => {
      checkPatientDuplicates({
        phone,
        excludePhone: tenantPatientPhone,
        signal: ctrl.signal,
      })
        .then((res) => {
          if (!cancelled) {
            setPhoneDuplicateConflicts(Array.isArray(res?.conflicts) ? res.conflicts : []);
          }
        })
        .catch(() => {
          if (!cancelled) setPhoneDuplicateConflicts([]);
        });
    }, 320);
    return () => {
      cancelled = true;
      window.clearTimeout(tid);
      ctrl.abort();
    };
  }, [editingPhone, phoneDraft, tenantPatientPhone]);

  useEffect(() => {
    let cancelled = false;
    if (!tenantPatientPhone) {
      setPatientAgendaLoading(false);
      return () => {
        cancelled = true;
      };
    }
    if (activeView === "history") {
      return () => {
        cancelled = true;
      };
    }

    const daysNeeded = activeView === "appointments" ? 60 : 14;
    if (agendaDaysLoaded >= daysNeeded) {
      return () => {
        cancelled = true;
      };
    }

    setPatientAgendaLoading(true);
    const fastQuery = `?upcoming_days=${daysNeeded}&skip_google=1`;
    const fullQuery = `?upcoming_days=${daysNeeded}`;
    api
      .tenantGetPatientAppointments(tenantPatientPhone, fastQuery)
      .then((res) => {
        if (cancelled) return;
        const slots = Array.isArray(res?.slots) ? res.slots : [];
        setTenantAgendaRawSlots(slots as Array<Record<string, unknown>>);
      })
      .catch(() => {
        if (!cancelled) setTenantAgendaRawSlots([]);
      })
      .then(() => {
        // Enrichissement Google : indispensable car certains patients n'ont leurs
        // RDV à venir que dans Google Calendar (aucun miroir local / public_booking).
        // Chaîné ici (et plus dans un setTimeout annulé par le re-run de l'effet)
        // pour qu'il s'exécute réellement, en overview comme dans l'onglet RDV.
        if (cancelled) return undefined;
        return api
          .tenantGetPatientAppointments(tenantPatientPhone, fullQuery)
          .then((fullRes) => {
            if (cancelled) return;
            const fullSlots = Array.isArray(fullRes?.slots) ? fullRes.slots : [];
            if (fullSlots.length) {
              setTenantAgendaRawSlots(fullSlots as Array<Record<string, unknown>>);
            }
          })
          .catch(() => {});
      })
      .finally(() => {
        // On ne marque la fenêtre comme chargée qu'à la toute fin : poser
        // agendaDaysLoaded plus tôt relançait l'effet et annulait le fetch Google.
        if (!cancelled) {
          setAgendaDaysLoaded(daysNeeded);
          setPatientAgendaLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeView, agendaDaysLoaded, agendaRefreshNonce, tenantPatientPhone]);

  useEffect(() => {
    let cancelled = false;
    const shouldLoad = !!tenantPatientPhone && (activeView === "history" || modal === "history");
    if (!shouldLoad) {
      return () => {
        cancelled = true;
      };
    }
    setPatientHistoryLoading(true);
    api
      .tenantGetPatientHistory(tenantPatientPhone, "?limit=50")
      .then((res) => {
        if (cancelled) return;
        setPatientHistory(mapPatientHistoryItems(res?.items));
      })
      .catch(() => {
        if (!cancelled) setPatientHistory([]);
      })
      .finally(() => {
        if (!cancelled) setPatientHistoryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tenantPatientPhone, activeView, modal, patientFetchNonce]);

  useEffect(() => {
    let cancelled = false;
    if (!tenantPatientPhone) {
      setPatientConsultations([]);
      setPatientConsultationsLoading(false);
      return () => {
        cancelled = true;
      };
    }
    setPatientConsultationsLoading(true);
    api
      .tenantListPatientConsultations(tenantPatientPhone, "?limit=20")
      .then((res) => {
        if (cancelled) return;
        const rows = Array.isArray(res?.items) ? res.items : [];
        const mapped = rows.map(mapPatientConsultationRow).filter((row): row is PatientConsultationRow => Boolean(row));
        setPatientConsultations(mapped);
      })
      .catch(() => {
        // Conserver la dernière liste connue évite l'effet "plus aucune fiche"
        // quand un refresh réseau échoue juste après un enregistrement réussi.
      })
      .finally(() => {
        if (!cancelled) setPatientConsultationsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tenantPatientPhone, patientFetchNonce, summaryRefreshNonce]);

  const refreshPatientAgenda = useCallback(() => {
    setAgendaDaysLoaded(0);
    setAgendaRefreshNonce((n) => n + 1);
  }, []);

  const downloadConsultationPdf = useCallback(async (item: PatientConsultationRow) => {
    if (!tenantPatientPhone) {
      notify("Sélectionnez d'abord un patient.", { sticky: true });
      return;
    }
    if (!item?.consultationId) {
      notify("Consultation introuvable.", { sticky: true });
      return;
    }
    try {
      const blob = await api.tenantFetchPatientConsultationPdf(tenantPatientPhone, item.consultationId);
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const isoDate = String((item.source?.date_consultation as string) || "").trim().slice(0, 10) || new Date().toISOString().slice(0, 10);
      anchor.href = objectUrl;
      anchor.download = `consultation-${isoDate}-${item.consultationId}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1200);
      notify("PDF de consultation téléchargé.");
    } catch (e) {
      const message = (e as Error)?.message || "Impossible de télécharger le PDF de la consultation.";
      notify(message, { sticky: true });
    }
  }, [tenantPatientPhone, notify]);

  const viewApptInAgenda = useCallback((
    slot: Record<string, unknown>,
    start: Date,
  ) => {
    navigate(buildAgendaViewUrl({
      date: start.toISOString().slice(0, 10),
      phone: tenantPatientPhone,
      slot,
    }));
  }, [navigate, tenantPatientPhone]);

  const goBackToPatientList = useCallback(() => {
    const np = new URLSearchParams(searchParams);
    np.delete("phone");
    setSearchParams(np, { replace: true });
  }, [searchParams, setSearchParams]);

  const consultationPatient = useMemo(() => {
    const row = patientCabinetRow || {};
    const rawAge = Number((row as { age?: unknown }).age);
    const ageFromBirth = computeAgeFromBirthDate((row as { birth_date?: unknown }).birth_date);
    const age = Number.isFinite(rawAge) && rawAge > 0 ? rawAge : ageFromBirth ?? 32;
    const sex = String(
      (row as { sexe?: unknown; sex?: unknown; gender?: unknown }).sexe
      || (row as { sex?: unknown }).sex
      || (row as { gender?: unknown }).gender
      || "",
    ).trim();
    const readProfileField = (keys: string[]) => {
      for (const key of keys) {
        const value = String((row as Record<string, unknown>)[key] || "").trim();
        if (value) return value;
      }
      return "";
    };
    return {
      id: tenantPatientPhone || "patient",
      nom: displayHero?.name || "Patient",
      age,
      sexe: sex,
      antecedents_medicaux: readProfileField([
        "antecedents_medicaux",
        "medical_history",
        "medical_antecedents",
      ]),
      antecedents_chirurgicaux: readProfileField([
        "antecedents_chirurgicaux",
        "surgical_history",
        "surgical_antecedents",
      ]),
      allergies: readProfileField(["allergies", "allergy_history"]),
      traitements: readProfileField([
        "traitements",
        "traitements_en_cours",
        "current_treatments",
      ]),
      facteurs_risque: readProfileField(["facteurs_risque", "risk_factors"]),
      points_attention: readProfileField(["points_attention", "attention_points"]),
      synthese_medicale: readProfileField(["synthese_medicale", "medical_summary"]),
      dernier_contexte_consultation: readProfileField([
        "dernier_contexte_consultation",
        "last_consultation_context",
      ]),
    };
  }, [patientCabinetRow, tenantPatientPhone, displayHero?.name]);

  const openConsultationModal = useCallback((preset?: Partial<ConsultationOpenDraft>) => {
    if (!tenantPatientPhone) {
      notify("Sélectionnez d'abord un patient pour créer une fiche consultation.", { sticky: true });
      return;
    }
    const todayIso = new Date().toISOString().slice(0, 10);
    setConsultationInitialDraft({
      ...CONSULTATION_DRAFT_EMPTY,
      date: todayIso,
      motif: "Consultation",
      ...(preset || {}),
    });
    setModal("createConsultation");
  }, [tenantPatientPhone, notify]);

  const duplicateLatestConsultation = useCallback(() => {
    if (!patientConsultations.length) {
      notify("Aucune consultation précédente à dupliquer.");
      return;
    }
    const latest = patientConsultations[0];
    const source = latest.source || {};
    openConsultationModal({
      date: new Date().toISOString().slice(0, 10),
      motif: String(source.motif || latest.motif || "Consultation").trim() || "Consultation",
      appointmentId: "",
      sourceConsultationId: String(latest.consultationId || ""),
      prefill: buildConsultationPrefillFromSource(source),
    });
    notify("Nouvelle fiche préremplie depuis la dernière consultation.");
  }, [patientConsultations, notify, openConsultationModal]);

  const editConsultation = useCallback((item: PatientConsultationRow) => {
    const source = item.source || {};
    const dateRaw = String(source.date_consultation || "").trim().slice(0, 10);
    const appointmentId = String(source.appointment_id || "").trim();
    openConsultationModal({
      consultationId: String(item.consultationId || ""),
      date: /^\d{4}-\d{2}-\d{2}$/.test(dateRaw) ? dateRaw : new Date().toISOString().slice(0, 10),
      motif: String(source.motif || item.motif || "Consultation").trim() || "Consultation",
      appointmentId,
      sourceConsultationId: String(item.consultationId || ""),
      prefill: buildConsultationPrefillFromSource(source),
    });
    notify("Mode modification activé pour cette fiche consultation.");
  }, [notify, openConsultationModal]);

  const deleteConsultation = useCallback(async (item: PatientConsultationRow) => {
    if (!tenantPatientPhone) {
      notify("Sélectionnez d'abord un patient.", { sticky: true });
      return;
    }
    if (consultationSaving) {
      notify("Une sauvegarde est déjà en cours.", { sticky: true });
      return;
    }
    if (!item?.consultationId) {
      notify("Consultation introuvable.", { sticky: true });
      return;
    }
    if (!confirmImportantAction("Confirmer la suppression définitive de cette fiche consultation ?")) {
      return;
    }
    setConsultationDeletingId(item.consultationId);
    try {
      await api.tenantDeletePatientConsultation(tenantPatientPhone, item.consultationId);
      setPatientConsultations((prev) => prev.filter((row) => row.consultationId !== item.consultationId));
      if (lastSavedConsultationId === item.consultationId) setLastSavedConsultationId(null);
      setSummaryRefreshNonce((value) => value + 1);
      notify("Fiche consultation supprimée.");
    } catch (e) {
      const message = (e as Error)?.message || "Impossible de supprimer la fiche consultation.";
      notify(message, { sticky: true });
    } finally {
      setConsultationDeletingId(null);
    }
  }, [
    tenantPatientPhone,
    consultationSaving,
    confirmImportantAction,
    notify,
    lastSavedConsultationId,
  ]);

  const submitConsultationForm = useCallback(async (draft: Record<string, unknown>) => {
    if (!tenantPatientPhone) {
      const message = "Sélectionnez d'abord un patient.";
      notify(message, { sticky: true });
      throw new Error(message);
    }
    const dateValue = String(draft?.date || "").trim();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(dateValue)) {
      const message = "Date de consultation invalide.";
      notify(message, { sticky: true });
      throw new Error(message);
    }
    const motif = String(draft?.motif || "").trim();
    if (!motif) {
      const message = "Le motif est requis.";
      notify(message, { sticky: true });
      throw new Error(message);
    }
    const impression = String(draft?.impression_clinique || "").trim() || "À compléter";
    const examenClinique =
      draft?.examen_clinique && typeof draft.examen_clinique === "object"
        ? (draft.examen_clinique as Record<string, unknown>)
        : {};
    const constantesRaw =
      examenClinique.constantes && typeof examenClinique.constantes === "object"
        ? (examenClinique.constantes as Record<string, unknown>)
        : {};
    const conduiteRaw =
      draft?.conduite_a_tenir && typeof draft.conduite_a_tenir === "object"
        ? (draft.conduite_a_tenir as Record<string, unknown>)
        : {};
    const suiviRaw =
      conduiteRaw.suivi && typeof conduiteRaw.suivi === "object"
        ? (conduiteRaw.suivi as Record<string, unknown>)
        : {};
    const iaRaw =
      draft?.ia_uwi && typeof draft.ia_uwi === "object"
        ? (draft.ia_uwi as Record<string, unknown>)
        : {};
    const examensSeen = new Set<string>();
    const examensComplementaires = Array.isArray(conduiteRaw.examens_complementaires)
      ? conduiteRaw.examens_complementaires
          .map((item) => String(item || "").trim())
          .filter((item) => {
            if (!item) return false;
            const k = item.toLowerCase();
            if (examensSeen.has(k)) return false;
            examensSeen.add(k);
            return true;
          })
      : [];
    const prochainRdvRaw = String(suiviRaw.prochain_rdv || "").trim();
    const prochainRdv = /^\d{4}-\d{2}-\d{2}$/.test(prochainRdvRaw) ? prochainRdvRaw : undefined;
    const followupBookingRaw =
      draft?.rdv_suivi_booking && typeof draft.rdv_suivi_booking === "object"
        ? (draft.rdv_suivi_booking as Record<string, unknown>)
        : {};
    const wantsFollowupBooking = Boolean(followupBookingRaw.create);
    const followupBookingDate = String(followupBookingRaw.date || prochainRdv || "").trim();
    const followupBookingTime = String(followupBookingRaw.time || "").trim();
    const followupBookingMotif = String(followupBookingRaw.motif || motif || "Consultation de suivi").trim() || "Consultation de suivi";

    const constantes = {
      fc_bpm: parseOptionalIntInput(String(constantesRaw.fc_bpm ?? "")),
      pa_systolique: parseOptionalIntInput(String(constantesRaw.pa_systolique ?? "")),
      pa_diastolique: parseOptionalIntInput(String(constantesRaw.pa_diastolique ?? "")),
      temperature_c: parseOptionalFloatInput(String(constantesRaw.temperature_c ?? "")),
      spo2_pct: parseOptionalIntInput(String(constantesRaw.spo2_pct ?? "")),
      fr_min: parseOptionalIntInput(String(constantesRaw.fr_min ?? "")),
      poids_kg: parseOptionalFloatInput(String(constantesRaw.poids_kg ?? "")),
      taille_cm: parseOptionalIntInput(String(constantesRaw.taille_cm ?? "")),
      imc: parseOptionalFloatInput(String(constantesRaw.imc ?? "")),
    };
    const iaResume = String(iaRaw.resume_consultation || "").trim();
    const iaContexte = String(iaRaw.contexte_patient || "").trim();
    const iaValidated = Boolean(iaRaw.validated_by_practitioner);
    const includeIa = Boolean(
      iaResume || iaContexte || iaValidated,
    );

    const payload = {
      appointment_id: String(draft?.appointment_id || consultationInitialDraft.appointmentId || "").trim() || undefined,
      date: dateValue,
      mode_consultation: draft?.mode_consultation === "complete" ? "complete" : "rapide",
      motif,
      anamnese: String(draft?.anamnese || "").trim(),
      examen_clinique: {
        etat_general: String(examenClinique.etat_general || "").trim(),
        examen_physique: String(examenClinique.examen_physique || "").trim(),
        constantes,
      },
      impression_clinique: impression,
      cim10: String(draft?.cim10 || "").trim() || undefined,
      conduite_a_tenir: {
        examens_complementaires: examensComplementaires,
        prescription: String(conduiteRaw.prescription || "").trim(),
        orientation: String(conduiteRaw.orientation || "").trim(),
        suivi: {
          prochain_rdv: prochainRdv,
          consignes: String(suiviRaw.consignes || "").trim(),
        },
      },
      ia_uwi: includeIa
        ? {
            resume_consultation: iaResume,
            contexte_patient: iaContexte,
            validated_by_practitioner: iaValidated,
          }
        : undefined,
      note_praticien: String(draft?.note_praticien || "").trim() || undefined,
    };
    const editingConsultationId = Number(String(consultationInitialDraft.consultationId || "").trim());
    const isEditingConsultation = Number.isFinite(editingConsultationId) && editingConsultationId > 0;
    const consultationAppointmentId = String(payload.appointment_id || "").trim();
    const canCreateFollowupBooking = wantsFollowupBooking && !consultationAppointmentId;
    if (canCreateFollowupBooking) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(followupBookingDate)) {
        const message = "Date invalide pour créer le prochain rendez-vous.";
        notify(message, { sticky: true });
        throw new Error(message);
      }
      if (!/^\d{2}:\d{2}$/.test(followupBookingTime)) {
        const message = "Heure invalide pour créer le prochain rendez-vous.";
        notify(message, { sticky: true });
        throw new Error(message);
      }
    }

    setConsultationSaving(true);
    try {
      const saveResponse = (isEditingConsultation
        ? await api.tenantUpdatePatientConsultation(tenantPatientPhone, editingConsultationId, payload)
        : await api.tenantCreatePatientConsultation(tenantPatientPhone, payload)
      ) as {
        consultation?: unknown;
      };
      const savedConsultationRow = mapPatientConsultationRow(saveResponse?.consultation);
      if (savedConsultationRow) {
        setPatientConsultations((prev) => [
          savedConsultationRow,
          ...prev.filter((item) => item.consultationId !== savedConsultationRow.consultationId),
        ]);
        setLastSavedConsultationId(savedConsultationRow.consultationId);
      }
      let followupBookingCreated = false;
      let followupBookingSkippedReason = "";
      if (wantsFollowupBooking) {
        if (consultationAppointmentId) {
          followupBookingSkippedReason = "un rendez-vous est déjà rattaché à cette consultation.";
        } else {
          const startIso = buildCabinetBookingStartIso(followupBookingDate, followupBookingTime);
          if (!startIso) {
            throw new Error("Date/heure du prochain rendez-vous invalide.");
          }
          try {
            await api.tenantCreateAgendaBooking({
              patient_name: String(displayHero?.name || "Patient").trim() || "Patient",
              patient_phone: tenantPatientPhone,
              patient_email: String(patientEmail || "").trim(),
              motif: followupBookingMotif,
              start_iso: startIso,
            });
            followupBookingCreated = true;
            refreshPatientAgenda();
          } catch (bookingErr) {
            const detail = String((bookingErr as Error)?.message || "").trim();
            followupBookingSkippedReason = detail || "impossible de créer le rendez-vous dans l'agenda.";
            notify(
              `Fiche enregistrée, mais le prochain rendez-vous n'a pas été créé (${followupBookingSkippedReason}).`,
              { sticky: true },
            );
          }
        }
      }
      // Pas de re-fetch bloquant ici: l'objectif est de confirmer l'enregistrement
      // le plus vite possible pour éviter l'effet "spinner infini".
      if (followupBookingCreated) {
        notify(
          `${isEditingConsultation ? "Fiche consultation mise à jour" : "Fiche consultation enregistrée"} (bloc "Dossier consultations"). Prochain rendez-vous créé le ${formatLongDateFR(followupBookingDate)} à ${formatTimeChoiceFR(followupBookingTime)}.`,
        );
      } else if (followupBookingSkippedReason) {
        notify(`${isEditingConsultation ? "Fiche consultation mise à jour" : "Fiche consultation enregistrée"} (bloc "Dossier consultations"). Prochain rendez-vous: ${followupBookingSkippedReason}`);
      } else {
        notify(`${isEditingConsultation ? "Fiche consultation mise à jour" : "Fiche consultation enregistrée"}. Retrouvez-la dans "Dossier consultations".`);
      }
      setModal(null);
      setSummaryRefreshNonce((value) => value + 1);
      window.setTimeout(() => {
        consultationDossierRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 120);
      setConsultationInitialDraft((prev) => ({
        ...CONSULTATION_DRAFT_EMPTY,
        consultationId: "",
        date: prev.date || new Date().toISOString().slice(0, 10),
        motif: prev.motif || "Consultation",
        appointmentId: prev.appointmentId || "",
      }));
      return {
        ok: true,
        followupBookingCreated,
        followupBookingSkippedReason,
      };
    } catch (e) {
      const message = (e as Error)?.message || "Impossible d'enregistrer la fiche consultation.";
      notify(message, { sticky: true });
      throw new Error(message);
    } finally {
      setConsultationSaving(false);
    }
  }, [
    consultationInitialDraft.appointmentId,
    consultationInitialDraft.consultationId,
    tenantPatientPhone,
    notify,
    displayHero?.name,
    patientEmail,
    refreshPatientAgenda,
    consultationDossierRef,
  ]);

  const generateConsultationSummary = useCallback(async (draft: Record<string, unknown>) => {
    const payload = {
      ...(draft || {}),
      patient_phone: tenantPatientPhone || undefined,
    };
    const res = await api.tenantGenerateConsultationSummary(payload) as {
      resume?: unknown;
      contexte?: unknown;
      is_fallback?: unknown;
      source?: unknown;
    };
    if (Boolean(res?.is_fallback)) {
      notify("Synthèse IA indisponible: version de secours générée.", { sticky: true });
    }
    return {
      resume: String(res?.resume || ""),
      contexte: String(res?.contexte || ""),
    };
  }, [tenantPatientPhone, notify]);

  const loadConsultationPrefill = useCallback(async () => {
    if (!tenantPatientPhone) return null;
    return api.tenantGetPatientConsultationPrefill(tenantPatientPhone);
  }, [tenantPatientPhone]);

  const transcribeConsultationAudio = useCallback(async (audioBlob: Blob) => {
    if (!(audioBlob instanceof Blob)) {
      throw new Error("Audio de dictée invalide.");
    }
    return api.tenantTranscribeConsultation(audioBlob, tenantPatientPhone || "");
  }, [tenantPatientPhone]);

  useEffect(() => {
    const wantsConsultation = (searchParams.get("consultation") || "").trim() === "1";
    if (!wantsConsultation) {
      consultationAutoOpenRef.current = false;
      return;
    }

    if (!tenantPatientPhone) {
      if (!consultationAutoOpenRef.current) {
        notify("Sélectionnez d'abord un patient pour ouvrir la fiche consultation.", { sticky: true });
      }
      return;
    }
    if (consultationAutoOpenRef.current) return;
    consultationAutoOpenRef.current = true;

    const dateFromQuery = String(searchParams.get("consultationDate") || "").trim();
    const motifFromQuery = String(searchParams.get("consultationMotif") || "").trim();
    const appointmentIdFromQuery = String(searchParams.get("consultationAppointmentId") || "").trim();
    openConsultationModal({
      date: /^\d{4}-\d{2}-\d{2}$/.test(dateFromQuery)
        ? dateFromQuery
        : new Date().toISOString().slice(0, 10),
      motif: motifFromQuery || "Consultation",
      appointmentId: appointmentIdFromQuery,
    });

    const next = new URLSearchParams(searchParams);
    next.delete("consultation");
    next.delete("consultationDate");
    next.delete("consultationMotif");
    next.delete("consultationAppointmentId");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams, tenantPatientPhone, openConsultationModal, notify]);

  const openCancelApptModal = useCallback((slot: Record<string, unknown>, start: Date) => {
    setApptActionTarget({ slot, start });
    setModal("cancelAppt");
  }, []);

  const openRescheduleApptModal = useCallback((slot: Record<string, unknown>, start: Date) => {
    setApptActionTarget({ slot, start });
    setModal("rescheduleAppt");
  }, []);

  const closeApptActionModal = useCallback(() => {
    if (apptActionLoading) return;
    setModal(null);
    setApptActionTarget(null);
  }, [apptActionLoading]);

  const renderPatientApptActions = useCallback((
    slot: Record<string, unknown>,
    start: Date,
    { compact = false }: { compact?: boolean } = {},
  ) => {
    const canCancel = canCancelAgendaSlot(slot);
    const canOpenReschedule = canOpenReschedulePatientAppt(slot, start);
    const isPast = isAgendaSlotPast(start);
    const handleReschedule = () => {
      if (isPast) {
        notify("Impossible de déplacer un rendez-vous passé.");
        return;
      }
      if (!canOpenReschedule) {
        notify("Déplacement indisponible pour ce rendez-vous.", { sticky: true });
        return;
      }
      openRescheduleApptModal(slot, start);
    };
    return (
      <div className={`flex flex-wrap gap-2${compact ? "" : " mt-5"}`}>
        <button
          type="button"
          disabled={isPast || !canOpenReschedule}
          onClick={handleReschedule}
          className="rounded-xl border border-[#72CDE0] px-4 py-2 text-sm font-black text-[#008EA1] hover:bg-[#E9FAFC] disabled:cursor-not-allowed disabled:opacity-50"
        >
          ▣ Déplacer le RDV
        </button>
        <button
          type="button"
          disabled={!canCancel}
          onClick={() => openCancelApptModal(slot, start)}
          className="rounded-xl border border-[#FF9B9B] px-4 py-2 text-sm font-black text-[#FF3030] hover:bg-[#FFF1F1] disabled:cursor-not-allowed disabled:opacity-50"
        >
          ♲ Annuler le RDV
        </button>
        {!compact ? (
          <button
            type="button"
            onClick={() => viewApptInAgenda(slot, start)}
            className="rounded-xl border border-[#B6C3D7] px-4 py-2 text-sm font-black text-[#53647F] hover:bg-[#F8FAFC]"
          >
            ▣ Voir le RDV dans l&apos;agenda
          </button>
        ) : (
          <button
            type="button"
            onClick={() => viewApptInAgenda(slot, start)}
            className="rounded-xl border border-[#B6C3D7] px-3 py-2 text-xs font-black text-[#53647F] hover:bg-[#F8FAFC]"
          >
            Voir dans l&apos;agenda
          </button>
        )}
      </div>
    );
  }, [notify, openCancelApptModal, openRescheduleApptModal, viewApptInAgenda]);

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
  const consultationExistingNextAppointment = useMemo(() => {
    if (!upcomingPatientAppointments.length) return null;
    const next = upcomingPatientAppointments[0];
    const start = next.start;
    return {
      dateLabel: start.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" }),
      timeLabel: formatAgendaSlotHour(start),
      motif: agendaSlotMotif(next.slot) || "Consultation",
    };
  }, [upcomingPatientAppointments]);

  const pastPatientAppointments = patientPastAppointments;

  useEffect(() => {
    if (modal !== "profile") return;
    if (urlPatientHero?.name) setProfileNameDraft(urlPatientHero.name);
    setProfileBirthDateDraft(String(patientCabinetRow?.birth_date || "").trim().slice(0, 10));
    setProfilePhysicianDraft(String(patientCabinetRow?.treating_physician_name || "").trim());
    setProfilePhysicianCityDraft(String(patientCabinetRow?.treating_physician_city || "").trim());
    setProfileMedicalAntecedentsDraft(String(patientCabinetRow?.antecedents_medicaux || "").trim());
    setProfileSurgicalAntecedentsDraft(String(patientCabinetRow?.antecedents_chirurgicaux || "").trim());
    setProfileAllergiesDraft(String(patientCabinetRow?.allergies || "").trim());
    setProfileTreatmentsDraft(String(patientCabinetRow?.traitements || "").trim());
    setProfileRiskFactorsDraft(String(patientCabinetRow?.facteurs_risque || "").trim());
    setProfileAttentionPointsDraft(String(patientCabinetRow?.points_attention || "").trim());
    setProfileMedicalSummaryDraft(String(patientCabinetRow?.synthese_medicale || "").trim());
    setProfileLastConsultationContextDraft(String(patientCabinetRow?.dernier_contexte_consultation || "").trim());
  }, [modal, urlPatientHero?.name, patientCabinetRow]);

  const createPatientFichePractice = useCallback(
    async (validatedName: string, opts?: { silent?: boolean }) => {
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
          setPatientCabinetRow((prev) => ({ ...(prev || {}), ...profile }));
          setPatientEmail(String(profile.email || ""));
        }
        setTenantPatientNotFound(false);
        if (!opts?.silent) {
          notify(res?.register_mode === "updated" ? "Fiche mise à jour" : "Fiche patient enregistrée");
        }
        setPatientFetchNonce((n) => n + 1);
        await loadTenantSidebarPatients({ force: true });
        return true;
      } catch (e) {
        console.error("[fiche.create] failure", debugCtx, e);
        const dup = parsePatientDuplicateError(e as Error & { data?: { detail?: unknown } });
        notify(dup.message || (e as Error)?.message || "Impossible d’enregistrer la fiche", { sticky: true });
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

  const openManualPatientCreateModal = () => {
    setManualPatientCreateForm(MANUAL_PATIENT_CREATE_EMPTY);
    setManualPatientCreateConflicts([]);
    setModal("createPatientManual");
  };

  const submitManualPatientCreate = async () => {
    if (manualPatientCreateSaving) return;
    const validated = validatePatientCreateFormForSubmit(manualPatientCreateForm);
    if (!validated.ok) {
      notify(validated.message || "Complétez le formulaire.", { sticky: true });
      return;
    }

    let conflicts = manualPatientCreateConflicts;
    try {
      const dupRes = await checkPatientDuplicates({ phone: validated.phone, email: validated.email });
      conflicts = Array.isArray(dupRes?.conflicts) ? dupRes.conflicts : [];
      setManualPatientCreateConflicts(conflicts);
      if (hasBlockingPatientDuplicate(conflicts)) {
        notify(formatPatientDuplicateConflict(conflicts[0]) || "Ce numéro ou cet email existe déjà.", {
          sticky: true,
        });
        return;
      }
    } catch {
      // best effort; le backend reste la source de vérité
    }

    setManualPatientCreateSaving(true);
    try {
      const res = await api.tenantRegisterPatient({
        patient_phone: validated.phone,
        validated_name: validated.name,
        raw_name: validated.name,
        first_name: validated.firstName || undefined,
        last_name: validated.lastName || undefined,
        patient_email: validated.email || undefined,
        birth_date: validated.birthDate || undefined,
        treating_physician_name: validated.treatingPhysicianName || undefined,
        treating_physician_city: validated.treatingPhysicianCity || undefined,
        initial_note: String(manualPatientCreateForm.initialNote || "").trim() || undefined,
      });
      const createdPhone = normalizePhone(
        String((res?.patient as Record<string, unknown> | undefined)?.phone || validated.phone),
      );
      await loadTenantSidebarPatients({ force: true });
      setModal(null);
      setManualPatientCreateForm(MANUAL_PATIENT_CREATE_EMPTY);
      setManualPatientCreateConflicts([]);
      notify(
        res?.register_mode === "updated"
          ? "Fiche patient mise à jour."
          : res?.register_mode === "completed"
            ? "Fiche patient complétée."
            : "Fiche patient créée.",
      );
      if (createdPhone) {
        const next = new URLSearchParams(searchParams);
        next.set("phone", createdPhone);
        setSearchParams(next, { replace: true });
      }
    } catch (e) {
      const dup = parsePatientDuplicateError(e as Error & { data?: { detail?: unknown } });
      notify(dup.message || (e as Error)?.message || "Impossible de créer la fiche patient.", { sticky: true });
    } finally {
      setManualPatientCreateSaving(false);
    }
  };

  const saveProfileFromModal = async () => {
    if (!tenantPatientPhone) return;
    const name = profileNameDraft.trim();
    if (name.length < 2) {
      notify("Saisissez un nom valide (au moins 2 caractères).", { sticky: true });
      return;
    }
    if (!confirmImportantAction("Confirmer l'enregistrement des modifications de la fiche patient ?")) {
      return;
    }
    setProfileSaveSaving(true);
    try {
      if (tenantPatientNotFound) {
        const okName = await createPatientFichePractice(name, { silent: true });
        if (!okName) return;
      }
      const birthDate = profileBirthDateDraft.trim();
      const physician = profilePhysicianDraft.trim();
      const physicianCity = profilePhysicianCityDraft.trim();
      const medicalAntecedents = profileMedicalAntecedentsDraft.trim();
      const surgicalAntecedents = profileSurgicalAntecedentsDraft.trim();
      const allergies = profileAllergiesDraft.trim();
      const treatments = profileTreatmentsDraft.trim();
      const riskFactors = profileRiskFactorsDraft.trim();
      const attentionPoints = profileAttentionPointsDraft.trim();
      const medicalSummary = profileMedicalSummaryDraft.trim();
      const lastConsultationContext = profileLastConsultationContextDraft.trim();
      const res = await api.tenantUpdatePatient(tenantPatientPhone, {
        validated_name: name,
        raw_name: name,
        birth_date: birthDate,
        treating_physician_name: physician,
        treating_physician_city: physicianCity,
        antecedents_medicaux: medicalAntecedents,
        antecedents_chirurgicaux: surgicalAntecedents,
        allergies,
        traitements: treatments,
        facteurs_risque: riskFactors,
        points_attention: attentionPoints,
        synthese_medicale: medicalSummary,
        dernier_contexte_consultation: lastConsultationContext,
      });
      const savedDisplayName =
        String((res?.patient as Record<string, unknown> | undefined)?.display_name || name).trim() || name;
      const savedPatient = {
        ...(patientCabinetRow || {}),
        ...(res?.patient as Record<string, unknown> | undefined),
        validated_name: String((res?.patient as Record<string, unknown> | undefined)?.validated_name || name),
        raw_name: String((res?.patient as Record<string, unknown> | undefined)?.raw_name || name),
        display_name: savedDisplayName,
        birth_date: String((res?.patient as Record<string, unknown> | undefined)?.birth_date || birthDate),
        treating_physician_name: String(
          (res?.patient as Record<string, unknown> | undefined)?.treating_physician_name || physician,
        ),
        treating_physician_city: String(
          (res?.patient as Record<string, unknown> | undefined)?.treating_physician_city || physicianCity,
        ),
        antecedents_medicaux: String(
          (res?.patient as Record<string, unknown> | undefined)?.antecedents_medicaux || medicalAntecedents,
        ),
        antecedents_chirurgicaux: String(
          (res?.patient as Record<string, unknown> | undefined)?.antecedents_chirurgicaux || surgicalAntecedents,
        ),
        allergies: String((res?.patient as Record<string, unknown> | undefined)?.allergies || allergies),
        traitements: String((res?.patient as Record<string, unknown> | undefined)?.traitements || treatments),
        facteurs_risque: String((res?.patient as Record<string, unknown> | undefined)?.facteurs_risque || riskFactors),
        points_attention: String(
          (res?.patient as Record<string, unknown> | undefined)?.points_attention || attentionPoints,
        ),
        synthese_medicale: String(
          (res?.patient as Record<string, unknown> | undefined)?.synthese_medicale || medicalSummary,
        ),
        dernier_contexte_consultation: String(
          (res?.patient as Record<string, unknown> | undefined)?.dernier_contexte_consultation || lastConsultationContext,
        ),
      };
      setPatientCabinetRow(savedPatient);
      setUrlPatientHero((prev) =>
        prev
          ? { ...prev, name: savedDisplayName, initials: initialsFromFullName(savedDisplayName) }
          : { name: savedDisplayName, phone: tenantPatientPhone, initials: initialsFromFullName(savedDisplayName) },
      );
      const cached = patientDetailCacheRef.current.get(tenantPatientPhone);
      if (cached) {
        patientDetailCacheRef.current.set(tenantPatientPhone, {
          ...cached,
          patientCabinetRow: savedPatient,
        });
      }
      notify("Profil enregistré");
      setModal(null);
    } catch (e) {
      notify((e as Error)?.message || "Impossible d'enregistrer le profil", { sticky: true });
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
      await loadTenantSidebarPatients({ force: true });
      const np = new URLSearchParams(searchParams);
      np.delete("phone");
      setSearchParams(np, { replace: true });
    } catch (e) {
      notify((e as Error)?.message || "Erreur suppression fiche", { sticky: true });
    } finally {
      setDeleteSaving(false);
    }
  };

  const confirmCancelPatientAppointment = useCallback(async () => {
    if (!apptActionTarget) return;
    const { slot } = apptActionTarget;
    const actionId = appointmentActionId(slot);
    if (!actionId) {
      notify("Impossible d’annuler ce rendez-vous (identifiant manquant).", { sticky: true });
      return;
    }
    setApptActionLoading(true);
    try {
      await api.tenantCancelAgendaAppointment(actionId, agendaCancelPayload(slot));
      notify("Rendez-vous annulé. Le patient a été notifié par SMS.");
      setModal(null);
      setApptActionTarget(null);
      refreshPatientAgenda();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Impossible d’annuler ce rendez-vous.";
      notify(msg, { sticky: true });
    } finally {
      setApptActionLoading(false);
    }
  }, [apptActionTarget, refreshPatientAgenda]);

  const confirmReschedulePatientAppointment = useCallback(async (newSlot: { slot_id: number; date: string; time: string }) => {
    if (!apptActionTarget) return;
    const { slot } = apptActionTarget;
    const apptId = appointmentLocalId(slot);
    if (!apptId) {
      notify("Déplacement impossible : rendez-vous introuvable en base UWi.", { sticky: true });
      return;
    }
    setApptActionLoading(true);
    try {
      const res = await api.tenantRescheduleAgendaAppointment(String(apptId), agendaReschedulePayload(slot, newSlot.slot_id));
      const syncedGoogle = res?.provider === "google+local" || res?.google_synced === true;
      notify(
        syncedGoogle
          ? `Rendez-vous déplacé sur UWi et Google Calendar au ${newSlot.date} à ${newSlot.time}.`
          : `Rendez-vous déplacé au ${newSlot.date} à ${newSlot.time}.`,
      );
      setModal(null);
      setApptActionTarget(null);
      refreshPatientAgenda();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Impossible de déplacer ce rendez-vous.";
      notify(msg, { sticky: true });
    } finally {
      setApptActionLoading(false);
    }
  }, [apptActionTarget, refreshPatientAgenda]);

  const saveNote = async () => {
    if (!note.trim()) {
      notify("Ajoute une note avant d'enregistrer");
      return false;
    }
    if (!tenantPatientPhone) {
      notify("Aucun patient sélectionné");
      return false;
    }
    if (!confirmImportantAction("Confirmer l'enregistrement de cette note dans le dossier patient ?")) {
      return false;
    }
    setNotesSaving(true);
    const noteText = note.trim();
    try {
      const res = await api.tenantCreatePatientNote(tenantPatientPhone, { text: noteText, author: "Praticien" });
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
      setSummaryRefreshNonce((n) => n + 1);
      if (String(created?.text || noteText).includes("[ABSENCE-RDV]")) {
        setPatientFetchNonce((n) => n + 1);
      }
      return true;
    } catch (e) {
      notify((e as Error)?.message || "Erreur ajout note");
      return false;
    } finally {
      setNotesSaving(false);
    }
  };

  const releaseNoteStream = useCallback(() => {
    const stream = noteStreamRef.current;
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      noteStreamRef.current = null;
    }
  }, []);

  const transcribeNoteBlob = useCallback(
    async (blob: Blob) => {
      if (!blob || blob.size === 0) return;
      setNoteTranscribing(true);
      try {
        const res = await api.tenantTranscribeNote(blob);
        const text = String(res?.transcription || "").trim();
        if (text) {
          setNote((prev) => {
            const sep = prev && !/\s$/.test(prev) ? " " : "";
            return prev + sep + text;
          });
        } else {
          notify("Aucune parole détectée. Réessayez ou saisissez la note.");
        }
      } catch (e) {
        notify((e as Error)?.message || "La dictée n'a pas pu être transcrite.", { sticky: true });
      } finally {
        setNoteTranscribing(false);
      }
    },
    [notify],
  );

  const stopNoteDictation = useCallback(() => {
    const rec = noteRecorderRef.current;
    if (rec && rec.state === "recording") {
      try {
        rec.stop();
      } catch {
        releaseNoteStream();
        setNoteRecording(false);
      }
    } else {
      releaseNoteStream();
      setNoteRecording(false);
    }
  }, [releaseNoteStream]);

  const toggleNoteDictation = useCallback(async () => {
    if (noteRecording) {
      stopNoteDictation();
      return;
    }
    if (noteTranscribing) return;
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      notify("La dictée vocale n'est pas disponible sur ce navigateur/appareil.", { sticky: true });
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      noteStreamRef.current = stream;
      const rec = new MediaRecorder(stream);
      noteChunksRef.current = [];
      rec.ondataavailable = (event) => {
        if (event.data && event.data.size) noteChunksRef.current.push(event.data);
      };
      rec.onstop = () => {
        const blob = new Blob(noteChunksRef.current, { type: rec.mimeType || "audio/webm" });
        releaseNoteStream();
        setNoteRecording(false);
        void transcribeNoteBlob(blob);
      };
      rec.start();
      noteRecorderRef.current = rec;
      setNoteRecording(true);
    } catch (e) {
      releaseNoteStream();
      setNoteRecording(false);
      const name = (e as Error)?.name || "";
      notify(
        name === "NotAllowedError" || name === "SecurityError"
          ? "Micro non autorisé. Autorisez l'accès au microphone dans le navigateur."
          : "Impossible d'accéder au microphone.",
        { sticky: true },
      );
    }
  }, [noteRecording, noteTranscribing, stopNoteDictation, releaseNoteStream, transcribeNoteBlob, notify]);

  const closeNoteModal = useCallback(() => {
    stopNoteDictation();
    setModal(null);
  }, [stopNoteDictation]);

  const reportAppointmentAbsence = async (start: Date) => {
    if (!tenantPatientPhone) {
      notify("Aucun patient sélectionné");
      return;
    }
    if (!confirmImportantAction("Confirmer l'enregistrement de cette absence dans les notes patient ?")) {
      return;
    }
    const rowKey = start.toISOString();
    setAbsenceNoteSavingKey(rowKey);
    try {
      const text = buildAbsenceNoteText(start);
      const res = await api.tenantCreatePatientNote(tenantPatientPhone, { text, author: "Praticien" });
      const created = res?.item;
      if (created) {
        setPatientNotes((prev) => [
          {
            id: Number(created.id),
            text: String(created.text || text),
            author: String(created.author || "Praticien"),
            created_at: String(created.created_at || ""),
          },
          ...prev,
        ]);
      }
      setPatientFetchNonce((n) => n + 1);
      notify("Absence enregistrée dans les notes patient");
    } catch (e) {
      notify((e as Error)?.message || "Erreur lors du signalement d'absence");
    } finally {
      setAbsenceNoteSavingKey("");
    }
  };

  const toggleNoteExpanded = (noteId: number) => {
    setNoteExpandedIds((prev) => ({ ...prev, [noteId]: !prev[noteId] }));
  };

  const startNoteEdit = (item: PatientNote) => {
    setNoteEditingId(item.id);
    setNoteEditDraft(String(item.text || ""));
  };

  const cancelNoteEdit = () => {
    setNoteEditingId(null);
    setNoteEditDraft("");
  };

  const saveEditedNote = async (noteId: number) => {
    if (!tenantPatientPhone || !noteId) return false;
    const normalizedText = String(noteEditDraft || "").trim();
    if (!normalizedText) {
      notify("Ajoute une note avant d'enregistrer");
      return false;
    }
    if (!confirmImportantAction("Confirmer la modification de cette note patient ?")) return false;
    setNoteUpdatingId(noteId);
    try {
      const res = await api.tenantUpdatePatientNote(tenantPatientPhone, noteId, { text: normalizedText });
      const updated = res?.item;
      setPatientNotes((prev) =>
        prev.map((item) =>
          item.id === noteId
            ? {
              ...item,
              text: String(updated?.text || normalizedText),
              author: String(updated?.author || item.author || "Praticien"),
              created_at: String(updated?.created_at || item.created_at || ""),
            }
            : item,
        ),
      );
      setNoteEditingId(null);
      setNoteEditDraft("");
      notify("Note modifiée");
      setSummaryRefreshNonce((n) => n + 1);
      return true;
    } catch (e) {
      notify((e as Error)?.message || "Erreur modification note");
      return false;
    } finally {
      setNoteUpdatingId(null);
    }
  };

  const removeNote = async (noteId: number) => {
    if (!tenantPatientPhone || !noteId) return;
    if (!confirmImportantAction("Confirmer la suppression de cette note ?")) return;
    setNoteDeletingId(noteId);
    try {
      await api.tenantDeletePatientNote(tenantPatientPhone, noteId);
      setPatientNotes((prev) => prev.filter((item) => item.id !== noteId));
      setNoteExpandedIds((prev) => {
        const next = { ...prev };
        delete next[noteId];
        return next;
      });
      if (noteEditingId === noteId) {
        setNoteEditingId(null);
        setNoteEditDraft("");
      }
      notify("Note supprimée");
      setSummaryRefreshNonce((n) => n + 1);
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
      const docId = Number(created?.id);
      if (!created || !Number.isFinite(docId) || docId <= 0) {
        throw new Error("Document non enregistré sur le serveur");
      }
      const newDoc: PatientDocument = {
        id: docId,
        original_name: String(created.original_name || file.name),
        mime_type: String(created.mime_type || file.type || "application/octet-stream"),
        size_bytes: Number(created.size_bytes || file.size || 0),
        created_at: String(created.created_at || ""),
      };
      setDocuments((prev) => [newDoc, ...prev]);
      const cached = patientDetailCacheRef.current.get(tenantPatientPhone);
      if (cached) {
        patientDetailCacheRef.current.set(tenantPatientPhone, {
          ...cached,
          documents: [newDoc, ...cached.documents],
        });
      }
      setPatientFetchNonce((n) => n + 1);
      setModal(null);
      setActiveView("documents");
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
      const blob = await api.tenantFetchPatientDocument(tenantPatientPhone, doc.id);
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
      const blob = await api.tenantFetchPatientDocument(tenantPatientPhone, doc.id);
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

  const openSingleMessageModal = useCallback(
    (channel: MessageChannel) => {
      if (!tenantPatientPhone) {
        notify("Aucun patient sélectionné", { sticky: true });
        return;
      }
      if (channel === "email" && !patientEmail) {
        notify("Ajoute d'abord l'email du patient", { sticky: true });
        return;
      }
      setSingleMessageChannel(channel);
      setSingleMessageSubject("Message de votre cabinet");
      setSingleMessageBody("");
      setModal("sendSingleMessage");
    },
    [tenantPatientPhone, patientEmail, notify],
  );

  const sendSingleMessage = async () => {
    if (!tenantPatientPhone) {
      notify("Aucun patient sélectionné", { sticky: true });
      return;
    }
    const message = singleMessageBody.trim();
    if (!message) {
      notify("Saisissez un message.", { sticky: true });
      return;
    }
    if (singleMessageChannel === "email" && !patientEmail) {
      notify("Ajoute d'abord l'email du patient", { sticky: true });
      return;
    }
    const channelLabel = singleMessageChannel === "sms" ? "SMS" : "email";
    if (!confirmImportantAction(`Confirmer l'envoi du ${channelLabel} à ce patient ?`)) {
      return;
    }
    setSingleMessageSending(true);
    try {
      const payload: Record<string, string> = {
        channel: singleMessageChannel,
        message,
      };
      if (singleMessageChannel === "email") {
        payload.subject = singleMessageSubject.trim() || "Message de votre cabinet";
      }
      const res = await api.tenantSendPatientMessage(tenantPatientPhone, payload);
      notify(
        singleMessageChannel === "sms"
          ? `SMS envoyé à ${formatDisplayFrenchPhone(String(res?.sent_to || tenantPatientPhone))}`
          : `Email envoyé à ${String(res?.sent_to || patientEmail)}`,
      );
      setModal(null);
      setSingleMessageBody("");
    } catch (e) {
      notify((e as Error)?.message || "Erreur envoi message", { sticky: true });
    } finally {
      setSingleMessageSending(false);
    }
  };

  const openBulkMessageModal = () => {
    setBulkMessageChannel("sms");
    setBulkMessageSubject("Message de votre cabinet");
    setBulkMessageBody("");
    setBulkMessageSendToAll(false);
    setBulkModalQuery("");
    setModal("sendBulkMessage");
  };

  const sendBulkMessage = async () => {
    const message = bulkMessageBody.trim();
    if (!message) {
      notify("Saisissez un message pour l'envoi groupé.", { sticky: true });
      return;
    }
    if (!bulkMessageSendToAll && selectedPatientPhones.length === 0) {
      notify("Sélectionnez au moins un patient ou cochez « Tous les patients ».", { sticky: true });
      return;
    }
    const targetLabel = bulkMessageSendToAll
      ? "tous les patients"
      : `${selectedPatientPhones.length} patient${selectedPatientPhones.length > 1 ? "s" : ""}`;
    const channelLabel = bulkMessageChannel === "sms" ? "SMS" : "emails";
    if (!confirmImportantAction(`Confirmer l'envoi groupé (${channelLabel}) vers ${targetLabel} ?`)) {
      return;
    }
    setBulkMessageSending(true);
    try {
      const payload: Record<string, unknown> = {
        channel: bulkMessageChannel,
        message,
        send_to_all: bulkMessageSendToAll,
      };
      if (!bulkMessageSendToAll) {
        payload.phone_numbers = selectedPatientPhones;
      }
      if (bulkMessageChannel === "email") {
        payload.subject = bulkMessageSubject.trim() || "Message de votre cabinet";
      }
      const res = await api.tenantSendBulkPatientMessage(payload);
      const sent = Number(res?.sent_count || 0);
      const failed = Number(res?.failed_count || 0);
      const skipped = Number(res?.skipped_count || 0);
      notify(
        `${bulkMessageChannel === "sms" ? "SMS" : "Emails"} groupé envoyé(s): ${sent} OK, ${failed} échec(s), ${skipped} ignoré(s).`,
        { sticky: true },
      );
      if (!bulkMessageSendToAll) {
        setSelectedPatientPhones([]);
      }
      setModal(null);
      setBulkMessageBody("");
    } catch (e) {
      notify((e as Error)?.message || "Erreur envoi groupé", { sticky: true });
    } finally {
      setBulkMessageSending(false);
    }
  };

  const saveEmail = async () => {
    if (!tenantPatientPhone) {
      notify("Aucun patient sélectionné", { sticky: true });
      return;
    }
    const next = emailDraft.trim();
    const emailCheck = validateContactEmail(next);
    if (!emailCheck.ok) {
      notify(emailCheck.message || "Email invalide", { sticky: true });
      return;
    }
    if (hasBlockingPatientDuplicate(emailDuplicateConflicts)) {
      notify("Cet email est déjà utilisé par une autre fiche patient.", { sticky: true });
      return;
    }
    if (!confirmImportantAction("Confirmer la mise à jour de l'email du patient ?")) {
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
      const cached = patientDetailCacheRef.current.get(tenantPatientPhone);
      if (cached) {
        patientDetailCacheRef.current.set(tenantPatientPhone, {
          ...cached,
          patientEmail: persisted,
          patientCabinetRow: res?.patient
            ? (res.patient as Record<string, unknown>)
            : cached.patientCabinetRow,
        });
      }
      notify(persisted ? `Email enregistré : ${persisted}` : "Email supprimé");
      setEmailDuplicateConflicts([]);
    } catch (e) {
      console.error("[patient.email] PATCH failure", e);
      const dup = parsePatientDuplicateError(e as Error & { data?: { detail?: unknown } });
      const msg = dup.message || (e as Error)?.message || "Erreur mise à jour email";
      notify(msg, { sticky: true });
    } finally {
      setEmailSaving(false);
    }
  };

  const savePhone = async () => {
    if (!tenantPatientPhone) {
      notify("Aucun patient sélectionné", { sticky: true });
      return;
    }
    if (tenantPatientNotFound) {
      notify("Créez d'abord la fiche patient avant de modifier le numéro.", { sticky: true });
      return;
    }
    const next = phoneDraft.trim();
    if (!next) {
      notify("Indiquez un numéro de téléphone", { sticky: true });
      return;
    }
    const phoneCheck = validatePatientPhone(next, { required: true });
    if (!phoneCheck.ok) {
      notify(phoneCheck.message || "Numéro invalide", { sticky: true });
      return;
    }
    const phoneConflict = phoneDuplicateConflicts.some((c) => c?.field === "phone");
    if (phoneConflict) {
      notify(formatPatientDuplicateConflict(phoneDuplicateConflicts[0]) || "Ce numéro est déjà utilisé", { sticky: true });
      return;
    }
    if (!confirmImportantAction("Confirmer la mise à jour du numéro de téléphone du patient ?")) {
      return;
    }
    setPhoneSaving(true);
    try {
      const res = await api.tenantUpdatePatient(tenantPatientPhone, { phone: next });
      const newPhone = normalizePhone(String(res?.patient?.phone || next));
      if (!newPhone) {
        notify("Numéro invalide", { sticky: true });
        return;
      }
      const cached = patientDetailCacheRef.current.get(tenantPatientPhone);
      if (cached) {
        patientDetailCacheRef.current.delete(tenantPatientPhone);
        patientDetailCacheRef.current.set(newPhone, {
          ...cached,
          patientCabinetRow: res?.patient
            ? (res.patient as Record<string, unknown>)
            : cached.patientCabinetRow,
          urlPatientHero: cached.urlPatientHero
            ? { ...cached.urlPatientHero, phone: newPhone }
            : cached.urlPatientHero,
        });
      }
      setTenantSidebarRows((prev) =>
        prev.map((row) => {
          if (row.phone !== tenantPatientPhone) return row;
          const updated = res?.patient ? cabinetRowToSidebar(res.patient as Record<string, unknown>) : null;
          return updated || {
            ...row,
            phone: newPhone,
            displayPhone: formatDisplayFrenchPhone(newPhone),
          };
        }),
      );
      if (patientSearchRows) {
        setPatientSearchRows((prev) =>
          (prev || []).map((row) => {
            if (row.phone !== tenantPatientPhone) return row;
            const updated = res?.patient ? cabinetRowToSidebar(res.patient as Record<string, unknown>) : null;
            return updated || {
              ...row,
              phone: newPhone,
              displayPhone: formatDisplayFrenchPhone(newPhone),
            };
          }),
        );
      }
      if (res?.patient) setPatientCabinetRow(res.patient as Record<string, unknown>);
      setUrlPatientHero((prev) => (prev ? { ...prev, phone: newPhone } : prev));
      setEditingPhone(false);
      setPhoneDuplicateConflicts([]);
      const np = new URLSearchParams(searchParams);
      np.set("phone", newPhone);
      setSearchParams(np, { replace: true });
      notify(`Numéro mis à jour : ${formatDisplayFrenchPhone(newPhone)}`);
    } catch (e) {
      const dup = parsePatientDuplicateError(e as Error & { data?: { detail?: unknown } });
      notify(dup.message || (e as Error)?.message || "Erreur mise à jour téléphone", { sticky: true });
    } finally {
      setPhoneSaving(false);
    }
  };

  const updateRequestStatus = async (nextStatus: "processed" | "cancelled") => {
    if (!activeRequestDetail?.id) return;
    const info = normalizeRequestKind(activeRequestDetail.id);
    if (info.kind === "call" && nextStatus === "cancelled") {
      notify("Annulation indisponible pour ce type de demande");
      return;
    }
    setRequestActionLoading(nextStatus);
    try {
      if (info.kind === "callback") {
        await api.tenantUpdateCallbackRequest(info.rawId, { status: nextStatus });
      } else if (info.kind === "handoff") {
        await api.tenantUpdateHandoff(info.rawId, { status: nextStatus });
      } else if (info.kind === "call") {
        await api.tenantUpdateCallFollowup(info.rawId, { followup_state: "processed" });
      } else {
        throw new Error("Demande introuvable");
      }
      const nextLabel = toStatusLabel(nextStatus);
      setRequestStatus(nextLabel);
      persistRequestStatusOverride(activeRequestDetail.id, nextStatus);
      window.dispatchEvent(new CustomEvent("uwi:request-status-updated"));
      const [handoffsRes, callbacksRes] = await Promise.all([
        fetchTenantHandoffsCached(api, "?limit=50").catch(() => ({ items: [] })),
        fetchTenantCallbacksCached(api, "?limit=50").catch(() => ({ items: [] })),
      ]);
      setTenantHandoffs(Array.isArray(handoffsRes?.items) ? handoffsRes.items : []);
      setTenantCallbacks(Array.isArray(callbacksRes?.items) ? callbacksRes.items : []);
      clearActiveRequest();
      notify(nextStatus === "cancelled" ? "Demande annulée" : "Demande marquée traitée");
    } catch (e) {
      notify((e as Error)?.message || "Erreur de mise à jour");
    } finally {
      setRequestActionLoading("");
    }
  };

  const renderOpenRequestRows = (rows: typeof patientOpenRequests) => (
    <div className="space-y-4">
      {rows.map((req) => {
        const badge = requestStatusBadge(req.status);
        return (
          <button
            key={req.id}
            type="button"
            onClick={() => openPatientRequest(req)}
            className="flex w-full items-center gap-4 rounded-2xl border border-[#EEF3F8] p-4 text-left hover:bg-[#F8FBFD]"
          >
            <div className="grid h-12 w-12 place-items-center rounded-xl bg-[#F8FAFC] text-xl">
              {requestTypeIcon(req.typeKey)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="font-black">{req.type}</div>
              <div className="mt-1 truncate text-sm text-[#61708B]">{req.summary}</div>
              <div className="mt-1 text-sm text-[#61708B]">Reçu : {req.createdAtLabel}</div>
            </div>
            <span
              className="rounded-lg px-3 py-2 text-xs font-black"
              style={{ background: badge.bg, color: badge.color }}
            >
              {badge.label}
            </span>
          </button>
        );
      })}
    </div>
  );

  const canSubmitBulkMessage =
    !!bulkMessageBody.trim() && (bulkMessageSendToAll || selectedPatientPhones.length > 0) && !bulkMessageSending;
  const bulkModalTitle = (
    <span className="inline-flex flex-wrap items-center gap-2">
      <span>Envoyer un message groupé</span>
      <span
        className={cx(
          "rounded-full px-2.5 py-1 text-xs font-black",
          bulkMessageSendToAll
            ? "bg-[#E9FAFC] text-[#007E8C]"
            : "bg-[#EEF2FF] text-[#3730A3]",
        )}
      >
        {bulkMessageSendToAll
          ? "Tous les patients"
          : `${selectedPatientPhones.length} sélectionné${selectedPatientPhones.length > 1 ? "s" : ""}`}
      </span>
    </span>
  );

  return (
    <div className="min-h-0 bg-[#F7FAFC] text-[#0A1628] xl:min-h-screen">
      <Toast message={toast} />
      {globalLoadingLabel ? (
        <div className="fixed left-1/2 top-3 z-[90] -translate-x-1/2 rounded-xl bg-[#0A1628] px-4 py-2 text-sm font-semibold text-white shadow-lg">
          <span className="inline-flex items-center gap-2">
            <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-[#11D6DB]" />
            {globalLoadingLabel}
          </span>
        </div>
      ) : null}

      {patientListOpen && tenantPatientPhone ? (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-[#0A1628]/35 xl:hidden"
          onClick={() => setPatientListOpen(false)}
          aria-label="Fermer la liste patients"
        />
      ) : null}

      <div className="grid min-h-0 grid-cols-1 xl:min-h-screen xl:grid-cols-[330px_minmax(0,1fr)]">
        <aside
          className={cx(
            "border-b border-[#E5EDF5] bg-white px-4 py-5 sm:px-6 sm:py-7 xl:border-b-0 xl:border-r xl:px-6 xl:py-8",
            tenantPatientPhone && !patientListOpen ? "hidden xl:block" : "block",
            tenantPatientPhone && patientListOpen
              ? "fixed inset-0 z-50 overflow-y-auto pb-24 xl:static xl:inset-auto xl:z-auto xl:overflow-visible xl:pb-0"
              : "relative",
          )}
        >
          <div className="mb-5 flex items-center justify-between">
            <h2 className="text-2xl font-black">Patients</h2>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={openManualPatientCreateModal}
                className="rounded-xl border border-[#BFEAF0] bg-[#E9FAFC] px-3 py-1.5 text-xs font-black text-[#007E8C] hover:bg-[#DDF6FA]"
              >
                + Créer une fiche
              </button>
              {tenantPatientPhone && patientListOpen ? (
                <button
                  type="button"
                  onClick={() => setPatientListOpen(false)}
                  className="rounded-lg border border-[#E2EAF4] px-3 py-1.5 text-xs font-black text-[#475569] xl:hidden"
                >
                  Fermer
                </button>
              ) : null}
              <span className="rounded-xl bg-[#EEF6FA] px-3 py-1.5 text-sm font-black text-[#1C4B6B]">{sidebarCounts.total}</span>
            </div>
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

          <div className="mb-5 rounded-2xl border border-[#E2EAF4] bg-[#F8FBFD] p-3">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => toggleSelectAllVisiblePatients()}
                className={cx(
                  "rounded-lg border px-3 py-1.5 text-xs font-black",
                  allVisibleSelected
                    ? "border-[#009CA4] bg-[#E9FAFC] text-[#007E8C]"
                    : "border-[#DDE7F1] bg-white text-[#475569] hover:bg-[#F8FAFC]",
                )}
              >
                {allVisibleSelected ? "Tout désélectionner (liste affichée)" : "Tout sélectionner (liste affichée)"}
              </button>
              <button
                type="button"
                onClick={openBulkMessageModal}
                className="rounded-lg border border-[#009CA4] bg-white px-3 py-1.5 text-xs font-black text-[#007E8C] hover:bg-[#E9FAFC]"
              >
                Envoyer un message groupé
              </button>
              {selectedPatientPhones.length > 0 ? (
                <button
                  type="button"
                  onClick={clearSelectedPatients}
                  className="rounded-lg border border-[#DDE7F1] bg-white px-3 py-1.5 text-xs font-black text-[#475569] hover:bg-[#F8FAFC]"
                >
                  Effacer la sélection
                </button>
              ) : null}
              <span className="text-xs font-semibold text-[#64748B]">
                {selectedPatientPhones.length} patient{selectedPatientPhones.length > 1 ? "s" : ""} sélectionné{selectedPatientPhones.length > 1 ? "s" : ""}
              </span>
            </div>
            {selectedPatientPhones.length > 0 ? (
              <p className="mt-2 text-[11px] font-semibold text-[#64748B]">
                {selectedPatientsPreviewLabel}
              </p>
            ) : null}
            <p className="mt-2 text-[11px] font-semibold text-[#64748B]">
              Cochez directement les patients dans la liste pour cibler votre SMS groupé.
            </p>
          </div>

          <div className="overflow-hidden rounded-3xl border border-[#E5EDF5] bg-white shadow-sm">
            {tenantListLoading ? (
              <div className="p-10 text-center text-sm font-semibold text-[#64748B]">Chargement de la liste…</div>
            ) : tenantListError ? (
              <div className="space-y-3 p-8 text-center">
                <p className="text-sm font-semibold text-red-600">{tenantListError}</p>
                <button
                  type="button"
                  onClick={() => {
                    setTenantListLoading(true);
                    void loadTenantSidebarPatients({ force: true }).finally(() => setTenantListLoading(false));
                  }}
                  className="rounded-xl border border-[#DDE7F1] bg-white px-4 py-2 text-sm font-black text-[#007E8C] hover:bg-[#F8FBFD]"
                >
                  Réessayer
                </button>
              </div>
            ) : sidebarSearchPending ? (
              <div className="p-10 text-center text-sm font-semibold text-[#64748B]">Recherche dans toutes les fiches…</div>
            ) : filteredSidebarRows.length === 0 ? (
              <div className="p-10 text-center text-sm font-semibold text-[#64748B]">Aucun patient ne correspond aux filtres.</div>
            ) : (
              filteredSidebarRows.map((patient) => {
                const selected = patient.phone === tenantPatientPhone;
                const checkedForBulk = selectedPatientPhones.includes(patient.phone);
                return (
                  <button
                    key={patient.phone}
                    type="button"
                    onClick={() => {
                      const cached = patientDetailCacheRef.current.get(patient.phone);
                      const cacheValid = isPatientDetailCacheValid(cached, patientFetchNonce, activeView);
                      if (cacheValid && cached) {
                        applyPatientDetailBundle(cached);
                        syncPatientEmailDraft(cached.patientEmail || "");
                        setDocumentsLoading(false);
                        setNotesLoading(false);
                      } else {
                        applyPatientDetailBundle(emptyPatientDetailBundle({
                          urlPatientHero: {
                            name: patient.name,
                            phone: patient.phone,
                            initials: patient.initials,
                          },
                        }));
                        syncPatientEmailDraft("");
                        setDocumentsLoading(true);
                        setNotesLoading(activeView === "overview");
                      }
                      const np = new URLSearchParams(searchParams);
                      np.set("phone", patient.phone);
                      setSearchParams(np, { replace: true });
                      setPatientListOpen(false);
                    }}
                    className={cx(
                      "flex w-full items-center gap-3 border-b border-[#EEF3F8] p-4 text-left transition last:border-b-0",
                      selected ? "bg-[#EAF8FC] ring-1 ring-inset ring-[#BFEAF0]" : "hover:bg-[#F8FBFD]",
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={checkedForBulk}
                      onClick={(event) => event.stopPropagation()}
                      onChange={() => toggleSelectedPatientPhone(patient.phone)}
                      className="h-4 w-4 shrink-0 accent-[#009CA4]"
                      aria-label={`Sélectionner ${patient.name}`}
                    />
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

        <main className="overflow-x-hidden px-3 pb-2 pt-0 max-xl:px-3 max-xl:pb-2 max-xl:pt-0 sm:px-5 xl:px-8 xl:py-6">
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

          {tenantPatientPhone && displayHero ? (
            <PatientDashboardMobile
              displayHero={displayHero}
              patientCabinetRow={patientCabinetRow}
              patientEmail={patientEmail}
              tenantPatientNotFound={tenantPatientNotFound}
              activeView={activeView}
              setActiveView={setActiveView}
              onBackToList={goBackToPatientList}
              onOpenProfile={() => setModal("profile")}
              onCall={() => {
                const t = normalizePhone(displayHero.phone);
                if (t) window.location.href = `tel:${t}`;
                else notify("Numéro absent pour passer un appel.");
              }}
              onWhatsApp={() => {
                const t = normalizePhone(displayHero.phone);
                if (!t) {
                  notify("Numéro absent pour WhatsApp.");
                  return;
                }
                window.open(`https://wa.me/${t.replace(/^\+/, "")}`, "_blank", "noopener,noreferrer");
              }}
              onCreateConsultation={() => openConsultationModal()}
              onSendProfessionalSms={() => openSingleMessageModal("sms")}
              onSendProfessionalEmail={() => openSingleMessageModal("email")}
              canSendProfessionalEmail={Boolean(patientEmail && !tenantPatientNotFound)}
              onAddNote={() => setModal("addNote")}
              onAddDocument={() => setModal("addDocument")}
              onViewDocuments={() => setActiveView("documents")}
              onOpenHistoryModal={() => setModal("history")}
              onCreateBooking={() => setCreatePatientBookingOpen(true)}
              createBookingDisabled={!tenantPatientPhone}
              tenantPatientPhone={tenantPatientPhone}
              notify={notify}
              summaryRefreshNonce={summaryRefreshNonce}
              onQuestionnaireApplied={() => {
                setPatientFetchNonce((n) => n + 1);
                setSummaryRefreshNonce((n) => n + 1);
              }}
              upcomingAppointments={upcomingPatientAppointments}
              pastAppointments={pastPatientAppointments}
              patientAgendaLoading={patientAgendaLoading}
              apptStatusLabel={patientAgendaRowStatus}
              renderApptActions={(slot, start) => renderPatientApptActions(slot, start)}
              patientNotes={patientNotes}
              notesLoading={notesLoading}
              noteDeletingId={noteDeletingId}
              noteUpdatingId={noteUpdatingId}
              noteEditingId={noteEditingId}
              noteEditDraft={noteEditDraft}
              noteExpandedIds={noteExpandedIds}
              onRemoveNote={removeNote}
              onStartEditNote={startNoteEdit}
              onCancelEditNote={cancelNoteEdit}
              onChangeNoteEditDraft={setNoteEditDraft}
              onSaveNoteEdit={(id) => {
                void saveEditedNote(id);
              }}
              onToggleNoteExpanded={toggleNoteExpanded}
              patientHistory={patientHistory}
              patientHistoryLoading={patientHistoryLoading}
              documents={documents}
              documentsLoading={documentsLoading}
              onPreviewDocument={(doc) => void openPreview(doc)}
              formatDocDate={(value) => formatCabinetMetaDate(value)}
              patientConsultations={patientConsultations}
              patientConsultationsLoading={patientConsultationsLoading}
              consultationSaving={consultationSaving}
              consultationDeletingId={consultationDeletingId}
              lastSavedConsultationId={lastSavedConsultationId}
              onEditConsultation={(item) => {
                const full = patientConsultations.find((c) => c.consultationId === item.consultationId);
                if (full) editConsultation(full);
              }}
              onDownloadConsultationPdf={(item) => {
                const full = patientConsultations.find((c) => c.consultationId === item.consultationId);
                if (full) void downloadConsultationPdf(full);
              }}
              onDeleteConsultation={(item) => {
                const full = patientConsultations.find((c) => c.consultationId === item.consultationId);
                if (full) void deleteConsultation(full);
              }}
              onDuplicateLatestConsultation={duplicateLatestConsultation}
              editingPhone={editingPhone}
              phoneDraft={phoneDraft}
              phoneSaving={phoneSaving}
              phoneSaveDisabled={phoneSaving || phoneDuplicateConflicts.some((c) => c?.field === "phone")}
              phoneConflictMessage={
                phoneDuplicateConflicts.length
                  ? formatPatientDuplicateConflict(phoneDuplicateConflicts[0]) || "Ce numéro est déjà utilisé"
                  : ""
              }
              onStartEditPhone={() => {
                setEditingPhone(true);
                setPhoneDraft(tenantPatientPhone || normalizePhone(displayHero.phone) || "");
              }}
              onCancelEditPhone={() => {
                setEditingPhone(false);
                setPhoneDuplicateConflicts([]);
              }}
              onChangePhoneDraft={(value) => setPhoneDraft(value)}
              onSavePhone={() => void savePhone()}
            />
          ) : null}

          <div className="hidden xl:block">
          {!tenantPatientPhone ? (
            <div className="min-h-[420px] rounded-[28px] border border-[#E2EAF4] bg-white p-10 shadow-[0_12px_32px_rgba(10,22,40,0.05)]">
              <div className="mx-auto max-w-3xl text-center">
                <div className="mb-4 text-5xl">👤</div>
                <h2 className="text-2xl font-black text-[#0A1628]">Choisir ou créer un patient</h2>
                <p className="mt-3 text-sm leading-7 text-[#61708B]">
                  Utilisez la recherche ou lancez une action rapide ci-dessous.
                </p>
              </div>

              <div className="mx-auto mt-8 max-w-2xl">
                <label className="block text-left text-sm font-black text-[#0A1628]">
                  Rechercher un patient
                  <div className="relative mt-2">
                    <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-lg text-[#8D9AAF]">⌕</span>
                    <input
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder="Nom, prénom ou téléphone..."
                      className="h-12 w-full rounded-xl border border-[#DDE7F1] bg-white pl-11 pr-20 text-sm font-semibold text-[#0A1628] outline-none transition placeholder:text-[#9AA8BB] focus:border-[#009CA4] focus:ring-4 focus:ring-[#009CA4]/10"
                    />
                    {query ? (
                      <button
                        type="button"
                        onClick={() => setQuery("")}
                        className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg border border-[#DDE7F1] bg-white px-2.5 py-1 text-xs font-black text-[#475569] hover:bg-[#F8FAFC]"
                      >
                        Effacer
                      </button>
                    ) : null}
                  </div>
                </label>
              </div>

              <div className="mx-auto mt-6 grid max-w-2xl grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={openManualPatientCreateModal}
                  className="rounded-2xl border border-[#BFEAF0] bg-[#E9FAFC] px-4 py-4 text-left transition hover:bg-[#DDF6FA]"
                >
                  <div className="text-sm font-black text-[#007E8C]">+ Créer une fiche patient</div>
                </button>
                <button
                  type="button"
                  onClick={openBulkMessageModal}
                  className="rounded-2xl border border-[#DDE7F1] bg-white px-4 py-4 text-left transition hover:bg-[#F8FBFD]"
                >
                  <div className="text-sm font-black text-[#0A1628]">✉ Envoyer un message groupé</div>
                </button>
                <button
                  type="button"
                  onClick={() => notify("Sélectionnez d'abord un patient dans la liste pour ajouter une note.", { sticky: true })}
                  className="rounded-2xl border border-[#DDE7F1] bg-white px-4 py-4 text-left transition hover:bg-[#F8FBFD]"
                >
                  <div className="text-sm font-black text-[#0A1628]">✎ Ajouter une note</div>
                </button>
                <button
                  type="button"
                  onClick={() => notify("Sélectionnez d'abord un patient dans la liste pour ajouter un document.", { sticky: true })}
                  className="rounded-2xl border border-[#DDE7F1] bg-white px-4 py-4 text-left transition hover:bg-[#F8FBFD]"
                >
                  <div className="text-sm font-black text-[#0A1628]">▤ Ajouter un document</div>
                </button>
              </div>
            </div>
          ) : (
          <>
          <section className="overflow-hidden rounded-[24px] border border-[#E2EAF4] bg-white shadow-[0_12px_32px_rgba(10,22,40,0.05)] sm:rounded-[28px] sm:shadow-[0_18px_45px_rgba(10,22,40,0.06)]">
            <div className="h-1 bg-gradient-to-r from-[#009CA4] via-[#00B3A4] to-[#004C69]" />
            {tenantPatientPhone ? (
              <div className="flex items-center border-b border-[#EEF3F8] px-3 py-2.5 sm:px-4 xl:hidden">
                <button
                  type="button"
                  onClick={() => setPatientListOpen(true)}
                  className="inline-flex items-center gap-1.5 rounded-lg px-1 py-1 text-sm font-black text-[#007E8C] hover:bg-[#F0FAFB]"
                >
                  <span aria-hidden="true">←</span>
                  Liste patients
                </button>
              </div>
            ) : null}
            <div className="p-3.5 sm:p-6 lg:p-7">
              <div className="flex flex-col gap-4 sm:gap-5">
                <div className="flex min-w-0 items-start gap-3 sm:gap-5">
                  <div
                    className={cx(
                      "flex h-14 w-14 shrink-0 items-center justify-center rounded-[18px] bg-gradient-to-br text-lg font-black uppercase leading-none text-white shadow-[0_10px_24px_rgba(0,156,164,0.16)] sm:h-20 sm:w-20 sm:rounded-[22px] sm:text-2xl lg:h-24 lg:w-24 lg:rounded-[26px] lg:text-3xl",
                      displayHero.gradient,
                    )}
                  >
                    {displayHero.initials}
                  </div>

                  <div className="min-w-0 flex-1">
                    <h1 className="break-words text-lg font-black leading-tight tracking-tight text-[#0A1628] sm:text-2xl lg:text-[2rem]">
                      {displayHero.name}
                    </h1>
                    <div className="mt-1.5">
                      <PatientStatusPill bucket={displayHero.statusBucket} />
                    </div>
                  </div>
                </div>

                <PatientQuickActions
                  notify={notify}
                  onOpenProfile={() => setModal("profile")}
                  onCreateBooking={() => setCreatePatientBookingOpen(true)}
                  onCreateConsultation={() => openConsultationModal()}
                  createBookingDisabled={!tenantPatientPhone}
                />

                <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2">
                  <ContactMetaCard
                    icon={<HeroSvgIcon name="phone" />}
                    label="Téléphone"
                    value={
                      tenantPatientNotFound ? (
                        <span className="text-[#94A3B8]">Créez la fiche pour modifier le numéro</span>
                      ) : editingPhone ? (
                        <span className="flex w-full flex-col gap-2">
                          <span className="flex flex-wrap items-center gap-2">
                            <input
                              type="tel"
                              value={phoneDraft}
                              onChange={(event) => setPhoneDraft(event.target.value)}
                              placeholder="06 12 34 56 78"
                              className="h-9 min-w-0 flex-1 rounded-lg border border-[#DDE7F1] px-2.5 text-sm font-semibold text-[#0A1628] outline-none focus:border-[#009CA4]"
                            />
                            <button
                              type="button"
                              onClick={() => void savePhone()}
                              disabled={phoneSaving || phoneDuplicateConflicts.some((c) => c?.field === "phone")}
                              className="rounded-lg bg-[#009CA4] px-2.5 py-1.5 text-xs font-black text-white disabled:opacity-60"
                            >
                              {phoneSaving ? "…" : "OK"}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setEditingPhone(false);
                                setPhoneDuplicateConflicts([]);
                              }}
                              className="rounded-lg border border-[#DDE7F1] px-2.5 py-1.5 text-xs font-black text-[#475569]"
                            >
                              Annuler
                            </button>
                          </span>
                          {phoneDuplicateConflicts.length ? (
                            <PatientDuplicateBanner conflicts={phoneDuplicateConflicts} />
                          ) : null}
                        </span>
                      ) : (
                        <button
                          type="button"
                          className="text-left hover:text-[#007E8C]"
                          onClick={() => {
                            const tel = normalizePhone(displayHero.phone);
                            if (tel) window.location.href = `tel:${tel}`;
                            else notify("Numéro absent pour passer un appel.");
                          }}
                        >
                          {displayHero.phone}
                        </button>
                      )
                    }
                    action={
                      !tenantPatientNotFound && !editingPhone ? (
                        <span className="flex flex-wrap gap-1.5">
                          <button
                            type="button"
                            onClick={() => {
                              setEditingPhone(true);
                              setPhoneDraft(tenantPatientPhone || normalizePhone(displayHero.phone) || "");
                            }}
                            className="rounded-lg border border-[#DDE7F1] bg-white px-2.5 py-1.5 text-[11px] font-black text-[#475569] hover:bg-[#F8FAFC]"
                          >
                            Modifier
                          </button>
                          {normalizePhone(displayHero.phone) ? (
                            <button
                              type="button"
                              className="rounded-lg border border-[#009CA4] bg-[#009CA4] px-2.5 py-1.5 text-[11px] font-black text-white hover:brightness-110"
                              onClick={() => {
                                const tel = normalizePhone(displayHero.phone);
                                if (tel) window.location.href = `tel:${tel}`;
                                else notify("Numéro absent pour passer un appel.");
                              }}
                            >
                              Appeler
                            </button>
                          ) : null}
                          {normalizePhone(displayHero.phone) ? (
                            <button
                              type="button"
                              className="rounded-lg border border-[#DDE7F1] bg-white px-2.5 py-1.5 text-[11px] font-black text-[#475569] hover:bg-[#F8FAFC]"
                              onClick={() => {
                                const tel = normalizePhone(displayHero.phone);
                                if (tel && navigator.clipboard?.writeText) {
                                  void navigator.clipboard.writeText(formatDisplayFrenchPhone(tel));
                                  notify("Numéro copié.");
                                }
                              }}
                            >
                              Copier
                            </button>
                          ) : null}
                          <button
                            type="button"
                            onClick={() => openSingleMessageModal("sms")}
                            className="rounded-lg border border-[#75D3DF] bg-[#E9FAFC] px-2.5 py-1.5 text-[11px] font-black text-[#007E8C] hover:bg-[#DDF6FA]"
                          >
                            SMS
                          </button>
                        </span>
                      ) : null
                    }
                  />

                  <ContactMetaCard
                    icon={<HeroSvgIcon name="mail" />}
                    label="Email"
                    value={
                      tenantPatientNotFound ? (
                        <span className="text-[#94A3B8]">Créez la fiche pour ajouter un email</span>
                      ) : editingEmail ? (
                        <span className="flex w-full flex-col gap-2">
                          <span className="flex flex-wrap items-center gap-2">
                            <input
                              value={emailDraft}
                              onChange={(event) => setEmailDraft(event.target.value)}
                              placeholder="email@cabinet.fr"
                              className="h-9 min-w-0 flex-1 rounded-lg border border-[#DDE7F1] px-2.5 text-sm font-semibold text-[#0A1628] outline-none focus:border-[#009CA4]"
                            />
                            <button
                              type="button"
                              onClick={saveEmail}
                              disabled={emailSaving || hasBlockingPatientDuplicate(emailDuplicateConflicts)}
                              className="rounded-lg bg-[#009CA4] px-2.5 py-1.5 text-xs font-black text-white disabled:opacity-60"
                            >
                              {emailSaving ? "…" : "OK"}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setEditingEmail(false);
                                setEmailDuplicateConflicts([]);
                              }}
                              className="rounded-lg border border-[#DDE7F1] px-2.5 py-1.5 text-xs font-black text-[#475569]"
                            >
                              Annuler
                            </button>
                          </span>
                          {emailDuplicateConflicts.length ? (
                            <PatientDuplicateBanner conflicts={emailDuplicateConflicts} />
                          ) : null}
                        </span>
                      ) : patientEmail ? (
                        patientEmail
                      ) : (
                        <span className="text-[#94A3B8]">Aucun email renseigné</span>
                      )
                    }
                    action={
                      !tenantPatientNotFound && !editingEmail ? (
                        <span className="flex flex-wrap gap-1.5">
                          <button
                            type="button"
                            onClick={() => setEditingEmail(true)}
                            className="rounded-lg border border-[#DDE7F1] bg-white px-2.5 py-1.5 text-[11px] font-black text-[#475569] hover:bg-[#F8FAFC]"
                          >
                            {patientEmail ? "Modifier" : "Ajouter"}
                          </button>
                          <button
                            type="button"
                            disabled={!patientEmail}
                            onClick={() => openSingleMessageModal("email")}
                            className="rounded-lg border border-[#6AD58B] bg-[#F0FFF5] px-2.5 py-1.5 text-[11px] font-black text-[#0EA348] hover:brightness-105 disabled:opacity-50"
                          >
                            Email
                          </button>
                        </span>
                      ) : null
                    }
                  />
                </div>

                <PatientProfileHeaderMeta
                  birthDate={patientCabinetRow?.birth_date}
                  treatingPhysician={patientCabinetRow?.treating_physician_name}
                  treatingPhysicianCity={patientCabinetRow?.treating_physician_city}
                  onOpenProfile={() => setModal("profile")}
                />

                {patientInsightTags.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {patientInsightTags.map((tag) => (
                      <OutlineTag key={tag.key} tone={tag.tone}>
                        {tag.label}
                      </OutlineTag>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          </section>

          <section className="mt-3.5 overflow-hidden rounded-[24px] border border-[#E2EAF4] bg-white shadow-sm sm:mt-5 sm:rounded-[26px]">
            <div className="flex snap-x snap-mandatory overflow-x-auto border-b border-[#EEF3F8] [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              {viewTabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveView(tab.id)}
                  className={cx(
                    "relative flex h-14 min-w-[25%] shrink-0 snap-start items-center justify-center gap-2 px-2 text-sm font-black transition sm:min-w-0 sm:flex-1 sm:gap-2.5 sm:px-4",
                    activeView === tab.id ? "text-[#008EA1]" : "text-[#42536E] hover:bg-[#F8FBFD]",
                  )}
                >
                  <HeroSvgIcon
                    name={
                      tab.id === "overview"
                        ? "overview"
                        : tab.id === "appointments"
                          ? "calendar"
                          : tab.id === "documents"
                            ? "documents"
                            : "history"
                    }
                  />
                  <span className="hidden sm:inline">{tab.label}</span>
                  <span className="sm:hidden">{tab.shortLabel}</span>
                  {activeView === tab.id ? (
                    <span className="absolute bottom-0 left-3 right-3 h-1 rounded-t-full bg-[#009CA4] sm:left-6 sm:right-6" />
                  ) : null}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-3 sm:gap-4 sm:p-5">
              <PrimaryCTA variant="note" onClick={() => setModal("addNote")}>✎ Ajouter une note</PrimaryCTA>
              <PrimaryCTA variant="document" onClick={() => setModal("addDocument")}>▤ Ajouter un document</PrimaryCTA>
              <PrimaryCTA variant="consult" onClick={() => openConsultationModal()}>
                🩺 Créer fiche consultation
              </PrimaryCTA>
            </div>
          </section>
          </>
          )}
          </div>

          {tenantPatientPhone && !activeRequestDetail && (patientOpenRequests.length > 0 || (requestsLoading && requestIdFromUrl)) ? (
            <section className="mt-6 rounded-[28px] border border-[#E2EAF4] bg-white p-7 shadow-sm">
              <div className="mb-5 flex items-center justify-between">
                <h2 className="text-2xl font-black">
                  <span className="text-[#FF8A00]">ϟ</span> À traiter{" "}
                  <span className="ml-2 rounded-full bg-[#FFF1E8] px-2 py-1 text-sm text-[#FF6B00]">
                    {patientOpenRequests.length}
                  </span>
                </h2>
                <button
                  type="button"
                  onClick={() => navigate(`/app/demandes?status=${encodeURIComponent("À traiter")}`)}
                  className="text-sm font-black text-[#008EA1]"
                >
                  Voir tout ›
                </button>
              </div>
              {requestsLoading ? (
                <p className="text-sm font-semibold text-[#61708B]">Chargement des demandes…</p>
              ) : patientOpenRequests.length === 0 ? (
                <p className="text-sm font-semibold text-[#61708B]">Aucune demande en attente pour ce patient.</p>
              ) : (
                renderOpenRequestRows(patientOpenRequests)
              )}
            </section>
          ) : null}

          {activeRequestDetail ? (
            <section className="mt-6 rounded-[28px] border border-[#FFD9B8] bg-[#FFF7F0] p-6 shadow-sm">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-2xl font-black text-[#0A1628]">Demande à traiter</h2>
                  <p className="mt-1 text-sm font-semibold text-[#6B5A4A]">
                    {activeRequestDetail.type} · {activeRequestDetail.priority}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={clearActiveRequest}
                  className="rounded-xl border border-[#F2C59F] bg-white px-4 py-2 text-xs font-black text-[#9A5A1C] hover:bg-[#FFF4EA]"
                >
                  Masquer
                </button>
              </div>

              <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
                <div className="rounded-xl border border-[#F4E1CF] bg-white p-3">
                  <div className="text-xs font-bold text-[#8B735D]">Type de demande</div>
                  <div className="mt-1 font-black text-[#0A1628]">{activeRequestDetail.type}</div>
                </div>
                <div className="rounded-xl border border-[#F4E1CF] bg-white p-3">
                  <div className="text-xs font-bold text-[#8B735D]">Statut</div>
                  <div className="mt-1 font-black text-[#0A1628]">{requestStatus || activeRequestDetail.status}</div>
                </div>
                <div className="rounded-xl border border-[#F4E1CF] bg-white p-3">
                  <div className="text-xs font-bold text-[#8B735D]">Date/heure de transfert</div>
                  <div className="mt-1 font-black text-[#0A1628]">{activeRequestDetail.createdAtLabel}</div>
                </div>
                <div className="rounded-xl border border-[#F4E1CF] bg-white p-3">
                  <div className="text-xs font-bold text-[#8B735D]">Source</div>
                  <div className="mt-1 font-black text-[#0A1628]">{activeRequestDetail.source}</div>
                </div>
              </div>

              <div className="mt-3 rounded-xl border border-[#F4E1CF] bg-white p-4">
                <div className="text-xs font-bold uppercase tracking-wide text-[#8B735D]">Résumé généré par Clara</div>
                <p className="mt-2 text-sm leading-7 text-[#334155]">{activeRequestDetail.summary}</p>
              </div>

              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <button type="button" onClick={() => notify("Action: Rappeler le patient")} className="rounded-xl bg-[#009CA4] px-4 py-3 text-sm font-black text-white hover:bg-[#00838A]">Rappeler le patient</button>
                <button type="button" onClick={() => notify("Action: Assigner au médecin")} className="rounded-xl border border-[#DDE7F1] bg-white px-4 py-3 text-sm font-black text-[#0A1628] hover:bg-[#F8FAFC]">Assigner au médecin</button>
                <button type="button" onClick={() => notify("Action: Planifier un créneau")} className="rounded-xl border border-[#DDE7F1] bg-white px-4 py-3 text-sm font-black text-[#0A1628] hover:bg-[#F8FAFC]">Planifier un créneau</button>
                <button type="button" onClick={() => setModal("addNote")} className="rounded-xl border border-[#DDE7F1] bg-white px-4 py-3 text-sm font-black text-[#0A1628] hover:bg-[#F8FAFC]">Ajouter une note</button>
                <button
                  type="button"
                  onClick={() => updateRequestStatus("processed")}
                  disabled={!!requestActionLoading || isTerminalLabel(requestStatus || activeRequestDetail.status)}
                  className={cx(
                    "rounded-xl border border-[#A7F3D0] bg-[#ECFDF5] px-4 py-3 text-sm font-black text-[#047857] lg:col-span-2",
                    !!requestActionLoading || isTerminalLabel(requestStatus || activeRequestDetail.status) ? "cursor-not-allowed opacity-60" : "hover:bg-[#DDFBEF]",
                  )}
                >
                  {requestActionLoading === "processed" ? "Traitement..." : "Marquer comme traitée"}
                </button>
                <button
                  type="button"
                  onClick={() => updateRequestStatus("cancelled")}
                  disabled={!!requestActionLoading || isTerminalLabel(requestStatus || activeRequestDetail.status)}
                  className={cx(
                    "rounded-xl border border-[#CBD5E1] bg-[#F8FAFC] px-4 py-3 text-sm font-black text-[#475569] lg:col-span-3",
                    !!requestActionLoading || isTerminalLabel(requestStatus || activeRequestDetail.status) ? "cursor-not-allowed opacity-60" : "hover:bg-[#F1F5F9]",
                  )}
                >
                  {requestActionLoading === "cancelled" ? "Annulation..." : "Annuler la demande"}
                </button>
              </div>

              {otherOpenRequests.length > 0 ? (
                <div className="mt-6 border-t border-[#F4E1CF] pt-5">
                  <h3 className="mb-4 text-sm font-black uppercase tracking-wide text-[#475569]">
                    Autres demandes ({otherOpenRequests.length})
                  </h3>
                  {renderOpenRequestRows(otherOpenRequests)}
                </div>
              ) : null}
            </section>
          ) : null}

          {activeView === "overview" && (
            <div className="mt-6 hidden space-y-6 xl:block">
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
                      Aucun rendez-vous à venir pour ce numéro (prochains 14 jours). Les créneaux réservés avec ce téléphone sur l’agenda apparaîtront ici.
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
                      <div className="mb-4 flex flex-wrap items-center gap-3 sm:gap-4">
                        <div className="text-3xl font-black sm:text-4xl">
                          {formatAgendaSlotHour(start)}{" "}
                          <span className="text-sm font-semibold text-[#64748B] sm:text-base">
                            ({agendaSlotDurationMinutes(slot)} min)
                          </span>
                        </div>
                        <span className={`rounded-lg px-3 py-2 text-sm font-black sm:text-base ${tone}`}>{statusLb}</span>
                      </div>

                      <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
                        <div><div className="mb-1 text-xs font-bold text-[#7D8CA5]">Motif</div><div className="font-black">{agendaSlotMotif(slot) || "—"}</div></div>
                        <div><div className="mb-1 text-xs font-bold text-[#7D8CA5]">Origine</div><div className="font-black">{agendaOriginLabel(slot)}</div></div>
                        <div><div className="mb-1 text-xs font-bold text-[#7D8CA5]">Préférence</div><div className="font-black">{timePreferenceLabel(slot.time_preference)}</div></div>
                        <div><div className="mb-1 text-xs font-bold text-[#7D8CA5]">Canal</div><div className="font-black">{contactTypeLabel(slot.contact_type)}</div></div>
                      </div>

                      {renderPatientApptActions(slot, start)}
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
                              className="flex flex-col gap-3 rounded-2xl border border-[#EEF3F8] bg-[#F8FBFD] px-4 py-3 text-sm sm:flex-row sm:flex-wrap sm:items-center sm:justify-between"
                            >
                              <div className="min-w-0 flex-1">
                                <div className="font-black text-[#0A1628]">
                                  {formatAgendaSlotHour(dt)} · {dLabel.replace(/\.$/, ".")}
                                </div>
                                <div className="mt-1 font-semibold text-[#475569]">{agendaSlotMotif(sRow) || "Consultation"}</div>
                              </div>
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="rounded-lg bg-white px-3 py-1.5 text-xs font-black text-[#007E8C]">{st}</span>
                                {renderPatientApptActions(sRow, dt, { compact: true })}
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ) : null}
                  </>
                  )}
                </section>

                <PatientMedicalContextPreview patient={patientCabinetRow} />

                <section
                  ref={consultationDossierRef}
                  className="overflow-hidden rounded-[28px] border border-[#DCE9F5] bg-gradient-to-b from-white to-[#F7FBFF] shadow-[0_12px_28px_rgba(10,22,40,0.06)]"
                >
                  <div className="border-b border-[#E8F0F8] bg-[#F3FAFF] px-6 py-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <h2 className="flex flex-wrap items-center gap-3 text-xl font-black text-[#0A1628]">
                          ▣ Dossier consultations
                          {!patientConsultationsLoading && patientConsultations.length > 0 ? (
                            <span className="rounded-full bg-[#E8F7F7] px-2.5 py-1 text-xs font-black text-[#008EA1]">
                              {patientConsultations.length}
                            </span>
                          ) : null}
                        </h2>
                        <p className="mt-1 text-sm font-semibold text-[#61708B]">
                          Chaque enregistrement de fiche consultation apparaît ici (plus récente en premier).
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={duplicateLatestConsultation}
                          disabled={patientConsultationsLoading || patientConsultations.length === 0}
                          className="rounded-xl border border-[#BFD5EC] bg-white px-4 py-2 text-sm font-black text-[#355D87] shadow-sm transition hover:bg-[#EFF6FC] disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Dupliquer la dernière fiche
                        </button>
                        <button
                          type="button"
                          onClick={() => openConsultationModal()}
                          className="rounded-xl border border-[#79CDDB] bg-white px-4 py-2 text-sm font-black text-[#008EA1] shadow-sm transition hover:bg-[#E9FAFC]"
                        >
                          + Nouvelle fiche
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="px-6 py-5">
                    {patientConsultationsLoading ? (
                      <div className="rounded-2xl border border-[#E7EEF6] bg-white px-4 py-3 text-sm font-semibold text-[#61708B]">
                        Chargement des consultations…
                      </div>
                    ) : patientConsultations.length === 0 ? (
                      <div className="rounded-2xl border border-dashed border-[#CFE1F1] bg-white px-4 py-5 text-sm font-semibold text-[#61708B]">
                        Aucune consultation enregistrée pour ce patient.
                      </div>
                    ) : (
                      <ul className="m-0 list-none space-y-3 p-0">
                        {patientConsultations.map((item) => (
                          <li
                            key={item.id}
                            className={cx(
                              "rounded-2xl border border-[#E7EEF6] bg-white px-4 py-3 shadow-[0_3px_10px_rgba(15,23,42,0.04)]",
                              lastSavedConsultationId === item.consultationId ? "ring-2 ring-[#7BD7E2]" : "",
                            )}
                          >
                            <div className="flex flex-wrap items-start justify-between gap-2">
                              <div className="rounded-lg bg-[#F1F7FF] px-2.5 py-1 text-xs font-black uppercase tracking-wide text-[#2B5B8A]">
                                {item.dateLabel}
                              </div>
                              {item.prochainRdv ? (
                                <span className="rounded-full bg-[#E8F7F7] px-2.5 py-1 text-xs font-black text-[#007E8C]">
                                  Suivi prévu : {item.prochainRdv}
                                </span>
                              ) : (
                                <span className="rounded-full bg-[#F4F7FB] px-2.5 py-1 text-xs font-bold text-[#71839A]">
                                  Aucun suivi planifié
                                </span>
                              )}
                            </div>
                            <div className="mt-2 text-sm font-semibold text-[#1E293B]">Motif : {item.motif}</div>
                            {item.impression ? (
                              <div className="mt-1 text-sm text-[#64748B]">
                                Impression : {item.impression.slice(0, 220)}
                                {item.impression.length > 220 ? "…" : ""}
                              </div>
                            ) : null}
                            <div className="mt-3 flex flex-wrap gap-2">
                              <button
                                type="button"
                                onClick={() => editConsultation(item)}
                                disabled={consultationSaving || consultationDeletingId === item.consultationId}
                                className="rounded-lg border border-[#91D9E3] bg-[#E9FAFC] px-3 py-1.5 text-xs font-black text-[#007E8C] hover:bg-[#DCF4F7] disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                Modifier
                              </button>
                              <button
                                type="button"
                                onClick={() => void downloadConsultationPdf(item)}
                                className="rounded-lg border border-[#C9D8E8] bg-[#F8FBFF] px-3 py-1.5 text-xs font-black text-[#355D87] hover:bg-[#EEF5FD]"
                              >
                                Télécharger PDF
                              </button>
                              <button
                                type="button"
                                onClick={() => void deleteConsultation(item)}
                                disabled={consultationSaving || consultationDeletingId === item.consultationId}
                                className="rounded-lg border border-[#F6C2C2] bg-[#FFF5F5] px-3 py-1.5 text-xs font-black text-[#C62828] hover:bg-[#FFEAEA] disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                {consultationDeletingId === item.consultationId ? "Suppression..." : "Supprimer"}
                              </button>
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </section>

                <section className="rounded-[28px] bg-gradient-to-br from-[#062E53] via-[#023E63] to-[#007B88] p-6 text-white shadow-[0_20px_45px_rgba(0,66,90,0.22)]">
                  <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-black uppercase tracking-[0.18em] text-[#66DDE2]">Résumé & suivi</p>
                      <h2 className="mt-1 text-2xl font-black">Contexte patient</h2>
                    </div>
                    <button
                      type="button"
                      onClick={() => setModal("profile")}
                      className="rounded-xl border border-white/20 bg-white/10 px-3 py-2 text-xs font-black text-white transition hover:bg-white/15"
                    >
                      Compléter le contexte
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-6">
                    <div>
                      <PatientContextSummary
                        key={tenantPatientPhone || "no-patient"}
                        phone={tenantPatientPhone}
                        refreshNonce={summaryRefreshNonce}
                      />
                    </div>

                    <div className="border-l border-white/25 pl-6">
                      <h3 className="mb-4 text-xl font-black text-white">✎ Notes de l'équipe</h3>

                      <div className="space-y-4">
                        {notesLoading ? (
                          <div className="text-sm text-white/70">Chargement des notes...</div>
                        ) : patientNotes.length === 0 ? (
                          <div className="text-sm text-white/70">Aucune note pour ce patient.</div>
                        ) : (
                          patientNotes.slice(0, 4).map((item) => {
                            const isDeleting = noteDeletingId === item.id;
                            const isUpdating = noteUpdatingId === item.id;
                            const isEditing = noteEditingId === item.id;
                            const isExpanded = Boolean(noteExpandedIds[item.id]);
                            const rawText = String(item.text || "");
                            const hasOverflow = rawText.length > PATIENT_NOTE_PREVIEW_LIMIT;
                            return (
                              <div key={item.id} className="border-b border-white/20 pb-4">
                                {isEditing ? (
                                  <div className="space-y-2">
                                    <textarea
                                      value={noteEditDraft}
                                      onChange={(event) => setNoteEditDraft(event.target.value)}
                                      disabled={isUpdating}
                                      className="h-20 w-full resize-none rounded-xl border border-white/20 bg-white px-3 py-2 text-sm font-semibold text-[#0A1628] outline-none focus:ring-4 focus:ring-[#00C4CC]/25 disabled:opacity-60"
                                    />
                                    <div className="flex flex-wrap gap-2">
                                      <button
                                        type="button"
                                        onClick={() => {
                                          void saveEditedNote(item.id);
                                        }}
                                        disabled={isUpdating}
                                        className="rounded border border-[#9DE7EC] bg-[#00A5AE] px-3 py-1 text-xs font-black text-white hover:bg-[#00939B] disabled:opacity-60"
                                      >
                                        {isUpdating ? "Enregistrement..." : "Enregistrer"}
                                      </button>
                                      <button
                                        type="button"
                                        onClick={cancelNoteEdit}
                                        disabled={isUpdating}
                                        className="rounded border border-white/30 px-3 py-1 text-xs font-black text-white/85 hover:bg-white/10 disabled:opacity-60"
                                      >
                                        Annuler
                                      </button>
                                    </div>
                                  </div>
                                ) : (
                                  <>
                                    <div className="text-base font-semibold">♡ {isExpanded ? rawText : previewPatientNoteText(rawText)}</div>
                                    <div className="mt-2 flex flex-wrap items-center gap-2">
                                      {hasOverflow ? (
                                        <button
                                          type="button"
                                          onClick={() => toggleNoteExpanded(item.id)}
                                          disabled={isDeleting || isUpdating}
                                          className="rounded border border-white/25 px-2 py-0.5 text-xs font-bold text-white/80 hover:bg-white/10 disabled:opacity-50"
                                        >
                                          {isExpanded ? "Afficher moins" : "Lire la suite"}
                                        </button>
                                      ) : null}
                                      <button
                                        type="button"
                                        onClick={() => startNoteEdit(item)}
                                        disabled={isDeleting || isUpdating}
                                        className="rounded border border-white/25 px-2 py-0.5 text-xs font-bold text-white/80 hover:bg-white/10 disabled:opacity-50"
                                      >
                                        Modifier
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() => removeNote(item.id)}
                                        disabled={isDeleting || isUpdating}
                                        className="rounded border border-white/25 px-2 py-0.5 text-xs font-bold text-white/80 hover:bg-white/10 disabled:opacity-50"
                                      >
                                        {isDeleting ? "..." : "Supprimer"}
                                      </button>
                                    </div>
                                  </>
                                )}
                                <div className="mt-1 text-sm text-white/60">
                                  <span>{item.author} · {new Date(item.created_at).toLocaleDateString("fr-FR")}</span>
                                </div>
                              </div>
                            );
                          })
                        )}
                      </div>

                      <textarea
                        value={note}
                        onChange={(event) => setNote(event.target.value)}
                        placeholder="Ajouter une note... (ou dictez-la à la voix)"
                        className="mt-4 h-16 w-full resize-none rounded-xl border border-white/20 bg-white px-4 py-3 text-[#0A1628] outline-none focus:ring-4 focus:ring-[#00C4CC]/25"
                      />
                      <div className="mt-3 flex flex-wrap items-center gap-3">
                        <button onClick={saveNote} disabled={notesSaving || noteRecording || noteTranscribing} className="rounded-xl bg-[#00A5AE] px-7 py-3 text-sm font-black text-white shadow-lg hover:bg-[#00949C] disabled:opacity-60">
                          {notesSaving ? "Enregistrement..." : "Enregistrer"}
                        </button>
                        <button
                          type="button"
                          onClick={toggleNoteDictation}
                          disabled={noteTranscribing}
                          aria-pressed={noteRecording}
                          className={cx(
                            "inline-flex items-center gap-2 rounded-xl border px-4 py-3 text-sm font-black transition disabled:opacity-60",
                            noteRecording
                              ? "border-[#FCA5A5] bg-[#E11D48] text-white"
                              : "border-white/30 bg-white/10 text-white hover:bg-white/20",
                          )}
                        >
                          <span className={cx("inline-block h-2.5 w-2.5 rounded-full", noteRecording ? "animate-pulse bg-white" : "bg-[#7CF3FB]")} />
                          {noteTranscribing ? "Transcription…" : noteRecording ? "Arrêter la dictée" : "Dicter"}
                        </button>
                        {noteRecording ? (
                          <span className="text-sm font-bold text-white/80">Dictée en cours… parlez.</span>
                        ) : null}
                      </div>
                    </div>
                  </div>
                </section>

                <PatientQuestionnaireCard
                  phone={tenantPatientPhone}
                  patientEmail={patientEmail}
                  profile={patientCabinetRow}
                  notify={notify}
                  onApplied={() => {
                    setPatientFetchNonce((n) => n + 1);
                    setSummaryRefreshNonce((n) => n + 1);
                  }}
                  disabled={tenantPatientNotFound}
                />
                <div className="mt-4">
                  <PatientAdminQuestionnaireCard
                    phone={tenantPatientPhone}
                    patientEmail={patientEmail}
                    notify={notify}
                    summaryRefreshNonce={summaryRefreshNonce}
                    onApplied={() => {
                      setPatientFetchNonce((n) => n + 1);
                      setSummaryRefreshNonce((n) => n + 1);
                    }}
                    disabled={tenantPatientNotFound}
                  />
                </div>
                <div className="mt-4">
                  <PatientMedicalQuestionnaireCard
                    phone={tenantPatientPhone}
                    patientEmail={patientEmail}
                    notify={notify}
                    summaryRefreshNonce={summaryRefreshNonce}
                    onApplied={() => {
                      setPatientFetchNonce((n) => n + 1);
                      setSummaryRefreshNonce((n) => n + 1);
                    }}
                    disabled={tenantPatientNotFound}
                  />
                </div>
              </div>
            </div>
          )}

          {activeView === "appointments" && (
            <section className="mt-6 hidden rounded-[28px] border border-[#E2EAF4] bg-white p-4 shadow-sm sm:p-6 lg:p-8 xl:block">
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
                Rendez-vous rattachés au numéro de ce patient dans l&apos;agenda du cabinet (60 prochains jours).
              </p>
              {!tenantPatientPhone ? (
                <p className="text-sm font-semibold text-[#61708B]">Sélectionnez un patient.</p>
              ) : patientAgendaLoading ? (
                <p className="text-sm font-semibold text-[#61708B]">Chargement…</p>
              ) : upcomingPatientAppointments.length === 0 && pastPatientAppointments.length === 0 ? (
                <p className="text-sm font-semibold text-[#61708B]">
                  Aucun rendez-vous trouvé avec ce téléphone. Vérifiez que chaque RDV comporte bien le numéro en contact dans l&apos;agenda ou Google&nbsp;Calendar.
                </p>
              ) : (
              <>
              {upcomingPatientAppointments.length > 0 ? (
              <div className="space-y-3 sm:space-y-4">
                {upcomingPatientAppointments.map(({ slot, start }) => {
                  const rowKey = `${String(slot.event_id || slot.appointment_id || "")}-${start.toISOString()}`;
                  const dateStr = start.toLocaleDateString("fr-FR", {
                    day: "2-digit",
                    month: "2-digit",
                    year: "numeric",
                  });
                  return (
                  <div key={rowKey} className="grid grid-cols-1 gap-3 rounded-2xl border border-[#EEF3F8] p-4 text-sm sm:grid-cols-[120px_90px_1fr_160px_auto] sm:items-center sm:gap-3">
                    <div className="flex items-center justify-between gap-3 sm:contents">
                      <b>{dateStr}</b>
                      <b>{formatAgendaSlotHour(start)}</b>
                    </div>
                    <span>{agendaSlotMotif(slot) || "Consultation"}</span>
                    <span className="rounded-lg bg-[#F2F8FA] px-3 py-2 text-center font-black text-[#007E8C]">{patientAgendaRowStatus(slot, start)}</span>
                    {renderPatientApptActions(slot, start, { compact: true })}
                  </div>
                  );
                })}
              </div>
              ) : null}

              {pastPatientAppointments.length > 0 ? (
                <div className={upcomingPatientAppointments.length > 0 ? "mt-8 border-t border-[#EEF3F8] pt-6" : ""}>
                  <h3 className="mb-4 text-lg font-black text-[#0A1628]">Rendez-vous passés</h3>
                  <p className="mb-4 text-sm font-semibold text-[#61708B]">
                    Signalez une absence pour alimenter le tag « Risque no-show » (à partir de 2 absences notées).
                  </p>
                  <div className="space-y-3 sm:space-y-4">
                    {pastPatientAppointments.map(({ start, key }) => {
                      const rowKey = key;
                      const dateStr = start.toLocaleDateString("fr-FR", {
                        day: "2-digit",
                        month: "2-digit",
                        year: "numeric",
                      });
                      const saving = absenceNoteSavingKey === key;
                      return (
                        <div key={rowKey} className="grid grid-cols-1 gap-3 rounded-2xl border border-[#EEF3F8] p-4 text-sm sm:grid-cols-[120px_90px_1fr_auto] sm:items-center sm:gap-3">
                          <div className="flex items-center justify-between gap-3 sm:contents">
                            <b>{dateStr}</b>
                            <b>{formatAgendaSlotHour(start)}</b>
                          </div>
                          <span>Consultation</span>
                          <button
                            type="button"
                            disabled={saving}
                            onClick={() => void reportAppointmentAbsence(start)}
                            className="rounded-xl border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-xs font-black text-[#B91C1C] hover:bg-[#FEE2E2] disabled:opacity-60"
                          >
                            {saving ? "Enregistrement…" : "Signaler absence"}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}
              </>
              )}
            </section>
          )}

          {activeView === "history" && (
            <section className="mt-6 hidden rounded-[28px] border border-[#E2EAF4] bg-white p-4 shadow-sm sm:p-6 lg:p-8 xl:block">
              <h2 className="mb-5 text-2xl font-black">Historique des interactions</h2>
              <HistoryList items={patientHistory} loading={patientHistoryLoading} />
            </section>
          )}

          {activeView === "documents" && (
            <section className="mt-6 hidden rounded-[28px] border border-[#E2EAF4] bg-white p-4 shadow-sm sm:p-6 lg:p-8 xl:block">
              <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-black">Documents du patient</h2>
                  {!documentsLoading ? (
                    <p className="mt-2 text-sm font-bold text-[#008EA1]">
                      {documents.length} document{documents.length > 1 ? "s" : ""} enregistré{documents.length > 1 ? "s" : ""}
                    </p>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setModal("addDocument")}
                    className="rounded-xl border border-[#6AD58B] bg-white px-4 py-2 text-sm font-black text-[#0EA348] hover:bg-[#F0FFF5]"
                  >
                    ▤ Ajouter un document
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveView("overview")}
                    className="rounded-xl border border-[#B6C3D7] px-4 py-2 text-sm font-black text-[#53647F] hover:bg-[#F8FAFC]"
                  >
                    ◂ Retour vue d&apos;ensemble
                  </button>
                </div>
              </div>
              <PatientDocumentsList
                documents={documents}
                loading={documentsLoading}
                patientEmail={patientEmail}
                documentSendingId={documentSendingId}
                documentDeletingId={documentDeletingId}
                onPreview={(doc) => void openPreview(doc)}
                onDownload={(doc) => void downloadDocument(doc)}
                onSend={(docId) => void sendDocument(docId)}
                onDelete={(docId) => void deleteDocument(docId)}
                onAddDocument={() => setModal("addDocument")}
              />
            </section>
          )}
        </main>
      </div>

      {modal === "profile" && (
        <Modal title="Profil patient" onClose={() => setModal(null)} width="max-w-4xl">
          {tenantPatientNotFound ? (
            <p className="m-0 text-sm leading-7 text-[#475569]">
              Créez d&apos;abord la fiche avec le formulaire en haut de page (nom puis « Créer la fiche »), puis vous pourrez modifier les détails ici.
            </p>
          ) : urlPatientHero ? (
            <>
              <div className="mb-5">
                <PatientMedicalContextPreview patient={patientCabinetRow} compact />
              </div>
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
                  <div className="mb-1 text-xs font-bold text-[#7D8CA5]">Date de naissance</div>
                  <input
                    type="date"
                    value={profileBirthDateDraft}
                    onChange={(e) => setProfileBirthDateDraft(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-[#DDE7F1] bg-white px-3 py-2 font-black text-[#0A1628] outline-none focus:border-[#009CA4]"
                  />
                </div>
                <div className="rounded-2xl bg-[#F8FBFD] p-4">
                  <div className="mb-1 text-xs font-bold text-[#7D8CA5]">Médecin traitant</div>
                  <input
                    value={profilePhysicianDraft}
                    onChange={(e) => setProfilePhysicianDraft(e.target.value)}
                    placeholder="Dr Martin Dupont"
                    className="mt-1 w-full rounded-xl border border-[#DDE7F1] bg-white px-3 py-2 font-black text-[#0A1628] outline-none focus:border-[#009CA4]"
                  />
                </div>
                <div className="rounded-2xl bg-[#F8FBFD] p-4">
                  <div className="mb-1 text-xs font-bold text-[#7D8CA5]">Ville d&apos;exercice</div>
                  <input
                    value={profilePhysicianCityDraft}
                    onChange={(e) => setProfilePhysicianCityDraft(e.target.value)}
                    placeholder="Lyon, Paris…"
                    className="mt-1 w-full rounded-xl border border-[#DDE7F1] bg-white px-3 py-2 font-black text-[#0A1628] outline-none focus:border-[#009CA4]"
                  />
                </div>
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
              <div className="mt-5 rounded-[22px] border border-[#DDE7F1] bg-[#F8FBFD] p-4">
                <div className="mb-4">
                  <div className="text-sm font-black text-[#0A1628]">Contexte médical utile en consultation</div>
                  <p className="mt-1 text-xs font-semibold leading-5 text-[#64748B]">
                    Ces informations alimentent le dossier patient affiché dans la fiche consultation.
                    La dernière consultation enregistrée enrichit automatiquement ce contexte.
                  </p>
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <PatientProfileTextArea
                    label="Antécédents médicaux"
                    value={profileMedicalAntecedentsDraft}
                    onChange={setProfileMedicalAntecedentsDraft}
                    placeholder="Ex. HTA, diabète, asthme..."
                  />
                  <PatientProfileTextArea
                    label="Antécédents chirurgicaux"
                    value={profileSurgicalAntecedentsDraft}
                    onChange={setProfileSurgicalAntecedentsDraft}
                    placeholder="Ex. Appendicectomie, césarienne..."
                  />
                  <PatientProfileTextArea
                    label="Allergies"
                    value={profileAllergiesDraft}
                    onChange={setProfileAllergiesDraft}
                    placeholder="Ex. Pénicilline, AINS..."
                  />
                  <PatientProfileTextArea
                    label="Traitements en cours"
                    value={profileTreatmentsDraft}
                    onChange={setProfileTreatmentsDraft}
                    placeholder="Ex. Metformine 500 mg, ramipril..."
                  />
                  <PatientProfileTextArea
                    label="Facteurs de risque"
                    value={profileRiskFactorsDraft}
                    onChange={setProfileRiskFactorsDraft}
                    placeholder="Ex. Tabac, alcool, grossesse, exposition professionnelle..."
                  />
                  <PatientProfileTextArea
                    label="Points d'attention"
                    value={profileAttentionPointsDraft}
                    onChange={setProfileAttentionPointsDraft}
                    placeholder="Ex. Surveiller observance, risque de chute, barrière linguistique..."
                  />
                  <PatientProfileTextArea
                    label="Synthèse médicale"
                    value={profileMedicalSummaryDraft}
                    onChange={setProfileMedicalSummaryDraft}
                    placeholder="Résumé stable du contexte patient."
                    className="sm:col-span-2"
                    rows={4}
                  />
                  <PatientProfileTextArea
                    label="Dernier contexte de consultation"
                    value={profileLastConsultationContextDraft}
                    onChange={setProfileLastConsultationContextDraft}
                    placeholder="Mis à jour automatiquement après une fiche consultation."
                    className="sm:col-span-2"
                    rows={4}
                  />
                </div>
              </div>
              <div className="mt-6">
                <button
                  type="button"
                  disabled={profileSaveSaving}
                  onClick={() => void saveProfileFromModal()}
                  className="w-full rounded-xl bg-[#009CA4] px-4 py-3 font-black text-white hover:bg-[#00838A] disabled:opacity-60"
                >
                  {profileSaveSaving ? "Enregistrement…" : "Enregistrer le profil"}
                </button>
              </div>
              <div className="mt-5 border-t border-[#EEF3F8] pt-4 text-center">
                <button
                  type="button"
                  onClick={() => void openDeletePatientModal()}
                  className="text-sm font-semibold text-[#94A3B8] underline-offset-2 transition hover:text-red-600 hover:underline"
                >
                  Supprimer la fiche patient…
                </button>
              </div>
            </>
          ) : (
            <p className="m-0 text-sm font-semibold text-[#61708B]">Chargement du profil…</p>
          )}
        </Modal>
      )}

      {modal === "addNote" && (
        <Modal title="Ajouter une note" onClose={closeNoteModal} width="max-w-xl">
          <div className="mb-3 flex items-center justify-between gap-3">
            <p className="m-0 text-sm font-semibold text-[#61708B]">
              Écrivez la note ou dictez-la à la voix.
            </p>
            <button
              type="button"
              onClick={toggleNoteDictation}
              disabled={noteTranscribing}
              aria-pressed={noteRecording}
              className={cx(
                "inline-flex shrink-0 items-center gap-2 rounded-xl border px-3.5 py-2 text-sm font-black transition disabled:opacity-60",
                noteRecording
                  ? "border-[#E11D48] bg-[#FFF1F3] text-[#E11D48]"
                  : "border-[#009CA4] bg-white text-[#008EA1] hover:bg-[#F2FBFC]",
              )}
            >
              <span
                className={cx(
                  "grid h-5 w-5 place-items-center rounded-full text-xs",
                  noteRecording ? "animate-pulse bg-[#E11D48] text-white" : "bg-[#E9FAFC] text-[#008EA1]",
                )}
              >
                ●
              </span>
              {noteTranscribing ? "Transcription…" : noteRecording ? "Arrêter la dictée" : "Dicter la note"}
            </button>
          </div>
          <textarea
            autoFocus
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Ex. Préfère les rendez-vous le matin, ne pas appeler après 18h..."
            className="h-40 w-full resize-none rounded-2xl border border-[#DDE7F1] p-4 outline-none focus:border-[#009CA4] focus:ring-4 focus:ring-[#009CA4]/10"
          />
          {noteRecording ? (
            <p className="mt-2 flex items-center gap-2 text-sm font-bold text-[#E11D48]">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-[#E11D48]" />
              Dictée en cours… parlez, puis cliquez sur « Arrêter la dictée ».
            </p>
          ) : noteTranscribing ? (
            <p className="mt-2 text-sm font-bold text-[#008EA1]">Transcription en cours…</p>
          ) : null}
          <button
            onClick={async () => {
              const ok = await saveNote();
              if (ok) setModal(null);
            }}
            disabled={notesSaving || noteRecording || noteTranscribing}
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
          <p className="mt-4 text-center text-sm text-[#61708B]">
            Le document sera visible dans{" "}
            <button type="button" onClick={() => { setModal(null); setActiveView("documents"); }} className="font-black text-[#008EA1] underline">
              Consulter les documents
            </button>
            .
          </p>
        </Modal>
      )}

      {modal === "createConsultation" && (
        <div className="fixed inset-0 z-[100] overflow-auto bg-[#0A1628]/35 backdrop-blur-sm">
          <button
            type="button"
            disabled={consultationSaving}
            onClick={() => {
              if (!consultationSaving) setModal(null);
            }}
            className="fixed right-4 top-4 z-[110] grid h-11 w-11 place-items-center rounded-xl border border-[#DDE7F1] bg-white/95 text-2xl font-black text-[#0A1628] shadow-sm hover:bg-white disabled:opacity-40"
            aria-label="Fermer la fiche consultation"
          >
            ×
          </button>
          <FicheConsultationUWI
            patient={consultationPatient}
            saving={consultationSaving}
            existingNextAppointment={consultationExistingNextAppointment}
            onOpenCreateBooking={() => setCreatePatientBookingOpen(true)}
            initialDraft={{
              consultation_id: consultationInitialDraft.consultationId,
              date: consultationInitialDraft.date,
              motif: consultationInitialDraft.motif,
              appointment_id: consultationInitialDraft.appointmentId,
              source_consultation_id: consultationInitialDraft.sourceConsultationId,
              prefill: consultationInitialDraft.prefill,
            }}
            onLoadPrefill={loadConsultationPrefill}
            onTranscribe={transcribeConsultationAudio}
            onGenerateSummary={generateConsultationSummary}
            onSave={(payload) => submitConsultationForm((payload || {}) as Record<string, unknown>)}
          />
        </div>
      )}

      {modal === "createPatientManual" && (
        <CreatePatientFromCallModal
          open
          showEmail
          emailRequired
          extendedProfile
          loading={manualPatientCreateSaving}
          form={manualPatientCreateForm}
          phoneError={manualPatientCreateFieldErrors.phoneError}
          emailError={manualPatientCreateFieldErrors.emailError}
          birthDateError={manualPatientCreateFieldErrors.birthDateError}
          physicianNameError={manualPatientCreateFieldErrors.physicianNameError}
          physicianCityError={manualPatientCreateFieldErrors.physicianCityError}
          submitDisabled={manualPatientCreateSubmitBlocked}
          onChange={(field, value) => setManualPatientCreateForm((prev) => ({ ...prev, [field]: value }))}
          onClose={() => {
            if (!manualPatientCreateSaving) setModal(null);
          }}
          onSubmit={() => void submitManualPatientCreate()}
          subtitleLine={
            <>
              {manualPatientCreateConflicts.length ? (
                <PatientDuplicateBanner conflicts={manualPatientCreateConflicts} className="mb-3" />
              ) : null}
              <span className="text-[#64748B]">
                Source : <strong>liste patients</strong>
              </span>
            </>
          }
        />
      )}

      {modal === "sendSingleMessage" && (
        <Modal title="Envoyer un message au patient" onClose={() => setModal(null)} width="max-w-xl">
          <div className="space-y-4">
            <div className="rounded-2xl border border-[#E2EAF4] bg-[#F8FBFD] p-3 text-sm font-semibold text-[#334155]">
              Destinataire: <span className="font-black">{displayHero?.name || "Patient"}</span>{" "}
              {singleMessageChannel === "sms" ? `(${formatDisplayFrenchPhone(tenantPatientPhone)})` : patientEmail ? `(${patientEmail})` : ""}
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setSingleMessageChannel("sms")}
                className={cx(
                  "rounded-lg border px-3 py-1.5 text-xs font-black",
                  singleMessageChannel === "sms"
                    ? "border-[#009CA4] bg-[#E9FAFC] text-[#007E8C]"
                    : "border-[#DDE7F1] bg-white text-[#475569]",
                )}
              >
                SMS
              </button>
              <button
                type="button"
                onClick={() => setSingleMessageChannel("email")}
                disabled={!patientEmail}
                className={cx(
                  "rounded-lg border px-3 py-1.5 text-xs font-black",
                  singleMessageChannel === "email"
                    ? "border-[#0EA348] bg-[#F0FFF5] text-[#0EA348]"
                    : "border-[#DDE7F1] bg-white text-[#475569]",
                  !patientEmail ? "opacity-50" : "",
                )}
              >
                Email
              </button>
            </div>
            {singleMessageChannel === "email" ? (
              <label className="block text-sm font-semibold text-[#334155]">
                Objet
                <input
                  value={singleMessageSubject}
                  onChange={(e) => setSingleMessageSubject(e.target.value)}
                  maxLength={180}
                  className="mt-2 w-full rounded-xl border border-[#DDE7F1] bg-white px-3 py-2 font-semibold text-[#0A1628] outline-none focus:border-[#009CA4]"
                />
              </label>
            ) : null}
            <label className="block text-sm font-semibold text-[#334155]">
              Message
              <textarea
                value={singleMessageBody}
                onChange={(e) => setSingleMessageBody(e.target.value)}
                rows={6}
                maxLength={4000}
                placeholder="Votre message pour le patient…"
                className="mt-2 w-full resize-none rounded-xl border border-[#DDE7F1] bg-white px-3 py-2 font-semibold text-[#0A1628] outline-none focus:border-[#009CA4]"
              />
            </label>
            <button
              type="button"
              disabled={singleMessageSending}
              onClick={() => void sendSingleMessage()}
              className="w-full rounded-xl bg-[#009CA4] px-4 py-3 font-black text-white hover:bg-[#00838A] disabled:opacity-60"
            >
              {singleMessageSending
                ? "Envoi…"
                : singleMessageChannel === "sms"
                  ? "Envoyer le SMS"
                  : "Envoyer l'email"}
            </button>
          </div>
        </Modal>
      )}

      {modal === "sendBulkMessage" && (
        <Modal title={bulkModalTitle} onClose={() => setModal(null)} width="max-w-2xl">
          <div className="space-y-4">
            <div className="rounded-2xl border border-[#E2EAF4] bg-[#F8FBFD] p-3 text-sm text-[#334155]">
              {bulkMessageSendToAll ? (
                <span className="font-black">Mode: tous les patients du cabinet</span>
              ) : (
                <span>
                  Patients sélectionnés:{" "}
                  <span className="font-black">
                    {selectedPatientPhones.length}
                  </span>
                </span>
              )}
            </div>
            {bulkMessageSendToAll ? (
              <p className="text-xs font-semibold text-[#64748B]">
                L&apos;envoi couvrira l&apos;ensemble des fiches patients du cabinet.
              </p>
            ) : selectedPatientPhones.length > 0 ? (
              <p className="text-xs font-semibold text-[#64748B]">
                Cibles: {selectedPatientsPreviewLabel}
              </p>
            ) : (
              <p className="text-xs font-semibold text-amber-700">
                Sélectionnez des patients dans la liste ou cochez « Tous les patients du cabinet ».
              </p>
            )}
            <label className="flex items-center gap-2 text-sm font-semibold text-[#334155]">
              <input
                type="checkbox"
                checked={bulkMessageSendToAll}
                onChange={(e) => setBulkMessageSendToAll(e.target.checked)}
              />
              Tous les patients du cabinet
            </label>
            <div className={cx("space-y-3 rounded-2xl border border-[#E2EAF4] bg-white p-3", bulkMessageSendToAll ? "opacity-60" : "")}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-xs font-black uppercase tracking-[0.07em] text-[#64748B]">
                  Sélection dans la modale
                </div>
                <button
                  type="button"
                  disabled={bulkMessageSendToAll || modalSelectablePhones.length === 0}
                  onClick={() => toggleSelectAllModalPatients()}
                  className="rounded-lg border border-[#DDE7F1] bg-white px-2.5 py-1 text-[11px] font-black text-[#475569] hover:bg-[#F8FAFC] disabled:opacity-50"
                >
                  {allModalSelected ? "Tout désélectionner" : "Tout sélectionner"}
                </button>
              </div>
              <input
                value={bulkModalQuery}
                onChange={(e) => setBulkModalQuery(e.target.value)}
                disabled={bulkMessageSendToAll}
                placeholder="Rechercher un patient (nom ou téléphone)…"
                className="h-10 w-full rounded-xl border border-[#DDE7F1] bg-[#F8FBFD] px-3 text-sm font-semibold text-[#0A1628] outline-none focus:border-[#009CA4] disabled:opacity-60"
              />
              <div className="max-h-56 overflow-y-auto rounded-xl border border-[#EEF3F8]">
                {bulkModalRows.length === 0 ? (
                  <div className="p-3 text-sm font-semibold text-[#64748B]">
                    Aucun patient trouvé.
                  </div>
                ) : (
                  bulkModalRows.map((row) => {
                    const checked = selectedPatientPhones.includes(row.phone);
                    return (
                      <label
                        key={`bulk-modal-${row.phone}`}
                        className={cx(
                          "flex cursor-pointer items-center gap-3 border-b border-[#EEF3F8] px-3 py-2.5 last:border-b-0",
                          checked ? "bg-[#EAF8FC]" : "bg-white hover:bg-[#F8FBFD]",
                          bulkMessageSendToAll ? "pointer-events-none" : "",
                        )}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={bulkMessageSendToAll}
                          onChange={() => toggleSelectedPatientPhone(row.phone)}
                          className="h-4 w-4 accent-[#009CA4]"
                        />
                        <div className="min-w-0">
                          <div className="truncate text-sm font-black text-[#0A1628]">{row.name}</div>
                          <div className="text-xs font-semibold text-[#64748B]">{row.displayPhone}</div>
                        </div>
                      </label>
                    );
                  })
                )}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setBulkMessageChannel("sms")}
                className={cx(
                  "rounded-lg border px-3 py-1.5 text-xs font-black",
                  bulkMessageChannel === "sms"
                    ? "border-[#009CA4] bg-[#E9FAFC] text-[#007E8C]"
                    : "border-[#DDE7F1] bg-white text-[#475569]",
                )}
              >
                SMS groupé
              </button>
              <button
                type="button"
                onClick={() => setBulkMessageChannel("email")}
                className={cx(
                  "rounded-lg border px-3 py-1.5 text-xs font-black",
                  bulkMessageChannel === "email"
                    ? "border-[#0EA348] bg-[#F0FFF5] text-[#0EA348]"
                    : "border-[#DDE7F1] bg-white text-[#475569]",
                )}
              >
                Email groupé
              </button>
            </div>
            {bulkMessageChannel === "email" ? (
              <p className="text-xs font-semibold text-[#64748B]">
                Les patients sans email valide seront ignorés automatiquement.
              </p>
            ) : null}
            {bulkMessageChannel === "email" ? (
              <label className="block text-sm font-semibold text-[#334155]">
                Objet
                <input
                  value={bulkMessageSubject}
                  onChange={(e) => setBulkMessageSubject(e.target.value)}
                  maxLength={180}
                  className="mt-2 w-full rounded-xl border border-[#DDE7F1] bg-white px-3 py-2 font-semibold text-[#0A1628] outline-none focus:border-[#009CA4]"
                />
              </label>
            ) : null}
            <label className="block text-sm font-semibold text-[#334155]">
              Message
              <textarea
                value={bulkMessageBody}
                onChange={(e) => setBulkMessageBody(e.target.value)}
                rows={7}
                maxLength={4000}
                placeholder="Message à envoyer en groupe…"
                className="mt-2 w-full resize-none rounded-xl border border-[#DDE7F1] bg-white px-3 py-2 font-semibold text-[#0A1628] outline-none focus:border-[#009CA4]"
              />
            </label>
            <button
              type="button"
              disabled={!canSubmitBulkMessage}
              onClick={() => void sendBulkMessage()}
              className="w-full rounded-xl bg-[#009CA4] px-4 py-3 font-black text-white hover:bg-[#00838A] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {bulkMessageSending ? "Envoi groupé…" : "Lancer l'envoi groupé"}
            </button>
          </div>
        </Modal>
      )}

      {modal === "history" && (
        <Modal title="Historique complet" onClose={() => setModal(null)} width="max-w-4xl">
          <HistoryList items={patientHistory} loading={patientHistoryLoading} extended />
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

      {modal === "cancelAppt" && apptActionTarget ? (
        <Modal title="Annuler le rendez-vous" onClose={closeApptActionModal} width="max-w-lg">
          <div className="space-y-4 text-sm leading-7 text-[#475569]">
            <p className="m-0">
              Confirmer l&apos;annulation du rendez-vous du{" "}
              <strong>
                {apptActionTarget.start.toLocaleDateString("fr-FR", {
                  weekday: "long",
                  day: "numeric",
                  month: "long",
                  year: "numeric",
                })}
              </strong>{" "}
              à <strong>{formatAgendaSlotHour(apptActionTarget.start)}</strong> ?
            </p>
            <p className="m-0 font-semibold text-[#64748B]">
              Le patient sera notifié par SMS. Aucune action sur la fiche patient n&apos;est nécessaire.
            </p>
            <div className="flex flex-wrap gap-3 pt-2">
              <button
                type="button"
                disabled={apptActionLoading}
                onClick={() => void confirmCancelPatientAppointment()}
                className="rounded-xl bg-[#FF3030] px-4 py-3 text-sm font-black text-white hover:bg-[#E11D48] disabled:opacity-60"
              >
                {apptActionLoading ? "Annulation…" : "Confirmer l’annulation"}
              </button>
              <button
                type="button"
                disabled={apptActionLoading}
                onClick={closeApptActionModal}
                className="rounded-xl border border-[#DDE7F1] px-4 py-3 text-sm font-black text-[#334155]"
              >
                Retour
              </button>
            </div>
          </div>
        </Modal>
      ) : null}

      {modal === "rescheduleAppt" && apptActionTarget ? (
        <Modal title="Déplacer le rendez-vous" onClose={closeApptActionModal} width="max-w-xl">
          <p className="mb-4 text-sm font-semibold text-[#61708B]">
            RDV actuel :{" "}
            {apptActionTarget.start.toLocaleDateString("fr-FR", {
              weekday: "long",
              day: "numeric",
              month: "long",
            })}{" "}
            à {formatAgendaSlotHour(apptActionTarget.start)}
          </p>
          <AgendaReschedulePanel
            loading={apptActionLoading}
            onClose={closeApptActionModal}
            onReschedule={(slot) => void confirmReschedulePatientAppointment(slot)}
          />
        </Modal>
      ) : null}

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

      <CreateCabinetBookingModal
        open={createPatientBookingOpen && !!tenantPatientPhone}
        onClose={() => setCreatePatientBookingOpen(false)}
        lockedPatient={{
          patient_name: displayHero?.name || urlPatientHero?.name || "",
          patient_phone: tenantPatientPhone,
          patient_email: patientEmail || "",
        }}
        excludePhoneForDuplicate={tenantPatientPhone}
        introVariant="patient"
        onSuccess={(payload) => {
          setAgendaDaysLoaded(0);
          setAgendaRefreshNonce((n) => n + 1);
          setPatientBookingConfirm(payload);
        }}
      />

      {patientBookingConfirm ? (
        <div
          className="fixed inset-0 z-[130] flex items-end justify-center bg-[#0A1628]/45 p-4 sm:items-center"
          role="dialog"
          aria-modal="true"
          aria-labelledby="patient-booking-confirm-title"
        >
          <div className="w-full max-w-md rounded-[24px] border border-[#E2EAF4] bg-white p-6 text-center shadow-[0_24px_60px_rgba(10,22,40,0.18)]">
            <div
              className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-full bg-[#EAF8EF] text-2xl font-black text-[#16A34A]"
              aria-hidden
            >
              ✓
            </div>
            <h2 id="patient-booking-confirm-title" className="text-xl font-black text-[#0A1628]">
              Rendez-vous confirmé
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-[#53647F]">
              Le rendez-vous du{" "}
              <strong className="text-[#0A1628]">{formatLongDateFR(patientBookingConfirm.bookingDate)}</strong> à{" "}
              <strong className="text-[#0A1628]">{formatTimeChoiceFR(patientBookingConfirm.bookingTime)}</strong> est bien
              confirmé pour <strong className="text-[#0A1628]">{patientBookingConfirm.patientName}</strong>.
            </p>
            {patientBookingConfirm.motif ? (
              <p className="mt-2 text-xs font-semibold text-[#7D8CA5]">
                Motif : {patientBookingConfirm.motif}
              </p>
            ) : null}
            <button
              type="button"
              onClick={() => setPatientBookingConfirm(null)}
              className="mt-6 w-full rounded-xl bg-[#009CA4] px-4 py-3 text-sm font-black text-white hover:bg-[#00838A]"
            >
              OK
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function HistoryList({
  items,
  loading = false,
  extended = false,
}: {
  items: PatientHistoryItem[];
  loading?: boolean;
  extended?: boolean;
}) {
  if (loading) {
    return <p className="text-sm font-semibold text-[#61708B]">Chargement de l&apos;historique…</p>;
  }
  if (!items.length) {
    return (
      <p className="text-sm font-semibold text-[#61708B]">
        Aucune interaction enregistrée pour ce patient (appels Clara, notes, documents, rendez-vous passés).
      </p>
    );
  }

  const rows = extended ? items : items.slice(0, 8);

  return (
    <div className="space-y-0 overflow-hidden rounded-2xl border border-[#EEF3F8] bg-white">
      {rows.map((row) => (
        <div
          key={row.id}
          className="grid grid-cols-1 gap-3 border-b border-[#EEF3F8] p-4 last:border-b-0 sm:grid-cols-[16px_110px_150px_1fr_180px] sm:items-center sm:gap-4"
        >
          <span
            className={cx(
              "hidden h-3 w-3 rounded-full sm:inline-block",
              row.tone === "green" ? "bg-[#18C765]" : row.tone === "red" ? "bg-[#EF4444]" : "bg-[#FF9E18]",
            )}
          />
          <div className="text-sm text-[#61708B]"><b>{row.date_label}</b><br />{row.time_label}</div>
          <div className="font-black">{row.type_label}</div>
          <div className="text-sm text-[#53647F]">{row.summary}</div>
          <span
            className={cx(
              "rounded-lg px-3 py-2 text-center text-xs font-black sm:justify-self-end",
              row.tone === "green"
                ? "bg-[#E8FAF0] text-[#0B9445]"
                : row.tone === "red"
                  ? "bg-[#FEE2E2] text-[#B91C1C]"
                  : "bg-[#FFF1DE] text-[#D96B00]",
            )}
          >
            {row.status_label}
          </span>
        </div>
      ))}
    </div>
  );
}
