import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../lib/api.js";

const T = {
  navy: "#071A33",
  teal: "#009CA4",
  tealDark: "#067A80",
  amber: "#B45309",
  amberBg: "#FFF7ED",
  amberBorder: "#FED7AA",
  green: "#067647",
  greenBg: "#ECFDF3",
  greenBorder: "#A7F3D0",
  muted: "#66758B",
  border: "#DDE7EF",
  red: "#B91C1C",
};

function prettyPhone(value) {
  const v = String(value || "").trim();
  const m = v.match(/^\+33(\d{9})$/);
  if (!m) return v;
  const d = m[1];
  return `+33 ${d[0]} ${d.slice(1, 3)} ${d.slice(3, 5)} ${d.slice(5, 7)} ${d.slice(7, 9)}`;
}

export default function InboundModeSwitch({ initialMode = "agent" }) {
  const navigate = useNavigate();
  const [mode, setMode] = useState(initialMode === "practitioner" ? "practitioner" : "agent");
  const [forwardReady, setForwardReady] = useState(true);
  const [forwardNumber, setForwardNumber] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api
      .tenantGetInboundMode()
      .then((data) => {
        if (cancelled || !data) return;
        setMode(data.inbound_mode === "practitioner" ? "practitioner" : "agent");
        setForwardReady(Boolean(data.forward_ready));
        setForwardNumber(String(data.forward_number || ""));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const practitioner = mode === "practitioner";

  const toggle = useCallback(async () => {
    if (saving) return;
    const next = practitioner ? "agent" : "practitioner";
    setSaving(true);
    setError("");
    try {
      const res = await api.tenantSetInboundMode(next);
      setMode(res?.inbound_mode === "practitioner" ? "practitioner" : "agent");
      if (res?.forward_number !== undefined) setForwardNumber(String(res.forward_number || ""));
      if (res?.forward_ready !== undefined) setForwardReady(Boolean(res.forward_ready));
    } catch (e) {
      setError(e?.message || "Impossible de changer le mode pour le moment.");
    } finally {
      setSaving(false);
    }
  }, [practitioner, saving]);

  const wrap = {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 14,
    flexWrap: "wrap",
    padding: "14px 16px",
    borderRadius: 14,
    border: `1.5px solid ${practitioner ? T.amberBorder : T.greenBorder}`,
    background: practitioner ? T.amberBg : T.greenBg,
    marginBottom: 14,
  };

  return (
    <section style={wrap}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 11,
            flexShrink: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: practitioner ? "#FDE9D2" : "#D1FADF",
            color: practitioner ? T.amber : T.green,
            fontSize: 20,
          }}
          aria-hidden
        >
          {practitioner ? "☎" : "🤖"}
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 800, color: T.navy }}>
            {practitioner ? "Vous prenez les appels" : "Clara prend les appels"}
          </div>
          <div style={{ fontSize: 12.5, color: T.muted, lineHeight: 1.5 }}>
            {practitioner
              ? `Les appels sur votre ligne UWI sonnent directement ${forwardNumber ? `sur ${prettyPhone(forwardNumber)}` : "sur votre ligne"}. L'assistant ne décroche pas.`
              : "L'assistant vocal répond aux appels entrants et transfère si besoin."}
          </div>
          {error ? <div style={{ fontSize: 12, color: T.red, marginTop: 4 }}>{error}</div> : null}
          {!forwardReady && !practitioner ? (
            <button
              type="button"
              onClick={() => navigate("/app/settings")}
              style={{ marginTop: 4, fontSize: 12, color: T.tealDark, background: "none", border: "none", padding: 0, cursor: "pointer", textDecoration: "underline" }}
            >
              Configurez un numéro de renvoi pour pouvoir reprendre les appels
            </button>
          ) : null}
        </div>
      </div>

      <button
        type="button"
        onClick={toggle}
        disabled={saving || (!practitioner && !forwardReady)}
        style={{
          flexShrink: 0,
          padding: "11px 18px",
          borderRadius: 11,
          border: "none",
          fontSize: 13.5,
          fontWeight: 700,
          cursor: saving || (!practitioner && !forwardReady) ? "not-allowed" : "pointer",
          color: "#fff",
          background: practitioner
            ? `linear-gradient(135deg, ${T.teal}, ${T.tealDark})`
            : "#0f172a",
          opacity: saving || (!practitioner && !forwardReady) ? 0.6 : 1,
          whiteSpace: "nowrap",
        }}
      >
        {saving
          ? "..."
          : practitioner
            ? "Rendre la main à Clara"
            : "Reprendre les appels"}
      </button>
    </section>
  );
}
