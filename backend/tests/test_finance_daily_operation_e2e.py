"""E2E real del ciclo financiero diario de una iglesia, con cleanup estricto."""
import os
from uuid import uuid4

import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
PASTOR = ("coreqa.pastor@example.com", "CoreQA2026!Pastor")
LEADER = ("coreqa.leader@example.com", "CoreQA2026!Leader")
MEMBER = ("coreqa.member@example.com", "CoreQA2026!Member")


def api(path):
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is required")
    return f"{BASE_URL}{path}"


def login(credentials):
    response = requests.post(api("/api/auth/login"), json={"email": credentials[0], "password": credentials[1]}, timeout=30)
    assert response.status_code == 200, response.text
    return response.json()["token"], response.json()["user"]


def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def governance_users(token):
    response = requests.get(api("/api/core/governance/users"), headers=headers(token), timeout=30)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def user_by_email(users, email):
    return next(item for item in users if item.get("email", "").lower() == email.lower())


def access_payload(user, finance=False):
    groups = list(user.get("privilege_groups") or ["membership"])
    groups = [group for group in groups if group != "finance"]
    if finance:
        groups.append("finance")
    capabilities = list(user.get("capabilities") or [])
    if not finance:
        capabilities = [capability for capability in capabilities if not capability.startswith("finance.")]
    return {"access_level": user.get("access_level") or user.get("rol"), "is_active": user.get("is_active", True), "privilege_groups": groups, "capabilities": capabilities}


def update_access(token, user, finance):
    payload = access_payload(user, finance)
    if finance:
        payload.pop("capabilities", None)
    return requests.put(api(f"/api/core/governance/users/{user['user_id']}/access"), headers=headers(token), json=payload, timeout=30)


def post(token, path, payload):
    return requests.post(api(path), headers=headers(token), json=payload, timeout=30)


def workflow(entry_id, leader_token, pastor_token):
    reviewed = post(leader_token, f"/api/finance/journals/{entry_id}/review", {})
    assert reviewed.status_code == 200, reviewed.text
    approved = post(pastor_token, f"/api/finance/journals/{entry_id}/approve", {})
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "posted"


@pytest.fixture
def daily_finance_state():
    pastor_token, _ = login(PASTOR)
    users = governance_users(pastor_token)
    leader = user_by_email(users, LEADER[0])
    member = user_by_email(users, MEMBER[0])
    originals = {"leader": access_payload(leader, "finance" in (leader.get("privilege_groups") or [])), "member": access_payload(member, "finance" in (member.get("privilege_groups") or []))}
    prefix = f"QA-G28-{uuid4().hex[:8]}"
    state = {"prefix": prefix, "pastor_token": pastor_token, "leader": leader, "member": member, "originals": originals, "statement_ids": []}
    assert update_access(pastor_token, leader, True).status_code == 200
    assert update_access(pastor_token, member, True).status_code == 200
    try:
        yield state
    finally:
        update_access(pastor_token, leader, False)
        requests.put(api(f"/api/core/governance/users/{leader['user_id']}/access"), headers=headers(pastor_token), json=originals["leader"], timeout=30)
        update_access(pastor_token, member, False)
        requests.put(api(f"/api/core/governance/users/{member['user_id']}/access"), headers=headers(pastor_token), json=originals["member"], timeout=30)

        client = MongoClient(os.environ["MONGO_URL"])
        database = client[os.environ["DB_NAME"]]
        contributions = list(database.finance_contributions.find({"reference": {"$regex": f"^{prefix}"}}, {"contribution_id": 1, "journal_entry_id": 1}))
        contribution_ids = [item["contribution_id"] for item in contributions]
        batches = list(database.finance_batches.find({"service_name": {"$regex": f"^{prefix}"}}, {"batch_id": 1}))
        batch_ids = [item["batch_id"] for item in batches]
        deposits = list(database.finance_deposits.find({"reference": {"$regex": f"^{prefix}"}}, {"deposit_id": 1, "journal_entry_id": 1}))
        deposit_ids = [item["deposit_id"] for item in deposits]
        vendors = list(database.finance_vendors.find({"name": {"$regex": f"^{prefix}"}}, {"vendor_id": 1}))
        vendor_ids = [item["vendor_id"] for item in vendors]
        expenses = list(database.finance_expenses.find({"description": {"$regex": f"^{prefix}"}}, {"expense_id": 1, "payment_id": 1, "journal_entry_id": 1}))
        expense_ids = [item["expense_id"] for item in expenses]
        payments = list(database.finance_payments.find({"expense_id": {"$in": expense_ids}}, {"payment_id": 1, "journal_entry_id": 1}))
        payment_ids = [item["payment_id"] for item in payments]
        campaigns = list(database.finance_campaigns.find({"name": {"$regex": f"^{prefix}"}}, {"campaign_id": 1}))
        campaign_ids = [item["campaign_id"] for item in campaigns]
        obligations = list(database.finance_recurring_obligations.find({"name": {"$regex": f"^{prefix}"}}, {"obligation_id": 1}))
        obligation_ids = [item["obligation_id"] for item in obligations]
        recurring_expenses = list(database.finance_expenses.find({"recurring_obligation_id": {"$in": obligation_ids}}, {"expense_id": 1, "journal_entry_id": 1, "payment_id": 1}))
        expense_ids += [item["expense_id"] for item in recurring_expenses]
        reconciliations = list(database.finance_reconciliations.find({"notes": {"$regex": f"^{prefix}"}}, {"reconciliation_id": 1}))
        reconciliation_ids = [item["reconciliation_id"] for item in reconciliations]
        periods = list(database.finance_periods.find({"name": {"$regex": f"^{prefix}"}}, {"period_id": 1}))
        period_ids = [item["period_id"] for item in periods]
        corrections = list(database.finance_contribution_corrections.find({"original_contribution_id": {"$in": contribution_ids}}, {"correction_id": 1, "reversal_journal_entry_id": 1}))
        correction_ids = [item["correction_id"] for item in corrections]
        journal_ids = [item.get("journal_entry_id") for item in contributions + deposits + expenses + payments + recurring_expenses if item.get("journal_entry_id")]
        journal_ids += [item.get("reversal_journal_entry_id") for item in corrections if item.get("reversal_journal_entry_id")]
        standalone = list(database.finance_journal_entries.find({"$or": [{"entry_id": {"$in": journal_ids}}, {"memo": {"$regex": f"^{prefix}"}}]}, {"entry_id": 1}))
        journal_ids = list({item["entry_id"] for item in standalone})
        file_docs = list(database["finance_documents.files"].find({"metadata.entity_id": {"$in": expense_ids}}, {"_id": 1}))
        file_ids = [item["_id"] for item in file_docs]

        if file_ids:
            database["finance_documents.files"].delete_many({"_id": {"$in": file_ids}})
            database["finance_documents.chunks"].delete_many({"files_id": {"$in": file_ids}})
        database.finance_annual_statements.delete_many({"statement_id": {"$in": state["statement_ids"]}})
        database.finance_contribution_corrections.delete_many({"correction_id": {"$in": correction_ids}})
        database.finance_recurring_runs.delete_many({"obligation_id": {"$in": obligation_ids}})
        database.finance_recurring_obligations.delete_many({"obligation_id": {"$in": obligation_ids}})
        database.finance_reconciliations.delete_many({"reconciliation_id": {"$in": reconciliation_ids}})
        database.finance_payments.delete_many({"$or": [{"payment_id": {"$in": payment_ids}}, {"expense_id": {"$in": expense_ids}}]})
        database.finance_expenses.delete_many({"expense_id": {"$in": expense_ids}})
        database.finance_vendors.delete_many({"vendor_id": {"$in": vendor_ids}})
        database.finance_deposits.delete_many({"deposit_id": {"$in": deposit_ids}})
        database.finance_batches.delete_many({"batch_id": {"$in": batch_ids}})
        database.finance_contributions.delete_many({"contribution_id": {"$in": contribution_ids}})
        database.finance_journal_entries.delete_many({"entry_id": {"$in": journal_ids}})
        database.finance_budgets.delete_many({"category": {"$regex": f"^{prefix}"}})
        database.finance_campaigns.delete_many({"campaign_id": {"$in": campaign_ids}})
        database.finance_periods.delete_many({"period_id": {"$in": period_ids}})
        entity_ids = contribution_ids + batch_ids + deposit_ids + vendor_ids + expense_ids + payment_ids + campaign_ids + obligation_ids + reconciliation_ids + period_ids + correction_ids + journal_ids + state["statement_ids"]
        if entity_ids:
            database.finance_audit_events.delete_many({"entity_id": {"$in": entity_ids}})
        client.close()


def test_daily_church_finance_cycle(daily_finance_state):
    state = daily_finance_state
    prefix = state["prefix"]
    pastor_token = state["pastor_token"]
    leader_token, _ = login(LEADER)
    member_token, _ = login(MEMBER)
    person_id = state["member"].get("person_id")
    assert person_id

    catalog_response = requests.get(api("/api/finance/catalog"), headers=headers(member_token), timeout=30)
    assert catalog_response.status_code == 200, catalog_response.text
    catalog = catalog_response.json()
    funds = {item["code"]: item for item in catalog["funds"]}
    accounts = {item["code"]: item for item in catalog["accounts"]}
    types = {item["type_key"] for item in catalog["contribution_types"]}
    assert {"tithe", "offering", "donation", "missions", "building", "project", "other"}.issubset(types)
    assert "GENERAL" in funds and "BUILDING" in funds

    batch = post(member_token, "/api/finance/batches", {"batch_date": "2026-09-20", "service_date": "2026-09-20", "service_name": f"{prefix} Servicio domingo", "expected_envelope_count": 3, "contribution_ids": [], "location": "Oficina", "notes": f"{prefix} Conteo"})
    assert batch.status_code == 201, batch.text
    assert batch.json()["status"] == "collecting"
    batch_id = batch.json()["batch_id"]

    campaign = post(member_token, "/api/finance/campaigns", {"name": f"{prefix} Pro-Templo", "fund_id": funds["BUILDING"]["fund_id"], "goal_cents": 500000, "budget_cents": 150000, "project_type": "project", "description": "Proyecto E2E", "start_date": "2026-09-01", "end_date": None})
    assert campaign.status_code == 201, campaign.text
    campaign_id = campaign.json()["campaign_id"]

    envelope = post(member_token, "/api/finance/contributions", {"person_id": person_id, "anonymous": False, "amount_cents": 22000, "received_date": "2026-09-20", "payment_method": "cash", "reference": f"{prefix}-ENVELOPE", "envelope_number": "43", "notes": "Servicio domingo", "batch_id": batch_id, "source": "manual", "allocations": [{"fund_id": funds["GENERAL"]["fund_id"], "amount_cents": 20000, "contribution_type": "tithe", "description": "Diezmo"}, {"fund_id": funds["GENERAL"]["fund_id"], "amount_cents": 2000, "contribution_type": "offering", "description": "Ofrenda"}]})
    assert envelope.status_code == 201, envelope.text
    assert envelope.json()["contribution_type"] == "mixed"

    zelle = post(member_token, "/api/finance/contributions", {"person_id": person_id, "anonymous": False, "amount_cents": 30000, "received_date": "2026-09-20", "payment_method": "zelle", "reference": f"{prefix}-ZELLE-BANK-300", "notes": "Confirmado en banco", "batch_id": batch_id, "source": "manual", "allocations": [{"fund_id": funds["GENERAL"]["fund_id"], "amount_cents": 30000, "contribution_type": "tithe"}]})
    assert zelle.status_code == 201, zelle.text

    building = post(member_token, "/api/finance/contributions", {"person_id": person_id, "anonymous": False, "amount_cents": 10000, "received_date": "2026-09-20", "payment_method": "cash", "reference": f"{prefix}-BUILDING", "description": "Donación designada Pro-Templo", "batch_id": batch_id, "source": "manual", "allocations": [{"fund_id": funds["BUILDING"]["fund_id"], "amount_cents": 10000, "contribution_type": "donation", "campaign_id": campaign_id, "description": "Pro-Templo"}]})
    assert building.status_code == 201, building.text
    contributions = [envelope.json(), zelle.json(), building.json()]

    started = post(member_token, f"/api/finance/batches/{batch_id}/start-count", {})
    assert started.status_code == 200, started.text
    batch_data = started.json()
    assert batch_data["expected_total_cents"] == 62000
    assert batch_data["expected_concept_totals"]["tithe"] == 50000
    assert batch_data["expected_concept_totals"]["offering"] == 2000
    assert batch_data["expected_concept_totals"]["donation"] == 10000
    first_count = post(member_token, f"/api/finance/batches/{batch_data['batch_id']}/counts", {"cash_cents": 32000, "check_cents": 0, "other_cents": 30000, "envelope_count": 3, "notes": "Primer conteo"})
    assert first_count.status_code == 200, first_count.text
    second_count = post(leader_token, f"/api/finance/batches/{batch_data['batch_id']}/counts", {"cash_cents": 32000, "check_cents": 0, "other_cents": 30000, "envelope_count": 3, "notes": "Segundo conteo independiente"})
    assert second_count.status_code == 200, second_count.text
    assert second_count.json()["status"] == "ready_for_deposit"

    deposit = post(member_token, "/api/finance/deposits", {"deposit_date": "2026-09-20", "bank_account_id": accounts["1020"]["account_id"], "contribution_ids": [item["contribution_id"] for item in contributions], "reference": f"{prefix}-DEPOSIT-SLIP", "batch_id": batch_data["batch_id"]})
    assert deposit.status_code == 201, deposit.text
    deposit_data = deposit.json()
    assert deposit_data["total_cents"] == 62000

    for item in contributions:
        workflow(item["journal_entry_id"], leader_token, pastor_token)
    workflow(deposit_data["journal_entry_id"], leader_token, pastor_token)

    vendor = post(member_token, "/api/finance/vendors", {"name": f"{prefix} Internet Provider", "email": None, "phone": None, "tax_id_last4": None})
    assert vendor.status_code == 201, vendor.text
    expense = post(member_token, "/api/finance/expenses", {"vendor_id": vendor.json()["vendor_id"], "invoice_number": f"{prefix}-INV", "expense_date": "2026-09-20", "due_date": "2026-09-20", "description": f"{prefix} Internet septiembre", "total_cents": 12000, "allocations": [{"account_id": accounts["5030"]["account_id"], "fund_id": funds["GENERAL"]["fund_id"], "debit_cents": 12000, "credit_cents": 0, "description": "Internet"}], "category": "Internet", "expense_nature": "fixed", "beneficiary_type": "vendor", "receipt_confirmed": True})
    assert expense.status_code == 201, expense.text
    expense_id = expense.json()["expense_id"]

    upload = requests.post(api("/api/finance/documents"), headers={"Authorization": f"Bearer {member_token}"}, data={"entity_type": "expense", "entity_id": expense_id}, files={"file": (f"{prefix}.pdf", b"%PDF-1.4\n% QA receipt\n%%EOF", "application/pdf")}, timeout=30)
    assert upload.status_code == 201, upload.text
    assert upload.json()["metadata"]["sha256"]

    reviewed = post(leader_token, f"/api/finance/expenses/{expense_id}/workflow/review", {})
    assert reviewed.status_code == 200, reviewed.text
    approved = post(pastor_token, f"/api/finance/expenses/{expense_id}/workflow/approve", {})
    assert approved.status_code == 200, approved.text
    scheduled = post(member_token, f"/api/finance/expenses/{expense_id}/schedule", {"scheduled_date": "2026-09-20", "bank_account_id": accounts["1020"]["account_id"], "payment_method": "ach", "reference": f"{prefix}-SCHEDULE"})
    assert scheduled.status_code == 200, scheduled.text
    payment = post(member_token, f"/api/finance/expenses/{expense_id}/payments", {"payment_date": "2026-09-20", "bank_account_id": accounts["1020"]["account_id"], "payment_method": "ach", "reference": f"{prefix}-PAYMENT"})
    assert payment.status_code == 201, payment.text
    workflow(payment.json()["journal_entry_id"], leader_token, pastor_token)
    paid_expenses = requests.get(api("/api/finance/expenses"), headers=headers(member_token), timeout=30).json()["items"]
    assert next(item for item in paid_expenses if item["expense_id"] == expense_id)["status"] == "paid"

    reconciliation = post(member_token, "/api/finance/reconciliations", {"bank_account_id": accounts["1020"]["account_id"], "statement_end_date": "2026-09-20", "statement_starting_balance_cents": 0, "statement_ending_balance_cents": 50000, "cleared_entry_ids": [deposit_data["journal_entry_id"], payment.json()["journal_entry_id"]], "notes": f"{prefix} Banco"})
    assert reconciliation.status_code == 201, reconciliation.text
    assert reconciliation.json()["status"] == "balanced"

    budget = post(member_token, "/api/finance/budgets", {"fiscal_year": 2026, "fund_id": funds["GENERAL"]["fund_id"], "account_id": accounts["5030"]["account_id"], "amount_cents": 100000, "ministry_id": "operations", "campaign_id": None, "category": f"{prefix} Internet"})
    assert budget.status_code == 201, budget.text
    fund_activity = requests.get(api(f"/api/finance/funds/{funds['GENERAL']['fund_id']}/activity"), headers=headers(member_token), timeout=30)
    assert fund_activity.status_code == 200, fund_activity.text
    assert fund_activity.json()["received_cents"] == 52000
    assert fund_activity.json()["spent_cents"] == 12000
    project_activity = requests.get(api(f"/api/finance/campaigns/{campaign_id}/activity"), headers=headers(member_token), timeout=30)
    assert project_activity.status_code == 200, project_activity.text
    assert project_activity.json()["received_cents"] == 10000

    summary = requests.get(api(f"/api/finance/contributors/{person_id}?year=2026"), headers=headers(member_token), timeout=30)
    assert summary.status_code == 200, summary.text
    summary_data = summary.json()
    assert summary_data["total_cents"] == 62000
    assert summary_data["totals_by_type"]["tithe"] == 50000
    assert summary_data["totals_by_type"]["offering"] == 2000
    assert summary_data["totals_by_type"]["donation"] == 10000
    search = requests.get(api(f"/api/finance/contributors/search?search={summary_data['person']['name'].split()[0]}"), headers=headers(member_token), timeout=30)
    assert search.status_code == 200 and any(item["person_id"] == person_id for item in search.json()["items"])
    statement = post(member_token, f"/api/finance/contributors/{person_id}/annual-statements/2026", {})
    assert statement.status_code == 201, statement.text
    state["statement_ids"].append(statement.json()["statement_id"])
    assert statement.json()["total_cents"] == 62000
    assert statement.json()["status"] in {"approved_template", "draft_pending_legal_approval"}

    period = post(pastor_token, "/api/finance/periods", {"name": f"{prefix} Septiembre", "start_date": "2026-09-20", "end_date": "2026-09-20"})
    assert period.status_code == 201, period.text
    period_id = period.json()["period_id"]
    checklist = requests.get(api(f"/api/finance/periods/{period_id}/checklist"), headers=headers(pastor_token), timeout=30)
    assert checklist.status_code == 200, checklist.text
    assert checklist.json()["checks"]["ready_to_close"] is True, checklist.text
    closed = post(pastor_token, f"/api/finance/periods/{period_id}/close", {})
    assert closed.status_code == 200, closed.text
    blocked_closed_period = post(member_token, "/api/finance/contributions", {"person_id": person_id, "anonymous": False, "amount_cents": 100, "received_date": "2026-09-20", "payment_method": "cash", "reference": f"{prefix}-BLOCKED-CLOSED", "source": "manual", "allocations": [{"fund_id": funds["GENERAL"]["fund_id"], "amount_cents": 100, "contribution_type": "tithe"}]})
    assert blocked_closed_period.status_code == 409, blocked_closed_period.text
    reopened = post(pastor_token, f"/api/finance/periods/{period_id}/reopen", {"reason": f"{prefix} Ajuste autorizado"})
    assert reopened.status_code == 200, reopened.text

    posted_correction = post(member_token, f"/api/finance/contributions/{building.json()['contribution_id']}/correct", {"reason": "Destino contable corregido después de contabilizar", "correction_date": "2026-10-01", "replacement": {"person_id": person_id, "anonymous": False, "amount_cents": 10000, "received_date": "2026-09-20", "payment_method": "cash", "reference": f"{prefix}-BUILDING-POSTED-CORRECTION", "description": "Donación designada Pro-Templo corregida", "source": "manual", "allocations": [{"fund_id": funds["BUILDING"]["fund_id"], "amount_cents": 10000, "contribution_type": "building", "campaign_id": campaign_id, "description": "Pro-Templo"}]}})
    assert posted_correction.status_code == 201, posted_correction.text
    assert posted_correction.json()["reversal_journal_entry_id"]
    adjusted_deposit = next(item for item in requests.get(api("/api/finance/deposits"), headers=headers(member_token), timeout=30).json()["items"] if item["deposit_id"] == deposit_data["deposit_id"])
    assert adjusted_deposit["status"] == "adjustment_required"

    correction_original = post(member_token, "/api/finance/contributions", {"person_id": person_id, "anonymous": False, "amount_cents": 3000, "received_date": "2026-10-01", "payment_method": "zelle", "reference": f"{prefix}-CORRECTION", "source": "manual", "allocations": [{"fund_id": funds["GENERAL"]["fund_id"], "amount_cents": 3000, "contribution_type": "offering"}]})
    assert correction_original.status_code == 201, correction_original.text
    correction = post(member_token, f"/api/finance/contributions/{correction_original.json()['contribution_id']}/correct", {"reason": "El concepto correcto es diezmo", "correction_date": "2026-10-01", "replacement": {"person_id": person_id, "anonymous": False, "amount_cents": 3000, "received_date": "2026-10-01", "payment_method": "zelle", "reference": f"{prefix}-CORRECTION-REPLACEMENT", "source": "manual", "allocations": [{"fund_id": funds["GENERAL"]["fund_id"], "amount_cents": 3000, "contribution_type": "tithe"}]}})
    assert correction.status_code == 201, correction.text
    assert correction.json()["before"]["contribution_type"] == "offering"

    recurring = post(member_token, "/api/finance/recurring-obligations", {"name": f"{prefix} Internet mensual", "vendor_id": vendor.json()["vendor_id"], "beneficiary_type": "vendor", "description": f"{prefix} Internet recurrente", "category": "Internet", "expense_nature": "fixed", "amount_cents": 12000, "account_id": accounts["5030"]["account_id"], "fund_id": funds["GENERAL"]["fund_id"], "frequency": "monthly", "next_due_date": "2026-10-01", "active": True})
    assert recurring.status_code == 201, recurring.text
    generated = post(member_token, "/api/finance/recurring-obligations/generate?through_date=2026-10-01", {})
    assert generated.status_code == 200, generated.text
    assert generated.json()["generated"] == 1
    generated_again = post(member_token, "/api/finance/recurring-obligations/generate?through_date=2026-10-01", {})
    assert generated_again.status_code == 200 and generated_again.json()["generated"] == 0

    audit_report = requests.get(api("/api/finance/reports/audit"), headers=headers(member_token), timeout=30)
    assert audit_report.status_code == 200
    actions = {item["action"] for item in audit_report.json()["items"]}
    assert {"contribution_created", "batch_created", "deposit_created", "payment_created", "reconciliation_created", "annual_statement_generated", "contribution_corrected"}.issubset(actions)
    pushpay = requests.get(api("/api/finance/integrations/pushpay"), headers=headers(member_token), timeout=30)
    assert pushpay.status_code == 200 and pushpay.json()["status"] == "blocked_credentials_required"

    assert update_access(pastor_token, state["member"], False).status_code == 200
    member_token_without_finance, _ = login(MEMBER)
    confidential = requests.get(api(f"/api/finance/contributors/{person_id}?year=2026"), headers=headers(member_token_without_finance), timeout=30)
    assert confidential.status_code == 403
    assert update_access(pastor_token, state["member"], True).status_code == 200