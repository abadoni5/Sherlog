import json
from pathlib import Path

from fake_system.common.logs import LogEvent

TEMPLATE = Path(__file__).resolve().parents[3] / "fake_system/elasticsearch/logs-template.json"


def test_template_maps_every_log_event_field():
    props = json.loads(TEMPLATE.read_text())["template"]["mappings"]["properties"]
    fields = {f.alias or name for name, f in LogEvent.model_fields.items()}
    assert fields <= set(props), f"unmapped fields: {fields - set(props)}"


def test_template_types_support_aggregations():
    props = json.loads(TEMPLATE.read_text())["template"]["mappings"]["properties"]
    for name in ("service", "level", "event", "route", "request_id"):
        assert props[name]["type"] == "keyword"
    assert props["duration_ms"]["type"] == "float"
    assert props["@timestamp"]["type"] == "date"
