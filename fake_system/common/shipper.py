"""Ship log lines to Elasticsearch without ever hurting the service.

`emit()` only puts the line on an in-memory queue. A background thread sends
batches to the `_bulk` API. If Elasticsearch is down or the queue is full, lines
are dropped: losing a log line is better than slowing or crashing a request.
"""

import json
import logging
import queue
import sys
import threading

import httpx

# Not "logs-*-*": Elasticsearch has a built-in template for that pattern which
# makes data streams, and those reject the plain `index` bulk action.
INDEX_PREFIX = "sherlog-logs-"


def index_for(line: str) -> str:
    """Daily index name from the event's own @timestamp (UTC date)."""
    day = json.loads(line)["@timestamp"][:10]
    return INDEX_PREFIX + day.replace("-", ".")


class ElasticsearchHandler(logging.Handler):
    def __init__(self, url: str | None = None, client: httpx.Client | None = None,
                 batch_size: int = 50, flush_interval: float = 1.0,
                 max_queue: int = 10_000, start_thread: bool = True) -> None:
        super().__init__()
        self._client = client or httpx.Client(base_url=url, timeout=5.0)
        self._queue: queue.Queue[str] = queue.Queue(maxsize=max_queue)
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.dropped = 0
        if start_thread:
            self._thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._queue.put_nowait(self.format(record))
        except queue.Full:
            self.dropped += 1
        except Exception:
            self.handleError(record)

    def drain_and_send(self) -> int:
        """Send everything currently queued, in batches. Returns lines sent."""
        sent = 0
        while True:
            batch: list[str] = []
            while len(batch) < self._batch_size:
                try:
                    batch.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            if not batch:
                return sent
            self._send(batch)
            sent += len(batch)

    def _send(self, lines: list[str]) -> None:
        body = "".join(
            json.dumps({"index": {"_index": index_for(line)}}) + "\n" + line + "\n"
            for line in lines
        )
        try:
            resp = self._client.post(
                "/_bulk", content=body,
                headers={"content-type": "application/x-ndjson"},
            )
            resp.raise_for_status()
            # _bulk answers 200 even when individual documents are rejected.
            result = resp.json()
            if result.get("errors"):
                failed = [i["index"] for i in result["items"] if i["index"].get("error")]
                self.dropped += len(failed)
                print(f"log shipper: {len(failed)} docs rejected, first: "
                      f"{failed[0]['error']}", file=sys.stderr)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            self.dropped += len(lines)
            print(f"log shipper: dropped {len(lines)} lines: {exc!r}", file=sys.stderr)

    def _run(self) -> None:
        while not self._stop.wait(self._flush_interval):
            self.drain_and_send()

    def close(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5)
        self.drain_and_send()
        self._client.close()
        super().close()
