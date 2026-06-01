"""Tests API documents fiche patient (upload + liste)."""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tests.test_tenant_rgpd import _make_jwt


@pytest.fixture
def client():
    from backend.main import app

    return TestClient(app)


@patch("backend.routes.tenant.insert_patient_document")
@patch("backend.routes.tenant.save_patient_dossier_upload")
@patch("backend.routes.tenant.get_cabinet_client_by_phone")
@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
def test_tenant_upload_patient_document_requires_bearer(
    mock_get_user,
    mock_get_profile,
    mock_save_upload,
    mock_insert_doc,
    client,
):
    mock_get_user.return_value = {"tenant_id": 2, "email": "test@example.com", "role": "owner"}
    mock_get_profile.return_value = {"phone": "+33612345678", "display_name": "Jean Dupont"}
    mock_save_upload.return_value = ("patient_docs/2/+33612345678/abc.pdf", "abc.pdf")
    mock_insert_doc.return_value = {
        "id": 42,
        "original_name": "ordonnance.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 12,
        "created_at": "2026-05-30T12:00:00+00:00",
    }

    token = _make_jwt(tenant_id=2)
    files = {"file": ("ordonnance.pdf", io.BytesIO(b"%PDF-test"), "application/pdf")}
    r = client.post(
        "/api/tenant/patients/%2B33612345678/documents",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["document"]["id"] == 42
    mock_save_upload.assert_called_once()
    mock_insert_doc.assert_called_once()


@patch("backend.routes.tenant.list_patient_documents")
@patch("backend.routes.tenant.get_cabinet_client_by_phone")
@patch("backend.routes.tenant.pg_get_tenant_user_by_id")
def test_tenant_get_patient_lightweight_includes_documents(
    mock_get_user,
    mock_get_profile,
    mock_list_docs,
    client,
):
    mock_get_user.return_value = {"tenant_id": 2, "email": "test@example.com", "role": "owner"}
    mock_get_profile.return_value = {"phone": "+33612345678", "display_name": "Jean Dupont"}
    mock_list_docs.return_value = [
        {
            "id": 7,
            "original_name": "scan.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
            "created_at": "2026-05-30T10:00:00+00:00",
        }
    ]

    token = _make_jwt(tenant_id=2)
    r = client.get(
        "/api/tenant/patients/%2B33612345678?lightweight=true",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 200
    docs = r.json().get("documents") or []
    assert len(docs) == 1
    assert docs[0]["id"] == 7
    assert docs[0]["original_name"] == "scan.pdf"
