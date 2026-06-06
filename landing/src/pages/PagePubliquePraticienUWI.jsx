import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { getApiBaseUrl } from "../lib/api";

const CLARA_IMAGE = "/clara-avatar.png?v=1";

const defaultPractitioner = {
  slug: "cabinet-dupond-demo",
  name: "Cabinet Dupond",
  initials: "CD",
  specialty: "Medecine generale",
  city: "Lille",
  verified: true,
  rating: 4.9,
  reviewCount: 142,
  reviewsVerified: true,
  photoUrl: "",
  address: { street: "12 rue Gambetta", postalCode: "59000", city: "Lille", country: "FR" },
  access: "Metro Republique Beaux-Arts",
  parking: "Parking Gambetta",
  phone: "03 20 12 34 56",
  phoneTel: "+33320123456",
  languages: ["Francais", "Anglais"],
  fee: "Secteur 1 - Tarifs conventionnes",
  carteVitale: true,
  pmr: true,
  voiceEnabled: false,
  vapiAssistantId: "",
  newPatients: "Selon disponibilite",
  documents: "Carte Vitale, piece d'identite, ordonnances et examens recents.",
  whatsappEnabled: true,
  whatsappUrl: "https://wa.me/33000000000?text=Bonjour%2C%20je%20souhaite%20prendre%20rendez-vous",
  canonicalUrl: "https://www.uwiapp.com/p/cabinet-dupond-demo",
};

const DEMO_SLOT_SPECS = [
  { id: "s1", businessOffset: 0, time: "14:00", motifs: ["Consultation", "Suivi", "Premiere consultation", "Renouvellement"] },
  { id: "s2", businessOffset: 0, time: "16:30", motifs: ["Consultation", "Suivi"] },
  { id: "s3", businessOffset: 1, time: "09:15", motifs: ["Consultation", "Suivi", "Premiere consultation"] },
  { id: "s4", businessOffset: 1, time: "11:00", motifs: ["Consultation", "Suivi"] },
  { id: "s5", businessOffset: 2, time: "10:00", motifs: ["Consultation", "Suivi", "Renouvellement"] },
  { id: "s6", businessOffset: 2, time: "15:45", motifs: ["Consultation", "Suivi"] },
];

const FR_WEEKDAYS_SHORT = ["Lun.", "Mar.", "Mer.", "Jeu.", "Ven.", "Sam.", "Dim."];
const FR_WEEKDAYS_LONG = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"];

function jsWeekdayIndex(date) {
  const day = date.getDay();
  return day === 0 ? 6 : day - 1;
}

function businessDayOnOrAfter(baseDate, businessOffset) {
  if (businessOffset <= 0) return new Date(baseDate);
  const cursor = new Date(baseDate);
  let added = 0;
  while (added < businessOffset) {
    cursor.setDate(cursor.getDate() + 1);
    if (cursor.getDay() !== 0 && cursor.getDay() !== 6) added += 1;
  }
  return cursor;
}

function publicSlotDayLabels(targetDate, refDate) {
  const ref = new Date(refDate);
  ref.setHours(0, 0, 0, 0);
  const target = new Date(targetDate);
  target.setHours(0, 0, 0, 0);
  const diffDays = Math.round((target.getTime() - ref.getTime()) / 86400000);
  if (diffDays === 0) return { day: "Auj.", long: "aujourd'hui" };
  if (diffDays === 1) return { day: "Dem.", long: "demain" };
  if (diffDays > 0 && diffDays < 7) {
    const idx = jsWeekdayIndex(target);
    return { day: FR_WEEKDAYS_SHORT[idx], long: FR_WEEKDAYS_LONG[idx] };
  }
  const formatted = `${String(target.getDate()).padStart(2, "0")}/${String(target.getMonth() + 1).padStart(2, "0")}`;
  return { day: formatted, long: formatted };
}

function buildDefaultDemoSlots(refDate = new Date()) {
  return DEMO_SLOT_SPECS.map(({ id, businessOffset, time, motifs }) => {
    const target = businessDayOnOrAfter(refDate, businessOffset);
    const date = formatLocalDate(target);
    const { day, long } = publicSlotDayLabels(target, refDate);
    return {
      id,
      label: `${long} a ${time}`,
      day,
      time,
      date,
      startIso: `${date}T${time}:00`,
      motifs,
    };
  });
}

const defaultSlots = buildDefaultDemoSlots();

const defaultOpeningHours = [
  { day: "Lundi", opens: "08:30", closes: "18:30", schemaDay: "Monday" },
  { day: "Mardi", opens: "08:30", closes: "18:30", schemaDay: "Tuesday" },
  { day: "Mercredi", opens: "08:30", closes: "18:30", schemaDay: "Wednesday" },
  { day: "Jeudi", opens: "08:30", closes: "18:30", schemaDay: "Thursday" },
  { day: "Vendredi", opens: "08:30", closes: "17:30", schemaDay: "Friday" },
  { day: "Samedi", opens: null, closes: null, schemaDay: "Saturday" },
  { day: "Dimanche", opens: null, closes: null, schemaDay: "Sunday" },
];

const defaultSearchData = [
  { id: "cabinet-dupond-demo", name: "Cabinet Dupond", specialty: "Medecine generale", city: "Lille", availability: "Disponible aujourd'hui", acceptsNewPatients: true, url: "/p/cabinet-dupond-demo" },
  { id: "karim-benali", name: "Dr Karim Benali", specialty: "Medecin generaliste", city: "Tourcoing", availability: "Demain matin", acceptsNewPatients: true, url: "/p/dr-karim-benali" },
  { id: "sophie-martin", name: "Dr Sophie Martin", specialty: "Dermatologue", city: "Lille", availability: "Cette semaine", acceptsNewPatients: false, url: "/p/dr-sophie-martin" },
  { id: "amina-haddad", name: "Dr Amina Haddad", specialty: "Pediatre", city: "Roubaix", availability: "Sous 48h", acceptsNewPatients: true, url: "/p/dr-amina-haddad" },
];

const inputExamples = [
  "Ex : Je souhaite un rendez-vous mardi matin",
  "Ex : Je voudrais modifier mon rendez-vous",
  "Ex : Acceptez-vous les nouveaux patients ?",
  "Ex : Quels documents dois-je apporter ?",
];

const GREETING_TOKENS = new Set([
  "bjr", "bjour", "slt", "bsr", "bonjour", "salut", "bonsoir",
  "hello", "hi", "hey", "coucou", "cc", "yo",
]);
const GREETING_ONLY = /^(bjr|bjour|slt|bsr|bonjour|salut|bonsoir|hello|hi|hey|coucou|cc|yo|bonne journ[ée]e|bonne soir[ée]e)[\s!.,?]*$/iu;

function isGreetingOnly(text) {
  const raw = String(text || "").trim();
  if (!raw) return false;
  if (GREETING_ONLY.test(raw)) return true;
  const n = norm(raw).replace(/[^\w\s]/g, "").trim();
  if (!n) return false;
  if (GREETING_ONLY.test(n)) return true;
  if (n === "bonne journee" || n === "bonne soiree") return true;
  const parts = n.split(/\s+/);
  return parts.length === 1 && GREETING_TOKENS.has(parts[0]);
}
const INSTANT_GREETING_REPLY = "Bonjour ! Comment puis-je vous aider ?";
const INSTANT_SLOTS_LOOKUP = "Je consulte les créneaux disponibles, un instant…";
const INSTANT_SLOTS_DATE_LOOKUP = "Je cherche les créneaux à la date demandée, un instant…";
const INSTANT_MORE_SLOTS_LOOKUP = "Je cherche d'autres créneaux disponibles, un instant…";
const CHAT_SSE_TIMEOUT_FALLBACK =
  "La recherche de créneaux prend plus de temps que prévu. Réessayez dans un instant ou précisez un jour (ex. mardi matin).";
const MORE_SLOTS_MSG = "Je souhaite voir d'autres créneaux.";
const BOOKING_START = /\b(je\s+voudrais?|je\s+veux|je\s+souhaite|je\s+v\s+(?:in|un)\s+rdv|jv\s+(?:un\s+)?rdv|prendre\s+(?:un\s+)?rdv|un\s+rdv|rendez[- ]?vous|c\s+est\s+pour|c\s+pour)\b/iu;
const CANCEL_INTENT = /\b(annuler|annulation|supprimer)\b.*\b(rdv|rendez[- ]?vous)\b|\b(rdv|rendez[- ]?vous)\b.*\b(annuler|annulation)\b/iu;
const RESCHEDULE_INTENT = /\b(modifier|decaler|deplacer|changer|reporter)\b.*\b(rdv|rendez[- ]?vous)\b|\b(rdv|rendez[- ]?vous)\b.*\b(modifier|decaler|deplacer|changer|reporter)\b/iu;
const CALLBACK_INTENT = /\b(etre\s+rappele|demande\s+de\s+rappel|rappelez[- ]?moi|me\s+rappele)\b/iu;
const MORE_SLOTS_REQUEST = /\b(voir\s+d['\u2019]?autres?\s+cr[eé]neaux|voir\s+plus\s+de\s+cr[eé]neaux|autres?\s+cr[eé]neaux|plus\s+de\s+cr[eé]neaux|aucun\s+ne\s+convient|autre\s+horaire)\b/iu;
const CHAT_REPLY_TIMEOUT_MS = 45000;
/** Délai avant d'afficher les créneaux déjà chargés dans la barre (sans attendre le moteur). */
const CHAT_SLOTS_BAR_INSTANT_MS = 280;
/** Repli barre si le SSE tarde encore (créneaux agenda pas prêts au 1er essai). */
const CHAT_SLOTS_EARLY_FALLBACK_MS = 1800;
const CHAT_UNCLEAR_FALLBACK =
  "Je peux vous aider à prendre un rendez-vous, répondre à une question, annuler ou modifier un rendez-vous. Que souhaitez-vous ?";
const CHAT_PROCESSING_REPLY = "Un instant, je traite votre demande…";
const CHAT_PROCESSING_PLACEHOLDERS = new Set([
  INSTANT_SLOTS_LOOKUP,
  INSTANT_SLOTS_DATE_LOOKUP,
  INSTANT_MORE_SLOTS_LOOKUP,
  CHAT_PROCESSING_REPLY,
]);
const BOOKING_DATE_HINT =
  /\b(\d{1,2})\s+(janv|f[eé]vr|mars|avr|mai|juin|juill|ao[uû]t|sept|oct|nov|d[eé]c)|\b(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[eé]cembre)\b|\b(\d{1,2})[/\-.](\d{1,2})\b|\b(demain|apr[eè]s[- ]?demain)\b/iu;
const LOOKS_LIKE_NAME = /^(?:(?:M\.|Mme|Mlle)\s+)?[A-ZÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ' -]{1,58}$/u;
const PLAUSIBLE_PATIENT_NAME = /^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ' -]{2,58}$/u;

const safeArray = (value) => (Array.isArray(value) ? value : []);

const SLOTS_SESSION_PREFIX = "uwi-public-slots:";
const SLOTS_SESSION_TTL_MS = 10 * 60 * 1000;

function readSessionSlots(slug) {
  if (typeof window === "undefined" || !slug) return null;
  try {
    const raw = sessionStorage.getItem(`${SLOTS_SESSION_PREFIX}${slug}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.ts || Date.now() - parsed.ts > SLOTS_SESSION_TTL_MS) return null;
    if (!safeArray(parsed.slots).length) return null;
    return parsed;
  } catch {
    return null;
  }
}

function writeSessionSlots(slug, slotData) {
  if (typeof window === "undefined" || !slug) return;
  try {
    sessionStorage.setItem(
      `${SLOTS_SESSION_PREFIX}${slug}`,
      JSON.stringify({
        ts: Date.now(),
        slots: safeArray(slotData?.slots),
        source: slotData?.source || null,
        calendar: slotData?.calendar || null,
        cached: Boolean(slotData?.cached),
      }),
    );
  } catch {
    /* quota / private mode */
  }
}

function formatLocalDate(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function nextWeekdayFrom(baseDate, weekdayIndex) {
  const next = new Date(baseDate);
  const daysAhead = (weekdayIndex - next.getDay() + 7) % 7 || 7;
  next.setDate(next.getDate() + daysAhead);
  return next;
}

function resolvePublicSlotDate(slot, refDate = new Date()) {
  const explicit = String(slot?.date || "").slice(0, 10);
  if (explicit) return explicit;
  const label = norm(String(slot?.label || ""));
  const dayShort = String(slot?.day || "");
  const base = new Date(refDate);
  if (label.includes("aujourd") || dayShort === "Auj.") return formatLocalDate(base);
  if (label.includes("demain") || dayShort === "Dem.") {
    base.setDate(base.getDate() + 1);
    return formatLocalDate(base);
  }
  const weekdays = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"];
  for (let i = 0; i < weekdays.length; i += 1) {
    if (label.includes(weekdays[i])) {
      const jsWeekday = i === 6 ? 0 : i + 1;
      return formatLocalDate(nextWeekdayFrom(base, jsWeekday));
    }
  }
  return "";
}

function parsePublicSlotStartMs(slot, refDate = new Date()) {
  const startIso = String(slot?.startIso || slot?.start_iso || "").trim();
  if (startIso) {
    const ms = Date.parse(startIso);
    if (!Number.isNaN(ms)) return ms;
  }
  const time = String(slot?.time || "").slice(0, 5);
  const date = resolvePublicSlotDate(slot, refDate);
  if (date && time) {
    const ms = Date.parse(`${date}T${time}:00`);
    if (!Number.isNaN(ms)) return ms;
  }
  return null;
}

function normalizePublicSlotDisplay(slot, refDate = new Date()) {
  const date = String(slot?.date || "").slice(0, 10) || resolvePublicSlotDate(slot, refDate);
  const time = String(slot?.time || "").slice(0, 5);
  if (!date || !time) return slot;
  const target = new Date(`${date}T12:00:00`);
  const { day, long } = publicSlotDayLabels(target, refDate);
  return {
    ...slot,
    date,
    time,
    day,
    label: `${long} a ${time}`,
    startIso: slot.startIso || `${date}T${time}:00`,
  };
}

function materializeDemoSlots(slots, refDate = new Date()) {
  return safeArray(slots).map((slot) => normalizePublicSlotDisplay(slot, refDate));
}

function filterFuturePublicSlots(slots, minLeadMinutes = 30) {
  const refDate = new Date();
  const cutoff = Date.now() + Math.max(0, minLeadMinutes) * 60 * 1000;
  return materializeDemoSlots(slots, refDate).filter((slot) => {
    const startMs = parsePublicSlotStartMs(slot, refDate);
    return startMs != null && startMs >= cutoff;
  });
}
const norm = (value) => String(value || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
const addr = (p) => [p?.address?.street, [p?.address?.postalCode, p?.address?.city].filter(Boolean).join(" ")].filter(Boolean).join(", ");
const telHref = (p) => "tel:" + String(p?.phoneTel || p?.phone || "").replace(/[^+0-9]/g, "");
const defaultMotif = (slot) => safeArray(slot?.motifs).find((m) => norm(m).includes("consultation")) || safeArray(slot?.motifs)[0] || "Consultation";

function apiUrl(path) {
  return `${getApiBaseUrl()}${path}`;
}

async function fetchJson(path, options = {}) {
  const response = await fetch(apiUrl(path), {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      if (data?.detail) detail = String(data.detail);
    } catch {
      /* body non-JSON */
    }
    throw new Error(detail);
  }
  return response.json();
}

function mapPublicActionError(err) {
  const raw = String(err?.message || err || "").trim();
  const lower = raw.toLowerCase();
  if (lower.includes("delai") || lower.includes("délai") || lower.includes("minimum")) {
    return raw;
  }
  if (lower.includes("non autorise") || lower.includes("non autorisé") || lower.includes("desactive") || lower.includes("désactiv")) {
    return raw;
  }
  if (lower.includes("401") || lower.includes("identifiant") || lower.includes("telephone") || lower.includes("email")) {
    return "Telephone ou email incorrect pour ce rendez-vous.";
  }
  if (lower.includes("404") || lower.includes("introuvable")) {
    return "Rendez-vous introuvable ou deja traite.";
  }
  if (lower.includes("409") || lower.includes("plus disponible")) {
    return "Ce creneau n'est plus disponible. Choisissez un autre horaire.";
  }
  return raw || "Action impossible pour le moment.";
}

function rulesHint(rules, mode) {
  if (!rules) return "";
  if (mode === "cancel") {
    if (rules.appointment_cancel_allowed === false) {
      return "Les annulations en ligne ne sont pas autorisees pour ce cabinet.";
    }
    const h = Number(rules.appointment_cancel_notice_hours);
    if (h > 0) return `Annulation possible jusqu'a ${h} h avant le rendez-vous.`;
  }
  if (mode === "reschedule") {
    if (rules.appointment_reschedule_allowed === false) {
      return "Le deplacement en ligne n'est pas autorise pour ce cabinet.";
    }
    const h = Number(rules.appointment_reschedule_notice_hours);
    if (h > 0) return `Deplacement possible jusqu'a ${h} h avant le rendez-vous.`;
  }
  return "";
}

async function trackPublicEvent(payload) {
  try {
    let body = payload;
    if (!body?.tenant_id && body?.slug && typeof window !== "undefined") {
      const storedTenantId = window.sessionStorage?.getItem(`uwi_public_tenant:${body.slug}`);
      if (storedTenantId) body = { ...body, tenant_id: Number(storedTenantId) || undefined };
    }
    await fetchJson("/api/public/analytics/event", {
      method: "POST",
      body: JSON.stringify(body),
    });
  } catch {
    // Tracking non-bloquant.
  }
}

function makeFaqs(p, openingHours) {
  return [
    { id: "f1", q: "Nouveaux patients ?", a: `Le cabinet accepte les nouveaux patients ${String(p?.newPatients || "").toLowerCase()}.` },
    { id: "f2", q: "Documents a apporter ?", a: p?.documents || "Carte Vitale, mutuelle, ordonnances." },
    { id: "f3", q: "Acces au cabinet ?", a: `${addr(p)}. ${p?.access || ""}${p?.parking ? `. Parking : ${p.parking}` : ""}.` },
    { id: "f4", q: "Horaires ?", a: safeArray(openingHours).map((h) => `${h.day} : ${h.opens ? `${h.opens}-${h.closes}` : "ferme"}`).join(" - ") },
    { id: "f5", q: "Quel est le tarif ?", a: `${p?.fee || "Non precise"}. Carte Vitale ${p?.carteVitale ? "acceptee" : "non acceptee"}.` },
  ];
}

function getAutoReply(text, faqs) {
  const t = norm(text);
  if (t.includes("urgence")) return "En cas d'urgence medicale, appelez le 15 ou le 112.";
  if (t.includes("horaire") || t.includes("horraire") || t.includes("ouvert")) {
    return faqs.find((f) => f.id === "f4")?.a || "Je peux vous donner les horaires.";
  }
  if (t.includes("adresse") || t.includes("acces") || t.includes("venir")) return faqs.find((f) => f.id === "f3")?.a || "Je peux vous indiquer comment venir.";
  if (t.includes("document") || t.includes("carte vitale")) return faqs.find((f) => f.id === "f2")?.a || "Je peux vous preciser les documents utiles.";
  if (t.includes("nouveau")) return faqs.find((f) => f.id === "f1")?.a || "Je peux vous indiquer si le cabinet accepte de nouveaux patients.";
  if (t.includes("tarif") || t.includes("prix")) return faqs.find((f) => f.id === "f5")?.a || "Je peux vous donner une indication tarifaire.";
  if (t.includes("annuler")) return "Indiquez votre nom et la date du rendez-vous a annuler, et je transmets au cabinet.";
  if (t.includes("modifier") || t.includes("decaler")) return "Indiquez votre nom et le creneau concerne, je transmets votre demande.";
  if (t.includes("rappel")) return "Indiquez votre nom et votre numero. Le cabinet vous rappellera.";
  if (t.includes("rdv") || t.includes("rendez-vous")) return "Bien sur. Choisissez un creneau ou precisez votre preference.";
  return "Merci. Je prends en compte votre demande et peux la transmettre au cabinet.";
}

function getVapiPublicKey() {
  return String(import.meta.env.VITE_VAPI_PUBLIC_KEY || "").trim();
}

function searchDoctors(query, list) {
  const value = norm(query).trim();
  if (value.length < 2) return [];
  const terms = value.split(" ").filter(Boolean);
  return safeArray(list)
    .map((pr) => ({
      pr,
      score: terms.reduce((s, term) => s + (norm([pr.name, pr.specialty, pr.city].join(" ")).includes(term) ? 1 : 0), 0) + (norm(pr.name).startsWith(value) ? 1 : 0),
    }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 6)
    .map((item) => item.pr);
}

function buildStructuredData(p, openingHours, faqs, slots) {
  const canonical = p?.canonicalUrl || `https://www.uwiapp.com/p/${p?.slug || defaultPractitioner.slug}`;
  const physician = {
    "@type": "Physician",
    "@id": `${canonical}#physician`,
    name: p?.name || "Praticien",
    medicalSpecialty: p?.specialty,
    telephone: p?.phone,
    url: canonical,
    address: {
      "@type": "PostalAddress",
      streetAddress: p?.address?.street || "",
      postalCode: p?.address?.postalCode || "",
      addressLocality: p?.address?.city || "",
      addressCountry: p?.address?.country || "FR",
    },
    openingHoursSpecification: safeArray(openingHours)
      .filter((h) => h.opens)
      .map((h) => ({ "@type": "OpeningHoursSpecification", dayOfWeek: h.schemaDay, opens: h.opens, closes: h.closes })),
    availableService: safeArray(slots).slice(0, 6).map((slot) => ({
      "@type": "MedicalProcedure",
      name: `Reserver ${slot.label}`,
      url: `${canonical}?slot=${encodeURIComponent(slot.id)}`,
    })),
  };
  if (p?.reviewsVerified && p?.rating) {
    physician.aggregateRating = { "@type": "AggregateRating", ratingValue: String(p.rating), reviewCount: String(p.reviewCount || 0) };
  }
  return {
    "@context": "https://schema.org",
    "@graph": [
      physician,
      {
        "@type": "FAQPage",
        mainEntity: safeArray(faqs).map((faq) => ({ "@type": "Question", name: faq.q, acceptedAnswer: { "@type": "Answer", text: faq.a } })),
      },
      {
        "@type": "WebSite",
        name: "UWI",
        url: "https://www.uwiapp.com",
        potentialAction: {
          "@type": "SearchAction",
          target: "https://www.uwiapp.com/search?q={search_term_string}",
          "query-input": "required name=search_term_string",
        },
      },
    ],
  };
}

function SeoManager({ practitioner, openingHours, faqs, slots }) {
  const structuredData = useMemo(() => buildStructuredData(practitioner, openingHours, faqs, slots), [practitioner, openingHours, faqs, slots]);

  useEffect(() => {
    if (typeof document === "undefined") return;
    const title = `${practitioner?.name || "Praticien"}, ${String(practitioner?.specialty || "medecin").toLowerCase()} a ${practitioner?.city || ""} - Prendre rendez-vous`;
    const description = `Prenez rendez-vous avec ${practitioner?.name || "ce praticien"} a ${practitioner?.city || ""}. Clara repond 24h/24.`;
    document.title = title;
    const setMeta = (attr, key, val) => {
      let el = document.head.querySelector(`meta[${attr}="${key}"]`);
      if (!el) {
        el = document.createElement("meta");
        el.setAttribute(attr, key);
        document.head.appendChild(el);
      }
      el.setAttribute("content", val);
    };
    setMeta("name", "description", description);
    setMeta("property", "og:title", title);
    setMeta("property", "og:description", description);
    if (practitioner?.canonicalUrl) {
      let canonical = document.head.querySelector('link[rel="canonical"]');
      if (!canonical) {
        canonical = document.createElement("link");
        canonical.setAttribute("rel", "canonical");
        document.head.appendChild(canonical);
      }
      canonical.setAttribute("href", practitioner.canonicalUrl);
    }
  }, [practitioner]);

  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }} />;
}

function ClaraPortrait({ size = 58, compact = false }) {
  const [failed, setFailed] = useState(false);
  return (
    <div className={compact ? "claraPhoto claraPhotoCompact" : "claraPhoto"} style={{ width: size, height: size }}>
      {!failed ? <img src={CLARA_IMAGE} alt="Clara" onError={() => setFailed(true)} /> : <div className="claraFallback">C</div>}
      <span className="claraOnlineDot" />
    </div>
  );
}

function UwiSearchBar({ data = defaultSearchData, onSearchUsed }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const inputRef = useRef(null);
  const results = useMemo(() => searchDoctors(q, data), [q, data]);

  useEffect(() => {
    const handle = (event) => {
      if (ref.current && !ref.current.contains(event.target)) setOpen(false);
    };
    document.addEventListener("pointerdown", handle);
    return () => document.removeEventListener("pointerdown", handle);
  }, []);

  return (
    <div ref={ref} className="uwiSearch">
      <span className="uwiSearchIcon">⌕</span>
      <input
        ref={inputRef}
        value={q}
        onChange={(event) => {
          setQ(event.target.value);
          setOpen(true);
          const query = String(event.target.value || "").trim();
          if (query.length >= 2) onSearchUsed?.(query, searchDoctors(query, data).length);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
          if (event.key === "Enter" && results[0]?.url) window.location.href = results[0].url;
        }}
        placeholder="Nom, specialite ou ville"
      />
      {q && <button className="uwiSearchClear" onClick={() => { setQ(""); inputRef.current?.focus(); }} type="button">x</button>}
      {open && q.length >= 2 && (
        <div className="uwiDrop">
          <div className="uwiDropTitle">Resultats UWI</div>
          {results.length > 0 ? results.map((pr) => (
            <a
              key={pr.id}
              className="uwiResult"
              href={pr.url}
              onClick={() => onSearchUsed?.(q, results.length)}
            >
              <span className="uwiResultBadge">{pr.specialty.charAt(0)}</span>
              <span className="uwiResultInfo"><strong>{pr.name}</strong><span>{pr.specialty} - {pr.city}</span><em>{pr.availability}</em></span>
              <span className={pr.acceptsNewPatients ? "uwiResultTag ok" : "uwiResultTag"}>{pr.acceptsNewPatients ? "Nouveaux" : "A confirmer"}</span>
            </a>
          )) : <div className="uwiDropEmpty"><strong>Aucun resultat</strong><span>Essayez une autre ville ou specialite.</span></div>}
        </div>
      )}
    </div>
  );
}

function barSlotsToChatOffers(apiSlots, max = 3) {
  return safeArray(apiSlots)
    .slice(0, max)
    .map((slot, i) => ({
      index: i + 1,
      label: slot.label || `Créneau ${i + 1}`,
      id: String(slot.id || ""),
      source: slot.source || "sqlite",
      startIso: slot.startIso || "",
      endIso: slot.endIso || "",
      motifs: safeArray(slot.motifs).length
        ? slot.motifs
        : ["Consultation", "Suivi", "Premiere consultation", "Renouvellement"],
    }));
}

function formatBarSlotsProposalMessage(apiSlots) {
  const offers = barSlotsToChatOffers(apiSlots, 3);
  if (!offers.length) return "";
  const lines = offers.map((o) => `${o.index}. ${o.label}`).join("\n");
  return `Créneaux disponibles :\n${lines}\n\nRépondez par le numéro (1, 2 ou 3), ou cliquez sur un créneau ci-dessous.`;
}

function chatOffersFromResponse(apiSlots) {
  return safeArray(apiSlots)
    .slice(0, 3)
    .map((slot, i) => ({
      index: Number(slot?.index) || i + 1,
      label: slot?.label || `Créneau ${i + 1}`,
      id: String(slot?.id || ""),
      source: slot?.source || "sqlite",
      startIso: slot?.startIso || slot?.start_iso || "",
      endIso: slot?.endIso || slot?.end_iso || "",
      motifs: safeArray(slot?.motifs).length
        ? slot.motifs
        : ["Consultation", "Suivi", "Premiere consultation", "Renouvellement"],
    }));
}

function formatChatSlotsProposalMessage(offers) {
  if (!offers.length) return "";
  const lines = offers.map((o) => `${o.index}. ${o.label}`).join("\n");
  return `Créneaux disponibles :\n${lines}\n\nRépondez par le numéro (1, 2 ou 3), ou cliquez sur un créneau ci-dessous.`;
}

function hasBookableAgendaSlots(apiSlots, meta) {
  if (meta?.source !== "agenda") return false;
  const list = filterFuturePublicSlots(apiSlots);
  return list.some((slot) => String(slot?.startIso || "").trim());
}

function isSlotsLookupPlaceholder(text) {
  const t = String(text || "").trim();
  return CHAT_PROCESSING_PLACEHOLDERS.has(t);
}

function slotFromChatOffer(offer) {
  const idx = Number(offer?.index) || 1;
  return {
    id: String(offer?.id || ""),
    label: offer?.label || `Créneau ${idx}`,
    day: "",
    time: "",
    motifs: safeArray(offer?.motifs).length ? offer.motifs : ["Consultation", "Suivi", "Premiere consultation"],
    source: offer?.source || "sqlite",
    startIso: offer?.startIso || "",
    endIso: offer?.endIso || "",
  };
}

function resolveChatSlotOffer(offer, apiSlots) {
  const base = slotFromChatOffer(offer);
  if (base.id && /^\d+$/.test(base.id) && base.startIso) return base;
  const list = safeArray(apiSlots);
  const idx = Number(offer?.index);
  if (idx >= 1 && list[idx - 1]) {
    const merged = { ...list[idx - 1] };
    if (!merged.startIso && base.startIso) merged.startIso = base.startIso;
    if (!merged.id && base.id) merged.id = base.id;
    if (!merged.source && base.source) merged.source = base.source;
    return merged;
  }
  const label = norm(offer?.label || "");
  const found = list.find((s) => {
    const sl = norm(s.label || "");
    return sl === label || sl.includes(label) || label.includes(sl);
  });
  if (found) {
    return {
      ...found,
      startIso: found.startIso || base.startIso,
      id: found.id || base.id,
      source: found.source || base.source,
    };
  }
  return base;
}

const EMAIL_STRICT = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

function normalizeFrenchPhone(raw) {
  let cleaned = String(raw || "").trim().replace(/[\s\-.()]/g, "");
  if (cleaned.startsWith("+33")) cleaned = `0${cleaned.slice(3)}`;
  else if (cleaned.startsWith("33") && cleaned.length === 11) cleaned = `0${cleaned.slice(2)}`;
  return cleaned;
}

function isValidFrenchPhone(raw) {
  return /^0[1-9]\d{8}$/.test(normalizeFrenchPhone(raw));
}

function phoneValidationError(raw) {
  const s = String(raw || "").trim();
  if (!s) return "Indiquez votre numero de telephone.";
  if (!isValidFrenchPhone(s)) return "Numero invalide (ex. 06 12 34 56 78).";
  return "";
}

function emailValidationError(raw) {
  const s = String(raw || "").trim();
  if (!s) return "";
  if (!EMAIL_STRICT.test(s)) return "Adresse email invalide.";
  return "";
}

function buildBookingSuccessClipboardText(success, cabinetName = "") {
  if (!success) return "";
  const lines = [];
  lines.push(success.confirmed ? "Rendez-vous confirme" : "Demande enregistree");
  if (cabinetName) lines.push(cabinetName);
  if (success.message) lines.push(success.message);
  if (success.label) lines.push(success.label);
  if (success.motif) lines.push(`Motif : ${success.motif}`);
  if (success.bookingCode) lines.push(`Code rendez-vous : ${success.bookingCode}`);
  return lines.filter(Boolean).join("\n");
}

function escapeIcsText(value) {
  return String(value || "")
    .replace(/\\/g, "\\\\")
    .replace(/\n/g, "\\n")
    .replace(/,/g, "\\,")
    .replace(/;/g, "\\;");
}

function toIcsUtcCompact(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return `${d.toISOString().replace(/[-:]/g, "").split(".")[0]}Z`;
}

function downloadBookingIcs({ title, location, description, startIso, endIso, durationMinutes = 30 }) {
  const start = toIcsUtcCompact(startIso);
  if (!start) return false;
  let end = endIso ? toIcsUtcCompact(endIso) : null;
  if (!end) {
    const d = new Date(startIso);
    if (Number.isNaN(d.getTime())) return false;
    d.setMinutes(d.getMinutes() + durationMinutes);
    end = toIcsUtcCompact(d.toISOString());
  }
  if (!end) return false;
  const stamp = toIcsUtcCompact(new Date().toISOString());
  const ics = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//UWI//FR",
    "CALSCALE:GREGORIAN",
    "BEGIN:VEVENT",
    `UID:uwi-${Date.now()}@uwiapp.com`,
    `DTSTAMP:${stamp}`,
    `DTSTART:${start}`,
    `DTEND:${end}`,
    `SUMMARY:${escapeIcsText(title)}`,
    location ? `LOCATION:${escapeIcsText(location)}` : "",
    description ? `DESCRIPTION:${escapeIcsText(description)}` : "",
    "END:VEVENT",
    "END:VCALENDAR",
  ]
    .filter(Boolean)
    .join("\r\n");
  const blob = new Blob([ics], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "rendez-vous-uwi.ics";
  link.click();
  URL.revokeObjectURL(url);
  return true;
}

async function copyTextToClipboard(text) {
  if (!text) return false;
  try {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fallback */
  }
  if (typeof document === "undefined") return false;
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.left = "-9999px";
  document.body.appendChild(ta);
  ta.select();
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch {
    ok = false;
  }
  document.body.removeChild(ta);
  return ok;
}

function BookingSuccessCard({
  success,
  cabinetName,
  location = "",
  onModify,
  onCancel,
  onDocuments,
  onAddress,
  onAskAnother,
}) {
  const [copyState, setCopyState] = useState("idle");
  const [calendarState, setCalendarState] = useState("idle");
  const copyPayload = useMemo(
    () => buildBookingSuccessClipboardText(success, cabinetName),
    [success, cabinetName],
  );
  const canCalendar = Boolean(success?.startIso);

  const handleCopy = useCallback(async () => {
    const ok = await copyTextToClipboard(copyPayload);
    setCopyState(ok ? "done" : "error");
    window.setTimeout(() => setCopyState("idle"), 2200);
  }, [copyPayload]);

  const handleCalendar = useCallback(() => {
    const ok = downloadBookingIcs({
      title: `RDV — ${cabinetName || "Cabinet"}`.trim(),
      location,
      description: copyPayload,
      startIso: success.startIso,
      endIso: success.endIso,
    });
    setCalendarState(ok ? "done" : "error");
    window.setTimeout(() => setCalendarState("idle"), 2200);
  }, [cabinetName, copyPayload, location, success]);

  if (!success) return null;

  return (
    <div className="inlineCard bookingSuccessCard" role="status" aria-live="polite">
      <div className="bookingSuccessIcon">✓</div>
      <b>{success.confirmed ? "Rendez-vous confirme" : "Demande enregistree"}</b>
      <p>{success.message}</p>
      {success.label ? <span className="bookingSuccessSlot">{success.label}</span> : null}
      {success.bookingCode ? (
        <p className="bookingSuccessCode">
          Code rendez-vous : <strong>{success.bookingCode}</strong>
        </p>
      ) : null}

      <div className="bookingSuccessActions">
        <button className="bookingSuccessCopyBtn" type="button" onClick={() => void handleCopy()}>
          {copyState === "done" ? "Copie !" : copyState === "error" ? "Copie impossible" : "Copier le recap"}
        </button>
        {canCalendar ? (
          <button className="bookingSuccessActionBtn" type="button" onClick={handleCalendar}>
            {calendarState === "done"
              ? "Fichier telecharge"
              : calendarState === "error"
                ? "Calendrier indisponible"
                : "Ajouter au calendrier"}
          </button>
        ) : null}
        <div className="bookingSuccessActionRow">
          <button className="bookingSuccessActionBtn" type="button" onClick={onModify}>
            Modifier
          </button>
          <button className="bookingSuccessActionBtn" type="button" onClick={onCancel}>
            Annuler
          </button>
        </div>
        <div className="bookingSuccessActionRow">
          <button className="bookingSuccessActionBtn bookingSuccessActionBtnSoft" type="button" onClick={onDocuments}>
            Documents
          </button>
          <button className="bookingSuccessActionBtn bookingSuccessActionBtnSoft" type="button" onClick={onAddress}>
            Adresse
          </button>
        </div>
        <button className="bookingSuccessWaBtn" type="button" onClick={onAskAnother}>
          Poser une question à Clara
        </button>
      </div>
    </div>
  );
}

function BookingFields({
  slot,
  slug,
  onConfirm,
  onCancel,
  compact = false,
  defaultName = "",
  phoneOnly = false,
  submitting = false,
}) {
  const [motif, setMotif] = useState(() => defaultMotif(slot));
  const [name, setName] = useState(defaultName);
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [knownHint, setKnownHint] = useState("");
  const [touched, setTouched] = useState({ phone: false, email: false, name: false });
  const lookupTimerRef = useRef(null);
  const showNameField = !phoneOnly || !defaultName.trim();
  const phoneErr = phoneValidationError(phone);
  const emailErr = emailValidationError(email);
  const nameErr =
    showNameField && touched.name && name.trim().length < 2
      ? "Indiquez votre nom complet."
      : "";
  const ok =
    Boolean(motif && name.trim().length >= 2 && !phoneErr && !emailErr) &&
    !submitting;

  useEffect(() => {
    setMotif(defaultMotif(slot));
    setKnownHint("");
    setTouched({ phone: false, email: false, name: false });
  }, [slot]);

  useEffect(() => {
    if (defaultName) setName(defaultName);
  }, [defaultName]);

  useEffect(() => {
    if (!slug) return undefined;
    if (lookupTimerRef.current) window.clearTimeout(lookupTimerRef.current);
    const ph = phone.trim();
    const em = email.trim();
    if (!isValidFrenchPhone(ph) && emailValidationError(em)) {
      setKnownHint("");
      return undefined;
    }
    lookupTimerRef.current = window.setTimeout(async () => {
      try {
        const qs = new URLSearchParams();
        if (ph) qs.set("phone", ph);
        if (em) qs.set("email", em);
        const data = await fetchJson(
          `/api/public/praticiens/${encodeURIComponent(slug)}/patient-hint?${qs.toString()}`
        );
        if (data?.found) {
          const display = String(data.displayName || data.name || "").trim();
          if (display && !name.trim()) setName(display);
          if (data.email && !email.trim()) setEmail(String(data.email).trim());
          setKnownHint(display ? `Patient reconnu : ${display}` : "Patient reconnu.");
        } else {
          setKnownHint("");
        }
      } catch {
        setKnownHint("");
      }
    }, 450);
    return () => {
      if (lookupTimerRef.current) window.clearTimeout(lookupTimerRef.current);
    };
  }, [phone, email, slug, name]);

  return (
    <div className={compact ? "modalBody" : "inlineCard"}>
      {!compact && (
        <div className="inlineCardTop">
          <b>Confirmer {slot.label}</b>
          <button className="inlineClose" onClick={onCancel} type="button">Changer</button>
        </div>
      )}
      {compact && <div className="modalSlotRecap">Creneau demande : <strong>{slot.label}</strong></div>}
      <span>
        {phoneOnly && defaultName
          ? `Creneau ${slot.label} — indiquez votre numero pour finaliser.`
          : "Motif pre-selectionne. Vous pouvez le changer si besoin."}
      </span>
      <div className="motifs">{safeArray(slot.motifs).map((m) => <button key={m} className={motif === m ? "motif active" : "motif"} onClick={() => setMotif(m)} type="button">{m}</button>)}</div>
      <div className={showNameField ? "inlineTwoCol" : "inlineOneCol"}>
        {showNameField ? (
          <div className="fieldWrap">
            <input
              className={touched.name && nameErr ? "inputInvalid" : ""}
              value={name}
              onChange={(event) => setName(event.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, name: true }))}
              placeholder="Nom complet"
              autoComplete="name"
            />
            {touched.name && nameErr ? <p className="fieldError">{nameErr}</p> : null}
          </div>
        ) : (
          <p className="inlineNameRecap">
            <b>{defaultName}</b>
          </p>
        )}
        <div className="fieldWrap">
          <input
            className={touched.phone && phoneErr ? "inputInvalid" : ""}
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            onBlur={() => setTouched((t) => ({ ...t, phone: true }))}
            placeholder="Telephone (ex. 06 12 34 56 78)"
            type="tel"
            inputMode="tel"
            autoComplete="tel"
          />
          {touched.phone && phoneErr ? <p className="fieldError">{phoneErr}</p> : null}
        </div>
      </div>
      <div className="fieldWrap">
        <input
          className={`inlineEmailField${touched.email && emailErr ? " inputInvalid" : ""}`}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          onBlur={() => setTouched((t) => ({ ...t, email: true }))}
          placeholder="Email (facultatif)"
          type="email"
          inputMode="email"
          autoComplete="email"
        />
        {touched.email && emailErr ? <p className="fieldError">{emailErr}</p> : null}
      </div>
      {knownHint ? <p className="inlineKnownHint">{knownHint}</p> : null}
      <button
        className="primary"
        disabled={!ok}
        type="button"
        onClick={() => {
          setTouched({ phone: true, email: true, name: true });
          if (!ok) return;
          onConfirm({
            slot,
            motif,
            name: name.trim(),
            phone: normalizeFrenchPhone(phone),
            email: email.trim(),
          });
        }}
      >
        {submitting ? "Confirmation en cours…" : "Confirmer mon rendez-vous"}
      </button>
    </div>
  );
}

const CALLBACK_REASONS = [
  { id: "question_rdv", label: "Question sur un rendez-vous" },
  { id: "modifier", label: "Modifier un rendez-vous" },
  { id: "annuler", label: "Annuler un rendez-vous" },
  { id: "admin", label: "Question administrative" },
  { id: "ordonnance", label: "Ordonnance / document" },
  { id: "other", label: "Autre demande" },
];

const ACTION_TITLES = {
  cancel: "Annuler un rendez-vous",
  reschedule: "Modifier un rendez-vous",
  callback: "Etre rappele par le cabinet",
};

function PublicAppointmentActionModal({ mode, slug, onClose, push, slots, onRefreshSlots, initialBookingCode = "" }) {
  const [step, setStep] = useState(mode === "callback" ? "callback_identify" : "identify");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lookupPhone, setLookupPhone] = useState("");
  const [lookupEmail, setLookupEmail] = useState("");
  const [lookupCode, setLookupCode] = useState(() => String(initialBookingCode || "").trim().toUpperCase());
  const autoLookupStarted = useRef(false);
  const [verifyPhone, setVerifyPhone] = useState("");
  const [verifyEmail, setVerifyEmail] = useState("");
  const [appointments, setAppointments] = useState([]);
  const [selected, setSelected] = useState(null);
  const [cancelReason, setCancelReason] = useState("");
  const [rescheduleSlots, setRescheduleSlots] = useState([]);
  const [pickedSlot, setPickedSlot] = useState(null);
  const [callbackName, setCallbackName] = useState("");
  const [callbackPhone, setCallbackPhone] = useState("");
  const [callbackEmail, setCallbackEmail] = useState("");
  const [callbackReason, setCallbackReason] = useState("other");
  const [callbackMessage, setCallbackMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [actionRules, setActionRules] = useState(null);
  const [verifiedContact, setVerifiedContact] = useState({ phone: "", email: "" });

  const rememberLookupContact = (phoneRaw, emailRaw) => {
    const phone = phoneRaw ? normalizeFrenchPhone(phoneRaw) : "";
    const email = String(emailRaw || "").trim();
    setVerifiedContact({ phone, email });
    if (phone) setVerifyPhone(phoneRaw.trim());
    if (email) setVerifyEmail(email);
  };

  const hasVerifiedContact = Boolean(
    verifiedContact.phone || verifiedContact.email || verifyPhone.trim() || verifyEmail.trim(),
  );

  const resolveConfirmContact = () => {
    const phoneRaw = verifyPhone.trim() || verifiedContact.phone || lookupPhone.trim();
    const emailRaw = verifyEmail.trim() || verifiedContact.email || lookupEmail.trim();
    return {
      phone: phoneRaw ? normalizeFrenchPhone(phoneRaw) : "",
      email: emailRaw.trim().toLowerCase(),
      phoneRaw,
      emailRaw,
    };
  };

  const verifiedContactHint = () => {
    if (selected?.phoneHint) return selected.phoneHint;
    const { phoneRaw } = resolveConfirmContact();
    if (!phoneRaw) return verifiedContact.email || lookupEmail.trim() || "";
    const digits = phoneRaw.replace(/\D/g, "");
    if (digits.length >= 4) return `${"•".repeat(Math.max(0, digits.length - 2))}${digits.slice(-2)}`;
    return phoneRaw;
  };

  useEffect(() => {
    const handle = (event) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handle);
    return () => document.removeEventListener("keydown", handle);
  }, [onClose]);

  useEffect(() => {
    const code = String(initialBookingCode || "").trim().toUpperCase();
    if (code) setLookupCode(code);
    autoLookupStarted.current = false;
  }, [initialBookingCode, mode]);

  const runLookup = async (overrides = {}) => {
    setError("");
    const phone = String(overrides.phone ?? lookupPhone).trim();
    const email = String(overrides.email ?? lookupEmail).trim();
    const bookingCode = String(overrides.bookingCode ?? lookupCode).trim();
    if (!phone && !email && !bookingCode) {
      setError("Renseignez votre telephone, email ou code rendez-vous.");
      return;
    }
    setLoading(true);
    try {
      const data = await fetchJson(`/api/public/${encodeURIComponent(slug)}/appointments/lookup`, {
        method: "POST",
        body: JSON.stringify({
          phone: phone ? normalizeFrenchPhone(phone) : undefined,
          email: email || undefined,
          bookingCode: bookingCode || undefined,
        }),
      });
      const found = safeArray(data?.appointments);
      if (!found.length) {
        setError("Aucun rendez-vous trouve. Verifiez vos informations ou demandez a etre rappele.");
        return;
      }
      setAppointments(found);
      setActionRules(data?.rules || null);
      rememberLookupContact(phone, email);
      const rulesText = rulesHint(data?.rules, mode);
      if (mode === "cancel" && data?.rules?.appointment_cancel_allowed === false) {
        setError(rulesText || "Annulation en ligne indisponible.");
        return;
      }
      if (mode === "reschedule" && data?.rules?.appointment_reschedule_allowed === false) {
        if (found.length === 1) setSelected(found[0]);
        setStep("reschedule-unavailable");
        return;
      }
      if (found.length === 1) {
        setSelected(found[0]);
        if (mode === "cancel") setStep("confirm-cancel");
        else if (mode === "reschedule") {
          const loaded = await loadRescheduleSlots();
          if (!loaded.length) setStep("reschedule-unavailable");
          else setStep("reschedule-slots");
        }
      } else {
        setStep("select");
      }
    } catch (err) {
      setError(mapPublicActionError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const code = String(initialBookingCode || "").trim();
    if (!code || mode === "callback" || autoLookupStarted.current) return;
    autoLookupStarted.current = true;
    void runLookup({ bookingCode: code, phone: "", email: "" });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- lookup initial une fois a l'ouverture
  }, [initialBookingCode, mode, slug]);

  const loadRescheduleSlots = async () => {
    let loaded = [];
    if (safeArray(slots).length) {
      loaded = filterFuturePublicSlots(slots).slice(0, 8);
    } else if (typeof onRefreshSlots === "function") {
      loaded = safeArray(await onRefreshSlots()).slice(0, 8);
    } else {
      try {
        const data = await fetchJson(`/api/public/slots/${encodeURIComponent(slug)}?count=8`);
        loaded = filterFuturePublicSlots(safeArray(data?.slots));
      } catch {
        loaded = [];
      }
    }
    setRescheduleSlots(loaded);
    return loaded;
  };

  const pickAppointment = async (appt) => {
    setSelected(appt);
    setError("");
    if (mode === "cancel") {
      setStep("confirm-cancel");
      return;
    }
    setLoading(true);
    try {
      const loaded = await loadRescheduleSlots();
      if (!loaded.length) setStep("reschedule-unavailable");
      else setStep("reschedule-slots");
    } finally {
      setLoading(false);
    }
  };

  const confirmCancel = async () => {
    if (!selected?.actionToken) return;
    const { phone, email } = resolveConfirmContact();
    if (!phone && !email) {
      setError("Indiquez le telephone ou l'email associe au rendez-vous.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await fetchJson(`/api/public/${encodeURIComponent(slug)}/appointments/cancel`, {
        method: "POST",
        body: JSON.stringify({
          actionToken: selected.actionToken,
          phone: phone || undefined,
          email: email || undefined,
          reason: cancelReason.trim() || undefined,
        }),
      });
      setSuccessMessage("Votre rendez-vous a bien ete annule. Le cabinet a ete informe. Un SMS et/ou un email de confirmation vous sera envoye si vos coordonnees sont connues.");
      setStep("success");
      push([{ from: "clara", text: "Votre rendez-vous a bien ete annule. Un SMS ou un email de confirmation vous a ete envoye si possible." }]);
      trackPublicEvent({ slug, event: "booking_cancelled", source: "public_action" });
    } catch (err) {
      setError(mapPublicActionError(err));
    } finally {
      setLoading(false);
    }
  };

  const confirmReschedule = async () => {
    if (!selected?.actionToken || !pickedSlot) return;
    const { phone, email } = resolveConfirmContact();
    if (!phone && !email) {
      setError("Indiquez le telephone ou l'email associe au rendez-vous.");
      return;
    }
    const slotId = String(pickedSlot.id || pickedSlot.slot_id || "").trim();
    if (!slotId) {
      setError("Ce creneau ne peut pas etre selectionne. Choisissez un autre horaire.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await fetchJson(`/api/public/${encodeURIComponent(slug)}/appointments/reschedule`, {
        method: "POST",
        body: JSON.stringify({
          actionToken: selected.actionToken,
          phone: phone || undefined,
          email: email || undefined,
          newSlotId: slotId,
          slotLabel: pickedSlot.label || "",
          startIso: pickedSlot.startIso || "",
          endIso: pickedSlot.endIso || "",
          slotSource: pickedSlot.source || "sqlite",
        }),
      });
      const codeHint = data?.bookingCode ? ` Nouveau code : ${data.bookingCode}.` : "";
      const notifyHint = " Un SMS et/ou un email de confirmation vous sera envoye si vos coordonnees sont connues.";
      setSuccessMessage(`Votre rendez-vous a ete deplace au creneau ${pickedSlot.label || pickedSlot.time || ""}.${codeHint}${notifyHint}`);
      setStep("success");
      push([{ from: "clara", text: `Votre rendez-vous a ete deplace avec succes.${codeHint} Un SMS ou un email de confirmation vous a ete envoye si possible.` }]);
      trackPublicEvent({ slug, event: "booking_rescheduled", source: "public_action" });
    } catch (err) {
      setError(mapPublicActionError(err));
    } finally {
      setLoading(false);
    }
  };

  const submitCallback = async () => {
    if (!callbackName.trim() || !isValidFrenchPhone(callbackPhone)) {
      setError("Renseignez votre nom et un numero de telephone valide.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await fetchJson(`/api/public/${encodeURIComponent(slug)}/callback-requests`, {
        method: "POST",
        body: JSON.stringify({
          name: callbackName.trim(),
          phone: normalizeFrenchPhone(callbackPhone),
          email: callbackEmail.trim() || undefined,
          reason: callbackReason,
          message: callbackMessage.trim() || undefined,
          actionToken: selected?.actionToken || undefined,
        }),
      });
      setSuccessMessage("Votre demande a ete transmise au cabinet. Vous serez recontacte dans les meilleurs delais.");
      setStep("success");
      push([{ from: "clara", text: "Votre demande de rappel a bien ete enregistree." }]);
      trackPublicEvent({ slug, event: "callback_requested", source: "public_action" });
    } catch (err) {
      const detail = String(err?.message || err?.detail || "").trim();
      if (err?.status === 403 || /enregistr/i.test(detail)) {
        setError("Cette demande est reservee aux patients deja enregistres au cabinet.");
      } else {
        setError(detail || "Impossible d'envoyer votre demande.");
      }
    } finally {
      setLoading(false);
    }
  };

  const verifyRegisteredPatientForCallback = async () => {
    setError("");
    const phone = lookupPhone.trim();
    const email = lookupEmail.trim();
    if (!phone && !email) {
      setError("Indiquez le telephone ou l'email associe a votre fiche patient.");
      return;
    }
    if (phone && !isValidFrenchPhone(phone)) {
      setError("Numero de telephone invalide.");
      return;
    }
    setLoading(true);
    try {
      const qs = new URLSearchParams();
      if (phone) qs.set("phone", normalizeFrenchPhone(phone));
      if (email) qs.set("email", email);
      const data = await fetchJson(
        `/api/public/praticiens/${encodeURIComponent(slug)}/patient-hint?${qs.toString()}`
      );
      if (!data?.found) {
        setError(
          "Cette demande est reservee aux patients deja enregistres au cabinet. "
          + "Prenez rendez-vous en ligne ou contactez le cabinet par telephone."
        );
        return;
      }
      const display = String(data.displayName || data.name || "").trim();
      setCallbackName(display);
      setCallbackPhone(data.phone ? normalizeFrenchPhone(data.phone) : (phone ? normalizeFrenchPhone(phone) : ""));
      setCallbackEmail(String(data.email || email || "").trim());
      rememberLookupContact(phone || data.phone || "", data.email || email || "");
      setStep("callback");
    } catch (err) {
      setError(err?.message || "Verification impossible pour le moment.");
    } finally {
      setLoading(false);
    }
  };

  const renderSelectedRecap = () => {
    if (!selected) return null;
    return (
      <div className="modalSlotRecap">
        {selected.slotLabel || `${selected.date || ""} ${selected.time || ""}`.trim()}
        {selected.bookingCode ? ` — ${selected.bookingCode}` : ""}
        {selected.motif ? ` · ${selected.motif}` : ""}
      </div>
    );
  };

  return (
    <div className="overlay" onClick={(event) => event.target.classList.contains("overlay") && onClose()} role="dialog" aria-modal="true">
      <div className="modal">
        <div className="modalClaraBar">
          <ClaraPortrait size={38} compact />
          <span>{ACTION_TITLES[mode] || "Gerer mon rendez-vous"}</span>
        </div>
        <div className="modalBody">
          {step === "identify" ? (
            <>
              <p className="actionModalHint">Renseignez votre telephone, email ou code rendez-vous (ex. RDV-A7K3M2).</p>
              <input value={lookupPhone} onChange={(e) => setLookupPhone(e.target.value)} placeholder="Telephone" type="tel" />
              <input value={lookupEmail} onChange={(e) => setLookupEmail(e.target.value)} placeholder="Email (facultatif)" type="email" />
              <input value={lookupCode} onChange={(e) => setLookupCode(e.target.value.toUpperCase())} placeholder="Code rendez-vous (facultatif)" />
              {error ? <p className="fieldError">{error}</p> : null}
              <button className="primary" type="button" disabled={loading} onClick={() => void runLookup()}>
                {loading ? "Recherche…" : "Retrouver mon rendez-vous"}
              </button>
            </>
          ) : null}

          {step === "select" ? (
            <>
              <p className="actionModalHint">Plusieurs rendez-vous trouves. Choisissez celui concerne :</p>
              {appointments.map((appt) => (
                <button key={appt.actionToken} type="button" className="actionApptPick" onClick={() => void pickAppointment(appt)}>
                  <strong>{appt.slotLabel || `${appt.date} ${appt.time}`}</strong>
                  <span>{appt.motif}{appt.bookingCode ? ` · ${appt.bookingCode}` : ""}</span>
                </button>
              ))}
              {error ? <p className="fieldError">{error}</p> : null}
            </>
          ) : null}

          {step === "confirm-cancel" ? (
            <>
              {renderSelectedRecap()}
              {rulesHint(actionRules, "cancel") ? (
                <p className="actionModalHint">{rulesHint(actionRules, "cancel")}</p>
              ) : null}
              {hasVerifiedContact ? (
                <p className="actionModalHint">
                  Confirmation avec vos coordonnees deja renseignees ({verifiedContactHint()}).
                </p>
              ) : (
                <>
                  <p className="actionModalHint">Pour confirmer l&apos;annulation, indiquez le telephone ou l&apos;email associe au rendez-vous.</p>
                  <input value={verifyPhone} onChange={(e) => setVerifyPhone(e.target.value)} placeholder="Telephone" type="tel" />
                  <input value={verifyEmail} onChange={(e) => setVerifyEmail(e.target.value)} placeholder="Email" type="email" />
                </>
              )}
              <input value={cancelReason} onChange={(e) => setCancelReason(e.target.value)} placeholder="Motif (facultatif)" />
              {error ? <p className="fieldError">{error}</p> : null}
              <button className="primary" type="button" disabled={loading} onClick={() => void confirmCancel()}>
                {loading ? "Annulation…" : "Confirmer l'annulation"}
              </button>
            </>
          ) : null}

          {step === "reschedule-slots" ? (
            <>
              {renderSelectedRecap()}
              {rulesHint(actionRules, "reschedule") ? (
                <p className="actionModalHint">{rulesHint(actionRules, "reschedule")}</p>
              ) : null}
              <p className="actionModalHint">
                {hasVerifiedContact
                  ? "Choisissez un nouveau creneau, puis confirmez."
                  : "Choisissez un nouveau creneau, puis confirmez avec votre telephone ou email."}
              </p>
              <div className="actionSlotGrid">
                {rescheduleSlots.map((slot) => (
                  <button
                    key={slot.id || slot.label}
                    type="button"
                    className={`actionSlotPick${pickedSlot?.id === slot.id ? " active" : ""}`}
                    onClick={() => setPickedSlot(slot)}
                  >
                    {slot.label || `${slot.day || ""} ${slot.time || ""}`}
                  </button>
                ))}
              </div>
              {pickedSlot && hasVerifiedContact ? (
                <p className="actionModalHint">
                  Confirmation avec vos coordonnees deja renseignees ({verifiedContactHint()}).
                </p>
              ) : null}
              {pickedSlot && !hasVerifiedContact ? (
                <>
                  <input value={verifyPhone} onChange={(e) => setVerifyPhone(e.target.value)} placeholder="Telephone" type="tel" />
                  <input value={verifyEmail} onChange={(e) => setVerifyEmail(e.target.value)} placeholder="Email" type="email" />
                </>
              ) : null}
              {error ? <p className="fieldError">{error}</p> : null}
              <button className="primary" type="button" disabled={loading || !pickedSlot} onClick={() => void confirmReschedule()}>
                {loading ? "Deplacement…" : "Confirmer le nouveau creneau"}
              </button>
            </>
          ) : null}

          {step === "reschedule-unavailable" ? (
            <>
              {renderSelectedRecap()}
              <p className="actionModalHint">Ce rendez-vous ne peut pas etre deplace automatiquement en ligne. Seuls les patients enregistres peuvent demander un rappel.</p>
              <button className="primary" type="button" onClick={() => setStep("callback_identify")}>Demander a etre rappele</button>
            </>
          ) : null}

          {step === "callback_identify" ? (
            <>
              <p className="actionModalHint">
                Pour etre rappele, identifiez-vous avec le telephone ou l&apos;email de votre fiche patient au cabinet.
              </p>
              <input value={lookupPhone} onChange={(e) => setLookupPhone(e.target.value)} placeholder="Telephone" type="tel" />
              <input value={lookupEmail} onChange={(e) => setLookupEmail(e.target.value)} placeholder="Email (facultatif)" type="email" />
              {error ? <p className="fieldError">{error}</p> : null}
              <button className="primary" type="button" disabled={loading} onClick={() => void verifyRegisteredPatientForCallback()}>
                {loading ? "Verification…" : "Continuer"}
              </button>
            </>
          ) : null}

          {step === "callback" ? (
            <>
              <p className="actionModalHint">Patient reconnu. Precisez votre demande de rappel.</p>
              <input value={callbackName} onChange={(e) => setCallbackName(e.target.value)} placeholder="Nom et prenom" readOnly />
              <input value={callbackPhone} onChange={(e) => setCallbackPhone(e.target.value)} placeholder="Telephone" type="tel" readOnly />
              <input value={callbackEmail} onChange={(e) => setCallbackEmail(e.target.value)} placeholder="Email (facultatif)" type="email" />
              <select className="actionReasonSelect" value={callbackReason} onChange={(e) => setCallbackReason(e.target.value)}>
                {CALLBACK_REASONS.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
              </select>
              <textarea className="actionMessageArea" value={callbackMessage} onChange={(e) => setCallbackMessage(e.target.value)} placeholder="Message (facultatif)" rows={3} />
              {error ? <p className="fieldError">{error}</p> : null}
              <button className="primary" type="button" disabled={loading} onClick={() => void submitCallback()}>
                {loading ? "Envoi…" : "Envoyer ma demande"}
              </button>
            </>
          ) : null}

          {step === "success" ? (
            <div className="modalSuccess">
              <div className="successIcon">✓</div>
              <div className="successTitle">{successMessage}</div>
              <button className="primary" type="button" onClick={onClose}>Fermer</button>
            </div>
          ) : null}
        </div>
        <button className="modalClose" onClick={onClose} type="button">x</button>
      </div>
    </div>
  );
}

function SupervisedModal({ slot, slug, onClose, onConfirm, done, onAskClara }) {
  useEffect(() => {
    const handle = (event) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handle);
    return () => document.removeEventListener("keydown", handle);
  }, [onClose]);

  return (
    <div className="overlay" onClick={(event) => event.target.classList.contains("overlay") && onClose()} role="dialog" aria-modal="true">
      <div className="modal">
        <div className="modalClaraBar">
          <ClaraPortrait size={38} compact />
          <span>{done ? "Votre demande est enregistree. Le cabinet confirmera par SMS." : "Je vois que vous souhaitez ce creneau. Je vous aide a le confirmer."}</span>
        </div>
        {done ? (
          <div className="modalSuccess">
            <div className="successIcon">✓</div>
            <div className="successTitle">Demande enregistree</div>
            <button
              className="modalWaCta"
              type="button"
              onClick={() => {
                if (onAskClara) onAskClara();
                else onClose();
              }}
            >
              Poser une question à Clara
            </button>
          </div>
        ) : (
          <BookingFields slot={slot} slug={slug} onConfirm={onConfirm} onCancel={onClose} compact />
        )}
        <button className="modalClose" onClick={onClose} type="button">x</button>
      </div>
    </div>
  );
}

export default function PagePubliquePraticienUWI() {
  const { slug = defaultPractitioner.slug } = useParams();
  const [practitioner, setPractitioner] = useState(defaultPractitioner);
  const [slots, setSlots] = useState(defaultSlots);
  const [slotsMeta, setSlotsMeta] = useState({ source: null, calendar: null });
  const [searchData, setSearchData] = useState(defaultSearchData);
  const [dataStatus, setDataStatus] = useState("loading");
  const [messages, setMessages] = useState([{ id: 0, from: "clara", text: "Bonjour, comment puis-je vous aider ?" }]);
  const [input, setInput] = useState("");
  const [inlineSlot, setInlineSlot] = useState(null);
  const [bookingSubmitting, setBookingSubmitting] = useState(false);
  const [bookingSuccess, setBookingSuccess] = useState(null);
  const [modalSlot, setModalSlot] = useState(null);
  const [placeholderIdx, setPlaceholderIdx] = useState(0);
  const [showAllSlots, setShowAllSlots] = useState(false);
  const [bookingDone, setBookingDone] = useState(false);
  const [actionFlowMode, setActionFlowMode] = useState(null);
  const [actionFlowInitialCode, setActionFlowInitialCode] = useState("");
  const [postBookingChatOpen, setPostBookingChatOpen] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState("idle");
  const [voiceError, setVoiceError] = useState("");
  const [composerOutOfView, setComposerOutOfView] = useState(false);
  const [slotsLoading, setSlotsLoading] = useState(true);
  const [slotsRefreshing, setSlotsRefreshing] = useState(false);
  const threadRef = useRef(null);
  const chatHeroRef = useRef(null);
  const slotInitDone = useRef(false);
  const pageViewTracked = useRef(false);
  const msgId = useRef(1);
  const sourceRef = useRef("direct");
  const vapiRef = useRef(null);
  const conversationIdRef = useRef(null);
  const tenantIdRef = useRef(null);
  const eventSourceRef = useRef(null);
  const streamConversationIdRef = useRef(null);
  const pendingTurnRef = useRef(null);
  const slotsRef = useRef(defaultSlots);
  const slotsMetaRef = useRef({ source: null, calendar: null });
  const openActionFlowRef = useRef(null);
  const openingHours = safeArray(practitioner.openingHours).length ? practitioner.openingHours : defaultOpeningHours;
  const faqs = useMemo(() => makeFaqs(practitioner, openingHours), [practitioner, openingHours]);
  const vapiPublicKey = useMemo(() => getVapiPublicKey(), []);
  const voiceReady = Boolean(vapiPublicKey && practitioner?.vapiAssistantId);

  const push = useCallback((items) => setMessages((prev) => prev.concat(items.map((m) => ({ ...m, id: msgId.current++ })))), []);

  useEffect(() => {
    slotsRef.current = slots;
  }, [slots]);

  useEffect(() => {
    slotsMetaRef.current = slotsMeta;
  }, [slotsMeta]);

  const pushSlotProposal = useCallback((offers, messageText, { provisional = false } = {}) => {
    if (!offers.length || !messageText) return false;
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      const lastText = last?.from === "clara" ? String(last?.text || "").trim() : "";
      const nextMsg = {
        id: msgId.current++,
        from: "clara",
        text: messageText,
        slots: offers,
        ...(provisional ? { provisional: true } : {}),
      };
      if (last?.from === "clara" && (isSlotsLookupPlaceholder(lastText) || last?.provisional)) {
        return prev.slice(0, -1).concat([nextMsg]);
      }
      return prev.concat([nextMsg]);
    });
    return true;
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      sourceRef.current = params.get("slot") ? "google_slot" : "direct";
    }
    pageViewTracked.current = false;
    slotInitDone.current = false;
    setBookingDone(false);
    setVoiceError("");
    setVoiceStatus("idle");
    setInlineSlot(null);
    setBookingSuccess(null);
    setBookingSubmitting(false);
    setModalSlot(null);
    setActionFlowMode(null);
    conversationIdRef.current = null;
    streamConversationIdRef.current = null;
    pendingTurnRef.current = null;
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setMessages([{ id: 0, from: "clara", text: "Bonjour, comment puis-je vous aider ?" }]);
    if (vapiRef.current && typeof vapiRef.current.stop === "function") {
      try {
        vapiRef.current.stop();
      } catch {
        // no-op
      }
    }
  }, [slug]);

  useEffect(() => {
    let cancelled = false;
    const sessionCached = readSessionSlots(slug);
    const hasSessionCache = Boolean(sessionCached?.slots?.length);

    setSlots(hasSessionCache ? filterFuturePublicSlots(sessionCached.slots) : filterFuturePublicSlots(buildDefaultDemoSlots()));
    setSlotsMeta({
      source: sessionCached?.source || null,
      calendar: sessionCached?.calendar || null,
    });
    setSlotsLoading(!hasSessionCache);
    setSlotsRefreshing(hasSessionCache);

    async function loadPractitioner() {
      setDataStatus("loading");
      try {
        const practitionerData = await fetchJson(
          `/api/public/practitioner/${encodeURIComponent(slug)}?requireExists=1`
        );
        if (cancelled) return;
        const tid = practitionerData?.tenantId ?? practitionerData?.tenant_id;
        if (tid != null && tid !== "") {
          tenantIdRef.current = Number(tid) || null;
          if (tenantIdRef.current && typeof window !== "undefined") {
            window.sessionStorage?.setItem(`uwi_public_tenant:${slug}`, String(tenantIdRef.current));
          }
        }
        setPractitioner({
          ...defaultPractitioner,
          ...practitionerData,
          slug,
          canonicalUrl: practitionerData.canonicalUrl || `https://www.uwiapp.com/p/${slug}`,
        });
        setDataStatus("ready");
      } catch (error) {
        if (cancelled) return;
        if (String(error?.message || "").includes("404")) {
          setDataStatus("not_found");
          setSlotsLoading(false);
          return;
        }
        setPractitioner({ ...defaultPractitioner, slug, canonicalUrl: `https://www.uwiapp.com/p/${slug}` });
        setDataStatus("fallback");
      }
    }

    async function loadSlots() {
      try {
        const slotData = await fetchJson(`/api/public/slots/${encodeURIComponent(slug)}?count=8`);
        if (cancelled) return;
        const freshSlots = filterFuturePublicSlots(slotData.slots);
        if (freshSlots.length) {
          setSlots(freshSlots);
          setSlotsMeta({ source: slotData.source || null, calendar: slotData.calendar || null });
          writeSessionSlots(slug, { ...slotData, slots: freshSlots });
        } else if (safeArray(slotData.slots).length) {
          setSlotsMeta({ source: slotData.source || null, calendar: slotData.calendar || null });
        }
      } catch {
        // Conserve les créneaux affichés (cache session ou démo).
      } finally {
        if (!cancelled) {
          setSlotsLoading(false);
          setSlotsRefreshing(false);
        }
      }
    }

    async function loadSearch() {
      try {
        const searchDataResponse = await fetchJson("/api/public/search?q=");
        if (cancelled) return;
        if (safeArray(searchDataResponse.results).length) setSearchData(searchDataResponse.results);
      } catch {
        // non bloquant
      }
    }

    void loadPractitioner();
    void loadSlots();
    void loadSearch();

    return () => {
      cancelled = true;
    };
  }, [slug]);

  useEffect(() => {
    if (typeof window === "undefined" || typeof IntersectionObserver === "undefined") return;
    const target = chatHeroRef.current;
    if (!target) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry) return;
      const scrolledPast = !entry.isIntersecting && entry.boundingClientRect.bottom < 80;
      setComposerOutOfView(scrolledPast);
    }, { threshold: 0, rootMargin: "0px 0px -60px 0px" });
    observer.observe(target);
    return () => observer.disconnect();
  }, [dataStatus]);

  const scrollToComposer = useCallback(() => {
    chatHeroRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, []);

  useEffect(() => {
    if (pageViewTracked.current) return;
    if (dataStatus !== "ready" && dataStatus !== "fallback") return;
    pageViewTracked.current = true;
    trackPublicEvent({
      slug,
      event: "page_view",
      source: sourceRef.current,
      metadata: {
        hasSlotParam: typeof window !== "undefined" ? window.location.search.includes("slot=") : false,
      },
    });
  }, [dataStatus, slug]);

  useEffect(() => {
    const el = threadRef.current;
    if (!el) return;
    const scroll = () => {
      el.scrollTop = el.scrollHeight;
    };
    scroll();
    requestAnimationFrame(scroll);
  }, [messages, inlineSlot]);

  useEffect(() => {
    const timer = setInterval(() => setPlaceholderIdx((idx) => (idx + 1) % inputExamples.length), 4200);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (slotInitDone.current || typeof window === "undefined" || !slots.length) return;
    slotInitDone.current = true;
    const found = slots.find((slot) => slot.id === new URLSearchParams(window.location.search).get("slot"));
    if (found) {
      setMessages([{ id: 0, from: "clara", text: "Je vois que vous souhaitez ce creneau. Je vous aide a le confirmer." }]);
      setModalSlot(found);
      trackPublicEvent({
        slug,
        event: "modal_opened",
        source: "url_param",
        slotId: found.id,
        slotLabel: found.label,
      });
    }
  }, [slots, slug]);

  const inferredPatientName = useMemo(() => {
    let sawNameAsk = false;
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const m = messages[i];
      if (m.from === "clara" && /nom\s+et\s+pr[ée]nom|nom\s+complet/i.test(String(m.text || ""))) {
        sawNameAsk = true;
        continue;
      }
      if (sawNameAsk && m.from === "patient") {
        const t = String(m.text || "").trim();
        if (!t || BOOKING_START.test(t) || isGreetingOnly(t)) break;
        if (PLAUSIBLE_PATIENT_NAME.test(t) && t.split(/\s+/).length >= 2) {
          return t
            .split(/\s+/)
            .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
            .join(" ");
        }
        if (LOOKS_LIKE_NAME.test(t)) return t;
        break;
      }
      if (m.from === "patient" && sawNameAsk) break;
    }
    return "";
  }, [messages]);

  const lastSlotOffers = useCallback(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const offers = safeArray(messages[i]?.slots);
      if (offers.length) return offers;
    }
    return [];
  }, [messages]);

  const lastSlotsMessageId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i]?.from === "clara" && safeArray(messages[i]?.slots).length) {
        return messages[i].id;
      }
    }
    return null;
  }, [messages]);

  const removeLastSlotsMessage = useCallback(() => {
    setMessages((prev) => {
      for (let i = prev.length - 1; i >= 0; i -= 1) {
        const msg = prev[i];
        if (msg?.from === "clara" && safeArray(msg?.slots).length) {
          return prev.filter((_, idx) => idx !== i);
        }
      }
      return prev;
    });
  }, []);

  const contactFormOpen = Boolean(inlineSlot || modalSlot || actionFlowMode);
  const postBookingMode = Boolean(bookingSuccess);
  const postBookingLocked = postBookingMode && !postBookingChatOpen;
  const hideChatComposer = contactFormOpen || (postBookingMode && !postBookingChatOpen);

  useEffect(() => {
    if (hideChatComposer) setInput("");
  }, [hideChatComposer]);

  const chooseSlot = useCallback((slot) => {
    if (slotsRefreshing) return;
    if (slotsMeta.source === "agenda" && !slot?.startIso) {
      push([{ from: "clara", text: "Les creneaux se mettent a jour. Patientez une seconde puis reessayez." }]);
      return;
    }
    const replace = Boolean(inlineSlot);
    setInput("");
    setInlineSlot(slot);
    push([
      { from: "patient", text: `${replace ? "Je prefere le creneau " : "Je souhaite le creneau "}${slot.label}.` },
      {
        from: "clara",
        text: `Parfait pour ${slot.label}. Indiquez votre nom et votre telephone ci-dessous pour confirmer votre rendez-vous.`,
      },
    ]);
    trackPublicEvent({
      slug,
      event: "slot_clicked",
      source: sourceRef.current,
      slotId: slot.id,
      slotLabel: slot.label,
      motif: defaultMotif(slot),
    });
    trackPublicEvent({
      slug,
      event: "booking_started",
      source: sourceRef.current,
      slotId: slot.id,
      slotLabel: slot.label,
      motif: defaultMotif(slot),
    });
  }, [inlineSlot, push, slug, slotsMeta.source, slotsRefreshing]);

  const handleStreamPayload = useCallback((payload) => {
    const type = String(payload?.type || "");
    if (type === "partial") return;
    if (type === "final") {
      const slotsPayload = Array.isArray(payload?.slots) ? payload.slots : [];
      const text = String(payload?.text || "").trim();
      const convState = String(payload?.conv_state || "");
      if (convState === "CONFIRMED" && text) {
        setBookingSuccess({ label: "", message: text, confirmed: true });
        setInlineSlot(null);
      }
      if (pendingTurnRef.current) {
        const resolve = pendingTurnRef.current;
        pendingTurnRef.current = null;
        resolve(Boolean(text) || slotsPayload.length > 0);
      }
      if (text) {
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          const lastText = last?.from === "clara" ? String(last?.text || "").trim() : "";
          if (
            last?.from === "clara"
            && (isSlotsLookupPlaceholder(lastText) || last?.provisional)
          ) {
            return prev.slice(0, -1).concat([
              {
                id: msgId.current++,
                from: "clara",
                text,
                slots: slotsPayload.length ? slotsPayload : undefined,
              },
            ]);
          }
          if (last?.from === "clara" && lastText === text && !slotsPayload.length) {
            return prev;
          }
          const asksNameAgain =
            /nom\s+et\s+pr[ée]nom/i.test(text) &&
            /nom\s+et\s+pr[ée]nom/i.test(lastText) &&
            !slotsPayload.length;
          if (asksNameAgain) return prev;
          if (last?.from === "clara" && lastText === text) {
            const prevSlots = JSON.stringify(safeArray(last?.slots));
            const newSlots = JSON.stringify(slotsPayload);
            if (!slotsPayload.length || prevSlots === newSlots) return prev;
          }
          return prev.concat([
            { id: msgId.current++, from: "clara", text, slots: slotsPayload.length ? slotsPayload : undefined },
          ]);
        });
      }
      return;
    }
    if (type === "transfer") {
      const slotsPayload = Array.isArray(payload?.slots) ? payload.slots : [];
      if (payload?.text) {
        push([{ from: "clara", text: String(payload.text), slots: slotsPayload.length ? slotsPayload : undefined }]);
      }
      return;
    }
    if (type === "error") {
      if (pendingTurnRef.current) {
        const resolve = pendingTurnRef.current;
        pendingTurnRef.current = null;
        resolve(true);
      }
      push([{ from: "clara", text: String(payload?.message || "Une erreur est survenue, veuillez reessayer.") }]);
    }
  }, [push]);

  const ensureConversationId = useCallback(() => {
    if (!conversationIdRef.current) {
      const id =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `web-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
      conversationIdRef.current = id;
    }
    return conversationIdRef.current;
  }, []);

  const ensureStream = useCallback((conversationId) => {
    if (typeof window === "undefined" || !conversationId) return;
    if (streamConversationIdRef.current === conversationId && eventSourceRef.current) return;
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    const streamUrl = apiUrl(
      `/api/public/praticiens/${encodeURIComponent(slug)}/stream/${encodeURIComponent(conversationId)}`
    );
    const stream = new EventSource(streamUrl);
    streamConversationIdRef.current = conversationId;
    stream.onmessage = (event) => {
      if (!event?.data) return;
      try {
        handleStreamPayload(JSON.parse(event.data));
      } catch {
        // ignore malformed payloads
      }
    };
    stream.onerror = () => {
      // Keep UX stable even if SSE reconnects in background.
    };
    eventSourceRef.current = stream;
  }, [handleStreamPayload, slug]);

  const waitForAgentTurn = useCallback(
    () =>
      new Promise((resolve) => {
        if (pendingTurnRef.current) {
          try {
            pendingTurnRef.current(null);
          } catch {
            // no-op
          }
        }
        pendingTurnRef.current = resolve;
        window.setTimeout(() => {
          if (pendingTurnRef.current === resolve) {
            pendingTurnRef.current = null;
            resolve(null);
          }
        }, CHAT_REPLY_TIMEOUT_MS);
      }),
    []
  );

  const sendChatMessage = useCallback(async (text) => {
    const clean = String(text || "").trim();
    if (!clean) return;
    const convId = ensureConversationId();
    ensureStream(convId);
    push([{ from: "patient", text: clean }]);
    trackPublicEvent({
      slug,
      event: "chat_message_sent",
      source: sourceRef.current,
      metadata: { length: clean.length },
    });

    const chatPayload = {
      message: clean,
      conversation_id: convId,
      ...(tenantIdRef.current ? { tenant_id: tenantIdRef.current } : {}),
    };

    const applyChatResponse = (response) => {
      const conversationId = String(response?.conversation_id || convId);
      if (conversationId) {
        conversationIdRef.current = conversationId;
        ensureStream(conversationId);
      }
      if (response?.reply) {
        push([{ from: "clara", text: String(response.reply) }]);
      }
    };

    const showInstantReply = (replyText) => {
      push([{ from: "clara", text: replyText }]);
    };

    const postChat = async () =>
      fetchJson(`/api/public/praticiens/${encodeURIComponent(slug)}/chat`, {
        method: "POST",
        body: JSON.stringify(chatPayload),
      });

    const applyBarSlotsFallback = ({ provisional = true } = {}) => {
      const currentSlots = slotsRef.current;
      const currentMeta = slotsMetaRef.current;
      if (!hasBookableAgendaSlots(currentSlots, currentMeta)) return false;
      const offers = barSlotsToChatOffers(currentSlots, 3);
      const msg = formatBarSlotsProposalMessage(currentSlots);
      return pushSlotProposal(offers, msg, { provisional });
    };

    const applyResponseSlots = (response, { provisional = true } = {}) => {
      const offers = chatOffersFromResponse(response?.slots);
      const msg = formatChatSlotsProposalMessage(offers);
      if (!offers.length || !msg) return false;
      return pushSlotProposal(offers, msg, { provisional });
    };

    const refreshAgendaSlotsForChat = async () => {
      try {
        const data = await fetchJson(`/api/public/slots/${encodeURIComponent(slug)}?count=8`);
        const fresh = filterFuturePublicSlots(safeArray(data?.slots));
        if (!fresh.length || data?.source !== "agenda") return false;
        setSlots(fresh);
        setSlotsMeta({ source: data.source || "agenda", calendar: data.calendar || null });
        writeSessionSlots(slug, { ...data, slots: fresh });
        slotsRef.current = fresh;
        slotsMetaRef.current = { source: data.source || "agenda", calendar: data.calendar || null };
        return true;
      } catch {
        return false;
      }
    };

    const syncChatInBackground = async (instantText, opts = {}) => {
      ensureStream(convId);
      const turnWait = waitForAgentTurn();
      const isSlotsLookup = Boolean(instantText && isSlotsLookupPlaceholder(instantText));
      const allowSlotsReuse = opts?.allowSlotsReuse !== false;
      const timers = [];

      if (instantText) showInstantReply(instantText);

      const tryShowCachedSlots = async ({ refresh = false } = {}) => {
        if (refresh) await refreshAgendaSlotsForChat();
        return applyBarSlotsFallback({ provisional: true });
      };

      if (isSlotsLookup && allowSlotsReuse) {
        timers.push(
          window.setTimeout(() => {
            void tryShowCachedSlots();
          }, CHAT_SLOTS_BAR_INSTANT_MS),
        );
        timers.push(
          window.setTimeout(() => {
            void tryShowCachedSlots({ refresh: true });
          }, CHAT_SLOTS_EARLY_FALLBACK_MS),
        );
      }

      let gotFinalReply = false;
      try {
        let response;
        try {
          response = await postChat();
        } catch {
          response = await postChat();
        }
        const conversationId = String(response?.conversation_id || convId);
        if (conversationId) {
          conversationIdRef.current = conversationId;
          ensureStream(conversationId);
        }
        if (isSlotsLookup && allowSlotsReuse && safeArray(response?.slots).length) {
          applyResponseSlots(response, { provisional: true });
        }
        if (!instantText && response?.reply) {
          applyChatResponse(response);
          gotFinalReply = true;
          if (pendingTurnRef.current) {
            const resolve = pendingTurnRef.current;
            pendingTurnRef.current = null;
            resolve(true);
          }
        } else {
          const sseOk = await turnWait;
          gotFinalReply = Boolean(sseOk);
        }
        if (!gotFinalReply) {
          if (
            isSlotsLookup
            && allowSlotsReuse
            && (await tryShowCachedSlots({ refresh: true }) || applyBarSlotsFallback({ provisional: true }))
          ) {
            gotFinalReply = true;
          } else {
            push([
              {
                from: "clara",
                text: instantText ? CHAT_SSE_TIMEOUT_FALLBACK : CHAT_UNCLEAR_FALLBACK,
              },
            ]);
          }
        }
      } catch {
        if (pendingTurnRef.current) {
          pendingTurnRef.current = null;
        }
        if (!gotFinalReply) {
          push([{ from: "clara", text: "Impossible de contacter l'agent pour le moment. Merci de reessayer." }]);
        }
      } finally {
        timers.forEach((id) => window.clearTimeout(id));
      }
    };

    if (isGreetingOnly(clean)) {
      void syncChatInBackground(INSTANT_GREETING_REPLY);
      return;
    }

    if (CANCEL_INTENT.test(clean)) {
      push([{ from: "clara", text: "J'ouvre le parcours d'annulation pour vous." }]);
      openActionFlowRef.current?.("cancel");
      return;
    }

    if (RESCHEDULE_INTENT.test(clean)) {
      push([{ from: "clara", text: "J'ouvre le parcours de modification pour vous." }]);
      openActionFlowRef.current?.("reschedule");
      return;
    }

    if (CALLBACK_INTENT.test(clean)) {
      push([{ from: "clara", text: "Pour etre rappele, vous devez etre deja enregistre comme patient du cabinet. Je vous propose de vous identifier." }]);
      openActionFlowRef.current?.("callback");
      return;
    }

    if (BOOKING_START.test(clean)) {
      const lookupMsg = BOOKING_DATE_HINT.test(clean) ? INSTANT_SLOTS_DATE_LOOKUP : INSTANT_SLOTS_LOOKUP;
      void syncChatInBackground(lookupMsg);
      return;
    }

    if (MORE_SLOTS_REQUEST.test(clean) || clean === MORE_SLOTS_MSG) {
      // UX: éviter de garder quelques secondes les anciens créneaux affichés.
      removeLastSlotsMessage();
      // Ne pas réafficher le cache barre ici: on veut de nouveaux créneaux côté moteur.
      void syncChatInBackground(INSTANT_MORE_SLOTS_LOOKUP, { allowSlotsReuse: false });
      return;
    }

    const offers = lastSlotOffers();
    const slotPick = clean.match(/^(?:oui\s*)?([123])$/iu);
    if (offers.length && slotPick) {
      const idx = Number(slotPick[1]);
      const offer = offers.find((o) => Number(o.index) === idx) || offers[idx - 1];
      if (offer) {
        setBookingSuccess(null);
        chooseSlot(resolveChatSlotOffer(offer, slots));
        return;
      }
    }

    void syncChatInBackground(CHAT_PROCESSING_REPLY);
  }, [chooseSlot, ensureConversationId, ensureStream, lastSlotOffers, push, pushSlotProposal, removeLastSlotsMessage, slug, waitForAgentTurn]);

  const pickChatSlot = useCallback(
    (offer) => {
      setBookingSuccess(null);
      chooseSlot(resolveChatSlotOffer(offer, slots));
    },
    [chooseSlot, slots]
  );

  const loadMoreChatSlots = useCallback(() => {
    void sendChatMessage(MORE_SLOTS_MSG);
  }, [sendChatMessage]);

  const ask = useCallback((text) => {
    void sendChatMessage(text);
  }, [sendChatMessage]);

  const confirm = useCallback(async (booking) => {
    const payload = {
      slug,
      ...(tenantIdRef.current ? { tenant_id: tenantIdRef.current } : {}),
      slotId: String(booking.slot.id || booking.slot.index || "1"),
      slotLabel: booking.slot.label,
      motif: booking.motif,
      patientName: booking.name,
      patientPhone: booking.phone,
      ...(booking.email ? { patientEmail: booking.email } : {}),
      source: modalSlot ? "google_slot" : "page_publique",
      slotSource: booking.slot.source || (booking.slot.startIso ? "google" : "sqlite"),
      startIso: booking.slot.startIso || "",
      endIso: booking.slot.endIso || "",
    };
    let responseData = null;
    let confirmed = false;
    setBookingSubmitting(true);
    try {
      responseData = await fetchJson("/api/public/book", { method: "POST", body: JSON.stringify(payload) });
      confirmed = Boolean(responseData?.confirmed || responseData?.status === "confirmed");
    } catch (err) {
      setBookingSubmitting(false);
      setBookingSuccess(null);
      const msg = String(err?.message || "");
      if (msg.includes("409") || msg.toLowerCase().includes("plus disponible")) {
        push([{ from: "clara", text: "Ce creneau vient d'etre pris. Choisissez un autre horaire, je vous en propose d'autres." }]);
        setInlineSlot(null);
        setModalSlot(null);
        setBookingDone(false);
        return;
      }
      if (msg.includes("422") || msg.toLowerCase().includes("invalide")) {
        push([{ from: "clara", text: "Telephone ou email invalide. Corrigez le formulaire puis reessayez." }]);
        return;
      }
      if (msg.includes("503") || msg.includes("502") || msg.toLowerCase().includes("confirmer ce creneau") || msg.toLowerCase().includes("enregistrement")) {
        const errText = msg.replace(/^HTTP \d+:\s*/i, "").trim();
        push([
          {
            from: "clara",
            text: msg.includes("503")
              ? "Le serveur n'a pas pu confirmer votre rendez-vous. Reessayez dans un instant."
              : errText || "Impossible de confirmer ce creneau. Choisissez un autre horaire.",
          },
        ]);
        return;
      }
      push([{ from: "clara", text: "La reservation n'a pas abouti. Verifiez vos informations et reessayez, ou choisissez un autre creneau." }]);
      return;
    }
    if (!responseData?.confirmationId) {
      setBookingSubmitting(false);
      push([{ from: "clara", text: "La reservation n'a pas pu etre enregistree. Reessayez dans un instant." }]);
      return;
    }
    setBookingSubmitting(false);
    const successText = confirmed
      ? `Parfait, votre rendez-vous pour ${booking.slot.label} est confirme. A bientot au cabinet.`
      : `Merci. Votre demande pour ${booking.slot.label} est enregistree. Le cabinet confirmera dans les meilleurs delais.`;
    const bookingCode = responseData?.bookingCode || "";
    setInlineSlot(null);
    setBookingDone(true);
    setPostBookingChatOpen(false);
    setBookingSuccess({
      label: booking.slot.label,
      message: successText,
      confirmed,
      confirmationId: responseData?.confirmationId,
      bookingCode,
      startIso: booking.slot.startIso || payload.startIso || "",
      endIso: booking.slot.endIso || payload.endIso || "",
      motif: booking.motif || "Consultation",
    });
    const codeHint = bookingCode ? ` Votre code rendez-vous : ${bookingCode}. Conservez-le pour modifier ou annuler.` : "";
    push([{ from: "clara", text: `${successText}${codeHint}` }]);
    trackPublicEvent({
      slug,
      event: "booking_confirmed",
      source: payload.source,
      slotId: booking.slot.id,
      slotLabel: booking.slot.label,
      motif: booking.motif,
    });
    window.setTimeout(() => setModalSlot(null), modalSlot ? 1000 : 0);
  }, [modalSlot, push, slug]);

  const closeModal = useCallback(() => {
    const label = modalSlot?.label;
    setModalSlot(null);
    setBookingDone(false);
    if (label) push([{ from: "clara", text: `Aucun souci. Le creneau ${label} reste disponible. Vous pouvez le reprendre ou choisir un autre horaire.` }]);
    if (label) {
      trackPublicEvent({
        slug,
        event: "modal_closed_without_confirm",
        source: sourceRef.current,
        slotLabel: label,
      });
    }
  }, [modalSlot, push, slug]);

  const send = useCallback(() => {
    const text = input.trim();
    if (!text) return;
    setInput("");
    void sendChatMessage(text);
  }, [input, sendChatMessage]);

  const openActionFlow = useCallback(
    (mode, bookingCode = "") => {
      const code = String(bookingCode || bookingSuccess?.bookingCode || "").trim().toUpperCase();
      setActionFlowInitialCode(code);
      setActionFlowMode(mode);
      trackPublicEvent({ slug, event: "manage_modal_opened", source: sourceRef.current, action: mode });
    },
    [bookingSuccess, slug],
  );
  openActionFlowRef.current = openActionFlow;

  const handlePostBookingDocuments = useCallback(() => {
    // Évite que la réponse chat soit masquée par une modale encore affichée.
    setModalSlot(null);
    setBookingDone(false);
    setActionFlowMode(null);
    setActionFlowInitialCode("");
    const text =
      practitioner.documents ||
      "Carte Vitale, piece d'identite, ordonnances et examens recents si besoin.";
    push([{ from: "clara", text: `Documents utiles : ${text}` }]);
    setPostBookingChatOpen(true);
  }, [practitioner.documents, push]);

  const handlePostBookingAddress = useCallback(() => {
    // Évite que la réponse chat soit masquée par une modale encore affichée.
    setModalSlot(null);
    setBookingDone(false);
    setActionFlowMode(null);
    setActionFlowInitialCode("");
    const text = addr(practitioner) || "Adresse communiquee par le cabinet.";
    const access = [practitioner.access, practitioner.parking].filter(Boolean).join(" — ");
    push([
      {
        from: "clara",
        text: access ? `${text}. Acces : ${access}.` : text,
      },
    ]);
    setPostBookingChatOpen(true);
  }, [practitioner, push]);

  const refreshPublicSlots = useCallback(async () => {
    try {
      const data = await fetchJson(`/api/public/slots/${encodeURIComponent(slug)}?count=8`);
      const next = filterFuturePublicSlots(safeArray(data?.slots));
      if (next.length) {
        setSlots(next);
        setSlotsMeta({ source: data?.source || null, calendar: data?.calendar || null });
      }
      return next;
    } catch {
      return filterFuturePublicSlots(safeArray(slots));
    }
  }, [slug, slots]);

  const handlePostBookingAskAnother = useCallback(() => {
    // Retourne à la landing (sans modale ni état "succès" bloquant), puis rouvre le chat normal.
    setModalSlot(null);
    setBookingDone(false);
    setBookingSuccess(null);
    setActionFlowMode(null);
    setActionFlowInitialCode("");
    setPostBookingChatOpen(true);
    void refreshPublicSlots();
    push([
      {
        from: "clara",
        text: "Je suis la pour vos autres questions : documents, acces, horaires, tarifs…",
      },
    ]);
  }, [push, refreshPublicSlots]);

  const mainChips = [
    { label: "Prendre RDV", text: "Je souhaite prendre rendez-vous.", action: "book" },
    { label: "Modifier", action: "reschedule" },
    { label: "Annuler", action: "cancel" },
    { label: "Etre rappele", action: "callback" },
  ];
  const visibleSlots = showAllSlots ? slots : slots.slice(0, 6);

  const stopVoiceCall = useCallback(async () => {
    const vapi = vapiRef.current;
    if (!vapi || typeof vapi.stop !== "function") return;
    try {
      await vapi.stop();
    } catch {
      // no-op
    }
    setVoiceStatus("idle");
    trackPublicEvent({
      slug,
      event: "voice_ended",
      source: sourceRef.current,
    });
  }, [slug]);

  const startVoiceCall = useCallback(async () => {
    if (!voiceReady) {
      setVoiceError("L'appel vocal n'est pas configure pour ce praticien.");
      return;
    }
    if (voiceStatus === "connecting" || voiceStatus === "active") return;
    setVoiceError("");
    setVoiceStatus("connecting");
    try {
      const { default: Vapi } = await import("@vapi-ai/web");
      let vapi = vapiRef.current;
      if (!vapi) {
        vapi = new Vapi(vapiPublicKey);
        vapi.on?.("call-start", () => setVoiceStatus("active"));
        vapi.on?.("call-end", () => setVoiceStatus("idle"));
        vapi.on?.("error", (error) => {
          setVoiceStatus("error");
          setVoiceError(error?.message || "Erreur audio");
        });
        vapiRef.current = vapi;
      }
      await vapi.start(practitioner.vapiAssistantId);
      trackPublicEvent({
        slug,
        event: "voice_started",
        source: sourceRef.current,
      });
    } catch (error) {
      setVoiceStatus("error");
      setVoiceError(error?.message || "Impossible de demarrer l'appel vocal.");
    }
  }, [practitioner.vapiAssistantId, slug, vapiPublicKey, voiceReady, voiceStatus]);

  useEffect(() => () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    if (vapiRef.current && typeof vapiRef.current.stop === "function") {
      vapiRef.current.stop().catch?.(() => {});
    }
  }, []);

  if (dataStatus === "not_found") {
    return (
      <main>
        <style>{css}</style>
        <div className="notFoundShell">
          <div className="notFoundCard">
            <h1>Praticien introuvable</h1>
            <p>Cette page publique n'est plus disponible ou l'URL est incorrecte.</p>
            <a href="https://www.uwiapp.com" className="notFoundCta">Retour a l'accueil UWI</a>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main>
      <style>{css}</style>
      <SeoManager practitioner={practitioner} openingHours={openingHours} faqs={faqs} slots={slots} />
      {modalSlot && (
        <SupervisedModal
          slot={modalSlot}
          slug={slug}
          onClose={closeModal}
          onConfirm={confirm}
          done={bookingDone}
          onAskClara={handlePostBookingAskAnother}
        />
      )}
      {actionFlowMode ? (
        <PublicAppointmentActionModal
          mode={actionFlowMode}
          slug={slug}
          initialBookingCode={actionFlowInitialCode}
          onClose={() => {
            setActionFlowMode(null);
            setActionFlowInitialCode("");
          }}
          push={push}
          slots={slots}
          onRefreshSlots={refreshPublicSlots}
        />
      ) : null}
      <div className="pageShell">
        <header>
          <strong>UWI</strong>
          <UwiSearchBar
            data={searchData}
            onSearchUsed={(query, resultsCount) => {
              trackPublicEvent({
                slug,
                event: "search_used",
                source: sourceRef.current,
                query,
                resultsCount,
              });
            }}
          />
          <nav>
            <a href={telHref(practitioner)}>Appeler</a>
            {practitioner.whatsappEnabled && (
              <a
                className="wa"
                href={practitioner.whatsappUrl}
                onClick={() =>
                  trackPublicEvent({
                    slug,
                    event: "whatsapp_clicked",
                    source: sourceRef.current,
                  })
                }
              >
                WhatsApp
              </a>
            )}
          </nav>
        </header>
        {dataStatus === "fallback" && <div className="demoNotice">Mode demo : les donnees publiques API ne sont pas encore disponibles.</div>}

        <div className="doctorMini">
          <div className={practitioner.photoUrl ? "avatar avatarPhoto" : "avatar"}>
            {practitioner.photoUrl ? <img src={practitioner.photoUrl} alt={practitioner.name} onError={(event) => { event.currentTarget.style.display = "none"; }} /> : practitioner.initials}
          </div>
          <div className="doctorMiniText">
            <h1>{practitioner.name}</h1>
            <p>{practitioner.specialty} a {practitioner.city}<span className="dotSep">-</span><span className="greenDot" />Page verifiee<span className="dotSep">-</span><span className="star">★</span> {practitioner.rating}</p>
            <p className="micro">📍 {addr(practitioner)} - Carte Vitale acceptee - Nouveaux patients : {String(practitioner.newPatients).toLowerCase()}</p>
          </div>
          <div className="trustBadges">
            <div className="trustBadge"><span>✓</span><span>Praticien verifie</span></div>
            <div className="trustBadge"><span>🗓</span><span>Prise de RDV rapide</span></div>
            <div className="trustBadge"><span>🔒</span><span>Donnees securisees</span></div>
          </div>
        </div>

        <section className="mainCard">
          <p className="chatSectionLead">Prendre rendez-vous en quelques secondes</p>
          <section
            className={`chatHero${hideChatComposer ? " chatHeroBookingFocus" : ""}${postBookingMode ? " chatHeroPostBooking" : ""}`}
            ref={chatHeroRef}
            aria-busy={hideChatComposer}
          >
            <div className="chatHeader">
              <ClaraPortrait size={54} />
              <div className="chatHeaderText">
                <div className="chatHeaderName">Clara <span>- En ligne</span></div>
                <p className="chatHelperBubble">Je peux vous aider pour la prise de RDV, l'annulation, la modification et vos questions pratiques.</p>
              </div>
              {(voiceReady || voiceStatus !== "idle") && (
                <div className="voiceControls">
                  <button
                    className={voiceStatus === "active" ? "voiceBtn voiceBtnStop" : "voiceBtn"}
                    type="button"
                    onClick={voiceStatus === "active" ? stopVoiceCall : startVoiceCall}
                    disabled={voiceStatus === "connecting"}
                  >
                    {voiceStatus === "active" ? "Arreter l'appel" : voiceStatus === "connecting" ? "Connexion..." : "Parler avec Clara"}
                  </button>
                  {voiceError && <span className="voiceError">{voiceError}</span>}
                </div>
              )}
              <div className="chatHeaderBadge">Reponse 24/7</div>
            </div>

            {!inlineSlot && (!postBookingMode || postBookingChatOpen) && slots.length > 0 ? (
              <div className="slotsStrip" aria-label="Creneaux disponibles">
                <p className="slotsStripLabel">
                  <span className="slotDot" />
                  Reserver en un clic
                  {slotsRefreshing ? (
                    <span className="slotsStripRefresh" title="Mise a jour des creneaux" aria-hidden="true">
                      ↻
                    </span>
                  ) : null}
                </p>
                <div className="slotsStripScroll">
                  {slotsLoading
                    ? Array.from({ length: 4 }).map((_, idx) => (
                        <div key={`sk-${idx}`} className="slotChip slotChipSkeleton" aria-hidden="true" />
                      ))
                    : visibleSlots.map((slot) => (
                        <button
                          key={slot.id}
                          className="slotChip"
                          disabled={slotsRefreshing || (slotsMeta.source === "agenda" && !slot.startIso)}
                          onClick={() => chooseSlot(slot)}
                          type="button"
                        >
                          <span className="slotChipDay">{slot.day}</span>
                          <span className="slotChipTime">{slot.time}</span>
                        </button>
                      ))}
                </div>
                {!showAllSlots && slots.length > 6 ? (
                  <button className="slotsStripMore" onClick={() => setShowAllSlots(true)} type="button" title="Voir plus de creneaux">
                    +
                  </button>
                ) : null}
                <button className="slotsStripAlt" onClick={() => ask("Je souhaite voir plus de creneaux.")} type="button" title="Autre horaire">
                  🗓
                </button>
              </div>
            ) : null}

            <div className="chatScroll" ref={threadRef} aria-live="polite" aria-relevant="additions">
              <div className="chatScrollInner">
                {messages.map((message) => (
                  <div key={message.id} className={message.from === "patient" ? "chatLine patientLine" : "chatLine assistantLine"}>
                    {message.from !== "patient" && <ClaraPortrait size={34} compact />}
                    <div className={message.from === "patient" ? "bubble patientBubble" : "bubble claraBubble"}>
                      {message.text}
                      {safeArray(message.slots).length ? (
                        <div className="chatSlotChoices">
                          <span className="chatSlotHint">Creneaux issus de l&apos;agenda du cabinet — confirmation immediate apres vos coordonnees.</span>
                          {message.slots.map((offer) => (
                            <button
                              key={`${message.id}-slot-${offer.index}`}
                              className="chatSlotBtn"
                              type="button"
                              disabled={postBookingLocked}
                              onClick={() => !postBookingLocked && pickChatSlot(offer)}
                            >
                              <span className="chatSlotBtnNum">{offer.index}</span>
                              <span className="chatSlotBtnLabel">{offer.label}</span>
                            </button>
                          ))}
                          {message.id === lastSlotsMessageId && !postBookingLocked && !message.provisional ? (
                            <button
                              className="chatSlotMoreBtn"
                              type="button"
                              onClick={loadMoreChatSlots}
                            >
                              Voir d&apos;autres créneaux
                            </button>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  </div>
                ))}
                {bookingSuccess ? (
                  <BookingSuccessCard
                    success={bookingSuccess}
                    cabinetName={practitioner.name}
                    location={addr(practitioner)}
                    onModify={() => openActionFlow("reschedule", bookingSuccess.bookingCode)}
                    onCancel={() => openActionFlow("cancel", bookingSuccess.bookingCode)}
                    onDocuments={handlePostBookingDocuments}
                    onAddress={handlePostBookingAddress}
                    onAskAnother={handlePostBookingAskAnother}
                  />
                ) : null}
                {inlineSlot ? (
                  <BookingFields
                    slot={inlineSlot}
                    slug={slug}
                    defaultName=""
                    submitting={bookingSubmitting}
                    onConfirm={confirm}
                    onCancel={() => {
                      setInlineSlot(null);
                      push([{ from: "clara", text: "Pas de probleme. Choisissez un autre creneau ou precisez votre preference." }]);
                    }}
                  />
                ) : null}
              </div>
            </div>

            {!hideChatComposer ? (
              <div className="chatComposerBar">
                <div className="composerInputWrap">
                  <span className="composerInputIcon">☺</span>
                  <input
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    onKeyDown={(event) => event.key === "Enter" && send()}
                    placeholder={inputExamples[placeholderIdx]}
                    aria-label="Message a Clara"
                  />
                </div>
                <button className="composerSendBtn" onClick={send} type="button">
                  Envoyer
                </button>
              </div>
            ) : null}
          </section>

          {!hideChatComposer ? (
          <div className="actionRows">
            <div className="actionRow">
              <span className="actionLabel">Actions rapides</span>
              <div className="softChips">{mainChips.map((chip) => (
                <button
                  key={chip.label}
                  type="button"
                  onClick={() => (chip.action === "book" ? ask(chip.text) : openActionFlow(chip.action))}
                >
                  {chip.label}
                </button>
              ))}</div>
            </div>
            <div className="actionRow">
              <span className="actionLabel">Questions frequentes</span>
              <div className="faqLinks">{faqs.map((faq) => <button key={faq.id} onClick={() => { ask(faq.q); trackPublicEvent({ slug, event: "faq_clicked", source: sourceRef.current, question: faq.q }); }} type="button">{faq.q}</button>)}</div>
            </div>
          </div>
          ) : null}
          <div className="urgencyNote">⚠️ Urgence medicale : appelez le <strong>15</strong> ou le <strong>112</strong>. N'utilisez pas ce chat.</div>
        </section>

        <section className="infoSeo">
          <div className="infoCard">
            <h2>Informations pratiques</h2>
            <div className="infoGrid">
              <p><b>Adresse</b><span>{addr(practitioner)}</span></p>
              <p><b>Tarif</b><span>{practitioner.fee}</span></p>
              <p><b>Langues</b><span>{safeArray(practitioner.languages).join(", ")}</span></p>
              <p><b>Acces</b><span>{practitioner.access}</span></p>
              <p><b>Carte Vitale</b><span>{practitioner.carteVitale ? "Acceptee" : "Non precise"}</span></p>
              <p><b>Documents</b><span>{practitioner.documents}</span></p>
              <p><b>Telephone</b><span>{practitioner.phone}</span></p>
              <p><b>Acces PMR</b><span>{practitioner.pmr ? "Oui" : "Non precise"}</span></p>
            </div>
          </div>
          <div className="infoCard hoursCard">
            <h2>Horaires</h2>
            {openingHours.map((h) => <p key={h.day}><span>{h.day}</span><b>{h.opens ? `${h.opens} - ${h.closes}` : "Ferme"}</b></p>)}
          </div>
        </section>
        <footer>UWI - Accueil patient augmente - <a href="https://uwiapp.com">uwiapp.com</a></footer>
      </div>
      <button
        type="button"
        className={`mobileStickyCta${composerOutOfView && !hideChatComposer ? " show" : ""}`}
        onClick={scrollToComposer}
        aria-hidden={!composerOutOfView || hideChatComposer}
      >
        <span className="mobileStickyCtaIcon" aria-hidden="true">📅</span>
        Reserver un creneau
      </button>
    </main>
  );
}

const css = `
*{box-sizing:border-box}
body{margin:0;background:#e8eef0;color:#111;font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif}
button,a,input{font:inherit}button{cursor:pointer}
.notFoundShell{min-height:100vh;display:grid;place-items:center;padding:24px;background:#e8eef0}
.notFoundCard{width:min(620px,100%);background:#fff;border:1px solid #e5eded;border-radius:20px;box-shadow:0 18px 55px rgba(12,45,51,.10);padding:28px;text-align:center}
.notFoundCard h1{margin:0 0 10px;font-size:30px;letter-spacing:-.03em;color:#16343b}
.notFoundCard p{margin:0 0 18px;color:#4c6470}
.notFoundCta{display:inline-block;text-decoration:none;color:#fff;background:#009CA4;border:0;border-radius:12px;padding:10px 16px;font-size:14px;font-weight:800}
.pageShell{max-width:1180px;margin:18px auto 34px;background:#fff;border:1px solid #e5eded;border-radius:28px;box-shadow:0 18px 55px rgba(12,45,51,.10);padding:26px;display:flex;flex-direction:column;gap:0}
.pageShell > .doctorMini{margin-bottom:0}
header{min-height:54px;display:grid;grid-template-columns:auto minmax(260px,1fr) auto;align-items:center;gap:20px;margin-bottom:8px}
header strong{font-size:34px;letter-spacing:-.06em;color:#008996;font-weight:950}
header nav{display:flex;gap:14px;justify-content:flex-end}
header a{text-decoration:none;color:#187683;border:1px solid #d6e5e8;background:#fff;border-radius:12px;padding:10px 18px;font-size:14px;font-weight:800}
header a.wa{color:#1b6d34;border-color:#cce9d2}
.demoNotice{margin:8px 0 14px;padding:10px 14px;border:1px solid #ffe2a8;background:#fff8e6;border-radius:12px;color:#7a5300;font-size:13px;font-weight:700}
.uwiSearch{position:relative;display:flex;align-items:center;gap:9px;background:#f8fbfb;border:1.5px solid #dce9eb;border-radius:13px;padding:0 12px;height:44px}
.uwiSearch:focus-within{background:#fff;border-color:#009CA4;box-shadow:0 0 0 3px rgba(0,156,164,.1)}
.uwiSearchIcon{color:#009CA4;font-size:19px}.uwiSearch input{flex:1;border:0;outline:0;background:transparent;color:#20363c;font-size:13px}
.uwiSearchClear{width:22px;height:22px;border:0;border-radius:50%;background:#e7f2f3;color:#60757b;font-weight:900}
.uwiDrop{position:absolute;left:0;right:0;top:52px;z-index:100;background:#fff;border:1px solid #dce9eb;border-radius:16px;box-shadow:0 20px 50px rgba(12,45,51,.15);padding:8px}
.uwiDropTitle{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#8a9ba1;font-weight:800;padding:5px 8px 8px}
.uwiResult{display:grid;grid-template-columns:36px 1fr auto;gap:10px;align-items:center;text-decoration:none;color:#1f3138;border-radius:12px;padding:9px 8px;transition:.12s}
.uwiResult:hover{background:#f0fbfb}.uwiResultBadge{width:36px;height:36px;border-radius:11px;background:linear-gradient(135deg,#e6f7f8,#fff);border:1px solid #cbe7eb;color:#008996;display:grid;place-items:center;font-weight:900}
.uwiResultInfo{display:flex;flex-direction:column;gap:1px;min-width:0}.uwiResultInfo strong{font-size:13px;color:#172b33}.uwiResultInfo span,.uwiResultInfo em{font-size:11px;color:#526777;font-style:normal}
.uwiResultTag{border:1px solid #e5eaec;border-radius:999px;padding:4px 8px;color:#798990;font-size:11px;font-weight:700;white-space:nowrap}.uwiResultTag.ok{border-color:#ccebd8;background:#f1fbf5;color:#207547}
.uwiDropEmpty{padding:14px;display:flex;flex-direction:column;gap:3px;color:#61727a;font-size:13px}
.mainCard{border:0;border-radius:0;padding:0 34px 18px;background:transparent;margin-top:0}
.chatSectionLead{margin:18px 0 10px;font-size:13px;font-weight:900;letter-spacing:.06em;text-transform:uppercase;color:#006e74}
.doctorMini{display:flex;align-items:center;gap:18px;padding:18px 34px 14px;border:1px solid #dce7ea;border-bottom:0;border-radius:22px 22px 0 0;background:#fafcfd}
.avatar{width:72px;height:72px;border-radius:50%;display:grid;place-items:center;background:linear-gradient(135deg,#009CA4,#008692);color:#fff;font-size:26px;font-weight:950;overflow:hidden;flex-shrink:0}
.avatarPhoto{background:#eef7f8;border:1px solid #d7e9ec}.avatarPhoto img{width:100%;height:100%;object-fit:cover;display:block}
.doctorMiniText{flex:1;min-width:0}.doctorMiniText h1{margin:0 0 4px;font-size:24px;letter-spacing:-.035em}.doctorMiniText p{margin:0 0 4px;color:#58627a;font-size:13px}.micro{font-size:12px!important;color:#7a8898!important}
.dotSep{color:#c7ced8;margin:0 5px}.greenDot{display:inline-block;width:10px;height:10px;border-radius:50%;background:#0dbb69;margin-right:5px}.star{color:#f6a800;margin-right:2px}
.trustBadges{display:flex;flex-direction:column;gap:5px;padding-left:16px;border-left:1px solid #edf0f2;flex-shrink:0}.trustBadge{display:flex;align-items:center;gap:6px;font-size:11px;color:#5a7a80;font-weight:700;white-space:nowrap}
.chatHero{border:2px solid #009CA4;background:linear-gradient(180deg,#e2f6f7 0%,#ffffff 38%);border-radius:24px;padding:0;display:flex;flex-direction:column;gap:0;margin-top:0;overflow:hidden;max-height:min(72vh,580px);box-shadow:0 22px 64px rgba(0,156,164,.20),0 8px 24px rgba(12,45,51,.08)}
.chatHero .chatHeader{padding:16px 18px 14px;margin:0}
.chatHeader{display:flex;align-items:center;gap:14px;padding-bottom:0;border-bottom:0;background:linear-gradient(135deg,#009CA4 0%,#00818a 100%);color:#fff}.chatHeaderText{flex:1;min-width:0}.chatHeaderName{font-weight:900;font-size:17px;color:#fff}.chatHeaderName span{color:#b8f5d0;font-size:13px;font-weight:800}.chatHeaderText p{margin:4px 0 0;color:rgba(255,255,255,.92);font-size:13px;line-height:1.45}.chatHelperBubble{margin:0}.chatHeaderBadge{border:1px solid rgba(255,255,255,.45);background:rgba(255,255,255,.16);color:#fff;border-radius:999px;padding:7px 12px;font-size:12px;font-weight:800;backdrop-filter:blur(4px)}
.voiceControls{display:flex;flex-direction:column;align-items:flex-end;gap:4px}.voiceBtn{border:1px solid rgba(255,255,255,.55);background:rgba(255,255,255,.18);color:#fff;border-radius:999px;padding:8px 12px;font-size:12px;font-weight:800}.voiceBtn:hover{background:rgba(255,255,255,.28)}.voiceBtn:disabled{opacity:.5;cursor:not-allowed}.voiceBtnStop{border-color:#ffd0d0;color:#fff;background:rgba(180,30,30,.35)}.voiceError{max-width:220px;text-align:right;font-size:11px;color:#ffe0e0}
.claraPhoto{position:relative;flex-shrink:0;border-radius:50%;overflow:hidden;background:#fff;border:2px solid rgba(255,255,255,.85);box-shadow:0 8px 20px rgba(0,0,0,.18)}.claraPhoto img{width:100%;height:100%;display:block;object-fit:cover;object-position:center 22%}.claraOnlineDot{position:absolute;right:1px;bottom:1px;width:10px;height:10px;border-radius:50%;background:#22b04d;border:2px solid #fff;z-index:2}.claraFallback{width:100%;height:100%;background:linear-gradient(135deg,#009CA4,#006f75);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:900;font-size:22px}
.slotsStrip{flex-shrink:0;display:flex;align-items:center;gap:8px;padding:10px 14px;background:rgba(255,255,255,.88);border-top:1px solid rgba(0,156,164,.12);border-bottom:1px solid rgba(0,156,164,.12)}
.slotsStripLabel{margin:0;display:flex;align-items:center;gap:6px;font-size:11px;font-weight:900;letter-spacing:.07em;color:#006e74;white-space:nowrap}
.slotsStripRefresh{display:inline-flex;font-size:12px;color:#009CA4;animation:uwiSpin 1s linear infinite;opacity:.85}
@keyframes uwiSpin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
.slotsStripScroll{display:flex;gap:7px;overflow-x:auto;flex:1;min-width:0;padding-bottom:2px;scrollbar-width:thin}
.slotChip{flex-shrink:0;min-width:88px;border:1px solid rgba(0,156,164,.22);background:#fff;border-radius:12px;padding:8px 10px;display:flex;flex-direction:column;align-items:center;gap:2px}
.slotChipDay{font-size:10px;font-weight:700;color:#7a9499}.slotChipTime{font-size:16px;font-weight:900;color:#006b73;line-height:1.1}
.slotChipSkeleton{min-height:52px;background:linear-gradient(90deg,#e6eff0 0%,#f4fafa 50%,#e6eff0 100%);background-size:300px 100%;animation:uwiSkShimmer 1.2s infinite linear}
.slotsStripMore,.slotsStripAlt{flex-shrink:0;width:36px;height:36px;border-radius:10px;border:1px solid rgba(0,156,164,.25);background:#fff;color:#006b73;font-size:16px;font-weight:900}
.chatScroll{flex:1;min-height:140px;overflow-y:auto;background:#fff;border-top:1px solid #e3ecef;border-bottom:1px solid #e3ecef;scroll-behavior:smooth}
.chatScrollInner{display:flex;flex-direction:column;justify-content:flex-end;gap:12px;min-height:100%;padding:14px 16px}
.chatHero.chatHeroBookingFocus .chatScroll{border-bottom:none;border-radius:0 0 20px 20px}
.chatHero.chatHeroBookingFocus .inlineCard{margin-bottom:4px}
.chatComposerBar{flex-shrink:0;display:grid;grid-template-columns:1fr 140px;gap:10px;align-items:center;padding:14px 16px;background:#f7fcfc;border-top:1px solid rgba(0,156,164,.10);border-radius:0 0 22px 22px}
.chatComposerBar .composerInputWrap{min-height:52px;border-width:2px}
.chatComposerBar .composerSendBtn{height:52px;font-size:15px;box-shadow:0 8px 22px rgba(0,156,164,.32)}
.chatLine{display:flex;align-items:flex-start;gap:10px}.assistantLine{justify-content:flex-start}.patientLine{justify-content:flex-end}.bubble{font-size:14px;line-height:1.55;border-radius:14px;padding:12px 16px;max-width:80%}.claraBubble{background:#009CA4;color:#fff;border-bottom-left-radius:3px}.patientBubble{background:#f4f6f6;border:1px solid #e3e7e8;color:#2f3c42;border-bottom-right-radius:3px}
.chatSlotChoices{display:flex;flex-direction:column;gap:8px;margin-top:10px}
.chatSlotHint{font-size:12px;opacity:.92;margin-bottom:2px}
.chatSlotBtn{display:flex;align-items:center;gap:10px;width:100%;text-align:left;border:1px solid rgba(255,255,255,.45);background:rgba(255,255,255,.14);color:#fff;border-radius:10px;padding:10px 12px;cursor:pointer;font-size:13px}
.chatSlotBtn:hover{background:rgba(255,255,255,.24)}
.chatSlotBtnNum{flex-shrink:0;width:26px;height:26px;border-radius:8px;background:#fff;color:#006b73;font-weight:900;display:flex;align-items:center;justify-content:center;font-size:13px}
.chatSlotBtnLabel{line-height:1.35}
.chatSlotMoreBtn{margin-top:4px;width:100%;text-align:center;border:1px dashed rgba(255,255,255,.55);background:transparent;color:#fff;border-radius:10px;padding:9px 12px;cursor:pointer;font-size:12px;font-weight:700;letter-spacing:.02em}
.chatSlotMoreBtn:hover{background:rgba(255,255,255,.12);border-style:solid}
.bookingSuccessCard{text-align:center;background:#e8f8f9;border:2px solid #009CA4;color:#0a4a50;margin-top:8px}
.bookingSuccessIcon{font-size:28px;color:#009CA4;margin-bottom:6px}
.bookingSuccessSlot{display:block;margin-top:8px;font-size:13px;opacity:.85}
.bookingSuccessCode{margin:10px 0 0;font-size:14px}
.bookingSuccessCode strong{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.06em}
.bookingSuccessActions{margin-top:16px;display:flex;flex-direction:column;gap:8px;width:100%;text-align:left}
.bookingSuccessActionRow{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.bookingSuccessCopyBtn,.bookingSuccessActionBtn{width:100%;border:1px solid #009CA4;background:#fff;color:#006b73;border-radius:12px;padding:11px 14px;font-size:14px;font-weight:800}
.bookingSuccessActionBtnSoft{border-color:#c5e3e6;background:#f8fdfd;font-weight:700}
.bookingSuccessCopyBtn:hover,.bookingSuccessActionBtn:hover{background:#f0fbfc}
.bookingSuccessWaBtn{display:block;width:100%;border:none;cursor:pointer;text-align:center;text-decoration:none;color:#fff;background:#25D366;border-radius:12px;padding:11px 14px;font-size:14px;font-weight:800}
.chatHeroPostBooking .chatScroll{opacity:.92}
.chatSlotBtn:disabled{opacity:.45;cursor:not-allowed}
.actionModalHint{margin:0;font-size:13px;color:#5f7375;line-height:1.45}
.actionApptPick{display:flex;flex-direction:column;align-items:flex-start;gap:4px;width:100%;text-align:left;border:1px solid #d6eeee;background:#f8fbfb;border-radius:12px;padding:12px 14px;color:#1f3138}
.actionApptPick strong{font-size:14px;color:#0a4a50}.actionApptPick span{font-size:12px;color:#60757b}
.actionApptPick:hover{border-color:#009CA4;background:#eefafa}
.actionSlotGrid{display:flex;flex-wrap:wrap;gap:8px}
.actionSlotPick{border:1px solid #cfe7ea;background:#fff;border-radius:10px;padding:8px 12px;font-size:12px;font-weight:700;color:#006b73}
.actionSlotPick.active{background:#e8f8f9;border-color:#009CA4;color:#004950}
.actionReasonSelect,.actionMessageArea{border:1.5px solid #e0e5e6;background:#f8fafa;border-radius:10px;padding:10px 12px;width:100%;font-size:14px}
.actionMessageArea{resize:vertical;min-height:72px}
.inlineOneCol{display:flex;flex-direction:column;gap:8px}
.inlineEmailField{border:1.5px solid #e0e5e6;background:#f8fafa;border-radius:10px;padding:10px 12px;outline:none;width:100%;font-size:14px}
.inlineEmailField:focus{border-color:#009CA4;background:#fff}
.fieldWrap{display:flex;flex-direction:column;gap:4px;min-width:0}
.fieldError{margin:0;font-size:11px;color:#c0392b;font-weight:600}
.inputInvalid{border-color:#e74c3c !important;background:#fff8f8 !important}
.inlineKnownHint{margin:0;font-size:12px;color:#006e74;font-weight:700;background:#e8f9f9;border-radius:8px;padding:8px 10px}
.inlineNameRecap{margin:0;padding:10px 12px;background:rgba(0,156,164,.08);border-radius:8px;font-size:14px}
.partialBubble{opacity:.72;font-style:italic}
@keyframes uwiSkShimmer{0%{background-position:-160px 0}100%{background-position:160px 0}}
.composerSlotSkeleton{cursor:default;border-color:#e0eef0;background:rgba(255,255,255,.9);pointer-events:none}
.composerSlotSkeleton:hover{transform:none;box-shadow:none;border-color:#e0eef0;background:rgba(255,255,255,.9)}
.sk{display:inline-block;border-radius:6px;background:linear-gradient(90deg,#e6eff0 0%,#f4fafa 50%,#e6eff0 100%);background-size:300px 100%;animation:uwiSkShimmer 1.2s infinite linear;height:11px;width:60%}
.sk-lg{height:18px;width:72%;border-radius:7px}
.mobileStickyCta{display:none}
.composerIntegrated{margin-top:4px;border:2.5px solid #009CA4;border-radius:26px;background:#e4f4f4;padding:18px 20px 18px;box-shadow:inset 0 1px 0 rgba(255,255,255,.55),0 14px 32px rgba(0,156,164,.14)}
.composerTop{display:flex;flex-direction:column;gap:10px}.composerTitle{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.slotDot{width:10px;height:10px;border-radius:50%;background:#22c66a;box-shadow:0 0 0 4px rgba(34,198,106,.14);flex-shrink:0}.composerTitleMain{font-size:12px;font-weight:900;letter-spacing:.1em;color:#52727a}.composerTitleSub{font-size:11px;color:#8aa9ad;font-weight:700}
.composerSlotsGrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(96px,1fr));gap:7px}.composerSlotBtn{min-height:74px;border-radius:14px;border:1px solid rgba(0,156,164,.18);background:rgba(255,255,255,.5);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;padding:8px 6px;transition:all .15s ease;overflow:hidden;backdrop-filter:saturate(140%)}.composerSlotBtn:hover{border-color:rgba(0,156,164,.55);background:rgba(255,255,255,.85);box-shadow:0 4px 12px rgba(0,156,164,.10)}.composerSlotBtn span{display:block;width:100%;text-align:center;white-space:nowrap}.composerSlotDay{font-size:clamp(11px,1.4vw,13px);font-weight:700;color:#7a9499;line-height:1;letter-spacing:.02em;text-transform:none}.composerSlotTime{font-size:clamp(20px,2.6vw,24px);font-weight:900;color:#006b73;line-height:1.1;letter-spacing:-.02em}
.composerTopActions{display:flex;align-items:center;justify-content:center;gap:10px;flex-wrap:wrap;margin-top:2px}.composerMoreLink{border:0;background:transparent;color:#007f89;font-size:12px;font-weight:800;text-decoration:underline;padding:0}.composerAltCta{border:1.5px solid rgba(0,156,164,.28);background:rgba(255,255,255,.45);color:#006e74;border-radius:999px;padding:8px 16px;font-size:13px;font-weight:700;white-space:nowrap}.composerAltCta:hover{background:rgba(255,255,255,.75);border-color:rgba(0,156,164,.5)}
.mobileClaraHint{display:none}
.composerDivider{height:1px;background:rgba(0,156,164,.18);margin:14px 0 14px;border-radius:1px}.composerBottom{display:grid;grid-template-columns:1fr 180px;gap:14px;align-items:center}.composerInputWrap{min-height:72px;display:flex;align-items:center;gap:14px;border-radius:18px;border:2px solid #c7dfe2;background:#fff;padding:0 20px;transition:border-color .15s ease,box-shadow .15s ease}.composerInputWrap:focus-within{border-color:#009CA4;box-shadow:0 0 0 4px rgba(0,156,164,.12)}.composerInputIcon{color:#009CA4;font-size:24px;flex-shrink:0}.composerInputWrap input{width:100%;border:0;outline:none;background:transparent;color:#406f73;font-size:16px;font-weight:600}.composerInputWrap input::placeholder{color:#9bb0b3;font-weight:500}.composerSendBtn{height:72px;border:0;border-radius:18px;background:#009CA4;color:#fff;font-size:17px;font-weight:800;letter-spacing:.01em;box-shadow:0 8px 22px rgba(0,156,164,.28);transition:transform .12s ease,box-shadow .12s ease}.composerSendBtn:hover:not(:disabled){transform:translateY(-1px);box-shadow:0 10px 26px rgba(0,156,164,.34)}.composerSendBtn:disabled{opacity:.55;cursor:not-allowed;box-shadow:none}
.inlineCard{background:#fff;border:1px solid #d5eeee;border-left:4px solid #009CA4;border-radius:14px;padding:14px 15px;display:flex;flex-direction:column;gap:9px}.inlineCardTop{display:flex;align-items:center;justify-content:space-between}.inlineCard b{font-size:13px}.inlineCard>span{font-size:11px;color:#888}.inlineClose{border:0;background:transparent;color:#007f89;font-size:11px;font-weight:700}.motifs{display:flex;flex-wrap:wrap;gap:7px}.motif{border:1px solid #dfe5e6;background:#f6f8f8;border-radius:999px;padding:7px 12px;font-size:12px;font-weight:600}.motif.active{background:#e8f9f9;border-color:#009CA4;color:#006e74}.inlineTwoCol{display:grid;grid-template-columns:1fr 1fr;gap:9px}.inlineTwoCol input,.inlineOneCol input,.modalBody input{border:1.5px solid #e0e5e6;background:#f8fafa;border-radius:10px;padding:10px 12px;outline:none;width:100%}.primary{border:0;background:#009CA4;color:#fff;border-radius:11px;padding:11px 16px;font-weight:700;box-shadow:0 5px 16px rgba(0,156,164,.22);width:100%}.primary:disabled{opacity:.4;cursor:not-allowed}
.actionRows{border:1px solid #e2e8eb;border-radius:16px;background:#f6f9fa;margin-top:14px;box-shadow:none}.actionRow{display:grid;grid-template-columns:150px 1fr;gap:14px;align-items:center;padding:10px 18px;border-top:1px solid #e8ecef}.actionLabel{font-weight:700;color:#6a7890;font-size:12px}.softChips,.faqLinks{display:flex;flex-wrap:wrap;gap:8px}.softChips button{border:1px solid #d8e4e6;background:#fff;border-radius:11px;padding:7px 12px;color:#4d8a94;font-size:12px;font-weight:700}.faqLinks button{border:0;background:transparent;color:#7a9aa0;font-size:12px;font-weight:700;text-decoration:underline;text-underline-offset:3px;padding:3px 0}.urgencyNote{text-align:center;color:#8a9ab0;font-size:12px;margin:12px 0 0;padding:10px 0 4px;border-top:0}
.infoSeo{display:grid;grid-template-columns:1.1fr .9fr;gap:12px;margin:14px 0 0}.infoCard{background:#f6f9fa;border:1px solid #e2e8eb;border-radius:16px;padding:18px;box-shadow:none}.infoCard h2{margin:0 0 12px;font-size:10px;text-transform:uppercase;letter-spacing:.09em;color:#9aa8b0;font-weight:700}.infoGrid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.infoGrid p{margin:0;display:flex;flex-direction:column;gap:3px}.infoGrid b{font-size:10px;color:#33405b;text-transform:uppercase;letter-spacing:.05em}.infoGrid span{font-size:12px;color:#556070;font-weight:500}.hoursCard p{display:grid;grid-template-columns:80px 1fr;margin:0 0 8px;font-size:13px}.hoursCard span{color:#6a7890}.hoursCard b{color:#009CA4;font-weight:700}footer{text-align:center;color:#a8afba;font-size:12px;padding:18px}footer a{color:#009CA4}
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.44);z-index:50;display:flex;align-items:center;justify-content:center;padding:16px}.modal{width:100%;max-width:430px;background:#fff;border-radius:24px;overflow:hidden;box-shadow:0 28px 80px rgba(0,0,0,.22);position:relative}.modalClaraBar{background:#009CA4;color:#fff;padding:14px 18px;display:flex;align-items:flex-start;gap:10px;font-size:13px;line-height:1.55}.modalBody{padding:16px 18px 18px;display:flex;flex-direction:column;gap:11px}.modalSlotRecap{font-size:12px;color:#5f7375;background:#f4fbfb;border:1px solid #d6eeee;border-radius:11px;padding:9px 12px}.modalSuccess{padding:24px 18px;text-align:center;display:flex;flex-direction:column;gap:12px;align-items:center}.successIcon{width:48px;height:48px;border-radius:50%;background:#009CA4;color:#fff;font-size:20px;display:flex;align-items:center;justify-content:center;margin:0 auto 2px}.successTitle{font-size:16px;font-weight:700}.modalWaCta{border:none;cursor:pointer;text-decoration:none;color:#fff;background:#1f9d4f;border-radius:10px;padding:10px 14px;font-size:13px;font-weight:800;display:inline-block}.modalClose{position:absolute;right:11px;width:26px;height:26px;border:0;border-radius:7px;background:rgba(255,255,255,.18);color:#fff;font-size:15px}
@media(max-width:860px){
.pageShell{margin:0;border:0;border-radius:0;box-shadow:none;padding:8px 8px 12px;gap:6px}
.demoNotice{margin:0 0 4px;padding:6px 10px;font-size:11px;font-weight:600;border-radius:8px}
header{grid-template-columns:auto 1fr;grid-template-areas:"logo nav" "search search";gap:8px;margin-bottom:0;padding-bottom:0}
header strong{grid-area:logo;font-size:26px}
header > .uwiSearch{grid-area:search}
header nav{grid-area:nav;justify-content:flex-end;gap:6px}
header a{padding:7px 11px;font-size:12px;border-radius:10px}
.pageShell > .doctorMini{order:0;flex-wrap:nowrap;align-items:center;gap:10px;padding:10px 4px 10px;margin:0;border:0;border-radius:0;background:transparent;box-shadow:none}
.pageShell > .doctorMini .avatar{width:48px;height:48px;font-size:18px;flex-shrink:0}
.pageShell > .doctorMini .doctorMiniText{flex:1;min-width:0}
.pageShell > .doctorMini .doctorMiniText h1{font-size:17px;margin:0 0 2px;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pageShell > .doctorMini .doctorMiniText p{font-size:12px;margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pageShell > .doctorMini .micro,.pageShell > .doctorMini .trustBadges{display:none}
.mainCard{padding:0;border:0;background:transparent;border-radius:0;display:flex;flex-direction:column;gap:6px}
.chatSectionLead{margin:8px 4px 6px;font-size:11px}
.mainCard > .chatHero{order:0;margin-top:0}
.mainCard > .actionRows{order:1;margin-top:8px}
.mainCard > .urgencyNote{order:2}
.chatHero{gap:0;padding:0;max-height:min(78vh,620px);border-radius:18px;border-width:2px;background:linear-gradient(180deg,#e2f6f7 0%,#ffffff 40%);box-shadow:0 18px 48px rgba(0,156,164,.22),0 6px 18px rgba(12,45,51,.08)}
.chatHero .chatHeader{padding:12px 12px 10px;background:linear-gradient(135deg,#009CA4 0%,#00818a 100%)}
.chatHeader{display:grid;grid-template-columns:auto 1fr auto;grid-template-areas:"avatar text voice";column-gap:10px;row-gap:0;align-items:center;padding-bottom:0;border-bottom:0}
.chatHeader > .claraPhoto{grid-area:avatar;width:40px!important;height:40px!important;border-color:rgba(255,255,255,.9)}
.chatHeaderText{grid-area:text;min-width:0}
.chatHeaderText p{display:none}
.chatHeaderName{font-size:14px;line-height:1.2;color:#fff}
.chatHeaderName span{font-size:11px;color:#b8f5d0}
.chatHeaderBadge{display:none}
.voiceControls{grid-area:voice;flex-direction:row;align-items:center;justify-content:flex-end;width:auto;gap:6px}
.voiceBtn{padding:5px 9px;font-size:11px}
.voiceError{text-align:right;max-width:100%;font-size:10px}
.slotsStrip{padding:6px 8px}
.slotsStripLabel{font-size:9px}
.slotChip{min-width:76px;padding:6px 8px}
.slotChipTime{font-size:15px}
.chatScroll{min-height:100px}
.chatScrollInner{padding:10px 12px;gap:8px}
.bubble{max-width:88%;font-size:13px;padding:9px 12px;line-height:1.5}
.chatComposerBar{grid-template-columns:1fr;gap:8px;padding:10px;border-radius:0 0 14px 14px}
.chatComposerBar .composerInputWrap{min-height:48px;padding:0 14px;border-width:1.5px;border-radius:12px}
.composerInputIcon{font-size:20px}
.chatComposerBar .composerInputWrap input{font-size:15px;font-weight:600}
.chatComposerBar .composerSendBtn{width:100%;height:48px;border-radius:12px;font-size:15px}
.actionRows{margin-top:8px;border:1px solid #e2e8eb;border-radius:14px;background:#f6f9fa}
.actionRow{grid-template-columns:1fr;padding:8px 12px;gap:6px}
.actionLabel{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:#6a7890}
.softChips button{padding:6px 10px;font-size:12px}
.faqLinks button{font-size:12px}
.urgencyNote{font-size:11px;padding:8px 0 0;margin:6px 0 0}
.infoSeo{grid-template-columns:1fr;gap:8px;margin-top:8px}
.infoCard{padding:14px;border-radius:14px}
.infoCard h2{margin:0 0 8px}
.infoGrid{grid-template-columns:1fr;gap:8px}
.infoGrid p{flex-direction:row;align-items:baseline;gap:8px;flex-wrap:wrap}
.infoGrid b{min-width:88px;font-size:10px}
.infoGrid span{font-size:13px;color:#374151}
.hoursCard p{grid-template-columns:90px 1fr;font-size:12px;margin:0 0 4px}
.inlineTwoCol{grid-template-columns:1fr}
.mobileStickyCta{display:flex;align-items:center;gap:6px;position:fixed;left:50%;transform:translate(-50%,12px);bottom:max(14px,env(safe-area-inset-bottom));z-index:60;border:0;border-radius:999px;background:#009CA4;color:#fff;font-weight:800;font-size:13px;padding:11px 18px;box-shadow:0 14px 32px rgba(0,156,164,.38);opacity:0;pointer-events:none;transition:opacity .2s ease,transform .2s ease}
.mobileStickyCta.show{opacity:1;pointer-events:auto;transform:translate(-50%,0)}
.mobileStickyCtaIcon{font-size:15px;line-height:1}
}
`;
