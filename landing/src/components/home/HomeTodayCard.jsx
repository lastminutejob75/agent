export default function HomeTodayCard({
  hasNextAppointment,
  nextHour,
  nextPatient,
  nextReason,
  nextLabels,
  agendaForDay,
  onOpenAgenda,
  onOpenNextPatient,
  onMoveNext,
  onCancelNext,
  onRowClick,
  CardComponent,
  PillComponent,
  styles,
}) {
  const Card = CardComponent;
  const Pill = PillComponent;
  const S = styles;
  const remaining = Array.isArray(agendaForDay) ? agendaForDay.slice(0, 4) : [];

  return (
    <Card
      title="Ma journée"
      icon="calendar"
      action={<button type="button" style={S.linkBtn} onClick={onOpenAgenda}>Agenda complet ›</button>}
    >
      {hasNextAppointment ? (
        <div className="uwi-dashboard-today-next" style={S.todayNext}>
          <div style={S.todayNextDate}>
            <strong>{nextHour}</strong>
            <span>{nextLabels?.dow || "Aujourd'hui"}</span>
          </div>
          <div style={S.todayNextContent}>
            <span style={S.todayEyebrow}>Prochain patient</span>
            <strong style={S.todayPatient}>{nextPatient || "Patient"}</strong>
            <small style={S.todayReason}>{nextReason || "Consultation"}</small>
          </div>
          <div className="uwi-dashboard-today-actions" style={S.todayNextActions}>
            {typeof onOpenNextPatient === "function" ? (
              <button type="button" style={S.todayPrimaryBtn} onClick={onOpenNextPatient}>Voir la fiche</button>
            ) : null}
            {typeof onMoveNext === "function" ? (
              <button type="button" style={S.todaySecondaryBtn} onClick={onMoveNext}>Déplacer</button>
            ) : null}
            {typeof onCancelNext === "function" ? (
              <button type="button" style={S.todaySecondaryBtn} onClick={onCancelNext}>Annuler</button>
            ) : null}
          </div>
        </div>
      ) : (
        <p style={S.todayEmpty}>Aucun rendez-vous à venir.</p>
      )}

      <div style={S.todayDivider} />
      <div style={S.todayListHead}>
        <strong>Rendez-vous suivants</strong>
        <span>{remaining.length} affiché{remaining.length > 1 ? "s" : ""}</span>
      </div>
      {remaining.length === 0 ? (
        <p style={S.todayEmpty}>Aucun autre rendez-vous prévu aujourd&apos;hui.</p>
      ) : (
        <div style={S.todayList}>
          {remaining.map((row) => (
            <button key={row.key} type="button" onClick={() => onRowClick(row)} style={S.todayRow}>
              <b>{row.time}</b>
              <span style={S.todayRowContent}>
                <strong style={S.todayRowPatient}>{row.name}</strong>
                <small style={S.todayRowReason}>{row.reason}</small>
              </span>
              <Pill tone={row.status === "Confirmé" ? "green" : "blue"}>{row.status}</Pill>
            </button>
          ))}
        </div>
      )}
    </Card>
  );
}
