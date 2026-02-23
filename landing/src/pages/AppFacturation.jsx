export default function AppFacturation() {
  return (
    <div className="client-dash cd-page-inner">
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "18px", marginBottom: "20px" }}>
        <div className="client-dash cd-card" style={{ padding: "22px" }}>
          <div style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--muted)", marginBottom: "8px" }}>Forfait actuel</div>
          <div style={{ fontSize: "30px", fontWeight: 800, color: "var(--navy)", letterSpacing: "-0.03em", marginBottom: "4px" }}>Growth — 149€</div>
          <div style={{ fontSize: "12px", color: "var(--muted)" }}>800 min incluses · 0,17€/min suppl.</div>
        </div>
        <div className="client-dash cd-card" style={{ padding: "22px" }}>
          <div style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--muted)", marginBottom: "8px" }}>Facture estimée — Ce mois</div>
          <div style={{ fontSize: "30px", fontWeight: 800, color: "var(--navy)", letterSpacing: "-0.03em" }}>149 €</div>
          <div style={{ display: "inline-flex", alignItems: "center", gap: "5px", marginTop: "10px", fontSize: "12px", fontWeight: 700, background: "var(--green-lt)", color: "#059669", padding: "5px 12px", borderRadius: "9px" }}>✓ Aucun dépassement prévu</div>
        </div>
      </div>
      <div className="client-dash cd-card">
        <div className="client-dash cd-ch">
          <div className="client-dash cd-ch-left">
            <div className="client-dash cd-ch-ico cd-ico-t">🧾</div>
            <div>
              <div className="client-dash cd-ch-title">Historique des factures</div>
            </div>
          </div>
        </div>
        <div style={{ padding: "24px", textAlign: "center", color: "var(--muted)" }}>
          Historique à connecter à l'API facturation
        </div>
      </div>
    </div>
  );
}
