import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

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
});
