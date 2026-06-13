# Model Card — Baseline Fraud Scoring Model

## 1. Model Overview

| Property | Value |
|---|---|
| Model name | Baseline Fraud Scoring Model |
| Artifact path | `saved_models/fraud_model.pkl` |
| Model type | `XGBClassifier` (XGBoost gradient-boosted decision trees) |
| Intended use | Baseline fraud risk scoring within the Fraud Intelligence Console pipeline |
| Role in system | One component of the hybrid 4-layer scoring engine; produces a base probability estimate that is combined with deterministic rule signals, rich-feature boosts, behavioural intelligence boosts, and graph intelligence boosts before the final risk score is computed |
| Enforcement | The model does not autonomously enforce decisions; all fraud decisions are subject to analyst-in-the-loop review and verdict capture |

---

## 2. Artifact Details

| Property | Value |
|---|---|
| File | `saved_models/fraud_model.pkl` |
| Serialisation format | joblib pickle (`XGBClassifier`) |
| Approximate size | 106 KB |
| MD5 | `887033d57056c6a22480c0b9cea202ca` |
| SHA256 prefix | `bdd6a72ce2aca237...` |
| Tracked in git | Yes — intentionally tracked because the artifact is small, deterministic, and required for fresh-clone Docker runtime |

**Deterministic rebuild path:**

```bash
# Step 1 — generate synthetic training data (deterministic, seed 42)
python data/synthetic/generate_transactions.py

# Step 2 — train model (deterministic, random_state=42)
python -m src.models.train_model

# Step 3 — rebuild Docker image with new artifact
docker compose up --build
```

Running these steps in sequence on any platform with the tracked package versions produces an identical `fraud_model.pkl`. The MD5 above serves as the verification reference.

---

## 3. Feature Schema

The model evaluates 9 binary and continuous input features derived by `src/features/transaction_features.py`:

| Feature | Type | Description |
|---|---|---|
| `amount` | Continuous | Raw transaction amount |
| `is_high_amount` | Binary | Amount exceeds high-value threshold (configurable via `HIGH_AMOUNT_THRESHOLD`) |
| `is_night_transaction` | Binary | Transaction hour falls in 00:00–05:59 UTC |
| `is_international` | Binary | Transaction country differs from registered domestic region |
| `is_high_risk_payment_method` | Binary | Payment method in high-risk set (e.g. prepaid, crypto rail) |
| `is_high_risk_country` | Binary | Transaction country in elevated-risk region list |
| `is_high_risk_merchant_category` | Binary | Merchant category in high-risk set (e.g. electronics, gaming) |
| `has_device_id` | Binary | Device identifier present in transaction payload |
| `is_mobile_device` | Binary | Device type is mobile |

Feature engineering is performed by `src/features/transaction_features.py`, which is the authoritative source for threshold values and risk sets. Feature names are stored in `model.feature_names_in_` and are validated at prediction time.

---

## 4. Training Configuration

| Property | Value |
|---|---|
| Algorithm | XGBoost (`XGBClassifier`) |
| `n_estimators` | 100 |
| `max_depth` | 4 |
| `learning_rate` | 0.1 |
| `eval_metric` | `logloss` |
| `random_state` | 42 |
| Train/test split | 80/20 |
| Split `random_state` | 42 |

---

## 5. Training Data Contract

| Property | Value |
|---|---|
| Generator source | `data/synthetic/generate_transactions.py` |
| Generated CSV | `data/synthetic/transactions.csv` |
| Rows | 1,000 synthetic transactions |
| Fraud rate | 8% (80 fraud, 920 non-fraud) |
| Generator seed | `random.seed(42)` |
| CSV git status | Intentionally gitignored — generated file, recreatable from source |
| Generator git status | Tracked — source code, not a generated artifact |

The generator produces a controlled synthetic dataset with realistic fraud signal distributions: elevated fraud rates at night, in high-risk regions, with high-risk payment methods, and at elevated amounts. It is not a representation of any institution's historical fraud population.

---

## 6. Decision System Context

The model output is not the final fraud score. The Fraud Intelligence Console applies a 4-layer scoring formula before a risk decision is issued:

```
risk_score = clip(
    base_score
    + rich_boost
    + behavioural_boost
    + graph_boost,
    upper=1.0
)
```

| Layer | Source | Notes |
|---|---|---|
| `base_score` | This model (`XGBClassifier`) × `MODEL_WEIGHT` + rule flag × `RULE_WEIGHT` | Hybrid model + deterministic rule combination |
| `rich_boost` | Enriched signal features (device trust, velocity, geolocation anomaly) | Applied when enriched context is present |
| `behavioural_boost` | Behavioural intelligence layer (Phase 13) | Account-level deviation signals |
| `graph_boost` | Graph intelligence layer (Phase 15) | Mule fan-in/fan-out, shared-device cluster signals |

Analyst-visible reason codes produced alongside the score preserve interpretability at each layer. Analyst verdict is required before any operational enforcement action.

---

## 7. Limitations and Deployment Boundary

The following constraints apply to operational deployment of this artifact:

| Constraint | Description |
|---|---|
| Training data | Controlled synthetic benchmark data; no labelled historical fraud outcomes from any institution |
| Threshold calibration | `REVIEW_THRESHOLD` and `BLOCK_THRESHOLD` require tuning against the institution's false-positive cost profile before live use |
| Model-risk review | Regulatory and risk governance review is required before deployment in a production fraud decisioning environment |
| Feature coverage | The 9-feature base vector captures transaction-level signals; account-level, network-level, and temporal drift signals are provided by the behavioural and graph intelligence layers, not by this model directly |
| No autonomous enforcement | This model does not issue enforcement actions independently; all decisions are subject to analyst-in-the-loop review |

This artifact is appropriate for: local development and integration testing, portfolio demonstration of the scoring architecture, and as a baseline reference for institution-specific model calibration exercises.

---

## 8. Governance and Reproducibility Record

| Item | Status |
|---|---|
| Artifact tracked in git | Yes — via `.gitignore` exception (`!saved_models/fraud_model.pkl`) |
| Generator tracked in git | Yes — via `.gitignore` exception (`!data/synthetic/generate_transactions.py`) |
| Generated CSV gitignored | Yes — `data/synthetic/transactions.csv` remains excluded |
| MD5 checksum documented | Yes — `887033d57056c6a22480c0b9cea202ca` |
| Rebuild deterministic | Yes — fixed seeds throughout generator and trainer |
| Analyst enforcement required | Yes — no autonomous decision enforcement |
| Model card version | Phase 20E |

Release readiness is validated by `scripts/verify_release_readiness.py`, which checks artifact presence, checksums, feature schema, and documentation completeness.
