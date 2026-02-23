import { useOutletContext } from "react-router-dom";

export default function AppProfil() {
  const { me } = useOutletContext() || {};
  const initials = (me?.tenant_name || "U").split(/\s+/).map((w) => w[0]).join("").toUpperCase().slice(0, 2);

  return (
    <div className="client-dash cd-page">
      <div className="client-dash cd-card">
        <div style={{ display: "flex", alignItems: "center", gap: "20px", padding: "28px", borderBottom: "1px solid var(--border)" }}>
          <div className="client-dash cd-doc-av" style={{ width: 66, height: 66, fontSize: 22 }}>{initials}</div>
          <div>
            <div style={{ fontSize: "18px", fontWeight: 800, color: "var(--navy)", letterSpacing: "-0.025em" }}>{me?.tenant_name || "Mon Cabinet"}</div>
            <div style={{ fontSize: "12.5px", color: "var(--muted)", marginTop: "3px" }}>{me?.contact_email || me?.email || "—"}</div>
            <div style={{ display: "inline-flex", alignItems: "center", gap: "5px", marginTop: "8px", fontSize: "11px", fontWeight: 700, background: "var(--green-lt)", color: "#059669", padding: "4px 11px", borderRadius: "8px" }}>✓ Compte certifié</div>
          </div>
        </div>
        <div style={{ padding: "28px", display: "flex", flexDirection: "column", gap: "20px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--muted)", marginBottom: "7px" }}>Nom du cabinet</label>
              <input readOnly className="client-dash" style={{ width: "100%", padding: "12px 15px", border: "1.5px solid var(--border)", borderRadius: 11, fontFamily: "var(--font)", fontSize: "13.5px", color: "var(--navy)", background: "var(--card)" }} value={me?.tenant_name || ""} />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--muted)", marginBottom: "7px" }}>Email</label>
              <input readOnly className="client-dash" style={{ width: "100%", padding: "12px 15px", border: "1.5px solid var(--border)", borderRadius: 11, fontFamily: "var(--font)", fontSize: "13.5px", color: "var(--navy)", background: "var(--card)" }} value={me?.email || ""} />
            </div>
          </div>
          <a href="/app/settings" className="client-dash cd-bill-cta" style={{ textDecoration: "none", textAlign: "center" }}>Modifier dans Paramètres</a>
        </div>
      </div>
    </div>
  );
}
