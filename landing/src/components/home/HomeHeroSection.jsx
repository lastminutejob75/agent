import { assistantDisplayFromMe } from "../../lib/assistantDisplay.js";

export default function HomeHeroSection({
  openHandoffsCount,
  rdvCreatedToday,
  aiCount,
  assistantName,
  assistantLive,
  voiceNumber,
  contactEmail,
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

  const {
    assistantName: displayName,
    displayPhone,
    displayEmail,
    statusLabel,
    statusTone,
  } = assistantDisplayFromMe({
    assistant_name: assistantName,
    assistant_live: assistantLive,
    voice_number: voiceNumber,
    contact_email: contactEmail,
  });

  return (
    <div className="uwi-dashboard-hero" style={S.hero}>
      <div className="uwi-dashboard-hero-left" style={S.heroLeft}>
        <ClaraPhotoComponent />
        <div>
          <div style={S.heroTitleRow}>
            <h2 style={S.heroTitle}>{displayName}</h2>
            <Pill tone={statusTone}>{statusLabel}</Pill>
          </div>
          <p style={S.meta}>
            {IconRenderer("phone", 14)}{displayPhone} · {IconRenderer("message", 14)}{displayEmail}
          </p>
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
