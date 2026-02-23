export default function AppActions() {
  return (
    <div className="client-dash cd-page-inner">
      <div className="client-dash cd-card">
        <div className="client-dash cd-ch">
          <div className="client-dash cd-ch-left">
            <div className="client-dash cd-ch-ico cd-ico-r">✅</div>
            <div>
              <div className="client-dash cd-ch-title">Actions en attente</div>
            </div>
          </div>
        </div>
        <div style={{ padding: "56px", textAlign: "center", color: "var(--muted)" }}>
          Rappels · Ordonnances · Messages
        </div>
      </div>
    </div>
  );
}
