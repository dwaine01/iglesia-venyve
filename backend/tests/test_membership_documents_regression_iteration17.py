"""Membership documents regression checks: RBAC, validation, cleanup and serialization."""
import io
import os

import pytest
import requests
from PIL import Image
from pymongo import MongoClient


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
PASTOR = ("coreqa.pastor@example.com", "CoreQA2026!Pastor")
LEADER = ("coreqa.leader@example.com", "CoreQA2026!Leader")
MEMBER = ("coreqa.member@example.com", "CoreQA2026!Member")
CAPABILITY = "membership.documents.manage"


def api(path: str) -> str:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is required")
    return f"{BASE_URL}{path}"


def login(credentials: tuple[str, str]) -> tuple[str, dict]:
    response = requests.post(
        api("/api/auth/login"),
        json={"email": credentials[0], "password": credentials[1]},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    return data["token"], data["user"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def transparent_png(width: int, height: int) -> bytes:
    image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def contains_forbidden_id(value):
    if isinstance(value, dict):
        if "_id" in value:
            return True
        return any(contains_forbidden_id(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_forbidden_id(item) for item in value)
    return False


# RBAC checks for membership documents manage capability and auth requirements
def test_membership_rbac_requires_explicit_capability_and_auth():
    pastor_token, _ = login(PASTOR)
    leader_token, _ = login(LEADER)
    member_token, member_user = login(MEMBER)
    person_id = member_user.get("person_id")
    assert person_id, "Member user must be linked to canonical person_id"

    no_auth = requests.get(api(f"/api/membership/persons/{person_id}"), timeout=30)
    assert no_auth.status_code == 401

    as_member = requests.get(api(f"/api/membership/persons/{person_id}"), headers=auth(member_token), timeout=30)
    assert as_member.status_code == 403

    users = requests.get(api("/api/core/governance/users"), headers=auth(pastor_token), timeout=30)
    assert users.status_code == 200, users.text
    leader = next(item for item in users.json()["items"] if item["email"] == LEADER[0])
    original = {
        "access_level": leader.get("access_level") or leader.get("rol"),
        "is_active": leader.get("is_active", True),
        "privilege_groups": leader.get("privilege_groups") or [],
        "capabilities": leader.get("capabilities") or [],
    }

    try:
        denied_leader = requests.get(api(f"/api/membership/persons/{person_id}"), headers=auth(leader_token), timeout=30)
        assert denied_leader.status_code == 403

        patched = {
            **original,
            "capabilities": sorted(set([*original["capabilities"], CAPABILITY])),
        }
        grant = requests.put(
            api(f"/api/core/governance/users/{leader['user_id']}/access"),
            headers={**auth(pastor_token), "Content-Type": "application/json"},
            json=patched,
            timeout=30,
        )
        assert grant.status_code == 200, grant.text

        leader_token, _ = login(LEADER)
        allowed_leader = requests.get(api(f"/api/membership/persons/{person_id}"), headers=auth(leader_token), timeout=30)
        assert allowed_leader.status_code == 200
    finally:
        restore = requests.put(
            api(f"/api/core/governance/users/{leader['user_id']}/access"),
            headers={**auth(pastor_token), "Content-Type": "application/json"},
            json=original,
            timeout=30,
        )
        assert restore.status_code == 200, restore.text


# Settings and signature validation checks for MIME, PNG magic bytes and dimensions
def test_membership_signature_rejects_invalid_file_cases():
    pastor_token, _ = login(PASTOR)

    wrong_mime = requests.post(
        api("/api/membership/settings/signature"),
        headers=auth(pastor_token),
        files={"file": ("firma.txt", b"not a png", "text/plain")},
        timeout=30,
    )
    assert wrong_mime.status_code == 415

    wrong_magic = requests.post(
        api("/api/membership/settings/signature"),
        headers=auth(pastor_token),
        files={"file": ("fake.png", b"not_png_content", "image/png")},
        timeout=30,
    )
    assert wrong_magic.status_code == 415

    too_small = requests.post(
        api("/api/membership/settings/signature"),
        headers=auth(pastor_token),
        files={"file": ("small.png", transparent_png(120, 60), "image/png")},
        timeout=30,
    )
    assert too_small.status_code == 422


# Governance response should not expose raw Mongo ObjectId fields
def test_core_governance_users_response_excludes_objectid_fields():
    pastor_token, _ = login(PASTOR)
    response = requests.get(api("/api/core/governance/users"), headers=auth(pastor_token), timeout=30)
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload and isinstance(payload["items"], list)
    assert contains_forbidden_id(payload) is False


# Ensure membership QA prefixes were cleaned up after e2e executions
def test_membership_cleanup_prefixes_absent():
    client = MongoClient(os.environ["MONGO_URL"])
    database = client[os.environ["DB_NAME"]]
    try:
        qa_member_doc_persons = database.persons.count_documents(
            {
                "$or": [
                    {"first_name": {"$regex": "QA-MEMBER-DOC"}},
                    {"last_name": {"$regex": "QA-MEMBER-DOC"}},
                    {"vv_number": {"$regex": "QA-MEMBER-DOC"}},
                ]
            }
        )
        qa_member_doc_photos = database.person_photos.count_documents(
            {
                "$or": [
                    {"filename": {"$regex": "QA-MEMBER-DOC"}},
                    {"person_id": {"$regex": "QA-MEMBER-DOC"}},
                ]
            }
        )
        qa_member_doc_ministry_catalog = database.ministry_catalog.count_documents({"_id": {"$regex": "QA-MEMBER-DOC"}})
        qa_member_doc_roles = database.ministry_roles.count_documents({"_id": {"$regex": "QA-MEMBER-DOC"}})
        qa_member_doc_assignments = database.ministry_assignments.count_documents(
            {
                "$or": [
                    {"_id": {"$regex": "QA-MEMBER-DOC"}},
                    {"person_id": {"$regex": "QA-MEMBER-DOC"}},
                ]
            }
        )
        qa_visual_memberships = database.person_memberships.count_documents(
            {
                "$or": [
                    {"member_number": {"$regex": "QA-MEMBERSHIP-VISUAL"}},
                    {"person_id": {"$regex": "QA-MEMBERSHIP-VISUAL"}},
                ]
            }
        )
        qa_issuances = database.membership_document_issuances.count_documents(
            {
                "$or": [
                    {"member_number": {"$regex": "^QA-MEMBERSHIP-VISUAL"}},
                    {"person_name_snapshot": {"$regex": "QA-MEMBERSHIP-VISUAL"}},
                ]
            }
        )
        assert qa_member_doc_persons == 0
        assert qa_member_doc_photos == 0
        assert qa_member_doc_ministry_catalog == 0
        assert qa_member_doc_roles == 0
        assert qa_member_doc_assignments == 0
        assert qa_visual_memberships == 0
        assert qa_issuances == 0
    finally:
        client.close()
