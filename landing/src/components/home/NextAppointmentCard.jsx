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
        <div className="uwi-dashboard-rdv-main" style={S.rdvMain}>
          <div className="uwi-dashboard-rdv-date" style={S.dateBlock}>
            <b className="uwi-dashboard-rdv-date-day">{nextLabels.day}</b>
            <span>{nextLabels.monthYear}</span>
            <strong>{nextLabels.dow}</strong>
          </div>
          <div className="uwi-dashboard-rdv-body">
            <div className="uwi-dashboard-rdv-top" style={S.rdvTop}>
              <div className="uwi-dashboard-rdv-headline">
                <b className="uwi-dashboard-rdv-hour">{nextHour}</b>
                <span className="uwi-dashboard-rdv-duration">(20 min)</span>
                <strong className="uwi-dashboard-rdv-patient">{nextPatient || "Patient"}</strong>
              </div>
              <Pill tone="green">Confirme</Pill>
            </div>
            <div className="uwi-dashboard-rdv-details" style={S.rdvDetails}>
              {[["Motif", nextReason || "—"], ["Source", nextSource || "—"], ["Préférence", "—"], ["Canal", "Téléphone"]].map(([k, v]) => (
                <p key={k} className="uwi-dashboard-rdv-detail">
                  <span>{k}</span>
                  <b>{v}</b>
                </p>
              ))}
            </div>
          </div>
        </div>
        <div className="uwi-dashboard-rdv-actions" style={S.rowBtns}>
          {typeof onMove === "function" ? <Btn variant="green" icon="calendar" onClick={onMove}>Deplacer</Btn> : null}
          {typeof onCancel === "function" ? <Btn variant="orange" icon="warn" onClick={onCancel}>Annuler</Btn> : null}
          <Btn icon="calendar" onClick={onOpenAgenda}>Agenda</Btn>
        </div>
      </div>
      )}
    </Card>
  );
}
