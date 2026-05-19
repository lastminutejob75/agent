import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  Building2,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  Clock3,
  CreditCard,
  ExternalLink,
  FileText,
  Globe2,
  MapPin,
  PauseCircle,
  Phone,
  Plus,
  RefreshCw,
  Save,
  Settings2,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  TestTube2,
  UserRound,
  Wand2,
  X,
} from "lucide-react";
import { api } from "../lib/api.js";

const C = {
  navy: "#071A33",
  teal: "#009CA4",
  tealDark: "#06747A",
  bg: "#F4F8FA",
  yellow: "#F5C842",
};

const TABS = [
  { id: "cabinet", label: "Cabinet", icon: Building2 },
  { id: "horaires", label: "Horaires", icon: Clock3 },
  { id: "regles", label: "Règles RDV", icon: CalendarDays },
  { id: "clara", label: "Clara", icon: Sparkles },
  { id: "abonnement", label: "Abonnement", icon: CreditCard },
];

const PLAN_META = {
  starter: { name: "Starter", price: 99, overage: 0.19 },
  growth: { name: "Growth", price: 149, overage: 0.17 },
  pro: { name: "Pro", price: 199, overage: 0.15 },
};

const DAYS = [
  { key: "monday", label: "Lundi" },
  { key: "tuesday", label: "Mardi" },
  { key: "wednesday", label: "Mercredi" },
  { key: "thursday", label: "Jeudi" },
  { key: "friday", label: "Vendredi" },
  { key: "saturday", label: "Samedi" },
  { key: "sunday", label: "Dimanche" },
];

const emptyProfile = {
  practitioner_name: "",
  cabinet_name: "",
  specialty: "",
  phone: "",
  email: "",
  address_line: "",
  postal_code: "",
  city: "",
  website_url: "",
  languages: [],
  accepts_new_patients: true,
  practitioner_photo_url: "",
  public_page_url: "",
};

const emptyAvailability = {
  temporary_closure_enabled: false,
  temporary_closure_start: "",
  temporary_closure_end: "",
  temporary_closure_message: "",
};

const emptyBookingRules = {
  default_appointment_duration_minutes: 30,
  minimum_booking_notice_hours: 24,
  accepts_new_patients: true,
  appointment_reschedule_allowed: true,
  appointment_reschedule_notice_hours: 24,
  appointment_cancel_allowed: true,
  appointment_cancel_notice_hours: 24,
  emergency_instruction: "",
  new_patient_instruction: "",
  booking_notes: "",
};

const emptyAssistant = {
  assistant_name: "Clara",
  welcome_message: "",
  documents_to_bring: "",
  access_instructions: "",
  payment_methods: "",
  parking_info: "",
  pmr_access: "",
  sensitive_medical_instruction: "Clara ne donne jamais d'avis medical.",
  escalation_instruction: "",
  human_handoff_instruction: "",
  faq_items: [],
};

function StatusPill({ children, tone = "teal", icon: Icon = CheckCircle2 }) {
  const cls =
    tone === "warning"
      ? "border-amber-200 bg-amber-50 text-amber-800"
      : tone === "navy"
        ? "border-slate-700 bg-white/10 text-white"
        : "border-[#BFE9EC] bg-[#E8F7F7] text-[#06747A]";
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-bold ${cls}`}>
      <Icon className="h-3.5 w-3.5" />
      {children}
    </span>
  );
}

function ActionButton({ children, variant = "primary", icon: Icon, ...rest }) {
  const cls =
    variant === "primary"
      ? "bg-[#009CA4] text-white shadow-lg shadow-[#009CA4]/20 hover:bg-[#06747A]"
      : variant === "dark"
        ? "bg-[#071A33] text-white hover:bg-[#0A1628]"
        : "border border-slate-200 bg-white text-slate-700 hover:border-[#009CA4]/50 hover:text-[#06747A]";
  return (
    <button
      className={`inline-flex h-11 items-center justify-center gap-2 rounded-2xl px-4 text-sm font-extrabold transition disabled:cursor-not-allowed disabled:opacity-60 ${cls}`}
      {...rest}
    >
      {Icon ? <Icon className="h-4 w-4" /> : null}
      {children}
    </button>
  );
}

function SectionCard({ title, subtitle, icon: Icon, children, action, id }) {
  return (
    <motion.section
      id={id}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/60"
    >
      <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[#E8F7F7] text-[#06747A]">
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-lg font-black tracking-tight text-[#071A33]">{title}</h2>
            <p className="mt-1 max-w-2xl text-sm font-medium leading-6 text-slate-500">{subtitle}</p>
          </div>
        </div>
        {action}
      </div>
      {children}
    </motion.section>
  );
}

function Field({ label, value, onChange, icon: Icon, type = "text", wide, placeholder, error }) {
  return (
    <label className={wide ? "md:col-span-2 block" : "block"}>
      <span className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.14em] text-slate-500">
        {Icon ? <Icon className="h-3.5 w-3.5" /> : null}
        {label}
      </span>
      <input
        type={type}
        value={value || ""}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className={`h-12 w-full rounded-2xl border bg-white px-4 text-sm font-semibold text-slate-800 outline-none transition focus:ring-4 focus:ring-[#009CA4]/10 ${
          error ? "border-red-300 focus:border-red-400" : "border-slate-200 focus:border-[#009CA4]"
        }`}
      />
      {error ? <p className="mt-1 text-xs font-semibold text-red-600">{error}</p> : null}
    </label>
  );
}

function TextArea({ label, value, onChange, rows = 4 }) {
  return (
    <label className="block">
      <span className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.14em] text-slate-500">{label}</span>
      <textarea
        rows={rows}
        value={value || ""}
        onChange={(event) => onChange(event.target.value)}
        className="w-full resize-none rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium leading-6 text-slate-800 outline-none transition focus:border-[#009CA4] focus:ring-4 focus:ring-[#009CA4]/10"
      />
    </label>
  );
}

function ComingSoonBadge() {
  return (
    <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-bold text-amber-800">
      Bientot dispo
    </span>
  );
}

function Modal({ title, open, onClose, children }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div className="w-full max-w-2xl rounded-3xl border border-slate-200 bg-white p-5 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-black text-[#071A33]">{title}</h3>
          <button type="button" onClick={onClose} className="rounded-xl p-2 text-slate-500 hover:bg-slate-100">
            <X className="h-5 w-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function toHourOnly(hhmm) {
  const raw = String(hhmm || "").trim();
  if (!raw.includes(":")) return 9;
  const h = Number(raw.split(":")[0]);
  return Number.isFinite(h) ? h : 9;
}

function normalizeHoursForUi(payload) {
  const byDay = new Map((payload?.opening_hours || []).map((item) => [String(item.day || ""), item]));
  return DAYS.map((day) => {
    const row = byDay.get(day.key) || {};
    return {
      day: day.key,
      label: day.label,
      is_open: Boolean(row.is_open),
      morning_start: row.morning_start || "08:30",
      morning_end: row.morning_end || "12:30",
      afternoon_start: row.afternoon_start || "14:00",
      afternoon_end: row.afternoon_end || "18:30",
    };
  });
}

export default function ClientCabinetProfilePage() {
  const restrictedMode = true;
  const editableTabs = new Set(["cabinet", "horaires"]);
  const [userRole, setUserRole] = useState("owner");
  const isOwner = userRole === "owner";
  const visibleTabs = useMemo(
    () => TABS.filter((tab) => isOwner || tab.id !== "abonnement"),
    [isOwner],
  );
  const [active, setActive] = useState("cabinet");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [dirty, setDirty] = useState(false);

  const [profile, setProfile] = useState(emptyProfile);
  const [profileErrors, setProfileErrors] = useState({});
  const [openingHours, setOpeningHours] = useState(normalizeHoursForUi({ opening_hours: [] }));
  const [availability, setAvailability] = useState(emptyAvailability);
  const [bookingRules, setBookingRules] = useState(emptyBookingRules);
  const [appointmentReasons, setAppointmentReasons] = useState([]);
  const [assistant, setAssistant] = useState(emptyAssistant);
  const [calendarStatus, setCalendarStatus] = useState({ connected: false, permission_status: "unknown" });
  const [profileSummary, setProfileSummary] = useState({
    profile_completion_percentage: 0,
    calendar_connected: false,
    billing_status: "unknown",
    current_plan: "growth",
    used_minutes_current_month: 0,
    missing_items: [],
  });
  const [billingSummary, setBillingSummary] = useState({
    current_plan: "growth",
    monthly_price: 149,
    included_minutes: 800,
    used_minutes_current_month: 0,
    usage_percentage: 0,
    estimated_overage_minutes: 0,
    estimated_overage_cost: 0,
    billing_status: "unknown",
    payment_method_brand: "",
    payment_method_last4: "",
    next_invoice_date: "",
    plans: [],
  });
  const [invoices, setInvoices] = useState([]);
  const [loadingInvoices, setLoadingInvoices] = useState(false);

  const [testClaraOpen, setTestClaraOpen] = useState(false);
  const [testClaraMessage, setTestClaraMessage] = useState("");
  const [testClaraAnswer, setTestClaraAnswer] = useState("");
  const [testBookingOpen, setTestBookingOpen] = useState(false);
  const [testBookingMessage, setTestBookingMessage] = useState("");
  const [testBookingResult, setTestBookingResult] = useState(null);

  const absenceRef = useRef(null);
  const claraRef = useRef(null);
  const billingRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    async function loadAll() {
      setLoading(true);
      setError("");
      try {
        const me = await api.tenantMe().catch(() => null);
        const role = String(me?.role || "owner").toLowerCase();
        const owner = role === "owner";
        if (!cancelled) {
          setUserRole(role);
          if (!owner && active === "abonnement") {
            setActive("cabinet");
          }
        }

        const baseRequests = [
          api.tenantGetProfile(),
          api.tenantGetOpeningHours(),
          api.tenantGetAvailabilitySettings(),
          api.tenantGetBookingRules(),
          api.tenantGetAppointmentReasons(),
          api.tenantGetAssistantSettings(),
          api.tenantGetCalendarStatus().catch(() => ({ connected: false, permission_status: "unknown" })),
          api.tenantGetProfileSummary().catch(() => null),
        ];
        if (owner) {
          baseRequests.push(api.tenantGetBillingSummary().catch(() => null));
        }

        const results = await Promise.all(baseRequests);
        const [
          profileData,
          openingData,
          availabilityData,
          bookingData,
          reasonsData,
          assistantData,
          calendarData,
          summaryData,
          billingData,
        ] = owner
          ? results
          : [...results, null];

        if (cancelled) return;
        setProfile({ ...emptyProfile, ...(profileData || {}) });
        setOpeningHours(normalizeHoursForUi(openingData || {}));
        setAvailability({ ...emptyAvailability, ...(availabilityData || {}) });
        setBookingRules({ ...emptyBookingRules, ...(bookingData || {}) });
        setAppointmentReasons(Array.isArray(reasonsData?.items) ? reasonsData.items : []);
        setAssistant({ ...emptyAssistant, ...(assistantData || {}) });
        setCalendarStatus(calendarData || { connected: false, permission_status: "unknown" });
        if (summaryData) setProfileSummary(summaryData);
        if (billingData) setBillingSummary((prev) => ({ ...prev, ...billingData }));
        setDirty(false);
      } catch (e) {
        if (cancelled) return;
        setError(e?.message || "Impossible de charger les donnees du cabinet.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadAll();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!dirty) return undefined;
    const handler = (event) => {
      event.preventDefault();
      event.returnValue = "";
      return "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  function markDirty() {
    setDirty(true);
    setSuccess("");
  }

  function showComingSoon(featureLabel = "Cette fonctionnalite") {
    setError("");
    setSuccess(`${featureLabel} sera bientot disponible. Pour l'instant, UWi configure ce module pour vous.`);
  }

  function setTab(next) {
    if (dirty && next !== active) {
      const ok = window.confirm("Des modifications non enregistrees seront perdues. Continuer ?");
      if (!ok) return;
    }
    setActive(next);
  }

  function parseLanguages(value) {
    return String(value || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function validateProfile() {
    const next = {};
    if (!String(profile.email || "").match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)) next.email = "Email invalide";
    if (profile.website_url && !String(profile.website_url).match(/^https?:\/\//i)) next.website_url = "URL invalide";
    if (profile.phone && String(profile.phone).replace(/[^\d+]/g, "").length < 10) next.phone = "Telephone invalide";
    setProfileErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleSave() {
    if (restrictedMode && !editableTabs.has(active)) {
      showComingSoon("La sauvegarde de cet onglet");
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      if (active === "cabinet") {
        if (!validateProfile()) return;
        await api.tenantPatchProfile(profile);
      } else if (active === "horaires") {
        await api.tenantPatchOpeningHours({ opening_hours: openingHours });
        await api.tenantPatchAvailabilitySettings(availability);
      } else if (active === "regles") {
        await api.tenantPatchBookingRules(bookingRules);
      } else if (active === "clara") {
        await api.tenantPatchAssistantSettings(assistant);
      }
      const [summaryData, billingData] = await Promise.all([
        api.tenantGetProfileSummary().catch(() => null),
        api.tenantGetBillingSummary().catch(() => null),
      ]);
      if (summaryData) setProfileSummary(summaryData);
      if (billingData) setBillingSummary((prev) => ({ ...prev, ...billingData }));
      setDirty(false);
      setSuccess("Modifications enregistrees.");
    } catch (e) {
      setError(e?.message || "Echec de sauvegarde.");
    } finally {
      setSaving(false);
    }
  }

  async function createReason() {
    const label = window.prompt("Nom du motif");
    if (!label) return;
    try {
      const created = await api.tenantCreateAppointmentReason({ label, duration_minutes: 30, enabled: true });
      setAppointmentReasons((prev) => [...prev, created]);
      setDirty(true);
    } catch (e) {
      setError(e?.message || "Impossible d'ajouter le motif.");
    }
  }

  async function toggleReason(reason) {
    try {
      const updated = await api.tenantPatchAppointmentReason(reason.id, { enabled: !reason.enabled });
      setAppointmentReasons((prev) => prev.map((item) => (item.id === reason.id ? updated : item)));
      setDirty(true);
    } catch (e) {
      setError(e?.message || "Impossible de modifier le motif.");
    }
  }

  async function removeReason(reason) {
    try {
      await api.tenantDeleteAppointmentReason(reason.id);
      setAppointmentReasons((prev) => prev.map((item) => (item.id === reason.id ? { ...item, enabled: false } : item)));
      setDirty(true);
    } catch (e) {
      setError(e?.message || "Impossible de desactiver le motif.");
    }
  }

  async function runClaraPreview() {
    try {
      const data = await api.tenantAssistantPreview(testClaraMessage);
      setTestClaraAnswer(data?.answer || "");
    } catch (e) {
      setTestClaraAnswer(e?.message || "Erreur pendant la simulation.");
    }
  }

  async function runBookingPreview() {
    try {
      const data = await api.tenantTestBookingRule(testBookingMessage);
      setTestBookingResult(data || null);
    } catch (e) {
      setTestBookingResult({ allowed: false, simulated_answer: e?.message || "Simulation impossible." });
    }
  }

  async function loadInvoices() {
    setLoadingInvoices(true);
    try {
      const data = await api.tenantGetBillingInvoices();
      setInvoices(Array.isArray(data?.items) ? data.items : []);
    } catch (e) {
      setError(e?.message || "Impossible de charger les factures.");
    } finally {
      setLoadingInvoices(false);
    }
  }

  async function openBillingPortal() {
    try {
      const data = await api.tenantBillingPortalSession();
      if (data?.url) {
        window.location.href = data.url;
        return;
      }
      setError("Le portail de facturation est indisponible.");
    } catch (e) {
      setError(e?.message || "Portail Stripe indisponible.");
    }
  }

  async function changePlan(planKey) {
    try {
      await api.tenantBillingChangePlan(planKey);
      const next = await api.tenantGetBillingSummary();
      setBillingSummary((prev) => ({ ...prev, ...(next || {}) }));
      setSuccess("Offre mise a jour.");
    } catch (e) {
      setError(e?.message || "Impossible de changer d'offre.");
    }
  }

  function openPublicPage() {
    if (!profile.public_page_url) return;
    window.open(profile.public_page_url, "_blank", "noopener,noreferrer");
  }

  function goToAbsence() {
    setTab("horaires");
    setTimeout(() => absenceRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 40);
  }

  function goToClara() {
    setTab("clara");
    setTimeout(() => claraRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 40);
  }

  function goToBilling() {
    if (!isOwner) {
      setError("La facturation est reservee au titulaire du cabinet.");
      return;
    }
    setTab("abonnement");
    setTimeout(() => billingRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 40);
  }

  const activeIcon = useMemo(() => TABS.find((tab) => tab.id === active)?.icon || Building2, [active]);
  const planKey = String(billingSummary.current_plan || "growth").toLowerCase();
  const planMeta = PLAN_META[planKey] || PLAN_META.growth;

  if (loading) {
    return (
      <div className="min-h-[60vh] rounded-3xl border border-slate-200 bg-white p-8 text-sm font-semibold text-slate-500">
        Chargement de la page Mon cabinet...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F4F8FA] p-2 text-slate-900 md:p-5">
      <div className="mx-auto max-w-7xl">
        <header className="overflow-hidden rounded-[1.7rem] bg-[#071A33] text-white shadow-xl shadow-slate-300/50 md:rounded-[2.4rem] md:shadow-2xl md:shadow-slate-300/60">
          <div className="relative p-5 md:p-8">
            <div className="absolute right-0 top-0 hidden h-56 w-56 rounded-full bg-[#009CA4]/30 blur-3xl md:block" />
            <div className="absolute bottom-0 right-32 hidden h-28 w-28 rounded-full bg-[#F5C842]/20 blur-2xl md:block" />
            <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <div className="mb-4 flex flex-wrap gap-2">
                  <StatusPill tone="navy" icon={activeIcon}>
                    Page client
                  </StatusPill>
                  <StatusPill tone="navy" icon={ShieldCheck}>
                    {calendarStatus.connected ? "Agenda connecte" : "Agenda a reconnecter"}
                  </StatusPill>
                  <StatusPill tone="navy" icon={CreditCard}>
                    {String(profileSummary.billing_status || "").toLowerCase() === "active" ? "Abonnement actif" : "Paiement a verifier"}
                  </StatusPill>
                </div>
                <h1 className="text-4xl font-black tracking-tight md:text-5xl">Mon cabinet</h1>
                <p className="mt-3 max-w-2xl text-sm font-medium leading-6 text-white/75 md:text-base md:leading-7 md:text-white/70">
                  Mettez a jour les informations du cabinet, les regles de rendez-vous, les reponses de Clara et votre abonnement UWi.
                </p>
              </div>
              <div className="hidden gap-3 sm:grid-cols-3 lg:min-w-[520px] md:grid">
                <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
                  <p className="text-2xl font-black">{profileSummary.profile_completion_percentage || 0}%</p>
                  <p className="mt-1 text-xs font-bold text-white/60">profil complete</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
                  <p className="text-2xl font-black">{profileSummary.used_minutes_current_month || 0}</p>
                  <p className="mt-1 text-xs font-bold text-white/60">minutes ce mois-ci</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
                  <p className="text-2xl font-black">{String(profileSummary.current_plan || "growth").toUpperCase()}</p>
                  <p className="mt-1 text-xs font-bold text-white/60">offre active</p>
                </div>
              </div>
            </div>
          </div>
        </header>
        <div className="mt-3 grid grid-cols-1 gap-2 md:hidden">
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
            <p className="text-xl font-black text-[#071A33]">{profileSummary.profile_completion_percentage || 0}%</p>
            <p className="mt-1 text-xs font-bold text-slate-500">profil complete</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
            <p className="text-xl font-black text-[#071A33]">{profileSummary.used_minutes_current_month || 0}</p>
            <p className="mt-1 text-xs font-bold text-slate-500">minutes ce mois-ci</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
            <p className="text-xl font-black text-[#071A33]">{String(profileSummary.current_plan || "growth").toUpperCase()}</p>
            <p className="mt-1 text-xs font-bold text-slate-500">offre active</p>
          </div>
        </div>

        <div className="sticky top-0 z-20 mt-5 rounded-[1.7rem] border border-slate-200 bg-white/90 p-2 shadow-sm backdrop-blur">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
            <nav className="flex gap-2 overflow-x-auto">
              {visibleTabs.map((tab) => {
                const Icon = tab.icon;
                const selected = active === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setTab(tab.id)}
                    className={`flex h-12 shrink-0 items-center gap-2 rounded-2xl px-4 text-sm font-black transition ${
                      selected
                        ? "bg-[#071A33] text-white shadow-lg shadow-slate-300/80"
                        : "text-slate-500 hover:bg-slate-50 hover:text-[#071A33]"
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {tab.label}
                  </button>
                );
              })}
            </nav>
            <div className="flex flex-wrap gap-2">
              <ActionButton variant="secondary" icon={ExternalLink} onClick={openPublicPage} disabled={!profile.public_page_url}>
                Previsualiser
              </ActionButton>
              <ActionButton variant="secondary" icon={TestTube2} onClick={() => showComingSoon("Le test Clara")} disabled>
                Bientot dispo
              </ActionButton>
              <ActionButton icon={Save} onClick={handleSave} disabled={saving || !dirty || (restrictedMode && !editableTabs.has(active))}>
                {saving
                  ? "Enregistrement..."
                  : active === "horaires"
                    ? "Enregistrer horaires et absences"
                    : active === "cabinet"
                      ? "Enregistrer le cabinet"
                      : "Bientot dispo"}
              </ActionButton>
            </div>
          </div>
        </div>

        {!isOwner ? (
          <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">
            Compte collaborateur : la facturation et les parametres systeme sont reserves au titulaire du cabinet.
          </div>
        ) : null}
        {restrictedMode ? (
          <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-900">
            Mode lancement: les sections <strong>Cabinet</strong> et <strong>Horaires / conges</strong> sont actives.
            Les autres reglages restent temporairement en lecture seule.
          </div>
        ) : null}

        {error ? (
          <div className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">{error}</div>
        ) : null}
        {success ? (
          <div className="mt-4 rounded-2xl border border-[#BFE9EC] bg-[#E8F7F7] px-4 py-3 text-sm font-semibold text-[#06747A]">{success}</div>
        ) : null}
        {dirty ? (
          <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-800">
            Modifications non enregistrees.
          </div>
        ) : null}

        <main className="mt-5 grid gap-5 lg:grid-cols-[1fr_320px]">
          <div className="grid gap-5">
            {active === "cabinet" ? (
              <>
                <SectionCard
                  title="Identite du cabinet"
                  subtitle="Ces informations sont utilisees sur la fiche publique et dans les reponses de Clara."
                  icon={Building2}
                  action={
                    <ActionButton variant="secondary" icon={ExternalLink} onClick={openPublicPage} disabled={!profile.public_page_url}>
                      Voir la fiche publique
                    </ActionButton>
                  }
                >
                  <div className="grid gap-4 md:grid-cols-[160px_1fr]">
                    <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4 text-center">
                      <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-[2rem] bg-[#071A33] text-3xl font-black text-white shadow-inner">
                        {(profile.practitioner_name || "MC")
                          .split(/\s+/)
                          .map((word) => word[0])
                          .join("")
                          .slice(0, 2)
                          .toUpperCase()}
                      </div>
                      <button className="mt-4 inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700">
                        Changer photo (bientot)
                      </button>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      <Field label="Nom du praticien" value={profile.practitioner_name} onChange={(v) => { setProfile((p) => ({ ...p, practitioner_name: v })); markDirty(); }} icon={UserRound} />
                      <Field label="Nom du cabinet" value={profile.cabinet_name} onChange={(v) => { setProfile((p) => ({ ...p, cabinet_name: v })); markDirty(); }} icon={Building2} />
                      <Field label="Specialite" value={profile.specialty} onChange={(v) => { setProfile((p) => ({ ...p, specialty: v })); markDirty(); }} icon={Stethoscope} />
                      <Field label="Telephone cabinet" value={profile.phone} onChange={(v) => { setProfile((p) => ({ ...p, phone: v })); markDirty(); }} icon={Phone} error={profileErrors.phone} />
                      <Field label="Email de contact" value={profile.email} onChange={(v) => { setProfile((p) => ({ ...p, email: v })); markDirty(); }} icon={FileText} type="email" error={profileErrors.email} />
                      <Field label="Site web" value={profile.website_url} onChange={(v) => { setProfile((p) => ({ ...p, website_url: v })); markDirty(); }} icon={Globe2} error={profileErrors.website_url} />
                      <Field label="Adresse" value={profile.address_line} onChange={(v) => { setProfile((p) => ({ ...p, address_line: v })); markDirty(); }} icon={MapPin} wide />
                      <Field label="Code postal" value={profile.postal_code} onChange={(v) => { setProfile((p) => ({ ...p, postal_code: v })); markDirty(); }} />
                      <Field label="Ville" value={profile.city} onChange={(v) => { setProfile((p) => ({ ...p, city: v })); markDirty(); }} />
                      <Field
                        label="Langues (separees par virgule)"
                        value={profile.languages.join(", ")}
                        onChange={(v) => {
                          setProfile((p) => ({ ...p, languages: parseLanguages(v) }));
                          markDirty();
                        }}
                        wide
                      />
                      <label className="md:col-span-2 flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">
                        <input
                          type="checkbox"
                          checked={Boolean(profile.accepts_new_patients)}
                          onChange={(event) => {
                            setProfile((p) => ({ ...p, accepts_new_patients: event.target.checked }));
                            markDirty();
                          }}
                        />
                        Accepte de nouveaux patients
                      </label>
                    </div>
                  </div>
                </SectionCard>
              </>
            ) : null}

            {active === "horaires" ? (
              <>
                <SectionCard
                  title="Horaires d'ouverture"
                  subtitle="Clara utilise ces horaires pour repondre aux patients et proposer les bons creneaux."
                  icon={Clock3}
                  action={<ActionButton variant="secondary" icon={Plus} disabled>Bientot dispo</ActionButton>}
                >
                  <div className="overflow-hidden rounded-[1.5rem] border border-slate-200">
                    {openingHours.map((row, idx) => (
                      <div key={row.day} className={`grid grid-cols-1 gap-3 px-4 py-3 text-sm md:grid-cols-[1fr_1.3fr_1.3fr_.8fr] md:items-center ${idx !== openingHours.length - 1 ? "border-b border-slate-100" : ""}`}>
                        <div className="font-black text-[#071A33]">{row.label}</div>
                        <div>
                          <input
                            value={row.morning_start}
                            onChange={(event) => {
                              setOpeningHours((prev) => prev.map((item) => (item.day === row.day ? { ...item, morning_start: event.target.value } : item)));
                              markDirty();
                            }}
                            className="w-20 rounded-lg border border-slate-200 px-2 py-1 text-xs"
                          />
                          <span className="mx-1">-</span>
                          <input
                            value={row.morning_end}
                            onChange={(event) => {
                              setOpeningHours((prev) => prev.map((item) => (item.day === row.day ? { ...item, morning_end: event.target.value } : item)));
                              markDirty();
                            }}
                            className="w-20 rounded-lg border border-slate-200 px-2 py-1 text-xs"
                          />
                        </div>
                        <div>
                          <input
                            value={row.afternoon_start}
                            onChange={(event) => {
                              setOpeningHours((prev) => prev.map((item) => (item.day === row.day ? { ...item, afternoon_start: event.target.value } : item)));
                              markDirty();
                            }}
                            className="w-20 rounded-lg border border-slate-200 px-2 py-1 text-xs"
                          />
                          <span className="mx-1">-</span>
                          <input
                            value={row.afternoon_end}
                            onChange={(event) => {
                              setOpeningHours((prev) => prev.map((item) => (item.day === row.day ? { ...item, afternoon_end: event.target.value } : item)));
                              markDirty();
                            }}
                            className="w-20 rounded-lg border border-slate-200 px-2 py-1 text-xs"
                          />
                        </div>
                        <label className="inline-flex items-center gap-2 text-xs font-bold text-slate-600">
                          <input
                            type="checkbox"
                            checked={row.is_open}
                            onChange={(event) => {
                              setOpeningHours((prev) => prev.map((item) => (item.day === row.day ? { ...item, is_open: event.target.checked } : item)));
                              markDirty();
                            }}
                          />
                          {row.is_open ? "Ouvert" : "Ferme"}
                        </label>
                      </div>
                    ))}
                  </div>
                </SectionCard>

                <SectionCard
                  id="absence-temporaire"
                  title="Absence temporaire"
                  subtitle="Activez un message special quand le cabinet est ferme, en conge ou indisponible."
                  icon={PauseCircle}
                >
                  <div ref={absenceRef} className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
                    <label className="flex items-center gap-3 text-sm font-bold text-[#071A33]">
                      <input
                        type="checkbox"
                        checked={Boolean(availability.temporary_closure_enabled)}
                        onChange={(event) => {
                          setAvailability((prev) => ({ ...prev, temporary_closure_enabled: event.target.checked }));
                          markDirty();
                        }}
                      />
                      Mode cabinet ferme temporairement
                    </label>
                    {availability.temporary_closure_enabled ? (
                      <div className="mt-4 grid gap-4 md:grid-cols-2">
                        <Field label="Debut" type="date" value={availability.temporary_closure_start} onChange={(v) => { setAvailability((prev) => ({ ...prev, temporary_closure_start: v })); markDirty(); }} />
                        <Field label="Fin" type="date" value={availability.temporary_closure_end} onChange={(v) => { setAvailability((prev) => ({ ...prev, temporary_closure_end: v })); markDirty(); }} />
                        <div className="md:col-span-2">
                          <TextArea
                            label="Message transmis aux patients"
                            value={availability.temporary_closure_message}
                            onChange={(v) => {
                              setAvailability((prev) => ({ ...prev, temporary_closure_message: v }));
                              markDirty();
                            }}
                          />
                        </div>
                      </div>
                    ) : null}
                  </div>
                </SectionCard>
              </>
            ) : null}

            {active === "regles" ? (
              <>
                <SectionCard
                  title="Regles de prise de rendez-vous"
                  subtitle="Definissez ce que Clara peut proposer, deplacer, annuler ou rediriger."
                  icon={CalendarDays}
                  action={<ActionButton icon={TestTube2} disabled>Bientot dispo</ActionButton>}
                >
                  <div className="mb-3"><ComingSoonBadge /></div>
                  <fieldset disabled className="grid gap-4 opacity-70 md:grid-cols-2">
                    <Field label="Duree moyenne d'un RDV (min)" value={String(bookingRules.default_appointment_duration_minutes || "")} onChange={(v) => { setBookingRules((prev) => ({ ...prev, default_appointment_duration_minutes: Number(v || 0) })); markDirty(); }} />
                    <Field label="Delai minimum avant RDV (h)" value={String(bookingRules.minimum_booking_notice_hours || "")} onChange={(v) => { setBookingRules((prev) => ({ ...prev, minimum_booking_notice_hours: Number(v || 0) })); markDirty(); }} />
                    <Field label="Delai deplacement (h)" value={String(bookingRules.appointment_reschedule_notice_hours || "")} onChange={(v) => { setBookingRules((prev) => ({ ...prev, appointment_reschedule_notice_hours: Number(v || 0) })); markDirty(); }} />
                    <Field label="Delai annulation (h)" value={String(bookingRules.appointment_cancel_notice_hours || "")} onChange={(v) => { setBookingRules((prev) => ({ ...prev, appointment_cancel_notice_hours: Number(v || 0) })); markDirty(); }} />
                    <TextArea label="Consigne urgence" value={bookingRules.emergency_instruction} onChange={(v) => { setBookingRules((prev) => ({ ...prev, emergency_instruction: v })); markDirty(); }} />
                    <TextArea label="Consigne nouveaux patients" value={bookingRules.new_patient_instruction} onChange={(v) => { setBookingRules((prev) => ({ ...prev, new_patient_instruction: v })); markDirty(); }} />
                  </fieldset>
                </SectionCard>

                <SectionCard title="Motifs acceptes" subtitle="Clara filtre les demandes pour eviter les rendez-vous non pertinents." icon={Settings2}>
                  <fieldset disabled className="grid gap-3 opacity-70 md:grid-cols-2">
                    {appointmentReasons.map((reason) => (
                      <div key={reason.id} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3">
                        <div>
                          <p className="text-sm font-black text-slate-700">{reason.label}</p>
                          <p className="text-xs font-semibold text-slate-500">{reason.duration_minutes} min</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <button type="button" onClick={() => toggleReason(reason)} className={`rounded-xl px-3 py-1 text-xs font-bold ${reason.enabled ? "bg-[#E8F7F7] text-[#06747A]" : "bg-slate-100 text-slate-500"}`}>
                            {reason.enabled ? "Actif" : "Inactif"}
                          </button>
                          <button type="button" onClick={() => removeReason(reason)} className="rounded-xl border border-slate-200 px-3 py-1 text-xs font-bold text-slate-600">
                            Desactiver
                          </button>
                        </div>
                      </div>
                    ))}
                  </fieldset>
                  <button disabled className="mt-4 inline-flex items-center gap-2 rounded-2xl border border-dashed border-[#009CA4]/50 bg-[#E8F7F7] px-4 py-3 text-sm font-black text-[#06747A] opacity-70">
                    <Plus className="h-4 w-4" /> Ajouter un motif
                  </button>
                </SectionCard>
              </>
            ) : null}

            {active === "clara" ? (
              <>
                <SectionCard
                  title="Informations utilisees par Clara"
                  subtitle="Toutes les reponses pratiques que Clara peut donner aux patients."
                  icon={Sparkles}
                  action={<ActionButton icon={Wand2} disabled>Bientot dispo</ActionButton>}
                >
                  <div className="mb-3"><ComingSoonBadge /></div>
                  <fieldset disabled className="grid gap-4 opacity-70 md:grid-cols-2">
                    <TextArea label="Message d'accueil" value={assistant.welcome_message} onChange={(v) => { setAssistant((prev) => ({ ...prev, welcome_message: v })); markDirty(); }} />
                    <TextArea label="Documents a apporter" value={assistant.documents_to_bring} onChange={(v) => { setAssistant((prev) => ({ ...prev, documents_to_bring: v })); markDirty(); }} />
                    <TextArea label="Acces au cabinet" value={assistant.access_instructions} onChange={(v) => { setAssistant((prev) => ({ ...prev, access_instructions: v })); markDirty(); }} />
                    <TextArea label="Moyens de paiement" value={assistant.payment_methods} onChange={(v) => { setAssistant((prev) => ({ ...prev, payment_methods: v })); markDirty(); }} />
                  </fieldset>
                </SectionCard>

                <SectionCard title="Consignes sensibles" subtitle="Regles strictes pour eviter les mauvaises orientations." icon={ShieldCheck}>
                  <div className="rounded-[1.5rem] border border-[#071A33] bg-[#071A33] p-5 text-white">
                    <div className="mb-4 flex items-center gap-2">
                      <ShieldCheck className="h-5 w-5 text-[#F5C842]" />
                      <p className="font-black">Clara ne donne jamais d'avis medical.</p>
                    </div>
                    <fieldset disabled className="opacity-70">
                      <TextArea
                        label="Consigne principale"
                        value={assistant.sensitive_medical_instruction}
                        onChange={(v) => {
                          setAssistant((prev) => ({ ...prev, sensitive_medical_instruction: v }));
                          markDirty();
                        }}
                      />
                    </fieldset>
                  </div>
                </SectionCard>
              </>
            ) : null}

            {active === "abonnement" ? (
              <>
                <SectionCard
                  id="billing-summary"
                  title="Abonnement actuel"
                  subtitle="Suivez votre offre, votre consommation et vos prochaines factures."
                  icon={CreditCard}
                  action={<ActionButton variant="secondary" icon={FileText} disabled>Bientot dispo</ActionButton>}
                >
                  <div ref={billingRef} className="grid gap-4 lg:grid-cols-[1.15fr_.85fr]">
                    <div className="rounded-[1.75rem] border border-[#BFE9EC] bg-[#E8F7F7] p-5">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="text-xs font-black uppercase tracking-[0.2em] text-[#06747A]">Offre actuelle</p>
                          <h3 className="mt-2 text-4xl font-black tracking-tight text-[#071A33]">{planMeta.name}</h3>
                          <p className="mt-1 text-sm font-bold text-slate-600">
                            {billingSummary.monthly_price || planMeta.price}EUR / mois · {billingSummary.included_minutes || 0} minutes incluses
                          </p>
                        </div>
                        <StatusPill>{String(billingSummary.billing_status || "").toLowerCase() === "active" ? "Actif" : "A verifier"}</StatusPill>
                      </div>
                      <div className="mt-6">
                        <div className="mb-2 flex items-center justify-between text-sm font-bold text-slate-700">
                          <span>
                            {billingSummary.used_minutes_current_month || 0} / {billingSummary.included_minutes || 0} minutes utilisees
                          </span>
                          <span>{billingSummary.usage_percentage || 0}%</span>
                        </div>
                        <div className="h-3 overflow-hidden rounded-full bg-white">
                          <div className="h-full rounded-full bg-[#009CA4]" style={{ width: `${billingSummary.usage_percentage || 0}%` }} />
                        </div>
                        <p className="mt-3 text-sm font-medium text-slate-600">
                          Depassement estime: {billingSummary.estimated_overage_minutes || 0} min · {billingSummary.estimated_overage_cost || 0}EUR
                        </p>
                      </div>
                    </div>

                    <div className="rounded-[1.75rem] border border-slate-200 bg-white p-5">
                      <p className="text-base font-black text-[#071A33]">Moyen de paiement</p>
                      <p className="mt-2 text-sm font-semibold text-slate-600">
                        {billingSummary.payment_method_brand
                          ? `${String(billingSummary.payment_method_brand).toUpperCase()} ···· ${billingSummary.payment_method_last4 || "----"}`
                          : "Moyen de paiement non disponible"}
                      </p>
                      <p className="mt-1 text-sm text-slate-500">Prochaine facture : {billingSummary.next_invoice_date || "—"}</p>
                      <div className="mt-5 grid gap-2">
                        <ActionButton variant="secondary" icon={RefreshCw} onClick={() => showComingSoon("La gestion de carte")} disabled>
                          Bientot dispo
                        </ActionButton>
                        <ActionButton variant="dark" icon={ChevronRight} onClick={() => showComingSoon("Le changement d'offre")} disabled>
                          Bientot dispo
                        </ActionButton>
                      </div>
                    </div>
                  </div>
                </SectionCard>

                <SectionCard
                  title="Comparaison des offres"
                  subtitle="UWi peut recommander automatiquement l'offre la plus avantageuse selon l'usage reel."
                  icon={FileText}
                >
                  <div className="grid gap-3 md:grid-cols-3">
                    {(billingSummary.plans || []).map((plan) => (
                      <button
                        key={plan.plan_key}
                        type="button"
                        onClick={() => showComingSoon("Le changement d'offre")}
                        disabled
                        className={`rounded-[1.5rem] border p-4 text-left ${
                          plan.plan_key === planKey ? "border-[#009CA4] bg-[#E8F7F7]" : "border-slate-200 bg-white"
                        } opacity-70`}
                      >
                        <p className="text-lg font-black text-[#071A33]">{String(plan.plan_key || "").toUpperCase()}</p>
                        <p className="mt-2 text-sm font-bold text-slate-600">{plan.included_minutes_month} minutes incluses</p>
                        {plan.plan_key === planKey ? (
                          <p className="mt-3 text-xs font-black uppercase tracking-[0.14em] text-[#06747A]">Offre active</p>
                        ) : (
                          <p className="mt-3 text-xs font-black uppercase tracking-[0.14em] text-slate-500">Changer vers ce plan</p>
                        )}
                      </button>
                    ))}
                  </div>
                  {loadingInvoices ? <p className="mt-4 text-sm text-slate-500">Chargement des factures...</p> : null}
                  {invoices.length > 0 ? (
                    <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200">
                      {invoices.map((invoice) => (
                        <a
                          key={invoice.id}
                          href={invoice.invoice_pdf || "#"}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center justify-between border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-700 last:border-b-0 hover:bg-slate-50"
                        >
                          <span>{invoice.number || invoice.id}</span>
                          <span>{invoice.amount_due} {invoice.currency || "EUR"}</span>
                        </a>
                      ))}
                    </div>
                  ) : null}
                </SectionCard>
              </>
            ) : null}
          </div>

          <aside className="grid content-start gap-5">
            <div className="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#E8F7F7] text-[#06747A]">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div>
                  <p className="font-black text-[#071A33]">Clara est prete</p>
                  <p className="text-sm font-medium text-slate-500">Dernier test : aujourd'hui</p>
                </div>
              </div>
              <div className="mt-4 rounded-2xl bg-slate-50 p-4 text-sm font-medium leading-6 text-slate-600">
                “Le cabinet est ouvert aujourd'hui selon vos horaires. Clara peut orienter le patient avec vos regles actuelles.”
              </div>
              <button type="button" disabled className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-300 px-4 py-3 text-sm font-black text-slate-600">
                Bientot dispo <ChevronRight className="h-4 w-4" />
              </button>
            </div>

            <div className="rounded-[2rem] border border-amber-200 bg-amber-50 p-5">
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
                <div>
                  <p className="font-black text-amber-950">A completer</p>
                  <p className="mt-1 text-sm font-medium leading-6 text-amber-800">
                    {profileSummary.missing_items?.[0]?.label ||
                      "Il manque les consignes pour les nouveaux patients. Clara utilisera une reponse prudente tant que ce champ est vide."}
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-sm">
              <p className="font-black text-[#071A33]">Actions rapides</p>
              <div className="mt-4 grid gap-2">
                {[
                  ["Indiquer une absence", PauseCircle, goToAbsence],
                  ["Ajouter une consigne", Plus, () => showComingSoon("Les consignes Clara")],
                  ["Reconnecter l'agenda", RefreshCw, () => showComingSoon("La reconnexion agenda")],
                  ["Voir les factures", FileText, () => showComingSoon("Les factures")],
                ].map(([label, Icon, onClick]) => (
                  <button
                    key={label}
                    type="button"
                    onClick={onClick}
                    className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-700 hover:border-[#009CA4]/50 hover:bg-[#E8F7F7]"
                  >
                    <span className="flex items-center gap-2">
                      <Icon className="h-4 w-4 text-[#06747A]" /> {label}
                    </span>
                    <ChevronRight className="h-4 w-4 text-slate-400" />
                  </button>
                ))}
              </div>
            </div>
          </aside>
        </main>
      </div>

      <Modal title="Tester Clara" open={testClaraOpen} onClose={() => setTestClaraOpen(false)}>
        <div className="grid gap-3">
          <textarea
            value={testClaraMessage}
            onChange={(event) => setTestClaraMessage(event.target.value)}
            placeholder="Ex: Est-ce que le cabinet est ouvert samedi ?"
            className="min-h-[120px] w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm font-medium outline-none focus:border-[#009CA4]"
          />
          <div className="flex justify-end">
            <ActionButton icon={TestTube2} onClick={runClaraPreview}>
              Simuler
            </ActionButton>
          </div>
          {testClaraAnswer ? <div className="rounded-2xl bg-slate-50 p-4 text-sm font-medium text-slate-700">{testClaraAnswer}</div> : null}
        </div>
      </Modal>

      <Modal title="Tester une demande patient" open={testBookingOpen} onClose={() => setTestBookingOpen(false)}>
        <div className="grid gap-3">
          <textarea
            value={testBookingMessage}
            onChange={(event) => setTestBookingMessage(event.target.value)}
            placeholder="Ex: Je voudrais un rendez-vous pour un controle ECG la semaine prochaine."
            className="min-h-[120px] w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm font-medium outline-none focus:border-[#009CA4]"
          />
          <div className="flex justify-end">
            <ActionButton icon={TestTube2} onClick={runBookingPreview}>
              Simuler
            </ActionButton>
          </div>
          {testBookingResult ? (
            <div className="rounded-2xl bg-slate-50 p-4 text-sm font-medium text-slate-700">
              <p>Autorise: {testBookingResult.allowed ? "Oui" : "Non"}</p>
              <p>Motif detecte: {testBookingResult.detected_reason || "Aucun"}</p>
              <p>Duree: {testBookingResult.duration_minutes || 0} min</p>
              <p className="mt-2">{testBookingResult.simulated_answer || ""}</p>
            </div>
          ) : null}
        </div>
      </Modal>
    </div>
  );
}
