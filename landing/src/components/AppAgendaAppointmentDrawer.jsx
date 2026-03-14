import React from "react";

const BORDER = "#e5e7eb";
const TEXT = "#111827";
const MUTED = "#6b7280";

const S = {
  modalOverlay: {
    position: "fixed",
    inset: 0,
    background: "rgba(15,23,42,.38)",
    display: "flex",
    justifyContent: "flex-end",
    zIndex: 50,
  },
  modalCard: {
    width: "min(560px, 100vw)",
    height: "100%",
    background: "#fff",
    borderLeft: `1px solid ${BORDER}`,
    boxShadow: "-12px 0 40px rgba(15,23,42,.12)",
    display: "flex",
    flexDirection: "column",
  },
  modalHeader: {
    padding: "18px 18px 14px",
    borderBottom: `1px solid ${BORDER}`,
    background: "#fafafa",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 12,
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: 700,
    color: TEXT,
  },
  modalSub: {
    marginTop: 4,
    fontSize: 12,
    color: MUTED,
  },
  closeButton: {
    border: `1px solid ${BORDER}`,
    background: "#fff",
    color: "#475569",
    borderRadius: 10,
    width: 34,
    height: 34,
    cursor: "pointer",
  },
  modalBody: {
    padding: 18,
    display: "flex",
    flexDirection: "column",
    gap: 16,
    overflowY: "auto",
  },
  actionRow: {
    display: "flex",
    gap: 10,
    flexWrap: "wrap",
  },
  actionButtonPrimary: {
    border: "none",
    background: "linear-gradient(135deg, #3b82f6, #2563eb)",
    color: "#fff",
    borderRadius: 10,
    padding: "10px 12px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
  },
  actionButton: {
    border: `1px solid ${BORDER}`,
    background: "#fff",
    color: "#475569",
    borderRadius: 10,
    padding: "10px 12px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
  },
  actionDangerButton: {
    border: "1px solid #fecaca",
    background: "#fff1f2",
    color: "#b91c1c",
    borderRadius: 10,
    padding: "10px 12px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
  },
  successInline: {
    borderRadius: 12,
    border: "1px solid #a7f3d0",
    background: "#ecfdf5",
    color: "#047857",
    padding: "10px 12px",
    fontSize: 13,
    fontWeight: 600,
  },
  detailTopGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: 12,
  },
  detailInfoCard: {
    border: `1px solid ${BORDER}`,
    borderRadius: 14,
    background: "#fff",
    padding: "14px 16px",
  },
  detailLabel: {
    fontSize: 12,
    color: MUTED,
    marginBottom: 8,
  },
  detailValue: {
    fontSize: 14,
    fontWeight: 700,
    color: TEXT,
  },
  statusBadge: {
    borderRadius: 999,
    padding: "5px 10px",
    fontSize: 10,
    fontWeight: 800,
    border: "1px solid transparent",
    display: "inline-flex",
    alignItems: "center",
    letterSpacing: ".02em",
  },
  detailSection: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  detailSectionTitle: {
    fontSize: 14,
    fontWeight: 700,
    color: TEXT,
  },
  detailText: {
    fontSize: 13,
    lineHeight: 1.6,
    color: "#4b5563",
  },
  transcriptBox: {
    border: `1px solid ${BORDER}`,
    borderRadius: 14,
    background: "#f8fafc",
    padding: 14,
  },
  rescheduleBox: {
    border: `1px solid ${BORDER}`,
    borderRadius: 14,
    background: "#f8fafc",
    padding: 14,
    display: "flex",
    flexDirection: "column",
    gap: 10,
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
};

export default function AppAgendaAppointmentDrawer({
  appointment,
  isConnected,
  actionMessage,
  slotsLoading,
  slotOptions,
  selectedNewSlotId,
  appointmentActionLoading,
  onClose,
  onCopyDetails,
  onGoToHoraires,
  onCancelAppointment,
  onConnectGoogle,
  onSlotChange,
  onReschedule,
}) {
  if (!appointment) return null;

  return (
    <div style={S.modalOverlay} onClick={onClose}>
      <div style={S.modalCard} onClick={(event) => event.stopPropagation()}>
        <div style={S.modalHeader}>
          <div>
            <div style={S.modalTitle}>Detail du rendez-vous</div>
            <div style={S.modalSub}>{appointment.patient || "Patient"}</div>
          </div>
          <button type="button" style={S.closeButton} onClick={onClose}>
            X
          </button>
        </div>

        <div style={S.modalBody}>
          <div style={S.actionRow}>
            <button type="button" style={S.actionButtonPrimary} onClick={onCopyDetails}>
              Copier les details
            </button>
            <button type="button" style={S.actionButton} onClick={onGoToHoraires}>
              Modifier mes horaires
            </button>
            {appointment.canCancel ? (
              <button
                type="button"
                style={S.actionDangerButton}
                disabled={appointmentActionLoading}
                onClick={onCancelAppointment}
              >
                Annuler le RDV
              </button>
            ) : null}
            {!isConnected ? (
              <button type="button" style={S.actionButton} onClick={onConnectGoogle}>
                Connecter Google
              </button>
            ) : null}
          </div>

          {actionMessage ? <div style={S.successInline}>{actionMessage}</div> : null}

          <div className="agenda-detail-grid" style={S.detailTopGrid}>
            <div style={S.detailInfoCard}>
              <div style={S.detailLabel}>Heure</div>
              <div style={S.detailValue}>{appointment.displayTime || "-"}</div>
            </div>
            <div style={S.detailInfoCard}>
              <div style={S.detailLabel}>Duree</div>
              <div style={S.detailValue}>{appointment.duration || "-"} min</div>
            </div>
            <div style={S.detailInfoCard}>
              <div style={S.detailLabel}>Statut</div>
              <div style={S.detailValue}>
                <span
                  style={{
                    ...S.statusBadge,
                    background: appointment.status.bg,
                    color: appointment.status.color,
                    borderColor: appointment.status.border,
                  }}
                >
                  {appointment.status.label}
                </span>
              </div>
            </div>
          </div>

          <div style={S.detailSection}>
            <div style={S.detailSectionTitle}>Motif</div>
            <div style={S.detailText}>{appointment.type || "Consultation"}</div>
          </div>

          <div style={S.detailSection}>
            <div style={S.detailSectionTitle}>Source</div>
            <div style={S.detailText}>{appointment.sourceLabel || "UWI"}</div>
          </div>

          <div style={S.detailSection}>
            <div style={S.detailSectionTitle}>Informations</div>
            <div style={S.transcriptBox}>
              <div style={S.detailText}>{appointment.detailLine || "Aucun detail supplementaire."}</div>
            </div>
          </div>

          {appointment.canReschedule ? (
            <div style={S.detailSection}>
              <div style={S.detailSectionTitle}>Deplacer ce rendez-vous</div>
              <div style={S.rescheduleBox}>
                {slotsLoading ? (
                  <div style={S.detailText}>Chargement des creneaux disponibles...</div>
                ) : slotOptions.length > 0 ? (
                  <>
                    <select value={selectedNewSlotId} onChange={(event) => onSlotChange(event.target.value)} style={S.input}>
                      {slotOptions.map((slot) => (
                        <option key={slot.slot_id} value={slot.slot_id}>
                          {slot.label}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      style={S.actionButtonPrimary}
                      disabled={!selectedNewSlotId || appointmentActionLoading}
                      onClick={onReschedule}
                    >
                      Deplacer vers ce creneau
                    </button>
                  </>
                ) : (
                  <div style={S.detailText}>Aucun autre creneau libre disponible pour le moment.</div>
                )}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
