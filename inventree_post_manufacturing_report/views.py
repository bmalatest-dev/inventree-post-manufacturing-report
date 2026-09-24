from __future__ import annotations
import io, json
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

from build.models import Build
from .services import REPORT_TYPES, discover, save_draft, finalize, latest

def get_build(pk):
    try:
        return Build.objects.select_related("part").get(pk=pk)
    except Build.DoesNotExist:
        raise Http404("Build Order not found")

def form_payload(request, build, report_type, discovered):
    selected = request.POST.getlist("selected_po")
    roles = {}
    for value in selected:
        roles[value] = request.POST.get(f"po_role_{value}", "Other")
    manual = {
        "responsible_individual": request.POST.get("responsible_individual", ""),
        "manufacturing_trigger": request.POST.get("manufacturing_trigger", ""),
        "preliminary_package_location": request.POST.get("preliminary_package_location", ""),
        "final_package_location": request.POST.get("final_package_location", ""),
        "pv_to_fab_package_location": request.POST.get("pv_to_fab_package_location", ""),
        "pv_to_assembly_package_location": request.POST.get("pv_to_assembly_package_location", ""),
        "fab_to_pv_package_location": request.POST.get("fab_to_pv_package_location", ""),
        "packing_list_locations": request.POST.get("packing_list_locations", ""),
        "significant_events": request.POST.get("significant_events", ""),
        "notes": request.POST.get("notes", ""),
    }
    selected_pos = []
    for po in discovered["candidate_pos"]:
        key = str(po["line_id"])
        if key in selected:
            row = dict(po)
            row["role"] = roles.get(key, "Other")
            selected_pos.append(row)
    return {
        "schema": 1,
        "report_type": report_type,
        "build": discovered["build"],
        "bom": discovered["bom"],
        "children": discovered["children"],
        "selected_pos": selected_pos,
        "manual": manual,
        "warnings": discovered["warnings"],
        # Integration slots deliberately retained in the snapshot schema.
        "test_results": [],
        "rework": [],
        "asr": None,
        "costs": {"CAD": {}, "USD": {}},
    }

@login_required
@require_http_methods(["GET", "POST"])
def report_view(request, pk):
    build = get_build(pk)
    report_type = request.GET.get("type") or request.POST.get("report_type") or ""
    if report_type not in REPORT_TYPES:
        return render(request, "post_manufacturing_report/select_type.html", {"build": build})

    discovered = discover(build, report_type)
    current = latest(build) or {}

    if request.method == "POST":
        payload = form_payload(request, build, report_type, discovered)
        action = request.POST.get("action")
        if action == "save":
            save_draft(build, payload)
            return redirect(f"{reverse('plugin:post-manufacturing-report:report', args=[pk])}?type={report_type}")
        if action == "finalize":
            if report_type == "final_product" and any(c["report_state"] != "Finalized" for c in discovered["children"]):
                discovered["warnings"].append("Cannot finalize: all required child BO reports must be finalized.")
            else:
                snap = finalize(build, payload)
                return redirect(reverse("plugin:post-manufacturing-report:pdf", args=[pk, snap["revision"]]))

    selected_ids = {str(x.get("line_id")) for x in current.get("selected_pos", [])}
    return render(request, "post_manufacturing_report/report.html", {
        "build": build, "report_type": report_type, "data": discovered,
        "current": current, "selected_ids": selected_ids,
    })

@login_required
def pdf_view(request, pk, revision=0):
    build = get_build(pk)
    metadata = getattr(build, "metadata", {}) or {}
    finals = (metadata.get("post_manufacturing_report", {}) or {}).get("finalized", []) or []
    if revision:
        if revision < 1 or revision > len(finals):
            raise Http404("Report revision not found")
        data = finals[revision - 1]
    else:
        data = latest(build)
    if not data:
        raise Http404("No report data")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Post-Manufacturing Report", styles["Title"]),
        Paragraph(f"BO {data['build'].get('reference','')} — {data['build'].get('part_ipn','')}", styles["Heading2"]),
        Paragraph(f"Type: {data.get('report_type','')} | Revision: {data.get('revision','DRAFT')}", styles["Normal"]),
        Spacer(1, 12),
    ]
    b = data["build"]
    summary = [
        ["Target Qty", str(b.get("target_qty","")), "Completed Qty", str(b.get("completed_qty",""))],
        ["Start", b.get("start_date",""), "Target", b.get("target_date","")],
        ["Completion", b.get("completion_date",""), "Status", b.get("status","")],
    ]
    t = Table(summary, colWidths=[90,130,90,130])
    t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.25,colors.grey),("BACKGROUND",(0,0),(0,-1),colors.whitesmoke),("BACKGROUND",(2,0),(2,-1),colors.whitesmoke)]))
    story += [t, Spacer(1, 14), Paragraph("Selected Purchase Orders", styles["Heading2"])]
    po_rows = [["PO","Supplier","Part","Qty","Role","Start","Target"]]
    for p in data.get("selected_pos", []):
        po_rows.append([p.get("po_reference",""), p.get("supplier",""), p.get("ipn",""),
                        str(p.get("quantity","")), p.get("role",""), p.get("po_start",""), p.get("po_target","")])
    if len(po_rows) == 1:
        po_rows.append(["—","—","—","—","—","—","—"])
    pt = Table(po_rows, repeatRows=1, colWidths=[55,80,65,35,60,65,65])
    pt.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.25,colors.grey), ("BACKGROUND",(0,0),(-1,0),colors.lightgrey), ("FONTSIZE",(0,0),(-1,-1),7)]))
    story += [pt, Spacer(1,14), Paragraph("Manual Manufacturing Record", styles["Heading2"])]
    for k,v in (data.get("manual") or {}).items():
        story.append(Paragraph(f"<b>{k.replace('_',' ').title()}:</b> {str(v)}", styles["BodyText"]))
    if data.get("warnings"):
        story += [Spacer(1,12), Paragraph("Warnings / Review Items", styles["Heading2"])]
        for w in data["warnings"]:
            story.append(Paragraph(f"• {w}", styles["BodyText"]))
    story += [Spacer(1,12), Paragraph("V0.1.0 integration status", styles["Heading2"]),
              Paragraph("Test history, stock-item rework history, ASR results, PO receipt timing, acceptance yield, and CAD/USD cost roll-up are reserved in the report schema but require validation against the production data model before automatic population.", styles["BodyText"])]
    doc.build(story)
    pdf = buf.getvalue()
    resp = HttpResponse(pdf, content_type="application/pdf")
    rev = data.get("revision","draft")
    resp["Content-Disposition"] = f'attachment; filename="post-manufacturing-{build.reference}-r{rev}.pdf"'
    return resp
