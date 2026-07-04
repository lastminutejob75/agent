"""Validation du payload consultation — traçabilité motif patient."""

from __future__ import annotations

from datetime import date

from backend.services.consultations_service import ConsultationCreate


def test_consultation_create_defaults_motif_traceability():
    body = ConsultationCreate(
        patient_id="pat_001",
        date=date(2026, 7, 4),
        motif="Consultation de suivi",
        impression_clinique="Stable",
    )
    dumped = body.model_dump(mode="json")
    assert dumped["motif_source"] == "praticien"
    assert dumped["motif_raw_patient"] is None


def test_consultation_create_preserves_motif_traceability_in_model_dump():
    body = ConsultationCreate(
        patient_id="pat_001",
        date=date(2026, 7, 4),
        motif="Douleurs abdominales à explorer",
        impression_clinique="Syndrome digestif à caractériser",
        motif_source="uwi_suggestion",
        motif_raw_patient="mal au ventre depuis 3 jours",
    )
    dumped = body.model_dump(mode="json")
    assert dumped["motif_source"] == "uwi_suggestion"
    assert dumped["motif_raw_patient"] == "mal au ventre depuis 3 jours"
