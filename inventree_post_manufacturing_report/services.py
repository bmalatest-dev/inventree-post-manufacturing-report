"""Report discovery and snapshot helpers.

V0.1.0 intentionally uses Build.metadata for persistence. This avoids adding plugin
database migrations while the workflow is being validated. Finalized revisions are
stored as immutable snapshots under metadata['post_manufacturing_report'].
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal

REPORT_TYPES = ("pcba", "mechanical", "final_product")

def iso(v):
    return v.isoformat() if hasattr(v, "isoformat") and v else (str(v) if v else "")

def money(v):
    if v is None:
        return None
    try:
        return float(getattr(v, "amount", v))
    except (TypeError, ValueError):
        return None

def base_build_data(build):
    part = getattr(build, "part", None)
    return {
        "build_id": build.pk,
        "reference": getattr(build, "reference", ""),
        "title": getattr(build, "title", ""),
        "part_id": getattr(part, "pk", None),
        "part_ipn": getattr(part, "IPN", "") or getattr(part, "name", ""),
        "part_name": getattr(part, "name", ""),
        "target_qty": getattr(build, "quantity", 0),
        "completed_qty": getattr(build, "completed", 0),
        "start_date": iso(getattr(build, "start_date", None)),
        "target_date": iso(getattr(build, "target_date", None)),
        "completion_date": iso(getattr(build, "completion_date", None)),
        "status": str(getattr(build, "status", "")),
    }

def bom_lines(part):
    """Best-effort BOM extraction against InvenTree 1.5.x."""
    rows = []
    manager = getattr(part, "bom_items", None)
    if manager is None:
        manager = getattr(part, "bom_items", None)
    try:
        items = manager.all() if manager is not None else []
    except Exception:
        items = []
    for line in items:
        sub = getattr(line, "sub_part", None) or getattr(line, "part", None)
        rows.append({
            "line_id": getattr(line, "pk", None),
            "part_id": getattr(sub, "pk", None),
            "ipn": getattr(sub, "IPN", "") or getattr(sub, "name", ""),
            "name": getattr(sub, "name", ""),
            "quantity": float(getattr(line, "quantity", 0) or 0),
            "assembly": bool(getattr(sub, "assembly", False)),
            "purchaseable": bool(getattr(sub, "purchaseable", False)),
        })
    return rows

def child_builds(build):
    rows = []
    try:
        from build.models import Build
        qs = Build.objects.filter(parent=build).select_related("part")
    except Exception:
        qs = []
    for child in qs:
        d = base_build_data(child)
        meta = getattr(child, "metadata", {}) or {}
        pmr = meta.get("post_manufacturing_report", {})
        finals = pmr.get("finalized", [])
        d["report_state"] = "Finalized" if finals else ("Draft" if pmr.get("draft") else "Missing")
        d["report_revision"] = len(finals) if finals else None
        rows.append(d)
    return rows

def candidate_purchase_orders(part_ids):
    """Find PO lines for BOM parts.

    This is intentionally a candidate list. The operator decides which POs belong to
    this manufacturing run, preventing old runs from being silently included.
    """
    if not part_ids:
        return []
    rows = []
    try:
        from order.models import PurchaseOrderLineItem
        qs = (PurchaseOrderLineItem.objects
              .filter(part__part_id__in=part_ids)
              .select_related("order", "order__supplier", "part", "part__part"))
    except Exception:
        return rows

    for line in qs:
        po = getattr(line, "order", None)
        supplier_part = getattr(line, "part", None)
        base = getattr(supplier_part, "part", None)
        rows.append({
            "line_id": line.pk,
            "po_id": getattr(po, "pk", None),
            "po_reference": getattr(po, "reference", ""),
            "supplier": str(getattr(po, "supplier", "") or ""),
            "part_id": getattr(base, "pk", None),
            "ipn": getattr(base, "IPN", "") or getattr(base, "name", ""),
            "description": getattr(line, "notes", "") or getattr(base, "description", "") or getattr(base, "name", ""),
            "quantity": float(getattr(line, "quantity", 0) or 0),
            "received": float(getattr(line, "received", 0) or 0),
            "purchase_price": money(getattr(line, "purchase_price", None)),
            "currency": str(getattr(getattr(line, "purchase_price", None), "currency", "") or ""),
            "po_start": iso(getattr(po, "start_date", None)),
            "po_target": iso(getattr(po, "target_date", None)),
            "status": str(getattr(po, "status", "")),
        })
    return rows

def discover(build, report_type):
    base = base_build_data(build)
    bom = bom_lines(build.part)
    ids = [r["part_id"] for r in bom if r["part_id"]]
    data = {
        "report_type": report_type,
        "build": base,
        "bom": bom,
        "candidate_pos": candidate_purchase_orders(ids),
        "children": child_builds(build),
        "warnings": [],
    }
    if report_type == "pcba":
        bare = [r for r in bom if str(r["ipn"]).upper().endswith("-BARE")]
        assembly = [r for r in bom if "ASSEMBLY" in str(r["ipn"]).upper() or "ASSEMBLY" in str(r["name"]).upper()]
        data["bare_parts"] = bare
        data["assembly_parts"] = assembly
        if not bare:
            data["warnings"].append("No <>-BARE BOM line was automatically identified.")
        if not assembly:
            data["warnings"].append("No <> Assembly BOM line was automatically identified.")
    if report_type == "final_product":
        missing = [c for c in data["children"] if c["report_state"] != "Finalized"]
        if missing:
            data["warnings"].append(f"{len(missing)} child Build Order report(s) are not finalized.")
    return data

def report_store(build):
    metadata = dict(getattr(build, "metadata", {}) or {})
    return metadata, dict(metadata.get("post_manufacturing_report", {}) or {})

def save_draft(build, payload):
    metadata, store = report_store(build)
    store["draft"] = payload
    metadata["post_manufacturing_report"] = store
    build.metadata = metadata
    build.save(update_fields=["metadata"])
    return payload

def finalize(build, payload):
    metadata, store = report_store(build)
    finals = list(store.get("finalized", []) or [])
    snapshot = dict(payload)
    snapshot["revision"] = len(finals) + 1
    snapshot["finalized_on"] = date.today().isoformat()
    finals.append(snapshot)
    store["finalized"] = finals
    store["draft"] = None
    metadata["post_manufacturing_report"] = store
    build.metadata = metadata
    build.save(update_fields=["metadata"])
    return snapshot

def latest(build):
    _, store = report_store(build)
    finals = store.get("finalized", []) or []
    return finals[-1] if finals else store.get("draft")
