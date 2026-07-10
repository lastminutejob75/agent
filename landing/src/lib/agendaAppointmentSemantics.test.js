import { describe, expect, it } from "vitest";
import {
  isRecoveredAgendaSlot,
  patientAgendaRowStatus,
  semanticLabelForAgendaTone,
  toneForAgendaSlot,
} from "./agendaAppointmentSemantics.js";

describe("toneForAgendaSlot", () => {
  it("marque un RDV public pending en orange", () => {
    expect(toneForAgendaSlot({
      source: "PAGE_PUBLIQUE",
      booking_status: "pending",
      motif: "Consultation",
    })).toBe("orange");
  });

  it("marque un renouvellement en indigo", () => {
    expect(toneForAgendaSlot({
      motif: "Renouvellement d'ordonnance",
      booking_status: "confirmed",
      source: "PAGE_PUBLIQUE",
    })).toBe("indigo");
  });

  it("marque une demande de document en bleu", () => {
    expect(toneForAgendaSlot({
      motif: "Certificat médical",
      booking_status: "confirmed",
      source: "UWI",
    })).toBe("blue");
  });

  it("marque un créneau récupéré en violet", () => {
    expect(toneForAgendaSlot({
      motif: "Créneau récupéré",
      booking_status: "confirmed",
      source: "UWI",
    })).toBe("purple");
  });

  it("marque une urgence en rouge", () => {
    expect(toneForAgendaSlot({
      motif: "Douleur prioritaire",
      booking_status: "confirmed",
      source: "UWI",
    })).toBe("red");
  });

  it("marque un RDV Clara confirmé en vert", () => {
    expect(toneForAgendaSlot({
      motif: "Consultation",
      booking_status: "confirmed",
      source: "UWI",
    })).toBe("green");
  });

  it("ne classe pas tout RDV UWI en vert si motif administratif", () => {
    expect(toneForAgendaSlot({
      motif: "Ordonnance à renouveler",
      booking_status: "confirmed",
      source: "UWI",
    })).toBe("indigo");
  });
});

describe("isRecoveredAgendaSlot", () => {
  it("détecte les libellés de récupération", () => {
    expect(isRecoveredAgendaSlot({ motif: "Suite annulation" })).toBe(true);
    expect(isRecoveredAgendaSlot({ slot_label: "Créneau sauvé" })).toBe(true);
    expect(isRecoveredAgendaSlot({ motif: "Consultation" })).toBe(false);
  });
});

describe("patientAgendaRowStatus", () => {
  it("retourne À confirmer pour un pending à venir", () => {
    const future = new Date(Date.now() + 3600_000);
    expect(patientAgendaRowStatus({ booking_status: "pending" }, future)).toBe("À confirmer");
  });
});

describe("semanticLabelForAgendaTone", () => {
  it("mappe les libellés courts", () => {
    expect(semanticLabelForAgendaTone("indigo")).toBe("Ordonnance");
    expect(semanticLabelForAgendaTone("purple")).toBe("Récupéré");
  });
});
