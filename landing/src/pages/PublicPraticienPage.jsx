import { useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import PublicPraticienChat from "../components/PublicPraticienChat.jsx";
import { getApiUrl } from "../lib/authConfig.js";

const C = {
  bg: "#F4F7FB",
  surface: "#FFFFFF",
  navy: "#071A33",
  text: "#475569",
  muted: "#64748B",
  border: "#E2E8F0",
  teal: "#009CA4",
  tealSoft: "#E0F7F8",
  green: "#16A34A",
  amber: "#F59E0B",
};

const DAYS_FR = {
  monday: "Lundi",
  tuesday: "Mardi",
  wednesday: "Mercredi",
  thursday: "Jeudi",
  friday: "Vendredi",
  saturday: "Samedi",
  sunday: "Dimanche",
};
const DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

const API_BASE =
  getApiUrl() ||
  (import.meta.env.DEV ? "http://localhost:8000" : (import.meta.env.VITE_UWI_API_BASE_URL || "")).replace(
    /\/$/,
    ""
  );

function fmtHours(row) {
  if (!row || !row.is_open) return "Fermé";
  const parts = [];
  if (row.morning_start && row.morning_end) parts.push(`${row.morning_start} – ${row.morning_end}`);
  if (row.afternoon_start && row.afternoon_end) parts.push(`${row.afternoon_start} – ${row.afternoon_end}`);
  return parts.length ? parts.join(" / ") : "Ouvert";
}

function sortOpeningHours(items) {
  const arr = Array.isArray(items) ? items : [];
  return [...arr].sort((a, b) => DAY_ORDER.indexOf(a.day) - DAY_ORDER.indexOf(b.day));
}

export default function PublicPraticienPage() {
  const { slug } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    fetch(`${API_BASE}/api/public/praticiens/${encodeURIComponent(slug)}`)
      .then(async (res) => {
        if (!res.ok) {
          if (res.status === 404) throw new Error("Cabinet introuvable.");
          throw new Error("Impossible de charger la fiche.");
        }
        return res.json();
      })
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e.message || "Erreur inconnue");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  const sortedHours = useMemo(() => sortOpeningHours(data?.opening_hours || []), [data?.opening_hours]);

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", background: C.bg, display: "grid", placeItems: "center", padding: 24 }}>
        <div style={{ color: C.muted, fontSize: 14 }}>Chargement…</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ minHeight: "100vh", background: C.bg, display: "grid", placeItems: "center", padding: 24 }}>
        <div
          style={{
            maxWidth: 460,
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderRadius: 18,
            padding: 24,
            textAlign: "center",
          }}
        >
          <h1 style={{ margin: 0, fontSize: 22, color: C.navy }}>Cabinet introuvable</h1>
          <p style={{ margin: "10px 0 18px", color: C.text, fontSize: 14 }}>
            {error || "Cette fiche n'est pas disponible."}
          </p>
          <Link
            to="/"
            style={{
              display: "inline-block",
              padding: "10px 16px",
              borderRadius: 12,
              background: C.teal,
              color: "#fff",
              textDecoration: "none",
              fontWeight: 700,
              fontSize: 14,
            }}
          >
            Retour à l'accueil
          </Link>
        </div>
      </div>
    );
  }

  const fullAddress = [data.address_line, [data.postal_code, data.city].filter(Boolean).join(" ")].filter(Boolean).join(", ");
  const mapsHref = fullAddress
    ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(fullAddress)}`
    : "";
  const telHref = data.phone ? `tel:${data.phone.replace(/\s/g, "")}` : "";
  const mailHref = data.email ? `mailto:${data.email}` : "";

  return (
    <div style={{ minHeight: "100vh", background: C.bg, padding: "32px 16px" }}>
      <style>{`
        @media (max-width: 760px) {
          .praticien-grid { grid-template-columns: 1fr !important; }
          .praticien-header { flex-direction: column !important; align-items: flex-start !important; }
          .praticien-photo { width: 96px !important; height: 96px !important; }
        }
      `}</style>
      <div style={{ maxWidth: 920, margin: "0 auto" }}>
        <header
          className="praticien-header"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 20,
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderRadius: 22,
            padding: 24,
            marginBottom: 18,
          }}
        >
          {data.practitioner_photo_url ? (
            <img
              className="praticien-photo"
              src={data.practitioner_photo_url}
              alt={data.practitioner_name || data.cabinet_name}
              style={{ width: 112, height: 112, borderRadius: "50%", objectFit: "cover", flexShrink: 0, border: `2px solid ${C.tealSoft}` }}
            />
          ) : (
            <div
              className="praticien-photo"
              style={{
                width: 112,
                height: 112,
                borderRadius: "50%",
                background: C.tealSoft,
                color: C.teal,
                display: "grid",
                placeItems: "center",
                fontSize: 36,
                fontWeight: 800,
                flexShrink: 0,
              }}
            >
              {(data.practitioner_name || data.cabinet_name || "?").slice(0, 1).toUpperCase()}
            </div>
          )}
          <div style={{ minWidth: 0, flex: 1 }}>
            <h1 style={{ margin: 0, fontSize: 26, fontWeight: 800, color: C.navy, letterSpacing: "-0.02em" }}>
              {data.practitioner_name || data.cabinet_name}
            </h1>
            {data.specialty ? (
              <p style={{ margin: "4px 0 8px", color: C.text, fontSize: 15 }}>{data.specialty}</p>
            ) : null}
            {data.cabinet_name && data.practitioner_name ? (
              <p style={{ margin: 0, color: C.muted, fontSize: 13 }}>{data.cabinet_name}</p>
            ) : null}
            <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", gap: 8 }}>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  borderRadius: 999,
                  padding: "5px 12px",
                  background: data.accepts_new_patients ? "#DCFCE7" : "#FEF3C7",
                  color: data.accepts_new_patients ? "#15803D" : "#92400E",
                }}
              >
                {data.accepts_new_patients ? "Accepte les nouveaux patients" : "N'accepte pas de nouveaux patients pour le moment"}
              </span>
              {(data.languages || []).map((lang) => (
                <span
                  key={lang}
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    borderRadius: 999,
                    padding: "5px 12px",
                    background: C.bg,
                    color: C.text,
                  }}
                >
                  {lang}
                </span>
              ))}
            </div>
          </div>
        </header>

        <PublicPraticienChat
          apiBase={API_BASE}
          slug={slug}
          assistantName={data.assistant_name || "Clara"}
          welcomeMessage={data.welcome_message}
          phone={data.phone}
        />

        <div className="praticien-grid" style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 18 }}>
          <section
            style={{
              background: C.surface,
              border: `1px solid ${C.border}`,
              borderRadius: 18,
              padding: 20,
            }}
          >
            <h2 style={{ margin: "0 0 14px", fontSize: 16, color: C.navy, fontWeight: 800 }}>Coordonnées</h2>
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 10, fontSize: 14, color: C.text }}>
              {fullAddress ? (
                <li>
                  <strong style={{ color: C.navy, display: "block", fontSize: 12, marginBottom: 2 }}>Adresse</strong>
                  {mapsHref ? (
                    <a href={mapsHref} target="_blank" rel="noopener noreferrer" style={{ color: C.teal, textDecoration: "none" }}>
                      {fullAddress}
                    </a>
                  ) : (
                    fullAddress
                  )}
                </li>
              ) : null}
              {data.phone ? (
                <li>
                  <strong style={{ color: C.navy, display: "block", fontSize: 12, marginBottom: 2 }}>Téléphone</strong>
                  <a href={telHref} style={{ color: C.teal, textDecoration: "none" }}>
                    {data.phone}
                  </a>
                </li>
              ) : null}
              {data.email ? (
                <li>
                  <strong style={{ color: C.navy, display: "block", fontSize: 12, marginBottom: 2 }}>Email</strong>
                  <a href={mailHref} style={{ color: C.teal, textDecoration: "none" }}>
                    {data.email}
                  </a>
                </li>
              ) : null}
              {data.website_url ? (
                <li>
                  <strong style={{ color: C.navy, display: "block", fontSize: 12, marginBottom: 2 }}>Site web</strong>
                  <a href={data.website_url} target="_blank" rel="noopener noreferrer" style={{ color: C.teal, textDecoration: "none" }}>
                    {data.website_url}
                  </a>
                </li>
              ) : null}
            </ul>
            {(data.access_instructions || data.parking_info || data.pmr_access || data.payment_methods) ? (
              <>
                <hr style={{ border: 0, borderTop: `1px solid ${C.border}`, margin: "16px 0" }} />
                <h3 style={{ margin: "0 0 8px", fontSize: 13, color: C.navy, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                  Infos pratiques
                </h3>
                <ul style={{ listStyle: "none", margin: 0, padding: 0, fontSize: 13, color: C.text, lineHeight: 1.6 }}>
                  {data.access_instructions ? <li>📍 {data.access_instructions}</li> : null}
                  {data.parking_info ? <li>🅿️ {data.parking_info}</li> : null}
                  {data.pmr_access ? <li>♿ Accès PMR</li> : null}
                  {data.payment_methods ? <li>💳 {data.payment_methods}</li> : null}
                </ul>
              </>
            ) : null}
          </section>

          <section
            style={{
              background: C.surface,
              border: `1px solid ${C.border}`,
              borderRadius: 18,
              padding: 20,
            }}
          >
            <h2 style={{ margin: "0 0 14px", fontSize: 16, color: C.navy, fontWeight: 800 }}>Horaires d'ouverture</h2>
            {sortedHours.length === 0 ? (
              <p style={{ margin: 0, color: C.muted, fontSize: 14 }}>Horaires non communiqués.</p>
            ) : (
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 6 }}>
                {sortedHours.map((row) => (
                  <li
                    key={row.day}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 12,
                      fontSize: 14,
                      color: row.is_open ? C.text : C.muted,
                      padding: "6px 0",
                      borderBottom: `1px dashed ${C.border}`,
                    }}
                  >
                    <span style={{ fontWeight: 600, color: C.navy }}>{DAYS_FR[row.day] || row.day}</span>
                    <span>{fmtHours(row)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        {data.appointment_reasons && data.appointment_reasons.length > 0 ? (
          <section
            style={{
              marginTop: 18,
              background: C.surface,
              border: `1px solid ${C.border}`,
              borderRadius: 18,
              padding: 20,
            }}
          >
            <h2 style={{ margin: "0 0 14px", fontSize: 16, color: C.navy, fontWeight: 800 }}>Motifs de consultation</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12 }}>
              {data.appointment_reasons.map((r, idx) => (
                <div
                  key={`${r.label}-${idx}`}
                  style={{
                    border: `1px solid ${C.border}`,
                    borderRadius: 14,
                    padding: 14,
                    background: C.bg,
                  }}
                >
                  <div style={{ fontSize: 14, fontWeight: 700, color: C.navy, marginBottom: 4 }}>{r.label}</div>
                  <div style={{ fontSize: 12, color: C.muted }}>
                    {r.duration_minutes} min{r.allowed_for_new_patients ? "" : " · sur invitation"}
                  </div>
                  {r.description ? <p style={{ margin: "6px 0 0", fontSize: 12, color: C.text }}>{r.description}</p> : null}
                </div>
              ))}
            </div>
          </section>
        ) : null}

        <footer style={{ marginTop: 24, textAlign: "center", fontSize: 12, color: C.muted }}>
          Propulsé par <strong style={{ color: C.navy }}>UWi</strong> — fiche publique du cabinet
        </footer>
      </div>
    </div>
  );
}
