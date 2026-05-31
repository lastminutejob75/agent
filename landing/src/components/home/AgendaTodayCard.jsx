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
      title="RDV d'aujourd'hui"
      icon="calendar"
      action={<button type="button" style={S.linkBtn} onClick={onOpenAgenda}>Voir l&apos;agenda ›</button>}
    >
      {agendaForDay.length === 0 ? (
        <p style={{ margin: 0, color: "#66758B", fontWeight: 600 }}>Aucun rendez-vous prévu aujourd&apos;hui.</p>
      ) : agendaForDay.map((row) => (
        <button
          key={row.key}
          type="button"
          onClick={() => onRowClick(row)}
          style={S.agendaRow}
        >
          <b>{row.time}</b>
          <span><strong>{row.name}</strong><small>{row.reason}</small></span>
          <Pill tone={row.status === "Confirmé" ? "green" : "blue"}>{row.status}</Pill>
        </button>
      ))}
    </Card>
  );
}
