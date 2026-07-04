import { describe, expect, it } from "vitest";

import { computeConsultationCompleteness } from "../../utils/consultationCompleteness.js";
import {
  getVisibleContextTiles,
  hasMedicalSignal,
  isEmptyOrGeneric,
  isGenericConsultationSummary,
  isKnownNegative,
} from "../../utils/medicalContext.js";
import { getMotifSuggestions, isSensitiveMotif } from "../../utils/motifReformulations.js";

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
    expect(isEmptyOrGeneric("Non renseigné")).toBe(true);
    expect(isEmptyOrGeneric("À compléter")).toBe(true);
    expect(isEmptyOrGeneric("Consultation")).toBe(true);
    expect(isEmptyOrGeneric("—")).toBe(true);
  });

  it("conserve le signal clinique réel", () => {
    expect(isEmptyOrGeneric("Pénicilline")).toBe(false);
    expect(isEmptyOrGeneric("Metformine 500 mg")).toBe(false);
  });

  it("ne traite pas une négation documentée comme vide", () => {
    expect(isEmptyOrGeneric("Aucune allergie connue")).toBe(false);
  });
});

describe("isKnownNegative", () => {
  it("identifie les négations documentées", () => {
    expect(isKnownNegative("Aucune allergie connue")).toBe(true);
    expect(isKnownNegative("Pas de traitement en cours")).toBe(true);
  });

  it("ignore les champs réellement vides", () => {
    expect(isKnownNegative("Non renseigné")).toBe(false);
  });
});

describe("isGenericConsultationSummary", () => {
  it("ignore une synthèse dont motif et impression sont génériques", () => {
    expect(
      isGenericConsultationSummary(
        "Derniere consultation: 2026-06-24 | Motif: Consultation | Impression: À compléter",
      ),
    ).toBe(true);
  });

  it("conserve une synthèse avec au moins un champ utile", () => {
    expect(
      isGenericConsultationSummary("Motif: Fatigue persistante | Impression: Anémie à explorer"),
    ).toBe(false);
  });
});

describe("getVisibleContextTiles", () => {
  it("affiche uniquement l'allergie quand c'est le seul signal", () => {
    const tiles = getVisibleContextTiles({ allergies: "Pénicilline" });
    expect(tiles).toHaveLength(1);
    expect(tiles[0].label).toBe("Allergies");
    expect(tiles[0].value).toBe("Pénicilline");
  });

  it("peut afficher une négation documentée comme information utile", () => {
    const tiles = getVisibleContextTiles({ allergies: "Aucune allergie connue" });
    expect(tiles).toHaveLength(1);
    expect(tiles[0].tone).toBe("muted");
  });
});

describe("hasMedicalSignal", () => {
  it("retourne false pour un dossier entièrement vide", () => {
    expect(hasMedicalSignal({ allergies: "—", traitements: "Non renseigné" })).toBe(false);
  });
});

describe("getMotifSuggestions", () => {
  it("propose des reformulations pour un motif patient courant", () => {
    const suggestions = getMotifSuggestions("mal au ventre depuis 3 jours");
    expect(suggestions).toContain("Douleurs abdominales à explorer");
    expect(suggestions.length).toBeGreaterThanOrEqual(2);
  });

  it("retourne une chip générique si aucun match", () => {
    expect(getMotifSuggestions("demande très atypique xyz123")).toEqual([
      "Consultation de médecine générale — motif à préciser",
    ]);
  });
});

describe("isSensitiveMotif", () => {
  it("détecte un motif potentiellement prioritaire", () => {
    expect(isSensitiveMotif("douleur thoracique depuis ce matin")).toBe(true);
    expect(isSensitiveMotif("mal au ventre")).toBe(false);
  });
});

describe("computeConsultationCompleteness", () => {
  it("atteint ≥ 80 % en mode rapide avec motif et impression remplis", () => {
    const score = computeConsultationCompleteness(
      { ...EMPTY_CONSULTATION, motif: "Fatigue", impression: "Asthénie à explorer" },
      "rapide",
    );
    expect(score).toBeGreaterThanOrEqual(80);
  });

  it("atteint 100 % en mode rapide avec prescription ou examens", () => {
    const score = computeConsultationCompleteness(
      { ...EMPTY_CONSULTATION, motif: "Suivi", impression: "Stable", examens: ["NFS"] },
      "rapide",
    );
    expect(score).toBe(100);
  });

  it("recalcule immédiatement à la bascule de mode", () => {
    const c = {
      ...EMPTY_CONSULTATION,
      motif: "Fatigue",
      impression: "Asthénie à explorer",
    };
    expect(computeConsultationCompleteness(c, "rapide")).toBeGreaterThan(
      computeConsultationCompleteness(c, "complete"),
    );
  });
});
