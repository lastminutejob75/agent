export default function NextAppointmentCard({
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
      <div style={S.rdv}>
        <div style={S.dateBlock}>
          <b>{nextLabels.day}</b>
          <span>{nextLabels.monthYear}</span>
          <strong>{nextLabels.dow}</strong>
        </div>
        <div style={{ flex: 1 }}>
          <div style={S.rdvTop}>
            <b>{nextHour}</b><span>(20 min)</span><strong>{nextPatient || "Dr Martin"}</strong><Pill tone="green">Confirme</Pill>
          </div>
          <div style={S.rdvDetails}>
            {[["Motif", nextReason], ["Source", nextSource], ["Preference", "Matin"], ["Canal", "Telephone"]].map(([k, v]) => (
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
    </Card>
  );
}
