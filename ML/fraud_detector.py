import os
import joblib
import pandas as pd

# Chargement des artefacts
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")

model = joblib.load(os.path.join(MODELS_DIR, "xgboost_model.pkl"))
iso_model = joblib.load(os.path.join(MODELS_DIR, "isolation_forest.pkl"))
label_encoders = joblib.load(os.path.join(MODELS_DIR, "label_encoders.pkl"))
feature_columns = joblib.load(os.path.join(MODELS_DIR, "feature_columns.pkl"))
threshold = joblib.load(os.path.join(MODELS_DIR, "threshold.pkl"))


def preprocess_transaction(transaction_dict):
    df = pd.DataFrame([transaction_dict])

    # timestamp preprocessing
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["year"] = df["timestamp"].dt.year
    df["month"] = df["timestamp"].dt.month
    df["day"] = df["timestamp"].dt.day
    df["hour"] = df["timestamp"].dt.hour
    # ajoute ici toute autre feature temporelle utilisée à l'entraînement (day_of_week, etc.)
    df.drop("timestamp", axis=1, inplace=True)

    # Encodage des variables catégorielles
    for col in df.select_dtypes(include=['object', 'string']).columns:
        if col in label_encoders:
            le = label_encoders[col]
            df[col] = df[col].astype(str)
            df[col] = df[col].apply(lambda x: x if x in le.classes_ else le.classes_[0])
            df[col] = le.transform(df[col])

    return df


def predict_fraud(transaction_dict):
    df = preprocess_transaction(transaction_dict)

    # Score Isolation Forest calculé
    iso_feature_columns = [c for c in feature_columns if c != 'iso_anomaly_score']
    df_iso = df.reindex(columns=iso_feature_columns, fill_value=0)
    iso_score = iso_model.decision_function(df_iso)[0]

    df['iso_anomaly_score'] = iso_score

    # Préparation pour XGBoost
    df = df.reindex(columns=feature_columns, fill_value=0)
    proba = model.predict_proba(df)[:, 1][0]
    is_fraud_alert = proba > threshold

    return {
        "is_fraud_alert": bool(is_fraud_alert),
        "fraud_probability": float(proba),
        "iso_anomaly_score": float(iso_score),
    }