"""E2E del carnet CR80, certificado Carta y verificación pública."""
import io
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import requests
from bson import Binary, ObjectId
from PIL import Image, ImageDraw
from pymongo import MongoClient


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
PASTOR = ("coreqa.pastor@example.com", "CoreQA2026!Pastor")
LEADER = ("coreqa.leader@example.com", "CoreQA2026!Leader")
MEMBER = ("coreqa.member@example.com", "CoreQA2026!Member")
CAPABILITY = "membership.documents.manage"


def api(path):
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is required")
    return f"{BASE_URL}{path}"


def login(credentials):
    response = requests.post(api("/api/auth/login"), json={"email": credentials[0], "password": credentials[1]}, timeout=30)
    assert response.status_code == 200, response.text
    return response.json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def signature_png(transparent=True):
    image = Image.new("RGBA", (700, 220), (255, 255, 255, 0 if transparent else 255))
    draw = ImageDraw.Draw(image)
    draw.line((80, 150, 600, 70), fill=(10, 42, 45, 255), width=12)
    draw.line((280, 65, 470, 175), fill=(10, 42, 45, 255), width=8)
    output = io.BytesIO(); image.save(output, format="PNG"); return output.getvalue()


@pytest.fixture
def membership_context():
    client = MongoClient(os.environ["MONGO_URL"]); database = client[os.environ["DB_NAME"]]
    pastor_token = login(PASTOR); users = requests.get(api("/api/core/governance/users"), headers=auth(pastor_token), timeout=30).json()["items"]
    leader = next(item for item in users if item["email"] == LEADER[0]); original_access = {"access_level": leader.get("access_level") or leader.get("rol"), "is_active": leader.get("is_active", True), "privilege_groups": leader.get("privilege_groups") or [], "capabilities": leader.get("capabilities") or []}
    original_settings = database.membership_document_settings.find_one({"settings_id": "primary"})
    original_counter = database.membership_counters.find_one({"counter_id": "member_number"})
    person_oid = ObjectId(); person_id = str(person_oid); prefix = f"QA-MEMBER-DOC-{uuid4().hex[:8]}"
    ministry_id = f"{prefix}-MINISTRY"; role_id = f"{prefix}-ROLE"; assignment_id = f"{prefix}-ASSIGNMENT"
    photo_id = str(uuid4()); photo = Image.new("RGB", (640, 800), (222, 232, 235)); draw = ImageDraw.Draw(photo); draw.ellipse((170, 120, 470, 420), fill=(156, 118, 89)); draw.rectangle((140, 430, 500, 800), fill=(25, 91, 111)); photo_bytes = io.BytesIO(); photo.save(photo_bytes, format="JPEG", quality=92)
    now = datetime.now(timezone.utc); membership_id = str(uuid4())
    database.persons.insert_one({"_id": person_oid, "first_name": "María Alejandra", "last_name": "Rodríguez de la Esperanza", "vv_number": "VV-90001", "idempotency_key": f"qa:membership:{prefix}", "estado": "activo", "created_at": now})
    database.membership_number_registry.delete_one({"member_number": "90001"})
    database.membership_number_registry.insert_one({"_id": "90001", "member_number": "90001", "person_id": person_id, "reserved_at": now, "source": "formal_acceptance_test"})
    database.person_memberships.insert_one({"_id": membership_id, "membership_id": membership_id, "person_id": person_id, "member_number": "90001", "status": "active", "acceptance_signed_at": now, "acceptance_verified_at": now, "acceptance_verified_by_user_id": "qa-test", "certificate_delivery_status": "pending_retreat", "card_delivery_status": "pending", "created_at": now, "updated_at": now})
    database.person_photos.insert_one({"_id": photo_id, "photo_id": photo_id, "person_id": person_id, "filename": f"{prefix}.jpg", "content_type": "image/jpeg", "data": Binary(photo_bytes.getvalue()), "is_current": True, "created_at": datetime.now(timezone.utc)})
    database.ministry_catalog.insert_one({"_id": ministry_id, "nombre": "Ministerio de Jóvenes", "activo": True})
    database.ministry_roles.insert_one({"_id": role_id, "nombre": "Directora", "normalized_name": "directora", "activo": True})
    database.ministry_assignments.insert_one({"_id": assignment_id, "person_id": person_id, "ministry_id": ministry_id, "role_id": role_id, "activo": True, "fecha_inicio": "2026-01-01", "version": 1})
    context = {"database": database, "client": client, "pastor_token": pastor_token, "leader": leader, "original_access": original_access, "original_settings": original_settings, "original_counter": original_counter, "person_id": person_id, "prefix": prefix, "photo_id": photo_id, "ministry_id": ministry_id, "role_id": role_id, "assignment_id": assignment_id, "signature_ids": []}
    try:
        yield context
    finally:
        requests.put(api(f"/api/core/governance/users/{leader['user_id']}/access"), headers={**auth(pastor_token), "Content-Type": "application/json"}, json=original_access, timeout=30)
        membership = database.person_memberships.find_one({"person_id": person_id}, {"_id": 0})
        if membership:
            database.membership_document_issuances.delete_many({"membership_id": membership["membership_id"]})
            database.person_memberships.delete_one({"membership_id": membership["membership_id"]})
            database.membership_number_registry.delete_one({"member_number": membership["member_number"]})
        database.person_photos.delete_many({"person_id": person_id})
        database.ministry_assignments.delete_one({"_id": assignment_id}); database.ministry_roles.delete_one({"_id": role_id}); database.ministry_catalog.delete_one({"_id": ministry_id}); database.persons.delete_one({"_id": person_oid})
        if original_settings:
            database.membership_document_settings.replace_one({"settings_id": "primary"}, original_settings, upsert=True)
        for signature_id in context["signature_ids"]:
            if ObjectId.is_valid(signature_id):
                oid = ObjectId(signature_id); database[f"membership_signatures.files"].delete_one({"_id": oid}); database[f"membership_signatures.chunks"].delete_many({"files_id": oid})
        if original_counter:
            database.membership_counters.replace_one({"counter_id": "member_number"}, original_counter, upsert=True)
        else:
            database.membership_counters.delete_one({"counter_id": "member_number"})
        client.close()


def test_membership_card_certificate_and_public_verification(membership_context):
    ctx = membership_context; pastor_token = ctx["pastor_token"]; member_token = login(MEMBER); leader_token = login(LEADER)
    denied = requests.get(api(f"/api/membership/persons/{ctx['person_id']}"), headers=auth(member_token), timeout=30)
    assert denied.status_code == 403
    leader_payload = {"access_level": ctx["leader"].get("access_level") or ctx["leader"].get("rol"), "is_active": True, "privilege_groups": ctx["leader"].get("privilege_groups") or [], "capabilities": list(set((ctx["leader"].get("capabilities") or []) + [CAPABILITY]))}
    grant = requests.put(api(f"/api/core/governance/users/{ctx['leader']['user_id']}/access"), headers={**auth(pastor_token), "Content-Type": "application/json"}, json=leader_payload, timeout=30)
    assert grant.status_code == 200, grant.text
    leader_token = login(LEADER)
    assert requests.get(api(f"/api/membership/persons/{ctx['person_id']}"), headers=auth(leader_token), timeout=30).status_code == 200
    forbidden_config = requests.put(api("/api/membership/settings"), headers={**auth(leader_token), "Content-Type": "application/json"}, json={"expiration_months": 14, "authorized_signer_name": "Pastora QA", "authorized_signer_title": "Pastora Principal", "organization_name": "Casa de Oración Ven y Ve"}, timeout=30)
    assert forbidden_config.status_code == 403

    configured = requests.put(api("/api/membership/settings"), headers={**auth(pastor_token), "Content-Type": "application/json"}, json={"expiration_months": 14, "authorized_signer_name": "Pastora QA", "authorized_signer_title": "Pastora Principal", "organization_name": "Casa de Oración Ven y Ve"}, timeout=30)
    assert configured.status_code == 200, configured.text
    opaque = requests.post(api("/api/membership/settings/signature"), headers=auth(pastor_token), files={"file": ("firma-opaca.png", signature_png(False), "image/png")}, timeout=30)
    assert opaque.status_code == 422
    uploaded = requests.post(api("/api/membership/settings/signature"), headers=auth(pastor_token), files={"file": ("firma-qa.png", signature_png(True), "image/png")}, timeout=30)
    assert uploaded.status_code == 200, uploaded.text
    ctx["signature_ids"].append(uploaded.json()["signature_file_id"])

    card = requests.post(api(f"/api/membership/persons/{ctx['person_id']}/documents/card/issue"), headers={**auth(leader_token), "Content-Type": "application/json"}, json={"issue_date": "2026-04-26"}, timeout=30)
    assert card.status_code == 201, card.text
    card_data = card.json()["data"]
    assert card.json()["action"] == "issued"
    assert card_data["membership"]["member_number"] == "90001"
    assert card_data["membership"]["card_issue_date"] == "2026-04-26"
    assert card_data["membership"]["card_expiration_date"] == "2027-06-26"
    assert card_data["person"]["position"] == "DIRECTORA · MINISTERIO DE JÓVENES"
    assert "email" not in card_data["person"] and "phone" not in card_data["person"]
    reprint = requests.post(api(f"/api/membership/persons/{ctx['person_id']}/documents/card/issue"), headers={**auth(leader_token), "Content-Type": "application/json"}, json={"issue_date": "2026-05-01"}, timeout=30)
    assert reprint.status_code == 201 and reprint.json()["action"] == "reprinted"
    assert reprint.json()["data"]["membership"]["card_issue_date"] == "2026-04-26"
    assert reprint.json()["data"]["membership"]["member_number"] == "90001"
    renewed = requests.post(api(f"/api/membership/persons/{ctx['person_id']}/card/renew"), headers={**auth(leader_token), "Content-Type": "application/json"}, json={"issue_date": "2026-06-15"}, timeout=30)
    assert renewed.status_code == 200, renewed.text
    assert renewed.json()["data"]["membership"]["member_number"] == "90001"
    assert renewed.json()["data"]["membership"]["card_expiration_date"] == "2027-08-15"

    certificate = requests.post(api(f"/api/membership/persons/{ctx['person_id']}/documents/certificate/issue"), headers={**auth(leader_token), "Content-Type": "application/json"}, json={"issue_date": "2026-04-26"}, timeout=30)
    assert certificate.status_code == 201, certificate.text
    certificate_data = certificate.json()["data"]
    assert certificate_data["membership"]["certificate_issue_date"] == "2026-04-26"
    assert certificate_data["certificate"]["authorized_signer_name"] == "Pastora QA"
    signature = requests.get(api("/api/membership/settings/signature"), headers=auth(leader_token), timeout=30)
    assert signature.status_code == 200 and signature.headers["content-type"].startswith("image/png")

    verification_url = certificate_data["verification_path"].replace("/verificar/carnet/", "/api/public/membership/verify/")
    verification = requests.get(api(verification_url), timeout=30)
    assert verification.status_code == 200, verification.text
    verified = verification.json()
    assert verified["valid"] is True and verified["member_number"] == "90001"
    assert verified["member_name"] == "María Alejandra Rodríguez de la Esperanza"
    assert set(verified).isdisjoint({"email", "phone", "address", "person_id", "financial_history"})
    invalid = requests.get(api("/api/public/membership/verify/token-invalido"), timeout=30)
    assert invalid.status_code == 200 and invalid.json() == {"valid": False, "status": "invalid"}
    issuances = requests.get(api(f"/api/membership/persons/{ctx['person_id']}/issuances"), headers=auth(leader_token), timeout=30)
    assert issuances.status_code == 200
    assert [item["action"] for item in issuances.json()["items"]] == ["issued", "renewed", "reprinted", "issued"]