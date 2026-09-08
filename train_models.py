"""
Trains the two ML models used by the prediction service:

1. Delay-risk classifier (RandomForestClassifier)
   Predicts probability an order misses its deadline from operational
   features: slack hours, machine queue depth, tier, duration, material
   shortage flag. Trained on a synthetic-but-structurally-realistic dataset
   generated from the same distributions the scheduling demo uses, so the
   model reflects real relationships (tight slack + long queue + material
   shortage => high delay probability) rather than random noise.

2. Machine failure-risk detector (IsolationForest)
   Trained on synthetic sensor telemetry (vibration, temperature, runtime
   hours since last service) to flag machines operating outside their
   normal envelope — the predictive-maintenance signal shown on the
   dashboard.

Run: python -m ml.train_models
Outputs: ml/models/delay_risk_model.pkl, ml/models/failure_risk_model.pkl
"""
import os
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(MODELS_DIR, exist_ok=True)
RNG = np.random.default_rng(42)


def generate_delay_training_data(n=4000):
    tier_code = RNG.integers(0, 4, n)                       # 0=platinum..3=standard
    slack_hours = RNG.uniform(-8, 30, n)                     # deadline - naive_finish
    queue_depth = RNG.integers(0, 8, n)                      # orders ahead on same machine
    duration = RNG.uniform(1, 10, n)
    material_shortage = RNG.integers(0, 2, n)
    worker_available = RNG.integers(0, 2, n)

    # ground-truth generating process (structural, not label leakage from a trivial rule)
    risk_logit = (
        -0.35 * slack_hours
        + 0.9 * queue_depth
        + 0.4 * duration
        + 2.2 * material_shortage
        + 1.1 * (1 - worker_available)
        + 0.3 * tier_code
        + RNG.normal(0, 1.4, n)
    )
    prob = 1 / (1 + np.exp(-0.22 * (risk_logit - 2)))
    y = (RNG.uniform(0, 1, n) < prob).astype(int)

    X = np.column_stack([tier_code, slack_hours, queue_depth, duration, material_shortage, worker_available])
    return X, y


def generate_failure_training_data(n_normal=1500, n_anomalous=80):
    # normal operating envelope
    vibration = RNG.normal(3.0, 0.6, n_normal)
    temperature = RNG.normal(55, 5, n_normal)
    runtime_since_service = RNG.uniform(0, 400, n_normal)
    normal = np.column_stack([vibration, temperature, runtime_since_service])

    # anomalous: elevated vibration/temperature and/or long overdue service
    vibration_a = RNG.normal(6.5, 1.2, n_anomalous)
    temperature_a = RNG.normal(78, 8, n_anomalous)
    runtime_a = RNG.uniform(350, 900, n_anomalous)
    anomalous = np.column_stack([vibration_a, temperature_a, runtime_a])

    X = np.vstack([normal, anomalous])
    return X


def train_delay_model():
    X, y = generate_delay_training_data()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    model = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42, class_weight="balanced")
    model.fit(X_train, y_train)
    report = classification_report(y_test, model.predict(X_test), digits=3)
    print("=== Delay-risk model evaluation (held-out test set) ===")
    print(report)
    joblib.dump(model, os.path.join(MODELS_DIR, "delay_risk_model.pkl"))
    return model, report


def train_failure_model():
    X = generate_failure_training_data()
    model = IsolationForest(n_estimators=200, contamination=0.05, random_state=42)
    model.fit(X)
    joblib.dump(model, os.path.join(MODELS_DIR, "failure_risk_model.pkl"))
    print("=== Machine failure-risk model trained (IsolationForest) ===")
    print(f"Trained on {X.shape[0]} synthetic sensor readings, contamination=0.05")
    return model


if __name__ == "__main__":
    train_delay_model()
    train_failure_model()
    print(f"\nModels saved to {MODELS_DIR}")
