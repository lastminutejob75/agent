const RDV_DETAILS = [
  ["Motif", "nextReason"],
  ["Source", "nextSource"],
  ["Préférence", null],
  ["Canal", "canal"],
];

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
}) {
  const Card = CardComponent;
  const Pill = PillComponent;
  const Btn = BtnComponent;

  const detailValues = {
    nextReason: nextReason || "—",
    nextSource: nextSource || "—",
    canal: "Téléphone",
  };

  const actionBtnStyle = {
    flex: 1,
    width: "auto",
    minWidth: 0,
    justifyContent: "center",
    padding: "0 8px",
    fontSize: 12,
  };

  return (
    <Card title="Prochain rendez-vous" icon="calendar">
      {!hasAppointment ? (
        <p style={{ margin: 0, color: "#66758B", fontWeight: 600, lineHeight: 1.5 }}>
          Aucun rendez-vous à venir. Les prochains RDV pris par Clara ou via votre agenda apparaîtront ici.
        </p>
      ) : (
        <div className="flex w-full flex-col gap-3">
          <div className="flex w-full items-center gap-3">
            <div className="flex h-[78px] w-[72px] shrink-0 flex-col items-center justify-center rounded-[14px] bg-gradient-to-br from-[#00A9AC] to-[#06455C] text-center text-white shadow-[0_10px_22px_rgba(0,156,164,0.24)] sm:h-[108px] sm:w-[108px] sm:rounded-2xl">
              <b className="block w-full text-center text-2xl leading-none sm:text-[34px]">{nextLabels.day}</b>
              <span className="mt-1 block w-full text-center text-[11px] capitalize leading-tight sm:text-sm">
                {nextLabels.monthYear}
              </span>
              <strong className="mt-1 block w-full text-center text-[11px] font-extrabold leading-none sm:text-sm">
                {nextLabels.dow}
              </strong>
            </div>

            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                <b className="text-[22px] font-extrabold leading-none text-[#071A33] sm:text-[30px]">{nextHour}</b>
                <span className="text-xs font-semibold text-[#66758B] sm:text-sm">(20 min)</span>
              </div>
              <strong className="mt-1 block truncate text-sm font-extrabold text-[#071A33] sm:text-base">
                {nextPatient || "Patient"}
              </strong>
              <div className="mt-2">
                <Pill tone="green">Confirme</Pill>
              </div>
            </div>
          </div>

          <div className="grid w-full grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4 sm:gap-3">
            {RDV_DETAILS.map(([label, key]) => (
              <div key={label} className="min-w-0">
                <span className="block text-[10px] font-bold uppercase tracking-wide text-[#66758B] sm:text-xs">
                  {label}
                </span>
                <b className="mt-0.5 block truncate text-xs font-extrabold text-[#071A33] sm:text-sm">
                  {key ? detailValues[key] : "—"}
                </b>
              </div>
            ))}
          </div>

          <div className="flex w-full gap-2">
            {typeof onMove === "function" ? (
              <Btn variant="green" icon="calendar" onClick={onMove} style={actionBtnStyle}>
                Deplacer
              </Btn>
            ) : null}
            {typeof onCancel === "function" ? (
              <Btn variant="orange" icon="warn" onClick={onCancel} style={actionBtnStyle}>
                Annuler
              </Btn>
            ) : null}
            <Btn icon="calendar" onClick={onOpenAgenda} style={actionBtnStyle}>
              Agenda
            </Btn>
          </div>
        </div>
      )}
    </Card>
  );
}
