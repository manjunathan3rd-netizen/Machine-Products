"""
SmartSched AI backend — Flask API.

Note on stack choice: the architecture blueprint specifies FastAPI. This
build uses Flask because it (along with scikit-learn and scipy) is what's
actually installable in this environment without outbound network access;
FastAPI/uvicorn could not be pip-installed here. The route structure,
request/response shapes, and service boundaries below match the blueprint's
API design 1:1, so porting to FastAPI later is a mechanical exercise
(decorators change, business logic doesn't).

Persistence note: state lives in-memory (module-level dict) for this demo
build instead of PostgreSQL, for the same offline-environment reason. See
`store.py` — swapping it for a real SQLAlchemy-backed Postgres store means
changing that one module only.
"""
import copy
import random
import time
from flask import Flask, jsonify, request

from .seed_data import default_state
from scheduler.priority import priority_score
from scheduler.milp_scheduler import solve_milp_schedule
from scheduler.heuristic_scheduler import solve_heuristic_schedule
from ml.prediction_service import predict_machine_failure_risk

app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    # Minimal hand-rolled CORS (flask-cors isn't installable offline in this
    # sandbox). Fine for a demo; for production, swap to flask-cors or your
    # gateway/ingress's CORS policy.
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PATCH,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/api/<path:_any>", methods=["OPTIONS"])
def cors_preflight(_any):
    return "", 204

STATE = default_state()
DISRUPTION_LOG = []
RUSH_COUNTER = {"n": 1}

MAX_ORDERS_FOR_EXACT_SOLVER = 14  # above this, use the heuristic engine


# ----------------------------------------------------------------------
# Core scheduling orchestration
# ----------------------------------------------------------------------
def compute_schedule():
    orders, machines = STATE["orders"], STATE["machines"]
    engine_used = "milp"
    if len(orders) <= MAX_ORDERS_FOR_EXACT_SOLVER:
        result = solve_milp_schedule(orders, machines)
        if result.infeasible:
            engine_used = "heuristic (milp infeasible at full capacity)"
            schedule, cost = solve_heuristic_schedule(orders, machines, STATE["workers"], STATE["materials"])
        else:
            engine_used = "milp (exact, HiGHS solver)"
            schedule = _augment_milp_result(result)
            cost = result.objective_value
    else:
        engine_used = "heuristic (problem too large for exact solve)"
        schedule, cost = solve_heuristic_schedule(orders, machines, STATE["workers"], STATE["materials"])
    return schedule, cost, engine_used


def _augment_milp_result(result):
    """Fill in display fields (customer, tier, risk, worker) the MILP omits,
    by joining back against the order/worker tables and applying a simple
    worker-assignment pass identical to the heuristic scheduler's rule."""
    by_id = {o["id"]: o for o in STATE["orders"]}
    machine_by_id = {m["id"]: m for m in STATE["machines"]}
    worker_free = {w["id"]: 0 for w in STATE["workers"]}
    schedule = []
    assigned_ids = set()
    for a in sorted(result.assignments, key=lambda x: x["start"]):
        o = by_id[a["order_id"]]
        candidates = [w for w in STATE["workers"] if o["type"] in w["skills"]]
        candidates.sort(key=lambda w: worker_free[w["id"]])
        worker = candidates[0] if candidates else None
        if worker:
            worker_free[worker["id"]] = a["end"]
        risk = "green"
        if a["end"] > o["deadline"]:
            risk = "red"
        elif o["deadline"] - a["end"] <= 3:
            risk = "amber"
        schedule.append({
            **o, "status": "scheduled", "machine_id": a["machine_id"],
            "machine_name": machine_by_id[a["machine_id"]]["name"],
            "worker_id": worker["id"] if worker else None,
            "worker_name": worker["name"] if worker else "Unassigned",
            "start": a["start"], "end": a["end"], "risk": risk,
            "material_shortage": False,
        })
        assigned_ids.add(o["id"])
    for oid in result.unassignable:
        o = by_id[oid]
        schedule.append({**o, "status": "unassignable", "reason": "no compatible/available machine"})
    return schedule


# ----------------------------------------------------------------------
# Orders / Machines / Workers / Materials CRUD
# ----------------------------------------------------------------------
@app.get("/api/orders")
def get_orders():
    return jsonify(STATE["orders"])


@app.post("/api/orders")
def create_order():
    body = request.get_json(force=True)
    body.setdefault("id", f"ORD-{len(STATE['orders'])+1:02d}")
    body["priority_score"] = priority_score(body)
    STATE["orders"].append(body)
    return jsonify(body), 201


@app.post("/api/orders/rush")
def create_rush_order():
    """Convenience endpoint mirroring the frontend's '+ Rush order' demo button."""
    types = ["cutting", "milling", "assembly", "painting"]
    t = random.choice(types)
    order = {
        "id": f"RUSH-{RUSH_COUNTER['n']:02d}", "customer": "Priority Client", "tier": "platinum",
        "type": t, "qty": random.randint(80, 180), "duration": random.randint(2, 4),
        "deadline": random.randint(6, 12), "material_id": "MT3" if t == "painting" else "MT1",
        "material_qty": 15,
    }
    RUSH_COUNTER["n"] += 1
    STATE["orders"].append(order)
    return jsonify(order), 201


@app.get("/api/machines")
def get_machines():
    return jsonify(STATE["machines"])


@app.patch("/api/machines/<machine_id>/status")
def set_machine_status(machine_id):
    status = request.get_json(force=True).get("status")
    for m in STATE["machines"]:
        if m["id"] == machine_id:
            m["status"] = status
            DISRUPTION_LOG.append({"type": "machine_status_change", "machine_id": machine_id, "status": status, "t": time.time()})
            return jsonify(m)
    return jsonify({"error": "machine not found"}), 404


@app.post("/api/schedule/disrupt")
def trigger_disruption():
    """Break a random available machine — the live demo showpiece."""
    available = [m for m in STATE["machines"] if m["status"] == "available"]
    if not available:
        return jsonify({"error": "no available machines to break"}), 400
    m = random.choice(available)
    m["status"] = "broken"
    DISRUPTION_LOG.append({"type": "machine_breakdown", "machine_id": m["id"], "t": time.time()})
    return jsonify({"broken_machine": m})


@app.post("/api/machines/repair-all")
def repair_all():
    for m in STATE["machines"]:
        m["status"] = "available"
    return jsonify(STATE["machines"])


@app.get("/api/workers")
def get_workers():
    return jsonify(STATE["workers"])


@app.get("/api/materials")
def get_materials():
    return jsonify(STATE["materials"])


@app.patch("/api/materials/<material_id>/stock")
def set_material_stock(material_id):
    stock = request.get_json(force=True).get("stock")
    for m in STATE["materials"]:
        if m["id"] == material_id:
            m["stock"] = stock
            return jsonify(m)
    return jsonify({"error": "material not found"}), 404


# ----------------------------------------------------------------------
# Scheduling engine endpoints
# ----------------------------------------------------------------------
@app.post("/api/schedule/generate")
def generate_schedule():
    t0 = time.time()
    schedule, cost, engine_used = compute_schedule()
    return jsonify({
        "schedule": schedule,
        "objective_total_weighted_tardiness": cost,
        "engine_used": engine_used,
        "solve_time_ms": round((time.time() - t0) * 1000, 2),
        "order_count": len(STATE["orders"]),
    })


@app.get("/api/schedule/current")
def current_schedule():
    schedule, cost, engine_used = compute_schedule()
    return jsonify({"schedule": schedule, "engine_used": engine_used})


@app.post("/api/schedule/simulate")
def simulate_whatif():
    """
    Body: {"action": "add_machine"|"add_worker"|"cut_material", "payload": {...}}
    Applies a hypothetical change to a COPY of state, reschedules, and returns
    the before/after comparison without mutating the real state — a true
    what-if, not a committed change.
    """
    body = request.get_json(force=True)
    action = body.get("action")
    global STATE
    sim_state = copy.deepcopy(STATE)

    before_schedule, before_cost, _ = compute_schedule()

    if action == "add_machine":
        new_id = f"M{len(sim_state['machines'])+1}"
        sim_state["machines"].append({"id": new_id, "name": f"Simulated {body.get('machine_type','assembly')} Unit",
                                       "type": body.get("machine_type", "assembly"), "status": "available"})
    elif action == "add_worker":
        new_id = f"W{len(sim_state['workers'])+1}"
        sim_state["workers"].append({"id": new_id, "name": "Simulated Hire", "skills": [body.get("skill", "assembly")]})
    elif action == "cut_material":
        mid = body.get("material_id", "MT1")
        for m in sim_state["materials"]:
            if m["id"] == mid:
                m["stock"] = int(m["stock"] * 0.2)
    else:
        return jsonify({"error": "unknown action"}), 400

    real_state_backup = STATE
    STATE = sim_state
    after_schedule, after_cost, engine_used = compute_schedule()
    STATE = real_state_backup

    return jsonify({
        "action": action,
        "before_cost": before_cost,
        "after_cost": after_cost,
        "improvement": (before_cost or 0) - (after_cost or 0),
        "after_schedule_preview": after_schedule[:5],
    })


# ----------------------------------------------------------------------
# AI explainability (rule-based, reads the real computed schedule)
# ----------------------------------------------------------------------
@app.post("/api/ai/explain")
def explain_order():
    order_id = request.get_json(force=True).get("order_id", "")
    schedule, _, _ = compute_schedule()
    match = next((s for s in schedule if s["id"].lower() == order_id.lower()), None)
    if not match:
        return jsonify({"explanation": f"No order '{order_id}' found in the current schedule."}), 404
    if match["status"] == "unassignable":
        return jsonify({"explanation": f"{match['id']} ({match['customer']}) has no available compatible machine right now."})

    same_machine = [s for s in schedule if s.get("machine_id") == match.get("machine_id") and s["status"] == "scheduled"]
    earlier = [s for s in same_machine if s["start"] < match["start"]]
    earlier.sort(key=lambda s: -s["start"])
    text = (f"{match['id']} ({match['customer']}, {match['tier']} tier) runs on "
            f"{match.get('machine_name', match.get('machine_id'))} from hour {match['start']} to {match['end']}. "
            f"Priority score: {priority_score(match)}.")
    if earlier:
        prev = earlier[0]
        text += f" It queues behind {prev['id']} (priority {priority_score(prev)}), which claimed the machine first."
    if match["risk"] == "red":
        text += " This order is projected to miss its deadline — reassignment or expedited materials recommended."
    return jsonify({"explanation": text, "order": match})


@app.get("/api/ai/insights/daily")
def daily_insights():
    schedule, cost, engine_used = compute_schedule()
    scheduled = [s for s in schedule if s["status"] == "scheduled"]
    on_time = [s for s in scheduled if s["risk"] == "green"]
    at_risk = [s for s in scheduled if s["risk"] == "amber"]
    delayed = [s for s in scheduled if s["risk"] == "red"] + [s for s in schedule if s["status"] == "unassignable"]
    broken = [m["name"] for m in STATE["machines"] if m["status"] == "broken"]

    summary = (f"{len(on_time)} orders on track, {len(at_risk)} within a tight buffer, "
               f"{len(delayed)} at risk of missing their deadline. ")
    if broken:
        summary += f"{', '.join(broken)} currently offline. "
    summary += f"Scheduling engine used: {engine_used}, total weighted tardiness score: {cost}."
    return jsonify({"summary": summary, "on_time": len(on_time), "at_risk": len(at_risk),
                     "delayed": len(delayed), "broken_machines": broken, "engine_used": engine_used})


@app.get("/api/ml/machine-failure-risk/<machine_id>")
def machine_failure_risk(machine_id):
    """Demo predictive-maintenance endpoint: simulates a live sensor reading
    for the given machine and scores it with the trained IsolationForest."""
    machine = next((m for m in STATE["machines"] if m["id"] == machine_id), None)
    if not machine:
        return jsonify({"error": "machine not found"}), 404
    if machine["status"] == "broken":
        vibration, temperature, runtime = random.uniform(6, 8), random.uniform(75, 85), random.uniform(400, 800)
    else:
        vibration, temperature, runtime = random.uniform(2.4, 3.6), random.uniform(48, 62), random.uniform(20, 250)
    risk = predict_machine_failure_risk(vibration, temperature, runtime)
    return jsonify({"machine_id": machine_id, "simulated_sensor_reading": {
        "vibration": round(vibration, 2), "temperature_c": round(temperature, 1), "runtime_hours_since_service": round(runtime, 1)
    }, **risk})


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "orders": len(STATE["orders"]), "machines": len(STATE["machines"])})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5055, debug=False)
