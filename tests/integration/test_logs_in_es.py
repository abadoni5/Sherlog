"""Needs `docker compose up -d` and a few seconds of traffic.
Run with: ELASTICSEARCH_URL=http://localhost:9200 uv run pytest -m integration"""
import os

import httpx
import pytest

ES = os.environ.get("ELASTICSEARCH_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not ES, reason="ELASTICSEARCH_URL not set"),
]


def _search(body: dict) -> dict:
    resp = httpx.post(f"{ES}/sherlog-logs-*/_search", json=body, timeout=10)
    resp.raise_for_status()
    return resp.json()


def test_logs_from_all_three_services_are_indexed():
    result = _search({"size": 0, "aggs": {"svc": {"terms": {"field": "service"}}}})
    services = {b["key"] for b in result["aggregations"]["svc"]["buckets"]}
    assert {"checkout", "inventory", "payments"} <= services


def test_fields_are_mapped_for_aggregation():
    # Only works if the index template was applied (keyword/float mappings).
    result = _search({"size": 0, "aggs": {
        "p95": {"percentiles": {"field": "duration_ms", "percents": [95]}},
        "levels": {"terms": {"field": "level"}},
    }})
    assert result["aggregations"]["p95"]["values"]["95.0"] is not None
    assert result["aggregations"]["levels"]["buckets"]
