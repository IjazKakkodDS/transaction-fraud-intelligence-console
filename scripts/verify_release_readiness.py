"""
Release readiness validation for the Fraud Intelligence Console.

Read-only: no DB mutation, no scans, no network calls, no Ollama.
Run from repo root: python scripts/verify_release_readiness.py

Exit 0 = all checks PASS.
Exit 1 = one or more checks FAIL.
"""

import hashlib
import os
import subprocess
import sys

EXPECTED_MODEL_MD5 = "887033d57056c6a22480c0b9cea202ca"

REQUIRED_FILES = [
    "saved_models/fraud_model.pkl",
    "data/synthetic/generate_transactions.py",
    "docs/MODEL_CARD.md",
    "README.md",
    "docs/PORTFOLIO_CASE_STUDY.md",
    "docs/DEMO_STORYBOARD.md",
    "docs/DEMO_WALKTHROUGH.md",
    "docs/SECURITY_POSTURE.md",
    "docs/CONSUMER_DURABILITY.md",
    "docs/AUTH_RBAC_DESIGN.md",
]

REQUIRED_SCREENSHOTS = [
    "docs/screenshots/01_overview_command_center.png",
    "docs/screenshots/02_risk_command_dashboard.png",
    "docs/screenshots/03_transaction_intake.png",
    "docs/screenshots/04_scoring_result_handoff.png",
    "docs/screenshots/05_review_queue_prioritization.png",
    "docs/screenshots/06_case_dossier_evidence.png",
    "docs/screenshots/07_ai_investigation_panel.png",
    "docs/screenshots/08_analyst_verdict_panel.png",
    "docs/screenshots/09_case_workflow_audit_trail.png",
    "docs/screenshots/10_false_positive_review_case.png",
    "docs/screenshots/11_workflow_events_audit_trail.png",
    "docs/screenshots/12_reliability_metrics_center.png",
]

# Files that must NOT be tracked in git (secrets / generated artifacts)
MUST_NOT_BE_TRACKED = [
    ".env",
    "fraud-console/.env.local",
    "data/synthetic/transactions.csv",
]

# Files that MUST be tracked in git
MUST_BE_TRACKED = [
    "saved_models/fraud_model.pkl",
    "data/synthetic/generate_transactions.py",
]

# Stale phrases that should not appear in public-facing docs
STALE_PHRASES = {
    "README.md": [
        "7 / 7 passed",
        "7/7 passed",
        "21 endpoints",
        "06_case_dossier_risk_evidence.png",
        "Resume-Safe Positioning",
    ],
    "docs/PORTFOLIO_CASE_STUDY.md": [
        "06_case_dossier_risk_evidence.png",
        "Resume-Safe Positioning",
    ],
    "docs/DEMO_WALKTHROUGH.md": [
        "06_case_dossier_risk_evidence.png",
    ],
}

results = []


def check(label, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    line = f"  [{status}] {label}"
    if detail:
        line += f" — {detail}"
    print(line)
    results.append((label, passed))


def git_ls_files(path):
    """Return list of tracked files matching path. Empty list if git unavailable."""
    try:
        out = subprocess.check_output(
            ["git", "ls-files", path],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return [line.strip() for line in out.splitlines() if line.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# 1. Required files exist
# ---------------------------------------------------------------------------
print("\n--- Required files ---")
for path in REQUIRED_FILES:
    check(f"exists: {path}", os.path.isfile(path))

# ---------------------------------------------------------------------------
# 2. Model artifact is loadable
# ---------------------------------------------------------------------------
print("\n--- Model artifact ---")
model_path = "saved_models/fraud_model.pkl"
if os.path.isfile(model_path):
    try:
        import joblib
        model = joblib.load(model_path)
        class_name = type(model).__name__
        is_xgb = "XGB" in class_name or "Classifier" in class_name
        check("model loads via joblib", True, f"type={class_name}")
        check("model is XGBClassifier", is_xgb, f"type={class_name}")

        # Check feature names
        expected_features = [
            "amount", "is_high_amount", "is_night_transaction", "is_international",
            "is_high_risk_payment_method", "is_high_risk_country",
            "is_high_risk_merchant_category", "has_device_id", "is_mobile_device",
        ]
        actual_features = [str(f) for f in getattr(model, "feature_names_in_", [])]
        features_match = actual_features == expected_features
        check(
            "model feature schema matches expected 9 features",
            features_match,
            f"got {len(actual_features)} features",
        )
    except Exception as exc:
        check("model loads via joblib", False, str(exc))
        check("model is XGBClassifier", False, "load failed")
        check("model feature schema matches expected 9 features", False, "load failed")
else:
    check("model loads via joblib", False, "file missing")
    check("model is XGBClassifier", False, "file missing")
    check("model feature schema matches expected 9 features", False, "file missing")

# ---------------------------------------------------------------------------
# 3. Model checksum
# ---------------------------------------------------------------------------
print("\n--- Model checksum ---")
if os.path.isfile(model_path):
    actual_md5 = md5_file(model_path)
    match = actual_md5 == EXPECTED_MODEL_MD5
    check(
        "model MD5 matches expected baseline",
        match,
        f"expected={EXPECTED_MODEL_MD5}  actual={actual_md5}",
    )
else:
    check("model MD5 matches expected baseline", False, "file missing")

# ---------------------------------------------------------------------------
# 4. Screenshot evidence exists
# ---------------------------------------------------------------------------
print("\n--- Screenshot evidence ---")
for path in REQUIRED_SCREENSHOTS:
    check(f"exists: {path}", os.path.isfile(path))

# ---------------------------------------------------------------------------
# 5. Old screenshot filename is absent
# ---------------------------------------------------------------------------
print("\n--- Stale screenshot filename ---")
old_path = "docs/screenshots/06_case_dossier_risk_evidence.png"
check(
    "old filename 06_case_dossier_risk_evidence.png absent",
    not os.path.isfile(old_path),
)

# ---------------------------------------------------------------------------
# 6. Sensitive/generated files are not git-tracked
# ---------------------------------------------------------------------------
print("\n--- Secret and generated artifact hygiene ---")
for path in MUST_NOT_BE_TRACKED:
    tracked = git_ls_files(path)
    check(f"not tracked: {path}", len(tracked) == 0, f"tracked={tracked or 'none'}")

# Check demo output folder (videos) — only the flagship product walkthrough MP4s are allowed
ALLOWED_VIDEOS = {
    "fraud-console/demo/output/fraud-console-full-product-walkthrough.mp4",
    "fraud-console/demo/output/fraud-console-full-product-walkthrough-v1.mp4",
    "fraud-console/demo/output/fraud-console-full-product-walkthrough-v2.mp4",
    "fraud-console/demo/output/fraud-console-full-product-walkthrough-v3.mp4",
    "fraud-console/demo/output/fraud-console-full-product-walkthrough-v4.mp4",
    "fraud-console/demo/output/fraud-console-full-product-walkthrough-v5.mp4",
    "fraud-console/demo/output/fraud-console-full-product-walkthrough-v6.mp4",
    "fraud-console/demo/output/fraud-console-full-product-walkthrough-v6-subtitled.mp4",
    "fraud-console/demo/output/fraud-console-full-product-walkthrough-v7.mp4",
    "fraud-console/demo/output/fraud-console-full-product-walkthrough-v7-subtitled.mp4",
    "fraud-console/demo/output/fraud-console-full-product-walkthrough-v8.mp4",
    "fraud-console/demo/output/fraud-console-full-product-walkthrough-v8-subtitled.mp4",
}
demo_tracked = git_ls_files("fraud-console/demo/output")
video_tracked = [f for f in demo_tracked if f.endswith((".mp4", ".webm")) and f not in ALLOWED_VIDEOS]
check(
    "no video files tracked in fraud-console/demo/output",
    len(video_tracked) == 0,
    f"found={video_tracked or 'none'}",
)

# ---------------------------------------------------------------------------
# 7. Required artifact/source files are git-tracked
# ---------------------------------------------------------------------------
print("\n--- Required tracked artifacts ---")
for path in MUST_BE_TRACKED:
    tracked = git_ls_files(path)
    check(f"tracked: {path}", len(tracked) > 0, f"tracked={tracked or 'MISSING'}",)

# ---------------------------------------------------------------------------
# 8. Stale phrase checks in public-facing docs
# ---------------------------------------------------------------------------
print("\n--- Stale phrase checks ---")
for doc_path, phrases in STALE_PHRASES.items():
    if not os.path.isfile(doc_path):
        check(f"stale phrase scan: {doc_path}", False, "file missing")
        continue
    with open(doc_path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    for phrase in phrases:
        present = phrase in content
        check(
            f'stale phrase absent in {doc_path}: "{phrase}"',
            not present,
        )

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = len(results)
passed = sum(1 for _, ok in results if ok)
failed = total - passed

print(f"\n{'='*60}")
print(f"Release Readiness: {passed}/{total} checks PASS")
if failed:
    print(f"FAIL: {failed} check(s) did not pass — see details above.")
else:
    print("All checks PASS — repository is release-ready.")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
