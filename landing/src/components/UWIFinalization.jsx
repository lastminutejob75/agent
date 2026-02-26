// Écran de finalisation UWI — 2 écrans: handoff (choix créneau) → done
import { useState, useCallback } from "react";
import { api } from "../lib/api.js";

const COLORS = {
  bg: "#0A1828",
  surface: "#0F2236",
  card: "#132840",
  border: "#1E3D56",
  accent: "#00E5A0",
  accentDim: "#00b87c",
  text: "#FFFFFF",
  muted: "#6B90A8",
  subtle: "#1A3550",
};

const ASSISTANTS = {
  Sophie: { gender: "f", voice: "Douce et professionnelle" },
  Léa: { gender: "f", voice: "Chaleureuse et rassurante" },
  Emma: { gender: "f", voice: "Dynamique et claire" },
  Lucas: { gender: "m", voice: "Calme et fiable" },
  Hugo: { gender: "m", voice: "Précis et efficace" },
};

const EXPERTS = [
  { name: "Julien Moreau", role: "Expert UWI · Île-de-France", reviews: 38, photo: "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=300&h=300&fit=crop&crop=face" },
  { name: "Marie Lefebvre", role: "Experte UWI · Grand Ouest", reviews: 52, photo: "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=300&h=300&fit=crop&crop=face" },
  { name: "Thomas Blanc", role: "Expert UWI · Auvergne-Rhône", reviews: 44, photo: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=300&h=300&fit=crop&crop=face" },
];

const SLOTS = ["9h00", "10h00", "11h00", "14h00", "15h00", "16h00", "17h00"];

function getNextWorkingDays(count) {
  const out = [];
  let d = new Date();
  d.setDate(d.getDate() + 1);
  while (out.length < count) {
    const day = d.getDay();
    if (day !== 0 && day !== 6) out.push(new Date(d));
    d.setDate(d.getDate() + 1);
  }
  return out;
}

function formatDayForDisplay(date) {
  const days = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"];
  const months = ["janv", "fév", "mars", "avr", "mai", "juin", "juil", "août", "sept", "oct", "nov", "déc"];
  return `${days[date.getDay()]} ${date.getDate()} ${months[date.getMonth()]}`;
}

export default function UWIFinalization({ leadId = "", initialPhone = "", assistantName = "Emma", practitioner = "votre cabinet", onComplete }) {
  const [phase, setPhase] = useState("handoff");
  const [expert] = useState(() => EXPERTS[Math.floor(Math.random() * EXPERTS.length)]);
  const [selectedDay, setSelectedDay] = useState(null);
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [phone, setPhone] = useState(() => (initialPhone || "").replace(/\D/g, "").slice(0, 10));
  const [isSubmitting, setIsSubmitting] = useState(false);

  const workingDays = getNextWorkingDays(4);
  const phoneDigits = (phone || "").replace(/\D/g, "");
  const phoneValid = phoneDigits.length >= 10;
  const canSubmit = selectedDay && selectedSlot && phoneValid;

  const handleHandoffSubmit = useCallback(() => {
    if (!canSubmit) return;
    setIsSubmitting(true);
    const dateIso = selectedDay ? selectedDay.toISOString().slice(0, 10) : "";
    const phoneDigitsOnly = (phone || "").replace(/\D/g, "");
    if (leadId && dateIso && selectedSlot && phoneDigitsOnly.length >= 10) {
      api.preOnboardingCallbackBooking(leadId, {
        date: dateIso,
        slot: selectedSlot,
        phone: phoneDigitsOnly,
      }).catch(() => {});
    }
    setTimeout(() => {
      setIsSubmitting(false);
      setPhase("done");
    }, 1400);
  }, [canSubmit, leadId, selectedDay, selectedSlot, phone]);

  const baseStyle = {
    fontFamily: "'DM Sans', -apple-system, sans-serif",
    boxSizing: "border-box",
    maxWidth: 420,
    margin: "0 auto",
    padding: "24px 20px",
    minHeight: "100vh",
    background: COLORS.bg,
    color: COLORS.text,
    position: "relative",
    overflow: "hidden",
  };

  const gridBg = {
    backgroundImage: `linear-gradient(${COLORS.border} 1px, transparent 1px), linear-gradient(90deg, ${COLORS.border} 1px, transparent 1px)`,
    backgroundSize: "40px 40px",
    opacity: 0.35,
    position: "absolute",
    inset: 0,
    pointerEvents: "none",
  };
  const orb1 = {
    position: "absolute",
    top: -100,
    right: -100,
    width: 300,
    height: 300,
    borderRadius: "50%",
    background: `radial-gradient(circle, ${COLORS.accent}33 0%, transparent 70%)`,
    pointerEvents: "none",
  };
  const orb2 = {
    position: "absolute",
    bottom: -80,
    left: -80,
    width: 250,
    height: 250,
    borderRadius: "50%",
    background: "radial-gradient(circle, rgba(91,168,255,0.25) 0%, transparent 70%)",
    pointerEvents: "none",
  };
  const barAccent = {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 3,
    background: "linear-gradient(90deg, " + COLORS.accent + ", transparent)",
    borderRadius: "3px 3px 0 0",
  };

  if (phase === "handoff") {
    return (
      <div style={{ ...baseStyle }}>
        <div style={gridBg} />
        <div style={orb1} />
        <div style={orb2} />
        <div style={barAccent} />
        <div style={{ position: "relative", zIndex: 1, paddingTop: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24, padding: "12px 14px", background: COLORS.surface, borderRadius: 12, border: `1px solid ${COLORS.border}` }}>
            <img src={expert.photo} alt="" style={{ width: 54, height: 54, borderRadius: "50%", objectFit: "cover", border: `2px solid ${COLORS.accent}` }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: 15 }}>{expert.name}</div>
              <div style={{ fontSize: 12, color: COLORS.muted }}>{expert.role}</div>
              <div style={{ fontSize: 11, color: COLORS.muted }}>★ {expert.reviews} avis</div>
            </div>
            <span style={{ padding: "4px 10px", borderRadius: 20, background: "rgba(0,229,160,0.1)", border: "1px solid rgba(0,229,160,0.25)", color: COLORS.accent, fontSize: 11, fontWeight: 600 }}>Expert dédié</span>
          </div>
          <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>Quand souhaitez-vous être rappelé ?</h2>
          <p style={{ fontSize: 13, color: COLORS.accent, marginBottom: 16 }}>Pour activer {assistantName}</p>
          <p style={{ fontSize: 12, color: COLORS.muted, marginBottom: 8 }}>Jour</p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 20 }}>
            {workingDays.map((d) => {
              const key = d.toISOString().slice(0, 10);
              const selected = selectedDay && selectedDay.toISOString().slice(0, 10) === key;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => { setSelectedDay(d); setSelectedSlot(null); }}
                  style={{
                    padding: "12px 14px",
                    borderRadius: 12,
                    border: `1.5px solid ${selected ? COLORS.accent : COLORS.border}`,
                    background: selected ? COLORS.accent : COLORS.card,
                    color: selected ? COLORS.bg : COLORS.text,
                    fontWeight: selected ? 700 : 500,
                    fontSize: 13,
                    cursor: "pointer",
                  }}
                >
                  {formatDayForDisplay(d)}
                </button>
              );
            })}
          </div>
          {selectedDay && (
            <>
              <p style={{ fontSize: 12, color: COLORS.muted, marginBottom: 8 }}>Créneau</p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 20 }}>
                {SLOTS.map((slot) => {
                  const selected = selectedSlot === slot;
                  return (
                    <button
                      key={slot}
                      type="button"
                      onClick={() => setSelectedSlot(slot)}
                      style={{
                        padding: "10px 16px",
                        borderRadius: 10,
                        border: `1.5px solid ${selected ? COLORS.accent : COLORS.border}`,
                        background: selected ? COLORS.accent : COLORS.card,
                        color: selected ? COLORS.bg : COLORS.text,
                        fontWeight: selected ? 700 : 500,
                        fontSize: 13,
                        cursor: "pointer",
                      }}
                    >
                      {slot}
                    </button>
                  );
                })}
              </div>
            </>
          )}
          <p style={{ fontSize: 12, color: COLORS.muted, marginBottom: 8 }}>Téléphone</p>
          <div style={{ position: "relative", marginBottom: 24 }}>
            <span style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", fontSize: 18 }}>📱</span>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value.replace(/\D/g, "").slice(0, 10))}
              placeholder="06 XX XX XX XX"
              style={{
                width: "100%",
                padding: "14px 14px 14px 44px",
                borderRadius: 12,
                border: `1.5px solid ${phoneValid ? COLORS.accent : COLORS.border}`,
                background: COLORS.card,
                color: COLORS.text,
                fontSize: 15,
                outline: "none",
              }}
            />
          </div>
          <div style={{ display: "flex", gap: 16, marginBottom: 24, fontSize: 12 }}>
            <span style={{ display: "flex", alignItems: "center", gap: 6, color: selectedDay ? COLORS.accent : COLORS.muted }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: selectedDay ? COLORS.accent : "transparent", border: `1.5px solid ${selectedDay ? COLORS.accent : COLORS.border}` }} /> Jour
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: 6, color: selectedSlot ? COLORS.accent : COLORS.muted }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: selectedSlot ? COLORS.accent : "transparent", border: `1.5px solid ${selectedSlot ? COLORS.accent : COLORS.border}` }} /> Créneau
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: 6, color: phoneValid ? COLORS.accent : COLORS.muted }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: phoneValid ? COLORS.accent : "transparent", border: `1.5px solid ${phoneValid ? COLORS.accent : COLORS.border}` }} /> Téléphone
            </span>
          </div>
          <button
            type="button"
            onClick={handleHandoffSubmit}
            disabled={!canSubmit || isSubmitting}
            style={{
              width: "100%",
              padding: "14px 20px",
              borderRadius: 12,
              border: "none",
              background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.accentDim})`,
              color: COLORS.bg,
              fontWeight: 800,
              fontSize: 15,
              cursor: canSubmit && !isSubmitting ? "pointer" : "not-allowed",
              opacity: canSubmit ? 1 : 0.4,
              boxShadow: "0 4px 20px rgba(0,229,160,0.25)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
            }}
          >
            {isSubmitting ? (
              <>
                <span style={{ width: 20, height: 20, border: `2px solid ${COLORS.bg}`, borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
                Confirmation...
              </>
            ) : (
              "Confirmer mon rappel"
            )}
          </button>
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (phase === "done") {
    const dayStr = selectedDay ? formatDayForDisplay(selectedDay) : "";
    return (
      <div style={{ ...baseStyle }}>
        <div style={gridBg} />
        <div style={orb1} />
        <div style={orb2} />
        <div style={barAccent} />
        <div style={{ position: "relative", zIndex: 1, paddingTop: 40, textAlign: "center" }}>
          <div style={{ width: 64, height: 64, margin: "0 auto 20px", borderRadius: "50%", background: COLORS.accent, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 32, animation: "popIn 0.5s cubic-bezier(0.34,1.56,0.64,1) forwards", boxShadow: "0 0 24px rgba(0,229,160,0.4)" }}>✅</div>
          <h1 style={{ fontSize: 22, fontWeight: 800, marginBottom: 12 }}>RDV confirmé !</h1>
          <p style={{ fontSize: 14, color: COLORS.muted, marginBottom: 24, lineHeight: 1.5 }}>
            {expert.name} vous appellera le {dayStr} à {selectedSlot} pour activer {assistantName}.
          </p>
          <div style={{ background: COLORS.surface, borderRadius: 16, padding: 16, marginBottom: 20, border: `1px solid ${COLORS.border}`, textAlign: "left" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
              <img src={expert.photo} alt="" style={{ width: 44, height: 44, borderRadius: "50%", objectFit: "cover", border: `2px solid ${COLORS.accent}` }} />
              <div>
                <div style={{ fontWeight: 700 }}>{expert.name}</div>
                <div style={{ fontSize: 12, color: COLORS.muted }}>{expert.role}</div>
              </div>
            </div>
            <div style={{ height: 1, background: COLORS.border, margin: "12px 0" }} />
            <p style={{ fontSize: 12, color: COLORS.muted, marginBottom: 4 }}>📅 Date</p>
            <p style={{ fontWeight: 600, marginBottom: 8 }}>{dayStr} à {selectedSlot}</p>
            <p style={{ fontSize: 12, color: COLORS.muted, marginBottom: 4 }}>📱 Rappel sur</p>
            <p style={{ fontWeight: 600, marginBottom: 8 }}>{phone.replace(/(\d{2})(?=\d)/g, "$1 ")}</p>
            <p style={{ fontSize: 12, color: COLORS.muted, marginBottom: 4 }}>🎯 Objectif</p>
            <p style={{ fontWeight: 600 }}>Activer {assistantName}</p>
          </div>
          <div style={{ background: "rgba(0,229,160,0.05)", border: "1px solid rgba(0,229,160,0.2)", borderRadius: 12, padding: 12, marginBottom: 24, fontSize: 12, color: COLORS.muted, textAlign: "left" }}>
            📩 SMS de rappel envoyé sur votre mobile
          </div>
          <button
            type="button"
            onClick={onComplete}
            style={{
              width: "100%",
              padding: "14px 20px",
              borderRadius: 12,
              border: "none",
              background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.accentDim})`,
              color: COLORS.bg,
              fontWeight: 800,
              fontSize: 15,
              cursor: "pointer",
              boxShadow: "0 4px 20px rgba(0,229,160,0.25)",
            }}
          >
            Aller au tableau de bord
          </button>
        </div>
        <style>{`@keyframes popIn { 0% { transform: scale(0.3); opacity: 0; } 100% { transform: scale(1); opacity: 1; } }`}</style>
      </div>
    );
  }

  return null;
}
