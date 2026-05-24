export default function AgendaTodayCard({
  agendaForDay,
  onOpenAgenda,
  onRowClick,
  CardComponent,
  PillComponent,
  styles,
}) {
  const S = styles;
  const Card = CardComponent;
  const Pill = PillComponent;
  return (
    <Card
      title="Agenda du jour"
      icon="calendar"
      action={<button type="button" style={S.linkBtn} onClick={onOpenAgenda}>Voir l'agenda ›</button>}
    >
      {agendaForDay.length === 0 ? (
        <p style={{ margin: 0, color: "#66758B", fontWeight: 600 }}>Aucun rendez-vous prévu aujourd'hui.</p>
      ) : agendaForDay.map(([time, name, reason, status]) => (
        <button key={`${time}-${name}`} type="button" onClick={() => onRowClick(name)} style={S.agendaRow}>
          <b>{time}</b>
          <span><strong>{name}</strong><small>{reason}</small></span>
          <Pill tone={status === "Confirme" ? "green" : "blue"}>{status}</Pill>
        </button>
      ))}
    </Card>
  );
}
