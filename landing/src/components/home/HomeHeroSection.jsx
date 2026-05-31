import { assistantDisplayFromMe } from "../../lib/assistantDisplay.js";

export default function HomeHeroSection({
  handledRequestsCount,
  rdvCreatedToday,
  inProgressRequestsCount,
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
              {handledRequestsCount} demande{handledRequestsCount > 1 ? "s" : ""} traitée{handledRequestsCount > 1 ? "s" : ""}
            </Pill>
            <Pill tone="blue" icon="plus" onClick={onOpenRdvToday} title="Demandes confirmées aujourd'hui pour des dates futures (Clara, page publique, cabinet)">
              {rdvCreatedToday} prise{rdvCreatedToday > 1 ? "s" : ""} de RDV aujourd&apos;hui
            </Pill>
            <Pill tone="green" icon="message" onClick={onOpenReminders}>
              {inProgressRequestsCount} en cours
            </Pill>
          </div>
        </div>
      </div>
    </div>
  );
}
