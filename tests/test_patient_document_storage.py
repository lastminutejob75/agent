"""Tests stockage documents questionnaire V2 (local + S3)."""

from __future__ import annotations

import os

import pytest

from backend.services import patient_document_storage as storage


def test_use_s3_storage_false_without_env(monkeypatch):
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    assert storage.use_s3_storage() is False


def test_use_s3_storage_true_with_env(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "my-bucket")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    assert storage.use_s3_storage() is True


def test_ovh_credentials_and_endpoint(monkeypatch):
    monkeypatch.setenv("S3_PROVIDER", "ovh")
    monkeypatch.setenv("OVH_S3_BUCKET", "uwi-docs")
    monkeypatch.setenv("OVH_S3_REGION", "gra")
    monkeypatch.setenv("OVH_ACCESS_KEY_ID", "ovh-key")
    monkeypatch.setenv("OVH_SECRET_ACCESS_KEY", "ovh-secret")
    assert storage.use_s3_storage() is True
    assert storage.s3_bucket() == "uwi-docs"
    assert storage._endpoint_url() == "https://s3.gra.io.cloud.ovh.net"
    assert storage.storage_backend_label() == "ovh"


def test_ovh_explicit_endpoint(monkeypatch):
    monkeypatch.setenv("OVH_S3_ENDPOINT", "s3.eu-west-par.io.cloud.ovh.net")
    monkeypatch.setenv("OVH_S3_BUCKET", "b")
    monkeypatch.setenv("OVH_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("OVH_SECRET_ACCESS_KEY", "s")
    assert storage._endpoint_url() == "https://s3.eu-west-par.io.cloud.ovh.net"


def test_save_local_disk(tmp_path, monkeypatch):
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.setattr(storage, "UPLOAD_ROOT", str(tmp_path))

    key, _name = storage.save_questionnaire_upload(
        1,
        "+33611111111",
        "req-abc",
        b"hello",
        "note.pdf",
        "application/pdf",
    )
    assert key.endswith(".pdf")
    assert storage.document_exists(key)
    assert storage.read_document(key) == b"hello"


def test_save_s3_when_configured(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "bucket-test")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    stored: dict = {}

    def fake_put(key, content, mime):
        stored[key] = (content, mime)

    monkeypatch.setattr(storage, "_s3_put_object", fake_put)
    monkeypatch.setattr(storage, "_s3_object_exists", lambda k: k in stored)
    monkeypatch.setattr(storage, "_s3_get_object", lambda k: stored[k][0])

    key, _ = storage.save_questionnaire_upload(
        2,
        "+33622222222",
        "req-xyz",
        b"%PDF",
        "scan.pdf",
        "application/pdf",
    )
    assert stored[key][0] == b"%PDF"
    assert storage.read_document(key) == b"%PDF"


def test_ovh_put_skips_sse_when_disabled(monkeypatch):
    monkeypatch.setenv("S3_PROVIDER", "ovh")
    monkeypatch.setenv("OVH_S3_BUCKET", "b")
    monkeypatch.setenv("OVH_S3_REGION", "gra")
    monkeypatch.setenv("OVH_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("OVH_SECRET_ACCESS_KEY", "s")
    monkeypatch.setenv("S3_SERVER_SIDE_ENCRYPTION", "none")
    assert storage._put_object_extra() == {}


def test_rejects_oversized_file(monkeypatch, tmp_path):
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.setattr(storage, "UPLOAD_ROOT", str(tmp_path))
    big = b"x" * (storage.MAX_UPLOAD_BYTES + 1)
    with pytest.raises(ValueError, match="10 Mo"):
        storage.save_questionnaire_upload(1, "+336", "r", big, "a.pdf", "application/pdf")


def test_delete_storage_object_local(tmp_path, monkeypatch):
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.setattr(storage, "UPLOAD_ROOT", str(tmp_path))

    key, _ = storage.save_questionnaire_upload(
        1,
        "+33611111111",
        "req-del",
        b"purge-me",
        "note.pdf",
        "application/pdf",
    )
    assert storage.document_exists(key)
    assert storage.delete_storage_object(key) is True
    assert storage.document_exists(key) is False
    assert storage.delete_storage_object(key) is False


def test_delete_patient_v2_data_purges_local_files(tmp_path, monkeypatch):
    from backend.db import upsert_cabinet_client
    from backend.patient_v2_db import delete_patient_v2_data, ensure_patient_v2_schema, insert_patient_document_v2

    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.setattr(storage, "UPLOAD_ROOT", str(tmp_path))
    ensure_patient_v2_schema()

    tenant_id = 1
    phone = "+33699998888"
    upsert_cabinet_client(tenant_id, phone, raw_name="Purge Test")
    key, _ = storage.save_questionnaire_upload(
        tenant_id,
        phone,
        "req-rgpd",
        b"secret-doc",
        "ordonnance.pdf",
        "application/pdf",
    )
    insert_patient_document_v2(
        tenant_id,
        phone,
        questionnaire_request_id="req-rgpd",
        filename="ordonnance.pdf",
        storage_key=key,
    )
    assert storage.document_exists(key)

    delete_patient_v2_data(tenant_id, phone)

    assert storage.document_exists(key) is False
    from backend.db import get_conn

    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM patient_documents_v2 WHERE tenant_id = ? AND patient_phone = ?",
            (tenant_id, phone),
        ).fetchone()
        assert row["c"] == 0
    finally:
        conn.close()


def test_delete_patient_document_v2_purges_local_file(tmp_path, monkeypatch):
    from backend.db import upsert_cabinet_client
    from backend.patient_v2_db import (
        delete_patient_document_v2,
        ensure_patient_v2_schema,
        get_patient_document_v2,
        insert_patient_document_v2,
    )

    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.setattr(storage, "UPLOAD_ROOT", str(tmp_path))
    ensure_patient_v2_schema()

    tenant_id = 1
    phone = "+33688887777"
    upsert_cabinet_client(tenant_id, phone, raw_name="Doc Delete")
    key, _ = storage.save_questionnaire_upload(
        tenant_id,
        phone,
        "req-one",
        b"to-delete",
        "radio.pdf",
        "application/pdf",
    )
    doc = insert_patient_document_v2(
        tenant_id,
        phone,
        questionnaire_request_id="req-one",
        filename="radio.pdf",
        storage_key=key,
    )
    doc_id = doc["id"]
    assert storage.document_exists(key)
    assert get_patient_document_v2(tenant_id, doc_id) is not None

    assert delete_patient_document_v2(tenant_id, doc_id, patient_phone=phone) is True
    assert storage.document_exists(key) is False
    assert get_patient_document_v2(tenant_id, doc_id) is None
    assert delete_patient_document_v2(tenant_id, doc_id) is False


def test_delete_questionnaire_v2_document_api(tmp_path, monkeypatch):
    from backend.main import app
    from backend.patient_v2_db import ensure_patient_v2_schema, insert_patient_document_v2
    from backend.routes import tenant as tenant_routes
    from fastapi.testclient import TestClient

    monkeypatch.setenv("UWI_HDS_ENABLED", "true")
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.setattr(storage, "UPLOAD_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "backend.routes.patient_context._tenant_detail",
        lambda _tid: {"params": {"hds_enabled": True}},
    )
    ensure_patient_v2_schema()

    tenant_id = 1
    phone = "+33666665555"
    from backend.db import upsert_cabinet_client

    upsert_cabinet_client(tenant_id, phone, raw_name="Api Del")
    key, _ = storage.save_questionnaire_upload(
        tenant_id,
        phone,
        "req-api",
        b"api-del",
        "scan.pdf",
        "application/pdf",
    )
    doc = insert_patient_document_v2(
        tenant_id,
        phone,
        questionnaire_request_id="req-api",
        filename="scan.pdf",
        storage_key=key,
        is_health=True,
    )

    app.dependency_overrides[tenant_routes.require_tenant_auth] = lambda: {
        "tenant_id": tenant_id,
        "sub": "1",
        "role": "owner",
        "email": "owner@test.fr",
    }
    try:
        client = TestClient(app)
        r = client.delete(f"/api/tenant/questionnaires-v2/documents/{doc['id']}")
        assert r.status_code == 200
        assert r.json().get("ok") is True
        assert storage.document_exists(key) is False
    finally:
        app.dependency_overrides.pop(tenant_routes.require_tenant_auth, None)


def test_save_patient_dossier_local_disk(tmp_path, monkeypatch):
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.setattr(storage, "UPLOAD_ROOT", str(tmp_path))

    key, _name = storage.save_patient_dossier_upload(
        2,
        "+33696854785",
        b"patient-doc",
        "ordonnance.pdf",
        "application/pdf",
    )
    assert key.startswith("patient_docs/2/+33696854785/")
    assert storage.patient_dossier_exists(key, 2, "+33696854785")
    assert storage.read_patient_dossier(key, 2, "+33696854785") == b"patient-doc"


def test_patient_dossier_legacy_path(tmp_path, monkeypatch):
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.setattr(storage, "LEGACY_PATIENT_DOSSIER_ROOT", str(tmp_path))

    legacy_name = "abc123.pdf"
    legacy_path = storage.legacy_patient_dossier_path(2, "+33696854785", legacy_name)
    os.makedirs(os.path.dirname(legacy_path), exist_ok=True)
    with open(legacy_path, "wb") as f:
        f.write(b"legacy")

    assert storage.patient_dossier_exists(legacy_name, 2, "+33696854785")
    assert storage.read_patient_dossier(legacy_name, 2, "+33696854785") == b"legacy"
    assert storage.delete_patient_dossier(legacy_name, 2, "+33696854785") is True
    assert storage.patient_dossier_exists(legacy_name, 2, "+33696854785") is False
