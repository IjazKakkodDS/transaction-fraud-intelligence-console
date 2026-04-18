"""
Fraud risk scoring configuration.

Values are loaded from environment variables when present.
Falls back to the original hardcoded defaults so the system
behaves identically without any environment setup.
"""

import os

from dotenv import load_dotenv

load_dotenv()  # reads .env if present; no-op if the file does not exist

MODEL_WEIGHT = float(os.getenv("MODEL_WEIGHT", "0.6"))
RULE_WEIGHT = float(os.getenv("RULE_WEIGHT", "0.4"))
REVIEW_THRESHOLD = float(os.getenv("REVIEW_THRESHOLD", "0.3"))
BLOCK_THRESHOLD = float(os.getenv("BLOCK_THRESHOLD", "0.7"))
HIGH_AMOUNT_THRESHOLD = float(os.getenv("HIGH_AMOUNT_THRESHOLD", "1000"))

# Dual-path retirement flag (see docs/dual_path_retirement_plan.md).
# true  — POST /predict scores synchronously AND publishes to transactions.raw
#         (current Phase 2 behavior; two Postgres rows per transaction).
# false — POST /predict publishes to transactions.raw only and returns HTTP 202;
#         scoring-consumer becomes the sole scorer (one Postgres row per transaction).
# Toggle to false only after GET /predictions/{transaction_id} is deployed and
# all clients have migrated off the synchronous /predict response.
SYNC_SCORING_ENABLED: bool = os.getenv("SYNC_SCORING_ENABLED", "true").lower() == "true"
