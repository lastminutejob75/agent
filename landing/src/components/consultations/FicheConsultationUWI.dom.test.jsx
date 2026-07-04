import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import FicheConsultationUWI from "./FicheConsultationUWI.jsx";

function renderFiche() {
  // onLoadPrefill -> null : pas de carte de préparation ni de timer démo.
  return render(<FicheConsultationUWI onLoadPrefill={() => Promise.resolve(null)} />);
}

describe("FicheConsultationUWI — barre de dictée", () => {
  afterEach(() => cleanup());

  it("propose les deux intentions et démarre sur Consultation", () => {
    renderFiche();
    expect(screen.getByRole("button", { name: "Consultation" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Note libre" })).toBeTruthy();
    expect(screen.getByText("Dicter la consultation")).toBeTruthy();
  });

  it("bascule sur Note libre et adapte le libellé (mémo -> note praticien)", () => {
    renderFiche();
    fireEvent.click(screen.getByRole("button", { name: "Note libre" }));
    expect(screen.getByText("Dicter une note libre")).toBeTruthy();
    expect(
      screen.getByText("Transcrite telle quelle dans la note praticien — vous relisez"),
    ).toBeTruthy();
  });

  it("n'affiche pas l'indicateur « N à relire » tant qu'aucune proposition n'est en attente", () => {
    renderFiche();
    // Le badge du garde-fou est de la forme "2 à relire" ; "À relire avant examen"
    // (contexte patient) ne doit pas être confondu avec lui.
    expect(screen.queryByText(/\d+\s+à relire/i)).toBeNull();
  });

  it("remplace les chips locales par la réponse LLM quand le niveau B répond", async () => {
    const onLoadPrefill = vi.fn(() => Promise.resolve({
      source: "clara",
      resume_appel: "« mal au ventre depuis 3 jours »",
      derniere_consultation: "Aucune consultation récente.",
      documents: "Aucun document.",
      extraction: { motif: "mal au ventre depuis 3 jours" },
      champs_confiance: [],
      avertissements: [],
    }));
    const onReformulateMotif = vi.fn(() => Promise.resolve({
      suggestions: ["Douleurs abdominales à explorer (LLM)", "Épigastralgies — évolution 3 jours"],
    }));

    render(
      <FicheConsultationUWI
        onLoadPrefill={onLoadPrefill}
        onReformulateMotif={onReformulateMotif}
      />,
    );

    expect(await screen.findByText("Douleurs abdominales à explorer")).toBeTruthy();

    await waitFor(() => {
      expect(screen.getByText("Douleurs abdominales à explorer (LLM)")).toBeTruthy();
    });
    expect(onReformulateMotif).toHaveBeenCalled();
  });
});
