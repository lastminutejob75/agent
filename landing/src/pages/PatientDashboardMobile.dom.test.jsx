import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PatientDashboardMobile from "./PatientDashboardMobile";

afterEach(() => cleanup());

const baseProps = {
  displayHero: {
    name: "Jean Dupont",
    phone: "06 12 34 56 78",
    initials: "JD",
    gradient: "from-[#009CA4] to-[#004C69]",
    statusBucket: "active",
  },
  patientCabinetRow: {
    birth_date: "1990-05-12",
    treating_physician_name: "Dr Martin",
    treating_physician_city: "Lyon",
  },
  patientEmail: "jean@example.com",
  tenantPatientNotFound: false,
  onBackToList: vi.fn(),
  onOpenProfile: vi.fn(),
  onCall: vi.fn(),
  onWhatsApp: vi.fn(),
  onCreateConsultation: vi.fn(),
  onAddNote: vi.fn(),
  onAddDocument: vi.fn(),
  onViewDocuments: vi.fn(),
  onOpenHistoryModal: vi.fn(),
  tenantPatientPhone: "",
  notify: vi.fn(),
  onQuestionnaireApplied: vi.fn(),
  summaryRefreshNonce: 0,
  upcomingAppointments: [],
  pastAppointments: [],
  patientAgendaLoading: false,
  apptStatusLabel: () => "Confirmé",
  renderApptActions: () => null,
  patientNotes: [],
  notesLoading: false,
  noteDeletingId: null,
  onRemoveNote: vi.fn(),
  patientHistory: [],
  patientHistoryLoading: false,
  documents: [],
  documentsLoading: false,
  onPreviewDocument: vi.fn(),
  formatDocDate: (v) => String(v),
  patientConsultations: [],
  patientConsultationsLoading: false,
  consultationSaving: false,
  consultationDeletingId: null,
  lastSavedConsultationId: null,
  onEditConsultation: vi.fn(),
  onDownloadConsultationPdf: vi.fn(),
  onDeleteConsultation: vi.fn(),
  onDuplicateLatestConsultation: vi.fn(),
  editingPhone: false,
  phoneDraft: "",
  phoneSaving: false,
  phoneSaveDisabled: false,
  phoneConflictMessage: "",
  onStartEditPhone: vi.fn(),
  onCancelEditPhone: vi.fn(),
  onChangePhoneDraft: vi.fn(),
  onSavePhone: vi.fn(),
};

describe("PatientDashboardMobile", () => {
  it("renders patient header and single-scroll sections", () => {
    render(<PatientDashboardMobile {...baseProps} />);
    expect(screen.getByLabelText("Retour à la liste patients")).toBeTruthy();
    expect(screen.getByText("Jean Dupont")).toBeTruthy();
    expect(screen.getByText("Prochain rendez-vous")).toBeTruthy();
    expect(screen.getByText("Documents")).toBeTruthy();
    expect(screen.queryByText("Aperçu")).toBeNull();
  });

  it("renders appointments list with past dates in the same scroll", () => {
    const past = [{ start: new Date("2024-01-15T10:00:00"), key: "past-1" }];
    render(
      <PatientDashboardMobile
        {...baseProps}
        pastAppointments={past}
        upcomingAppointments={[
          {
            slot: { motif: "Consultation", source: "UWI" },
            start: new Date("2026-06-01T14:00:00"),
          },
        ]}
      />,
    );
    expect(screen.getByText("Tous les rendez-vous")).toBeTruthy();
  });
});
