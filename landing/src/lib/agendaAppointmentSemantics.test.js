import { describe, expect, it } from "vitest";
import {
  countRecoveredAgendaSlotsInPeriod,
  isAgendaSlotCancelled,
  isRecoveredAgendaSlot,
  isUpcomingAgendaSlot,
  patientAgendaRowStatus,
  semanticLabelForAgendaTone,
  toneForAgendaSlot,
} from "./agendaAppointmentSemantics.js";

describe("isAgendaSlotCancelled", () => {
  it("détecte les annulations dans status et booking_status", () => {
    expect(isAgendaSlotCancelled({ status: "cancelled" })).toBe(true);
    expect(isAgendaSlotCancelled({ booking_status: "annulé" })).toBe(true);
    expect(isAgendaSlotCancelled({ status: "confirmed", booking_status: "confirmed" })).toBe(false);
  });
});

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

  it("compte uniquement les créneaux actifs de la période affichée", () => {
    const start = new Date("2026-07-10T00:00:00");
    const end = new Date("2026-07-17T00:00:00");
    expect(countRecoveredAgendaSlotsInPeriod([
      { event_id: "in", start_iso: "2026-07-12T10:00:00", motif: "Créneau récupéré" },
      { event_id: "in", start_iso: "2026-07-12T10:00:00", motif: "Créneau récupéré" },
      { event_id: "cancelled", start_iso: "2026-07-13T10:00:00", motif: "Créneau récupéré", status: "cancelled" },
      { event_id: "out", start_iso: "2026-07-18T10:00:00", motif: "Créneau récupéré" },
    ], start, end)).toBe(1);
  });
});

describe("patientAgendaRowStatus", () => {
  it("retourne À confirmer pour un pending à venir", () => {
    const future = new Date(Date.now() + 3600_000);
    expect(patientAgendaRowStatus({ booking_status: "pending" }, future)).toBe("À confirmer");
  });

  it("conserve le statut Annulé sans classer le RDV futur comme à venir", () => {
    const future = new Date(Date.now() + 3600_000);
    const slot = { status: "cancelled" };
    expect(patientAgendaRowStatus(slot, future)).toBe("Annulé");
    expect(isUpcomingAgendaSlot(slot, future)).toBe(false);
  });

  it("classe un RDV futur actif comme à venir", () => {
    const future = new Date(Date.now() + 3600_000);
    expect(isUpcomingAgendaSlot({ status: "confirmed" }, future)).toBe(true);
  });
});

describe("semanticLabelForAgendaTone", () => {
  it("mappe les libellés courts", () => {
    expect(semanticLabelForAgendaTone("indigo")).toBe("Ordonnance");
    expect(semanticLabelForAgendaTone("purple")).toBe("Récupéré");
  });
});
