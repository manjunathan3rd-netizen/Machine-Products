"""
End-to-end smoke tests against a running instance of the API.
Run: python3 -m pytest tests/test_api.py -v   (or just: python3 tests/test_api.py)
Requires the server already running: python3 -m app.main
"""
import requests

BASE = "http://127.0.0.1:5055"


def test_health():
    r = requests.get(f"{BASE}/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_generate_schedule_uses_exact_solver_by_default():
    r = requests.post(f"{BASE}/api/schedule/generate")
    body = r.json()
    assert r.status_code == 200
    assert "milp" in body["engine_used"]
    assert body["order_count"] == len(body["schedule"])


def test_disruption_then_repair_roundtrip():
    r = requests.post(f"{BASE}/api/schedule/disrupt")
    assert r.status_code == 200
    broken_id = r.json()["broken_machine"]["id"]

    machines = requests.get(f"{BASE}/api/machines").json()
    assert any(m["id"] == broken_id and m["status"] == "broken" for m in machines)

    r2 = requests.post(f"{BASE}/api/machines/repair-all")
    assert all(m["status"] == "available" for m in r2.json())


def test_explain_returns_grounded_text():
    orders = requests.get(f"{BASE}/api/orders").json()
    target = orders[0]["id"]
    r = requests.post(f"{BASE}/api/ai/explain", json={"order_id": target})
    assert r.status_code == 200
    assert target in r.json()["explanation"]


def test_whatif_does_not_mutate_real_state():
    before = len(requests.get(f"{BASE}/api/machines").json())
    requests.post(f"{BASE}/api/schedule/simulate", json={"action": "add_machine", "machine_type": "cutting"})
    after = len(requests.get(f"{BASE}/api/machines").json())
    assert before == after


def test_failure_risk_flags_broken_machine_higher():
    machines = requests.get(f"{BASE}/api/machines").json()
    mid = machines[0]["id"]
    requests.patch(f"{BASE}/api/machines/{mid}/status", json={"status": "broken"})
    risky = requests.get(f"{BASE}/api/ml/machine-failure-risk/{mid}").json()
    requests.patch(f"{BASE}/api/machines/{mid}/status", json={"status": "available"})
    assert risky["risk_pct"] > 50


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
