function formatShortDate(d) {
  if (!(d instanceof Date) || Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" }).replace(".", "");
}

export default function UpcomingAppointmentsCard({
  rows,
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
      title="Prochains rendez-vous"
      icon="calendar"
      action={<button type="button" style={S.linkBtn} onClick={onOpenAgenda}>Voir l&apos;agenda ›</button>}
    >
      {rows.length === 0 ? (
        <p style={{ margin: 0, color: "#66758B", fontWeight: 600 }}>Aucun rendez-vous planifié sur les 14 prochains jours.</p>
      ) : rows.map((row) => (
        <button
          key={row.key}
          type="button"
          onClick={() => onRowClick(row)}
          style={S.agendaRow}
        >
          <b>{row.time}</b>
          <span className="uwi-dashboard-agenda-row-text">
            <strong>{row.name}</strong>
            <small>{row.dateLabel ? `${row.dateLabel} · ${row.reason}` : row.reason}</small>
          </span>
          <Pill tone={row.status === "Confirmé" ? "green" : "blue"}>{row.status}</Pill>
        </button>
      ))}
    </Card>
  );
}

export { formatShortDate };
