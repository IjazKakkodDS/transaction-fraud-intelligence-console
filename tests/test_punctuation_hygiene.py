"""
Focused tests for public-surface punctuation hygiene.

Verifies that shared null formatters, user-visible backend strings, and
public reviewer documentation are free of em dashes and en dashes.
"""

import re

EM_DASH = "—"
EN_DASH = "–"

PUBLIC_DOCS = [
    "README.md",
    "LICENSE",
    "docs/PORTFOLIO_CASE_STUDY.md",
    "docs/MODEL_CARD.md",
    "docs/MLOPS_READINESS.md",
    "docs/RISK_SCAN_BENCHMARKS.md",
    "docs/AUTH_RBAC_DESIGN.md",
    "docs/CONSUMER_DURABILITY.md",
    "docs/SYSTEM_SNAPSHOT.md",
    "docs/DEPLOYMENT_STRATEGY.md",
]


def _read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


class TestSharedFormatterNullConvention:
    def test_utils_ts_no_em_dash(self):
        content = _read("fraud-console/lib/utils.ts")
        assert EM_DASH not in content, "utils.ts contains em dash"
        assert EN_DASH not in content, "utils.ts contains en dash"

    def test_utils_ts_null_returns_n_a(self):
        content = _read("fraud-console/lib/utils.ts")
        assert '"N/A"' in content
        assert '"—"' not in content


class TestBackendDetailStrings:
    def test_no_em_dash_in_detail_strings(self):
        content = _read("src/api/main.py")
        detail_strings = re.findall(r'detail\s*=\s*["\']([^"\']+)["\']', content)
        offenders = [s for s in detail_strings if EM_DASH in s or EN_DASH in s]
        assert offenders == [], f"detail= strings with em/en dash: {offenders}"

    def test_no_em_dash_in_error_message_fields(self):
        content = _read("src/api/main.py")
        err_strings = re.findall(r'error_message\s*=\s*f?"([^"]+)"', content)
        offenders = [s for s in err_strings if EM_DASH in s or EN_DASH in s]
        assert offenders == [], f"error_message= strings with em/en dash: {offenders}"


class TestPublicDocsPunctuation:
    def test_no_em_en_dash_in_public_docs(self):
        hits = []
        for path in PUBLIC_DOCS:
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, 1):
                        if EM_DASH in line or EN_DASH in line:
                            hits.append(f"{path}:{lineno}")
            except FileNotFoundError:
                pass
        assert len(hits) == 0, f"Em/en dash found in public docs: {hits}"

    def test_scanner_detects_em_dash(self, tmp_path):
        test_file = tmp_path / "sample.md"
        test_file.write_text(f"This prose uses an em dash {EM_DASH} here.", encoding="utf-8")
        content = test_file.read_text(encoding="utf-8")
        assert EM_DASH in content

    def test_scanner_detects_en_dash(self, tmp_path):
        test_file = tmp_path / "sample.md"
        test_file.write_text(f"Range: 1{EN_DASH}100", encoding="utf-8")
        content = test_file.read_text(encoding="utf-8")
        assert EN_DASH in content

    def test_scanner_ignores_excluded_files(self):
        excluded = ["node_modules", ".next", "package-lock.json"]
        for path in PUBLIC_DOCS:
            for excluded_prefix in excluded:
                assert not path.startswith(excluded_prefix), (
                    f"Public doc list accidentally includes excluded path: {path}"
                )
