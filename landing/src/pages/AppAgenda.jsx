export default function AppAgenda() {
  return (
    <div className="client-dash cd-page-inner">
      <div className="client-dash cd-card">
        <div className="client-dash cd-ch">
          <div className="client-dash cd-ch-left">
            <div className="client-dash cd-ch-ico cd-ico-t">📆</div>
            <div>
              <div className="client-dash cd-ch-title">Agenda complet</div>
            </div>
          </div>
        </div>
        <div style={{ padding: "56px", textAlign: "center", color: "var(--muted)" }}>
          Vue hebdomadaire et mensuelle
        </div>
      </div>
    </div>
  );
}
