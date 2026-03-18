from backend.routes.tenant import _tenant_display_name


def test_tenant_display_name_prefers_business_name():
    detail = {
        "name": "Cabinet UWI",
        "params": {
            "business_name": "Cabinet Dupont",
        },
    }

    assert _tenant_display_name(detail, tenant_id=2) == "Cabinet Dupont"


def test_tenant_display_name_falls_back_to_tenant_name():
    detail = {
        "name": "Cabinet UWI",
        "params": {},
    }

    assert _tenant_display_name(detail, tenant_id=2) == "Cabinet UWI"
