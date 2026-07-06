import { describe, expect, it } from "vitest";

import {
  NR_TEXT,
  buildChecklist,
  buildConsultationPayloadFromBlocks,
  buildDossierTiles,
  computeImcFrontend,
  isDossierFieldKnown,
  isNonRenseigneTrace,
  markChecklistCaptured,
  pendingCriticalLabels,
  prepareReviewBlocks,
  splitBlocks,
} from "./dictationBlocks.js";

const EMPTY_PATIENT = {
  allergies: "",
  antecedents_medicaux: "",
  antecedents_chirurgicaux: "",
  traitements: "",
};

const FULL_PATIENT = {
  allergies: "Pénicilline",
  antecedents_medicaux: "Appendicectomie (2010)",
  antecedents_chirurgicaux: "",
  traitements: "Contraception œstroprogestative",
};

function block(field, dest, overrides = {}) {
  const critical = ["impression", "decision", "allergies"].includes(field);
  return {
    id: `${field}-0`,
    field,
    dest,
    label: field,
    text: `texte ${field}`,
    sourceSpans: ["extrait"],
    provenance: "dictee",
    critical,
    danger: field === "allergies",
    confirmed: !critical,
    status: "propose",
    ...overrides,
  };
}

describe("trace « non renseigné »", () => {
  it("reconnaît la trace horodatée écrite par le backend", () => {
    expect(isNonRenseigneTrace("Non renseigné (interrogé le 2026-07-06)")).toBe(true);
    expect(isNonRenseigneTrace("non renseigne")).toBe(true);
    expect(isNonRenseigneTrace("Pénicilline")).toBe(false);
    expect(isNonRenseigneTrace("")).toBe(false);
  });

  it("un champ tracé « non renseigné » n'est pas connu", () => {
    expect(isDossierFieldKnown("Non renseigné (interrogé le 2026-07-06)")).toBe(false);
    expect(isDossierFieldKnown("Pénicilline")).toBe(true);
    expect(isDossierFieldKnown("")).toBe(false);
  });
});

describe("checklist", () => {
  it("dossier vide => checklist complète avec mesures", () => {
    const items = buildChecklist(EMPTY_PATIENT);
    expect(items.map((i) => i.key)).toEqual(["allergies", "antecedents", "traitements", "mesures"]);
    expect(items.find((i) => i.key === "allergies").priority).toBe(true);
    expect(items.find((i) => i.key === "traitements").priority).toBe(true);
    expect(items.find((i) => i.key === "antecedents").priority).toBe(false);
  });

  it("dossier complet + mesures connues => checklist vide", () => {
    expect(buildChecklist(FULL_PATIENT, { mesuresConnues: true })).toEqual([]);
  });

  it("dossier partiel => seulement les items manquants", () => {
    const items = buildChecklist({ ...FULL_PATIENT, traitements: "" }, { mesuresConnues: true });
    expect(items.map((i) => i.key)).toEqual(["traitements"]);
  });

  it("« non renseigné » tracé => la chip réapparaît sans priorité (critère 12)", () => {
    const items = buildChecklist(
      { ...FULL_PATIENT, allergies: "Non renseigné (interrogé le 2026-06-01)" },
      { mesuresConnues: true },
    );
    const allergies = items.find((i) => i.key === "allergies");
    expect(allergies).toBeTruthy();
    expect(allergies.priority).toBe(false);
  });

  it("les chips s'allument sur les blocs capturés", () => {
    const checklist = buildChecklist(EMPTY_PATIENT);
    const marked = markChecklistCaptured(checklist, [block("allergies", "dossier")]);
    expect(marked.find((i) => i.key === "allergies").captured).toBe(true);
    expect(marked.find((i) => i.key === "traitements").captured).toBe(false);
  });
});

describe("prepareReviewBlocks", () => {
  it("1re consultation : complète le socle, Allergies bloquante sans état au dossier", () => {
    const prepared = prepareReviewBlocks(
      [block("impression", "day")],
      { checklist: buildChecklist(EMPTY_PATIENT), firstConsultation: true, allergiesAsked: false },
    );
    const allergies = prepared.find((b) => b.field === "allergies");
    expect(allergies).toBeTruthy();
    expect(allergies.synthetic).toBe(true);
    expect(allergies.critical).toBe(true);
    expect(allergies.confirmed).toBe(false);
    const antecedents = prepared.find((b) => b.field === "antecedents");
    expect(antecedents.confirmed).toBe(true);
  });

  it("mode classique : pas de tuiles synthétiques hormis Allergies sans état", () => {
    const prepared = prepareReviewBlocks(
      [block("impression", "day")],
      { checklist: buildChecklist(EMPTY_PATIENT), firstConsultation: false, allergiesAsked: false },
    );
    expect(prepared.map((b) => b.field)).toEqual(["impression", "allergies"]);
    expect(prepared.find((b) => b.field === "allergies").critical).toBe(true);
  });

  it("« non renseigné » tracé = état documenté : plus de tuile Allergies bloquante (critère 12)", () => {
    const checklist = buildChecklist(
      { ...FULL_PATIENT, allergies: "Non renseigné (interrogé le 2026-06-01)" },
      { mesuresConnues: true },
    );
    const prepared = prepareReviewBlocks(
      [block("impression", "day")],
      { checklist, firstConsultation: false, allergiesAsked: true },
    );
    expect(prepared.find((b) => b.field === "allergies")).toBeUndefined();
  });

  it("ne duplique pas un bloc déjà détecté dans la dictée", () => {
    const prepared = prepareReviewBlocks(
      [block("allergies", "dossier")],
      { checklist: buildChecklist(EMPTY_PATIENT), firstConsultation: true },
    );
    expect(prepared.filter((b) => b.field === "allergies")).toHaveLength(1);
    expect(prepared.find((b) => b.field === "allergies").synthetic).toBe(false);
  });

  it("mode dégradé : rien ne bloque, pas de tuiles synthétiques", () => {
    const prepared = prepareReviewBlocks(
      [block("elements", "day")],
      { checklist: buildChecklist(EMPTY_PATIENT), degraded: true, firstConsultation: true },
    );
    expect(prepared).toHaveLength(1);
    expect(prepared.every((b) => b.confirmed)).toBe(true);
  });
});

describe("pending / split", () => {
  it("liste les blocs critiques non confirmés", () => {
    const blocks = [
      block("impression", "day", { label: "Impression" }),
      block("decision", "day", { label: "Conduite", confirmed: true }),
      block("allergies", "dossier", { label: "Allergies" }),
    ];
    expect(pendingCriticalLabels(blocks)).toEqual(["Impression", "Allergies"]);
  });

  it("répartit et ordonne day / dossier", () => {
    const { day, dossier } = splitBlocks([
      block("decision", "day"),
      block("motif", "day"),
      block("antecedents", "dossier"),
      block("mesures", "dossier"),
    ]);
    expect(day.map((b) => b.field)).toEqual(["motif", "decision"]);
    expect(dossier.map((b) => b.field)).toEqual(["mesures", "antecedents"]);
  });
});

describe("tuiles fiche patient", () => {
  it("le bloc mesures produit poids/taille/IMC, IMC calculé non éditable", () => {
    const tiles = buildDossierTiles([
      block("mesures", "dossier", { structured: { poids_kg: 68, taille_cm: 165 } }),
    ]);
    const byKey = Object.fromEntries(tiles.map((t) => [t.key, t]));
    expect(byKey.poids.value).toBe("68 kg");
    expect(byKey.taille.value).toBe("165 cm");
    expect(byKey.imc.value).toBe("25");
    expect(byKey.imc.calc).toBe(true);
    expect(byKey.imc.nrable).toBe(false);
  });

  it("IMC en attente si poids manquant", () => {
    const tiles = buildDossierTiles([
      block("mesures", "dossier", { structured: { poids_kg: null, taille_cm: 165 } }),
    ]);
    const imc = tiles.find((t) => t.key === "imc");
    expect(imc.missing).toBe(true);
    expect(imc.value).toBe("—");
    const poids = tiles.find((t) => t.key === "poids");
    expect(poids.status).toBe("non_renseigne");
  });

  it("computeImcFrontend arrondit à une décimale", () => {
    expect(computeImcFrontend(68, 165)).toBe(25);
    expect(computeImcFrontend("68,5", "165")).toBe(25.2);
    expect(computeImcFrontend(null, 165)).toBe(null);
  });
});

describe("payload d'enregistrement", () => {
  const blocks = [
    block("motif", "day", { text: "Douleurs abdominales à explorer." }),
    block("elements", "day", { text: "Depuis 3 jours, épigastriques." }),
    block("examen", "day", { text: "Abdomen souple." }),
    block("impression", "day", { text: "À caractériser.", confirmed: true }),
    block("decision", "day", { text: "Surveillance.", confirmed: true }),
    block("mesures", "dossier", { structured: { poids_kg: 68, taille_cm: 165 } }),
    block("allergies", "dossier", { text: "Pénicilline", confirmed: true, status: "confirme" }),
  ];

  it("mappe les blocs day vers les champs classiques et calcule l'IMC", () => {
    const payload = buildConsultationPayloadFromBlocks({
      blocks,
      date: "2026-07-06",
      decisionTags: ["Surveillance"],
      motifSource: "uwi_suggestion",
      motifRawPatient: "mal au ventre",
      durationSeconds: 154,
    });
    expect(payload.motif).toBe("Douleurs abdominales à explorer.");
    expect(payload.anamnese).toBe("Depuis 3 jours, épigastriques.");
    expect(payload.examen_clinique.examen_physique).toBe("Abdomen souple.");
    expect(payload.impression_clinique).toBe("À caractériser.");
    expect(payload.conduite_a_tenir.suivi.consignes).toBe("Surveillance.");
    expect(payload.examen_clinique.constantes).toEqual({ poids_kg: 68, taille_cm: 165, imc: 25 });
    expect(payload.motif_source).toBe("uwi_suggestion");
    expect(payload.dictee.consent_patient).toBe(true);
    expect(payload.dictee.duration_seconds).toBe(154);
    expect(payload.dictee.decision_tags).toEqual(["Surveillance"]);
  });

  it("le transcript n'apparaît nulle part dans le payload", () => {
    const payload = buildConsultationPayloadFromBlocks({ blocks, date: "2026-07-06" });
    expect(JSON.stringify(payload)).not.toContain("transcript");
  });

  it("les tuiles synthétiques non touchées sont exclues, non_renseigne est tracé", () => {
    const withSynthetic = [
      ...blocks,
      block("antecedents", "dossier", { synthetic: true, status: "propose", text: "" }),
      block("contexte", "dossier", { synthetic: true, status: "non_renseigne", text: NR_TEXT }),
    ];
    const payload = buildConsultationPayloadFromBlocks({ blocks: withSynthetic, date: "2026-07-06" });
    const fields = payload.dictee.dossier_blocks.map((b) => b.field);
    expect(fields).not.toContain("antecedents");
    expect(fields).toContain("contexte");
    const contexte = payload.dictee.dossier_blocks.find((b) => b.field === "contexte");
    expect(contexte.status).toBe("non_renseigne");
    expect(contexte.text).toBe("");
  });

  it("motif absent => fallback Consultation", () => {
    const payload = buildConsultationPayloadFromBlocks({
      blocks: blocks.filter((b) => b.field !== "motif"),
      date: "2026-07-06",
    });
    expect(payload.motif).toBe("Consultation");
  });
});
