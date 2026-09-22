import inspect

import server


def test_every_finance_endpoint_has_the_expected_rbac_dependency():
    routes = [route for route in server.app.routes if route.path.startswith("/api/finance")]
    assert len(routes) == 63
    for route in routes:
        dependencies = {getattr(item.call, "__name__", "") for item in route.dependant.dependencies}
        expected = "private_person_reader" if route.path == "/api/finance/persons/{person_id}/contributions" else None
        if expected:
            assert expected in dependencies, f"{route.methods} {route.path} carece del gate privado"
        else:
            assert dependencies.intersection({"reader", "manager"}), f"{route.methods} {route.path} carece de gate financiero"


def test_every_board_endpoint_has_authentication_and_an_access_guard():
    routes = [route for route in server.app.routes if route.path.startswith("/api/board")]
    assert len(routes) == 41
    accepted_guards = {
        "ensure_board_access",
        "board_access_snapshot",
        "ensure_recording_access",
        "require_pastoral_board_admin",
        "ensure_pastor",
    }
    for route in routes:
        dependencies = {getattr(item.call, "__name__", "") for item in route.dependant.dependencies}
        source = inspect.getsource(route.endpoint)
        assert "get_current_user" in dependencies, f"{route.methods} {route.path} carece de autenticación"
        assert any(guard in source for guard in accepted_guards), f"{route.methods} {route.path} carece de gate de Junta"


def test_private_person_finance_does_not_share_the_module_reader():
    route = next(item for item in server.app.routes if item.path == "/api/finance/persons/{person_id}/contributions")
    dependencies = {getattr(item.call, "__name__", "") for item in route.dependant.dependencies}
    assert dependencies == {"private_person_reader"}