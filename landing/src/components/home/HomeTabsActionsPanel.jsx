export default function HomeTabsActionsPanel({
  tab,
  setTab,
  onPriority,
  onDayAgenda,
  onMessages,
  onClaraSettings,
  styles,
  BtnComponent,
}) {
  const S = styles;
  const Btn = BtnComponent;
  return (
    <section style={S.panel}>
      <div className="uwi-dashboard-tabs" style={S.tabs}>
        {[["overview", "Vue d'ensemble"], ["rdv", "Rendez-vous"], ["history", "Historique"]].map(([id, label]) => (
          <button key={id} type="button" onClick={() => setTab(id)} style={{ ...S.tab, ...(tab === id ? S.tabActive : {}) }}>{label}</button>
        ))}
      </div>
      <div className="uwi-dashboard-quick-actions" style={S.quickActions}>
        <Btn variant="dark" icon="warn" onClick={onPriority}>Traiter les demandes prioritaires</Btn>
        <Btn icon="calendar" onClick={onDayAgenda}>Voir les rendez-vous du jour</Btn>
        <Btn variant="green" icon="message" onClick={onMessages}>Consulter les messages patients</Btn>
      </div>
      <div style={S.panelFooter}>
        <button type="button" onClick={onClaraSettings} style={S.claraSettingsLink}>
          <span style={S.claraSettingsIcon}>⚙</span>
          Parametres Clara
        </button>
      </div>
    </section>
  );
}
