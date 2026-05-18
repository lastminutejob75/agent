export default function HomeHeroSection({
  openHandoffsCount,
  rdvCreatedToday,
  aiCount,
  onOpenHandledRequests,
  onOpenRdvToday,
  onOpenReminders,
  ClaraPhotoComponent,
  PillComponent,
  IconRenderer,
  styles,
}) {
  const S = styles;
  const Pill = PillComponent;
  return (
    <div style={S.hero}>
      <div style={S.heroLeft}>
        <ClaraPhotoComponent />
        <div>
          <div style={S.heroTitleRow}>
            <h2 style={S.heroTitle}>Clara</h2>
            <Pill tone="green">Actif</Pill>
          </div>
          <p style={S.meta}>{IconRenderer("phone", 14)}06 90 00 01 58 · {IconRenderer("message", 14)}Aucun email</p>
          <div style={S.pills}>
            <Pill icon="check" onClick={onOpenHandledRequests}>
              {openHandoffsCount || 18} demandes traitees
            </Pill>
            <Pill tone="blue" icon="plus" onClick={onOpenRdvToday}>
              {rdvCreatedToday} RDV pris aujourd'hui
            </Pill>
            <Pill tone="green" icon="message" onClick={onOpenReminders}>
              {Math.max(1, Math.round(aiCount / 4))} rappels prepares
            </Pill>
          </div>
        </div>
      </div>
    </div>
  );
}
