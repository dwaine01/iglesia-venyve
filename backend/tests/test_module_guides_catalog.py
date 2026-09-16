import server  # noqa: F401

from module_guides import load_guides, prepare_guide


EXPECTED_GUIDES = {
    "dashboard_general", "leader_dashboard", "personal_progress", "core_governance",
    "persons_directory", "person_create", "person_profile", "talent_directory",
    "ministries", "ministry_detail", "processes_dashboard", "processes_seven_weeks",
    "processes_seven_weeks_detail", "processes_consolidation", "processes_mentorship",
    "processes_cap", "evangelism_journal", "invite_codes", "statistics",
    "seven_weeks_manual", "cellular_dashboard", "cellular_networks", "cellular_cells",
    "cellular_meeting", "cellular_ready", "cellular_needs", "cellular_health",
    "doors_dashboard", "door_profile", "board_dashboard", "board_meeting",
    "board_recording",
}


def test_every_platform_module_has_a_complete_context_guide():
    catalog = load_guides()
    assert catalog["schema_version"] == "2.0"
    assert EXPECTED_GUIDES.issubset(catalog["modules"])

    for module_key in EXPECTED_GUIDES:
        raw = {**catalog["modules"][module_key], "module_key": module_key}
        guide = prepare_guide(raw, {"rol": "pastor"})
        for field in ["title", "purpose", "result", "next", "role_focus", "example"]:
            assert guide.get(field), f"{module_key} missing {field}"
        for field in ["flow", "roles", "states", "steps", "inputs", "outputs", "connections", "common_errors", "good_practices", "tour_steps"]:
            assert isinstance(guide.get(field), list) and guide[field], f"{module_key} missing {field}"


def test_role_focus_and_tour_steps_are_adapted_per_user_role():
    raw = {**load_guides()["modules"]["processes_dashboard"], "module_key": "processes_dashboard"}

    pastor = prepare_guide(raw, {"rol": "pastor"})
    leader = prepare_guide(raw, {"rol": "lider"})
    person = prepare_guide(raw, {"rol": "persona"})

    assert pastor["active_role_label"] == "Pastor"
    assert leader["active_role_label"] == "Líder"
    assert person["active_role_label"] == "Persona"
    assert pastor["role_focus"] != leader["role_focus"] != person["role_focus"]
    assert any(step["target"] == "open-alert-rules-button" for step in pastor["tour_steps"])
    assert all(step["target"] != "open-alert-rules-button" for step in leader["tour_steps"])