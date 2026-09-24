from django.urls import path
from plugin import InvenTreePlugin
from plugin.mixins import SettingsMixin, UserInterfaceMixin, UrlsMixin, ReportMixin
from . import PLUGIN_VERSION
from . import views

class PostManufacturingReportPlugin(
    SettingsMixin, UserInterfaceMixin, UrlsMixin, ReportMixin, InvenTreePlugin
):
    NAME = "PostManufacturingReport"
    SLUG = "post-manufacturing-report"
    TITLE = "Post-Manufacturing Report"
    DESCRIPTION = "BO-based PCBA, mechanical and final-product manufacturing reports"
    VERSION = PLUGIN_VERSION
    AUTHOR = "Per Vices Corporation"
    LICENSE = "MIT"

    SETTINGS = {
        "ENABLE_BO_PANEL": {
            "name": "Show Build Order panel",
            "description": "Show the Post-Manufacturing Report panel on Build Orders",
            "default": True,
            "validator": bool,
        }
    }

    def setup_urls(self):
        return [
            path("build/<int:pk>/", views.report_view, name="report"),
            path("build/<int:pk>/pdf/", views.pdf_view, name="pdf-latest"),
            path("build/<int:pk>/pdf/<int:revision>/", views.pdf_view, name="pdf"),
        ]

    def get_ui_panels(self, request, context, **kwargs):
        if not self.get_setting("ENABLE_BO_PANEL"):
            return []
        context = context or {}
        if context.get("target_model") != "build":
            return []
        target_id = context.get("target_id")
        if target_id is None:
            return []
        return [{
            "key": "post-manufacturing-report",
            "title": "Post-Manufacturing Report",
            "description": "Create, review and finalize the manufacturing report for this Build Order",
            "source": self.plugin_static_file("panel.js"),
            "icon": "ti:file-report:outline",
            "context": {
                "build_id": target_id,
                "report_url": f"/plugin/{self.slug}/build/{target_id}/",
                "version": self.VERSION,
            },
        }]

    def add_report_context(self, report_instance, model_instance, user, context):
        """Expose stored PMR data to standard InvenTree report templates too."""
        metadata = getattr(model_instance, "metadata", {}) or {}
        context["post_manufacturing_report"] = metadata.get("post_manufacturing_report")
