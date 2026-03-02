import { useState, useEffect } from "react";

const C = {
  bg: "#0A1828",
  surface: "#0F2236",
  card: "#132840",
  border: "#1E3D56",
  accent: "#00E5A0",
  accentDim: "#00b87c",
  text: "#FFFFFF",
  muted: "#6B90A8",
};

export const ASSISTANTS = [
  { id: "sophie", prenom: "Sophie", gender: "f", voice: "Douce et professionnelle", img: "/avatars/uwi-avatar-sophie.png" },
  { id: "laura", prenom: "Laura", gender: "f", voice: "Chaleureuse et rassurante", img: "/avatars/uwi-avatar-laura.png" },
  { id: "emma", prenom: "Emma", gender: "f", voice: "Dynamique et claire", img: "/avatars/uwi-avatar-emma.png" },
  { id: "julie", prenom: "Julie", gender: "f", voice: "Calme et professionnelle", img: "/avatars/uwi-avatar-julie.png" },
  { id: "clara", prenom: "Clara", gender: "f", voice: "Précise et efficace", img: "/avatars/uwi-avatar-clara.png" },
  { id: "hugo", prenom: "Hugo", gender: "m", voice: "Analytique et fiable", img: "/avatars/uwi-avatar-hugo.png" },
  { id: "julien", prenom: "Julien", gender: "m", voice: "Chaleureux et rassurant", img: "/avatars/uwi-avatar-julien.png" },
  { id: "nicolas", prenom: "Nicolas", gender: "m", voice: "Dynamique et efficace", img: "/avatars/uwi-avatar-nicolas.png" },
  { id: "alexandre", prenom: "Alexandre", gender: "m", voice: "Charismatique et précis", img: "/avatars/uwi-avatar-alexandre.png" },
  { id: "thomas", prenom: "Thomas", gender: "m", voice: "Calme et professionnel", img: "/avatars/uwi-avatar-thomas.png" },
];

// ── Thumb picker ──────────────────────────────────────────────────────────────
function ThumbPicker({ assistants, activeId, onSelect }) {
  return (
    <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap", marginBottom: 32 }}>
      {assistants.map((a) => {
        const active = a.id === activeId;
        return (
          <div
            key={a.id}
            onClick={() => onSelect(a)}
            style={{
              width: 52,
              height: 52,
              borderRadius: "50%",
              overflow: "hidden",
              cursor: "pointer",
              flexShrink: 0,
              border: `2.5px solid ${active ? C.accent : C.border}`,
              boxShadow: active ? "0 0 14px rgba(0,229,160,0.4)" : "none",
              transform: active ? "scale(1.12)" : "scale(1)",
              transition: "all 0.2s ease",
              background: C.bg,
            }}
          >
            <div style={{ position: "relative", width: "100%", height: "100%" }}>
              <div style={{ position: "absolute", inset: 0, background: C.bg }} />
              <img
                src={a.img}
                alt={a.prenom}
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                  objectPosition: "top",
                  mixBlendMode: "luminosity",
                  filter: active ? "brightness(1.2) saturate(1.1)" : "brightness(0.8) saturate(0.7)",
                  position: "relative",
                  zIndex: 1,
                  transition: "filter 0.25s",
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Spotlight Card ────────────────────────────────────────────────────────────
function SpotlightCard({ assistant, onCTA }) {
  const [vis, setVis] = useState(false);

  useEffect(() => {
    setVis(false);
    const t = setTimeout(() => setVis(true), 60);
    return () => clearTimeout(t);
  }, [assistant.id]);

  const pronoun = assistant.gender === "f" ? "assistante" : "assistant";
  const status = assistant.gender === "f" ? "Prête à répondre" : "Prêt à répondre";

  return (
    <div
      className="uwi-spotlight-card"
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 24,
        overflow: "hidden",
        maxWidth: 760,
        margin: "0 auto",
        boxShadow: "0 24px 80px rgba(0,0,0,0.5), 0 0 0 1px rgba(0,229,160,0.08)",
      }}
    >
      {/* Photo */}
      <div className="uwi-spotlight-photo" style={{ position: "relative", overflow: "hidden", background: C.bg }}>
        <img
          src={assistant.img}
          alt={assistant.prenom}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            objectPosition: "top",
            display: "block",
            mixBlendMode: "luminosity",
            filter: "brightness(1.18) contrast(1.05) saturate(1.05)",
            opacity: vis ? 1 : 0,
            transform: vis ? "scale(1)" : "scale(1.04)",
            transition: "all 0.5s ease",
          }}
        />
        {/* Accent bar gauche */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            bottom: 0,
            width: 3,
            background: `linear-gradient(to bottom, ${C.accent}, ${C.accentDim})`,
          }}
        />
        {/* Fondu bas */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: 90,
            background: `linear-gradient(to top, ${C.surface}, transparent)`,
          }}
        />
      </div>

      {/* Infos */}
      <div className="uwi-spotlight-info" style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
        <div
          style={{
            opacity: vis ? 1 : 0,
            transform: vis ? "translateX(0)" : "translateX(16px)",
            transition: "all 0.5s ease 0.1s",
          }}
        >
          {/* Tag */}
          <div
            style={{
              fontSize: 11,
              color: C.accent,
              fontWeight: 700,
              letterSpacing: 2,
              textTransform: "uppercase",
              marginBottom: 10,
            }}
          >
            ✦ Votre {pronoun}
          </div>

          {/* Prénom */}
          <div
            className="uwi-spotlight-name"
            style={{
              fontSize: 52,
              fontWeight: 800,
              color: C.text,
              letterSpacing: -2,
              lineHeight: 1,
              marginBottom: 8,
            }}
          >
            {assistant.prenom}
          </div>

          {/* Voix */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 15, color: C.muted, marginBottom: 22 }}>
            <span>🎙️</span>
            <span>{assistant.voice}</span>
          </div>

          {/* Stats */}
          <div className="uwi-spotlight-stats" style={{ display: "flex", gap: 12, marginBottom: 24 }}>
            {[
              ["24/7", "Disponible"],
              ["< 2s", "Réponse"],
              ["🇫🇷", "Français"],
            ].map(([v, l]) => (
              <div
                key={l}
                style={{
                  background: C.card,
                  border: `1px solid ${C.border}`,
                  borderRadius: 10,
                  padding: "8px 14px",
                  textAlign: "center",
                }}
              >
                <div style={{ fontSize: 14, fontWeight: 800, color: C.accent }}>{v}</div>
                <div
                  style={{
                    fontSize: 10,
                    color: C.muted,
                    marginTop: 2,
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                  }}
                >
                  {l}
                </div>
              </div>
            ))}
          </div>

          {/* Status online */}
          <div style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 12, color: C.accent, marginBottom: 24 }}>
            <div
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: C.accent,
                boxShadow: `0 0 8px ${C.accent}`,
                animation: "uwi-pulse 1.8s ease-in-out infinite",
              }}
            />
            {status} à vos clients
          </div>

          {/* CTA */}
          <button onClick={() => onCTA(assistant)} className="uwi-btn-primary">
            Choisir {assistant.prenom} comme mon {pronoun} →
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Dots ──────────────────────────────────────────────────────────────────────
function Dots({ total, active, onChange }) {
  return (
    <div style={{ display: "flex", gap: 6, justifyContent: "center", marginTop: 20 }}>
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          onClick={() => onChange(i)}
          style={{
            width: active === i ? 20 : 6,
            height: 6,
            borderRadius: 3,
            background: active === i ? C.accent : C.border,
            cursor: "pointer",
            transition: "all 0.3s ease",
          }}
        />
      ))}
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function AgentsSpotlight({ onSelectAgent }) {
  const [activeIdx, setActiveIdx] = useState(0);

  // Auto-rotate 4s
  useEffect(() => {
    const iv = setInterval(() => setActiveIdx((i) => (i + 1) % ASSISTANTS.length), 4000);
    return () => clearInterval(iv);
  }, []);

  const handleCTA = (a) => {
    if (onSelectAgent) onSelectAgent(a);
  };

  return (
    <section style={{ background: C.bg, padding: "80px 24px", position: "relative", overflow: "hidden" }}>
      <style>
        {`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700;800&display=swap');
        @keyframes uwi-pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.5;transform:scale(1.4)} }
        .uwi-btn-primary {
          background: linear-gradient(135deg, #00E5A0, #00b87c);
          color: #0A1828; border: none; border-radius: 14px;
          padding: 14px 24px; font-size: 15px; font-weight: 800;
          cursor: pointer; letter-spacing: 0.2px;
          box-shadow: 0 4px 24px rgba(0,229,160,0.3);
          transition: all 0.2s ease; font-family: 'DM Sans', sans-serif;
          text-align: left; width: 100%;
        }
        .uwi-btn-primary:hover { filter: brightness(1.08); transform: translateY(-2px); }
        .uwi-spotlight-card { display: flex; }
        .uwi-spotlight-photo { width: 300px; flex-shrink: 0; min-height: 340px; }
        .uwi-spotlight-info  { padding: 36px 32px; }
        @media (max-width: 640px) {
          .uwi-spotlight-card  { flex-direction: column !important; }
          .uwi-spotlight-photo { width: 100% !important; height: 260px !important; min-height: unset !important; }
          .uwi-spotlight-info  { padding: 24px 20px !important; }
          .uwi-spotlight-name  { font-size: 36px !important; }
          .uwi-spotlight-stats { flex-wrap: wrap; gap: 8px !important; }
        }
      `}
      </style>

      {/* Orbs */}
      <div
        style={{
          position: "absolute",
          top: "-20%",
          right: "-5%",
          width: 500,
          height: 500,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(0,229,160,0.06), transparent 70%)",
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: "-20%",
          left: "-5%",
          width: 400,
          height: 400,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(91,168,255,0.05), transparent 70%)",
          pointerEvents: "none",
        }}
      />

      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: 40, position: "relative", zIndex: 1 }}>
        <div
          style={{
            fontSize: 12,
            color: C.accent,
            fontWeight: 700,
            letterSpacing: 3,
            textTransform: "uppercase",
            marginBottom: 10,
          }}
        >
          ✦ Vos assistants vocaux
        </div>
        <div
          style={{
            fontSize: 36,
            fontWeight: 800,
            color: C.text,
            letterSpacing: -1.5,
            lineHeight: 1.1,
            marginBottom: 12,
          }}
        >
          Choisissez la voix qui
          <br />
          répondra à vos clients
        </div>
        <div style={{ fontSize: 16, color: C.muted, maxWidth: 420, margin: "0 auto", lineHeight: 1.6 }}>
          10 assistants disponibles. Humains, chaleureux, disponibles 24h/24.
        </div>
      </div>

      {/* Thumb picker */}
      <div style={{ position: "relative", zIndex: 1, maxWidth: 760, margin: "0 auto" }}>
        <ThumbPicker
          assistants={ASSISTANTS}
          activeId={ASSISTANTS[activeIdx].id}
          onSelect={(a) => setActiveIdx(ASSISTANTS.findIndex((x) => x.id === a.id))}
        />
      </div>

      {/* Spotlight */}
      <div style={{ position: "relative", zIndex: 1, maxWidth: 800, margin: "0 auto" }}>
        <SpotlightCard assistant={ASSISTANTS[activeIdx]} onCTA={handleCTA} />
        <Dots total={ASSISTANTS.length} active={activeIdx} onChange={setActiveIdx} />
      </div>
    </section>
  );
}
