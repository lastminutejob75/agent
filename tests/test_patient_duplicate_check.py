from unittest.mock import patch

from backend.db import detect_patient_duplicate_conflicts


def test_detect_patient_duplicate_conflicts_phone_only():
    with patch("backend.db.get_cabinet_client_by_phone") as mock_phone, patch(
        "backend.db.get_cabinet_client_by_email"
    ) as mock_email:
        mock_phone.return_value = {
            "phone": "+33612345678",
            "validated_name": "Claire Dupont",
            "display_name": "Claire Dupont",
            "email": "",
        }
        mock_email.return_value = None

        result = detect_patient_duplicate_conflicts(1, phone="+33612345678")

    assert result["has_conflict"] is True
    assert len(result["conflicts"]) == 1
    assert result["conflicts"][0]["field"] == "phone"
    assert result["conflicts"][0]["display_name"] == "Claire Dupont"


def test_detect_patient_duplicate_conflicts_email_other_phone():
    with patch("backend.db.get_cabinet_client_by_phone", return_value=None), patch(
        "backend.db.get_cabinet_client_by_email"
    ) as mock_email:
        mock_email.return_value = {
            "phone": "+33611111111",
            "validated_name": "Paul Martin",
            "display_name": "Paul Martin",
            "email": "paul@example.com",
        }

        result = detect_patient_duplicate_conflicts(
            1,
            phone="+33622222222",
            email="paul@example.com",
        )

    assert result["has_conflict"] is True
    assert any(c["field"] == "email" for c in result["conflicts"])


def test_detect_patient_duplicate_conflicts_exclude_current_phone():
    with patch("backend.db.get_cabinet_client_by_phone") as mock_phone, patch(
        "backend.db.get_cabinet_client_by_email"
    ) as mock_email:
        mock_phone.return_value = {
            "phone": "+33612345678",
            "validated_name": "Claire Dupont",
            "display_name": "Claire Dupont",
            "email": "claire@example.com",
        }
        mock_email.return_value = {
            "phone": "+33612345678",
            "validated_name": "Claire Dupont",
            "display_name": "Claire Dupont",
            "email": "claire@example.com",
        }

        result = detect_patient_duplicate_conflicts(
            1,
            email="claire@example.com",
            exclude_phone="+33612345678",
        )

    assert result["has_conflict"] is False
    assert result["conflicts"] == []
