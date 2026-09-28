"""Librería 360 · Fase 4: Centro de Reportes exportables (PDF/Excel).
Lee exclusivamente datos ya existentes del ledger/catálogo/compras — no crea
ningún dato ni sistema paralelo, solo tabula y exporta lo que ya existe,
respetando exactamente los filtros seleccionados."""
import io
from datetime import date, datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from access_control import LIBRARY_DELIVER, LIBRARY_REPORTS_READ, has_capability
from library_module import canonical_person, holder_label, is_library_manager, now_utc, person_display_name
from library_purchase_orders import po_overdue_info
from server import db, get_current_user

router = APIRouter(prefix="/api/library/reports", tags=["library-reports"])

PAYMENT_LABELS = {"pagado": "Pagado", "pendiente": "Pendiente", "exonerado": "Exonerado", "beca": "Beca",
                   "descuento": "Descuento", "pago_parcial": "Pago parcial", "no_aplica": "Gratis"}
STATUS_LABELS = {"draft": "Borrador", "submitted": "Enviada a Finanzas", "approved": "Aprobada", "rejected": "Rechazada",
                  "changes_requested": "Devuelta para cambios", "ordered": "Ordenada", "partially_received": "Recibida parcial",
                  "received": "Recibida completa", "closed": "Cerrada", "cancelled": "Cancelada"}

REPORTS_CATALOG = [
    {"key": "inventory_current", "name": "Inventario actual", "group": "Inventario"},
    {"key": "inventory_by_process", "name": "Inventario por proceso", "group": "Inventario"},
    {"key": "inventory_by_responsible", "name": "Inventario por responsable", "group": "Inventario"},
    {"key": "delivered", "name": "Materiales entregados", "group": "Movimientos"},
    {"key": "reserved", "name": "Materiales reservados", "group": "Movimientos"},
    {"key": "pending", "name": "Materiales pendientes", "group": "Movimientos"},
    {"key": "free_materials", "name": "Materiales gratuitos", "group": "Movimientos"},
    {"key": "sold_materials", "name": "Materiales vendidos", "group": "Financiero"},
    {"key": "library_income", "name": "Ingresos de Librería", "group": "Financiero"},
    {"key": "pending_payments", "name": "Pagos pendientes", "group": "Financiero"},
    {"key": "purchase_orders", "name": "Órdenes de compra", "group": "Compras"},
    {"key": "partial_receipts", "name": "Recepciones parciales", "group": "Compras"},
    {"key": "overdue_orders", "name": "Órdenes vencidas", "group": "Compras"},
    {"key": "damaged_lost", "name": "Material perdido/dañado", "group": "Movimientos"},
    {"key": "consumption_by_period", "name": "Consumo por período", "group": "Movimientos"},
    {"key": "movement_history", "name": "Historial de movimientos del ledger", "group": "Auditoría"},
    {"key": "person_ledger", "name": "Historial de Librería por persona", "group": "Persona", "requires_person": True},
]


def fmt_dt(value) -> str:
    if not value:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def fmt_money(cents: Optional[int]) -> str:
    return f"${(cents or 0) / 100:,.2f}"


async def person_name_for(person_id: Optional[str]) -> str:
    if not person_id:
        return "—"
    try:
        person = await canonical_person(person_id)
        return person_display_name(person)
    except HTTPException:
        return person_id


def apply_common_filters(query: dict, f: dict, date_field: str = "occurred_at") -> None:
    if f.get("book_id"):
        query["book_id"] = f["book_id"]
    if f.get("process_key"):
        query["process_key"] = f["process_key"]
    if f.get("person_id"):
        query["person_id"] = f["person_id"]
    date_query = {}
    if f.get("date_from"):
        date_query["$gte"] = datetime.combine(f["date_from"], datetime.min.time(), tzinfo=timezone.utc)
    if f.get("date_to"):
        date_query["$lte"] = datetime.combine(f["date_to"], datetime.max.time(), tzinfo=timezone.utc)
    if date_query:
        query[date_field] = date_query
    if f.get("payment_type") and "payment_status" not in query:
        if f["payment_type"] == "gratis":
            query["payment_status"] = {"$in": ["no_aplica", "exonerado", "beca"]}
        elif f["payment_type"] == "pagado":
            query["payment_status"] = {"$in": ["pagado", "pago_parcial", "descuento"]}


async def build_inventory_current(f: dict) -> tuple[list[str], list[list]]:
    query: dict = {"is_active": True}
    if f.get("book_id"):
        query["book_id"] = f["book_id"]
    if f.get("process_key"):
        query["process_key"] = f["process_key"]
    books = await db.library_books.find(query, {"_id": 0}).sort("name", 1).to_list(2000)
    holdings = await db.library_holdings.find({"holder_type": "warehouse", "holder_id": "central"}, {"_id": 0}).to_list(5000)
    holding_by_book = {h["book_id"]: h for h in holdings}
    rows = []
    for book in books:
        holding = holding_by_book.get(book["book_id"], {})
        on_hand, reserved = holding.get("quantity_on_hand", 0), holding.get("reserved_qty", 0)
        rows.append([book["name"], book.get("sku") or "—", book.get("process_key") or "—", on_hand, reserved, on_hand - reserved])
    return ["Material", "SKU", "Proceso", "Stock físico", "Reservado", "Disponible"], rows


async def build_inventory_by_process(f: dict) -> tuple[list[str], list[list]]:
    _, rows = await build_inventory_current(f)
    agg: dict[str, dict] = {}
    for _name, _sku, process_key, on_hand, reserved, available in rows:
        entry = agg.setdefault(process_key, {"materiales": 0, "stock": 0, "reservado": 0, "disponible": 0})
        entry["materiales"] += 1
        entry["stock"] += on_hand
        entry["reservado"] += reserved
        entry["disponible"] += available
    out = [[key, v["materiales"], v["stock"], v["reservado"], v["disponible"]] for key, v in agg.items()]
    return ["Proceso", "Materiales", "Stock físico total", "Reservado total", "Disponible total"], out


async def build_inventory_by_responsible(f: dict) -> tuple[list[str], list[list]]:
    query: dict = {"holder_type": {"$in": ["user", "person"]}, "quantity_on_hand": {"$gt": 0}}
    if f.get("book_id"):
        query["book_id"] = f["book_id"]
    holdings = await db.library_holdings.find(query, {"_id": 0}).to_list(5000)
    books = {b["book_id"]: b["name"] for b in await db.library_books.find({}, {"_id": 0, "book_id": 1, "name": 1}).to_list(2000)}
    rows = []
    for holding in holdings:
        if f.get("responsible_user_id") and holding.get("holder_id") != f["responsible_user_id"]:
            continue
        label = await holder_label({"type": holding["holder_type"], "id": holding["holder_id"]})
        tipo = "Líder/Usuario" if holding["holder_type"] == "user" else "Persona"
        rows.append([label, tipo, books.get(holding["book_id"], holding["book_id"]), holding["quantity_on_hand"]])
    return ["Responsable", "Tipo", "Material", "Cantidad en su poder"], rows


async def _delivered_rows(query: dict) -> tuple[list[str], list[list]]:
    movements = await db.library_movements.find(query, {"_id": 0}).sort("occurred_at", -1).to_list(5000)
    rows = []
    for m in movements:
        actor_name = await holder_label({"type": "user", "id": m["actor_user_id"]})
        rows.append([fmt_dt(m["occurred_at"]), m["book_name"], await person_name_for(m.get("person_id")), m.get("process_key") or "—",
                     m["quantity"], PAYMENT_LABELS.get(m.get("payment_status"), m.get("payment_status") or "—"), actor_name])
    return ["Fecha", "Material", "Persona", "Proceso", "Cantidad", "Pago", "Entregado por"], rows


async def build_delivered(f: dict) -> tuple[list[str], list[list]]:
    query: dict = {"movement_type": {"$in": ["DELIVERY", "LOAN"]}}
    apply_common_filters(query, f)
    return await _delivered_rows(query)


async def build_free_materials(f: dict) -> tuple[list[str], list[list]]:
    query: dict = {"movement_type": {"$in": ["DELIVERY", "LOAN"]}, "payment_status": {"$in": ["no_aplica", "exonerado", "beca"]}}
    apply_common_filters(query, f)
    return await _delivered_rows(query)


async def build_sold_materials(f: dict) -> tuple[list[str], list[list]]:
    query: dict = {"movement_type": {"$in": ["DELIVERY", "LOAN"]}, "amount_paid_cents": {"$gt": 0}}
    apply_common_filters(query, f)
    return await _delivered_rows(query)


async def build_reserved(f: dict) -> tuple[list[str], list[list]]:
    query: dict = {"status": "active"}
    if f.get("book_id"):
        query["book_id"] = f["book_id"]
    if f.get("process_key"):
        query["process_key"] = f["process_key"]
    if f.get("person_id"):
        query["person_id"] = f["person_id"]
    reservations = await db.library_reservations.find(query, {"_id": 0}).sort("created_at", -1).to_list(5000)
    rows = []
    for r in reservations:
        rows.append([fmt_dt(r["created_at"]), r["book_name"], r.get("process_key") or "—", await person_name_for(r.get("person_id"))])
    return ["Fecha de reserva", "Material", "Proceso", "Persona"], rows


async def build_library_income(f: dict) -> tuple[list[str], list[list]]:
    query: dict = {"allocations.contribution_type": "libreria_material_educativo", "status": {"$ne": "corrected"}}
    date_query = {}
    if f.get("date_from"):
        date_query["$gte"] = f["date_from"].isoformat()
    if f.get("date_to"):
        date_query["$lte"] = f["date_to"].isoformat()
    if date_query:
        query["received_date"] = date_query
    if f.get("person_id"):
        query["person_id"] = f["person_id"]
    contributions = await db.finance_contributions.find(query, {"_id": 0}).sort("received_date", -1).to_list(5000)
    rows = []
    for c in contributions:
        amount = sum(a["amount_cents"] for a in c.get("allocations", []) if a.get("contribution_type") == "libreria_material_educativo")
        rows.append([c.get("received_date") or "—", await person_name_for(c.get("person_id")), fmt_money(amount), c.get("source") or "—"])
    return ["Fecha", "Persona", "Monto", "Origen"], rows


async def build_pending_payments(f: dict) -> tuple[list[str], list[list]]:
    query: dict = {"payment_status": {"$in": ["pendiente", "pago_parcial"]}}
    apply_common_filters(query, f)
    movements = await db.library_movements.find(query, {"_id": 0}).sort("occurred_at", -1).to_list(2000)
    rows = []
    for m in movements:
        balance = max(0, (m.get("list_price_cents") or 0) - (m.get("amount_paid_cents") or 0))
        if balance <= 0:
            continue
        rows.append([fmt_dt(m["occurred_at"]), m["book_name"], await person_name_for(m.get("person_id")),
                     fmt_money(m.get("list_price_cents") or 0), fmt_money(m.get("amount_paid_cents") or 0), fmt_money(balance),
                     PAYMENT_LABELS.get(m.get("payment_status"), m.get("payment_status") or "—")])
    return ["Fecha", "Material", "Persona", "Precio", "Pagado", "Saldo", "Estado"], rows


async def build_purchase_orders(f: dict) -> tuple[list[str], list[list]]:
    query: dict = {}
    if f.get("status"):
        query["status"] = f["status"]
    date_query = {}
    if f.get("date_from"):
        date_query["$gte"] = datetime.combine(f["date_from"], datetime.min.time(), tzinfo=timezone.utc)
    if f.get("date_to"):
        date_query["$lte"] = datetime.combine(f["date_to"], datetime.max.time(), tzinfo=timezone.utc)
    if date_query:
        query["created_at"] = date_query
    pos = await db.library_purchase_orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(2000)
    rows = [[po["po_number"], po["provider_name"], STATUS_LABELS.get(po["status"], po["status"]), fmt_money(po["total_cents"]),
             fmt_dt(po.get("expected_date")), fmt_dt(po["created_at"])] for po in pos]
    return ["Número", "Proveedor", "Estado", "Total", "Fecha esperada", "Fecha creación"], rows


async def build_partial_receipts(f: dict) -> tuple[list[str], list[list]]:
    pos = await db.library_purchase_orders.find({"status": {"$in": ["partially_received", "received"]}}, {"_id": 0}).to_list(2000)
    rows = []
    for po in pos:
        for line in po["lines"]:
            if line["quantity_received"] > 0 and (not f.get("book_id") or line["book_id"] == f["book_id"]):
                rows.append([po["po_number"], po["provider_name"], line["book_name"], line["quantity_ordered"], line["quantity_received"],
                             line["quantity_ordered"] - line["quantity_received"]])
    return ["Orden", "Proveedor", "Material", "Ordenado", "Recibido", "Pendiente"], rows


async def build_overdue_orders(f: dict) -> tuple[list[str], list[list]]:
    pos = await db.library_purchase_orders.find({"status": {"$in": ["ordered", "partially_received"]}}, {"_id": 0}).to_list(2000)
    rows = []
    for po in pos:
        info = po_overdue_info(po)
        if info["is_overdue"]:
            rows.append([po["po_number"], po["provider_name"], fmt_dt(po.get("expected_date")), info["days_overdue"], info["pending_quantity"]])
    return ["Orden", "Proveedor", "Fecha esperada", "Días de retraso", "Cantidad pendiente"], rows


async def build_damaged_lost(f: dict) -> tuple[list[str], list[list]]:
    query: dict = {"movement_type": {"$in": ["DAMAGE", "LOSS"]}}
    apply_common_filters(query, f)
    movements = await db.library_movements.find(query, {"_id": 0}).sort("occurred_at", -1).to_list(2000)
    rows = [[fmt_dt(m["occurred_at"]), m["book_name"], m["movement_type"], m["quantity"], m.get("notes") or "—"] for m in movements]
    return ["Fecha", "Material", "Tipo", "Cantidad", "Notas"], rows


async def build_consumption_by_period(f: dict) -> tuple[list[str], list[list]]:
    query: dict = {"movement_type": {"$in": ["DELIVERY", "LOAN"]}}
    apply_common_filters(query, f)
    movements = await db.library_movements.find(query, {"_id": 0, "occurred_at": 1, "quantity": 1}).to_list(20000)
    buckets: dict[str, int] = {}
    for m in movements:
        period = m["occurred_at"].strftime("%Y-%m")
        buckets[period] = buckets.get(period, 0) + m["quantity"]
    rows = [[period, qty] for period, qty in sorted(buckets.items())]
    return ["Período", "Unidades entregadas"], rows


async def build_movement_history(f: dict) -> tuple[list[str], list[list]]:
    query: dict = {}
    apply_common_filters(query, f)
    movements = await db.library_movements.find(query, {"_id": 0}).sort("occurred_at", -1).limit(5000).to_list(5000)
    rows = []
    for m in movements:
        actor_name = await holder_label({"type": "user", "id": m["actor_user_id"]})
        rows.append([fmt_dt(m["occurred_at"]), m["movement_type"], m["book_name"], m["quantity"], await holder_label(m.get("from_holder")),
                     await holder_label(m.get("to_holder")), await person_name_for(m.get("person_id")), actor_name, m.get("scan_method") or "MANUAL"])
    return ["Fecha", "Tipo", "Material", "Cantidad", "Origen", "Destino", "Persona", "Usuario", "Método"], rows


async def build_person_ledger(f: dict) -> tuple[list[str], list[list]]:
    person_id = f.get("person_id")
    if not person_id:
        raise HTTPException(status_code=422, detail="Debe indicar la persona para este reporte")
    query: dict = {"person_id": person_id, "movement_type": {"$nin": ["RESERVATION", "RESERVATION_RELEASE"]}}
    if f.get("_restrict_actor_user_id"):
        query["actor_user_id"] = f["_restrict_actor_user_id"]
    apply_common_filters(query, f)
    movements = await db.library_movements.find(query, {"_id": 0}).sort("occurred_at", -1).to_list(1000)
    rows = []
    for m in movements:
        balance = max(0, (m.get("list_price_cents") or 0) - (m.get("amount_paid_cents") or 0))
        actor_name = await holder_label({"type": "user", "id": m["actor_user_id"]})
        rows.append([fmt_dt(m["occurred_at"]), m["book_name"], m.get("process_key") or "—",
                     PAYMENT_LABELS.get(m.get("payment_status"), m.get("payment_status") or "—"), fmt_money(m.get("list_price_cents") or 0),
                     fmt_money(m.get("amount_paid_cents") or 0), fmt_money(balance), m["movement_type"], actor_name])
    return ["Fecha", "Material", "Proceso", "Gratis/Pago", "Precio aplicado", "Pago realizado", "Saldo pendiente", "Estado", "Entregado por"], rows


REPORT_BUILDERS = {
    "inventory_current": build_inventory_current, "inventory_by_process": build_inventory_by_process,
    "inventory_by_responsible": build_inventory_by_responsible, "delivered": build_delivered,
    "reserved": build_reserved, "pending": build_reserved, "free_materials": build_free_materials,
    "sold_materials": build_sold_materials, "library_income": build_library_income,
    "pending_payments": build_pending_payments, "purchase_orders": build_purchase_orders,
    "partial_receipts": build_partial_receipts, "overdue_orders": build_overdue_orders,
    "damaged_lost": build_damaged_lost, "consumption_by_period": build_consumption_by_period,
    "movement_history": build_movement_history, "person_ledger": build_person_ledger,
}


FORMULA_PREFIXES = ("=", "+", "-", "@")


def sanitize_cell(value):
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def export_xlsx(report_name: str, columns: list[str], rows: list[list]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = report_name[:31] or "Reporte"
    sheet.append(columns)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append([sanitize_cell(value) for value in row])
    for index in range(1, len(columns) + 1):
        sheet.column_dimensions[get_column_letter(index)].width = 22
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def export_pdf(report_name: str, filters_summary: str, columns: list[str], rows: list[list]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("VEN Y VE 360 · Librería 360", styles["Title"]),
        Paragraph(report_name, styles["Heading2"]),
        Paragraph(filters_summary or "Sin filtros aplicados", styles["Normal"]),
        Paragraph(f"Generado: {now_utc().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]),
        Spacer(1, 12),
    ]
    table_data = [columns] + [[str(value) for value in row] for row in rows] if rows else [columns, ["Sin resultados para los filtros aplicados"] + [""] * (len(columns) - 1)]
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#132443")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F1EA")]),
    ]))
    elements.append(table)
    doc.build(elements)
    return buffer.getvalue()


def has_reports_access(current_user: dict) -> bool:
    return is_library_manager(current_user) or has_capability(current_user, LIBRARY_REPORTS_READ)


def has_person_ledger_access(current_user: dict) -> bool:
    return has_reports_access(current_user) or has_capability(current_user, LIBRARY_DELIVER)


@router.get("/catalog", response_model=dict)
async def reports_catalog_endpoint(current_user: dict = Depends(get_current_user)):
    if not has_person_ledger_access(current_user):
        raise HTTPException(status_code=403, detail="No tiene acceso a reportes de Librería")
    return {"items": REPORTS_CATALOG}


@router.get("/{report_key}")
async def get_report(
    report_key: str,
    current_user: dict = Depends(get_current_user),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    book_id: Optional[str] = None,
    process_key: Optional[str] = None,
    person_id: Optional[str] = None,
    responsible_user_id: Optional[str] = None,
    status: Optional[str] = None,
    payment_type: Optional[str] = None,
    format: Literal["json", "pdf", "xlsx"] = "json",
):
    builder = REPORT_BUILDERS.get(report_key)
    if not builder:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    filters = {"date_from": date_from, "date_to": date_to, "book_id": book_id, "process_key": process_key,
               "person_id": person_id, "responsible_user_id": responsible_user_id, "status": status, "payment_type": payment_type}
    if report_key == "person_ledger":
        if not has_person_ledger_access(current_user):
            raise HTTPException(status_code=403, detail="No tiene acceso a este reporte")
        if not person_id:
            raise HTTPException(status_code=422, detail="Este reporte requiere seleccionar una persona")
        if not has_reports_access(current_user):
            filters["_restrict_actor_user_id"] = current_user["user_id"]
    elif not has_reports_access(current_user):
        raise HTTPException(status_code=403, detail="No tiene acceso al centro de reportes de Librería")

    columns, rows = await builder(filters)
    report_name = next((r["name"] for r in REPORTS_CATALOG if r["key"] == report_key), report_key)

    if format == "json":
        return {"columns": columns, "rows": rows, "generated_at": now_utc().isoformat(), "report_name": report_name}
    filters_summary = ", ".join(f"{key}: {value}" for key, value in filters.items() if value)
    if format == "xlsx":
        content = export_xlsx(report_name, columns, rows)
        return Response(content=content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         headers={"Content-Disposition": f'attachment; filename="{report_key}.xlsx"'})
    content = export_pdf(report_name, filters_summary, columns, rows)
    return Response(content=content, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{report_key}.pdf"'})
