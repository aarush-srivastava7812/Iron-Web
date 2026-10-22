import hashlib
import pytest

from tests.test_application_integration import connected_app, user, trip  # noqa: F401


@pytest.fixture(autouse=True)
def model_chat_mode(monkeypatch):
    """These model-contract cases must not depend on the developer's .env mode."""
    from agents.config import settings
    monkeypatch.setattr(settings, "agent_mode", "nvidia")


class ChatModel:
    def __init__(self,*answers):
        self.answers=iter(answers)
        self.requests=[]
    def chat_json(self,messages,**kwargs):
        self.requests.append((messages,kwargs))
        if messages[0]["content"].startswith("You extract"):
            self.current=next(self.answers)
            return self.current
        return self.current


def chat(client,headers,path,message):
    response=client.post(path+"/chat",headers=headers,json={"content":message,"page":"plan"})
    assert response.status_code==200,response.text
    return response.json()


def draft(client,headers,path):
    current=client.get(path+"/workspace",headers=headers).json()
    body=dict(destination="Kerala",start_date="2026-12-12",end_date="2026-12-16",traveller_count=2,
              budget=100000,pace="relaxed",dietary="vegetarian",interests=["nature","culture"],origin="New Delhi")
    response=client.put(path+"/workspace",headers=headers,json={"expected_revision":current["revision"],"draft":body})
    assert response.status_code==200,response.text
    return response.json()


def confirm(client,headers,path,current):
    response=client.post(path+"/confirm",headers=headers,json={"expected_revision":current["revision"],"mode":"manual","remember_preferences":True})
    assert response.status_code==200,response.text
    assert response.json()["orchestration"]["status"]=="ok",response.json()
    return response.json()


def test_chat_guides_partial_trip_without_promoting_unreviewed_model_facts(connected_app,monkeypatch):  # noqa: F811
    from app import journey
    model=ChatModel(dict(reply="Kerala sounds lovely. What exact date will you leave?",updates={"destination":"Kerala","duration_days":5},cards=[]),
                    dict(reply="Please review your trip details, then confirm to run the team.",updates={"start_date":"2026-12-12","traveller_count":2,"budget":80000,"origin":"New Delhi","pace":"relaxed","dietary":"vegetarian"},cards=[]))
    monkeypatch.setattr(journey,"get_nim_client",lambda:model)
    client,_=connected_app
    headers=user(client,"chat_builder");path=trip(client,headers)
    first=chat(client,headers,path,"I want a 5-day trip to Kerala")
    assert first["workspace"]["draft"]["destination"]=="Kerala"
    assert "start_date" in first["workspace"]["missing_fields"]
    assert not first["workspace"]["confirmed"]
    second=chat(client,headers,path,"Start 12 December 2026. Two people, INR 80000 total, from New Delhi, relaxed and vegetarian.")
    assert second["workspace"]["draft"]["end_date"]=="2026-12-16"
    assert not second["workspace"]["missing_fields"]
    packet=client.get(path+"/requirements",headers=headers).json()
    assert not any(f["status"]=="supported" and f["predicate"]=="destination" for f in packet["fields"])
    assert all(request[1]["temperature"]>0 for request in model.requests)
    assert "I want a 5-day trip" in str(model.requests[2][0])
    assert len(client.get(path,headers=headers).json()["messages"])==4


def test_manual_and_chat_share_catalog_selected_flight_and_immutable_private_pdf(connected_app,tmp_path):  # noqa: F811
    client,_=connected_app
    headers=user(client,"book_builder");other=user(client,"book_intruder");path=trip(client,headers)
    work=draft(client,headers,path)
    assert {"Kochi","Munnar","Alleppey"} <= {s["location"] for s in work["options"]["stays"]}
    assert work["options"]["flights"]
    chosen=work["options"]["flights"][0]
    response=client.post(path+"/selections",headers=headers,json={"expected_revision":work["revision"],"kind":"flight","item_id":chosen["id"]})
    assert response.status_code==200,response.text
    work=response.json()
    result=confirm(client,headers,path,work)
    preview=client.get(path+"/travel-book",headers=headers)
    assert preview.status_code==200,preview.text
    data=preview.json()
    assert data["flight"]["id"]==chosen["id"]
    assert data["budget"]["total_inr"]==result["orchestration"]["budget"]["total_inr"]+chosen["price_inr"]*2
    assert all("confirmed" not in s["status"].lower() for s in [data["stay"]] if s)
    created=client.post(path+"/travel-books",headers=headers)
    assert created.status_code==201,created.text
    pdf_url=created.json()["download_url"]
    pdf=client.get(pdf_url,headers=headers)
    assert pdf.status_code==200 and pdf.content.startswith(b"%PDF-")
    assert pdf.headers["content-type"]=="application/pdf"
    (tmp_path/"travel_book.pdf").write_bytes(pdf.content)
    assert client.get(pdf_url,headers=other).status_code==404
    assert client.get(path+"/workspace",headers=other).status_code==404
    assert client.post(path+"/travel-books",headers=other).status_code==404
    duplicate=client.post(path+"/travel-books",headers=headers)
    assert duplicate.json()["id"]==created.json()["id"]
    current=client.get(path+"/workspace",headers=headers).json()
    response=client.put(path+"/workspace",headers=headers,json={"expected_revision":current["revision"],"draft":dict(current["draft"],budget=90000)})
    assert response.status_code==200
    assert client.get(path+"/travel-book",headers=headers).status_code==409
    assert hashlib.sha256(client.get(pdf_url,headers=headers).content).digest()==hashlib.sha256(pdf.content).digest()


def test_invalid_model_updates_and_provider_failure_preserve_draft(connected_app,monkeypatch):  # noqa: F811
    from app import journey
    client,_=connected_app;headers=user(client,"invalid_chat");path=trip(client,headers)
    work=draft(client,headers,path)
    model=ChatModel(dict(reply="Invalid invented plan",updates={"budget":-5,"destination":"Imaginary Island"},cards=[{"kind":"stay","id":999999}]),None)
    monkeypatch.setattr(journey,"get_nim_client",lambda:model)
    failed=chat(client,headers,path,"Change my trip")
    assert failed["status"]=="needs_clarification"
    assert failed["workspace"]["draft"]==work["draft"]
    unavailable=chat(client,headers,path,"Try again")
    assert unavailable["status"]=="unavailable"
    assert unavailable["workspace"]["draft"]==work["draft"]
    assert unavailable["cards"]==[]


def test_unsupported_conditions_and_stale_edit_cannot_generate_a_book(connected_app):  # noqa: F811
    client,_=connected_app;headers=user(client,"conditions");path=trip(client,headers)
    work=draft(client,headers,path)
    bad=client.put(path+"/workspace",headers=headers,json={"expected_revision":1,"draft":work["draft"]})
    assert bad.status_code==409
    response=client.put(path+"/workspace",headers=headers,json={"expected_revision":work["revision"],"draft":dict(work["draft"],hard_requirements=["verified step-free access"])})
    assert response.status_code==200
    paused=client.post(path+"/confirm",headers=headers,json={"expected_revision":response.json()["revision"],"mode":"manual"})
    assert paused.status_code==422
    assert client.post(path+"/travel-books",headers=headers).status_code==409


def test_readonly_chat_keeps_a_confirmed_plan_current(connected_app,monkeypatch):  # noqa: F811
    from app import journey
    client,_=connected_app;headers=user(client,"readonly_chat");path=trip(client,headers)
    work=draft(client,headers,path);confirm(client,headers,path,work)
    before=client.get(path+"/workspace",headers=headers).json()
    model=ChatModel(dict(reply="Here is your saved estimate.",updates={},cards=[]))
    monkeypatch.setattr(journey,"get_nim_client",lambda:model)
    preview=client.get(path+"/travel-book",headers=headers).json()
    after=chat(client,headers,path,"Show my current budget without changing my trip")
    assert after["workspace"]["revision"]==before["revision"]
    assert after["workspace"]["plan_ready"]
    assert after["estimate"]["budget"]==preview["budget"]
    assert f"Total: INR {preview['budget']['total_inr']:,}" in after["reply"]
    import json
    context=json.loads(model.requests[1][0][1]["content"])
    assert context["authoritative_estimate"]["budget"]==preview["budget"]
    plan=client.get(path+"/plan",headers=headers).json()
    stay_options=next(r["stay_options"] for r in plan["plan"]["agent_results"] if r["agent_id"]=="stay_agent")
    assert len(stay_options)>1
    changed=client.post(path+"/plan/edits",headers=headers,json={"expected_version":plan["version"],"action":"stay","candidate":1})
    assert changed.status_code==200,changed.text
    current=client.get(path+"/workspace",headers=headers).json()
    assert current["selections"]["stay"]==stay_options[1]["stay_id"]
    assert client.get(path+"/travel-book",headers=headers).json()["stay"]["id"]==current["selections"]["stay"]


def test_model_does_not_decide_end_date_arithmetic(connected_app,monkeypatch):  # noqa: F811
    from app import journey
    client,_=connected_app;headers=user(client,"date_arithmetic");path=trip(client,headers)
    model=ChatModel(dict(reply="Please review your five-day trip.",updates={"destination":"Kerala","duration_days":5,"start_date":"2026-12-12","end_date":"2026-12-17"},cards=[]))
    monkeypatch.setattr(journey,"get_nim_client",lambda:model)
    response=chat(client,headers,path,"Start 12 December 2026 for five days in Kerala")
    assert response["workspace"]["draft"]["end_date"]=="2026-12-16"
    assert response["workspace"]["draft"]["duration_days"]==5
