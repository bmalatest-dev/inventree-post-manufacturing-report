# InvenTree Post-Manufacturing Report — v0.1.0

First testable implementation of the Per Vices BO-based post-manufacturing report workflow.

## V1 workflow

Open a Build Order → **Post-Manufacturing Report** → choose:

- PCBA / Assembled Board
- Mechanical / Subassembly
- Final Product / SDR

The plugin then discovers the BO summary, BOM, child BOs and candidate PO lines. The operator
selects the POs which actually belong to the manufacturing run and assigns each selected line
a role: **Original / Replacement / Supplemental / Other**.

This operator-confirmed PO step is intentional. It preserves poor supplier performance from an
original PO even where the final stock consumed came from a later replacement PO, without
silently pulling old POs from unrelated manufacturing runs.

## Implemented in 0.1.0

- BO-only UI panel
- explicit report-type selection
- BO summary
- BOM discovery
- child BO report-state discovery
- candidate PO-line discovery from BOM parts
- manual PO selection and role
- manual manufacturing record fields
- draft persistence in `Build.metadata`
- immutable finalized revision snapshots in `Build.metadata`
- final-product finalization blocked while child BO reports are not finalized
- PDF generation from a finalized revision
- ReportMixin context exposure for future native InvenTree report templates
- schema slots for tests, rework, ASR and CAD/USD costs

## Intentionally deferred until test data confirms the exact production records

The following are part of the agreed design, but are **not yet auto-populated** in 0.1.0:

- all part-level PCBA test results and VI / BU / SW / other yield calculations
- overall First Pass Yield and Final Yield
- stock-item rework history
- Assembly Stock Reconciliation result ingestion
- PO receipt history (First Receipt / Final Receipt)
- accepted / rejected quantities
- supplier lead time and schedule variance
- mechanical acceptance/status history
- automatic NRE-line classification
- CAD and USD cost roll-up
- stock-receipt lineage used to pre-check candidate POs
- automatic PDF attachment back to the BO

The generated PDF clearly marks these integration items so the first test cannot be mistaken for
a complete manufacturing record.

## Why Build.metadata for V0.1.0?

This avoids introducing AppMixin database migrations before the workflow is validated. InvenTree
Build Orders expose a JSON metadata field. Once the report workflow is stable, the data can be
moved to dedicated plugin models if desired.

## Install

Recommended repository name:

`inventree-post-manufacturing-report`

Upload the ZIP contents to the repository root and install from:

`git+https://github.com/bmalatest-dev/inventree-post-manufacturing-report`

Enable the plugin and ensure **ENABLE_PLUGINS_INTERFACE** is enabled in InvenTree.

## First tests

1. Start with a known PCBA BO.
2. Open the Post-Manufacturing Report panel.
3. Select **PCBA**.
4. Confirm BOM discovery.
5. Confirm the expected `<>-BARE` / assembly-related BOM content is visible.
6. Review candidate PO lines and select both an original and replacement PO if applicable.
7. Save Draft.
8. Reopen the report and verify the BO metadata contains `post_manufacturing_report`.
9. Finalize and confirm the PDF downloads.
10. Repeat with a mechanical BO such as TR8-MECH.
11. Repeat with a final SDR BO and confirm child report states are shown.

### Important
Test this in the local/test InvenTree instance first. V0.1.0 writes only to the selected Build
Order's `metadata` field; it does not modify allocations, stock quantities, POs, tests or ASR data.
