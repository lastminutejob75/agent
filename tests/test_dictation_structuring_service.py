"""Tests structuration dictée ambiante — post-traitement déterministe."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.services.dictation_structuring_service import (
    StructureDictationRequest,
    build_degraded_blocks,
    build_structure_user_prompt,
    compute_imc,
    sanitize_blocks,
    span_in_transcript,
    _normalize_for_match,
)

TRANSCRIPT = (
    "Nouvelle patiente. Antécédent d'appendicectomie en 2010, hypertension chez le père. "
    "Allergie à la pénicilline. Traitement en cours : contraception œstroprogestative. "
    "Poids 68 kilos, taille 1 mètre 65. Consulte pour des douleurs depuis trois jours, "
    "plutôt épigastriques, sans vomissement, pas de fièvre, transit conservé. "
    "Abdomen souple, sensibilité épigastrique modérée, pas de défense. "
    "Je retiens des douleurs épigastriques à caractériser. "
    "Conseils de surveillance, reconsulter si aggravation."
)


def test_span_in_transcript_tolerant_case_accents_spaces():
    norm = _normalize_for_match(TRANSCRIPT)
    assert span_in_transcript("allergie à la pénicilline", norm)
    assert span_in_transcript("ALLERGIE  A LA PENICILLINE", norm)
    assert span_in_transcript("gastrite probable", norm) is False
    assert span_in_transcript("", norm) is False


def test_compute_imc():
    assert compute_imc(68, 165) == 25.0
    assert compute_imc("68", "165") == 25.0
    assert compute_imc("68,5", "165") == 25.2
    assert compute_imc(None, 165) is None
    assert compute_imc(68, 0) is None


def test_sanitize_blocks_rejects_block_without_valid_source_spans():
    raw = [
        {"field": "impression", "text": "Gastrite probable.", "sourceSpans": ["gastrite probable"]},
        {
            "field": "examen",
            "text": "Abdomen souple, sensibilité épigastrique modérée.",
            "sourceSpans": ["Abdomen souple, sensibilité épigastrique modérée"],
        },
    ]
    blocks = sanitize_blocks(raw, TRANSCRIPT)
    fields = [b["field"] for b in blocks]
    assert "impression" not in fields
    assert "examen" in fields


def test_sanitize_blocks_forces_criticality_and_dest():
    raw = [
        {
            "field": "allergies",
            "dest": "day",
            "critical": False,
            "text": "Pénicilline.",
            "sourceSpans": ["Allergie à la pénicilline"],
        },
        {
            "field": "impression",
            "critical": False,
            "text": "Douleurs épigastriques à caractériser.",
            "sourceSpans": ["Je retiens des douleurs épigastriques à caractériser"],
        },
        {
            "field": "elements",
            "critical": True,
            "text": "Depuis 3 jours, épigastriques, sans vomissement.",
            "sourceSpans": ["douleurs depuis trois jours"],
        },
    ]
    blocks = {b["field"]: b for b in sanitize_blocks(raw, TRANSCRIPT)}
    assert blocks["allergies"]["dest"] == "dossier"
    assert blocks["allergies"]["critical"] is True
    assert blocks["allergies"]["danger"] is True
    assert blocks["allergies"]["confirmed"] is False
    assert blocks["impression"]["critical"] is True
    assert blocks["impression"]["confirmed"] is False
    assert blocks["elements"]["critical"] is False
    assert blocks["elements"]["confirmed"] is True


def test_sanitize_blocks_computes_imc_server_side():
    raw = [
        {
            "field": "mesures",
            "text": "Poids 68 kg, taille 165 cm.",
            "sourceSpans": ["Poids 68 kilos, taille 1 mètre 65"],
            "structured": {"poids_kg": 68, "taille_cm": 165, "imc": 99.9},
        },
    ]
    blocks = sanitize_blocks(raw, TRANSCRIPT)
    mesures = blocks[0]
    assert mesures["structured"]["imc"] == 25.0
    assert "25,0" in mesures["extra"]


def test_sanitize_blocks_motif_choisi_overrides_llm_motif():
    raw = [
        {"field": "motif", "text": "Douleurs abdominales.", "sourceSpans": ["Consulte pour des douleurs"]},
    ]
    blocks = sanitize_blocks(
        raw,
        TRANSCRIPT,
        motif_choisi="Douleurs abdominales à explorer",
        motif_patient_verbatim="mal au ventre depuis 3 jours",
    )
    motif = next(b for b in blocks if b["field"] == "motif")
    assert motif["text"] == "Douleurs abdominales à explorer"
    assert motif["provenance"] == "motif_patient"


def test_sanitize_blocks_rejects_unknown_field_and_dedupes():
    raw = [
        {"field": "diagnostic", "text": "x", "sourceSpans": ["Abdomen souple"]},
        {"field": "examen", "text": "Premier.", "sourceSpans": ["Abdomen souple"]},
        {"field": "examen", "text": "Doublon.", "sourceSpans": ["pas de défense"]},
    ]
    blocks = sanitize_blocks(raw, TRANSCRIPT)
    assert len(blocks) == 1
    assert blocks[0]["text"] == "Premier."


def test_build_degraded_blocks_keeps_full_transcript():
    blocks = build_degraded_blocks(TRANSCRIPT)
    assert len(blocks) == 1
    block = blocks[0]
    assert block["field"] == "elements"
    assert block["dest"] == "day"
    assert block["critical"] is False
    assert TRANSCRIPT in block["text"]


def test_structure_request_validates_transcript():
    with pytest.raises(ValidationError):
        StructureDictationRequest(transcript="   ")
    req = StructureDictationRequest(transcript=" abc ")
    assert req.transcript == "abc"


def test_user_prompt_mentions_known_dossier_fields_and_motif():
    req = StructureDictationRequest(
        transcript=TRANSCRIPT,
        motif_choisi="Douleurs abdominales à explorer",
        dossier_state={"allergies_connues": True, "traitements_connus": True},
    )
    prompt = build_structure_user_prompt(req)
    assert "ne crée PAS de bloc motif" in prompt
    assert "allergies" in prompt
    assert "traitements" in prompt


def test_apply_dictation_dossier_blocks_upserts_and_traces_non_renseigne():
    from unittest.mock import patch

    from backend.routes.tenant import _apply_dictation_dossier_blocks

    profile = {"allergies": "Pénicilline", "traitements": "", "antecedents_medicaux": "", "facteurs_risque": ""}
    captured = {}

    def fake_update(tenant_id, phone, **kwargs):
        captured.update(kwargs)
        return profile

    dictee = {
        "dossier_blocks": [
            # Nouvelle allergie en consultation n : fusion, pas d'écrasement.
            {"field": "allergies", "text": "Fraise", "status": "confirme"},
            # Champ vide + non renseigné explicite : trace horodatée.
            {"field": "traitements", "text": "", "status": "non_renseigne"},
            # Les mesures ne vont jamais dans les colonnes patient.
            {"field": "mesures", "text": "Poids 68 kg", "status": "confirme", "structured": {"poids_kg": 68}},
        ]
    }
    with patch("backend.routes.tenant.get_cabinet_client_by_phone", return_value=profile):
        with patch("backend.routes.tenant.update_patient_fields", side_effect=fake_update):
            _apply_dictation_dossier_blocks(1, "0600000000", {"consultation_date": "2026-07-06"}, dictee)

    assert captured["allergies"] == "Pénicilline\nFraise"
    assert captured["traitements"] == "Non renseigné (interrogé le 2026-07-06)"
    assert "mesures" not in captured
    assert not any(k.startswith("poids") for k in captured)


def test_apply_dictation_dossier_blocks_never_overwrites_with_non_renseigne():
    from unittest.mock import patch

    from backend.routes.tenant import _apply_dictation_dossier_blocks

    profile = {"allergies": "Pénicilline"}
    captured = {}

    def fake_update(tenant_id, phone, **kwargs):
        captured.update(kwargs)
        return profile

    dictee = {"dossier_blocks": [{"field": "allergies", "text": "", "status": "non_renseigne"}]}
    with patch("backend.routes.tenant.get_cabinet_client_by_phone", return_value=profile):
        with patch("backend.routes.tenant.update_patient_fields", side_effect=fake_update):
            _apply_dictation_dossier_blocks(1, "0600000000", {"consultation_date": "2026-07-06"}, dictee)

    assert captured == {}


def test_apply_dictation_dossier_blocks_replaces_previous_non_renseigne_trace():
    """Critère 12 : un « non renseigné » tracé en consultation n-1 est remplacé
    par le contenu réel capté en consultation n (jamais concaténé)."""
    from unittest.mock import patch

    from backend.routes.tenant import _apply_dictation_dossier_blocks

    profile = {
        "allergies": "Non renseigné (interrogé le 2026-06-01)",
        "traitements": "Non renseigné (interrogé le 2026-06-01)",
    }
    captured = {}

    def fake_update(tenant_id, phone, **kwargs):
        captured.update(kwargs)
        return profile

    dictee = {
        "dossier_blocks": [
            {"field": "allergies", "text": "Pénicilline", "status": "confirme"},
            # Toujours pas de réponse : la trace est réécrite avec la nouvelle date.
            {"field": "traitements", "text": "", "status": "non_renseigne"},
        ]
    }
    with patch("backend.routes.tenant.get_cabinet_client_by_phone", return_value=profile):
        with patch("backend.routes.tenant.update_patient_fields", side_effect=fake_update):
            _apply_dictation_dossier_blocks(1, "0600000000", {"consultation_date": "2026-07-06"}, dictee)

    assert captured["allergies"] == "Pénicilline"
    assert captured["traitements"] == "Non renseigné (interrogé le 2026-07-06)"


def test_patient_consultation_state_first_consultation_flag():
    """is_first_consultation = aucune consultation enregistrée, même si le
    dossier contient déjà des antécédents (import Doctolib)."""
    from unittest.mock import patch

    from backend.routes.tenant import _patient_consultation_state

    with patch("backend.routes.tenant.list_patient_consultations", return_value=[]):
        state = _patient_consultation_state(1, "0600000000")
    assert state == {"is_first_consultation": True, "mesures_connues": False}

    consultations = [
        {"id": 1, "vitals": {}},
        {"id": 2, "vitals": {"poids_kg": 68}},
    ]
    with patch("backend.routes.tenant.list_patient_consultations", return_value=consultations):
        state = _patient_consultation_state(1, "0600000000")
    assert state["is_first_consultation"] is False
    assert state["mesures_connues"] is True

    with patch("backend.routes.tenant.list_patient_consultations", return_value=[{"id": 3, "vitals": {}}]):
        state = _patient_consultation_state(1, "0600000000")
    assert state["is_first_consultation"] is False
    assert state["mesures_connues"] is False
