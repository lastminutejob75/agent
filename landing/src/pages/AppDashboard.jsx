import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { agendaSlotMotif, formatAgendaSlotHour, parseAgendaSlotStart } from "../lib/agendaSlotParse.js";
import { buildAgendaViewUrl } from "../lib/agendaAppointmentActions.js";
import { api } from "../lib/api.js";
import { computeUpcomingFillRate } from "../lib/agendaFillRate.js";
import HomeHeroSection from "../components/home/HomeHeroSection.jsx";
import { buildRequestItemsFromCallsAndHandoffs, summarizeRequestItems } from "../lib/requestUiStatus.js";
import HomeTabsActionsPanel from "../components/home/HomeTabsActionsPanel.jsx";
import HomeStatsStrip from "../components/home/HomeStatsStrip.jsx";
import NextAppointmentCard from "../components/home/NextAppointmentCard.jsx";
import TasksCard from "../components/home/TasksCard.jsx";
import AgendaTodayCard from "../components/home/AgendaTodayCard.jsx";
import UpcomingAppointmentsCard, { formatShortDate } from "../components/home/UpcomingAppointmentsCard.jsx";
import DarkSummaryCard from "../components/home/DarkSummaryCard.jsx";
import TeamNotesCard from "../components/home/TeamNotesCard.jsx";

const CLARA_PHOTO = "/images/clara-headset.png";

const C = {
  navy: "#071A33",
  navy2: "#063A4A",
  teal: "#009CA4",
  teal2: "#00B8B0",
  bg: "#F5F8FB",
  border: "#DDE7EF",
  muted: "#66758B",
  red: "#EF4444",
  orange: "#F97316",
  green: "#16A34A",
  blue: "#2563EB",
  purple: "#7C3AED",
};

const soft = {
  red: "#FEF2F2",
  orange: "#FFF7ED",
  green: "#ECFDF3",
  blue: "#EFF6FF",
  purple: "#F5F3FF",
  teal: "#E8FAFA",
};

const border = {
  red: "#FECACA",
  orange: "#FED7AA",
  green: "#BBF7D0",
  blue: "#BFDBFE",
  purple: "#DDD6FE",
  teal: "#A7F3F0",
};

function Icon({ name, size = 18, color = "currentColor" }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: color,
    strokeWidth: 2,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    style: { flexShrink: 0 },
  };
  const paths = {
    phone: <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.1 9.9a16 16 0 0 0 6 6l1.26-1.26a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z" />,
    calendar: <><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" /></>,
    message: <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
    gear: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9c.14.31.22.65.22 1h.38a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></>,
    plus: <path d="M12 5v14M5 12h14" />,
    chart: <path d="M18 20V10M12 20V4M6 20v-6" />,
    warn: <><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /><path d="M12 9v4M12 17h.01" /></>,
    check: <path d="M20 6 9 17l-5-5" />,
    edit: <><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" /></>,
    star: <path d="M12 2l2.7 6.7 7.3.6-5.5 4.7 1.7 7-6.2-3.7L5.8 21l1.7-7L2 9.3l7.3-.6z" />,
    doc: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6M16 13H8M16 17H8" /></>,
  };
  return <svg {...common}>{paths[name] || paths.calendar}</svg>;
}

function Pill({ tone = "teal", children, icon, onClick }) {
  const clickable = typeof onClick === "function";
  const sharedStyle = {
    ...S.pill,
    color: C[tone] || C.teal,
    background: soft[tone] || soft.teal,
    borderColor: border[tone] || border.teal,
    cursor: clickable ? "pointer" : "default",
  };
  if (clickable) {
    return (
      <button type="button" onClick={onClick} style={sharedStyle}>
        {icon ? <Icon name={icon} size={13} /> : null}
        {children}
      </button>
    );
  }
  return (
    <span style={sharedStyle}>
      {icon ? <Icon name={icon} size={13} /> : null}
      {children}
    </span>
  );
}

function Btn({ children, icon, variant = "outline", onClick, style }) {
  const base = variant === "dark"
    ? S.btnDark
    : variant === "teal"
      ? S.btnTeal
      : variant === "green"
        ? S.btnGreen
        : variant === "orange"
          ? S.btnOrange
          : S.btnOutline;
  return (
    <button type="button" onClick={onClick} style={{ ...base, ...style }}>
      {icon ? <Icon name={icon} size={16} /> : null}
      {children}
    </button>
  );
}

function ClaraPhoto({ size = 98 }) {
  const [ok, setOk] = useState(true);
  return (
    <div style={{ ...S.claraPhoto, width: size, height: size }}>
      {ok ? (
        <img src={CLARA_PHOTO} alt="Clara" onError={() => setOk(false)} style={S.claraImg} />
      ) : (
        <div style={S.claraFallback}>C</div>
      )}
    </div>
  );
}

function Card({ title, icon, action, children }) {
  return (
    <section style={S.card}>
      <div style={S.cardHead}>
        <h3 style={S.cardTitle}><Icon name={icon} size={17} />{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

function sameDay(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function firstDateLabel(d) {
  if (!(d instanceof Date) || Number.isNaN(d.getTime())) return { day: "—", monthYear: "Aucun RDV", dow: "" };
  return {
    day: String(d.getDate()),
    monthYear: d.toLocaleDateString("fr-FR", { month: "long", year: "numeric" }),
    dow: `${d.toLocaleDateString("fr-FR", { weekday: "short" }).replace(".", "").toUpperCase()}.`,
  };
}

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function callTimestamp(call) {
  const raw = call?.started_at || call?.last_event_at || call?.created_at || call?.createdAt;
  const dt = new Date(String(raw || ""));
  return Number.isNaN(dt.getTime()) ? null : dt;
}

function isCancellationCall(call) {
  const category = String(call?.reason_category || "").toLowerCase();
  const summary = String(call?.summary || "").toLowerCase();
  const result = String(call?.result || call?.status || "").toLowerCase();
  return category.includes("cancel")
    || /annul/.test(summary)
    || result.includes("cancel")
    || result === "cancelled";
}

function isRecoveredAgendaSlot(slot) {
  const text = `${slot?.patient || slot?.patient_name || ""} ${slot?.type || ""} ${slot?.motif || ""} ${slot?.slot_label || ""}`.toLowerCase();
  return /récup|recup|repris|sauvé|sauve/.test(text);
}

export default function AppDashboard() {
  const navigate = useNavigate();
  const { me } = useOutletContext() || {};
  const [tab, setTab] = useState("overview");
  const [isMobile, setIsMobile] = useState(false);
  const [toast, setToast] = useState("");
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [kpis, setKpis] = useState(null);
  const [agenda, setAgenda] = useState([]);
  const [handoffs, setHandoffs] = useState([]);
  const [callbacks, setCallbacks] = useState([]);
  const [calls, setCalls] = useState([]);
  const [freeSlotsByDate, setFreeSlotsByDate] = useState({});
  const [connections, setConnections] = useState({ vapi: null, calendar: null });

  const notify = (msg) => {
    setToast(msg);
    window.clearTimeout(notify.t);
    notify.t = window.setTimeout(() => setToast(""), 2200);
  };

  const loadDashboard = useCallback(async (cancelledRef, { silent = false } = {}) => {
    if (!silent) {
      setLoading(true);
      setStatsLoading(true);
    }

    api.tenantDashboardStatsFast()
      .then((data) => {
        if (cancelledRef?.cancelled) return;
        if (data?.today) setKpis({ today: data.today });
        setFreeSlotsByDate(data?.free_slots_by_date && typeof data.free_slots_by_date === "object" ? data.free_slots_by_date : {});
        setCalls(Array.isArray(data?.calls) ? data.calls : []);
        setStatsLoading(false);
        if (!silent) setLoading(false);
      })
      .catch(() => {
        if (cancelledRef?.cancelled) return;
        setStatsLoading(false);
        if (!silent) setLoading(false);
      });

    api.tenantGetAgenda("?upcoming_days=14&compact=1")
      .then((value) => {
        if (cancelledRef?.cancelled) return;
        setAgenda(Array.isArray(value?.slots) ? value.slots : []);
      })
      .catch(() => {
        if (cancelledRef?.cancelled) return;
        setAgenda([]);
      });

    Promise.allSettled([
      api.tenantGetHandoffs("?limit=30&days=30"),
      api.tenantGetCallbackRequests("?limit=30"),
      api.tenantVapiStatus(),
      api.tenantGetCalendarStatus(),
    ]).then(([handoffRes, callbackRes, vapiRes, calendarRes]) => {
      if (cancelledRef?.cancelled) return;
      if (handoffRes.status === "fulfilled") setHandoffs(Array.isArray(handoffRes.value?.items) ? handoffRes.value.items : []);
      if (callbackRes.status === "fulfilled") setCallbacks(Array.isArray(callbackRes.value?.items) ? callbackRes.value.items : []);
      setConnections({
        vapi: vapiRes.status === "fulfilled" ? vapiRes.value : null,
        calendar: calendarRes.status === "fulfilled" ? calendarRes.value : null,
      });
    });
  }, []);

  useEffect(() => {
    const cancelledRef = { cancelled: false };
    loadDashboard(cancelledRef);
    return () => { cancelledRef.cancelled = true; };
  }, [loadDashboard]);

  useEffect(() => {
    if (typeof document === "undefined") return undefined;
    const refresh = () => {
      if (document.visibilityState === "visible") loadDashboard({ cancelled: false }, { silent: true });
    };
    document.addEventListener("visibilitychange", refresh);
    return () => document.removeEventListener("visibilitychange", refresh);
  }, [loadDashboard]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const onResize = () => setIsMobile(window.innerWidth <= 760);
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const today = new Date();
  const bookedSlots = useMemo(() => agenda.filter((s) => Boolean(s?.patient || s?.patient_name)), [agenda]);
  const sortedBookedSlots = useMemo(() => bookedSlots
    .map((slot) => ({ slot, start: parseAgendaSlotStart(slot) }))
    .filter((x) => x.start)
    .sort((a, b) => a.start.getTime() - b.start.getTime()), [bookedSlots]);

  const todaySlots = useMemo(() => sortedBookedSlots.filter((x) => sameDay(x.start, today)), [sortedBookedSlots, today]);
  /** Pas de repli sur le 1er créneau chronologique : après filtrage passé par l’API, un échec ici éviterait d’afficher un RDV déjà terminé */
  const nextSlot = useMemo(
    () => sortedBookedSlots.find((x) => x.start.getTime() >= Date.now()) ?? null,
    [sortedBookedSlots],
  );

  const nextDate = nextSlot?.start || null;
  const hasNextAppointment = Boolean(nextSlot);
  const nextLabels = firstDateLabel(nextDate);
  const nextHour = nextDate ? formatAgendaSlotHour(nextDate) : "—";
  const nextReason = agendaSlotMotif(nextSlot?.slot || null);
  const nextSource = String(nextSlot?.slot?.source || "").toUpperCase() === "UWI" ? "Pris par Clara" : "Agenda cabinet";
  const nextPatient = String(nextSlot?.slot?.patient || nextSlot?.slot?.patient_name || "").trim();

  const openNextAgendaAction = (action) => {
    if (!nextSlot?.slot || !nextSlot?.start) {
      notify("Aucun rendez-vous à venir");
      return;
    }
    navigate(buildAgendaViewUrl({
      date: nextSlot.start.toISOString().slice(0, 10),
      slot: nextSlot.slot,
      action,
      view: "day",
    }));
  };

  const openAgendaSlot = (slot, startDate, action) => {
    if (!slot || !startDate) {
      notify("Rendez-vous introuvable");
      return;
    }
    navigate(buildAgendaViewUrl({
      date: startDate.toISOString().slice(0, 10),
      slot,
      action,
      view: "day",
    }));
  };

  const buildAgendaRow = (entry, includeDate = false) => {
    const { slot, start } = entry;
    const name = String(slot?.patient || slot?.patient_name || "Patient").trim();
    const reason = agendaSlotMotif(slot) || "Consultation";
    const status = String(slot?.status || "").toLowerCase() === "confirmed" ? "Confirmé" : "Prévu";
    const focus = slot?.appointment_id || slot?.event_id || name;
    return {
      key: `${start?.toISOString?.() || "na"}-${focus}`,
      time: formatAgendaSlotHour(start),
      name,
      reason,
      status,
      dateLabel: includeDate ? formatShortDate(start) : "",
      slot,
      start,
    };
  };

  const agendaForDay = useMemo(
    () => todaySlots.map((entry) => buildAgendaRow(entry, false)),
    [todaySlots],
  );

  const upcomingRows = useMemo(
    () => sortedBookedSlots
      .filter((x) => x.start.getTime() >= Date.now())
      .slice(0, 6)
      .map((entry) => buildAgendaRow(entry, !sameDay(entry.start, today))),
    [sortedBookedSlots, today],
  );

  const openHandoffs = useMemo(() => handoffs.filter((h) => {
    const s = String(h?.status || "").toLowerCase();
    return s !== "processed" && s !== "cancelled";
  }), [handoffs]);

  const requestSummary = useMemo(() => {
    const items = buildRequestItemsFromCallsAndHandoffs(calls, handoffs, callbacks);
    return summarizeRequestItems(items);
  }, [calls, handoffs, callbacks]);

  const taskRows = useMemo(() => openHandoffs.slice(0, 2).map((h, idx) => {
    const title = String(h?.summary || h?.reason || h?.label || `Demande ${idx + 1}`).slice(0, 64);
    const dt = new Date(String(h?.created_at || h?.createdAt || ""));
    const due = Number.isNaN(dt.getTime())
      ? "Échéance : à définir"
      : `Échéance : ${dt.toLocaleDateString("fr-FR")}`;
    const tone = String(h?.priority || "").toLowerCase().includes("urgent") ? "red" : "orange";
    const badge = tone === "red" ? "À faire" : "En attente";
    return [title || "Demande patient", due, tone, badge];
  }), [openHandoffs]);

  const kpiCurrent = kpis?.current || {};
  const rdvCreatedToday = Number.isFinite(Number(kpis?.today?.bookings))
    ? Number(kpis.today.bookings)
    : (() => {
      const day = (kpis?.days || []).find((d) => d?.date === todayISO());
      return Number.isFinite(Number(day?.bookings)) ? Number(day.bookings) : 0;
    })();
  /** Créneaux prévus dans l'agenda pour la journée civile (≠ prises de RDV confirmées aujourd'hui). */
  const rdvPlannedToday = todaySlots.length;
  const fillStats = useMemo(
    () => computeUpcomingFillRate({
      today,
      bookedEntries: sortedBookedSlots,
      freeSlotsByDate,
      horizonDays: 7,
    }),
    [today, sortedBookedSlots, freeSlotsByDate],
  );
  const { fillRate, totalBooked: fillBooked, totalCapacity: fillCapacity } = fillStats;
  const cancellationsToday = useMemo(
    () => calls.filter((call) => {
      if (!isCancellationCall(call)) return false;
      const dt = callTimestamp(call);
      return dt ? sameDay(dt, today) : false;
    }).length,
    [calls, today],
  );
  const recoveredCount = useMemo(
    () => agenda.filter(isRecoveredAgendaSlot).length,
    [agenda],
  );

  const vapiConnected = connections.vapi?.connected ?? Boolean(me?.assistant_live);
  const calendarConnected = connections.calendar?.connected === true;

  const agendaTodayHref = `/app/agenda?view=day&date=${encodeURIComponent(todayISO())}`;
  const bookingsTodayHref = `/app/agenda?view=week&date=${encodeURIComponent(todayISO())}&focus=prises-jour`;
  const agendaAnnulationsHref = `/app/appels?type=annulation&period=today`;
  const agendaCreneauxRecuperesHref = `/app/agenda?view=week&date=${encodeURIComponent(todayISO())}&focus=creneaux-recuperes`;
  const stats = useMemo(() => {
    const placeholder = (label, note = "Chargement…") => ["—", label, note, "teal", "plus", ""];
    if (statsLoading) {
      return [
        placeholder("Prises de RDV aujourd'hui"),
        placeholder("RDV d'aujourd'hui"),
        placeholder("Taux de remplissage"),
        placeholder("Annulations"),
        placeholder("Créneaux récupérés", "—"),
      ];
    }
    return [
    [
      String(rdvCreatedToday),
      "Prises de RDV aujourd'hui",
      rdvCreatedToday > 0 ? "confirmées pour l'avenir" : "aucune confirmation aujourd'hui",
      "teal",
      "plus",
      bookingsTodayHref,
    ],
    [
      String(rdvPlannedToday),
      "RDV d'aujourd'hui",
      rdvPlannedToday > 0 ? "prévus dans l'agenda" : "agenda vide",
      "blue",
      "calendar",
      agendaTodayHref,
    ],
    [
      `${fillRate}%`,
      "Taux de remplissage",
      fillCapacity > 0
        ? `${fillBooked}/${fillCapacity} créneaux réservés sur 7 jours`
        : "aucun créneau ouvert sur 7 jours",
      "green",
      "chart",
      `/app/agenda?view=week&date=${encodeURIComponent(todayISO())}`,
    ],
    [
      String(cancellationsToday),
      "Annulations",
      cancellationsToday > 0 ? "traitées par Clara aujourd'hui" : "aucune aujourd'hui",
      "orange",
      "warn",
      agendaAnnulationsHref,
    ],
    [
      String(recoveredCount),
      "Créneaux récupérés",
      recoveredCount > 0 ? "créneaux sauvés par Clara" : "—",
      "purple",
      "check",
      agendaCreneauxRecuperesHref,
    ],
  ];
  }, [
    statsLoading,
    rdvCreatedToday,
    rdvPlannedToday,
    fillRate,
    fillBooked,
    fillCapacity,
    cancellationsToday,
    recoveredCount,
    bookingsTodayHref,
    agendaTodayHref,
    agendaAnnulationsHref,
    agendaCreneauxRecuperesHref,
  ]);

  const priorityItems = [
    {
      key: "handoffs",
      title: "Demandes prioritaires",
      value: openHandoffs.length,
      hint: openHandoffs.length > 0 ? "A traiter maintenant" : "Aucune urgence en attente",
      tone: openHandoffs.length > 0 ? "orange" : "green",
      action: () => navigate("/app/demandes?status=%C3%80%20traiter&priority=Urgence"),
    },
    {
      key: "next",
      title: "Prochain RDV",
      value: nextHour,
      hint: hasNextAppointment ? `${nextPatient || "Patient"} · ${nextReason || "Consultation"}` : "Aucun rendez-vous planifié",
      tone: "teal",
      action: () => navigate("/app/agenda"),
    },
    {
      key: "today",
      title: "RDV d'aujourd'hui",
      value: String(rdvPlannedToday),
      hint: "Prévus dans l'agenda (pas les prises du jour)",
      tone: "blue",
      action: () => navigate(`/app/agenda?view=day&date=${encodeURIComponent(todayISO())}`),
    },
  ];

  const nextAppointmentCard = (
    <NextAppointmentCard
      hasAppointment={hasNextAppointment}
      nextLabels={nextLabels}
      nextHour={nextHour}
      nextPatient={nextPatient}
      nextReason={nextReason}
      nextSource={nextSource}
      onMove={() => openNextAgendaAction("reschedule")}
      onCancel={() => openNextAgendaAction("cancel")}
      onOpenAgenda={() => navigate("/app/agenda")}
      CardComponent={Card}
      PillComponent={Pill}
      BtnComponent={Btn}
      styles={S}
    />
  );

  return (
    <div className="uwi-dashboard-page" style={S.page}>
      {!loading && (connections.vapi || connections.calendar) ? (
        <div style={S.connectionStrip}>
          <span style={{ ...S.connectionPill, ...(vapiConnected ? S.connectionOk : S.connectionWarn) }}>
            Clara {vapiConnected ? "connectée" : "non configurée"}
            {connections.vapi?.voice_number ? ` · ${connections.vapi.voice_number}` : ""}
          </span>
          <span style={{ ...S.connectionPill, ...(calendarConnected ? S.connectionOk : S.connectionMuted) }}>
            Agenda {calendarConnected ? "connecté" : "non lié au cabinet"}
          </span>
          <span style={{ ...S.connectionPill, ...S.connectionMuted }}>
            Données en direct · {calls.length} appel{calls.length > 1 ? "s" : ""} (7 j)
          </span>
        </div>
      ) : null}

      <HomeHeroSection
        handledRequestsCount={requestSummary.handled}
        rdvCreatedToday={rdvCreatedToday}
        inProgressRequestsCount={requestSummary.inProgress}
        assistantName={me?.assistant_name}
        assistantLive={Boolean(me?.assistant_live)}
        voiceNumber={me?.voice_number || me?.phone_number}
        contactEmail={me?.contact_email}
        onOpenHandledRequests={() => navigate("/app/demandes?status=Trait%C3%A9es")}
        onOpenRdvToday={() => navigate(bookingsTodayHref)}
        onOpenReminders={() => navigate("/app/demandes?status=En%20cours")}
        ClaraPhotoComponent={ClaraPhoto}
        PillComponent={Pill}
        IconRenderer={(name, size = 18) => <Icon name={name} size={size} />}
        styles={S}
      />

      <HomeTabsActionsPanel
        tab={tab}
        setTab={setTab}
        onPriority={() => navigate("/app/demandes?status=%C3%80%20traiter&priority=Urgence")}
        onDayAgenda={() => navigate(`/app/agenda?view=day&date=${encodeURIComponent(todayISO())}`)}
        onMessages={() => navigate("/app/demandes?status=Toutes&type=Question")}
        onClaraSettings={() => navigate("/app/clara")}
        styles={S}
        BtnComponent={Btn}
      />

      {isMobile ? (
        <section style={S.mobilePriorityCard}>
          <p style={S.mobilePriorityTitle}>Priorite du moment</p>
          <div style={S.mobilePriorityGrid}>
            {priorityItems.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={item.action}
                style={{
                  ...S.mobilePriorityItem,
                  borderColor: border[item.tone] || C.border,
                  background: soft[item.tone] || "#fff",
                }}
              >
                <p style={S.mobilePriorityValue}>{item.value}</p>
                <p style={S.mobilePriorityLabel}>{item.title}</p>
                <p style={S.mobilePriorityHint}>{item.hint}</p>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      <HomeStatsStrip
        stats={stats}
        loading={statsLoading}
        styles={S}
        soft={soft}
        colors={C}
        IconRenderer={(name, size = 18) => <Icon name={name} size={size} />}
      />

      {isMobile ? <div style={S.mobileNextRdv}>{nextAppointmentCard}</div> : null}

      <div className="uwi-dashboard-grid" style={S.grid}>
        {isMobile ? (
          <>
            <div style={S.colLeft}>
              <TasksCard
                taskRows={taskRows}
                onOpenAll={() => navigate("/app/demandes")}
                onTaskClick={notify}
                CardComponent={Card}
                PillComponent={Pill}
                IconRenderer={(name, size = 18) => <Icon name={name} size={size} />}
                styles={S}
                soft={soft}
                colors={C}
              />

              <AgendaTodayCard
                agendaForDay={agendaForDay}
                onOpenAgenda={() => navigate(`/app/agenda?view=day&date=${encodeURIComponent(todayISO())}`)}
                onRowClick={(row) => openAgendaSlot(row.slot, row.start)}
                CardComponent={Card}
                PillComponent={Pill}
                styles={S}
              />

              <UpcomingAppointmentsCard
                rows={upcomingRows}
                onOpenAgenda={() => navigate("/app/agenda?view=week")}
                onRowClick={(row) => openAgendaSlot(row.slot, row.start)}
                CardComponent={Card}
                PillComponent={Pill}
                styles={S}
              />

            </div>

            <div style={S.colRight}>
              <DarkSummaryCard
                handledTodayCount={requestSummary.handledToday}
                urgentCount={requestSummary.urgentOpen}
                avgResponseMinutes={requestSummary.avgResponseMinutes}
                cancelledCount={cancellationsToday}
                recoveredCount={recoveredCount}
                loading={loading}
                IconRenderer={(name, size = 18) => <Icon name={name} size={size} />}
                styles={S}
              />

              <TeamNotesCard
                onSave={() => notify("Note enregistrée")}
                IconRenderer={(name, size = 18) => <Icon name={name} size={size} />}
                BtnComponent={Btn}
                styles={S}
                colors={C}
              />
            </div>
          </>
        ) : (
          <>
            <div style={S.colLeft}>
              {nextAppointmentCard}

              <DarkSummaryCard
                handledTodayCount={requestSummary.handledToday}
                urgentCount={requestSummary.urgentOpen}
                avgResponseMinutes={requestSummary.avgResponseMinutes}
                cancelledCount={cancellationsToday}
                recoveredCount={recoveredCount}
                loading={loading}
                IconRenderer={(name, size = 18) => <Icon name={name} size={size} />}
                styles={S}
              />

              <TeamNotesCard
                onSave={() => notify("Note enregistrée")}
                IconRenderer={(name, size = 18) => <Icon name={name} size={size} />}
                BtnComponent={Btn}
                styles={S}
                colors={C}
              />
            </div>

            <div style={S.colRight}>
              <TasksCard
                taskRows={taskRows}
                onOpenAll={() => navigate("/app/demandes")}
                onTaskClick={notify}
                CardComponent={Card}
                PillComponent={Pill}
                IconRenderer={(name, size = 18) => <Icon name={name} size={size} />}
                styles={S}
                soft={soft}
                colors={C}
              />

              <AgendaTodayCard
                agendaForDay={agendaForDay}
                onOpenAgenda={() => navigate(`/app/agenda?view=day&date=${encodeURIComponent(todayISO())}`)}
                onRowClick={(row) => openAgendaSlot(row.slot, row.start)}
                CardComponent={Card}
                PillComponent={Pill}
                styles={S}
              />

              <UpcomingAppointmentsCard
                rows={upcomingRows}
                onOpenAgenda={() => navigate("/app/agenda?view=week")}
                onRowClick={(row) => openAgendaSlot(row.slot, row.start)}
                CardComponent={Card}
                PillComponent={Pill}
                styles={S}
              />
            </div>
          </>
        )}
      </div>

      {toast ? <div style={S.toast}>✓ {toast}</div> : null}
      <style>{CSS}</style>
    </div>
  );
}

const S = {
  page: { maxWidth: 1280, margin: "0 auto", padding: "18px 24px 30px", color: C.navy },
  connectionStrip: { display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12 },
  connectionPill: { display: "inline-flex", alignItems: "center", borderRadius: 999, padding: "6px 12px", fontSize: 12, fontWeight: 700, border: "1px solid" },
  connectionOk: { color: C.green, background: soft.green, borderColor: border.green },
  connectionWarn: { color: C.orange, background: soft.orange, borderColor: border.orange },
  connectionMuted: { color: C.muted, background: "#fff", borderColor: C.border },
  hero: { background: "#fff", border: `1px solid ${C.border}`, borderRadius: 24, padding: 24, display: "flex", justifyContent: "space-between", gap: 18, boxShadow: "0 18px 44px rgba(7,26,51,.07)", marginBottom: 14 },
  heroLeft: { display: "flex", alignItems: "center", gap: 20 },
  claraPhoto: { borderRadius: 999, border: `3px solid ${C.teal}`, overflow: "hidden", boxShadow: "0 14px 30px rgba(0,156,164,.18)" },
  claraImg: { width: "100%", height: "100%", objectFit: "cover", objectPosition: "center top" },
  claraFallback: { width: "100%", height: "100%", background: "linear-gradient(135deg,#2EE6D0,#009CA4,#071A33)", color: "#fff", display: "grid", placeItems: "center", fontSize: 34, fontWeight: 800 },
  heroTitleRow: { display: "flex", alignItems: "center", gap: 12, marginBottom: 5 },
  heroTitle: { margin: 0, fontSize: 28, fontWeight: 800, letterSpacing: "-.03em" },
  meta: { margin: 0, display: "flex", alignItems: "center", gap: 7, color: C.muted, fontWeight: 600, fontSize: 13 },
  pills: { display: "flex", gap: 9, flexWrap: "wrap", marginTop: 10 },
  heroButtons: { display: "flex", flexDirection: "column", gap: 10, alignItems: "flex-end" },
  heroBtnCompact: { height: 40, minHeight: 40, borderRadius: 11, fontSize: 15, padding: "0 16px", lineHeight: 1.1 },
  panel: { background: "#fff", border: `1px solid ${C.border}`, borderRadius: 20, boxShadow: "0 10px 28px rgba(7,26,51,.055)", overflow: "hidden", marginBottom: 14 },
  tabs: { display: "flex", height: 52, borderBottom: `1px solid ${C.border}` },
  tab: { padding: "0 30px", border: 0, background: "transparent", fontWeight: 800, cursor: "pointer", color: C.navy, fontFamily: "inherit" },
  tabActive: { color: C.teal, borderBottom: `3px solid ${C.teal}` },
  quickActions: { display: "grid", gridTemplateColumns: "repeat(3, minmax(0,1fr))", gap: 14, padding: 14 },
  panelFooter: { display: "flex", justifyContent: "flex-end", padding: "0 14px 12px" },
  claraSettingsLink: { display: "inline-flex", alignItems: "center", gap: 6, border: 0, background: "transparent", color: C.muted, fontWeight: 700, fontSize: 13, cursor: "pointer", fontFamily: "inherit", padding: "6px 4px" },
  claraSettingsIcon: { fontSize: 13, lineHeight: 1 },
  statsStrip: { display: "grid", gridTemplateColumns: "190px 1fr", gap: 14, background: "#fff", border: `1px solid ${C.border}`, borderRadius: 20, padding: 14, boxShadow: "0 12px 32px rgba(7,26,51,.06)", marginBottom: 16 },
  statsIntro: { borderRadius: 16, background: "linear-gradient(135deg,#071A33,#063A4A)", color: "#fff", padding: 16, display: "flex", flexDirection: "column", justifyContent: "center", fontWeight: 700 },
  statsGrid: { display: "grid", gridTemplateColumns: "repeat(5, minmax(0, 1fr))", gap: 10 },
  statBox: { border: `1px solid ${C.border}`, background: "#fff", borderRadius: 15, padding: 12, textAlign: "left", display: "grid", gap: 3, cursor: "pointer", fontFamily: "inherit" },
  grid: { display: "grid", gridTemplateColumns: "1.15fr .85fr", gap: 18 },
  colLeft: { display: "flex", flexDirection: "column", gap: 16 },
  colRight: { display: "flex", flexDirection: "column", gap: 16 },
  card: { background: "#fff", border: `1px solid ${C.border}`, borderRadius: 20, padding: 22, boxShadow: "0 12px 32px rgba(7,26,51,.06)" },
  cardHead: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  cardTitle: { margin: 0, display: "inline-flex", alignItems: "center", gap: 8, fontSize: 20, fontWeight: 800 },
  linkBtn: { border: 0, background: "transparent", color: C.teal, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" },
  rdv: { display: "flex", gap: 22 },
  dateBlock: { width: 108, borderRadius: 16, background: "linear-gradient(160deg,#00A9AC,#06455C)", color: "#fff", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", boxShadow: "0 10px 22px rgba(0,156,164,.24)" },
  rdvTop: { display: "flex", alignItems: "center", gap: 12, marginBottom: 14, flexWrap: "wrap" },
  rdvDetails: { display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 12, marginBottom: 14 },
  rowBtns: { display: "flex", gap: 9, flexWrap: "wrap" },
  darkCard: { borderRadius: 22, background: "linear-gradient(135deg,#071A33 0%,#063A4A 52%,#009CA4 135%)", color: "#fff", padding: 26, boxShadow: "0 20px 44px rgba(7,26,51,.24)" },
  darkTitle: { margin: "0 0 8px", display: "inline-flex", alignItems: "center", gap: 8, fontSize: 21, fontWeight: 800 },
  darkText: { margin: 0, lineHeight: 1.5, color: "rgba(255,255,255,.92)" },
  darkFooter: { display: "block", marginTop: 12, color: "rgba(255,255,255,.75)" },
  task: { width: "100%", display: "grid", gridTemplateColumns: "42px 1fr auto", alignItems: "center", gap: 12, border: `1px solid ${C.border}`, borderRadius: 14, background: "#fff", padding: 11, marginTop: 10, textAlign: "left", cursor: "pointer", fontFamily: "inherit" },
  agendaRow: { width: "100%", display: "grid", gridTemplateColumns: "64px 1fr auto", alignItems: "center", gap: 12, border: `1px solid ${C.border}`, borderRadius: 14, background: "#fff", padding: 11, marginTop: 9, textAlign: "left", cursor: "pointer", fontFamily: "inherit" },
  input: { width: "100%", height: 50, borderRadius: 12, border: `1px solid ${C.border}`, padding: "0 14px", boxSizing: "border-box", margin: "10px 0", fontFamily: "inherit" },
  toast: { position: "fixed", left: "50%", bottom: 24, transform: "translateX(-50%)", background: C.navy, color: "#fff", padding: "13px 24px", borderRadius: 999, fontWeight: 800, boxShadow: "0 18px 44px rgba(7,26,51,.28)", zIndex: 40 },
  pill: { display: "inline-flex", alignItems: "center", gap: 6, border: "1px solid", borderRadius: 9, padding: "6px 10px", fontSize: 12, fontWeight: 800, whiteSpace: "nowrap" },
  btnDark: { height: 44, display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8, border: 0, borderRadius: 12, padding: "0 17px", background: "linear-gradient(135deg,#071A33,#063A4A)", color: "#fff", fontWeight: 800, cursor: "pointer", fontFamily: "inherit" },
  btnTeal: { height: 42, display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8, border: 0, borderRadius: 12, padding: "0 17px", background: "linear-gradient(135deg,#009CA4,#00B8B0)", color: "#fff", fontWeight: 800, cursor: "pointer", fontFamily: "inherit" },
  btnOutline: { height: 42, display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8, border: `1.5px solid ${C.border}`, borderRadius: 12, padding: "0 17px", background: "#fff", color: C.navy, fontWeight: 800, cursor: "pointer", fontFamily: "inherit" },
  btnOrange: { height: 42, display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8, border: "1.5px solid #FED7AA", borderRadius: 12, padding: "0 17px", background: "#fff", color: C.orange, fontWeight: 800, cursor: "pointer", fontFamily: "inherit" },
  btnGreen: { height: 42, display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8, border: "1.5px solid #BBF7D0", borderRadius: 12, padding: "0 17px", background: "#fff", color: C.green, fontWeight: 800, cursor: "pointer", fontFamily: "inherit" },
  mobilePriorityCard: { background: "#fff", border: `1px solid ${C.border}`, borderRadius: 18, padding: 12, boxShadow: "0 10px 24px rgba(7,26,51,.05)", marginBottom: 12 },
  mobileNextRdv: { marginBottom: 12 },
  mobilePriorityTitle: { margin: "0 0 10px", fontSize: 14, fontWeight: 800, color: C.navy },
  mobilePriorityGrid: { display: "grid", gridTemplateColumns: "1fr", gap: 8 },
  mobilePriorityItem: { width: "100%", border: `1px solid ${C.border}`, borderRadius: 14, padding: "10px 12px", background: "#fff", textAlign: "left", cursor: "pointer", fontFamily: "inherit" },
  mobilePriorityValue: { margin: 0, fontSize: 20, fontWeight: 800, color: C.navy },
  mobilePriorityLabel: { margin: "2px 0 0", fontSize: 13, fontWeight: 800, color: C.navy },
  mobilePriorityHint: { margin: "2px 0 0", fontSize: 12, color: C.muted, lineHeight: 1.35 },
};

const CSS = `
  .uwi-main p { line-height: 1.42; }
  .uwi-main em { width: 32px; height: 32px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; }
  .uwi-main p { margin: 0; }
  .uwi-dashboard-agenda-row-text {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    min-width: 0;
    text-align: left;
  }
  .uwi-dashboard-agenda-row-text strong {
    font-size: 14px;
    font-weight: 800;
    color: ${C.navy};
  }
  .uwi-dashboard-agenda-row-text small {
    font-size: 12px;
    font-weight: 600;
    color: ${C.muted};
    line-height: 1.35;
  }
  .uwi-dashboard-rdv-detail {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
    margin: 0;
  }
  .uwi-dashboard-rdv-detail span {
    font-size: 12px;
    font-weight: 700;
    color: ${C.muted};
    line-height: 1.2;
  }
  .uwi-dashboard-rdv-detail b {
    font-size: 14px;
    font-weight: 800;
    color: ${C.navy};
    line-height: 1.3;
  }
  @media (max-width: 1180px) {
    .uwi-dashboard-grid { grid-template-columns: 1fr !important; }
    .uwi-dashboard-stats-grid { grid-template-columns: repeat(3, minmax(0, 1fr)) !important; }
    .uwi-dashboard-rdv-details { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
  }
  @media (max-width: 1000px) {
    .uwi-dashboard-quick-actions { grid-template-columns: 1fr !important; }
    .uwi-dashboard-stats-strip { grid-template-columns: 1fr !important; }
    .uwi-dashboard-stats-grid { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
  }
  @media (max-width: 760px) {
    .uwi-dashboard-page { padding: 14px 12px 20px !important; }
    .uwi-dashboard-hero { flex-direction: column !important; align-items: flex-start !important; padding: 16px !important; }
    .uwi-dashboard-hero-left { flex-direction: column !important; align-items: flex-start !important; gap: 14px !important; }
    .uwi-dashboard-hero-buttons { align-items: stretch !important; width: 100% !important; }
    .uwi-dashboard-stats-grid { grid-template-columns: 1fr !important; }
    .uwi-dashboard-rdv { flex-direction: column !important; gap: 14px !important; }
    .uwi-dashboard-rdv-details { grid-template-columns: 1fr !important; }
    .uwi-dashboard-tabs { overflow-x: auto !important; }
    .uwi-dashboard-tabs button { flex: 0 0 auto !important; padding: 0 18px !important; }
  }
`;
