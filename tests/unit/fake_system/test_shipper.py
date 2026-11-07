import json
import logging

import httpx

from fake_system.common.logs import JsonFormatter
from fake_system.common.shipper import ElasticsearchHandler, index_for


def _handler(transport, **kw):
    client = httpx.Client(base_url="http://es", transport=transport)
    h = ElasticsearchHandler(client=client, start_thread=False, **kw)
    h.setFormatter(JsonFormatter("payments", "v1", "abc"))
    return h


def _log(handler, n=1, **extra):
    lg = logging.getLogger("test.shipper")
    lg.handlers.clear(); lg.addHandler(handler)
    lg.setLevel(logging.INFO); lg.propagate = False
    for i in range(n):
        lg.info(f"m{i}", extra={"event": "e", **extra})


def test_index_name_comes_from_event_timestamp():
    line = json.dumps({"@timestamp": "2026-11-07T10:00:00Z"})
    assert index_for(line) == "sherlog-logs-2026.11.07"


def test_drain_sends_bulk_ndjson_in_batches():
    requests = []
    def handler(req):
        requests.append(req)
        return httpx.Response(200, json={"errors": False})
    h = _handler(httpx.MockTransport(handler), batch_size=2)
    _log(h, n=5)
    assert h.drain_and_send() == 5
    assert len(requests) == 3  # 2 + 2 + 1
    assert requests[0].url.path == "/_bulk"
    assert requests[0].headers["content-type"] == "application/x-ndjson"
    lines = requests[0].content.decode().splitlines()
    assert len(lines) == 4 and lines[0].startswith('{"index": {"_index": "sherlog-logs-')
    assert json.loads(lines[1])["service"] == "payments"
    assert requests[0].content.endswith(b"\n")  # _bulk requires a trailing newline


def test_elasticsearch_down_drops_lines_without_raising():
    def handler(req):
        raise httpx.ConnectError("refused")
    h = _handler(httpx.MockTransport(handler))
    _log(h, n=3)
    h.drain_and_send()  # must not raise
    assert h.dropped == 3


def test_http_error_status_counts_as_dropped():
    h = _handler(httpx.MockTransport(lambda r: httpx.Response(500)))
    _log(h, n=2)
    h.drain_and_send()
    assert h.dropped == 2


def test_full_queue_drops_instead_of_blocking():
    h = _handler(httpx.MockTransport(lambda r: httpx.Response(200)), max_queue=2)
    _log(h, n=5)
    assert h.dropped == 3


def test_rejected_documents_in_a_200_bulk_response_are_counted():
    # Elasticsearch answers 200 with errors=true when single docs are rejected.
    body = {"errors": True, "items": [
        {"index": {"status": 400, "error": {"type": "illegal_argument_exception"}}},
        {"index": {"status": 201}},
    ]}
    h = _handler(httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    _log(h, n=2)
    h.drain_and_send()
    assert h.dropped == 1
