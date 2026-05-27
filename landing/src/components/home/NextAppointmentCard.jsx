export default function NextAppointmentCard({
  hasAppointment = true,
  nextLabels,
  nextHour,
  nextPatient,
  nextReason,
  nextSource,
  onMove,
  onCancel,
  onOpenAgenda,
  CardComponent,
  PillComponent,
  BtnComponent,
  styles,
}) {
  const S = styles;
  const Card = CardComponent;
  const Pill = PillComponent;
  const Btn = BtnComponent;
  return (
    <Card title="Prochain rendez-vous" icon="calendar">
      {!hasAppointment ? (
        <p style={{ margin: 0, color: "#66758B", fontWeight: 600, lineHeight: 1.5 }}>
          Aucun rendez-vous à venir. Les prochains RDV pris par Clara ou via votre agenda apparaîtront ici.
        </p>
      ) : (
      <div className="uwi-dashboard-rdv" style={S.rdv}>
        <div style={S.dateBlock}>
          <b>{nextLabels.day}</b>
          <span>{nextLabels.monthYear}</span>
          <strong>{nextLabels.dow}</strong>
        </div>
        <div style={{ flex: 1 }}>
          <div style={S.rdvTop}>
            <b>{nextHour}</b><span>(20 min)</span><strong>{nextPatient || "Patient"}</strong><Pill tone="green">Confirme</Pill>
          </div>
          <div className="uwi-dashboard-rdv-details" style={S.rdvDetails}>
            {[["Motif", nextReason || "—"], ["Source", nextSource || "—"], ["Preference", "—"], ["Canal", "Telephone"]].map(([k, v]) => (
              <p key={k}><span>{k}</span><b>{v}</b></p>
            ))}
          </div>
          <div style={S.rowBtns}>
            <Btn variant="green" icon="calendar" onClick={onMove}>Deplacer</Btn>
            <Btn variant="orange" icon="warn" onClick={onCancel}>Annuler</Btn>
            <Btn icon="calendar" onClick={onOpenAgenda}>Agenda</Btn>
          </div>
        </div>
      </div>
      )}
    </Card>
  );
}
