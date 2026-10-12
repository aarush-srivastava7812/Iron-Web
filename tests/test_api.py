import json
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import pytest
import server
from memory.engine import MemoryEngine
from memory.tool_adapter import MemoryToolAdapter


@pytest.fixture
def api(tmp_path, monkeypatch):
    engine = MemoryEngine(config={}, qdrant_path=str(tmp_path/"vectors"), kuzu_path=str(tmp_path/"graph.db"))
    monkeypatch.setattr(server, "get_engine", lambda: engine)
    http = server.ThreadingHTTPServer(("127.0.0.1", 0), server.IronWebHandler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{http.server_port}", engine
    http.shutdown()
    http.server_close()
    thread.join(timeout=5)
    engine.close()


def post(url, path, payload, headers=None):
    data = payload.encode() if isinstance(payload, str) else json.dumps(payload).encode()
    request = Request(url+path, data=data, headers=headers or {"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.load(response)
    except HTTPError as response:
        return response.code, json.load(response)


def test_actual_api_save_and_search_preserve_literal_text(api):
    url, _ = api
    content = '<script>window.unexpected = true</script> & memory'
    status, saved = post(url, "/api/add", {"content": content, "entity_ids": ["topic"]})
    assert status == 201 and saved["success"]
    status, result = post(url, "/api/search", {"query": "memory", "retrieval_mode": "vector"})
    assert status == 200 and result["results"][0]["content"] == content


def test_bad_requests_return_errors_without_writes(api):
    url, engine = api
    for path, body in [("/api/add", "broken JSON"), ("/api/add", []),
                       ("/api/add", {"content": "fact", "metadata": {"text": "override"}}),
                       ("/api/add", {"content": "fact", "entity_ids": "bad"}),
                       ("/api/search", {"query": "fact", "k": -1}),
                       ("/api/search", {"query": "fact", "retrieval_mode": "imaginary"})]:
        status, result = post(url, path, body)
        assert status == 400 and result["error"]
    assert engine.vector_store.count() == 0


def test_cross_origin_writes_are_rejected(api):
    url, _ = api
    status, _ = post(url, "/api/add", {"content": "fact"}, {"Content-Type": "application/json", "Origin": "https://unrelated.example"})
    assert status == 403


def test_empty_report_directory_has_no_fabricated_values(tmp_path):
    result = server.load_verified_reports(tmp_path)
    assert result["status"] == "no_verified_results" and result["reports"] == []
    (tmp_path/"old_summary.json").write_text('{"recall": 1.0}', encoding="utf-8")
    assert server.load_verified_reports(tmp_path)["reports"] == []


def test_tool_adapter_maintenance_uses_supported_arguments(api):
    _, engine = api
    adapter = MemoryToolAdapter(engine)
    assert adapter.call_tool("run_maintenance", {"tasks": [], "dry_run": True}) == {"success": True, "result": {}}
    assert adapter.call_tool("run_maintenance", {"tasks": ["unknown"]})["success"] is False
    assert adapter.call_tool("search_memory", {"query": "fact", "k": -1})["success"] is False
