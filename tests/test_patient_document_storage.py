"""Tests stockage documents questionnaire V2 (local + S3)."""

from __future__ import annotations

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


def test_rejects_oversized_file(monkeypatch, tmp_path):
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.setattr(storage, "UPLOAD_ROOT", str(tmp_path))
    big = b"x" * (storage.MAX_UPLOAD_BYTES + 1)
    with pytest.raises(ValueError, match="10 Mo"):
        storage.save_questionnaire_upload(1, "+336", "r", big, "a.pdf", "application/pdf")
