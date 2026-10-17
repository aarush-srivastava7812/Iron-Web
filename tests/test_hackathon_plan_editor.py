from tests.test_application_integration import connected_app, user, trip, requirements, plan  # noqa: F401


def test_saved_plan_edit_reprice_restore_ownership_and_stale_requirements(connected_app):  # noqa: F811
    client, _ = connected_app
    headers = user(client)
    path = trip(client, headers)
    requirements(client, headers, path)
    result = plan(client, headers, path)
    assert result["orchestration"]["status"] == "ok", result
    original = client.get(path + "/plan", headers=headers).json()
    assert original["version"] == 1
    other = user(client, "other_editor")
    assert client.get(path + "/plan", headers=other).status_code == 404
    assert client.post(path + "/plan/edits", headers=other, json={"expected_version":1,"action":"remove"}).status_code == 404
    edit = {"expected_version":1, "action":"remove", "day":1, "stop":0}
    response = client.post(path + "/plan/edits", headers=headers, json=edit)
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["version"] == 2
    assert updated["plan"]["budget"]["total_inr"] < original["plan"]["budget"]["total_inr"]
    assert updated["plan"]["delta_inr"] < 0
    assert len(updated["history"]) == 2
    assert client.get(path + "/plan", headers=headers).json()["version"] == 2
    assert client.post(path + "/plan/edits", headers=headers, json=edit).status_code == 409
    forged = dict(edit, expected_version=2, total_inr=1)
    assert client.post(path + "/plan/edits", headers=headers, json=forged).status_code == 422
    restore = {"expected_version":2,"action":"restore","candidate":1}
    response = client.post(path + "/plan/edits", headers=headers, json=restore)
    assert response.status_code == 200, response.text
    restored = response.json()
    assert restored["version"] == 3
    assert restored["plan"]["budget"]["total_inr"] == original["plan"]["budget"]["total_inr"]
    requirements(client, headers, path, budget=80000)
    assert client.get(path + "/plan", headers=headers).json()["stale"]
    assert client.post(path + "/plan/edits", headers=headers,
                       json=dict(edit, expected_version=3)).status_code == 409
