// Écran de sélection de l'assistant UWI — remplace homme/femme par choix visuel (photo, prénom, voix)
import { useState, useEffect } from "react";
import ASSISTANTS from "../assistants.config.js";

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

export default function AssistantSelector({ onSelect, onBack }) {
  const [selected, setSelected] = useState(null);
  const [visible, setVisible] = useState(false);
  const [imgFailed, setImgFailed] = useState(() => new Set());

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 80);
    return () => clearTimeout(t);
  }, []);

  const markImgFailed = (id) => setImgFailed((s) => new Set(s).add(id));

  const handleConfirm = () => {
    if (selected) onSelect(selected);
  };

  return (
    <div
      style={{
        fontFamily: "'DM Sans', sans-serif",
        background: C.bg,
        minHeight: "100%",
        display: "flex",
        flexDirection: "column",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Barre accent top */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 3,
          background: "linear-gradient(90deg, #00E5A0, transparent)",
          zIndex: 1,
        }}
      />
      {/* Fond grille + orbs */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          background: `radial-gradient(ellipse 80% 50% at 50% 0%, rgba(0,229,160,0.06), transparent 50%),
            radial-gradient(ellipse 60% 40% at 80% 60%, rgba(0,184,124,0.05), transparent 40%),
            linear-gradient(to right, ${C.border} 1px, transparent 1px),
            linear-gradient(to bottom, ${C.border} 1px, transparent 1px)`,
          backgroundSize: "40px 40px",
          opacity: 0.35,
        }}
      />

      <div style={{ position: "relative", zIndex: 2, flex: 1, display: "flex", flexDirection: "column", paddingBottom: 80, overflowY: "auto" }}>
        <div style={{ maxWidth: 420, margin: "0 auto", width: "100%", padding: "24px 16px" }}>
          {typeof onBack === "function" && (
            <button
              type="button"
              onClick={onBack}
              style={{
                background: "none",
                border: "none",
                color: C.muted,
                fontSize: 14,
                cursor: "pointer",
                marginBottom: 8,
                padding: 0,
              }}
            >
              ← Retour
            </button>
          )}
          <h1
            style={{
              fontSize: 22,
              fontWeight: 700,
              color: C.text,
              textAlign: "center",
              marginBottom: 4,
            }}
          >
            Choisissez votre assistant
          </h1>
          <p
            style={{
              fontSize: 14,
              color: C.muted,
              textAlign: "center",
              marginBottom: 24,
            }}
          >
            Il répondra à vos clients à votre place 24h/24
          </p>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 12,
            }}
          >
            {ASSISTANTS.map((a, index) => {
              const isSelected = selected && selected.id === a.id;
              return (
                <div
                  key={a.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelected(a)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelected(a);
                    }
                  }}
                  style={{
                    position: "relative",
                    opacity: visible ? 1 : 0,
                    transform: visible ? (isSelected ? "translateY(-2px)" : "translateY(0)") : "translateY(20px)",
                    transition: `opacity 0.4s ease ${index * 0.06}s, transform 0.4s ease ${index * 0.06}s, border-color 0.2s ease, box-shadow 0.2s ease`,
                    borderRadius: 16,
                    overflow: "hidden",
                    cursor: "pointer",
                    background: C.card,
                    border: isSelected ? "2px solid #00E5A0" : "1.5px solid #1E3D56",
                    boxShadow: isSelected
                      ? "0 0 0 3px rgba(0,229,160,0.15), 0 8px 30px rgba(0,229,160,0.2)"
                      : "none",
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.borderColor = "rgba(0,229,160,0.4)";
                      e.currentTarget.style.transform = "translateY(-1px)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.borderColor = C.border;
                      e.currentTarget.style.transform = "translateY(0)";
                    }
                  }}
                >
                  {isSelected && (
                    <div
                      style={{
                        position: "absolute",
                        top: 8,
                        right: 8,
                        width: 24,
                        height: 24,
                        background: C.accent,
                        borderRadius: "50%",
                        color: C.bg,
                        fontSize: 12,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        zIndex: 2,
                        fontWeight: 700,
                      }}
                    >
                      ✓
                    </div>
                  )}
                  <div style={{ position: "relative", height: 180, overflow: "hidden", background: C.border }}>
                    {imgFailed.has(a.id) ? (
                      <div
                        style={{
                          width: "100%",
                          height: "100%",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          color: C.muted,
                          fontSize: 48,
                          fontWeight: 700,
                        }}
                      >
                        {a.prenom.charAt(0)}
                      </div>
                    ) : (
                      <img
                        src={a.img}
                        alt={a.prenom}
                        style={{
                          width: "100%",
                          height: "100%",
                          objectFit: "cover",
                          objectPosition: "top",
                          filter: isSelected ? "none" : "brightness(0.85) saturate(0.9)",
                        }}
                        onError={() => markImgFailed(a.id)}
                      />
                    )}
                    {isSelected && (
                      <div
                        style={{
                          position: "absolute",
                          bottom: 0,
                          left: 0,
                          right: 0,
                          height: "40%",
                          background: "linear-gradient(to top, rgba(0,229,160,0.15), transparent)",
                          pointerEvents: "none",
                        }}
                      />
                    )}
                  </div>
                  <div
                    style={{
                      padding: "10px 12px",
                      background: isSelected ? "rgba(0,229,160,0.08)" : "transparent",
                    }}
                  >
                    <div style={{ fontSize: 15, fontWeight: 700, color: isSelected ? C.accent : C.text }}>
                      {a.prenom}
                    </div>
                    <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>
                      🎙️ {a.voice}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* CTA fixe en bas */}
      <div
        style={{
          position: "fixed",
          bottom: 0,
          left: 0,
          right: 0,
          padding: "16px",
          background: `linear-gradient(to top, ${C.bg} 80%, transparent)`,
          zIndex: 10,
        }}
      >
        <div style={{ maxWidth: 420, margin: "0 auto" }}>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={!selected}
            style={{
              width: "100%",
              padding: "14px 20px",
              borderRadius: 12,
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 15,
              fontWeight: 700,
              cursor: selected ? "pointer" : "not-allowed",
              opacity: selected ? 1 : 0.5,
              background: selected
                ? "linear-gradient(135deg, #00E5A0, #00b87c)"
                : C.card,
              color: selected ? C.bg : C.muted,
              border: selected ? "none" : "1px solid #1E3D56",
              boxShadow: selected ? "0 4px 20px rgba(0,229,160,0.3)" : "none",
              animation: selected ? "subtlePulse 2s ease-in-out infinite" : "none",
            }}
          >
            {selected ? `Choisir ${selected.prenom} comme mon assistant →` : "Sélectionnez votre assistant"}
          </button>
        </div>
      </div>

      <style>{`
        @keyframes subtlePulse {
          0%, 100% { box-shadow: 0 4px 20px rgba(0,229,160,0.25); }
          50% { box-shadow: 0 4px 30px rgba(0,229,160,0.45); }
        }
      `}</style>
    </div>
  );
}
