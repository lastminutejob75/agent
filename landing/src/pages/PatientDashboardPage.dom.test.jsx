import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/api.js", () => ({
  api: {
    tenantGetPatients: vi.fn().mockResolvedValue({
      items: [
        {
          phone: "+33612345678",
          display_name: "Jean Dupont",
          validated_name: "Jean Dupont",
          status_bucket: "active",
          updated_at: "2026-05-01T10:00:00Z",
        },
      ],
    }),
    tenantGetPatient: vi.fn().mockResolvedValue({
      patient: {
        phone: "+33612345678",
        display_name: "Jean Dupont",
        validated_name: "Jean Dupont",
        birth_date: "1990-01-01",
        treating_physician_name: "Dr Martin",
      },
      documents: [],
      insights: { tags: [], recent_past_appointments: [] },
    }),
    tenantGetPatientNotes: vi.fn().mockResolvedValue({ items: [] }),
    tenantGetHandoffs: vi.fn().mockResolvedValue({ items: [] }),
    tenantGetCalls: vi.fn().mockResolvedValue({ calls: [] }),
    tenantGetAgenda: vi.fn().mockResolvedValue({ slots: [] }),
    tenantGetPatientHistory: vi.fn().mockResolvedValue({ items: [] }),
  },
}));

import PatientDashboardPage from "./PatientDashboardPage";

function renderPage(initialEntry = "/app/patient-dashboard?phone=%2B33612345678") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/app/patient-dashboard" element={<PatientDashboardPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("PatientDashboardPage mobile", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => cleanup());

  it("renders without crashing when phone is in URL", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Patients").length).toBeGreaterThan(0);
    });
    expect(screen.getByText("Prochain rendez-vous")).toBeTruthy();
  });
});
