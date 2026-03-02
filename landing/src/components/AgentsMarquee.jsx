import { useState } from "react";

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

const ASSISTANTS = [
  { id: "sophie", prenom: "Sophie", img: "/avatars/uwi-avatar-sophie.png" },
  { id: "laura", prenom: "Laura", img: "/avatars/uwi-avatar-laura.png" },
  { id: "emma", prenom: "Emma", img: "/avatars/uwi-avatar-emma.png" },
  { id: "julie", prenom: "Julie", img: "/avatars/uwi-avatar-julie.png" },
  { id: "clara", prenom: "Clara", img: "/avatars/uwi-avatar-clara.png" },
  { id: "hugo", prenom: "Hugo", img: "/avatars/uwi-avatar-hugo.png" },
  { id: "julien", prenom: "Julien", img: "/avatars/uwi-avatar-julien.png" },
  { id: "nicolas", prenom: "Nicolas", img: "/avatars/uwi-avatar-nicolas.png" },
  { id: "alexandre", prenom: "Alexandre", img: "/avatars/uwi-avatar-alexandre.png" },
  { id: "thomas", prenom: "Thomas", img: "/avatars/uwi-avatar-thomas.png" },
];

const ROW1 = ASSISTANTS.slice(0, 5);
const ROW2 = ASSISTANTS.slice(5);

// ── Single marquee row ────────────────────────────────────────────────────────
function Row({ items, reverse, onHover, hoveredId }) {
  const [paused, setPaused] = useState(false);
  const tripled = [...items, ...items, ...items];

  return (
    <div
      style={{ overflow: "hidden", width: "100%", position: "relative" }}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => {
        setPaused(false);
        onHover(null);
      }}
    >
      {/* Fade edges */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          bottom: 0,
          width: 100,
          background: `linear-gradient(90deg, ${C.bg}, transparent)`,
          zIndex: 2,
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          position: "absolute",
          right: 0,
          top: 0,
          bottom: 0,
          width: 100,
          background: `linear-gradient(270deg, ${C.bg}, transparent)`,
          zIndex: 2,
          pointerEvents: "none",
        }}
      />

      <div
        style={{
          display: "flex",
          gap: 10,
          animation: `uwi-marquee${reverse ? "Rev" : ""} 32s linear infinite`,
          animationPlayState: paused ? "paused" : "running",
          width: "max-content",
        }}
      >
        {tripled.map((a, i) => {
          const isHovered = a.id === hoveredId;
          return (
            <div
              key={`${a.id}-${i}`}
              onMouseEnter={() => onHover(a.id)}
              style={{
                position: "relative",
                width: 100,
                height: 120,
                borderRadius: 14,
                overflow: "hidden",
                flexShrink: 0,
                cursor: "default",
                border: `2px solid ${isHovered ? C.accent : "transparent"}`,
                boxShadow: isHovered ? "0 0 18px rgba(0,229,160,0.3)" : "none",
                transform: isHovered ? "scale(1.08) translateY(-4px)" : "scale(1)",
                transition: "all 0.25s ease",
                background: C.bg,
              }}
            >
              {/* Dark bg pour absorber fond blanc des photos */}
              <div style={{ position: "absolute", inset: 0, background: C.bg, zIndex: 0 }} />
              <img
                src={a.img}
                alt={a.prenom}
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                  objectPosition: "top",
                  mixBlendMode: "luminosity",
                  filter: isHovered
                    ? "brightness(1.2) contrast(1.05) saturate(1.1)"
                    : "brightness(0.85) saturate(0.8)",
                  position: "relative",
                  zIndex: 1,
                  transition: "filter 0.25s ease",
                }}
              />
              {/* Overlay teinté */}
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  zIndex: 2,
                  pointerEvents: "none",
                  background: isHovered ? "rgba(0,229,160,0.08)" : "rgba(10,24,40,0.3)",
                  transition: "background 0.25s",
                }}
              />
              {/* Nom en bas */}
              <div
                style={{
                  position: "absolute",
                  bottom: 0,
                  left: 0,
                  right: 0,
                  padding: "18px 6px 7px",
                  background: "linear-gradient(to top, rgba(0,0,0,0.85), transparent)",
                  fontSize: 11,
                  fontWeight: 700,
                  color: isHovered ? C.accent : C.text,
                  textAlign: "center",
                  zIndex: 3,
                  transition: "color 0.25s",
                  letterSpacing: 0.3,
                }}
              >
                {a.prenom}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function AgentsMarquee({ onSelectAgent }) {
  const [hoveredId, setHoveredId] = useState(null);

  return (
    <section style={{ background: C.bg, padding: "64px 0 56px", position: "relative", overflow: "hidden" }}>
      <style>
        {`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700;800&display=swap');
        @keyframes uwi-marquee    { from{transform:translateX(0)} to{transform:translateX(-33.333%)} }
        @keyframes uwi-marqueeRev { from{transform:translateX(-33.333%)} to{transform:translateX(0)} }
        .uwi-marquee-btn {
          background: transparent;
          color: #00E5A0;
          border: 1.5px solid rgba(0,229,160,0.4);
          border-radius: 12px;
          padding: 12px 28px;
          font-size: 14px; font-weight: 700;
          cursor: pointer; letter-spacing: 0.2px;
          font-family: 'DM Sans', sans-serif;
          transition: all 0.2s ease;
        }
        .uwi-marquee-btn:hover {
          background: rgba(0,229,160,0.1);
          border-color: #00E5A0;
          transform: translateY(-2px);
          box-shadow: 0 4px 20px rgba(0,229,160,0.15);
        }
      `}
      </style>

      {/* Séparateur top */}
      <div
        style={{
          width: "100%",
          height: 1,
          background: `linear-gradient(90deg, transparent, ${C.border}, transparent)`,
          marginBottom: 48,
        }}
      />

      {/* Texte intro centré */}
      <div style={{ textAlign: "center", padding: "0 24px", marginBottom: 36 }}>
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
          ✦ 10 assistants disponibles
        </div>
        <div
          style={{
            fontSize: 26,
            fontWeight: 800,
            color: C.text,
            letterSpacing: -1,
            lineHeight: 1.2,
            marginBottom: 10,
          }}
        >
          Une voix humaine pour votre cabinet
        </div>
        <div style={{ fontSize: 14, color: C.muted, maxWidth: 380, margin: "0 auto", lineHeight: 1.6 }}>
          Survolez pour découvrir chaque assistant
        </div>
      </div>

      {/* Marquee rows */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 40 }}>
        <Row items={ROW1} reverse={false} onHover={setHoveredId} hoveredId={hoveredId} />
        <Row items={ROW2} reverse onHover={setHoveredId} hoveredId={hoveredId} />
      </div>

      {/* CTA bas */}
      <div style={{ textAlign: "center", padding: "0 24px" }}>
        <button
          className="uwi-marquee-btn"
          onClick={() => {
            if (onSelectAgent) onSelectAgent();
          }}
        >
          Choisir mon assistant →
        </button>
        <div style={{ fontSize: 12, color: C.muted, marginTop: 12 }}>
          Gratuit pendant 14 jours · Sans engagement
        </div>
      </div>

      {/* Séparateur bottom */}
      <div
        style={{
          width: "100%",
          height: 1,
          background: `linear-gradient(90deg, transparent, ${C.border}, transparent)`,
          marginTop: 48,
        }}
      />
    </section>
  );
}
