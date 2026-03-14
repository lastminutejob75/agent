const TEXT = "#111827";
const MUTED = "#6b7280";
const BORDER = "#e5e7eb";
const BG = "#f5f6f8";
const CARD = "#ffffff";

const S = {
  setupGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
    gap: 16,
  },
  setupCard: {
    background: CARD,
    border: `1px solid ${BORDER}`,
    borderRadius: 14,
    padding: 18,
    boxShadow: "0 2px 10px rgba(15,23,42,.035)",
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  setupTitle: {
    fontSize: 17,
    fontWeight: 800,
    color: TEXT,
  },
  setupText: {
    fontSize: 13,
    color: MUTED,
    lineHeight: 1.5,
  },
  code: {
    display: "inline-block",
    marginTop: 4,
    padding: "2px 6px",
    borderRadius: 8,
    background: BG,
    border: `1px solid ${BORDER}`,
    color: TEXT,
    fontSize: 12,
  },
  input: {
    width: "100%",
    borderRadius: 12,
    border: `1px solid ${BORDER}`,
    background: "#fff",
    padding: "12px 14px",
    fontSize: 14,
    color: TEXT,
    outline: "none",
  },
  primaryButton: {
    border: "none",
    borderRadius: 12,
    padding: "10px 18px",
    background: "linear-gradient(135deg, #3b82f6, #2563eb)",
    color: "#fff",
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  secondaryButton: {
    border: `1px solid ${BORDER}`,
    borderRadius: 12,
    padding: "11px 16px",
    background: "#fff",
    color: "#475569",
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  successBox: {
    borderRadius: 12,
    border: "1px solid #a7f3d0",
    background: "#ecfdf5",
    color: "#047857",
    padding: "10px 12px",
    fontSize: 13,
    fontWeight: 600,
  },
  errorInline: {
    borderRadius: 12,
    border: "1px solid #fecaca",
    background: "#fff1f2",
    color: "#b91c1c",
    padding: "10px 12px",
    fontSize: 13,
  },
};

export default function AppAgendaSetupSection({
  serviceAccountEmail,
  calendarId,
  setCalendarId,
  onVerifyGoogle,
  verifyLoading,
  verifySuccess,
  verifyError,
  contactSoftware,
  setContactSoftware,
  contactOther,
  setContactOther,
  onContactRequest,
  contactLoading,
  contactSent,
  onActivateNone,
  noneLoading,
  noneDone,
}) {
  return (
    <div style={S.setupGrid}>
      <div style={S.setupCard}>
        <div style={S.setupTitle}>Connecter Google Calendar</div>
        <div style={S.setupText}>
          Partagez votre calendrier avec <code style={S.code}>{serviceAccountEmail}</code>, puis collez son identifiant.
        </div>
        <input
          type="text"
          value={calendarId}
          onChange={(event) => setCalendarId(event.target.value)}
          placeholder="xxx@group.calendar.google.com"
          style={S.input}
        />
        <button type="button" onClick={onVerifyGoogle} disabled={verifyLoading || !calendarId.trim()} style={S.primaryButton}>
          {verifyLoading ? "Verification..." : "Verifier et connecter"}
        </button>
        {verifySuccess ? <div style={S.successBox}>Agenda connecte avec succes.</div> : null}
        {verifyError ? <div style={S.errorInline}>{verifyError}</div> : null}
      </div>

      <div style={S.setupCard}>
        <div style={S.setupTitle}>Logiciel metier</div>
        <div style={S.setupText}>Pabau, Maiia, Doctolib ou autre logiciel cabinet: notre equipe finalise la connexion avec vous.</div>
        <select value={contactSoftware} onChange={(event) => setContactSoftware(event.target.value)} style={S.input}>
          <option value="pabau">Pabau</option>
          <option value="maiia">Maiia</option>
          <option value="doctolib">Doctolib</option>
          <option value="autre">Autre</option>
        </select>
        {contactSoftware === "autre" ? (
          <input
            type="text"
            value={contactOther}
            onChange={(event) => setContactOther(event.target.value)}
            placeholder="Precisez le logiciel"
            style={S.input}
          />
        ) : null}
        <button type="button" onClick={onContactRequest} disabled={contactLoading} style={S.secondaryButton}>
          {contactLoading ? "Envoi..." : "Demander le setup"}
        </button>
        {contactSent ? <div style={S.successBox}>Demande envoyee. Notre equipe vous recontacte.</div> : null}
      </div>

      <div style={S.setupCard}>
        <div style={S.setupTitle}>Mode sans agenda externe</div>
        <div style={S.setupText}>
          Si vous ne connectez pas encore Google, UWI garde son propre agenda interne et continue de prendre les rendez-vous.
        </div>
        <button type="button" onClick={onActivateNone} disabled={noneLoading} style={S.secondaryButton}>
          {noneLoading ? "Activation..." : "Activer ce mode"}
        </button>
        {noneDone ? <div style={S.successBox}>Mode agenda interne active.</div> : null}
      </div>
    </div>
  );
}
