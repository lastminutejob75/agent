from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "054_consular_core.sql"


def _migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_consular_schema_contains_required_tables_and_fields():
    sql = _migration_sql()

    for table in (
        "posts",
        "post_config",
        "applications",
        "application_documents",
        "application_events",
        "document_requirements",
        "document_labels",
        "counter_slots",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql

    for field in (
        "post_id UUID",
        "reference TEXT",
        "lang TEXT",
        "purpose TEXT",
        "visa_category TEXT",
        "reclassified_from TEXT",
        "passport_ok BOOLEAN",
        "host_nationality TEXT",
        "fee_exempt BOOLEAN",
        "is_minor BOOLEAN",
        "is_first_application BOOLEAN",
        "schengen_history BOOLEAN",
        "previous_refusal BOOLEAN",
        "qualified_at TIMESTAMPTZ",
    ):
        assert field in sql


def test_consular_rls_is_forced_and_checks_reads_and_writes():
    sql = _migration_sql()

    assert "CREATE OR REPLACE FUNCTION app_current_post_id()" in sql
    assert "CREATE OR REPLACE FUNCTION app_post_matches(candidate_post_id uuid)" in sql
    assert "ALTER TABLE %I FORCE ROW LEVEL SECURITY" in sql
    assert "USING (app_post_matches(post_id))" in sql
    assert "WITH CHECK (app_post_matches(post_id))" in sql

    for child_table in ("application_documents", "application_events"):
        assert f"ALTER TABLE {child_table} ENABLE ROW LEVEL SECURITY" in sql
        assert f"ALTER TABLE {child_table} FORCE ROW LEVEL SECURITY" in sql
        assert f"CREATE POLICY {child_table}_post_isolation" in sql


def test_document_requirements_are_post_scoped_and_labels_are_multilingual():
    sql = _migration_sql()

    assert (
        "PRIMARY KEY (post_id, visa_category, purpose, doc_key)"
        in sql
    )
    assert "CHECK (lang IN ('bg', 'fr', 'en', 'ar'))" in sql
