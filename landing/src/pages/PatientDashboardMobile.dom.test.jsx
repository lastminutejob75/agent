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
  activeView: "overview",
  setActiveView: vi.fn(),
  onBackToList: vi.fn(),
  onOpenProfile: vi.fn(),
  onCall: vi.fn(),
  onWhatsApp: vi.fn(),
  onSms: vi.fn(),
  onAddNote: vi.fn(),
  onAddDocument: vi.fn(),
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
};

describe("PatientDashboardMobile", () => {
  it("renders patient header and tabs", () => {
    render(<PatientDashboardMobile {...baseProps} />);
    expect(screen.getByLabelText("Retour à la liste patients")).toBeTruthy();
    expect(screen.getByText("Jean Dupont")).toBeTruthy();
    expect(screen.getByText("Prochain rendez-vous")).toBeTruthy();
    expect(screen.getByText("Documents")).toBeTruthy();
  });

  it("renders appointments tab with past dates", () => {
    const past = [{ start: new Date("2024-01-15T10:00:00"), key: "past-1" }];
    render(
      <PatientDashboardMobile
        {...baseProps}
        activeView="appointments"
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
