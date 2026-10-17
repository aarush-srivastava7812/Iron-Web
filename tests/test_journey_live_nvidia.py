"""Opt-in NVIDIA chat → confirmed memory → specialists → private PDF."""
import json
import os
from pathlib import Path

import pytest
from tests.test_application_integration import connected_app, user, trip  # noqa: F401


@pytest.mark.skipif(os.getenv("VOYARA_JOURNEY_LIVE")!="1",reason="Opt-in hosted NVIDIA journey check")
def test_live_conversation_to_personal_travel_book(connected_app,monkeypatch):  # noqa: F811
    from agents.config import settings
    monkeypatch.setattr(settings,"agent_mode","nvidia")
    client,_=connected_app;headers=user(client,"journey_live");path=trip(client,headers)
    first=client.post(path+"/chat",headers=headers,json={"content":"I would like a relaxed 5-day holiday in Kerala. Help me build it.","page":"plan"})
    assert first.status_code==200,first.text
    partial=first.json()
    report=Path("report/travel_chat_catalog_20261017");report.mkdir(parents=True,exist_ok=True)
    (report/"first_chat_turn.json").write_text(json.dumps(partial,indent=2),encoding="utf-8")
    assert partial["status"]=="ok",partial
    assert partial["workspace"]["draft"].get("destination")=="Kerala",partial
    assert "start_date" in partial["workspace"]["missing_fields"]
    second=client.post(path+"/chat",headers=headers,json={"content":"We are 2 adults, departing New Delhi on 12 December 2026 for exactly 5 days. Our total budget for both people is INR 100000. We are vegetarian and enjoy nature and culture.","page":"plan"})
    assert second.status_code==200,second.text
    ready=second.json();assert ready["status"]=="ok",ready
    work=ready["workspace"]
    assert not work["missing_fields"],work
    assert work["draft"]["start_date"]=="2026-12-12" and work["draft"]["end_date"]=="2026-12-16"
    assert work["draft"]["budget"]==100000 and work["draft"]["traveller_count"]==2
    flight=work["options"]["flights"][0]
    work=client.post(path+"/selections",headers=headers,json={"expected_revision":work["revision"],"kind":"flight","item_id":flight["id"]}).json()
    confirmed=client.post(path+"/confirm",headers=headers,json={"expected_revision":work["revision"],"mode":"ai","remember_preferences":True})
    assert confirmed.status_code==200,confirmed.text
    complete=confirmed.json()
    report=Path("report/travel_chat_catalog_20261017");report.mkdir(parents=True,exist_ok=True)
    evidence=dict(scope="Live NVIDIA chatbot and specialist decisions; synthetic catalog; offline embedding fixture with actual temporary memory stores",
                  turns=[{k:v for k,v in turn.items() if k in {"status","reply","cards","workspace"}} for turn in [partial,ready]],
                  orchestration=complete["orchestration"],workspace=complete["workspace"])
    evidence["orchestration"].pop("memory",None)
    (report/"live_journey.json").write_text(json.dumps(evidence,indent=2),encoding="utf-8")
    assert complete["orchestration"]["status"]=="ok",complete["reply"]
    assert all(r["execution"]["completed"] and r["execution"]["mode"]=="nvidia" for r in complete["orchestration"]["agent_results"])
    preview=client.get(path+"/travel-book",headers=headers)
    assert preview.status_code==200,preview.text
    (report/"travel_book_snapshot.json").write_text(json.dumps(preview.json(),indent=2),encoding="utf-8")
    exported=client.post(path+"/travel-books",headers=headers)
    assert exported.status_code==201,exported.text
    pdf=client.get(exported.json()["download_url"],headers=headers)
    assert pdf.status_code==200 and pdf.content.startswith(b"%PDF-")
    (report/"Kerala_Travel_Book.pdf").write_bytes(pdf.content)
