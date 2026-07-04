import { describe, expect, it } from "vitest";

import {
  computeCompletude,
  isEmptyOrGeneric,
  isEmptyOrGenericSynthese,
} from "./FicheConsultationUWI.jsx";
import { getMotifSuggestions } from "./motifReformulations.js";

const EMPTY_CONSULTATION = {
  motif: "",
  anamnese: "",
  etatGeneral: "",
  impression: "",
  prescription: "",
  examens: [],
  suiviConsignes: "",
  suiviRdv: "",
  fc: "",
  pas: "",
  pad: "",
  temp: "",
  spo2: "",
  fr: "",
  poids: "",
  taille: "",
};

describe("isEmptyOrGeneric", () => {
  it("considère les valeurs génériques comme vides", () => {
    expect(isEmptyOrGeneric("Consultation")).toBe(true);
    expect(isEmptyOrGeneric("À compléter")).toBe(true);
    expect(isEmptyOrGeneric("—")).toBe(true);
    expect(isEmptyOrGeneric("Aucune allergie connue")).toBe(true);
  });

  it("conserve le signal clinique réel", () => {
    expect(isEmptyOrGeneric("Pénicilline")).toBe(false);
    expect(isEmptyOrGeneric("Metformine 500 mg")).toBe(false);
  });
});

describe("isEmptyOrGenericSynthese", () => {
  it("ignore une synthèse dont motif et impression sont génériques", () => {
    expect(
      isEmptyOrGenericSynthese(
        "Derniere consultation: 2026-06-24 | Motif: Consultation | Impression: À compléter",
      ),
    ).toBe(true);
  });

  it("conserve une synthèse avec au moins un champ utile", () => {
    expect(
      isEmptyOrGenericSynthese("Motif: Fatigue persistante | Impression: Anémie à explorer"),
    ).toBe(false);
  });
});

describe("getMotifSuggestions", () => {
  it("propose des reformulations pour un motif patient courant", () => {
    const suggestions = getMotifSuggestions("mal au ventre depuis 3 jours");
    expect(suggestions).toContain("Douleurs abdominales à explorer");
    expect(suggestions.length).toBeGreaterThanOrEqual(2);
    expect(suggestions.length).toBeLessThanOrEqual(3);
  });

  it("retourne une chip générique si aucun match", () => {
    expect(getMotifSuggestions("demande très atypique xyz123")).toEqual([
      "Consultation de médecine générale — motif à préciser",
    ]);
  });
});

describe("computeCompletude", () => {
  it("atteint ≥ 80 % en mode rapide avec motif et impression remplis", () => {
    const score = computeCompletude(
      { ...EMPTY_CONSULTATION, motif: "Fatigue", impression: "Asthénie à explorer" },
      "rapide",
    );
    expect(score).toBeGreaterThanOrEqual(80);
  });

  it("recalcule immédiatement à la bascule de mode", () => {
    const c = {
      ...EMPTY_CONSULTATION,
      motif: "Fatigue",
      impression: "Asthénie à explorer",
    };
    const rapide = computeCompletude(c, "rapide");
    const complet = computeCompletude(c, "complete");
    expect(rapide).toBeGreaterThan(complet);
  });

  it("compte prescription ou examens dans le score rapide", () => {
    const withExamens = computeCompletude(
      { ...EMPTY_CONSULTATION, motif: "Suivi", impression: "Stable", examens: ["NFS"] },
      "rapide",
    );
    const withoutExamens = computeCompletude(
      { ...EMPTY_CONSULTATION, motif: "Suivi", impression: "Stable" },
      "rapide",
    );
    expect(withExamens).toBe(100);
    expect(withoutExamens).toBe(80);
  });
});
