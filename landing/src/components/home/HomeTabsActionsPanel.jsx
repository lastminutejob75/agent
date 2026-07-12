export default function HomeTabsActionsPanel({
  onPriority,
  onDayAgenda,
  onMessages,
  onCreateConsultation,
  onClaraSettings,
  styles,
  BtnComponent,
}) {
  const S = styles;
  const Btn = BtnComponent;
  return (
    <section style={S.panel}>
      <div style={S.quickActionsHead}>
        <strong>Actions rapides</strong>
        <button type="button" onClick={onClaraSettings} style={S.claraSettingsLink}>
          Paramètres Clara
        </button>
      </div>
      <div className="uwi-dashboard-quick-actions" style={S.quickActions}>
        <Btn variant="dark" icon="warn" onClick={onPriority}>Demandes</Btn>
        <Btn icon="calendar" onClick={onDayAgenda}>Agenda du jour</Btn>
        <Btn variant="teal" icon="doc" onClick={onCreateConsultation}>Dicter une consultation</Btn>
        <Btn variant="green" icon="message" onClick={onMessages}>Messages patients</Btn>
      </div>
    </section>
  );
}
