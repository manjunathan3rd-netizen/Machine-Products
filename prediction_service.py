import os
import joblib
import numpy as np

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

_delay_model = None
_failure_model = None


def _load():
    global _delay_model, _failure_model
    if _delay_model is None:
        _delay_model = joblib.load(os.path.join(MODELS_DIR, "delay_risk_model.pkl"))
    if _failure_model is None:
        _failure_model = joblib.load(os.path.join(MODELS_DIR, "failure_risk_model.pkl"))


TIER_CODE = {"platinum": 0, "gold": 1, "silver": 2, "standard": 3}


def predict_delay_probability(order: dict, queue_depth: int, worker_available: bool, material_shortage: bool) -> float:
    """Returns predicted probability (0-1) this order misses its deadline."""
    _load()
    slack_hours = order["deadline"] - order.get("naive_finish", order["deadline"])
    X = np.array([[
        TIER_CODE.get(order.get("tier", "standard"), 3),
        slack_hours,
        queue_depth,
        order["duration"],
        1 if material_shortage else 0,
        1 if worker_available else 0,
    ]])
    proba = _delay_model.predict_proba(X)[0]
    # class 1 = "will be delayed"
    idx = list(_delay_model.classes_).index(1) if 1 in _delay_model.classes_ else -1
    return float(proba[idx]) if idx >= 0 else 0.0


def predict_machine_failure_risk(vibration: float, temperature: float, runtime_since_service: float) -> dict:
    """Returns an anomaly score + boolean flag for predictive maintenance."""
    _load()
    X = np.array([[vibration, temperature, runtime_since_service]])
    raw_score = _failure_model.decision_function(X)[0]   # higher = more normal
    is_anomaly = _failure_model.predict(X)[0] == -1
    # convert to an intuitive 0-100 "risk" score (lower decision_function -> higher risk)
    risk_pct = float(np.clip((0.15 - raw_score) / 0.30 * 100, 0, 100))
    return {"risk_pct": round(risk_pct, 1), "flagged": bool(is_anomaly)}
