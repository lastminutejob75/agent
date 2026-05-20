import { useEffect, useRef } from "react";
import { usePublicPraticienChat } from "../hooks/usePublicPraticienChat.js";

const C = {
  surface: "#FFFFFF",
  navy: "#071A33",
  text: "#475569",
  muted: "#64748B",
  border: "#E2E8F0",
  teal: "#009CA4",
  tealSoft: "#E0F7F8",
  bg: "#F8FAFC",
};

/**
 * Chat assistant (logique widget /frontend) avec le design de la fiche publique.
 */
export default function PublicPraticienChat({ apiBase, slug, assistantName, welcomeMessage, phone }) {
  const scrollRef = useRef(null);
  const { messages, input, setInput, typing, error, locked, maxLen, submit, sendMessage } =
    usePublicPraticienChat({
      apiBase,
      slug,
      welcomeMessage,
    });

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, typing]);

  const name = (assistantName || "Clara").trim();

  return (
    <section
      style={{
        marginTop: 18,
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 18,
        overflow: "hidden",
      }}
      aria-label="Discuter avec l'assistante"
    >
      <div
        style={{
          padding: "16px 20px",
          borderBottom: `1px solid ${C.border}`,
          background: C.tealSoft,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <div>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 800, color: C.navy }}>
            Discuter avec {name}
          </h2>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: C.muted }}>
            Prise de rendez-vous et questions — réponses instantanées
          </p>
        </div>
        {phone ? (
          <a
            href={`tel:${String(phone).replace(/\s/g, "")}`}
            style={{
              flexShrink: 0,
              fontSize: 12,
              fontWeight: 700,
              color: C.teal,
              textDecoration: "none",
              padding: "8px 12px",
              borderRadius: 10,
              border: `1px solid ${C.teal}`,
              background: C.surface,
            }}
          >
            Appeler
          </a>
        ) : null}
      </div>

      <div
        ref={scrollRef}
        style={{
          minHeight: 280,
          maxHeight: 420,
          overflowY: "auto",
          padding: 16,
          background: C.bg,
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        {messages.map((m) => (
          <div
            key={m.id}
            style={{
              alignSelf: m.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "88%",
            }}
          >
            <div
              style={{
                padding: "10px 14px",
                borderRadius: m.role === "user" ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
                background: m.role === "user" ? C.teal : C.surface,
                color: m.role === "user" ? "#fff" : C.text,
                fontSize: 14,
                lineHeight: 1.55,
                border: m.role === "user" ? "none" : `1px solid ${C.border}`,
                whiteSpace: "pre-wrap",
              }}
            >
              {m.text}
            </div>
            {m.slots?.length && !locked ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
                {m.slots.map((slot) => (
                  <button
                    key={`${m.id}-slot-${slot.index}`}
                    type="button"
                    onClick={() => sendMessage(String(slot.index))}
                    style={{
                      textAlign: "left",
                      padding: "10px 12px",
                      borderRadius: 12,
                      border: `1px solid ${C.teal}`,
                      background: C.surface,
                      color: C.navy,
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: "pointer",
                      lineHeight: 1.4,
                    }}
                  >
                    <span style={{ color: C.teal, marginRight: 6 }}>{slot.index}.</span>
                    {slot.label}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ))}
        {typing ? (
          <p style={{ margin: 0, fontSize: 13, color: C.muted, fontStyle: "italic" }}>{name} écrit…</p>
        ) : null}
      </div>

      {error ? (
        <p style={{ margin: 0, padding: "8px 16px", fontSize: 13, color: "#B91C1C", background: "#FEF2F2" }}>{error}</p>
      ) : null}

      <form onSubmit={submit} style={{ padding: 16, borderTop: `1px solid ${C.border}` }}>
        <div style={{ display: "flex", gap: 8 }}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={locked}
            placeholder={locked ? "Conversation terminée" : "Écrivez votre message…"}
            rows={2}
            maxLength={maxLen}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit(e);
              }
            }}
            style={{
              flex: 1,
              resize: "none",
              borderRadius: 12,
              border: `1px solid ${C.border}`,
              padding: "10px 12px",
              fontSize: 14,
              fontFamily: "inherit",
              outline: "none",
            }}
          />
          <button
            type="submit"
            disabled={locked || !input.trim()}
            style={{
              alignSelf: "flex-end",
              padding: "10px 16px",
              borderRadius: 12,
              border: "none",
              background: locked || !input.trim() ? C.border : C.teal,
              color: locked || !input.trim() ? C.muted : "#fff",
              fontWeight: 700,
              fontSize: 14,
              cursor: locked || !input.trim() ? "not-allowed" : "pointer",
            }}
          >
            Envoyer
          </button>
        </div>
        <p style={{ margin: "6px 0 0", fontSize: 11, color: C.muted, textAlign: "right" }}>
          {input.length}/{maxLen}
        </p>
      </form>
    </section>
  );
}
