from backend.routes.tenant import _tenant_display_name


def test_tenant_display_name_prefers_business_name():
    detail = {
        "name": "Cabinet UWI",
        "params": {
            "business_name": "Cabinet Dupont",
        },
    }

    assert _tenant_display_name(detail, tenant_id=2) == "Cabinet Dupont"


def test_tenant_display_name_replaces_legacy_cabinet_uwi_placeholder():
    detail = {
        "name": "Cabinet UWI",
        "params": {},
    }

    assert _tenant_display_name(detail, tenant_id=2) == "Cabinet Dupont"


def test_tenant_display_name_replaces_legacy_uwi_placeholder(monkeypatch):
    detail = {
        "name": "uwi",
        "params": {},
    }

    monkeypatch.setattr(
        "backend.routes.tenant.get_tenant_display_config",
        lambda tenant_id: {"business_name": "Cabinet Dupont"},
    )

    assert _tenant_display_name(detail, tenant_id=2) == "Cabinet Dupont"
