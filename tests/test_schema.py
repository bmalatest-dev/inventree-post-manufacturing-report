from types import SimpleNamespace
from inventree_post_manufacturing_report.services import base_build_data

def test_build_snapshot():
    part = SimpleNamespace(pk=9, IPN="TR8R", name="TR8 Rx")
    build = SimpleNamespace(pk=2, reference="BO-2", title="", part=part, quantity=10,
                            completed=8, start_date=None, target_date=None,
                            completion_date=None, status=20)
    x = base_build_data(build)
    assert x["part_ipn"] == "TR8R"
    assert x["target_qty"] == 10
    assert x["completed_qty"] == 8
